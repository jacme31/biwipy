# Simulation and Replay

Simulation is the core feature of the library.
It applies a cycling physics model using your input data (rider, route, weather, behavior).

You first create a [Simulator object](SIM-label), then run:

- [Prediction](Pred-label): estimate performance on a route using forecast wind.
- [Replay](Repl-label): analyze a completed ride using GPX timestamps.

Both modes return a structured [SimulationResult](SR-label) for analysis.

(SIM-label)=
## Simulator Class

`Simulator` is the main public interface for route simulation.

Constructor inputs:

- `wind`: `weather.grib` object (or `None` for no-wind simulation)
- `behavior`: cyclist behavior profile
- cyclist parameters: `CdA`, `Cr`, `m`

```{code-block} python3
from biwipy.weather import WeatherProvider
from biwipy.core.cyclist_params import CyclistBehavior
from biwipy.core import Simulator

# Weather object (gribs_list obtained earlier)
weather = WeatherProvider(gribs_list)
mygrib = weather.grib

# Behavior profile
my_profile = CyclistBehavior(
    uphill='realistic',
    downhill='realistic',
    corner='realistic',
)

# Rider + bike parameters
my_cda = 0.480
my_crr = 0.005
my_mass = 80.0

# Create simulator
sim = Simulator(mygrib, behavior=my_profile, CdA=my_cda, Cr=my_crr, m=my_mass)
```

Useful conversion helpers:

```{code-block} python3
# Convert v0 (m/s) to P0 (W)
v0 = 25 / 3.6
P0 = sim.P0_from_v0(v0)

# Convert P0 (W) to v0 (m/s)
P0 = 200.0
v0 = sim.v0_from_P0(P0)
```

(Pred-label)=
## Prediction

Use `simulate_future()` to predict performance with weather forecast.

Required inputs:

- preprocessed route segments
- ride start datetime
- reference effort (`P0` or `v0`)

```{code-block} python3
from datetime import datetime
from zoneinfo import ZoneInfo
from biwipy.analysis import RouteAnalyzer

# Preprocess GPX
analyzer = RouteAnalyzer()
gpx_result = analyzer.process_gpx('route.gpx')

# Start time
t_start = datetime(2026, 2, 23, 10, 0, 0, tzinfo=ZoneInfo('UTC'))

# Run prediction
result = sim.simulate_future(
    segments_in=gpx_result.segments,
    t_start=t_start,
    P0=200.0,
)

print(f"Estimated time: {result.time.total_hours:.2f} h")
print(f"Average speed: {result.speed.avg:.1f} km/h")
print(f"Wind score: {result.wind_score.grade}")
```

(Repl-label)=
## Replay

Use `simulate_replay()` for post-ride analysis when GPX timestamps are available.

Required input:

- preprocessed segments with timestamps

Notes:

- `t_start` is auto-extracted from GPX by default.
- `P0` is not required for replay.

```{code-block} python3
from biwipy.analysis import RouteAnalyzer

analyzer = RouteAnalyzer()
gpx_result = analyzer.process_gpx('ride_with_timestamps.gpx')

result = sim.simulate_replay(
    segments_in=gpx_result.segments,
)

print(f"Actual time: {result.time.total_hours:.2f} h")
print(f"Average speed: {result.speed.avg:.1f} km/h")
print(f"Wind score: {result.wind_score.grade}")

if result.power and result.power.P0_calibrated is not None:
    print(f"Calibrated P0: {result.power.P0_calibrated:.1f} W")
```

(SR-label)=
## Simulation Results

`simulate_future()` and `simulate_replay()` return a `SimulationResult` object.

### Main Output Structure

Top-level fields include:

- `distance`: route length and segment count
- `time`: total seconds, minutes, hours
- `speed`: average, min, max, moving average
- `power` (optional): average/min/max and calibrated `P0` when available
- `wind`: TWS and average TWD
- `gusts`: gust statistics and positions
- `slopes`: terrain, virtual (wind), and effective slopes
- `wind_along_trajectory`: headwind/tailwind split
- `crosswind`: lateral wind statistics
- `wind_score`: grade and safety/performance details
- `segments`: full segment list for advanced analysis and plotting

### Complete Field Reference (Python object)

Use this section when you need the exact field names.

Top-level `SimulationResult` fields:

- `segments: List[Dict]`
- `distance: DistanceAnalysis`
- `time: TimeAnalysis`
- `speed: SpeedAnalysis`
- `power: Optional[PowerAnalysis]`
- `wind: WindAnalysis`
- `gusts: GustAnalysis`
- `slopes: SlopeAnalysis`
- `wind_along_trajectory: WindAlongTrajectoryAnalysis`
- `crosswind: CrosswindAnalysis`
- `wind_score: WindScore`
- `t_start: Optional[datetime]`

Nested fields:

- `distance`: `total_km`, `segment_count`
- `time`: `total_seconds`, `total_minutes`, `total_hours`
- `speed`: `avg`, `min`, `max`, `moving_avg`
- `power` (optional): `avg`, `min`, `max`, `P0_calibrated`
- `wind`:
    - `tws`: `avg`, `min`, `max`, `min_at_km`, `max_at_km`
    - `twd_avg`, `twd_compass`
    - convenience properties: `tws_avg_kmh`, `tws_min_kmh`, `tws_max_kmh`
