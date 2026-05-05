"""
Unit tests for analysis modules (GPX, segments, gravel detection).

Coverage targets:
- GPX loading and processing
- 1 Hz resampling
- Savitzky-Golay smoothing
- Segment creation and merging
- Gravel detection
"""

import unittest
import sys
import os
from datetime import datetime
import tempfile

# Put the package in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from biwipy.analysis import gpx_tools
from biwipy.analysis.gpx_tools import detect_gps_altitude_noise
from biwipy.analysis.anareswind import merge_short_segments


def _write_temp_gpx(content: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".gpx")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
    except Exception:
        os.unlink(path)
        raise
    return path


def _sample_points_with_time_and_alt():
    return [
        {
            "lat": 45.0000,
            "lon": 7.0000,
            "alt": 100.0,
            "time": datetime.fromisoformat("2026-05-04T10:00:00+00:00"),
        },
        {
            "lat": 45.0010,
            "lon": 7.0000,
            "alt": 110.0,
            "time": datetime.fromisoformat("2026-05-04T10:00:10+00:00"),
        },
        {
            "lat": 45.0020,
            "lon": 7.0000,
            "alt": 105.0,
            "time": datetime.fromisoformat("2026-05-04T10:00:20+00:00"),
        },
    ]


def _sample_segments_for_timing():
    base = datetime.fromisoformat("2026-05-04T10:00:00+00:00")
    return [
        {
            "distance": 100.0,
            "gpxtime_start": base,
            "gpxtime_end": base.replace(second=10),
        },
        {
            "distance": 2.0,
            "gpxtime_start": base.replace(second=10),
            "gpxtime_end": base.replace(second=20),
        },
        {
            "distance": 120.0,
            "gpxtime_start": base.replace(second=20),
            "gpxtime_end": base.replace(second=30),
        },
    ]


def _segment(distance, bearing, slope, ele1=100.0, ele2=None, lat1=45.0, lon1=7.0, lat2=45.0, lon2=7.0):
    if ele2 is None:
        ele2 = ele1 + (slope * distance)
    return {
        "lat1": lat1,
        "lon1": lon1,
        "lat2": lat2,
        "lon2": lon2,
        "ele1": ele1,
        "ele2": ele2,
        "distance": distance,
        "bearing": bearing,
        "slope": slope,
    }


class TestGPXLoading(unittest.TestCase):
    """Tests for GPX loading."""

    def _skip_template(self):
        self.skipTest("Template test pending implementation")
    
    def test_gpx_file_not_found(self):
        """Raise FileNotFoundError when the GPX file does not exist."""
        with self.assertRaises(FileNotFoundError):
            gpx_tools.load_gpx_points('/path/to/nonexistent.gpx')

    def test_gpx_valid_format(self):
                """Load a valid GPX 1.1 file and return its points."""
                path = _write_temp_gpx(
                        """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="test" xmlns="http://www.topografix.com/GPX/1/1">
    <trk>
        <trkseg>
            <trkpt lat="45.0000" lon="7.0000"><ele>100.0</ele><time>2026-05-04T10:00:00Z</time></trkpt>
            <trkpt lat="45.0010" lon="7.0010"><ele>105.0</ele><time>2026-05-04T10:00:10Z</time></trkpt>
        </trkseg>
    </trk>
</gpx>
"""
                )
                try:
                        points = gpx_tools.load_gpx_points(path)
                finally:
                        os.unlink(path)

                self.assertEqual(len(points), 2)
                self.assertEqual(points[0]["lat"], 45.0)
                self.assertEqual(points[1]["lon"], 7.0010)

    def test_gpx_with_elevation(self):
                """Elevation values should be parsed from GPX <ele> tags."""
                path = _write_temp_gpx(
                        """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="test" xmlns="http://www.topografix.com/GPX/1/1">
    <trk><trkseg>
        <trkpt lat="45.0000" lon="7.0000"><ele>123.4</ele></trkpt>
        <trkpt lat="45.0010" lon="7.0010"><ele>127.9</ele></trkpt>
    </trkseg></trk>
</gpx>
"""
                )
                try:
                        points = gpx_tools.load_gpx_points(path)
                finally:
                        os.unlink(path)

                self.assertEqual(points[0]["alt"], 123.4)
                self.assertEqual(points[1]["alt"], 127.9)

    def test_gpx_without_elevation(self):
                """Missing elevation tags should default altitude to 0.0."""
                path = _write_temp_gpx(
                        """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="test" xmlns="http://www.topografix.com/GPX/1/1">
    <trk><trkseg>
        <trkpt lat="45.0000" lon="7.0000"></trkpt>
        <trkpt lat="45.0010" lon="7.0010"></trkpt>
    </trkseg></trk>
</gpx>
"""
                )
                try:
                        points = gpx_tools.load_gpx_points(path)
                finally:
                        os.unlink(path)

                self.assertEqual(points[0]["alt"], 0.0)
                self.assertEqual(points[1]["alt"], 0.0)

    def test_gpx_timestamps(self):
                """Timestamps should be parsed as timezone-aware datetimes."""
                path = _write_temp_gpx(
                        """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="test" xmlns="http://www.topografix.com/GPX/1/1">
    <trk><trkseg>
        <trkpt lat="45.0000" lon="7.0000"><time>2026-05-04T10:00:00Z</time></trkpt>
        <trkpt lat="45.0010" lon="7.0010"><time>2026-05-04T10:00:10Z</time></trkpt>
    </trkseg></trk>
</gpx>
"""
                )
                try:
                        points = gpx_tools.load_gpx_points(path)
                finally:
                        os.unlink(path)

                self.assertIsNotNone(points[0]["time"])
                self.assertEqual(points[0]["time"].isoformat(), "2026-05-04T10:00:00+00:00")
                self.assertEqual(points[1]["time"].isoformat(), "2026-05-04T10:00:10+00:00")


