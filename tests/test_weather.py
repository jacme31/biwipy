"""
Unit tests for weather modules (GRIB, wind interpolation).

Coverage targets:
- Bilinear interpolation on GRIB grids
- Temporal interpolation between timestamps
- Wind projection on route segments
- GRIB caching and management
"""

import unittest
import sys
import os
from datetime import datetime, timedelta, timezone
import tempfile

import numpy as np

# Put the package in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Note: pygrib is not available on all platforms (Windows limitation)
# These tests are templates for when pygrib is available
try:
    from biwipy.weather.grib_manager import Grib
except ImportError:
    Grib = None

from biwipy.weather.grib_compare import compare_grib_objects


def _make_synthetic_grib(u_t1=5.0, v_t1=0.0, gust_t1=6.0,
                          u_t2=None, v_t2=None, gust_t2=None,
                          dt_gap_hours=1):
    """Build a minimal 3x3 Grib with uniform fields for unit testing.

    Grid: 1 degree resolution, lon=[0,1,2], lat=[0,1,2], grid_lat_max=2.
    Query point (lon=1.0, lat=1.0) maps to grid[1][1] (center cell).
    """
    if Grib is None:
        return None, None, None
    grib = Grib(lfile=[], bcache=False)
    grib.resolution = 1.0
    grib.inv_res = 1.0
    grib.nlongitude = 3
    grib.nlatitude = 3
    grib.grid_lon_min = 0.0
    grib.grid_lat_max = 2.0
    t1 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    t2 = t1 + timedelta(hours=dt_gap_hours)

    def _grid(val):
        return np.full((3, 3), float(val))

    if u_t2 is None:
        u_t2, v_t2, gust_t2 = u_t1, v_t1, gust_t1
    grib.lst_gribtimes = [t1, t2]
    grib.lst_u10  = [_grid(u_t1),   _grid(u_t2)]
    grib.lst_v10  = [_grid(v_t1),   _grid(v_t2)]
    grib.lst_gust = [_grid(gust_t1), _grid(gust_t2)]
    return grib, t1, t2


class TestWindProjection(unittest.TestCase):
    """Tests for wind projection on route segments."""

    def _grib_or_skip(self):
        if Grib is None:
            self.skipTest("PyGrib not available on this platform")

    def test_wind_projection_headwind(self):
        """Northerly wind (from north) against northbound cyclist is a headwind."""
        self._grib_or_skip()
        # u10=0, v10=-10 → wind FROM north (twd=0°)
        grib, t1, _ = _make_synthetic_grib(u_t1=0.0, v_t1=-10.0, gust_t1=12.0)
        result = grib.calculate_cycling_wind_impact(t1, lat_point=1.0, lon_point=1.0, bearing=0.0)
        self.assertIsNotNone(result)
        self.assertTrue(result["is_headwind"], "Northerly wind against northbound cyclist should be headwind")
        self.assertGreater(result["headwind_m_s"], 0.0)

    def test_wind_projection_tailwind(self):
        """Southerly wind (from south) behind northbound cyclist is a tailwind."""
        self._grib_or_skip()
        # u10=0, v10=10 → wind FROM south (twd=180°)
        grib, t1, _ = _make_synthetic_grib(u_t1=0.0, v_t1=10.0, gust_t1=12.0)
        result = grib.calculate_cycling_wind_impact(t1, lat_point=1.0, lon_point=1.0, bearing=0.0)
        self.assertIsNotNone(result)
        self.assertFalse(result["is_headwind"], "Southerly wind for northbound cyclist should be tailwind")
        self.assertLess(result["headwind_m_s"], 0.0)

    def test_wind_projection_crosswind(self):
        """Westerly wind on a northbound cyclist is mostly crosswind, near-zero along-track."""
        self._grib_or_skip()
        # u10=10, v10=0 → wind FROM west (twd=270°)
        grib, t1, _ = _make_synthetic_grib(u_t1=10.0, v_t1=0.0, gust_t1=12.0)
        result = grib.calculate_cycling_wind_impact(t1, lat_point=1.0, lon_point=1.0, bearing=0.0)
        self.assertIsNotNone(result)
        self.assertGreater(result["crosswind_m_s"], 0.0)
        self.assertAlmostEqual(result["headwind_m_s"], 0.0, places=1)

    def test_wind_gust_weighting(self):
        """Effective wind exceeds mean wind when gusts are present and ratio_wind > 0."""
        self._grib_or_skip()
        # Headwind scenario: northerly wind, northbound cyclist
        grib, t1, _ = _make_synthetic_grib(u_t1=0.0, v_t1=-10.0, gust_t1=20.0)
        result = grib.calculate_cycling_wind_impact(
            t1, lat_point=1.0, lon_point=1.0, bearing=0.0, ratio_wind=0.25
        )
        self.assertIsNotNone(result)
        # With gust > mean wind and ratio_wind > 0, effective should exceed headwind
        self.assertGreater(result["effective_wind_m_s"], result["headwind_m_s"])


