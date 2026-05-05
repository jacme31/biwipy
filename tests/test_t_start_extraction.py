# -*- coding: utf-8 -*-
"""
Test t_start auto-extraction in replay mode

Validates that simulate_replay() can now auto-extract t_start
from GPX timestamps instead of requiring it as a parameter.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from biwipy.core import Simulator, SimulationResult


def create_test_segments_with_timestamps():
    """Create simple test segments with GPX timestamps"""
    # Define a specific start time
    base_time = datetime(2026, 1, 15, 8, 0, 0, tzinfo=ZoneInfo('Europe/Paris'))
    
    segments = []
    for i in range(10):
        t_start = base_time + timedelta(seconds=i*60)
        t_end = t_start + timedelta(seconds=60)
        lat1 = 48.8566 + (i * 0.001)
        lon1 = 2.3522 + (i * 0.001)
        lat2 = 48.8566 + ((i + 1) * 0.001)
        lon2 = 2.3522 + ((i + 1) * 0.001)
        
        segments.append({
            'distance': 200.0,  # 200m per segment
            'bearing': 45.0,
            'ele1': 100.0,
            'ele2': 100.0,
            'lat': lat1,
            'lon': lon1,
            'lat1': lat1,
            'lon1': lon1,
            'lat2': lat2,
            'lon2': lon2,
            'gpxtime_start': t_start,  # GPX timestamps
            'gpxtime_end': t_end,
            'speed_m_s': 3.33,  # 12 km/h
            'slope': 0.0,
        })
    
    return segments, base_time


def test_t_start_auto_extraction():
    """Test that t_start is auto-extracted when not provided"""
    print("\n" + "="*70)
    print("TEST: Auto-extract t_start from GPX timestamps")
    print("="*70)
    
    # Create minimal mock grib
    class MockGrib:
        def calculate_cycling_wind_impact(self, *args, **kwargs):
            return {
                'tws_m_s': 2.0,
                'twd_deg': 180.0,
                'gust_m_s': 3.0,
                'headwind_m_s': 1.5,
                'gust_along_m_s': 2.0,
                'effective_wind_m_s': 1.5,
                'crosswind_m_s': 0.5,
                'is_headwind': True,
            }
    
    grib = MockGrib()
    simulator = Simulator(grib, CdA=0.5)
    
    # Create test segments
    segments, expected_t_start = create_test_segments_with_timestamps()
    
    print(f"\nExpected t_start from GPX: {expected_t_start}")
    
    # Test 1: Call without t_start (should auto-extract)
    print("\n--- Test 1: simulate_replay() WITHOUT t_start parameter ---")
    result = simulator.simulate_replay(
        segments_in=segments,
        # t_start NOT PROVIDED - should auto-extract
        passes=1,
    )
    
    # Verify result type
    assert isinstance(result, SimulationResult), f"Expected SimulationResult, got {type(result)}"
    print("✓ Return type is SimulationResult")
    
    # Verify t_start was auto-extracted
    assert result.t_start is not None, "t_start should not be None"
    assert result.t_start == expected_t_start, f"Expected {expected_t_start}, got {result.t_start}"
    print(f"✓ t_start auto-extracted: {result.t_start}")
    print(f"✓ Timezone preserved: {result.t_start.tzinfo}")
    
    # Test 2: Call with matching explicit t_start (should work)
    print("\n--- Test 2: simulate_replay() WITH matching t_start parameter ---")
    result2 = simulator.simulate_replay(
        segments_in=segments,
        t_start=expected_t_start,  # Matching timestamp
        passes=1,
    )
    
    assert result2.t_start == expected_t_start, f"Expected {expected_t_start}, got {result2.t_start}"
    print(f"✓ Matching t_start accepted: {result2.t_start}")
    
    # Test 3: Verify error when segments have no timestamps and t_start not provided
    print("\n--- Test 3: Error when no timestamps and no t_start ---")
    segments_no_timestamps = [{
        'distance': 200.0,
        'bearing': 45.0,
        'ele1': 100.0,
        'ele2': 100.0,
        'lat': 48.8566,
        'lon': 2.3522,
        'lat1': 48.8566,
        'lon1': 2.3522,
        'lat2': 48.8567,
        'lon2': 2.3523,
        'slope': 0.0,
    }]
    
    try:
        result3 = simulator.simulate_replay(
            segments_in=segments_no_timestamps,
            # No t_start, no timestamps → should raise error
            passes=1,
        )
        print("✗ Should have raised ValueError")
        assert False, "Should have raised ValueError for missing timestamps"
    except ValueError as e:
        print(f"✓ Correctly raised ValueError: {e}")
    
    print("\n" + "="*70)
    print("✓ ALL TESTS PASS - t_start auto-extraction works correctly!")
    print("="*70)


def test_t_start_mismatch_validation():
    """Test validation when t_start doesn't match GPX timestamps"""
    print("\n" + "="*70)
    print("TEST: Validate t_start mismatch detection")
    print("="*70)
    
    # Create minimal mock grib
    class MockGrib:
        def calculate_cycling_wind_impact(self, *args, **kwargs):
            return {
                'tws_m_s': 2.0,
                'twd_deg': 180.0,
                'gust_m_s': 3.0,
                'headwind_m_s': 1.5,
                'gust_along_m_s': 2.0,
                'effective_wind_m_s': 1.5,
                'crosswind_m_s': 0.5,
                'is_headwind': True,
            }
    
    grib = MockGrib()
    simulator = Simulator(grib, CdA=0.5)
    
    # Create test segments with specific timestamps
    segments, gpx_start = create_test_segments_with_timestamps()
    
    print(f"\nGPX timestamps start at: {gpx_start}")
    
    # Test 1: t_start matches exactly (should work)
    print("\n--- Test 1: t_start matches GPX exactly ---")
    try:
        result = simulator.simulate_replay(
            segments_in=segments,
            t_start=gpx_start,  # Exact match
            passes=1,
        )
        print(f"✓ Exact match accepted: {result.t_start}")
    except ValueError as e:
        print(f"✗ Should not have raised error: {e}")
        assert False
    
    # Test 2: Small diff (< 1s, should pass silently)
    print("\n--- Test 2: Small difference (0.5s) ---")
    small_diff_start = gpx_start + timedelta(seconds=0.5)
    try:
        result = simulator.simulate_replay(
            segments_in=segments,
            t_start=small_diff_start,
            passes=1,
        )
        print(f"✓ Small diff accepted silently: {result.t_start}")
    except ValueError as e:
        print(f"✗ Should not have raised error for <1s diff: {e}")
        assert False
    
    # Test 3: Medium diff (5s, should warn but accept)
    print("\n--- Test 3: Medium difference (5s, should warn) ---")
    medium_diff_start = gpx_start + timedelta(seconds=5)
    try:
        result = simulator.simulate_replay(
            segments_in=segments,
            t_start=medium_diff_start,
            passes=1,
        )
        print(f"✓ Medium diff accepted with warning: {result.t_start}")
    except ValueError as e:
        print(f"✗ Should not have raised error for 5s diff: {e}")
        assert False
    
    # Test 4: Large diff (2 minutes, should raise error)
    print("\n--- Test 4: Large difference (2 minutes, should raise error) ---")
    large_diff_start = gpx_start + timedelta(minutes=2)
    try:
        result = simulator.simulate_replay(
            segments_in=segments,
            t_start=large_diff_start,
            passes=1,
        )
        print(f"✗ Should have raised ValueError for 2min diff")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        if "t_start mismatch" in str(e):
            print(f"✓ Correctly raised ValueError for large mismatch")
            print(f"   Error message: {str(e).splitlines()[0]}")
        else:
            print(f"✗ Wrong error: {e}")
            raise
    
    print("\n" + "="*70)
    print("✓ ALL TESTS PASS - t_start validation working correctly!")
    print("="*70)


if __name__ == "__main__":
    test_t_start_auto_extraction()
    test_t_start_mismatch_validation()
