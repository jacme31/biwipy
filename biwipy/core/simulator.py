from typing import Optional, List, Dict, Tuple
import numpy as np

from .bike_physics import (
    simulate_future_route,
    simulate_replay_route,
    estimate_P0_from_v0,
    solve_speed_for_power,
    print_power_model_info,
    RHO_STD,
    G,
)
from .cyclist_params import CyclistBehavior
from .simulation_result import (
    SimulationResult,
    DistanceAnalysis,
    TimeAnalysis,
    SpeedAnalysis,
    PowerAnalysis,
    WindAnalysis,
    GustAnalysis,
    SlopeAnalysis,
    SlopeStats,
    WindAlongTrajectoryAnalysis,
    WindAlongSegment,
    CrosswindAnalysis,
    WindScore,
    NumericStats,
)

# Import windscore calculation module
try:
    from .windscore import compute_windscore as compute_windscore_func
    WINDSCORE_AVAILABLE = True
except ImportError:
    # Fallback if windscore module not available
    WINDSCORE_AVAILABLE = False


class Simulator:
    """
    Interface publique stable pour les simulations.

    - simulate_future(): simulation prospective (prévision) → SimulationResult
    - simulate_replay(): rejeu d'un parcours (post-ride) → SimulationResult
    - P0_from_v0(): convertit une vitesse cible sur plat en puissance de référence
    - v0_from_P0(): convertit une puissance de référence en vitesse d'équilibre sur plat
    - print_power_model(): affiche le tableau des puissances adaptées par pente
    """

    def __init__(
        self,
        grib,
        behavior: Optional[CyclistBehavior] = None,
        CdA: float = 0.5,
        Cr: float = 0.004,
        m: float = 75.0,
        g: float = G,
        clip_wind: float = 40.0,
        use_yaw_cdA: bool = True,
        ratio_wind: float = 0.25,
        yaw_k: float = 0.02,
        v_max: float = 25.0,
        use_dynamic: bool = True,
        limit_speed_in_corners: bool = True,
        rho_forced: Optional[float] = None,
    ) -> None:
        self.grib = grib
        self.behavior = behavior
        self.CdA = CdA
        self.Cr = Cr
        self.m = m
        self.g = g
        self.clip_wind = clip_wind
        self.use_yaw_cdA = use_yaw_cdA
        self.ratio_wind = ratio_wind
        self.yaw_k = yaw_k
        self.v_max = v_max
        self.use_dynamic = use_dynamic
        self.limit_speed_in_corners = limit_speed_in_corners
        self.rho_forced = rho_forced

    def P0_from_v0(self, v0: float) -> float:
        """
        Calcule P0 (W) à partir d'une vitesse de référence v0 (m/s) sur plat et sans vent.

        Wrapper de ``estimate_P0_from_v0`` en utilisant les paramètres du Simulator
        (`CdA`, `Cr`, `m`, `g`, `rho_forced`).
        """
        if v0 < 0:
            raise ValueError("v0 must be >= 0 m/s")

        rho_value = self.rho_forced if self.rho_forced is not None else RHO_STD
        return estimate_P0_from_v0(v0, CdA=self.CdA, Cr=self.Cr, m=self.m, rho=rho_value, g=self.g)

    def v0_from_P0(self, P0: float) -> float:
        """
        Calcule la vitesse d'équilibre v0 (m/s) à partir d'une puissance P0 (W) sur plat et sans vent.

        Utilise ``solve_speed_for_power`` avec pente nulle et vent nul.
        """
        if P0 < 0:
            raise ValueError("P0 must be >= 0 W")

        rho_value = self.rho_forced if self.rho_forced is not None else RHO_STD
        return solve_speed_for_power(
            P=P0,
            CdA=self.CdA,
            Cr=self.Cr,
            m=self.m,
            slope=0.0,
            wind_along=0.0,
            rho=rho_value,
            g=self.g,
            v_max=self.v_max,
            behavior=self.behavior,
        )

    def print_power_model(self, P0: float) -> None:
        """
        Affiche le tableau du modèle de puissance adaptative selon la pente.

        Wrapper de ``print_power_model_info`` avec le comportement configuré
        dans le Simulator.
        """
        print_power_model_info(P0=P0, behavior=self.behavior)

    def _build_result_from_segments(self, segments: List[Dict], avg_kmh: float, P0: Optional[float], avg_power: Optional[float], t_start=None, velocity_smooth_window: int = 0) -> SimulationResult:
        """
        Build a SimulationResult from simulation output.
        
        Extracts all statistics from segments and builds the hierarchical SimulationResult structure.
        
        Parameters:
        -----------
        segments : List[Dict]
            Raw segment data from simulation
        avg_kmh : float
            Average speed in km/h
        P0 : Optional[float]
            Calibrated or computed reference power (Watts)
        avg_power : Optional[float]
            Average power (Watts)
        t_start : datetime, optional
            Start timestamp
        velocity_smooth_window : int
            Window size for moving average velocity smoothing (0=no smoothing, >0=window size).
            Applied to raw segment speeds before calculating max. Used to eliminate GPS noise artifacts.
            Default is 0 (no smoothing).
        
        Returns:
        --------
        SimulationResult
            Complete structured output
        """
        
        # ============================================================
        # DISTANCE ANALYSIS
        # ============================================================
        total_dist_km = sum(seg['distance'] for seg in segments) / 1000.0
        segment_count = len(segments)
        distance = DistanceAnalysis(total_km=total_dist_km, segment_count=segment_count)
        
        # ============================================================
        # TIME ANALYSIS
        # ============================================================
        total_time_s = sum(seg.get('time_s', 0) for seg in segments 
                          if seg.get('time_s') not in (None, float('inf')))
        total_time_min = total_time_s / 60.0
        total_time_h = total_time_min / 60.0
        time = TimeAnalysis(
            total_seconds=total_time_s,
            total_minutes=total_time_min,
            total_hours=total_time_h,
        )
        
        speed_kmh_values = [seg.get('speed_m_s', 0) * 3.6 for seg in segments]
        
        # Apply velocity smoothing if requested (e.g., to eliminate GPS timestamp noise)
        if velocity_smooth_window > 0 and len(speed_kmh_values) > velocity_smooth_window:
            speed_kmh_values_smooth = []
            for i in range(len(speed_kmh_values)):
                half_win = velocity_smooth_window // 2
                start = max(0, i - half_win)
                end = min(len(speed_kmh_values), i + half_win + 1)
                window_vals = speed_kmh_values[start:end]
                avg_speed = sum(window_vals) / len(window_vals)
                speed_kmh_values_smooth.append(avg_speed)
            speed_kmh_values = speed_kmh_values_smooth
        
        speed_min_kmh = min(speed_kmh_values) if speed_kmh_values else 0.0
        speed_max_kmh = max(speed_kmh_values) if speed_kmh_values else 0.0
        
        # Moving average (only segments with v >= 1 m/s = 3.6 km/h)
        # Calculate as time-weighted average (consistent with avg_kmh calculation)
        moving_distance = sum(seg['distance'] for seg in segments 
                             if seg.get('speed_m_s', 0) >= 1.0)
        moving_time = sum(seg.get('time_s', 0) for seg in segments 
                         if seg.get('speed_m_s', 0) >= 1.0 
                         and seg.get('time_s') not in (None, float('inf')))
        moving_avg = (moving_distance / moving_time) * 3.6 if moving_time > 0 else None  # km/h
        
        # Find position of min/max
        speed_min_at_km = 0.0
        speed_max_at_km = 0.0
        if speed_kmh_values:
            cumulative_dist = 0.0
            for i, seg in enumerate(segments):
                cumulative_dist += seg['distance'] / 1000.0
                if speed_kmh_values[i] == speed_min_kmh:
                    speed_min_at_km = cumulative_dist
                if speed_kmh_values[i] == speed_max_kmh:
                    speed_max_at_km = cumulative_dist
        
        speed = SpeedAnalysis(
            avg=avg_kmh,
            min=speed_min_kmh,
            max=speed_max_kmh,
            moving_avg=moving_avg,
        )
        
        # ============================================================
        # POWER ANALYSIS (optional)
        # ============================================================
        power = None
        if avg_power is not None:
            power_values = [seg.get('power', 0) for seg in segments]
            power = PowerAnalysis(
                avg=avg_power,
                min=min(power_values) if power_values else 0.0,
                max=max(power_values) if power_values else 0.0,
                P0_calibrated=P0,
            )
        
        # ============================================================
        # WIND ANALYSIS
        # ============================================================
        tws_values = [seg.get('tws', 0) for seg in segments]  # m/s
        twd_values = [seg.get('twd', 0) for seg in segments]  # degrees
        
        # Vectorial average of wind direction
        u_comp = np.array([seg.get('tws', 0) * np.sin(np.radians(seg.get('twd', 0))) for seg in segments])
        v_comp = np.array([seg.get('tws', 0) * np.cos(np.radians(seg.get('twd', 0))) for seg in segments])
        avg_u = np.mean(u_comp)
        avg_v = np.mean(v_comp)
        avg_twd = np.degrees(np.arctan2(avg_u, avg_v))
        if avg_twd < 0:
            avg_twd += 360.0
        
        # Cardinal direction
        compass_dirs = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
        compass_idx = int((avg_twd + 11.25) / 22.5) % 16
        twd_compass = compass_dirs[compass_idx]
        
        # Find min/max positions
        cumulative_dist = 0.0
        tws_min_at_km = 0.0
        tws_max_at_km = 0.0
        for i, seg in enumerate(segments):
            if i > 0:
                cumulative_dist += seg['distance'] / 1000.0
            if tws_values[i] == min(tws_values):
                tws_min_at_km = cumulative_dist
            if tws_values[i] == max(tws_values):
                tws_max_at_km = cumulative_dist
        
        wind = WindAnalysis(
            tws=NumericStats(
                avg=np.mean(tws_values) if tws_values else 0.0,
                min=min(tws_values) if tws_values else 0.0,
                max=max(tws_values) if tws_values else 0.0,
                min_at_km=tws_min_at_km,
                max_at_km=tws_max_at_km,
            ),
            twd_avg=avg_twd,
            twd_compass=twd_compass,
        )
        
        # ============================================================
        # GUST ANALYSIS
        # ============================================================
        gust_values = [seg.get('gust', 0) for seg in segments]  # m/s
        cumulative_dist = 0.0
        gust_min_at_km = 0.0
        gust_max_at_km = 0.0
        for i, seg in enumerate(segments):
            if i > 0:
                cumulative_dist += seg['distance'] / 1000.0
            if gust_values[i] == min(gust_values):
                gust_min_at_km = cumulative_dist
            if gust_values[i] == max(gust_values):
                gust_max_at_km = cumulative_dist
        
        gusts = GustAnalysis(
            avg=np.mean(gust_values) if gust_values else 0.0,
            min=min(gust_values) if gust_values else 0.0,
            max=max(gust_values) if gust_values else 0.0,
            min_at_km=gust_min_at_km,
            max_at_km=gust_max_at_km,
        )
        
        # ============================================================
        # SLOPE ANALYSIS
        # ============================================================
        # Terrain slopes
        slope_terrain_values = [seg.get('slope', 0) * 100 for seg in segments]  # %
        deniv_pos_terrain = sum(seg['ele2'] - seg['ele1'] for seg in segments if (seg['ele2'] - seg['ele1']) > 0)
        deniv_neg_terrain = sum(seg['ele2'] - seg['ele1'] for seg in segments if (seg['ele2'] - seg['ele1']) < 0)  # Négatif = perte d'altitude
        
        # Wind-induced virtual slopes
        slope_wind_values = [seg.get('slope_wind', 0) * 100 if seg.get('slope_wind') is not None else 0.0 for seg in segments]  # %
        elevation_virtual_values = [seg.get('elevation_virtual_m', 0) for seg in segments]  # m
        deniv_pos_virtual = sum(e for e in elevation_virtual_values if e > 0)
        deniv_neg_virtual = sum(e for e in elevation_virtual_values if e < 0)  # Négatif = vent défavorable
        
        # Effective slopes (terrain + virtual)
        slope_effective_values = [seg.get('slope_effective', 0) * 100 if seg.get('slope_effective') is not None else 0.0 for seg in segments]  # %
        deniv_pos_effective = deniv_pos_terrain + deniv_pos_virtual
        deniv_neg_effective = deniv_neg_terrain + deniv_neg_virtual
        
        slopes = SlopeAnalysis(
            terrain=SlopeStats(
                avg_pct=np.mean(slope_terrain_values) if slope_terrain_values else 0.0,
                min_pct=min(slope_terrain_values) if slope_terrain_values else 0.0,
                max_pct=max(slope_terrain_values) if slope_terrain_values else 0.0,
                deniv_pos_m=deniv_pos_terrain,
                deniv_neg_m=deniv_neg_terrain,
            ),
            virtual=SlopeStats(
                avg_pct=np.mean(slope_wind_values) if slope_wind_values else 0.0,
                min_pct=min(slope_wind_values) if slope_wind_values else 0.0,
                max_pct=max(slope_wind_values) if slope_wind_values else 0.0,
                deniv_pos_m=deniv_pos_virtual,
                deniv_neg_m=deniv_neg_virtual,
            ),
            effective=SlopeStats(
                avg_pct=np.mean(slope_effective_values) if slope_effective_values else 0.0,
                min_pct=min(slope_effective_values) if slope_effective_values else 0.0,
                max_pct=max(slope_effective_values) if slope_effective_values else 0.0,
                deniv_pos_m=deniv_pos_effective,
                deniv_neg_m=deniv_neg_effective,
            ),
        )
        
        # ============================================================
        # WIND ALONG TRAJECTORY (headwind vs tailwind)
        # ============================================================
        wind_along_values = [seg.get('wind_along', 0) * 3.6 for seg in segments]  # km/h
        total_dist_m = sum(seg['distance'] for seg in segments)
        
        # Headwind segments
        dist_headwind = 0.0
        sum_headwind_weighted = 0.0
        cumulative_dist = 0.0
        hw_min_at_km = 0.0
        hw_max_at_km = 0.0
        hw_values = []
        
        for i, seg in enumerate(segments):
            wind_along = wind_along_values[i]  # Renamed to avoid shadowing WindAnalysis object
            if wind_along > 0:  # headwind
                dist_headwind += seg['distance']
                sum_headwind_weighted += wind_along * seg['distance']
                hw_values.append(wind_along)
                if wind_along == min(hw_values) if hw_values else False:
                    hw_min_at_km = cumulative_dist
                if wind_along == max(hw_values) if hw_values else False:
                    hw_max_at_km = cumulative_dist
            cumulative_dist += seg['distance'] / 1000.0
        
        ratio_headwind = (dist_headwind / total_dist_m * 100) if total_dist_m > 0 else 0.0
        avg_headwind = (sum_headwind_weighted / dist_headwind) if dist_headwind > 0 else 0.0
        min_headwind = min(hw_values) if hw_values else 0.0
        max_headwind = max(hw_values) if hw_values else 0.0
        
        # Tailwind segments
        dist_tailwind = 0.0
        sum_tailwind_weighted = 0.0
        cumulative_dist = 0.0
        tw_min_at_km = 0.0
        tw_max_at_km = 0.0
        tw_values = []
        
        for i, seg in enumerate(segments):
            wind_along = wind_along_values[i]  # Renamed to avoid shadowing WindAnalysis object
            if wind_along < 0:  # tailwind
                dist_tailwind += seg['distance']
                sum_tailwind_weighted += wind_along * seg['distance']
                tw_values.append(wind_along)
                if wind_along == max(tw_values) if tw_values else False:  # max of negative = min in absolute
                    tw_min_at_km = cumulative_dist
                if wind_along == min(tw_values) if tw_values else False:  # min of negative = max in absolute
                    tw_max_at_km = cumulative_dist
            cumulative_dist += seg['distance'] / 1000.0
        
        ratio_tailwind = (dist_tailwind / total_dist_m * 100) if total_dist_m > 0 else 0.0
        avg_tailwind = (sum_tailwind_weighted / dist_tailwind) if dist_tailwind > 0 else 0.0
        min_tailwind = max(tw_values) if tw_values else 0.0  # less negative
        max_tailwind = min(tw_values) if tw_values else 0.0  # more negative
        
        wind_along_trajectory = WindAlongTrajectoryAnalysis(
            headwind=WindAlongSegment(
                percentage=ratio_headwind,
                distance_km=dist_headwind / 1000.0,
                avg_kmh=avg_headwind,
                min_kmh=min_headwind,
                max_kmh=max_headwind,
                min_at_km=hw_min_at_km,
                max_at_km=hw_max_at_km,
            ),
            tailwind=WindAlongSegment(
                percentage=ratio_tailwind,
                distance_km=dist_tailwind / 1000.0,
                avg_kmh=avg_tailwind,
                min_kmh=min_tailwind,
                max_kmh=max_tailwind,
                min_at_km=tw_min_at_km,
                max_at_km=tw_max_at_km,
            ),
        )
        
        # ============================================================
        # CROSSWIND ANALYSIS
        # ============================================================
        # Crosswind is perpendicular component
        crosswind_values = []
        for seg in segments:
            tws = seg.get('tws', 0)  # m/s
            twd = seg.get('twd', 0)  # degrees
            bearing = seg.get('bearing', 0)  # degrees
            
            # Angular difference
            diff = (twd - bearing) % 360
            if diff > 180:
                diff = 360 - diff
            rad_diff = np.radians(diff)
            
            # Cross-wind component (perpendicular)
            cross = tws * np.sin(rad_diff) * 3.6  # convert to km/h
            crosswind_values.append(abs(cross))  # absolute value
        
        cumulative_dist = 0.0
        cw_min_at_km = 0.0
        cw_max_at_km = 0.0
        for i, seg in enumerate(segments):
            if crosswind_values[i] == min(crosswind_values):
                cw_min_at_km = cumulative_dist
            if crosswind_values[i] == max(crosswind_values):
                cw_max_at_km = cumulative_dist
            cumulative_dist += seg['distance'] / 1000.0
        
        crosswind = CrosswindAnalysis(
            avg_kmh=np.mean(crosswind_values) if crosswind_values else 0.0,
            min_kmh=min(crosswind_values) if crosswind_values else 0.0,
            max_kmh=max(crosswind_values) if crosswind_values else 0.0,
            min_at_km=cw_min_at_km,
            max_at_km=cw_max_at_km,
        )
        
        # ============================================================
        # WIND SCORE (calibrated on 515 simulations, R²=0.826)
        # ============================================================
        if WINDSCORE_AVAILABLE:
            # Extract required parameters (all in km/h)
            wind_headwind_avg_kmh = wind_along_trajectory.headwind.avg_kmh
            wind_headwind_pct = wind_along_trajectory.headwind.percentage
            wind_tailwind_pct = wind_along_trajectory.tailwind.percentage
            gust_max_kmh = gusts.max * 3.6  # m/s → km/h
            wind_tws_avg_kmh = wind.tws.avg * 3.6  # m/s → km/h
            crosswind_avg_kmh = crosswind.avg_kmh  # already in km/h
            
            # Compute windscore using calibrated formula
            ws_result = compute_windscore_func(
                wind_headwind_avg_kmh=wind_headwind_avg_kmh,
                wind_headwind_pct=wind_headwind_pct,
                wind_tailwind_pct=wind_tailwind_pct,
                gust_max_kmh=gust_max_kmh,
                wind_tws_avg_kmh=wind_tws_avg_kmh,
                crosswind_avg_kmh=crosswind_avg_kmh,
            )
            
            wind_score = WindScore(
                grade=ws_result.grade,
                reason=ws_result.reason,
                performance_grade=ws_result.performance_grade,
                performance_score=ws_result.performance_score,
                safety_grade=ws_result.safety_grade,
                safety_danger_score=ws_result.safety_danger_score,
            )
        else:
            # Fallback if windscore module not available
            wind_score = WindScore(
                grade=None,
                reason="windscore module not available",
                performance_grade=None,
                performance_score=None,
                safety_grade=None,
                safety_danger_score=None,
            )
        
        # ============================================================
        # BUILD RESULT
        # ============================================================
        return SimulationResult(
            segments=segments,
            distance=distance,
            time=time,
            speed=speed,
            wind=wind,
            gusts=gusts,
            slopes=slopes,
            wind_along_trajectory=wind_along_trajectory,
            crosswind=crosswind,
            wind_score=wind_score,
            t_start=t_start,
            power=power,
        )

    def simulate_future(
        self,
        segments_in: List[Dict],
        t_start,
        v0: Optional[float] = None,
        P0: Optional[float] = None,
        passes: int = 2,
        velocity_smooth_window: int = 0,
    ) -> SimulationResult:
        """
        Prospective simulation (future forecast).
        
        Parameters:
        -----------
        segments_in : List[Dict]
            Route segment data
        t_start : datetime
            Start timestamp
        v0 : Optional[float]
            Initial speed (m/s)
        P0 : Optional[float]
            Reference power for simulation (Watts) - REQUIRED for forecast
        passes : int
            Number of simulation passes (default: 2)
        velocity_smooth_window : int
            Window size for velocity smoothing (default: 0, no smoothing).
            Typically not needed for prospective simulations (use for replay only).
        
        Returns:
        --------
        SimulationResult
            Complete structured output with all statistics.
            The t_start field preserves the provided timezone (typically UTC from GPX files).
        """
        segments, avg_kmh, P0_result, avg_power, t_start_extracted = simulate_future_route(
            segments_in,
            self.grib,
            t_start,
            v0=v0,
            P0=P0,
            passes=passes,
            CdA=self.CdA,
            Cr=self.Cr,
            m=self.m,
            g=self.g,
            clip_wind=self.clip_wind,
            use_yaw_cdA=self.use_yaw_cdA,
            ratio_wind=self.ratio_wind,
            yaw_k=self.yaw_k,
            v_max=self.v_max,
            use_dynamic=self.use_dynamic,
            limit_speed_in_corners=self.limit_speed_in_corners,
            rho_forced=self.rho_forced,
            behavior=self.behavior,
        )
        return self._build_result_from_segments(segments, avg_kmh, P0_result, avg_power, t_start_extracted, velocity_smooth_window=velocity_smooth_window)

    def simulate_replay(
        self,
        segments_in: List[Dict],
        t_start=None,
        passes: int = 2,
        velocity_smooth_window: int = 7,
    ) -> SimulationResult:
        """
        Replay simulation (post-ride analysis).
        
        Uses GPS timestamps to calculate power from observed speeds.
        P0 is automatically calibrated from the ride data (always enabled).
        
        Parameters:
        -----------
        segments_in : List[Dict]
            GPS segment data with timestamps and speeds
        t_start : datetime, optional
            Start timestamp. If None, will be auto-extracted from first segment's gpxtime_start.
            GPX segments must contain timestamps (gpxtime_start, gpxtime_end).
        passes : int
            Number of simulation passes (default: 2)
        velocity_smooth_window : int
            Window size for velocity smoothing to eliminate GPS timestamp noise.
            Default is 7 segments. Set to 0 to disable smoothing.
        
        Returns:
        --------
        SimulationResult
            Complete structured output with all statistics and power data.
            The t_start field will contain the auto-extracted start time (in UTC timezone).
            The P0 field contains the calibrated reference power matching observed performance.
        """
        segments, avg_kmh, P0_result, avg_power, t_start_extracted = simulate_replay_route(
            segments_in,
            self.grib,
            t_start,
            P0=None,
            passes=passes,
            CdA=self.CdA,
            Cr=self.Cr,
            m=self.m,
            g=self.g,
            clip_wind=self.clip_wind,
            use_yaw_cdA=self.use_yaw_cdA,
            ratio_wind=self.ratio_wind,
            yaw_k=self.yaw_k,
            v_max=self.v_max,
            limit_speed_in_corners=self.limit_speed_in_corners,
            rho_forced=self.rho_forced,
            behavior=self.behavior,
        )
        return self._build_result_from_segments(segments, avg_kmh, P0_result, avg_power, t_start_extracted, velocity_smooth_window=velocity_smooth_window)