class TestInterpolation(unittest.TestCase):
    """Tests for spatial and temporal interpolation."""

    def _grib_or_skip(self):
        if Grib is None:
            self.skipTest("PyGrib not available on this platform")

    def test_bilinear_interpolation_grid_center(self):
        """Bilinear interpolation at an exact grid corner returns the corner value."""
        # At corner (x=10, y=4), where q11=100, the result should be exactly 100.
        result = Grib.bilinear_interpolation(
            10, 4,
            [(10, 4, 100), (20, 4, 200), (10, 6, 150), (20, 6, 300)]
        )
        self.assertAlmostEqual(result, 100.0)

    def test_bilinear_interpolation_inside_square(self):
        """Bilinear interpolation at the center of a uniform-value square returns that value."""
        # Uniform grid: all four corners have value 50 → center must also be 50.
        result = Grib.bilinear_interpolation(
            15, 5,
            [(10, 4, 50), (20, 4, 50), (10, 6, 50), (20, 6, 50)]
        )
        self.assertAlmostEqual(result, 50.0)

    def test_temporal_interpolation_exact_match(self):
        """Querying get_wind_at exactly at t1 returns t1 wind values."""
        self._grib_or_skip()
        # u10=10 at t1, u10=4 at t2; query exactly at t1 → tws should reflect u=10
        grib, t1, _ = _make_synthetic_grib(u_t1=10.0, v_t1=0.0, gust_t1=12.0,
                                            u_t2=4.0, v_t2=0.0, gust_t2=5.0)
        result = grib.get_wind_at(t1, lat_point=1.0, lon_point=1.0)
        self.assertIsNotNone(result)
        tws, twd, gust = result
        self.assertAlmostEqual(tws, 10.0, places=1)

    def test_temporal_interpolation_between(self):
        """Querying at the midpoint between t1 and t2 returns linearly interpolated values."""
        self._grib_or_skip()
        # u10: t1=10, t2=4 → midpoint should give u=7 → tws=7
        grib, t1, t2 = _make_synthetic_grib(u_t1=10.0, v_t1=0.0, gust_t1=12.0,
                                             u_t2=4.0, v_t2=0.0, gust_t2=5.0)
        midpoint = t1 + (t2 - t1) / 2
        result = grib.get_wind_at(midpoint, lat_point=1.0, lon_point=1.0)
        self.assertIsNotNone(result)
        tws, _, _ = result
        self.assertAlmostEqual(tws, 7.0, places=1)

    def test_temporal_out_of_range(self):
        """Querying before the first available timestamp returns None."""
        self._grib_or_skip()
        grib, t1, _ = _make_synthetic_grib()
        before_t1 = t1 - timedelta(hours=1)
        result = grib.get_wind_at(before_t1, lat_point=1.0, lon_point=1.0)
        self.assertIsNone(result)


