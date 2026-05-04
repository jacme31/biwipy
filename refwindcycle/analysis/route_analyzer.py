from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import math
from typing import Iterator, List, Dict, Optional, Any, Tuple

from .gpx_tools import (
    bearing,
    load_gpx_points,
    gpx_to_segments,
    compute_moving_average_from_gpx_segments,
    filter_stopped_segments,
    detect_gps_altitude_noise,
    remove_gps_altitude_noise,
)


logger = logging.getLogger(__name__)


def _interpolate_scalar(v1: float, v2: float, ratio: float) -> float:
    return float(v1) + (float(v2) - float(v1)) * ratio


def _interpolate_datetime(t1: datetime, t2: datetime, ratio: float) -> datetime:
    return t1 + (t2 - t1) * ratio


def _slice_segment_by_ratio(seg: Dict[str, Any], start_ratio: float, end_ratio: float) -> Dict[str, Any]:
    if end_ratio <= start_ratio:
        raise ValueError("Invalid segment slice: end_ratio must be > start_ratio")

    lat1 = _interpolate_scalar(seg["lat1"], seg["lat2"], start_ratio)
    lon1 = _interpolate_scalar(seg["lon1"], seg["lon2"], start_ratio)
    ele1 = _interpolate_scalar(seg.get("ele1", 0.0), seg.get("ele2", 0.0), start_ratio)

    lat2 = _interpolate_scalar(seg["lat1"], seg["lat2"], end_ratio)
    lon2 = _interpolate_scalar(seg["lon1"], seg["lon2"], end_ratio)
    ele2 = _interpolate_scalar(seg.get("ele1", 0.0), seg.get("ele2", 0.0), end_ratio)

    ratio = end_ratio - start_ratio
    distance = float(seg.get("distance", 0.0)) * ratio
    slope = ((ele2 - ele1) / distance) if distance > 0 else 0.0

    new_seg = dict(seg)
    new_seg.update(
        {
            "lat1": lat1,
            "lon1": lon1,
            "lat2": lat2,
            "lon2": lon2,
            "ele1": ele1,
            "ele2": ele2,
            "distance": distance,
            "bearing": bearing(lat1, lon1, lat2, lon2),
            "slope": slope,
        }
    )

    if "gpxtime_start" in seg and "gpxtime_end" in seg:
        t1 = seg["gpxtime_start"]
        t2 = seg["gpxtime_end"]
        if isinstance(t1, datetime) and isinstance(t2, datetime):
            new_seg["gpxtime_start"] = _interpolate_datetime(t1, t2, start_ratio)
            new_seg["gpxtime_end"] = _interpolate_datetime(t1, t2, end_ratio)

    return new_seg


