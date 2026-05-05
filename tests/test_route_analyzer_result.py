import unittest
from unittest.mock import patch

from biwipy.analysis.route_analyzer import RouteAnalyzer, GPXProcessingResult


class TestGPXProcessingResultCut(unittest.TestCase):
    def test_cut_between_km_keeps_requested_window(self):
        segments = [
            {
                'lat1': 45.0, 'lon1': 6.0,
                'lat2': 45.0, 'lon2': 6.01,
                'ele1': 100.0, 'ele2': 110.0,
                'distance': 1000.0,
                'bearing': 90.0,
                'slope': 0.01,
            },
            {
                'lat1': 45.0, 'lon1': 6.01,
                'lat2': 45.0, 'lon2': 6.02,
                'ele1': 110.0, 'ele2': 120.0,
                'distance': 1000.0,
                'bearing': 90.0,
                'slope': 0.01,
            },
            {
                'lat1': 45.0, 'lon1': 6.02,
                'lat2': 45.0, 'lon2': 6.03,
                'ele1': 120.0, 'ele2': 110.0,
                'distance': 1000.0,
                'bearing': 90.0,
                'slope': -0.01,
            },
        ]

        result = GPXProcessingResult(segments=segments, stats={})
        cut_result = result.cut(0.5, 2.5)

        self.assertAlmostEqual(cut_result.distance_km, 2.0, places=6)
        self.assertEqual(len(cut_result.segments), 3)

    def test_cut_with_none_bounds_supports_start_and_end(self):
        segments = [
            {
                'lat1': 45.0, 'lon1': 6.0,
                'lat2': 45.0, 'lon2': 6.01,
                'ele1': 100.0, 'ele2': 110.0,
                'distance': 1000.0,
                'bearing': 90.0,
                'slope': 0.01,
            },
            {
                'lat1': 45.0, 'lon1': 6.01,
                'lat2': 45.0, 'lon2': 6.02,
                'ele1': 110.0, 'ele2': 120.0,
                'distance': 1000.0,
                'bearing': 90.0,
                'slope': 0.01,
            },
            {
                'lat1': 45.0, 'lon1': 6.02,
                'lat2': 45.0, 'lon2': 6.03,
                'ele1': 120.0, 'ele2': 110.0,
                'distance': 1000.0,
                'bearing': 90.0,
                'slope': -0.01,
            },
        ]

        result = GPXProcessingResult(segments=segments, stats={})

        from_start = result.cut(None, 1.0)
        to_end = result.cut(2.0, None)

        self.assertAlmostEqual(from_start.distance_km, 1.0, places=6)
        self.assertAlmostEqual(to_end.distance_km, 1.0, places=6)


class TestRouteAnalyzerProcessResult(unittest.TestCase):
    @patch.object(RouteAnalyzer, 'load_gpx')
    @patch.object(RouteAnalyzer, 'segments_from_gpx')
    @patch.object(RouteAnalyzer, 'merge_segments')
    def test_process_gpx_returns_structured_result_and_tuple_compat(
        self,
        mock_merge_segments,
        mock_segments_from_gpx,
        mock_load_gpx,
    ):
        mock_load_gpx.return_value = [
            {'lat': 43.12, 'lon': 0.21, 'alt': 100.0, 'time': None},
            {'lat': 44.78, 'lon': 1.84, 'alt': 110.0, 'time': None},
            {'lat': 43.95, 'lon': 0.65, 'alt': 102.0, 'time': None},
        ]

        mock_segments_from_gpx.return_value = [
            {
                'lat1': 45.0, 'lon1': 6.0,
                'lat2': 45.0, 'lon2': 6.01,
                'ele1': 100.0, 'ele2': 110.0,
                'distance': 1000.0,
                'bearing': 90.0,
                'slope': 0.01,
            },
            {
                'lat1': 45.0, 'lon1': 6.01,
                'lat2': 45.0, 'lon2': 6.02,
                'ele1': 110.0, 'ele2': 120.0,
                'distance': 1000.0,
                'bearing': 90.0,
                'slope': 0.01,
            },
        ]
        mock_merge_segments.return_value = (mock_segments_from_gpx.return_value, 0)

        analyzer = RouteAnalyzer()
        result = analyzer.process_gpx('dummy.gpx', detect_noise=False, verbose=False)

        self.assertAlmostEqual(result.distance_km, 2.0, places=6)
        self.assertIn('distance_km', result.stats)
        self.assertEqual(result.stats['rectangle_SN'], (43, 45))
        self.assertEqual(result.stats['rectangle_EW'], (0, 2))

        segments, stats = result
        self.assertEqual(segments, result.segments)
        self.assertEqual(stats, result.stats)


if __name__ == '__main__':
    unittest.main()
