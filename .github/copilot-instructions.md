# RefWindCycle: AI Coding Agent Instructions

## Project Overview
**RefWindCycle** is a Python-based cycling performance analysis tool that simulates cyclist behavior by integrating GPS traces, GRIB meteorological data, and physics-based power models. It validates Strava metrics against simulated performance for route analysis and model calibration.

## Architecture

### Core Data Pipeline
1. **GPX Input** → Load GPS points with elevation and timestamps
2. **Segment Creation** → Convert points to distance/slope/bearing segments
3. **GRIB Weather Data** → Fetch wind (U10/V10 components) and gust from meteorological files
4. **Wind Calculation** → Project wind vectors onto segment bearings
5. **Physics Simulation** → Calculate speed/power using bike dynamics
6. **Strava Comparison** → Validate against real-world power averages

### Key Modules

- **`bike_physics.py`** - Core physics engine with two power solvers (`solve_speed_for_power()` and `solve_speed_dynamic()`). Contains adaptive power modes (realistic, conservative, aggressive) and **critical downhill speed limiter** (see below).
- **`gribmg.py`** - GRIB file parser/interpolator using PyGrib. Handles spatial/temporal wind interpolation with caching.
- **`gpx_tools.py`** - GPX loading, 1Hz resampling, Savitzky-Golay smoothing, elevation noise detection.
- **`anareswind.py`** - Segment merging, wind impact analysis, visualization utilities.
- **`calibrate_cda.py`** - CdA (drag coefficient) optimization using bisection search to match Strava power.
- **`chung_calibrator.py`** - Alternative calibration using `model_power()` and least-squares fitting.

### External Dependencies
- **PyGrib**: GRIB file parsing (requires installation)
- **Stravalib**: Strava API client (config in `/mnt/nasdocker/grib/.config/strava/` or `G:/grib/.config/strava/`)
- **GPXPy**: GPX parsing
- **NumPy, SciPy**: Numerics and optimization

## GRIB Format & Wind Data

### GRIB File Specifications
- **Format**: GRIB2 (Gridded Binary, WMO standard)
- **Grid Resolution**: 0.25° × 0.25° (approximately 28 km at equator)
- **Coverage**: Global (0–360° longitude, -90°–+90° latitude)
- **Grid Dimensions**: 1440×721 points (longitude × latitude)
  - Latitude table: `i/4 - 90` for i ∈ [0, 720]
  - Longitude table: `i/4` for i ∈ [0, 1439]
- **Time Cadence**: Typically 3-hour intervals (0Z, 3Z, 6Z, 9Z, 12Z, etc.)

### Wind Variables in GRIB Files
Three mandatory wind parameters per timestamp:

| Parameter | GRIB shortName | Units | Meaning |
|-----------|---|---|---|
| **U-Component** | `u10` or `10u` | m/s | Zonal (East-West) wind at 10m height |
| **V-Component** | `v10` or `10v` | m/s | Meridional (North-South) wind at 10m height |
| **Wind Gust** | `gust` | m/s | Maximum gust during the 3-hour period |

**Formula for True Wind Speed (TWS)**: `TWS = sqrt(u10² + v10²)`  
**Formula for True Wind Direction (TWD)**: `TWD = atan2(u10, v10)` (meteorological convention: 0°=N, 90°=E)

### PyGrib Reading in gribmg.py

```python
for grb in pygrib.open(filename):
    ctime = grb.validDate  # Timestamp when forecast is valid
    shortname = grb.shortName  # Returns 'u10', 'v10', or 'gust'
    data, lats, lons = grb.data()  # Numpy arrays: (721, 1440) grid
```

### Spatial Interpolation Strategy

The module uses **bilinear interpolation** for points not on grid boundaries:

1. **Identify bounding grid points**: If GPS point (lat, lon) falls between grid points:
   - Lower bounds: `la1 = floor(lat × 4) / 4`, `lo1 = floor(lon × 4) / 4`
   - Upper bounds: `la2 = ceil(lat × 4) / 4`, `lo2 = ceil(lon × 4) / 4`

2. **Extract four corners**: Get U10/V10/Gust at (lo1,la1), (lo2,la1), (lo1,la2), (lo2,la2)

