# RefWindCycle Core Module

Documentation for `refwindcycle.core` - physics engine and cyclist behavior models.

## Overview

The **core** module contains the fundamental physics engine for cycling performance simulation:

- **`bike_physics.py`** : Bicycle dynamics, power calculations, speed solvers
- **`cyclist_params.py`** : Cyclist behavior profiles (realistic, conservative, aggressive)
- **`simulator.py`** : High-level API for route simulation (future/replay modes)
- **`simulation_result.py`** : Structured output with comprehensive statistics

## Quick Start: Simulator API

The `Simulator` class is the main public interface for route simulation.

### Basic Usage

```python
from refwindcycle.core import Simulator
from refwindcycle.core.cyclist_params import CyclistBehavior
from refwindcycle.weather import Grib
from datetime import datetime

# Load weather data
grib = Grib(['path/to/grib/file.grib2'])

# Configure cyclist profile
behavior = CyclistBehavior('realistic', 'realistic', 'realistic')

# Create simulator
sim = Simulator(
    grib=grib,
    behavior=behavior,
    CdA=0.35,      # Aerodynamic drag (m²)
    Cr=0.005,      # Rolling resistance
    m=85.0,        # Total mass (kg)
    v_max=22.0,    # Max speed (m/s = 79 km/h)
)
```

### Simulation Modes

#### 1. Future Simulation (Forecasting)

Predict performance on a route with weather forecast:

```python
# Load route segments (from GPX or other source)
from refwindcycle.analysis import RouteAnalyzer
analyzer = RouteAnalyzer()
gpx_result = analyzer.process_gpx('route.gpx')

# Simulate with given start time and power
t_start = datetime(2026, 2, 23, 10, 0, 0, tzinfo=ZoneInfo('UTC'))
result = sim.simulate_future(
    segments_in=gpx_result.segments,
    t_start=t_start,
    P0=200,        # Reference power (W)
    passes=2,      # Simulation iterations for wind convergence
)

# Access results
print(f"Estimated time: {result.time.total_hours:.2f}h")
print(f"Average speed: {result.speed.avg:.1f} km/h")
print(f"Wind score: {result.wind_score.grade}")
```

#### 2. Replay Simulation (Post-Ride Analysis)

Analyze an actual ride with GPS timestamps:

```python
# Process GPX with timestamps
gpx_result = analyzer.process_gpx('ride.gpx')

# Replay automatically extracts t_start from GPX
result = sim.simulate_replay(
    segments_in=gpx_result.segments,
    # t_start optional - auto-extracted if not provided
    passes=2,
)

# P0 is automatically calibrated from observed speeds
print(f"Calibrated P0: {result.power.P0_calibrated:.1f}W")
print(f"Average power: {result.power.avg:.1f}W")
print(f"Actual time: {result.time.total_hours:.2f}h")
```

### Simulator API Reference

#### Constructor

```python
Simulator(
    grib,                          # Grib object with weather data
    behavior=None,                 # CyclistBehavior (default if None)
    CdA=0.5,                       # Drag area (m²)
    Cr=0.004,                      # Rolling resistance coefficient
    m=75.0,                        # Total mass (kg)
    g=9.80665,                     # Gravity (m/s²)
    clip_wind=40.0,                # Max wind speed to consider (m/s)
    use_yaw_cdA=True,              # Adjust CdA for crosswind
    ratio_wind=0.25,               # Gust effect weighting
    yaw_k=0.02,                    # CdA yaw sensitivity
    v_max=25.0,                    # Max speed (m/s)
    use_dynamic=True,              # Enable acceleration modeling
    limit_speed_in_corners=True,   # Apply corner speed limits
    rho_forced=None,               # Force air density (kg/m³), None=auto
)
```

#### Method: `simulate_future()`

**Purpose:** Forecast performance on a future route.

**Signature:**
```python
simulate_future(
    segments_in: List[Dict],   # Route segments
    t_start: datetime,         # Start time (REQUIRED)
    v0: Optional[float] = None,  # Initial speed (m/s)
    P0: Optional[float] = None,  # Reference power (W) - REQUIRED
    passes: int = 2,           # Simulation iterations
) -> SimulationResult
```

**Returns:** `SimulationResult` with all statistics (distance, time, speed, wind, power, windscore).

**Example:**
```python
result = sim.simulate_future(
    segments_in=route_segments,
    t_start=datetime(2026, 2, 23, 10, 0, tzinfo=ZoneInfo('UTC')),
    P0=200,  # Cyclist will produce 200W on flat
    passes=2,
)
```

#### Method: `simulate_replay()`

**Purpose:** Analyze past ride using GPS timestamps and speeds.

