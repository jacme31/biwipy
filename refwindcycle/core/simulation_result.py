# -*- coding: utf-8 -*-
"""
SimulationResult - Structured output for Simulator results

Provides hierarchical data classes for all simulation outputs (speed, wind, slopes, etc)
with nested sub-structures and JSON serialization support.

Architecture:
::

    SimulationResult
    ├── segments (List[Dict]) - Full segment data (NOT serialized to JSON)
    ├── distance: DistanceAnalysis
    ├── time: TimeAnalysis
    ├── speed: SpeedAnalysis
    ├── power: PowerAnalysis (optional)
    ├── wind: WindAnalysis
    │   ├── tws (True Wind Speed)
    │   └── twd (True Wind Direction)
    ├── gusts: GustAnalysis
    ├── slopes: SlopeAnalysis
    │   ├── terrain
    │   ├── virtual (wind effect)
    │   └── effective (terrain + wind)
    └── wind_along_trajectory: WindAlongTrajectoryAnalysis
        ├── headwind
        └── tailwind
"""

from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta


@dataclass
class NumericStats:
    """Generic numeric statistics (avg, min, max, position)"""
    avg: float
    min: float
    max: float
    min_at_km: float = 0.0
    max_at_km: float = 0.0

    # Base unit for this structure is m/s (for wind-like metrics).
    @property
    def avg_m_s(self) -> float:
        return self.avg

    @property
    def min_m_s(self) -> float:
        return self.min

    @property
    def max_m_s(self) -> float:
        return self.max

    @property
    def avg_kmh(self) -> float:
        return self.avg * 3.6

    @property
    def min_kmh(self) -> float:
        return self.min * 3.6

    @property
    def max_kmh(self) -> float:
        return self.max * 3.6
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DistanceAnalysis:
    """Distance metrics"""
    total_km: float
    segment_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TimeAnalysis:
    """Time metrics (seconds converted to min/hours)"""
    total_seconds: float
    total_minutes: float
    total_hours: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_seconds': self.total_seconds,
            'total_minutes': round(self.total_minutes, 2),
            'total_hours': round(self.total_hours, 2),
        }


@dataclass
class SpeedAnalysis:
    """Speed statistics (km/h)"""
    avg: float  # Time-weighted average
    min: float
    max: float
    moving_avg: Optional[float] = None  # Segments with v >= 1 m/s
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'avg_kmh': round(self.avg, 2),
            'min_kmh': round(self.min, 2),
            'max_kmh': round(self.max, 2),
            'moving_avg_kmh': round(self.moving_avg, 2) if self.moving_avg else None,
        }


@dataclass
class PowerAnalysis:
    """Power statistics (Watts) - optional, only when available"""
    avg: float
    min: float
    max: float
    P0_calibrated: Optional[float] = None  # Calibrated reference power
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            'avg_watts': round(self.avg, 1),
            'min_watts': round(self.min, 1),
            'max_watts': round(self.max, 1),
        }
        if self.P0_calibrated:
            result['P0_calibrated_watts'] = round(self.P0_calibrated, 1)
        return result


@dataclass
class WindAnalysis:
    """True Wind Speed and Direction statistics"""
    tws: NumericStats  # True Wind Speed (m/s internally, km/h in output)
    twd_avg: float     # Average True Wind Direction (degrees)
    twd_compass: str   # Cardinal direction (N, NE, E, etc)

    @property
    def tws_avg_kmh(self) -> float:
        return self.tws.avg_kmh

    @property
    def tws_min_kmh(self) -> float:
        return self.tws.min_kmh

    @property
    def tws_max_kmh(self) -> float:
        return self.tws.max_kmh
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'tws': {
                'avg_kmh': round(self.tws.avg * 3.6, 2),
                'min_kmh': round(self.tws.min * 3.6, 2),
                'max_kmh': round(self.tws.max * 3.6, 2),
            },
            'twd': {
                'avg_degrees': round(self.twd_avg, 1),
                'compass': self.twd_compass,
            }
        }


