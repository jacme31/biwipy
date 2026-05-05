# -*- coding: utf-8 -*-
"""
Test Phase 2: Simulator returning SimulationResult

Validates that the Simulator now returns SimulationResult objects
instead of tuples.
"""

import json
import pytest
from datetime import datetime, timedelta
from biwipy.core import Simulator, SimulationResult


def create_test_segments(duration_seconds=600, distance_m=10000):
    """Create simple test segments"""
    segments = []
    avg_speed = distance_m / duration_seconds  # m/s
    segment_duration = duration_seconds / 100  # 100 segments
    segment_distance = distance_m / 100
    
    for i in range(100):
        t_start = datetime.now() + timedelta(seconds=i*segment_duration)
        t_end = t_start + timedelta(seconds=segment_duration)
        lat1 = 48.8566 + (i * 0.0001)
        lon1 = 2.3522 + (i * 0.0001)
        lat2 = 48.8566 + ((i + 1) * 0.0001)
        lon2 = 2.3522 + ((i + 1) * 0.0001)
        segments.append({
            'distance': segment_distance,
            'bearing': 45.0,
            'ele1': 100.0,
            'ele2': 100.0 + (0.5 * (i % 10 - 5)),  # slight elevation changes
            'lat': lat1,
            'lon': lon1,
            'lat1': lat1,
            'lon1': lon1,
            'lat2': lat2,
            'lon2': lon2,
            'time': t_start,
            'gpxtime_start': t_start,
            'gpxtime_end': t_end,
            'speed_m_s': avg_speed,
            'slope': (100.0 - 100.0) / segment_distance - 0.001,  # slight downhill bias
            'slope_terrain': 0.001,
            'slope_wind': -0.0002,
            'slope_effective': 0.0008,
            'elevation_virtual_m': -0.2,
            'tws': 3.0,  # 3 m/s
            'twd': 180.0,  # South (headwind if bearing is North)
            'gust': 4.5,  # m/s
            'wind_along': 2.5,  # m/s headwind
            'power': 200.0,  # Watts
        })
    
    return segments


def test_simulator_returns_result():
    """Test that Simulator returns SimulationResult (not tuple)"""
    print("\n" + "="*70)
    print("TEST: Simulator.simulate_replay() returns SimulationResult")
    print("="*70)
    
    # Create minimal mock grib
    class MockGrib:
        def calculate_cycling_wind_impact(self, *args, **kwargs):
            return {
                'tws_m_s': 3.0,
                'twd_deg': 180.0,
                'gust_m_s': 4.5,
                'headwind_m_s': 2.5,
                'gust_along_m_s': 3.0,
                'effective_wind_m_s': 2.5,
                'crosswind_m_s': 1.0,
                'is_headwind': True,
            }
    
    grib = MockGrib()
    simulator = Simulator(grib, CdA=0.5)
    
    # Create test segments
    segments = create_test_segments()
    t_start = segments[0]['gpxtime_start']
    
    try:
        # This should return SimulationResult, not tuple
        result = simulator.simulate_replay(
            segments_in=segments,
            t_start=t_start,
            passes=1,
        )
        
        # Verify result type
        assert isinstance(result, SimulationResult), f"Expected SimulationResult, got {type(result)}"
        print("✓ Return type is SimulationResult")
        
        # Verify key attributes
        assert hasattr(result, 'segments')
        assert hasattr(result, 'distance')
        assert hasattr(result, 'time')
        assert hasattr(result, 'speed')
        assert hasattr(result, 'power')
        assert hasattr(result, 'wind')
        assert hasattr(result, 'gusts')
        assert hasattr(result, 'slopes')
        assert hasattr(result, 'wind_along_trajectory')
        assert hasattr(result, 'crosswind')
        assert hasattr(result, 'wind_score')
        print("✓ All expected attributes present")
        
        # Verify distance analysis
        assert result.distance.total_km > 0
        assert result.distance.segment_count > 0
        print(f"✓ Distance: {result.distance.total_km:.2f} km ({result.distance.segment_count} segments)")
        
        # Verify speed analysis
        assert result.speed.avg > 0
        print(f"✓ Speed: {result.speed.avg:.2f} km/h (min: {result.speed.min:.2f}, max: {result.speed.max:.2f})")
        
        # Verify power analysis
        assert result.power is not None
        assert result.power.avg > 0
        print(f"✓ Power: {result.power.avg:.1f} W (min: {result.power.min:.1f}, max: {result.power.max:.1f})")
        
        # Verify wind analysis
        assert result.wind.tws.avg > 0
        print(f"✓ Wind: {result.wind.tws.avg:.2f} m/s from {result.wind.twd_compass}")
        
        # Verify crosswind analysis
        assert result.crosswind.avg_kmh >= 0
        print(f"✓ Crosswind: {result.crosswind.avg_kmh:.2f} km/h (min: {result.crosswind.min_kmh:.2f}, max: {result.crosswind.max_kmh:.2f})")
        
        # Verify wind score structure (computed or fallback)
        if result.wind_score.grade is None:
            assert result.wind_score.reason == "windscore module not available"
            print("✓ WindScore fallback initialized")
        else:
            assert result.wind_score.grade in {"A", "B", "C", "D", "E", "F"}
            assert result.wind_score.performance_grade in {"A", "B", "C", "D", "E", "F"}
            assert result.wind_score.safety_grade in {"A", "B", "C", "D", "E", "F"}
            assert result.wind_score.performance_score is not None
            assert result.wind_score.safety_danger_score is not None
            print("✓ WindScore computed with current schema")
        
        # Test JSON export
        data = result.to_dict()
        json_str = json.dumps(data, indent=2)
        reloaded = json.loads(json_str)
        assert reloaded['distance']['total_km'] > 0
        assert 'segments' not in data  # Segments NOT in JSON
        assert 'crosswind' in data  # Crosswind IS in JSON
        assert 'wind_score' in data  # WindScore IS in JSON
        print("✓ JSON export works (includes crosswind and wind_score, excludes segments)")
        
        # Segments still accessible via getter
        segs = result.get_segments()
        assert len(segs) > 0
        print(f"✓ Segments accessible via getter ({len(segs)} segments)")
        
        print("\n" + "="*70)
        print("✓ ALL TESTS PASS - Phase 2 Simulator Complete")
        print("="*70)
        
    except TypeError as e:
        pytest.fail(f"Simulator may still be returning tuple instead of SimulationResult: {e}")
    except Exception as e:
        pytest.fail(f"Unexpected error: {e}")


if __name__ == '__main__':
    test_simulator_returns_result()


def test_simulator_helper_wrappers():
    """Test helper wrappers exposed on Simulator (no direct bike_physics import)."""

    simulator = Simulator(grib=None, CdA=0.5, Cr=0.004, m=75.0)

    # Forward conversion: v0 -> P0
    v0 = 8.33  # ~30 km/h
    p0 = simulator.P0_from_v0(v0)
    assert p0 > 0

    # Inverse conversion: P0 -> v0 (same model assumptions: flat, no wind)
    v0_back = simulator.v0_from_P0(p0)
    assert abs(v0_back - v0) < 0.05

    # Print helper should execute without raising
    simulator.print_power_model(p0)
