from datetime import datetime

from biwipy.visualization.interactive_map import _resolve_arrival_time


def test_resolve_arrival_time_uses_last_segment_end_when_available():
    segments = [
        {
            "gpxtime_start": datetime(2026, 7, 30, 13, 0, 0),
            "gpxtime_end": datetime(2026, 7, 30, 13, 20, 0),
            "time_s": 1200,
        },
        {
            "gpxtime_start": datetime(2026, 7, 30, 13, 20, 0),
            "gpxtime_end": datetime(2026, 7, 30, 13, 53, 0),
            "time_s": 1980,
        },
    ]

    assert _resolve_arrival_time(segments) == datetime(2026, 7, 30, 13, 53, 0)