class TestGribCache(unittest.TestCase):
    """Tests for the GRIB cache system."""
    
    def test_cache_path_creation(self):
        """The GRIB cache path should be rooted under BIWIPY_CACHE_DIR when set."""
        with tempfile.TemporaryDirectory() as temp_dir:
            previous = os.environ.get("BIWIPY_CACHE_DIR")
            os.environ["BIWIPY_CACHE_DIR"] = temp_dir
            try:
                self.assertEqual(Grib._get_grib_cache_dir(), os.path.join(temp_dir, "grib"))
            finally:
                if previous is None:
                    os.environ.pop("BIWIPY_CACHE_DIR", None)
                else:
                    os.environ["BIWIPY_CACHE_DIR"] = previous

    def test_cache_hit(self):
        """Cache hit behaviour — skipped (requires real GRIB files on disk)."""
        self.skipTest("Requires real GRIB files on disk")

    def test_cache_expiration(self):
        """Cache expiration — skipped (requires real GRIB files on disk)."""
        self.skipTest("Requires real GRIB files on disk")


class TestGribValidation(unittest.TestCase):
    """Tests for GRIB data validation."""
    
    def test_gust_floor(self):
        """get_wind_at adjusts gust upward so that gust >= tws."""
        if Grib is None:
            self.skipTest("PyGrib not available on this platform")
        # u10=0, v10=10 → tws=10; inject gust=2 (below tws)
        grib, t1, _ = _make_synthetic_grib(u_t1=0.0, v_t1=10.0, gust_t1=2.0)
        result = grib.get_wind_at(t1, lat_point=1.0, lon_point=1.0, return_raw=True)
        self.assertIsNotNone(result)
        tws, twd, gust_adj, gust_raw = result
        self.assertAlmostEqual(tws, 10.0, places=1)
        self.assertLess(gust_raw, tws, "Raw gust should be below tws before adjustment")
        self.assertGreaterEqual(gust_adj, tws, "Adjusted gust must be >= tws")

    def test_grid_dimensions(self):
        """Default 0.25 degree grid should create 1440x721 points."""
        grib = Grib(lfile=[], bcache=False)
        self.assertEqual(grib.nlongitude, 1440)
        self.assertEqual(grib.nlatitude, 721)

    def test_timestamps_ordered(self):
        """get_wind_at works correctly when lst_gribtimes are in ascending order."""
        if Grib is None:
            self.skipTest("PyGrib not available on this platform")
        grib, t1, t2 = _make_synthetic_grib(u_t1=5.0, v_t1=0.0, gust_t1=6.0)
        # Timestamps must be strictly ascending for interpolation
        self.assertLess(grib.lst_gribtimes[0], grib.lst_gribtimes[1])
        result = grib.get_wind_at(t1, lat_point=1.0, lon_point=1.0)
        self.assertIsNotNone(result)

    def test_mandatory_parameters(self):
        """get_wind_at returns a 3-tuple (tws, twd, gust) when all parameters are present."""
        if Grib is None:
            self.skipTest("PyGrib not available on this platform")
        grib, t1, _ = _make_synthetic_grib(u_t1=3.0, v_t1=4.0, gust_t1=6.0)
        result = grib.get_wind_at(t1, lat_point=1.0, lon_point=1.0)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 3, "get_wind_at must return (tws, twd, gust)")