3. **Bilinear interpolation formula**:
   ```
   f(x,y) = f₁₁(x₂-x)(y₂-y) + f₂₁(x-x₁)(y₂-y) + f₁₂(x₂-x)(y-y₁) + f₂₂(x-x₁)(y-y₁)
            ────────────────────────────────────────────────────────────────────────
                              (x₂-x₁)(y₂-y₁)
   ```

### Temporal Interpolation

1. **Find bracketing timestamps**: Locate `t1` and `t2` where `t1 ≤ query_time < t2`
2. **Linear interpolation**: Interpolate U10/V10/Gust linearly between timestamps
3. **Timestamp validation**:
   - If query_time < first GRIB timestamp → **Error** (data out of range)
   - If query_time > last GRIB timestamp → **Error** (data out of range)

### Wind-to-Segment Projection

When computing wind impact on a segment with bearing θ:

```python
# Wind vector components
tws = sqrt(u10² + v10²)  # True wind speed
twd = atan2(u10, v10)    # True wind direction

# Angular difference (normalized to [0, 180°])
diff_angle = (twd - bearing) % 360
if diff_angle > 180: diff_angle = 360 - diff_angle
rad_diff = radians(diff_angle)

# Component projections
wind_along = tws * cos(rad_diff)      # Headwind (+) / Tailwind (-)
gust_along = gust * cos(rad_diff)     # Gust component along axis
crosswind = tws * sin(rad_diff)       # Lateral force (not used in power model)

# Effective wind (weights gusts by ratio_wind ≈ 0.25)
# Cyclists slow more during gusts than re-accelerate afterward
effective_wind_along = wind_along + ratio_wind * (gust_along - wind_along)
```

### Caching Mechanism

**Location**: `~/.cache/grib/YYYYMMDD/` (organized by date from GRIB filename)

**Cache Strategy**:
- **First run**: Parse GRIB files with PyGrib, extract U10/V10/Gust arrays, serialize to pickle
- **Subsequent runs**: Load from cache (100x faster than PyGrib parsing)
- **Automatic purge**: Remove cache files older than 48 hours
- **Update capability**: `Grib.update_wind()` merges new GRIB files, replacing duplicate timestamps

**Cache Format**: Serialized `grib_essential_data` object containing:
```python
lst_gribtimes: List[datetime]  # Timestamps
lst_u10: List[ndarray]         # U-component grids (721, 1440)
lst_v10: List[ndarray]         # V-component grids (721, 1440)
lst_gust: List[ndarray]        # Gust grids (721, 1440)
```

### Wind Data Validation Rules

1. **Mandatory parameters**: U10, V10, and Gust must ALL be present for each timestamp
2. **Gust floor**: Ensure `gust ≥ tws` (gust cannot be weaker than mean wind)
3. **Grid alignment**: Verify 1440×721 dimensions after reading
4. **Time ordering**: GRIB timestamps must be sorted ascending

## Critical Patterns & Conventions

### ⚡ Physics Model Critical Behaviors

#### Downhill Speed Limiter (Jan 2026 fix)
Realistic cyclist behavior includes braking on steep descents. The model applies **dynamic velocity ceiling reduction** on downhill slopes:
- Constants: `DESCENTE_VITESSE_MAX_REDUCTION_FACTOR = 2.5`, `DESCENTE_VITESSE_MAX_REDUCTION_CAP = 0.40`
- Logic: `v_max_limit = v_max * (1 - abs(slope) * FACTOR)`, capped at `v_max * (1 - CAP)`
- Example: -10% slope reduces v_max by 25%, preventing unrealistic 80+ km/h speeds
- Applied in: `solve_speed_for_power()`, `solve_speed_dynamic()`
- **Never remove or disable this without explicit user request** - it ensures simulation/Strava alignment

#### Mode-Specific Power Multipliers
Three power adjustment modes for different slopes:
- **Realistic** (default): `FACTEUR_MONTEE_FORTE_REALISTE = 3.5` (steep climbs), `FACTEUR_DESCENTE_FORTE_REALISTE = 20` (steep descent reduction)
- **Conservative**: More aggressive altitude penalties (`FACTEUR_MONTEE = 2.0`)
- **Aggressive**: Less power reduction (`FACTEUR_MONTEE = 4.0`)
- **Custom**: User-defined factors
- Slope thresholds (e.g., `SEUIL_MONTEE_FORTE = 0.08`) determine which multiplier applies

