import unittest

from biwipy.analysis.anareswind import detect_real_climbs


class TestDetectRealClimbs(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