def _recompute_cumulative_elevation(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    updated_segments: List[Dict[str, Any]] = []
    deniv_pos = 0.0
    deniv_neg = 0.0

    for seg in segments:
        seg_copy = dict(seg)
        dz = float(seg_copy.get("ele2", 0.0)) - float(seg_copy.get("ele1", 0.0))
        deniv_pos += max(0.0, dz)
        deniv_neg += min(0.0, dz)
        seg_copy["dcumplus"] = deniv_pos
        seg_copy["dcummoins"] = deniv_neg
        updated_segments.append(seg_copy)

    return updated_segments


def _normalize_segment_slopes(
    segments: List[Dict[str, Any]],
    short_segment_clip_dist_m: float = 10.0,
    max_abs_slope_short: float = 0.15,
    max_abs_slope_global: float = 0.25,
    debug_stats: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Normalize segment slope values with a consistent rule across pipelines.

    For short segments, clip extreme slopes that are usually interpolation/noise artifacts.
    For normal-length segments, preserve raw slope to keep real steep ramps.
    """
    normalized: List[Dict[str, Any]] = []
    clipped_short_count = 0
    clipped_global_count = 0
    micro_zeroed_count = 0
    positive_elev_loss_m = 0.0

    for seg in segments:
        s = dict(seg)
        d = float(s.get("distance", 0.0) or 0.0)
        e1 = float(s.get("ele1", 0.0) or 0.0)
        e2 = float(s.get("ele2", 0.0) or 0.0)
        raw_dz = e2 - e1

        if d <= 0.5:
            micro_zeroed_count += 1
            s["slope"] = 0.0
            s["ele2"] = e1
        else:
            raw_slope = (e2 - e1) / d
            if d < short_segment_clip_dist_m:
                clipped_short = abs(raw_slope) > max_abs_slope_short
                slope = max(-max_abs_slope_short, min(max_abs_slope_short, raw_slope))
                if clipped_short:
                    clipped_short_count += 1
            else:
                slope = raw_slope

            # Additional global guardrail to remove implausible GPS outliers
            # while preserving realistic steep ramps (e.g. ~18-20%).
            clipped_global = abs(slope) > max_abs_slope_global
            slope = max(-max_abs_slope_global, min(max_abs_slope_global, slope))
            if clipped_global:
                clipped_global_count += 1
            s["slope"] = slope
            s["ele2"] = e1 + slope * d

        new_dz = float(s.get("ele2", e1)) - e1
        positive_elev_loss_m += max(0.0, raw_dz) - max(0.0, new_dz)

        normalized.append(s)

    if debug_stats is not None:
        debug_stats.update(
            {
                "clipped_short_count": int(clipped_short_count),
                "clipped_global_count": int(clipped_global_count),
                "micro_zeroed_count": int(micro_zeroed_count),
                "positive_elev_loss_m": float(positive_elev_loss_m),
            }
        )

    return normalized


def _compute_elevation_metrics(segments: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Return compact elevation diagnostics for a segment list."""
    distance_km = sum(float(seg.get("distance", 0.0) or 0.0) for seg in segments) / 1000.0
    deniv_pos_m = 0.0
    deniv_neg_m = 0.0
    short_lt_5m = 0
    short_lt_10m = 0
    slope_min_pct = 0.0
    slope_max_pct = 0.0
    slope_values_pct: List[float] = []

    for seg in segments:
        d = float(seg.get("distance", 0.0) or 0.0)
        e1 = float(seg.get("ele1", 0.0) or 0.0)
        e2 = float(seg.get("ele2", 0.0) or 0.0)
        dz = e2 - e1
        deniv_pos_m += max(0.0, dz)
        deniv_neg_m += min(0.0, dz)

        if d < 5.0:
            short_lt_5m += 1
        if d < 10.0:
            short_lt_10m += 1

        if d > 0.5:
            slope_values_pct.append((dz / d) * 100.0)

    if slope_values_pct:
        slope_min_pct = min(slope_values_pct)
        slope_max_pct = max(slope_values_pct)

    return {
        "segment_count": len(segments),
        "distance_km": float(distance_km),
        "deniv_pos_m": float(deniv_pos_m),
        "deniv_neg_m": float(deniv_neg_m),
        "short_lt_5m": int(short_lt_5m),
        "short_lt_10m": int(short_lt_10m),
        "slope_min_pct": float(slope_min_pct),
        "slope_max_pct": float(slope_max_pct),
    }


def _compute_inclusive_integer_rectangle(points: List[Dict[str, Any]]) -> Tuple[Optional[Tuple[int, int]], Optional[Tuple[int, int]]]:
    """Return inclusive integer bounding box as (south, north), (west, east)."""
    if not points:
        return None, None

    lats = [float(p["lat"]) for p in points if "lat" in p]
    lons = [float(p["lon"]) for p in points if "lon" in p]

    if not lats or not lons:
        return None, None

    south = int(math.floor(min(lats)))
    north = int(math.ceil(max(lats)))
    west = int(math.floor(min(lons)))
    east = int(math.ceil(max(lons)))

    return (south, north), (west, east)


def cut_segments_by_km(
    segments: List[Dict[str, Any]],
    p1_km: Optional[float] = None,
    p2_km: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Keep only GPX segment portions between p1_km and p2_km."""
    if not segments:
        return []

    total_distance_m = sum(float(seg.get("distance", 0.0)) for seg in segments)
    start_m = 0.0 if p1_km is None else float(p1_km) * 1000.0
    end_m = total_distance_m if p2_km is None else float(p2_km) * 1000.0

    if start_m < 0 or end_m < 0:
        raise ValueError("p1_km and p2_km must be >= 0")
    if start_m >= end_m:
        raise ValueError("Invalid cut range: p1_km must be < p2_km")
    if end_m > total_distance_m:
        raise ValueError(
            f"p2_km ({end_m / 1000.0:.3f} km) exceeds route length ({total_distance_m / 1000.0:.3f} km)"
        )

    cut_segments: List[Dict[str, Any]] = []
    cumulative_m = 0.0

    for seg in segments:
        seg_distance = float(seg.get("distance", 0.0))
        if seg_distance <= 0:
            continue

        seg_start_m = cumulative_m
        seg_end_m = cumulative_m + seg_distance

        overlap_start_m = max(start_m, seg_start_m)
        overlap_end_m = min(end_m, seg_end_m)

        if overlap_end_m > overlap_start_m:
            start_ratio = (overlap_start_m - seg_start_m) / seg_distance
            end_ratio = (overlap_end_m - seg_start_m) / seg_distance
            cut_segments.append(_slice_segment_by_ratio(seg, start_ratio, end_ratio))

        cumulative_m = seg_end_m
        if cumulative_m >= end_m:
            break


    # --- post-traitement robuste après cut ---
    min_edge_dist_m = 8.0
    short_segment_clip_dist_m = 10.0
    max_abs_slope_short = 0.15  # Clip only suspicious short segments

    # 1) supprimer micro-segments aux bords (artefacts de découpe)
    while len(cut_segments) > 2 and float(cut_segments[0].get("distance", 0.0) or 0.0) < min_edge_dist_m:
        cut_segments = cut_segments[1:]
    while len(cut_segments) > 2 and float(cut_segments[-1].get("distance", 0.0) or 0.0) < min_edge_dist_m:
        cut_segments = cut_segments[:-1]

    # 2) même normalisation que le pipeline complet pour garantir la cohérence
    cut_segments = _normalize_segment_slopes(
        cut_segments,
        short_segment_clip_dist_m=short_segment_clip_dist_m,
        max_abs_slope_short=max_abs_slope_short,
        max_abs_slope_global=0.25,
    )

    return _recompute_cumulative_elevation(cut_segments)


@dataclass
class GPXProcessingResult:
    """
    Result from GPX processing with route segments and temporal metadata.
    
    Attributes:
    -----------
    segments : List[Dict[str, Any]]
        Processed route segments with geometry, elevation, and optional timestamps
    stats : Dict[str, Any]
        Processing statistics (merged segments, GPS noise removed, etc.)
    has_timestamps : bool
        True if GPX file contains timestamp data
    t_start : Optional[datetime]
        Start time in UTC timezone (extracted from GPX)
    t_end : Optional[datetime]
        End time in UTC timezone (extracted from GPX)
    duration : Optional[timedelta]
        Total route duration
    
    Example:
    --------
    >>> from refwindcycle.analysis.route_analyzer import RouteAnalyzer
    >>> from refwindcycle.weather import WeatherProvider
    >>> from refwindcycle.weather.grib_finder import build_grib_list
    >>> 
    >>> # Load GPX and extract temporal info
    >>> analyzer = RouteAnalyzer()
    >>> result = analyzer.process_gpx('route.gpx')
    >>> 
    >>> # Check timestamps and load appropriate GRIB files
    >>> if result.has_timestamps:
    >>>     # Convert duration to hours (round up)
    >>>     duration_hours = int(result.duration.total_seconds() / 3600) + 1
    >>>     gribs = build_grib_list(data_dir, result.t_start, step=1, duration_hours=duration_hours)
    >>>     weather = WeatherProvider(gribs, bcache=True)
    >>> else:
    >>>     weather = None  # No-wind simulation
    >>> 
    >>> # Simulate with auto-extracted t_start
    >>> sim = Simulator(weather.grib if weather else None, CdA=0.3, Cr=0.005, m=75)
    >>> sim_result = sim.simulate_replay(result.segments)  # t_start auto-extracted
    """
    segments: List[Dict[str, Any]]
    stats: Dict[str, Any]
    has_timestamps: bool = False
    t_start: Optional[datetime] = None  # Start time (UTC timezone from GPX)
    t_end: Optional[datetime] = None    # End time (UTC timezone from GPX)
    duration: Optional[timedelta] = None  # Total duration

    @property
    def distance_m(self) -> float:
        """Total distance in meters."""
        return sum(float(seg.get("distance", 0.0)) for seg in self.segments)

    @property
    def distance_km(self) -> float:
        """Total distance in kilometers."""
        return self.distance_m / 1000.0

    def cut(self, p1_km: Optional[float] = None, p2_km: Optional[float] = None) -> "GPXProcessingResult":
        """
        Extract a portion of the route between two kilometer markers.
        
        Parameters:
        -----------
        p1_km : Optional[float]
            Start position in kilometers (None = from beginning)
        p2_km : Optional[float]
            End position in kilometers (None = to end)
            
        Returns:
        --------
        GPXProcessingResult
            New result object with cut segments and updated stats
        """
        cut_segs = cut_segments_by_km(self.segments, p1_km=p1_km, p2_km=p2_km)
        
        # Extract temporal information from cut segments
        has_timestamps = False
        t_start = None
        t_end = None
        duration = None
        
        if cut_segs and 'gpxtime_start' in cut_segs[0] and 'gpxtime_end' in cut_segs[-1]:
            t_start = cut_segs[0]['gpxtime_start']
            t_end = cut_segs[-1]['gpxtime_end']
            # Only set has_timestamps if values are not None
            if t_start is not None and t_end is not None:
                has_timestamps = True
                duration = t_end - t_start
        
        return GPXProcessingResult(
            segments=cut_segs,
            stats=self.stats,
            has_timestamps=has_timestamps,
            t_start=t_start,
            t_end=t_end,
            duration=duration
        )

    def __iter__(self) -> Iterator[Any]:
        """Backward compatibility: allows segments, stats = process_gpx(...)."""
        yield self.segments
        yield self.stats


class RouteAnalyzer:
    """
    Stable public interface for GPX pre-processing and route analysis.

    Individual methods (for flexibility):
    - load_gpx(): load GPS points
    - segments_from_gpx(): create segments (with smoothing)
    - merge_segments(): merge short segments
    - moving_average_kmh(): moving average speed in km/h
    - filter_stops(): remove stops (v < threshold)

    Full workflow (convenience):
    - process_gpx(): wraps the entire GPX cleaning pipeline
    """

    def __init__(
        self,
        smoothing_window: int = 11,
        smoothing_method: str = "mediane",
        merge_min_distance: float = 50.0,
        merge_max_bearing_diff: float = 20.0,
        merge_max_slope_diff: float = 0.10,
        merge_max_slope: float = 0.15,
    ) -> None:
        self.smoothing_window = smoothing_window
        self.smoothing_method = smoothing_method
        self.merge_min_distance = merge_min_distance
        self.merge_max_bearing_diff = merge_max_bearing_diff
        self.merge_max_slope_diff = merge_max_slope_diff
        self.merge_max_slope = merge_max_slope

    def load_gpx(self, gpx_file: str) -> List[Dict[str, Any]]:
        return load_gpx_points(gpx_file)

    def segments_from_gpx(self, points: List[Dict[str, Any]], smooth: bool = True) -> List[Dict]:
        return gpx_to_segments(
            points,
            smooth=smooth,
            smoothing_window=self.smoothing_window,
            smoothing_method=self.smoothing_method,
        )

    def merge_segments(self, segments: List[Dict], verbose: bool = True) -> Tuple[List[Dict], int]:
        from .anareswind import merge_short_segments

        return merge_short_segments(
            segments,
            min_distance=self.merge_min_distance,
            max_bearing_diff=self.merge_max_bearing_diff,
            max_slope_diff=self.merge_max_slope_diff,
            max_slope=self.merge_max_slope,
            verbose=verbose,
        )

    def moving_average_kmh(self, segments: List[Dict], speed_threshold: float = 1.0) -> float:
        return compute_moving_average_from_gpx_segments(segments, speed_threshold=speed_threshold)

    def filter_stops(self, segments: List[Dict], speed_threshold: float = 1.0, verbose: bool = True) -> List[Dict]:
        return filter_stopped_segments(segments, speed_threshold=speed_threshold, verbose=verbose)

    def process_gpx(
        self,
        gpx_file: str,
        smooth: bool = True,
        detect_noise: bool = True,
        remove_noise: bool = True,
        merge_segments_flag: bool = True,
        filter_stops_flag: bool = False,
        debug_elevation_pipeline: bool = False,
        max_dist_noise: float = 5.0,
        min_slope_threshold_noise: float = 0.10,
        normal_slope_threshold_noise: float = 0.05,
        log_file: Optional[str] = None,
        verbose: bool = True,
    ) -> GPXProcessingResult:
        """
        Run the full GPX cleanup pipeline and return a structured result.

        The returned object provides:
        - segments: List of processed segments
        - stats: Dictionary with processing statistics
        - distance_km: Total distance property
        - cut(p1_km, p2_km): Method to extract a portion of the route

        Example:
        --------
        >>> analyzer = RouteAnalyzer()
        >>> result = analyzer.process_gpx('route.gpx')
        >>> print(f\"Total: {result.distance_km:.1f} km\")
        >>> cut_result = result.cut(p1_km=5.0, p2_km=15.0)
        >>> print(f\"Cut: {cut_result.distance_km:.1f} km\")

        Backward-compatible tuple unpacking is preserved:
        >>> segments, stats = analyzer.process_gpx('route.gpx')
        """
        stats: Dict[str, Any] = {}
        elevation_pipeline: List[Dict[str, Any]] = []

        def _push_stage(stage_name: str, extra: Optional[Dict[str, Any]] = None) -> None:
            if not debug_elevation_pipeline:
                return
            row = {"stage": stage_name}
            row.update(_compute_elevation_metrics(segments))
            if extra:
                row.update(extra)
            elevation_pipeline.append(row)

        if verbose:
            logger.info("\n%s", "=" * 70)
            logger.info("  GPX CLEANUP: %s", gpx_file)
            logger.info("%s", "=" * 70)
            logger.info("[1/6] Loading GPX file...")
        points = self.load_gpx(gpx_file)

        if verbose:
            logger.info("[2/6] Creating segments (smooth=%s)...", smooth)
        segments = self.segments_from_gpx(points, smooth=smooth)
        _push_stage("after_segments_from_gpx")
        rectangle_sn, rectangle_ew = _compute_inclusive_integer_rectangle(points)
        stats["rectangle_SN"] = rectangle_sn
        stats["rectangle_EW"] = rectangle_ew
        stats["segment_count_initial"] = len(segments)
        stats["distance_km_initial"] = sum(float(seg.get("distance", 0.0)) for seg in segments) / 1000.0
        stats["deniv_pos_initial"] = sum(
            seg["ele2"] - seg["ele1"]
            for seg in segments
            if seg["ele2"] - seg["ele1"] > 0
        )
        if verbose:
            logger.info("      %s segments created, elevation gain: %.1f m", len(segments), stats['deniv_pos_initial'])

        stats["gps_noise_count"] = 0
        stats["gps_noise_removed"] = 0
        if detect_noise:
            if verbose:
                logger.info("[3/6] Detecting GPS noise...")
            gps_noise = detect_gps_altitude_noise(
                segments,
                max_dist=max_dist_noise,
                min_slope_threshold=min_slope_threshold_noise,
                normal_slope_threshold=normal_slope_threshold_noise,
                log_file=log_file,
            )
            stats["gps_noise_count"] = len(gps_noise)

            if gps_noise and remove_noise:
                if verbose:
                    logger.warning("      %s abnormal segments detected", len(gps_noise))
                    logger.info("      Removing noise...")
                segments = remove_gps_altitude_noise(
                    segments,
                    max_dist=max_dist_noise,
                    min_slope_threshold=min_slope_threshold_noise,
                    normal_slope_threshold=normal_slope_threshold_noise,
                    verbose=False,
                )
                stats["gps_noise_removed"] = len(gps_noise)
                _push_stage("after_remove_gps_noise", {"gps_noise_removed": len(gps_noise)})
            elif gps_noise and not remove_noise:
                if verbose:
                    logger.warning("      %s abnormal segments detected (not removed)", len(gps_noise))
                _push_stage("after_noise_detected_not_removed", {"gps_noise_detected": len(gps_noise)})
            else:
                if verbose:
                    logger.info("      No abnormal segment detected")
                _push_stage("after_noise_detection_no_changes")
        else:
            if verbose:
                logger.info("[3/6] GPS noise detection: disabled")
            _push_stage("after_noise_step_disabled")

        stats["merged_count"] = 0
        if merge_segments_flag:
            if verbose:
                logger.info("[4/6] Merging short segments (min_dist=%sm)...", self.merge_min_distance)
            segments, n_merged = self.merge_segments(segments, verbose=False)
            stats["merged_count"] = n_merged
            _push_stage("after_merge_short_segments", {"merged_count": n_merged})
            if verbose:
                logger.info("      %s segments merged", n_merged)
        else:
            if verbose:
                logger.info("[4/6] Segment merging: disabled")
            _push_stage("after_merge_step_disabled")

        stats["stopped_count"] = 0
        if filter_stops_flag:
            if verbose:
                logger.info("[5/6] Filtering stopped segments (v < 1 m/s)...")
            try:
                segments_before = len(segments)
                segments = self.filter_stops(segments, speed_threshold=1.0, verbose=False)
                stats["stopped_count"] = segments_before - len(segments)
                _push_stage("after_filter_stops", {"stopped_count": stats["stopped_count"]})
                if verbose:
                    logger.info("      %s stopped segments filtered", stats['stopped_count'])
            except (TypeError, KeyError):
                if verbose:
                    logger.warning("      Stop filtering skipped (missing GPX timestamps)")
                stats["stopped_count"] = 0
                _push_stage("after_filter_stops_skipped")
        else:
            if verbose:
                logger.info("[5/6] Stop filtering: disabled")
            _push_stage("after_filter_stops_disabled")

        # Apply the same slope normalization rule used by cut() for consistency.
        norm_debug: Dict[str, Any] = {}
        segments = _normalize_segment_slopes(
            segments,
            short_segment_clip_dist_m=10.0,
            max_abs_slope_short=0.15,
            max_abs_slope_global=0.25,
            debug_stats=norm_debug if debug_elevation_pipeline else None,
        )
        _push_stage("after_normalize_segment_slopes", norm_debug)

        stats["segment_count_final"] = len(segments)
        stats["distance_km_final"] = sum(float(seg.get("distance", 0.0)) for seg in segments) / 1000.0
        stats["distance_km"] = stats["distance_km_final"]
        stats["deniv_pos_final"] = sum(
            seg["ele2"] - seg["ele1"]
            for seg in segments
            if seg["ele2"] - seg["ele1"] > 0
        )
        if debug_elevation_pipeline:
            stats["elevation_pipeline"] = elevation_pipeline

        # Extract temporal information from segments (if present)
        has_timestamps = False
        t_start = None
        t_end = None
        duration = None
        
        if segments and 'gpxtime_start' in segments[0] and 'gpxtime_end' in segments[-1]:
            t_start = segments[0]['gpxtime_start']
            t_end = segments[-1]['gpxtime_end']
            # Only set has_timestamps if values are not None
            if t_start is not None and t_end is not None:
                has_timestamps = True
                duration = t_end - t_start

        if verbose:
            logger.info("[6/6] Processing summary:")
            logger.info("      Segments: %s -> %s", stats['segment_count_initial'], stats['segment_count_final'])
            logger.info("      Distance: %.3fkm -> %.3fkm", stats['distance_km_initial'], stats['distance_km_final'])
            logger.info("      Elevation gain: %.1fm -> %.1fm", stats['deniv_pos_initial'], stats['deniv_pos_final'])
            if stats["rectangle_SN"] is not None and stats["rectangle_EW"] is not None:
                logger.info("      Rectangle SN: %s, EW: %s", stats['rectangle_SN'], stats['rectangle_EW'])
            if has_timestamps:
                logger.info("      Timestamps: %s -> duration: %s", t_start.strftime('%Y-%m-%d %H:%M:%S %Z'), duration)
            logger.info("%s\n", "=" * 70)

        return GPXProcessingResult(
            segments=segments,
            stats=stats,
            has_timestamps=has_timestamps,
            t_start=t_start,
            t_end=t_end,
            duration=duration
        )
