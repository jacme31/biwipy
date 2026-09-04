import unittest

from biwipy.analysis import CLIMB_PROFILES, get_climb_profile
from biwipy.analysis.anareswind import detect_real_climbs


class TestDetectRealClimbs(unittest.TestCase):
    def test_builtin_climb_profiles_have_expected_names_and_parameters(self):
        self.assertEqual(set(CLIMB_PROFILES), {"flat", "mountains", "hills"})
        self.assertEqual(get_climb_profile("flat")["slope_threshold_pct"], 3.5)
        self.assertEqual(get_climb_profile("mountains")["max_gap_segments"], 200)
        self.assertEqual(get_climb_profile("hills")["gap_max_distance_m"], 900.0)

    def test_get_climb_profile_returns_an_independent_copy(self):
        profile = get_climb_profile("mountains")
        profile["min_distance_m"] = 1.0

        self.assertEqual(get_climb_profile("mountains")["min_distance_m"], 1200.0)

    def test_get_climb_profile_rejects_unknown_profile(self):
        with self.assertRaises(ValueError):
            get_climb_profile("mountain")

    @staticmethod
    def _segment(
        distance: float,
        slope: float,
        ele1: float,
        lat1: float = 45.0,
        lon1: float = 6.0,
    ):
        ele2 = ele1 + (distance * slope)
        lat2 = lat1 + 0.0005
        lon2 = lon1 + 0.0005
        return {
            "distance": distance,
            "slope": slope,
            "lat1": lat1,
            "lon1": lon1,
            "lat2": lat2,
            "lon2": lon2,
            "ele1": ele1,
            "ele2": ele2,
        }

    def test_detects_contiguous_climb_with_threshold_and_min_distance(self):
        # 3 climbing segments at 4% (3 x 200m = 600m), then a flat segment.
        segments = [
            {
                "distance": 200.0,
                "slope": 0.04,
                "lat1": 45.0000,
                "lon1": 6.0000,
                "lat2": 45.0005,
                "lon2": 6.0005,
                "ele1": 100.0,
                "ele2": 108.0,
            },
            {
                "distance": 200.0,
                "slope": 0.04,
                "lat1": 45.0005,
                "lon1": 6.0005,
                "lat2": 45.0010,
                "lon2": 6.0010,
                "ele1": 108.0,
                "ele2": 116.0,
            },
            {
                "distance": 200.0,
                "slope": 0.04,
                "lat1": 45.0010,
                "lon1": 6.0010,
                "lat2": 45.0015,
                "lon2": 6.0015,
                "ele1": 116.0,
                "ele2": 124.0,
            },
            {
                "distance": 100.0,
                "slope": 0.01,
                "lat1": 45.0015,
                "lon1": 6.0015,
                "lat2": 45.0018,
                "lon2": 6.0018,
                "ele1": 124.0,
                "ele2": 125.0,
            },
        ]

        climbs = detect_real_climbs(segments, slope_threshold_pct=3.0, min_distance_m=500.0)
        self.assertEqual(len(climbs), 1)

        climb = climbs[0]
        self.assertAlmostEqual(climb["start_km"], 0.0, places=6)
        self.assertAlmostEqual(climb["end_km"], 0.6, places=6)
        self.assertAlmostEqual(climb["summit_lat"], 45.0015, places=6)
        self.assertAlmostEqual(climb["summit_lon"], 6.0015, places=6)
        self.assertAlmostEqual(climb["avg_slope_pct"], 4.0, places=6)

    def test_ignores_short_candidate_below_min_distance(self):
        segments = [
            {
                "distance": 150.0,
                "slope": 0.05,
                "lat1": 45.0,
                "lon1": 6.0,
                "lat2": 45.0005,
                "lon2": 6.0005,
                "ele1": 100.0,
                "ele2": 107.5,
            },
            {
                "distance": 150.0,
                "slope": 0.05,
                "lat1": 45.0005,
                "lon1": 6.0005,
                "lat2": 45.0010,
                "lon2": 6.0010,
                "ele1": 107.5,
                "ele2": 115.0,
            },
        ]

        climbs = detect_real_climbs(segments, slope_threshold_pct=3.0, min_distance_m=400.0)
        self.assertEqual(climbs, [])

    def test_strict_mode_splits_climb_when_gap_segment_below_threshold(self):
        segments = [
            self._segment(200.0, 0.05, 100.0),
            self._segment(200.0, 0.05, 110.0),
            self._segment(50.0, 0.0, 120.0),
            self._segment(200.0, 0.05, 120.0),
            self._segment(200.0, 0.05, 130.0),
        ]

        climbs = detect_real_climbs(segments, slope_threshold_pct=3.0, min_distance_m=300.0)
        self.assertEqual(len(climbs), 2)
        self.assertAlmostEqual(climbs[0]["distance_m"], 400.0, places=6)
        self.assertAlmostEqual(climbs[1]["distance_m"], 400.0, places=6)

    def test_gap_tolerance_merges_blocks_when_gap_is_short(self):
        segments = [
            self._segment(200.0, 0.05, 100.0),
            self._segment(200.0, 0.05, 110.0),
            self._segment(50.0, 0.0, 120.0),
            self._segment(200.0, 0.05, 120.0),
            self._segment(200.0, 0.05, 130.0),
        ]

        climbs = detect_real_climbs(
            segments,
            slope_threshold_pct=3.0,
            min_distance_m=300.0,
            sustain_threshold_pct=2.0,
            gap_ratio=0.20,
            gap_min_distance_m=20.0,
            gap_max_distance_m=100.0,
            max_gap_segments=2,
            min_gap_slope_pct=-0.5,
            hard_break_slope_pct=-2.5,
        )

        self.assertEqual(len(climbs), 1)
        self.assertAlmostEqual(climbs[0]["distance_m"], 850.0, places=6)
        self.assertAlmostEqual(climbs[0]["start_km"], 0.0, places=6)
        self.assertAlmostEqual(climbs[0]["end_km"], 0.85, places=6)

    def test_gap_tolerance_does_not_merge_when_gap_exceeds_budget(self):
        segments = [
            self._segment(300.0, 0.05, 100.0),
            self._segment(300.0, 0.05, 115.0),
            self._segment(250.0, 0.0, 130.0),
            self._segment(300.0, 0.05, 130.0),
            self._segment(300.0, 0.05, 145.0),
        ]

        climbs = detect_real_climbs(
            segments,
            slope_threshold_pct=3.0,
            min_distance_m=500.0,
            sustain_threshold_pct=2.0,
            gap_ratio=0.08,
            gap_min_distance_m=20.0,
            gap_max_distance_m=200.0,
            max_gap_segments=3,
            min_gap_slope_pct=-0.5,
            hard_break_slope_pct=-2.5,
        )

        self.assertEqual(len(climbs), 2)
        self.assertAlmostEqual(climbs[0]["distance_m"], 600.0, places=6)
        self.assertAlmostEqual(climbs[1]["distance_m"], 600.0, places=6)

    def test_hard_break_forces_climb_split_even_if_gap_budget_available(self):
        segments = [
            self._segment(250.0, 0.05, 100.0),
            self._segment(250.0, 0.05, 112.5),
            self._segment(80.0, -0.03, 125.0),
            self._segment(250.0, 0.05, 122.6),
            self._segment(250.0, 0.05, 135.1),
        ]

        climbs = detect_real_climbs(
            segments,
            slope_threshold_pct=3.0,
            min_distance_m=400.0,
            sustain_threshold_pct=2.0,
            gap_ratio=0.5,
            gap_min_distance_m=50.0,
            gap_max_distance_m=500.0,
            max_gap_segments=5,
            min_gap_slope_pct=-1.0,
            hard_break_slope_pct=-2.5,
        )

        self.assertEqual(len(climbs), 2)
        self.assertAlmostEqual(climbs[0]["distance_m"], 500.0, places=6)
        self.assertAlmostEqual(climbs[1]["distance_m"], 500.0, places=6)

    def test_min_elevation_gain_filters_low_gain_candidates(self):
        segments = [
            self._segment(300.0, 0.04, 100.0),
            self._segment(300.0, -0.02, 112.0),
            self._segment(300.0, 0.04, 106.0),
        ]

        climbs = detect_real_climbs(
            segments,
            slope_threshold_pct=3.0,
            min_distance_m=800.0,
            sustain_threshold_pct=2.0,
            gap_ratio=0.3,
            gap_min_distance_m=300.0,
            gap_max_distance_m=1200.0,
            max_gap_segments=3,
            min_gap_slope_pct=-2.1,
            hard_break_slope_pct=-3.0,
            min_elevation_gain_m=25.0,
        )
        self.assertEqual(climbs, [])

        climbs_without_gain_filter = detect_real_climbs(
            segments,
            slope_threshold_pct=3.0,
            min_distance_m=800.0,
            sustain_threshold_pct=2.0,
            gap_ratio=0.3,
            gap_min_distance_m=300.0,
            gap_max_distance_m=1200.0,
            max_gap_segments=3,
            min_gap_slope_pct=-2.1,
            hard_break_slope_pct=-3.0,
            min_elevation_gain_m=0.0,
        )
        self.assertEqual(len(climbs_without_gain_filter), 1)
        self.assertAlmostEqual(climbs_without_gain_filter[0]["elevation_gain_m"], 24.0, places=6)


if __name__ == "__main__":
    unittest.main()
