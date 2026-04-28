# Troubleshooting

This page lists common issues, expected log messages, and quick fixes.

## Logging and Debug Levels

Before troubleshooting, make sure log verbosity is set correctly.

Recommended levels:

- WARNING: default day-to-day usage (only warnings/errors).
- INFO: high-level processing steps and key values.
- DEBUG: detailed diagnostics for wind interpolation, cache behavior, limits, and internal checks.

Typical setup:

```{code-block} python3
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Switch to detailed diagnostics only when needed
# logging.getLogger().setLevel(logging.DEBUG)
```

Practical workflow:

1. Start with INFO.
2. If the issue is unclear, switch to DEBUG.
3. Re-run once and focus on the first error block, not all downstream messages.

## GPX Issues

### GPX has no timestamps

Symptoms:

- Replay mode fails or is unavailable.

Typical messages:

```text
2026-03-19 09:42:13 - ERROR - Mode replay (use_gpx_timestamps=True) requires t_start parameter or GPX timestamps in segments. First segment must have 'gpxtime_start' field.
2026-03-19 09:42:13 - ERROR - Segment 0: gpxtime_start ou gpxtime_end manquant.
```

Checks:

- Confirm the GPX source includes timestamps.
- Use `simulate_future()` when timestamps are missing.

### Invalid or inconsistent timestamps

Symptoms:

- Replay aborts early.
- Time/speed metrics are inconsistent.

Typical messages:

```text
2026-03-19 09:47:01 - INFO - Validation des timestamps GPX...
2026-03-19 09:47:01 - ERROR - ⚠️  3 timestamps GPX aberrants détectés:
2026-03-19 09:47:01 - ERROR -    - Segment 42: durée négative (-12.0s)
2026-03-19 09:47:01 - INFO - T_start validated: 2026-02-14 10:25:00+01:00
```

Checks:

- Verify timezone consistency in GPX data.
- Ensure timestamps are monotonic.
- Check for negative segment durations.

### Unrealistic elevation noise

Symptoms:

- Spikes in slope, speed, or power.

Typical messages:

```text
2026-03-19 09:50:22 - INFO -   FILTRAGE: Suppression des segments aberrants (bruit GPS)
2026-03-19 09:50:22 - INFO - Avant: 11467 segments
2026-03-19 09:50:22 - INFO - Supprimés: 6 segments (bruit GPS)
2026-03-19 09:50:22 - INFO - Après: 11461 segments
```

Checks:

- Re-run preprocessing and inspect route statistics.
- Verify smoothing and short-segment merge behavior.

## GRIB and Weather Issues

### Missing GRIB coverage for ride time

Symptoms:

- Wind lookup fails at startup or mid-route.

Typical messages:

```text
2026-03-19 10:03:41 - ERROR - OUT of GRIB : Requested time 2026-02-14 07:00:00+00:00 before grib data start 2026-02-14 09:00:00+00:00
2026-03-19 10:03:41 - ERROR - OUT of GRIB :Requested time 2026-02-14 19:00:00+00:00 after grib data end 2026-02-14 18:00:00+00:00
2026-03-19 10:03:41 - ERROR - Wind impact calculation failed at time 2026-02-14 10:42:22+01:00, lat 43.55231, lon 1.28744
```

Checks:

- Confirm requested date range and ride duration.
- Regenerate GRIB list with sufficient duration margin.
- Verify files are present under your GRIB directory.

### GRIB file content is invalid

Symptoms:

- Initialization fails despite files being present.

Typical messages:

```text
2026-03-19 10:06:18 - ERROR - File G:/grib/.../subset_xxx.grib2 invalid: less than 2 GRIB messages (u10/v10 missing)
2026-03-19 10:06:18 - ERROR - Fichier G:/grib/... invalide pour 2026-02-14 12:00:00+00:00: gust manquant
2026-03-19 10:06:18 - ERROR - Error reading data for gust at 2026-02-14 12:00:00+00:00 in G:/grib/...: <exception>
```

Checks:

- Redownload the problematic GRIB files.
- Confirm required parameters are present: u10, v10, gust.

### Slow weather initialization

Symptoms:

- Long startup time when loading wind model.

Typical messages:

```text
2026-03-19 10:10:05 - INFO - Purged 14 expired cache files from C:/Users/.../.cache/grib/
2026-03-19 10:10:07 - INFO - Init wind end- time for wind initialization : 2.31
```

Checks:

- Ensure cache is enabled.
- Reuse existing GRIB files when possible.
- Avoid enabling DEBUG permanently during large runs.

## Roughness Provider Issues

### Roughness map unavailable

Symptoms:

- Provider initialization fails and falls back to default z0.

Typical messages:

```text
2026-03-19 10:16:44 - ERROR - RoughnessProvider.prepare failed: <exception>
⚠ Roughness map unavailable (<exception>). Falling back to default z0=0.03 m.
2026-03-19 10:16:45 - WARNING - Roughness lookup failed at lat=43.55231, lon=1.28744: <exception>
```

Checks:

- Verify network access to the map source.
- Check local cache directory permissions.
- Confirm route bounding box values are valid.

## Simulation Issues

### Unrealistic speed or power

Symptoms:

- Speeds too high/low versus expected ride profile.

Typical messages:

```text
2026-03-19 10:21:03 - INFO - Corner speed limiting: ENABLED (reduces speed in turns, especially in descents)
2026-03-19 10:21:03 - INFO - Using CYCLIST BEHAVIOR: realistic/realistic/realistic (P0=245.0 W, dynamic=True)
2026-03-19 10:21:04 - DEBUG - Downhill speed limit: slope=-9.8% -> reduction=24.5% -> v_max=16.6m/s
```

Checks:

- Recheck CdA, Crr, mass, and P0/v0.
- Confirm behavior profile settings.
- Compare with no-wind baseline.

### Inconsistent replay results

Symptoms:

- Replay outputs vary more than expected.

Typical messages:

```text
2026-03-19 10:24:55 - INFO - ✅ T_start auto-extracted from GPX: 2026-02-14 10:25:00+01:00
2026-03-19 10:24:55 - INFO - T_start validated: 2026-02-14 10:25:00+01:00
2026-03-19 10:24:55 - WARNING - ⚠️  Mode use_gpx_timestamps: P0 ou v0 fournis mais INUTILISÉS pour le calcul de vitesse/temps
```

Checks:

- Ensure timestamps and timezone handling are correct.
- Verify GPX quality and preprocessing output.
- Confirm weather data covers the full route timeframe.

## Diagnostic Checklist

- Confirm GPX validity and timestamp availability.
- Confirm GRIB coverage for full route time window.
- Confirm cyclist parameters and profile consistency.
- Run one no-wind baseline before wind-enabled analysis.
- Increase log level from WARNING to INFO, then DEBUG only if needed.