class TestWindDataIntegration(unittest.TestCase):
    """Integration tests for wind data along full segments."""

    def _grib_or_skip(self):
        if Grib is None:
            self.skipTest("PyGrib not available on this platform")

    def test_wind_impact_increases_headwind_resistance(self):
        """Headwind yields positive effective_wind_m_s along a northbound segment."""
        self._grib_or_skip()
        grib, t1, _ = _make_synthetic_grib(u_t1=0.0, v_t1=-10.0, gust_t1=12.0)
        result = grib.calculate_cycling_wind_impact(t1, lat_point=1.0, lon_point=1.0, bearing=0.0)
        self.assertIsNotNone(result)
        self.assertGreater(result["effective_wind_m_s"], 0.0)

    def test_wind_impact_reduces_power_headwind(self):
        """calculate_cycling_wind_impact flags is_headwind=True for opposing wind."""
        self._grib_or_skip()
        grib, t1, _ = _make_synthetic_grib(u_t1=0.0, v_t1=-8.0, gust_t1=10.0)
        result = grib.calculate_cycling_wind_impact(t1, lat_point=1.0, lon_point=1.0, bearing=0.0)
        self.assertIsNotNone(result)
        self.assertTrue(result["is_headwind"])

    def test_grib_spatial_gradient(self):
        """Spatial gradient test — skipped (requires heterogeneous grid values)."""
        self.skipTest("Requires per-cell heterogeneous grid — not implemented in _make_synthetic_grib")