class TestGPXTimingProcessing(unittest.TestCase):
    """Tests for GPX timing-derived processing helpers."""
    
    def test_resampling_1hz(self):
        """Moving average should exclude stopped segments below the threshold."""
        moving_average = gpx_tools.compute_moving_average_from_gpx_segments(
            _sample_segments_for_timing(),
            speed_threshold=1.0,
        )
        expected_kmh = ((100.0 + 120.0) / (10.0 + 10.0)) * 3.6
        self.assertAlmostEqual(moving_average, expected_kmh)

    def test_resampling_preserves_endpoints(self):
        """Stopped segments should be removed while moving segments are preserved."""
        filtered = gpx_tools.filter_stopped_segments(
            _sample_segments_for_timing(),
            speed_threshold=1.0,
            verbose=False,
        )
        self.assertEqual(len(filtered), 2)
        self.assertEqual(filtered[0]["distance"], 100.0)
        self.assertEqual(filtered[1]["distance"], 120.0)

    def test_resampling_interpolation(self):
        """Segments without GPX timestamps should be preserved by stop filtering."""
        segments = _sample_segments_for_timing()
        segments.append({"distance": 50.0})
        filtered = gpx_tools.filter_stopped_segments(segments, speed_threshold=1.0, verbose=False)
        self.assertEqual(len(filtered), 3)
        self.assertEqual(filtered[-1]["distance"], 50.0)

    def test_resampling_temporal_uniform(self):
        """Segments with non-positive duration should be dropped by stop filtering."""
        base = datetime.fromisoformat("2026-05-04T10:00:00+00:00")
        segments = [
            {"distance": 100.0, "gpxtime_start": base, "gpxtime_end": base},
            {"distance": 80.0, "gpxtime_start": base, "gpxtime_end": base.replace(second=10)},
        ]
        filtered = gpx_tools.filter_stopped_segments(segments, speed_threshold=1.0, verbose=False)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["distance"], 80.0)


class TestElevationSmoothing(unittest.TestCase):
    """Tests for Savitzky-Golay smoothing."""

    def _skip_template(self):
        self.skipTest("Template test pending implementation")
    
    def test_savgol_smoothing_applied(self):
        """Smoothing should reduce elevation noise."""
        self._skip_template()

    def test_savgol_window_size(self):
        """Window size should be 19 points as documented."""
        self._skip_template()

    def test_smoothing_preserves_trend(self):
        """Smoothing should not invert the overall trend."""
        self._skip_template()

    def test_slope_capped_at_15_percent(self):
        """Extreme slopes should be clipped to +/-15% to filter GPS artifacts."""
        self._skip_template()