### Segment Processing Conventions
- **Merge short segments** with `merge_short_segments()` BEFORE wind calculation to avoid noise
- **Thresholds for merging**: distance < 50m, bearing diff < 20°, slope diff < 10%
- **Altitude processing**: 1Hz resampling → Savitzky-Golay smoothing (window=19) → GPS noise removal
- **Max slope clipping**: Limit to ±15% to reject GPS artifacts

### Configuration Paths (OS-Dependent)
```python
if os.name == 'posix':
    configdir = "/mnt/nasdocker/grib/.config/"  # Linux
else:
    configdir = "G:/grib/.config/"               # Windows
```
- GRIB data: `configdir + 'grib/data/'`
- GPX files: `configdir + 'grib/data/gpx/'`
- Strava tokens: `configdir + 'strava/strava_tokens.json'`

## Developer Workflows

### Calibration Pipeline
1. **Prepare GPX**: Run `clean_gpx_for_calibration.py` to remove GPS noise
2. **Run calibration**: `python calibrate_cda.py` (configures CdA for target Strava power)
3. **Validate**: Compare simulated power curve vs. Strava using `compare_wind_impact.py`

### Testing & Validation
- **Test files** follow naming: `test_*.py` (not tests/ directory)
- **Key tests**: `test_corrections_apply.py` (downhill fix), `test_wind_impact.py` (wind projection)
- **Run tests directly**: `python test_corrections_apply.py` (prints detailed output)
- **No pytest integration** - scripts use print statements and assertions

### Common Debugging Tasks
- **Wind interpolation issues**: Check `gribmg.py` timestamps; enable `verbose=True` in Grib constructor
- **Unrealistic speeds**: First suspect downhill limiter was disabled; check `DESCENTE_VITESSE_MAX_REDUCTION_*` constants
- **CdA calibration fails**: Verify Strava power is realistic; check GRIB file availability
- **Segment merging too aggressive**: Reduce `min_distance` or increase `max_bearing_diff` in `merge_short_segments()`

## Important Behaviors to Preserve

1. **Strava token refresh** (`Clientstrava_test.py`): Handles OAuth2 expiration automatically; store tokens in JSON
2. **GRIB caching** (`Grib(bcache=True)`): Dramatically speeds up repeated simulations; clear cache when updating GRIB data
3. **Adaptive solver selection**: Use `solve_speed_dynamic()` for realistic acceleration; use `solve_speed_for_power()` for steady-state analysis
4. **Slope-based logic branching**: Many functions check `SEUIL_*` constants (thresholds); preserve exact numerical values as they've been calibrated

## Anti-Patterns to Avoid

- ❌ **Don't** modify physics constants without testing against test suites (especially downhill limiter)
- ❌ **Don't** skip segment merging before GRIB wind queries (causes interpolation noise)
- ❌ **Don't** use relative imports in top-level test scripts; use absolute imports with module path
- ❌ **Don't** assume GPS timestamps are always valid; always validate with `t_start` parameter
- ❌ **Don't** ignore `SEUIL_DESCENTE_MAX = 0.00` logic; it's a critical classifier for downhill behavior

## Recent Major Changes (Jan 2026)
- **Downhill speed limiting**: Prevents unrealistic speeds in steep descents with favorable wind
- **Constant renaming**: Unified naming conventions for slope thresholds (`SEUIL_*`)
- **Documentation**: Added `CORRECTIONS_DESCENTE_VENT.md`, `CHANGELOG.md` for transparency

## File Organization
```
refwindcycle/
├── bike_physics.py              # Physics engine + calibration
├── gribmg.py                    # Weather data handling
├── gpx_tools.py                 # GPS/elevation processing
├── anareswind.py                # Segment analysis + visualization
├── calibrate_cda.py             # Main calibration entry point
├── chung_calibrator.py          # Alternative calibration method
├── test_*.py                    # Validation & debugging scripts
├── Clientstrava_test.py         # Strava API integration
└── .github/copilot-instructions.md  # This file
```

## When Adding New Features
1. Preserve backward compatibility with existing calibrations
2. Add slope-threshold checks using existing `SEUIL_*` constants
3. Test against `test_corrections_apply.py` to ensure downhill behavior is intact
4. Document in `CHANGELOG.md` with issue context
5. Maintain OS-agnostic path handling (posix/Windows check)