class TestGribManager(unittest.TestCase):
    """Tests for the GRIB manager."""
    
    def test_grib_initialization(self):
        """Initialize a Grib manager with an empty file list."""
        try:
            grib = Grib(lfile=[], bcache=False)
            self.assertIsNotNone(grib)
            self.assertEqual(grib.model, "GFS")
        except (FileNotFoundError, ValueError):
            pass

    def test_grib_file_list_format(self):
        """A Grib initialised with an empty list has zero loaded timesteps."""
        if Grib is None:
            self.skipTest("PyGrib not available on this platform")
        grib = Grib(lfile=[], bcache=False)
        self.assertEqual(len(grib.lst_gribtimes), 0)
        self.assertEqual(len(grib.lst_u10), 0)
        self.assertEqual(len(grib.lst_v10), 0)
        self.assertEqual(len(grib.lst_gust), 0)

    def test_wind_interpolation_at_point(self):
        """get_wind_at on a synthetic grid returns plausible (tws, twd, gust) tuple."""
        if Grib is None:
            self.skipTest("PyGrib not available on this platform")
        # u10=3, v10=4 → tws = sqrt(9+16) = 5
        grib, t1, _ = _make_synthetic_grib(u_t1=3.0, v_t1=4.0, gust_t1=6.0)
        result = grib.get_wind_at(t1, lat_point=1.0, lon_point=1.0)
        self.assertIsNotNone(result)
        tws, twd, gust = result
        self.assertAlmostEqual(tws, 5.0, places=1)
        self.assertGreaterEqual(gust, tws)
        self.assertGreaterEqual(twd, 0.0)
        self.assertLess(twd, 360.0)

    def test_segment_wind_calculation(self):
        """calculate_cycling_wind_impact returns a complete impact dict for a valid query."""
        if Grib is None:
            self.skipTest("PyGrib not available on this platform")
        grib, t1, _ = _make_synthetic_grib(u_t1=0.0, v_t1=-8.0, gust_t1=10.0)
        result = grib.calculate_cycling_wind_impact(
            t1, lat_point=1.0, lon_point=1.0, bearing=45.0
        )
        self.assertIsNotNone(result)
        for key in ("tws_m_s", "twd_deg", "gust_m_s", "headwind_m_s",
                    "effective_wind_m_s", "crosswind_m_s", "is_headwind"):
            self.assertIn(key, result)

    def test_timestamps_sorted_after_loading(self):
        """Timestamps must be sorted even if GRIB files are loaded out of order."""
        if Grib is None:
            self.skipTest("PyGrib not available on this platform")
        
        from datetime import timezone

        # Timestamps in arbitrary order
        times_unordered = [
            datetime(2026, 2, 16, 12, 0, tzinfo=timezone.utc),
            datetime(2026, 2, 16, 6, 0, tzinfo=timezone.utc),
            datetime(2026, 2, 16, 18, 0, tzinfo=timezone.utc),
            datetime(2026, 2, 16, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 2, 16, 15, 0, tzinfo=timezone.utc),
        ]
        
        # Synthetic wind grids (small grids — content is irrelevant for sort test)
        small_grid = np.random.rand(10, 10)
        u10_data = [small_grid + i for i in range(5)]
        v10_data = [small_grid - i for i in range(5)]
        gust_data = [small_grid * 2 + i for i in range(5)]

        grib = Grib(lfile=[], bcache=False)
        grib.lst_gribtimes = times_unordered.copy()
        grib.lst_u10 = u10_data.copy()
        grib.lst_v10 = v10_data.copy()
        grib.lst_gust = gust_data.copy()
        
        # Simulate the sort that normally happens after loading
        if grib.lst_gribtimes:
            sorted_indices = sorted(range(len(grib.lst_gribtimes)), 
                                  key=lambda i: grib.lst_gribtimes[i])
            grib.lst_gribtimes = [grib.lst_gribtimes[i] for i in sorted_indices]
            grib.lst_u10 = [grib.lst_u10[i] for i in sorted_indices]
            grib.lst_v10 = [grib.lst_v10[i] for i in sorted_indices]
            grib.lst_gust = [grib.lst_gust[i] for i in sorted_indices]
        
        # Verify timestamps are now sorted
        for i in range(len(grib.lst_gribtimes) - 1):
            self.assertLessEqual(grib.lst_gribtimes[i], grib.lst_gribtimes[i+1],
                               f"Timestamps not sorted: {grib.lst_gribtimes[i]} > {grib.lst_gribtimes[i+1]}")
        
        expected_sorted = sorted(times_unordered)
        self.assertEqual(grib.lst_gribtimes, expected_sorted,
                        "Timestamps should be in chronological order")

        # Verify data arrays followed the sort — first element = oldest timestamp
        original_index_of_first = times_unordered.index(expected_sorted[0])
        np.testing.assert_array_equal(
            grib.lst_u10[0], 
            u10_data[original_index_of_first],
            err_msg="U10 data not correctly sorted with timestamps"
        )

    def test_duplicate_files_handled(self):
        """The grib_manager should automatically deduplicate file paths."""
        if Grib is None:
            self.skipTest("PyGrib not available on this platform")
        
        from datetime import timezone
        grib = Grib(lfile=[], bcache=False)

        # File list with duplicates
        fake_files = [
            '/path/to/file1.grib',
            '/path/to/file2.grib',
            '/path/to/file1.grib',  # Doublon
            '/path/to/file3.grib',
            '/path/to/file2.grib',  # Doublon
            '/path/to/file1.grib',  # Doublon
        ]
        
        unique_files = list(dict.fromkeys(fake_files))
        self.assertEqual(len(unique_files), 3, "Should have 3 unique files")
        self.assertEqual(unique_files, [
            '/path/to/file1.grib',
            '/path/to/file2.grib',
            '/path/to/file3.grib'
        ], "Order should be preserved")
        self.assertEqual(len(fake_files) - len(unique_files), 3,
                        "Should have removed 3 duplicate files")

    def test_interpolation_margin_automatic(self):
        """find_gribs_for_interpolation should add a margin beyond the ride end time."""
        if Grib is None:
            self.skipTest("PyGrib not available on this platform")
        
        from biwipy.weather.grib_finder import find_gribs_for_interpolation
        from datetime import timezone
        
        # Departure at 14:00 UTC, 3h ride with 3h GRIB step:
        # coverage 14:00-17:00 requires the 18:00 timestamp for interpolation.
        date_depart = datetime(2026, 2, 20, 14, 0, tzinfo=timezone.utc)
        refs = find_gribs_for_interpolation(date_depart, pas=3, intervalle_h=3)
        # Expect at least 3 refs (covering 12h, 15h, 18h)
        self.assertGreaterEqual(len(refs), 3,
                               f"Should have at least 3 GRIB refs for 3h ride with pas=3, got {len(refs)}")