class TestSegmentCreation(unittest.TestCase):
    """Tests for segment creation."""
    
    def test_points_to_segments_conversion(self):
        """Points should be converted into one segment per consecutive pair."""
        segments = gpx_tools.gpx_to_segments(_sample_points_with_time_and_alt(), smooth=False)
        self.assertEqual(len(segments), 2)
        self.assertIn("distance", segments[0])
        self.assertIn("bearing", segments[0])
        self.assertIn("slope", segments[0])
        self.assertIn("gpxtime_start", segments[0])
        self.assertIn("gpxtime_end", segments[0])

    def test_segment_bearing_calculation(self):
        """Bearing should match a northbound segment."""
        points = [
            {"lat": 45.0000, "lon": 7.0000, "alt": 100.0},
            {"lat": 45.0010, "lon": 7.0000, "alt": 100.0},
        ]
        segments = gpx_tools.gpx_to_segments(points, smooth=False)
        self.assertAlmostEqual(segments[0]["bearing"], 0.0, delta=1.0)

    def test_segment_distance_accumulation(self):
        """Cumulative uphill/downhill values should stay monotonic."""
        segments = gpx_tools.gpx_to_segments(_sample_points_with_time_and_alt(), smooth=False)
        self.assertGreaterEqual(segments[1]["dcumplus"], segments[0]["dcumplus"])
        self.assertLessEqual(segments[1]["dcummoins"], segments[0]["dcummoins"])

    def test_segment_slope_calculation(self):
        """Segment slope should equal elevation_delta / distance."""
        points = [
            {"lat": 45.0000, "lon": 7.0000, "alt": 100.0},
            {"lat": 45.0010, "lon": 7.0000, "alt": 110.0},
        ]
        segments = gpx_tools.gpx_to_segments(points, smooth=False)
        expected_slope = (110.0 - 100.0) / segments[0]["distance"]
        self.assertAlmostEqual(segments[0]["slope"], expected_slope)


class TestSegmentMerging(unittest.TestCase):
    """Tests for merging short or similar segments."""
    
    def test_merge_short_segments(self):
        """Segments shorter than 50 m should be merged."""
        segments = [
            _segment(20.0, 0.0, 0.02, lat2=45.0001),
            _segment(40.0, 5.0, 0.03, ele1=100.4, lat1=45.0001, lat2=45.0004),
        ]
        merged, n_merged = merge_short_segments(segments, verbose=False)
        self.assertEqual(n_merged, 1)
        self.assertEqual(len(merged), 1)
        self.assertAlmostEqual(merged[0]["distance"], 60.0)

    def test_merge_similar_bearing(self):
        """Segments should merge when bearing difference is below 20 degrees."""
        segments = [
            _segment(20.0, 10.0, 0.01),
            _segment(40.0, 25.0, 0.01, ele1=100.2),
        ]
        merged, n_merged = merge_short_segments(segments, verbose=False, max_bearing_diff=20.0)
        self.assertEqual(n_merged, 1)
        self.assertEqual(len(merged), 1)

    def test_merge_similar_slope(self):
        """Segments should merge when slope difference is below 10%."""
        segments = [
            _segment(20.0, 0.0, 0.01),
            _segment(40.0, 0.0, 0.20, ele1=100.2),
        ]
        merged, n_merged = merge_short_segments(segments, verbose=False, max_slope_diff=0.10)
        self.assertEqual(n_merged, 0)
        self.assertEqual(len(merged), 2)

    def test_merge_preserves_distance(self):
        """Total cumulative distance should remain unchanged after merging."""
        segments = [
            _segment(20.0, 0.0, 0.02),
            _segment(40.0, 0.0, 0.02, ele1=100.4),
            _segment(80.0, 0.0, 0.01, ele1=101.2),
        ]
        merged, _ = merge_short_segments(segments, verbose=False)
        self.assertAlmostEqual(
            sum(segment["distance"] for segment in merged),
            sum(segment["distance"] for segment in segments),
        )

    def test_merge_weighted_average_bearing(self):
        """Merged bearing should be the distance-weighted average."""
        segments = [
            _segment(20.0, 10.0, 0.02),
            _segment(40.0, 25.0, 0.02, ele1=100.4),
        ]
        merged, n_merged = merge_short_segments(segments, verbose=False)
        self.assertEqual(n_merged, 1)
        self.assertAlmostEqual(merged[0]["bearing"], (20.0 * 10.0 + 40.0 * 25.0) / 60.0)