**Signature:**
```python
simulate_replay(
    segments_in: List[Dict],     # Route segments WITH timestamps
    t_start: Optional[datetime] = None,  # Start time (auto-extracted if None)
    passes: int = 2,             # Simulation iterations
) -> SimulationResult
```

**Key Features:**
- **Auto-extracts `t_start`** from first segment's `gpxtime_start` if not provided
- **Always calibrates P0** from observed speeds (matches actual performance)
- Validates timestamp consistency

**Returns:** `SimulationResult` with `power.P0_calibrated` containing fitted power.

**Example:**
```python
# Minimal - auto-extracts everything from GPX
result = sim.simulate_replay(segments_in=gpx_segments)

# With explicit t_start (validated against GPX)
result = sim.simulate_replay(
    segments_in=gpx_segments,
    t_start=datetime(2026, 1, 15, 8, 0, tzinfo=ZoneInfo('Europe/Paris')),
)
```

### SimulationResult Structure

The result object provides hierarchical access to all statistics:

```python
result.distance.total_km        # Total distance (km)
result.time.total_hours         # Total time (hours)
result.speed.avg                # Average speed (km/h)
result.speed.moving_avg         # Moving average (excludes stops)

# Wind analysis
result.wind.tws.avg             # True wind speed avg (m/s)
result.wind.twd_compass         # Wind direction (cardinal)
result.wind_along_trajectory.headwind.percentage  # % distance with headwind
result.wind_along_trajectory.tailwind.avg_kmh    # Avg tailwind (km/h)
result.crosswind.avg_kmh        # Crosswind avg (km/h)

# Power (only in replay mode or when calibrated)
result.power.avg                # Average power (W)
result.power.P0_calibrated      # Calibrated reference power (W)

# Wind scoring
result.wind_score.grade         # 'A', 'B', 'C', 'D', 'E'
result.wind_score.reason        # Textual explanation
result.wind_score.performance_score  # Performance impact (0-100)
result.wind_score.safety_danger_score  # Safety concern (0-100)

# Slope analysis
result.slopes.terrain.deniv_pos_m     # Terrain elevation gain (m)
result.slopes.virtual.deniv_pos_m     # Wind-induced virtual climb (m)
result.slopes.effective.avg_pct       # Effective slope avg (%)

# Access raw segments
for seg in result.segments:
    print(f"{seg['distance']:.0f}m @ {seg['slope']*100:+.1f}%")
```

See `QUICK_REFERENCE_SimulationResult.md` (at project root) for complete structure.

## Physics Model

### Fundamental Equation

Cycling power balance on a segment:

$$P = v \cdot (F_{aero} + F_{roll} + F_{grav})$$

Where:
- **$P$** : Power output (W)
- **$v$** : Speed (m/s)
- **$F_{aero} = 0.5 \rho \cdot CdA \cdot v_{rel}^2$** : Aerodynamic drag (N)
  - $\rho$ : Air density (kg/m³)
  - $CdA$ : Drag coefficient × frontal area (m²)
  - $v_{rel}$ : Speed relative to wind (m/s)
- **$F_{roll} = Cr \cdot m \cdot g$** : Rolling resistance (N)
  - $Cr$ : Rolling resistance coefficient
  - $m$ : Total mass including bike (kg)
  - $g$ : Gravity (9.81 m/s²)
- **$F_{grav} = m \cdot g \cdot slope$** : Gravitational component (N)

### Speed Solvers

#### 1. `solve_speed_for_power()` - Steady-State Speed

Given constant power, find the equilibrium speed using **binary search**:

```python
from refwindcycle.core import bike_physics

# Calculate speed on flat terrain at 200W
speed = bike_physics.solve_speed_for_power(
    P=200,        # Watts
    CdA=0.35,     # m² (typical road bike)
    Cr=0.005,     # Rolling resistance coefficient
    m=85,         # kg (80kg rider + 5kg bike)
    slope=0.0,    # Flat (0%)
    wind_along=0  # No wind (m/s)
)
print(f"Speed: {speed:.1f} m/s = {speed*3.6:.1f} km/h")  # ~9.2 m/s = 33 km/h
```

**Key Features:**
- Iterative binary search for robustness
- Downhill speed limiter: prevents unrealistic speeds (e.g., 80+ km/h on steep descent)
- Includes `behavior` parameter for realistic velocity caps

#### 2. `solve_speed_dynamic()` - Acceleration Profile

Model realistic acceleration/deceleration over a distance:

```python
v_final, v_avg, duration = bike_physics.solve_speed_dynamic(
    P=300,           # Watts
    CdA=0.35,
    Cr=0.005,
    m=85,
    slope=0.0,
    wind_along=0,
    v_initial=5.0,   # Start at 5 m/s (18 km/h)
    distance=500     # Over 500m
)
print(f"Final speed: {v_final:.1f} m/s, Avg: {v_avg:.1f} m/s, Time: {duration:.1f}s")
```