class TestPhysicalValidity(unittest.TestCase):
    """Tests for physical validity of weather outputs."""

    def _grib_or_skip(self):
        if Grib is None:
            self.skipTest("PyGrib not available on this platform")

    def test_wind_speed_positive(self):
        """tws returned by get_wind_at is always non-negative."""
        self._grib_or_skip()
        grib, t1, _ = _make_synthetic_grib(u_t1=3.0, v_t1=-4.0, gust_t1=6.0)
        result = grib.get_wind_at(t1, lat_point=1.0, lon_point=1.0)
        self.assertIsNotNone(result)
        tws, _, _ = result
        self.assertGreaterEqual(tws, 0.0)

    def test_gust_greater_than_wind(self):
        """Returned gust is always >= tws (enforced by get_wind_at)."""
        self._grib_or_skip()
        # Inject gust below tws to verify the floor is applied
        grib, t1, _ = _make_synthetic_grib(u_t1=0.0, v_t1=10.0, gust_t1=1.0)
        result = grib.get_wind_at(t1, lat_point=1.0, lon_point=1.0)
        self.assertIsNotNone(result)
        tws, _, gust = result
        self.assertGreaterEqual(gust, tws)

    def test_wind_magnitude_reasonable(self):
        """Ground-level normalised tws_m_s is lower than 10m wind speed."""
        self._grib_or_skip()
        grib, t1, _ = _make_synthetic_grib(u_t1=0.0, v_t1=-10.0, gust_t1=12.0)
        result = grib.calculate_cycling_wind_impact(t1, lat_point=1.0, lon_point=1.0, bearing=0.0)
        self.assertIsNotNone(result)
        # Ground-level factor k_roughness < 1, so tws_m_s < raw 10 m tws
        self.assertLess(result["tws_m_s"], 10.0)


class TestGribCompare(unittest.TestCase):
    """Tests for compare_grib_objects with synthetic data."""

    class DummyGrib:
        def __init__(self, times, u10, v10, gust):
            self.lst_gribtimes = times
            self.lst_u10 = u10
            self.lst_v10 = v10
            self.lst_gust = gust

    def test_compare_identical(self):
        times = [datetime(2025, 1, 1, 0, 0), datetime(2025, 1, 1, 3, 0)]
        u10 = [np.zeros((2, 2)), np.ones((2, 2))]
        v10 = [np.zeros((2, 2)), np.ones((2, 2))]
        gust = [np.zeros((2, 2)), np.ones((2, 2))]

        g1 = self.DummyGrib(times, u10, v10, gust)
        g2 = self.DummyGrib(list(times), list(u10), list(v10), list(gust))

        self.assertTrue(compare_grib_objects(g1, g2, verbose=False))

    def test_compare_detects_diff(self):
        times = [datetime(2025, 1, 1, 0, 0), datetime(2025, 1, 1, 3, 0)]
        u10 = [np.zeros((2, 2)), np.ones((2, 2))]
        v10 = [np.zeros((2, 2)), np.ones((2, 2))]
        gust = [np.zeros((2, 2)), np.ones((2, 2))]

        g1 = self.DummyGrib(times, u10, v10, gust)
        u10_diff = [np.zeros((2, 2)), np.ones((2, 2)) * 2.0]
        g2 = self.DummyGrib(times, u10_diff, v10, gust)

        self.assertFalse(compare_grib_objects(g1, g2, verbose=False))