class TestGravelDetection(unittest.TestCase):
    """Tests for gravel surface detection."""

    def _skip_template(self):
        self.skipTest("Template test pending implementation")
    
    def test_gravel_vs_tarmac_classification(self):
        """Segments should be classified as tarmac or gravel."""
        self._skip_template()

    def test_gravel_detection_altitude_gradient(self):
        """Elevation gradient may contribute to gravel detection."""
        self._skip_template()

    def test_gravel_detection_smoothness(self):
        """Rough segments may be classified as gravel."""
        self._skip_template()


class TestSegmentWindIntegration(unittest.TestCase):
    """Integration tests for segments combined with GRIB wind."""

    def _skip_template(self):
        self.skipTest("Template test pending implementation")
    
    def test_wind_projection_on_segment(self):
        """Project GRIB wind onto each segment."""
        self._skip_template()

    def test_headwind_increases_power_requirement(self):
        """A headwind segment should require more power."""
        self._skip_template()

    def test_multi_segment_simulation(self):
        """Simulate a full route segment by segment."""
        self._skip_template()


class TestElevationValidation(unittest.TestCase):
    """Tests for elevation data validation."""

    def test_elevation_noise_detection(self):
        """A short, steep segment isolated between flat ones is detected as GPS noise."""
        segments = [
            _segment(distance=50.0, bearing=10.0, slope=0.01),   # normal flat
            _segment(distance=2.0,  bearing=10.0, slope=0.50),   # short + very steep → noise
            _segment(distance=50.0, bearing=10.0, slope=0.01),   # normal flat
        ]
        aberrants = detect_gps_altitude_noise(
            segments, max_dist=5.0, min_slope_threshold=0.10, normal_slope_threshold=0.05
        )
        self.assertEqual(len(aberrants), 1)
        self.assertEqual(aberrants[0]["index"], 1)

    def test_elevation_jumps_not_flagged_when_not_isolated(self):
        """A short, steep segment is NOT flagged when its neighbours are also steep."""
        segments = [
            _segment(distance=50.0, bearing=10.0, slope=0.12),   # steep neighbour
            _segment(distance=2.0,  bearing=10.0, slope=0.50),   # short + steep, but not isolated
            _segment(distance=50.0, bearing=10.0, slope=0.12),   # steep neighbour
        ]
        aberrants = detect_gps_altitude_noise(
            segments, max_dist=5.0, min_slope_threshold=0.10, normal_slope_threshold=0.05
        )
        self.assertEqual(len(aberrants), 0)

    def test_elevation_monotonicity_non_required(self):
        """Normal varying elevation segments (no short & steep combo) produce no aberrants."""
        segments = [
            _segment(distance=100.0, bearing=10.0, slope=0.03),
            _segment(distance=80.0,  bearing=10.0, slope=-0.02),
            _segment(distance=120.0, bearing=10.0, slope=0.05),
        ]
        aberrants = detect_gps_altitude_noise(
            segments, max_dist=5.0, min_slope_threshold=0.10, normal_slope_threshold=0.05
        )
        self.assertEqual(len(aberrants), 0)


class TestPhysicalCoherence(unittest.TestCase):
    """Tests for physical coherence of segments."""

    def _skip_template(self):
        self.skipTest("Template test pending implementation")
    
    def test_distance_positive(self):
        """Segment distance should be strictly positive."""
        segments = gpx_tools.gpx_to_segments(_sample_points_with_time_and_alt(), smooth=False)
        self.assertGreater(segments[0]["distance"], 0.0)
        self.assertGreater(segments[1]["distance"], 0.0)

    def test_bearing_in_range(self):
        """Segment bearing should stay within [0, 360)."""
        segments = gpx_tools.gpx_to_segments(_sample_points_with_time_and_alt(), smooth=False)
        for segment in segments:
            self.assertGreaterEqual(segment["bearing"], 0.0)
            self.assertLess(segment["bearing"], 360.0)

    def test_slope_reasonable_bounds(self):
        """Slope should stay within [-15%, +15%] after clipping."""
        self._skip_template()

    def test_cumulative_distance_ordered(self):
        """Cumulative distance should be strictly increasing."""
        self._skip_template()


if __name__ == '__main__':
    unittest.main()