@dataclass
class GustAnalysis:
    """Wind gust statistics"""
    avg: float      # m/s
    min: float
    max: float
    min_at_km: float
    max_at_km: float

    @property
    def avg_kmh(self) -> float:
        return self.avg * 3.6

    @property
    def min_kmh(self) -> float:
        return self.min * 3.6

    @property
    def max_kmh(self) -> float:
        return self.max * 3.6
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'avg_kmh': round(self.avg_kmh, 2),
            'min_kmh': round(self.min_kmh, 2),
            'min_at_km': round(self.min_at_km, 2),
            'max_kmh': round(self.max_kmh, 2),
            'max_at_km': round(self.max_at_km, 2),
        }


@dataclass
class SlopeStats:
    """Slope statistics for a specific slope type (terrain, virtual, or effective)"""
    avg_pct: float
    min_pct: float
    max_pct: float
    deniv_pos_m: float    # Positive elevation change
    deniv_neg_m: float    # Negative elevation change
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'avg_pct': round(self.avg_pct, 2),
            'min_pct': round(self.min_pct, 2),
            'max_pct': round(self.max_pct, 2),
            'deniv_pos_m': round(self.deniv_pos_m, 1),
            'deniv_neg_m': round(self.deniv_neg_m, 1),
            'deniv_total_m': round(self.deniv_pos_m + self.deniv_neg_m, 1),  # Bilan net (deniv_neg_m déjà négatif)
        }


@dataclass
class SlopeAnalysis:
    """All slope types: terrain, virtual (wind), and effective (combined)"""
    terrain: SlopeStats
    virtual: SlopeStats  # Wind effect as virtual slope
    effective: SlopeStats  # Terrain + virtual combined
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'terrain': self.terrain.to_dict(),
            'virtual_wind': self.virtual.to_dict(),
            'effective': self.effective.to_dict(),
        }


@dataclass
class WindAlongSegment:
    """Wind component along trajectory for a single direction"""
    percentage: float      # % of route
    distance_km: float     # absolute distance
    avg_kmh: float        # average wind component
    min_kmh: float
    max_kmh: float
    min_at_km: float
    max_at_km: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'percentage': round(self.percentage, 1),
            'distance_km': round(self.distance_km, 2),
            'avg_kmh': round(self.avg_kmh, 2),
            'min_kmh': round(self.min_kmh, 2),
            'min_at_km': round(self.min_at_km, 2),
            'max_kmh': round(self.max_kmh, 2),
            'max_at_km': round(self.max_at_km, 2),
        }


@dataclass
class WindAlongTrajectoryAnalysis:
    """Wind component along the ride (headwind vs tailwind)"""
    headwind: WindAlongSegment
    tailwind: WindAlongSegment
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'headwind': self.headwind.to_dict(),
            'tailwind': self.tailwind.to_dict(),
        }


@dataclass
class CrosswindAnalysis:
    """Cross-wind (lateral wind component) statistics"""
    avg_kmh: float
    min_kmh: float
    max_kmh: float
    min_at_km: float
    max_at_km: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'avg_kmh': round(self.avg_kmh, 2),
            'min_kmh': round(self.min_kmh, 2),
            'max_kmh': round(self.max_kmh, 2),
            'min_at_km': round(self.min_at_km, 2),
            'max_at_km': round(self.max_at_km, 2),
        }


@dataclass
class WindScore:
    """Wind impact score with letter grade (A-F) and reasoning"""
    grade: Optional[str] = None                    # A-F final grade (max of safety & performance)
    reason: Optional[str] = None                   # 'safety', 'performance', or 'safety+performance'
    performance_grade: Optional[str] = None        # A-F grade from speed loss
    performance_score: Optional[float] = None      # Raw performance score (negative = harder)
    safety_grade: Optional[str] = None             # A-F grade from absolute wind thresholds
    safety_danger_score: Optional[int] = None      # Cumulative danger points (0-8)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'grade': self.grade,
            'reason': self.reason,
            'performance_grade': self.performance_grade,
            'performance_score': self.performance_score,
            'safety_grade': self.safety_grade,
            'safety_danger_score': self.safety_danger_score,
        }