### Adaptive Power Model

Cyclists naturally adjust their power output based on terrain:

```python
from refwindcycle.core.cyclist_params import CyclistBehavior

# Create a realistic rider profile
behavior = CyclistBehavior(
    uphill='realistic',
    downhill='realistic', 
    corner='realistic'
)

# Base power on flat
P0 = 200  # Watts

# Calculate power on different slopes
P_uphill_5pct = bike_physics.calculate_adaptive_power(P0, slope=0.05, behavior=behavior)
P_downhill_8pct = bike_physics.calculate_adaptive_power(P0, slope=-0.08, behavior=behavior)

print(f"Uphill (+5%): {P_uphill_5pct:.1f}W (vs {P0}W base)")
print(f"Downhill (-8%): {P_downhill_8pct:.1f}W (vs {P0}W base)")
```

## Cyclist Behavior Profiles

The `CyclistBehavior` class centralizes all realistic behavior parameters.

### Built-in Presets

Three predefined behavior modes for each category:

#### Uphill Modes

| Mode | Forte Facteur | Modérée | Légère | Description |
|------|---|---|---|---|
| **realistic** | 3.5 | 2.5 | 1.5 | Balanced, realistic effort |
| **conservative** | 2.0 | 2.0 | 2.0 | Prudent, steady effort |
| **aggressive** | 4.0 | 4.0 | 4.0 | High-effort climber |

#### Downhill Modes

| Mode | Légère Factor | Forte | Max Speed | Description |
|------|---|---|---|---|
| **realistic** | 6.0 | 20.0 | 22 m/s | Safe, controlled descent |
| **conservative** | 3.0 | 3.0 | 18 m/s | Very cautious, low speed |
| **aggressive** | 5.0 | 5.0 | 22 m/s | Pro level, confident descent |

#### Corner Modes (max speed in m/s)

| Mode | Straight | Slight | Moderate | Sharp | Hairpin |
|------|---|---|---|---|---|
| **realistic** | 22.0 | 18.0 | 14.0 | 7.0 | 4.5 |
| **conservative** | 20.0 | 16.0 | 12.0 | 6.0 | 4.0 |
| **aggressive** | 22.0 | 22.0 | 22.0 | 22.0 | 22.0 |

### Creating Custom Profiles

**Mixed mode profile:**
```python
behavior = CyclistBehavior(
    uphill='conservative',    # Steady climber
    downhill='aggressive',     # Aggressive descender
    corner='realistic'         # Normal cornering
)
```

**Customizing individual parameters:**
```python
behavior = CyclistBehavior()
behavior.uphill_facteur_forte = 5.0      # More aggressive on steep climbs
behavior.downhill_vitesse_max_absolue = 20.0  # Lower absolute max speed
behavior.corner_speed_slight = 20.0      # More speed in slight turns
```

**Saving and loading profiles:**
```python
# Save custom profile
behavior.save('/path/to/profiles', 'my_rider.json')

# Load later
behavior = CyclistBehavior.load('/path/to/profiles', 'my_rider.json')
```

## Complete Example: Route Simulation

Simulate a complete route segment by segment:

```python
from refwindcycle.core import bike_physics
from refwindcycle.core.cyclist_params import CyclistBehavior

# Define segments (from GPX or manual)
segments = [
    {
        'distance': 1000,  # meters
        'slope': 0.02,     # 2% uphill
        'bearing': 45,     # degrees
    },
    {
        'distance': 500,
        'slope': -0.05,    # 5% downhill
        'bearing': 90,
    },
    {
        'distance': 2000,
        'slope': 0.0,      # flat
        'bearing': 0,
    }
]

# Rider parameters
behavior = CyclistBehavior()
P0 = 250  # Watts
CdA = 0.35
Cr = 0.005
m = 85

v = 9.0  # Starting speed (m/s)
total_time = 0

for seg in segments:
    # Adapt power to slope
    P_adjusted = bike_physics.calculate_adaptive_power(P0, seg['slope'], behavior)
    
    # Get speed on this segment
    v = bike_physics.solve_speed_for_power(
        P=P_adjusted,
        CdA=CdA,
        Cr=Cr,
        m=m,
        slope=seg['slope'],
        wind_along=0,  # No wind for this example
        behavior=behavior
    )
    
    # Time for this segment
    time_seg = seg['distance'] / v
    total_time += time_seg
    
    print(f"Segment: {seg['distance']}m @ {seg['slope']*100:+.1f}% → "
          f"P={P_adjusted:.0f}W, v={v*3.6:.1f} km/h, t={time_seg:.1f}s")

print(f"\nTotal time: {total_time:.0f}s = {total_time/60:.1f} minutes")
```