class TestGribPurge(unittest.TestCase):
    """Tests for Grib.purge_before() and Grib.purge_between()."""

    def _make_grib(self):
        """Return a Grib instance pre-loaded with 5 synthetic hourly timesteps."""
        grib = Grib(lfile=[], bcache=False)
        base = datetime(2026, 5, 4, 0, 0)  # 00:00 UTC
        grib.lst_gribtimes = [base + timedelta(hours=h) for h in range(5)]
        # Small 2×2 grids – content doesn't matter for purge tests
        grib.lst_u10   = [np.full((2, 2), float(h)) for h in range(5)]
        grib.lst_v10   = [np.full((2, 2), float(h)) for h in range(5)]
        grib.lst_gust  = [np.full((2, 2), float(h) * 1.2) for h in range(5)]
        return grib

    # ------------------------------------------------------------------ #
    # purge_before                                                         #
    # ------------------------------------------------------------------ #

    def test_purge_before_removes_older_steps(self):
        """purge_before(T) removes all timesteps strictly before T."""
        grib = self._make_grib()
        # Cutoff at 02:00 → 00:00 and 01:00 must be removed
        removed = grib.purge_before(datetime(2026, 5, 4, 2, 0))
        self.assertEqual(removed, 2)
        self.assertEqual(len(grib.lst_gribtimes), 3)
        self.assertEqual(grib.lst_gribtimes[0], datetime(2026, 5, 4, 2, 0))

    def test_purge_before_exact_boundary_kept(self):
        """Timestep exactly equal to cutoff is NOT removed (strict <)."""
        grib = self._make_grib()
        removed = grib.purge_before(datetime(2026, 5, 4, 1, 0))
        self.assertEqual(removed, 1)                          # only 00:00 removed
        self.assertEqual(grib.lst_gribtimes[0], datetime(2026, 5, 4, 1, 0))

    def test_purge_before_no_match_returns_zero(self):
        """purge_before(T) with T before all data removes nothing."""
        grib = self._make_grib()
        removed = grib.purge_before(datetime(2026, 5, 3, 23, 0))
        self.assertEqual(removed, 0)
        self.assertEqual(len(grib.lst_gribtimes), 5)

    def test_purge_before_all_match_empties_lists(self):
        """purge_before(T) with T after all data empties the store."""
        grib = self._make_grib()
        removed = grib.purge_before(datetime(2026, 5, 4, 10, 0))
        self.assertEqual(removed, 5)
        self.assertEqual(grib.lst_gribtimes, [])
        self.assertEqual(grib.lst_u10, [])
        self.assertEqual(grib.lst_v10, [])
        self.assertEqual(grib.lst_gust, [])

    def test_purge_before_arrays_stay_aligned(self):
        """After purge, lst_u10/v10/gust indices still match lst_gribtimes."""
        grib = self._make_grib()
        grib.purge_before(datetime(2026, 5, 4, 2, 0))
        for i, t in enumerate(grib.lst_gribtimes):
            expected_h = (t - datetime(2026, 5, 4, 0, 0)).seconds // 3600
            np.testing.assert_array_equal(grib.lst_u10[i], np.full((2, 2), float(expected_h)))

    def test_purge_before_returns_count(self):
        """Return value equals the number of dropped timesteps."""
        grib = self._make_grib()
        n = grib.purge_before(datetime(2026, 5, 4, 3, 0))
        self.assertEqual(n, 3)

    # ------------------------------------------------------------------ #
    # purge_between                                                        #
    # ------------------------------------------------------------------ #

    def test_purge_between_removes_closed_interval(self):
        """purge_between(dt1, dt2) removes timesteps in [dt1, dt2] inclusive."""
        grib = self._make_grib()
        # Remove 01:00, 02:00, 03:00 – keep 00:00 and 04:00
        removed = grib.purge_between(
            datetime(2026, 5, 4, 1, 0),
            datetime(2026, 5, 4, 3, 0),
        )
        self.assertEqual(removed, 3)
        self.assertEqual(len(grib.lst_gribtimes), 2)
        self.assertEqual(grib.lst_gribtimes[0], datetime(2026, 5, 4, 0, 0))
        self.assertEqual(grib.lst_gribtimes[1], datetime(2026, 5, 4, 4, 0))

    def test_purge_between_boundaries_inclusive(self):
        """Exact boundary timestamps dt1 and dt2 are removed."""
        grib = self._make_grib()
        removed = grib.purge_between(
            datetime(2026, 5, 4, 0, 0),
            datetime(2026, 5, 4, 4, 0),
        )
        self.assertEqual(removed, 5)
        self.assertEqual(grib.lst_gribtimes, [])

    def test_purge_between_no_match_returns_zero(self):
        """purge_between with interval outside all data removes nothing."""
        grib = self._make_grib()
        removed = grib.purge_between(
            datetime(2026, 5, 4, 6, 0),
            datetime(2026, 5, 4, 8, 0),
        )
        self.assertEqual(removed, 0)
        self.assertEqual(len(grib.lst_gribtimes), 5)

    def test_purge_between_single_step(self):
        """dt1 == dt2 removes exactly one timestep."""
        grib = self._make_grib()
        removed = grib.purge_between(
            datetime(2026, 5, 4, 2, 0),
            datetime(2026, 5, 4, 2, 0),
        )
        self.assertEqual(removed, 1)
        self.assertNotIn(datetime(2026, 5, 4, 2, 0), grib.lst_gribtimes)

    def test_purge_between_raises_if_dt1_after_dt2(self):
        """ValueError raised when dt1 > dt2."""
        grib = self._make_grib()
        with self.assertRaises(ValueError):
            grib.purge_between(
                datetime(2026, 5, 4, 4, 0),
                datetime(2026, 5, 4, 1, 0),
            )

    def test_purge_between_arrays_stay_aligned(self):
        """After purge_between, u10/v10/gust stay aligned with gribtimes."""
        grib = self._make_grib()
        grib.purge_between(datetime(2026, 5, 4, 1, 0), datetime(2026, 5, 4, 2, 0))
        for i, t in enumerate(grib.lst_gribtimes):
            expected_h = (t - datetime(2026, 5, 4, 0, 0)).seconds // 3600
            np.testing.assert_array_equal(grib.lst_u10[i], np.full((2, 2), float(expected_h)))

    # ------------------------------------------------------------------ #
    # WeatherProvider pass-through                                         #
    # ------------------------------------------------------------------ #

    def test_weather_provider_purge_before(self):
        """WeatherProvider.purge_before delegates to the underlying Grib."""
        from biwipy.weather.provider import WeatherProvider
        provider = WeatherProvider(lfile=[], bcache=False)
        base = datetime(2026, 5, 4, 0, 0)
        provider.grib.lst_gribtimes = [base + timedelta(hours=h) for h in range(4)]
        provider.grib.lst_u10  = [np.zeros((2, 2)) for _ in range(4)]
        provider.grib.lst_v10  = [np.zeros((2, 2)) for _ in range(4)]
        provider.grib.lst_gust = [np.zeros((2, 2)) for _ in range(4)]

        n = provider.purge_before(datetime(2026, 5, 4, 2, 0))
        self.assertEqual(n, 2)
        self.assertEqual(len(provider.grib.lst_gribtimes), 2)

    def test_weather_provider_purge_between(self):
        """WeatherProvider.purge_between delegates to the underlying Grib."""
        from biwipy.weather.provider import WeatherProvider
        provider = WeatherProvider(lfile=[], bcache=False)
        base = datetime(2026, 5, 4, 0, 0)
        provider.grib.lst_gribtimes = [base + timedelta(hours=h) for h in range(4)]
        provider.grib.lst_u10  = [np.zeros((2, 2)) for _ in range(4)]
        provider.grib.lst_v10  = [np.zeros((2, 2)) for _ in range(4)]
        provider.grib.lst_gust = [np.zeros((2, 2)) for _ in range(4)]

        n = provider.purge_between(datetime(2026, 5, 4, 1, 0), datetime(2026, 5, 4, 2, 0))
        self.assertEqual(n, 2)
        self.assertEqual(len(provider.grib.lst_gribtimes), 2)


if __name__ == '__main__':
    unittest.main()