@dataclass
class SimulationResult:
    """
    Complete structured output from Simulator.simulate_*() methods.
    
    Contains:
    - segments: Raw segment data (NOT serialized to JSON)
    - All hierarchical statistics organized by domain
    - to_dict() method for JSON serialization (excludes segments)
    - t_start: Start time of the simulation (for time-at-km queries)
    """
    segments: List[Dict]  # Full segment data for graphing, etc
    distance: DistanceAnalysis
    time: TimeAnalysis
    speed: SpeedAnalysis
    wind: WindAnalysis
    gusts: GustAnalysis
    slopes: SlopeAnalysis
    wind_along_trajectory: WindAlongTrajectoryAnalysis
    crosswind: CrosswindAnalysis
    wind_score: WindScore
    t_start: Optional[datetime] = None  # Start time for time-at-km calculations (always in UTC)
    power: Optional[PowerAnalysis] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for JSON serialization.
        Excludes segments (they're large and not needed in REST API).
        """
        result = {
            'distance': self.distance.to_dict(),
            'time': self.time.to_dict(),
            'speed': self.speed.to_dict(),
            'wind': self.wind.to_dict(),
            'gusts': self.gusts.to_dict(),
            'slopes': self.slopes.to_dict(),
            'wind_along_trajectory': self.wind_along_trajectory.to_dict(),
            'crosswind': self.crosswind.to_dict(),
            'wind_score': self.wind_score.to_dict(),
        }
        if self.power:
            result['power'] = self.power.to_dict()
        return result
    
    def get_segments(self) -> List[Dict]:
        """Accessor for segments (kept separate from JSON export)"""
        return self.segments
    
    def segment_count(self) -> int:
        """Number of segments"""
        return len(self.segments)
    
    def get_time_at_km(self, distance_km: float) -> Optional[datetime]:
        """
        Get the estimated time of passage at a given distance from start.
        
        Parameters:
        -----------
        distance_km : float
            Distance from start in kilometers
            
        Returns:
        --------
        Optional[datetime]
            Time of passage at the requested distance.
            Returns in the same timezone as t_start if available, otherwise UTC.
            Returns None if t_start was not provided or distance is out of range.
            
        Example:
        --------
        >>> from datetime import datetime
        >>> from zoneinfo import ZoneInfo
        >>> t_start = datetime(2026, 3, 15, 8, 0, tzinfo=ZoneInfo('Europe/Paris'))
        >>> result = sim.simulate_future(segments, t_start, P0=200)
        >>> time_at_50km = result.get_time_at_km(50.0)
        >>> print(f"Passage at 50km: {time_at_50km.strftime('%H:%M:%S')}")
        """
        if self.t_start is None:
            return None
        
        if distance_km < 0 or distance_km > self.distance.total_km:
            return None
        
        # Find the segment closest to the requested distance
        target_distance_m = distance_km * 1000.0
        cumulative_distance = 0.0
        closest_seg = None
        min_diff = float('inf')
        
        for seg in self.segments:
            seg_distance = seg.get('distance', 0.0)
            seg_mid_distance = cumulative_distance + seg_distance / 2.0
            
            diff = abs(seg_mid_distance - target_distance_m)
            if diff < min_diff:
                min_diff = diff
                closest_seg = seg
            
            cumulative_distance += seg_distance
        
        if closest_seg is None:
            return None
        
        # Get cumulative time at segment midpoint
        cum_t_start = closest_seg.get('cum_t_start', 0.0)
        cum_t_end = closest_seg.get('cum_t_end', 0.0)
        
        if cum_t_start is None or cum_t_end is None:
            return None
        
        # Use midpoint time
        time_at_segment = (cum_t_start + cum_t_end) / 2.0
        
        # Add to start time
        passage_time = self.t_start + timedelta(seconds=time_at_segment)
        
        return passage_time
