# Analysis of Simulation Results

This page explains how to interpret simulation outputs in practice.

## Scope of This Page

Use this page to understand:

- summary metrics (`print_summary_statistics`),
- virtual elevation and effective slope,
- WindScore interpretation,
- recommended plots and what to look for.

For simulation execution, see [Simulation and Replay](Simulation.md).

## Field Lookup (Complete Reference)

This page focuses on interpretation. For the exhaustive field list and exact names, use:

- [Simulation and Replay](Simulation.md), section `Complete Field Reference (Python object)`
- [Simulation and Replay](Simulation.md), section `Complete to_dict() key map`

Quick reminder for frequent lookups:

- object fields: `result.speed.avg`, `result.wind.tws.avg`, `result.wind_score.grade`
- JSON keys: `speed.avg_kmh`, `wind.tws.avg_kmh`, `wind_score.grade`

## Quick Summary First: print_summary_statistics

`print_summary_statistics(result, label)` is the fastest way to inspect a run.

Typical usage:

```{code-block} python3
from refwindcycle.analysis.anareswind import print_summary_statistics

print_summary_statistics(result, "Ride with wind")
```

What it gives at a glance:

- distance, total time, speed and power,
- mean/min/max wind and gusts,
- terrain slope, virtual slope, effective slope,
- wind-along split (headwind vs tailwind),
- final WindScore and sub-scores.

Recommended workflow:

1. Run one no-wind baseline.
2. Run wind-enabled simulation.
3. Compare both summaries before opening plots.

## Virtual Elevation and Effective Slope

### Definitions

- Terrain slope: slope from GPX elevation profile only.
- Virtual slope: slope-equivalent effect of wind.
- Effective slope: terrain slope + virtual slope.

Interpretation rule:

- positive virtual slope means wind behaves like extra climbing,
- negative virtual slope means wind behaves like downhill assistance.

Practical reading:

- If terrain slope is moderate but effective slope is high, wind is a major load driver.
- If terrain is hard but effective slope drops, tailwind is compensating part of the effort.

## WindScore: How to Read It

WindScore combines two dimensions:

- Performance component: impact on speed/effort.
- Safety component: absolute wind hazard (gusts, crosswind, etc.).

Main fields:

- `result.wind_score.grade`: final grade,
- `result.wind_score.reason`: why this grade dominates (`safety`, `performance`, or both),
- `result.wind_score.performance_grade`,
- `result.wind_score.safety_grade`,
- `result.wind_score.safety_danger_score`.

Interpretation rule:

- The final grade is the most restrictive one between safety and performance dimensions.

## Plot Guide

The analysis module provides several useful plotting functions:

- `plot_segments_evolution(...)`
- `plot_elevation_profile(...)`
- `plot_wind_rose(...)`
- `compare_scenarios(...)`

### 1. Segments Evolution Plot

Use it for time/distance evolution of key signals:

- speed,
- power,
- wind-along,
- slopes.

Look for:

- speed drops aligned with strong headwind or high effective slope,
- sustained high power in sections that are not steep terrain-wise (wind penalty),
- descents with limited speed due to safety constraints.

### 2. Elevation Profile Plot

Use it to compare:

- real terrain elevation,
- virtual elevation from wind,
- combined profile intuition.

Look for:

- long sections where virtual elevation accumulates,
- mismatch between terrain shape and perceived effort.

### 3. Wind Rose Plot

Use it to understand directional wind structure:

- dominant wind directions,
- spread and consistency,
- whether the route repeatedly exposes the same bearings.

### 4. Scenario Comparison

Use `compare_scenarios` for side-by-side analysis:

- no wind vs wind,
- different days,
- different behavior profiles.

## Practical Comparison Recipe

```{code-block} python3
# 1) Baseline without wind
result_nowind = sim_nowind.simulate_future(segments, t_start, P0=P0)

# 2) With wind
result_wind = sim_wind.simulate_future(segments, t_start, P0=P0)

# 3) Summaries
print_summary_statistics(result_nowind, "No wind")
print_summary_statistics(result_wind, "With wind")
```

Then inspect evolution plots to localize where differences are produced.

## Common Interpretation Pitfalls

- Looking only at average speed and ignoring safety indicators.
- Reading terrain slope alone and ignoring effective slope.
- Comparing scenarios with different rider parameters/profile settings.
- Over-interpreting a single run without a no-wind baseline.

## Suggested Reading Order

1. [Input data](Input-data.md)
2. [Simulation and Replay](Simulation.md)
3. This page (Analysis)
4. [Tips](Tips.md)
5. [Troubleshooting](Troubleshooting.md)