## Air Density & Altitude

Air density decreases with altitude, reducing aerodynamic drag:

```python
# Sea level
rho_sea = bike_physics.calculate_air_density(0)         # 1.225 kg/m³

# High altitude
rho_kigali = bike_physics.calculate_air_density(1500)   # 1.049 kg/m³ (-14%)
rho_lapaz = bike_physics.calculate_air_density(3640)    # 0.907 kg/m³ (-26%)
```

**Impact on power:** At high altitude, the same power produces higher speed (less air resistance).

## Critical Features

### Downhill Speed Limiter (Jan 2026 Fix)

The model includes realistic braking on steep descents:

```python
# Without limiter: physically could reach 80+ km/h
# With limiter: realistic 60-75 km/h

v = bike_physics.solve_speed_for_power(
    P=100,
    CdA=0.35,
    Cr=0.005,
    m=85,
    slope=-0.10,     # -10% descent
    wind_along=-5,   # Tailwind 5 m/s
    behavior=behavior  # Applies realistic speed cap
)
# Result: ~20-22 m/s (72-79 km/h), not 30 m/s
```

### Wind Effects

Wind is added to the cyclist's speed for aerodynamic calculations:

```python
# Headwind (positive = vent de face)
v_headwind = bike_physics.solve_speed_for_power(P=200, ..., wind_along=5)  # Slower

# Tailwind (negative = vent arrière)
v_tailwind = bike_physics.solve_speed_for_power(P=200, ..., wind_along=-5)  # Faster

# Note: Wind projection from GRIB files is handled by weather.wind_calculator
```

## API Reference

### Main Functions

#### `solve_speed_for_power(P, CdA, Cr, m, slope, wind_along, behavior=None)`
Find steady-state speed for given power and conditions.

#### `solve_speed_dynamic(P, CdA, Cr, m, slope, wind_along, v_initial, distance, behavior=None)`
Model acceleration/deceleration over a distance.

#### `calculate_adaptive_power(P0, slope, behavior=None)`
Adjust power output based on slope and rider profile.

#### `calculate_air_density(altitude_m, temperature_c=15.0)`
Calculate air density at given altitude (ISA model).

#### `get_default_behavior()`
Return the default `CyclistBehavior` instance.

### CyclistBehavior Class

#### Initialization
```python
behavior = CyclistBehavior(
    uphill='realistic',      # 'realistic', 'conservative', 'aggressive'
    downhill='realistic',
    corner='realistic'
)
```

#### Methods

- **`get_corner_speed_limit(bearing_change_degrees)`** → Speed limit in m/s
- **`save(directory, filename)`** → Save profile to JSON
- **`load(directory, filename)`** → Load profile from JSON (class method)

#### Key Attributes

**Slope thresholds (shared across all instances):**
- `SEUIL_MONTEE_FORTE` = 0.08 (8%)
- `SEUIL_MONTEE_MODEREE` = 0.03 (3%)
- `SEUIL_MONTEE_LEGERE` = 0.01 (1%)
- `SEUIL_DESCENTE_LEGERE` = -0.05 (-5%)

**Uphill parameters:**
- `uphill_facteur_forte` → Power multiplier for steep climbs
- `uphill_facteur_moderee` → Power multiplier for moderate climbs
- `uphill_facteur_legere` → Power multiplier for slight climbs

**Downhill parameters:**
- `downhill_facteur_legere` → Power reduction for slight descent
- `downhill_facteur_forte` → Power reduction for steep descent
- `downhill_vitesse_max_absolue` → Max speed cap on descent
- `downhill_vitesse_reduction_factor` → Rate of speed limit reduction per percent slope
- `downhill_vitesse_reduction_cap` → Maximum total reduction (40% typical)

**Corner parameters:**
- `corner_speed_straight` → Max speed on straight sections
- `corner_speed_slight` → Max speed on slight turns
- `corner_speed_moderate` → Max speed on moderate turns
- `corner_speed_sharp` → Max speed on sharp turns
- `corner_speed_hairpin` → Max speed on hairpin turns

## Testing

Run tests to validate the physics model:

```bash
pytest tests/test_core.py -v
```

Tests cover:
- CyclistBehavior creation and mode validation
- Speed/power calculations on various slopes
- Downhill speed limiter
- Air density calculations
- Physical coherence (more power → faster speed)

## Performance Notes

- **Binary search** in `solve_speed_for_power`: ~40 iterations for convergence
- **Typical execution time**: <1ms per segment
- **Suitable for**: Real-time planning, batch analysis, API endpoints

## See Also

- `refwindcycle.weather` module - GRIB wind data handling
- `refwindcycle.analysis` module - GPX processing and segmentation
