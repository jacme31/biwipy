# -*- coding: utf-8 -*-
"""
roughness_provider.py
=====================
Optional roughness (z0) map provider based on ESA WorldCover raster data.

Usage pattern:
    from biwipy.weather.roughness_provider import RoughnessProvider

    provider = RoughnessProvider(raster_dir="G:/grib/data/roughness_cache")
    # prepare once after GPX processing:
    provider.prepare(south=43, north=46, west=0, east=4)
    # then query inside simulation loop:
    z0 = provider.get_z0(lat=44.5, lon=2.3)  # returns float or None

Design:
- index SQLite : one row per downloaded raster tile
- rasterio COG windowed read : only the bbox is downloaded/read
- ESA WorldCover class -> z0 table (Davenport / GWA inspired)
- All exceptions are caught and logged; caller receives None -> fallback to default z0
- No hard dependency on windkit
"""

import logging
import math
import os
import sqlite3
import struct
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional, Tuple

logger = logging.getLogger(__name__)


def _env_flag(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).lower() in ("1", "true", "yes")


def _read_libcurl_version_subprocess(lib_target: Optional[str]) -> Optional[str]:
    """Return the libcurl version string reported by ctypes in a fresh Python process."""
    if lib_target:
        lib_expr = repr(lib_target)
    else:
        lib_expr = repr("libcurl.so.4")

    code = (
        "import ctypes\n"
        f"lib = ctypes.CDLL({lib_expr})\n"
        "lib.curl_version.restype = ctypes.c_char_p\n"
        "raw = lib.curl_version()\n"
        "print(raw.decode('utf-8', 'replace') if raw else '')\n"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as exc:
        logger.debug("Unable to query libcurl version for %s: %s", lib_target or "runtime", exc)
        return None

    version = result.stdout.strip()
    return version or None


def _extract_libcurl_semver(version_string: Optional[str]) -> Optional[str]:
    if not version_string:
        return None
    first_token = version_string.split()[0]
    if "/" not in first_token:
        return None
    name, version = first_token.split("/", 1)
    if name != "libcurl":
        return None
    return version


def _detect_libcurl_runtime_conflict() -> Tuple[bool, str]:
    """
    Detect a libcurl mismatch before rasterio/GDAL touches native I/O code.

    This specifically guards Conda environments where GDAL was built against the
    env libcurl, but the runtime loader resolves a different system libcurl.
    """
    if _env_flag("FORCE_RASTERIO"):
        return False, ""

    if sys.platform != "linux":
        return False, ""

    conda_prefix = os.environ.get("CONDA_PREFIX")
    if not conda_prefix:
        return False, ""

    expected_libcurl = Path(conda_prefix) / "lib" / "libcurl.so.4"
    if not expected_libcurl.exists():
        return False, ""

    runtime_version_raw = _read_libcurl_version_subprocess(None)
    expected_version_raw = _read_libcurl_version_subprocess(str(expected_libcurl))
    runtime_version = _extract_libcurl_semver(runtime_version_raw)
    expected_version = _extract_libcurl_semver(expected_version_raw)

    if not runtime_version or not expected_version:
        return False, ""

    if runtime_version == expected_version:
        return False, ""

    return (
        True,
        "libcurl runtime mismatch detected "
        f"(runtime={runtime_version_raw}, conda={expected_version_raw})",
    )


def _sanitize_geospatial_env(verbose: bool = False) -> None:
    """
    Normalize PROJ/GDAL env vars before importing/using rasterio.

    Why this helps:
    - VS Code/Conda terminals can inherit stale PROJ_* paths from prior sessions.
    - rasterio wheels bundle their own PROJ/GDAL data; conflicting env vars can break lookups.
    """
    actions: list[str] = []

    # 1) Resolve PROJ_LIB legacy alias to PROJ_DATA, then clear PROJ_LIB to avoid ambiguity.
    proj_lib = os.environ.get("PROJ_LIB")
    if proj_lib:
        if os.path.exists(proj_lib) and not os.environ.get("PROJ_DATA"):
            os.environ["PROJ_DATA"] = proj_lib
            actions.append("set PROJ_DATA from PROJ_LIB")
        os.environ.pop("PROJ_LIB", None)
        try:
            os.unsetenv("PROJ_LIB")
        except Exception:
            pass
        actions.append("unset PROJ_LIB")

    # 2) Remove broken paths early.
    for key in ("PROJ_DATA", "GDAL_DATA"):
        value = os.environ.get(key)
        if value and not os.path.exists(value):
            os.environ.pop(key, None)
            try:
                os.unsetenv(key)
            except Exception:
                pass
            actions.append(f"unset {key} (missing path)")

    # 3) If unset, use rasterio bundled data directories when available.
    try:
        import rasterio

        rio_dir = Path(rasterio.__file__).resolve().parent
        proj_candidate = rio_dir / "proj_data"
        gdal_candidate = rio_dir / "gdal_data"

        if not os.environ.get("PROJ_DATA") and proj_candidate.exists():
            os.environ["PROJ_DATA"] = str(proj_candidate)
            actions.append("set PROJ_DATA from rasterio bundle")

        if not os.environ.get("GDAL_DATA") and gdal_candidate.exists():
            os.environ["GDAL_DATA"] = str(gdal_candidate)
            actions.append("set GDAL_DATA from rasterio bundle")
    except Exception as exc:
        logger.debug("Unable to inspect rasterio bundled data paths: %s", exc)

    if verbose and actions:
        print("[INFO] Geospatial env normalized: " + ", ".join(actions))

# ─────────────────────────────────────────────────────
#  ESA WorldCover 2021 classes → roughness length z0 (m)
#  Source: Davenport roughness classification cross-referenced
#  with WAsP/GWA tables and ESA class descriptions.
#
#  Class IDs: https://esa-worldcover.org/en/data
#  10  Tree cover                → 1.00  (dense forest)
#  20  Shrubland                 → 0.20  (low bushes / shrubs)
#  30  Grassland                 → 0.05  (short grass / meadow)
#  40  Cropland                  → 0.08  (crops, hedgerows)
#  50  Built-up                  → 0.40  (urban, suburban)
#  60  Bare / sparse vegetation  → 0.01  (bare soil, rock)
#  70  Snow and ice              → 0.001 (very smooth)
#  80  Permanent water bodies    → 0.001 (sea/lake, very smooth)
#  90  Herbaceous wetland        → 0.07  (reeds, rushes)
#  95  Mangroves                 → 0.50  (dense coastal forest)
#  100 Moss and lichen           → 0.03  (tundra)
# ─────────────────────────────────────────────────────
ESA_Z0_TABLE: dict[int, float] = {
    10:  1.00,   # Tree cover
    20:  0.20,   # Shrubland
    30:  0.05,   # Grassland
    40:  0.08,   # Cropland
    50:  0.40,   # Built-up
    60:  0.01,   # Bare / sparse vegetation
    70:  0.001,  # Snow and ice
    80:  0.001,  # Permanent water bodies
    90:  0.07,   # Herbaceous wetland
    95:  0.50,   # Mangroves
    100: 0.03,   # Moss and lichen
}

# Fallback z0 when class is unknown or raster unavailable
Z0_DEFAULT = 0.03  # m  (open terrain, Davenport class 2)

# ESA WorldCover COG URL template
ESA_URL = "https://esa-worldcover.s3.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"

# Global COG (single mosaic) — simpler for arbitrary bounding boxes:
ESA_GLOBAL_COG_URL = (
    "https://opengeodata.universiteitleiden.nl/esa-worldcover/"
    "2021/ESA_WorldCover_10m_2021_v200.vrt"
)

# Preferred source: Global Wind Atlas COG (stable public endpoint)
STAC_COG_URL = "https://api.globalwindatlas.info/cogs/GWA4_ESA_WorldCover_2021_50m.tif"

# Buffer in degrees to add around the route rectangle when downloading
BBOX_MARGIN_DEG = 0.05


class RoughnessProvider:
    """
    Manages a local cache of ESA WorldCover roughness tiles indexed by spatial extent.

    Parameters
    ----------
    raster_dir : str or Path
        Directory where downloaded raster tiles are stored.
        Created automatically if it does not exist.
    z0_scale : float
        Global multiplicative factor applied to all z0 values (calibration).
        Default 1.0 (no adjustment).
    source_url : str, optional
        Override the COG source URL.  Default uses ESA STAC mosaic.
    """

    _INDEX_DB = "roughness_index.db"
    _RASTER_PREFIX = "roughness_"
    _SQLITE_TIMEOUT_S = 30.0
    _SQLITE_BUSY_TIMEOUT_MS = 30_000
    _SQLITE_MAX_RETRIES = 5
    _SQLITE_RETRY_BASE_DELAY_S = 0.2
    _SQLITE_JOURNAL_MODE = os.environ.get("ROUGHNESS_SQLITE_JOURNAL_MODE", "DELETE").upper()
    _INDEX_LOCK_FILE = "roughness_index.db.lock"

    def __init__(
        self,
        raster_dir: Optional[str] = None,
        z0_scale: float = 1.0,
        source_url: Optional[str] = None,
        index_dir: Optional[str] = None,
        cache_dir: Optional[str] = None,
    ) -> None:
        # Backward compatibility: cache_dir is accepted as deprecated alias for raster_dir.
        selected_raster_dir = raster_dir or cache_dir
        if selected_raster_dir is None:
            raise ValueError("raster_dir is required")

        self.raster_dir = Path(selected_raster_dir)
        self.raster_dir.mkdir(parents=True, exist_ok=True)
        # Keep rasters in raster_dir (can be NAS), but store SQLite index locally by default.
        biwipy_cache_root = os.environ.get("BIWIPY_CACHE_DIR")
        default_index_dir = (
            os.path.join(biwipy_cache_root, "roughness_index")
            if biwipy_cache_root
            else (
                os.environ.get("ROUGHNESS_INDEX_DIR")
                or os.path.expanduser("~/.cache/biwipy/roughness_index")
            )
        )
        self.index_dir = Path(
            index_dir
            or default_index_dir
        )
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.z0_scale = z0_scale
        self.source_url = source_url or STAC_COG_URL
        self._db_path = self.index_dir / self._INDEX_DB
        self._init_db()

        # In-memory raster data loaded by prepare()
        self._z0_array: Optional[Any] = None  # numpy ndarray
        self._transform: Optional[Any] = None  # rasterio Affine
        self._crs: Optional[Any] = None  # raster CRS
        self._bounds: Optional[Tuple[float, float, float, float]] = None  # west, south, east, north

    # ─────────────────────────────────────────────────────
    #  Public API
    # ─────────────────────────────────────────────────────

    def prepare(
        self,
        south: int,
        north: int,
        west: int,
        east: int,
        verbose: bool = True,
    ) -> bool:
        """
        Ensure a raster covering the given integer-degree rectangle is available
        and load it into memory.

        Parameters
        ----------
        south, north, west, east : int
            Inclusive integer-degree bounding box (from stats.rectangle_SN / _EW).
        verbose : bool
            Print progress messages.

        Returns
        -------
        bool
            True if raster is ready, False if an error occurred (caller should disable roughness).
        """
        if _env_flag("DISABLE_RASTERIO"):
            if verbose:
                print("[WARN] Roughness provider disabled by DISABLE_RASTERIO=1.")
            return False

        has_conflict, reason = _detect_libcurl_runtime_conflict()
        if has_conflict:
            logger.error("RoughnessProvider.prepare skipped: %s", reason)
            if verbose:
                print(f"[WARN] {reason}. Falling back to default z0={Z0_DEFAULT} m.")
                print("[WARN] Set FORCE_RASTERIO=1 to bypass this guard and retry.")
            return False

        _sanitize_geospatial_env(verbose=verbose)
        try:
            bbox = (
                west  - BBOX_MARGIN_DEG,
                south - BBOX_MARGIN_DEG,
                east  + BBOX_MARGIN_DEG,
                north + BBOX_MARGIN_DEG,
            )
            raster_path = self._get_or_download(bbox, verbose=verbose)
            self._load_into_memory(raster_path, bbox, verbose=verbose)
            return True
        except Exception as exc:
            logger.error("RoughnessProvider.prepare failed: %s", exc, exc_info=True)
            if verbose:
                print(f"[WARN] Roughness map unavailable ({exc}). Falling back to default z0={Z0_DEFAULT} m.")
            return False

    def get_z0(self, lat: float, lon: float) -> Optional[float]:
        """
        Return roughness length z0 (m) at the given coordinates.

        Returns None if the raster is not loaded or the point is outside the extent.
        Caller should fall back to the grib_manager internal default when None is returned.
        """
        if self._z0_array is None:
            return None
        try:
            return self._lookup_z0(lat, lon)
        except Exception as exc:
            logger.debug("z0 lookup failed at (%.4f, %.4f): %s", lat, lon, exc)
            return None

    # ─────────────────────────────────────────────────────
    #  SQLite index helpers
    # ─────────────────────────────────────────────────────

    def _init_db(self) -> None:
        journal_mode = self._SQLITE_JOURNAL_MODE
        if journal_mode not in {"DELETE", "WAL", "TRUNCATE", "PERSIST", "MEMORY", "OFF"}:
            logger.warning("Invalid ROUGHNESS_SQLITE_JOURNAL_MODE=%s, fallback to DELETE", journal_mode)
            journal_mode = "DELETE"

        with self._connect() as con:
            # Configure journal mode once at startup. Doing this per connection can itself cause lock contention.
            con.execute(f"PRAGMA journal_mode = {journal_mode}")
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS raster_index (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename    TEXT NOT NULL UNIQUE,
                    south       REAL NOT NULL,
                    north       REAL NOT NULL,
                    west        REAL NOT NULL,
                    east        REAL NOT NULL,
                    source_url  TEXT,
                    downloaded  TEXT,   -- ISO datetime
                    filesize    INTEGER
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(
            str(self._db_path),
            timeout=self._SQLITE_TIMEOUT_S,
            isolation_level=None,
        )
        con.execute(f"PRAGMA busy_timeout = {self._SQLITE_BUSY_TIMEOUT_MS}")
        con.execute("PRAGMA synchronous = NORMAL")
        return con

    def _find_covering_raster(
        self,
        west: float,
        south: float,
        east: float,
        north: float,
    ) -> Optional[Path]:
        """Return path of a local raster that fully covers the requested bbox."""
        with self._connect() as con:
            row = con.execute(
                """
                SELECT filename FROM raster_index
                WHERE south <= ? AND north >= ? AND west <= ? AND east >= ?
                ORDER BY (east - west) * (north - south)   -- prefer smallest covering tile
                LIMIT 1
                """,
                (south, north, west, east),
            ).fetchone()
        if row is None:
            return None
        path = self.raster_dir / row[0]
        return path if path.exists() else None

    def _register_raster(
        self,
        filename: str,
        south: float,
        north: float,
        west: float,
        east: float,
        source_url: str,
        filesize: int,
    ) -> None:
        from datetime import datetime, timezone
        lock_path = self.index_dir / self._INDEX_LOCK_FILE
        now_iso = datetime.now(timezone.utc).isoformat()
        last_exc: Optional[Exception] = None
        with open(lock_path, "a") as lock_file:
            try:
                import fcntl
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            except Exception:
                # Best effort: if flock is unavailable, keep SQLite retry path below.
                pass

            try:
                for attempt in range(self._SQLITE_MAX_RETRIES):
                    try:
                        with self._connect() as con:
                            con.execute(
                                "BEGIN IMMEDIATE"
                            )
                            con.execute(
                                """
                                INSERT OR REPLACE INTO raster_index
                                    (filename, south, north, west, east, source_url, downloaded, filesize)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                (filename, south, north, west, east, source_url, now_iso, filesize),
                            )
                        return
                    except sqlite3.OperationalError as exc:
                        last_exc = exc
                        if "database is locked" not in str(exc).lower() or attempt == self._SQLITE_MAX_RETRIES - 1:
                            raise
                        delay = self._SQLITE_RETRY_BASE_DELAY_S * (2 ** attempt)
                        logger.warning(
                            "SQLite index busy while registering roughness raster (attempt %d/%d). Retrying in %.2fs.",
                            attempt + 1,
                            self._SQLITE_MAX_RETRIES,
                            delay,
                        )
                        time.sleep(delay)
            finally:
                try:
                    import fcntl
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass

        if last_exc is not None:
            raise last_exc

    # ─────────────────────────────────────────────────────
    #  Download / cache logic
    # ─────────────────────────────────────────────────────

    def _get_or_download(
        self,
        bbox: Tuple[float, float, float, float],
        verbose: bool = True,
    ) -> Path:
        """
        Return path to a local raster covering `bbox` (west, south, east, north).
        Download from COG source if not already cached.
        """
        west, south, east, north = bbox

        existing = self._find_covering_raster(west, south, east, north)
        if existing is not None:
            if verbose:
                print(f"[OK] Roughness raster found in cache: {existing.name}")
            return existing

        return self._download_cog_window(bbox, verbose=verbose)

    def _download_cog_window(
        self,
        bbox: Tuple[float, float, float, float],
        verbose: bool = True,
    ) -> Path:
        """
        Download a windowed portion of the ESA WorldCover COG and save as GeoTIFF.
        Uses rasterio to read only the bbox window from the remote COG.
        """
        import rasterio
        from rasterio.crs import CRS
        from rasterio.warp import transform_bounds
        from rasterio.windows import Window

        west, south, east, north = bbox
        filename = f"{self._RASTER_PREFIX}{south:.2f}_{north:.2f}_{west:.2f}_{east:.2f}.tif"
        dest_path = self.raster_dir / filename

        # If raster is already on disk but index row is missing (new local index), just register it.
        if dest_path.exists():
            filesize = dest_path.stat().st_size
            self._register_raster(filename, south, north, west, east, self.source_url, filesize)
            if verbose:
                print(f"[OK] Roughness raster already present on disk: {dest_path.name} (index repaired)")
            return dest_path

        if verbose:
            print(
                f"[INFO] Downloading roughness raster from ESA WorldCover...\n"
                f"  bbox: W={west:.2f} S={south:.2f} E={east:.2f} N={north:.2f}\n"
                f"  -> {dest_path}"
            )

        env_opts = {
            "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
            "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.vrt",
        }
        try:
            # On some Windows setups GDAL_DATA is not initialized, causing gdalvrt.xsd errors.
            from rasterio.env import GDALDataFinder
            gdal_data = GDALDataFinder().search()
            if gdal_data:
                env_opts["GDAL_DATA"] = gdal_data
        except Exception:
            # Best effort only; if lookup fails, continue with defaults.
            pass

        with rasterio.Env(**env_opts):  # type: ignore[arg-type]
            with rasterio.open(self.source_url) as src:
                src_crs = src.crs or CRS.from_epsg(4326)

                # Source may not be in EPSG:4326; transform bbox before creating raster window.
                if src_crs.to_epsg() == 4326:
                    w_src, s_src, e_src, n_src = west, south, east, north
                else:
                    w_src, s_src, e_src, n_src = transform_bounds(
                        "EPSG:4326",
                        src_crs,
                        west,
                        south,
                        east,
                        north,
                        densify_pts=21,
                    )

                window = self._window_from_bounds_safe(
                    src.transform,
                    src.width,
                    src.height,
                    w_src,
                    s_src,
                    e_src,
                    n_src,
                )
                data = src.read(1, window=window)
                win_transform = src.window_transform(window)

                profile = src.profile.copy()
                profile.update(
                    driver="GTiff",
                    height=data.shape[0],
                    width=data.shape[1],
                    transform=win_transform,
                    crs=src_crs,
                    count=1,
                    compress="lzw",
                )

                with rasterio.open(dest_path, "w", **profile) as dst:
                    dst.write(data, 1)

        filesize = dest_path.stat().st_size
        self._register_raster(filename, south, north, west, east, self.source_url, filesize)

        if verbose:
            print(f"  [OK] Saved ({filesize / 1024:.0f} KB), registered in index.")

        return dest_path

    # ─────────────────────────────────────────────────────
    #  In-memory loading and lookup
    # ─────────────────────────────────────────────────────

    def _load_into_memory(
        self,
        raster_path: Path,
        bbox: Tuple[float, float, float, float],
        verbose: bool = True,
    ) -> None:
        """
        Load the raster window that covers `bbox` into memory as a z0 numpy array.
        Converts ESA landcover class codes to z0 values using ESA_Z0_TABLE.
        """
        import numpy as np
        import rasterio
        from rasterio.warp import transform_bounds
        from rasterio.windows import Window

        west, south, east, north = bbox

        with rasterio.open(raster_path) as src:
            src_crs = src.crs
            if src_crs is not None and src_crs.to_epsg() != 4326:
                w_src, s_src, e_src, n_src = transform_bounds(
                    "EPSG:4326",
                    src_crs,
                    west,
                    south,
                    east,
                    north,
                    densify_pts=21,
                )
            else:
                w_src, s_src, e_src, n_src = west, south, east, north

            window = self._window_from_bounds_safe(
                src.transform,
                src.width,
                src.height,
                w_src,
                s_src,
                e_src,
                n_src,
            )
            lc_data = src.read(1, window=window).astype(np.int16)
            transform = src.window_transform(window)
            raster_crs = src.crs

        # Convert landcover class -> z0
        z0_data = np.full(lc_data.shape, Z0_DEFAULT, dtype=np.float32)
        for lc_class, z0_val in ESA_Z0_TABLE.items():
            z0_data[lc_data == lc_class] = float(z0_val)

        # Apply calibration scale factor
        z0_data *= self.z0_scale

        self._z0_array = z0_data
        self._transform = transform
        self._crs = raster_crs
        self._bounds = (west, south, east, north)

        if verbose:
            print(
                f"  [OK] z0 map loaded: {lc_data.shape[1]}x{lc_data.shape[0]} px, "
                f"z0 range [{z0_data.min():.4f} - {z0_data.max():.4f}] m"
            )

    def _lookup_z0(self, lat: float, lon: float) -> Optional[float]:
        """
        Return z0 at (lat, lon) using nearest-neighbor lookup in the in-memory array.
        Returns None if the point is outside the loaded extent.
        """
        import numpy as np

        west, south, east, north = self._bounds  # type: ignore[misc]
        if not (south <= lat <= north and west <= lon <= east):
            return None

        x = lon
        y = lat
        if self._crs is not None:
            try:
                from rasterio.warp import transform as crs_transform
                if self._crs.to_epsg() != 4326:
                    xs, ys = crs_transform("EPSG:4326", self._crs, [lon], [lat])[:2]  # type: ignore[misc]
                    x, y = xs[0], ys[0]
            except Exception:
                return None

        transform = self._transform
        assert transform is not None
        assert self._z0_array is not None
        # rasterio Affine: col = (x - x0) / pixel_width
        #                  row = (y - y0) / pixel_height
        col = int((x - transform.c) / transform.a)
        row = int((y - transform.f) / transform.e)

        nrows, ncols = self._z0_array.shape
        col = max(0, min(col, ncols - 1))
        row = max(0, min(row, nrows - 1))

        return float(self._z0_array[row, col])

    @staticmethod
    def _window_from_bounds_safe(transform, width: int, height: int, west: float, south: float, east: float, north: float):
        """Compute a raster window from bounds without calling rasterio.windows.from_bounds.

        This avoids a native crash observed on some Windows/GDAL builds with very large COG rasters.
        """
        from rasterio.windows import Window

        a = transform.a
        e = transform.e
        c = transform.c
        f = transform.f

        if a == 0 or e == 0:
            raise ValueError("Invalid raster transform with zero pixel size")

        # Pixel coordinates of bounds corners
        col_w = (west - c) / a
        col_e = (east - c) / a
        row_n = (north - f) / e
        row_s = (south - f) / e

        col_min = int(math.floor(min(col_w, col_e)))
        col_max = int(math.ceil(max(col_w, col_e)))
        row_min = int(math.floor(min(row_n, row_s)))
        row_max = int(math.ceil(max(row_n, row_s)))

        # Clamp to dataset extent
        col_min = max(0, min(col_min, width))
        col_max = max(0, min(col_max, width))
        row_min = max(0, min(row_min, height))
        row_max = max(0, min(row_max, height))

        win_w = col_max - col_min
        win_h = row_max - row_min
        if win_w <= 0 or win_h <= 0:
            raise ValueError("Requested bbox does not intersect raster extent")

        return Window(col_off=col_min, row_off=row_min, width=win_w, height=win_h)  # type: ignore[call-arg]

    # ─────────────────────────────────────────────────────
    #  Utilitaires
    # ─────────────────────────────────────────────────────

    def list_cached_rasters(self) -> list:
        """Return list of registered rasters (dict per row)."""
        with self._connect() as con:
            rows = con.execute(
                "SELECT filename, south, north, west, east, downloaded, filesize FROM raster_index ORDER BY downloaded DESC"
            ).fetchall()
        return [
            dict(zip(["filename", "south", "north", "west", "east", "downloaded", "filesize"], r))
            for r in rows
        ]