- `gusts`: `avg`, `min`, `max`, `min_at_km`, `max_at_km`
- `slopes`:
    - `terrain`: `avg_pct`, `min_pct`, `max_pct`, `deniv_pos_m`, `deniv_neg_m`
    - `virtual`: `avg_pct`, `min_pct`, `max_pct`, `deniv_pos_m`, `deniv_neg_m`
    - `effective`: `avg_pct`, `min_pct`, `max_pct`, `deniv_pos_m`, `deniv_neg_m`
- `wind_along_trajectory`:
    - `headwind`: `percentage`, `distance_km`, `avg_kmh`, `min_kmh`, `max_kmh`, `min_at_km`, `max_at_km`
    - `tailwind`: `percentage`, `distance_km`, `avg_kmh`, `min_kmh`, `max_kmh`, `min_at_km`, `max_at_km`
- `crosswind`: `avg_kmh`, `min_kmh`, `max_kmh`, `min_at_km`, `max_at_km`
- `wind_score`: `grade`, `reason`, `performance_grade`, `performance_score`, `safety_grade`, `safety_danger_score`

Utility methods:

- `result.to_dict()` -> compact JSON-ready dict (excludes `segments`)
- `result.get_segments()` -> full segment list
- `result.segment_count()` -> number of segments
- `result.get_time_at_km(km)` -> estimated passage time at distance `km`

### Common Access Patterns

```{code-block} python3
# Distance and time
print(result.distance.total_km)
print(result.time.total_seconds)
print(result.time.total_hours)

# Speed metrics
print(result.speed.avg)
print(result.speed.max)
print(result.speed.moving_avg)

# Wind metrics
print(result.wind.tws.avg)          # m/s (raw)
print(result.wind.tws.avg_kmh)      # km/h (convenience)
print(result.wind.tws_avg_kmh)      # km/h (shortcut)
print(result.wind.twd_avg)          # degrees
print(result.wind.twd_compass)      # N, NE, E, ...

# Gusts and crosswind
print(result.gusts.max)             # m/s (raw)
print(result.gusts.max_kmh)         # km/h (convenience)
print(result.crosswind.avg_kmh)

# Wind score
print(result.wind_score.grade)
print(result.wind_score.reason)
```

### Slope Breakdown

`result.slopes` contains three complementary views:

- `terrain`: GPX terrain slope only
- `virtual`: slope equivalent induced by wind
- `effective`: terrain + virtual

```{code-block} python3
print(result.slopes.terrain.avg_pct)
print(result.slopes.virtual.avg_pct)
print(result.slopes.effective.avg_pct)
```

### Time of Passage at a Given Distance

For route timing queries, use `get_time_at_km()`:

```{code-block} python3
time_at_50 = result.get_time_at_km(50.0)
print(time_at_50)
```

This is useful for race analysis and intermediate checkpoints.

### JSON Export for API or Reporting

Use `to_dict()` for compact structured export.

```{code-block} python3
payload = result.to_dict()
print(payload['speed'])
print(payload['wind_score'])
```

Notes:

- `to_dict()` excludes `segments` to keep payload size reasonable.
- Use `result.get_segments()` when you need full segment-level detail.
- Key names in `to_dict()` are user-facing and may differ from object attributes (for example `speed.avg` -> `speed.avg_kmh`).
- Rule of thumb:
    - use raw object fields for physics-level work (often SI units),
    - use `_kmh` convenience fields or `to_dict()` for user-facing reports.

#### Complete `to_dict()` key map

Top-level keys:

- `distance`, `time`, `speed`, `wind`, `gusts`, `slopes`, `wind_along_trajectory`, `crosswind`, `wind_score`
- optional: `power`

Nested keys:

- `distance`: `total_km`, `segment_count`
- `time`: `total_seconds`, `total_minutes`, `total_hours`
- `speed`: `avg_kmh`, `min_kmh`, `max_kmh`, `moving_avg_kmh`
- `power` (if present): `avg_watts`, `min_watts`, `max_watts`, optional `P0_calibrated_watts`
- `wind`:
    - `tws`: `avg_kmh`, `min_kmh`, `max_kmh`
    - `twd`: `avg_degrees`, `compass`
- `gusts`: `avg_kmh`, `min_kmh`, `min_at_km`, `max_kmh`, `max_at_km`
- `slopes`:
    - `terrain`: `avg_pct`, `min_pct`, `max_pct`, `deniv_pos_m`, `deniv_neg_m`, `deniv_total_m`
    - `virtual_wind`: `avg_pct`, `min_pct`, `max_pct`, `deniv_pos_m`, `deniv_neg_m`, `deniv_total_m`
    - `effective`: `avg_pct`, `min_pct`, `max_pct`, `deniv_pos_m`, `deniv_neg_m`, `deniv_total_m`
- `wind_along_trajectory`:
    - `headwind`: `percentage`, `distance_km`, `avg_kmh`, `min_kmh`, `min_at_km`, `max_kmh`, `max_at_km`
    - `tailwind`: `percentage`, `distance_km`, `avg_kmh`, `min_kmh`, `min_at_km`, `max_kmh`, `max_at_km`
- `crosswind`: `avg_kmh`, `min_kmh`, `max_kmh`, `min_at_km`, `max_at_km`
- `wind_score`: `grade`, `reason`, `performance_grade`, `performance_score`, `safety_grade`, `safety_danger_score`

### Next Reading

- Input setup: [Input data](Input-data.md)
- Practical debugging: [Troubleshooting](Troubleshooting.md)
- Operational recommendations: [Tips](Tips.md)