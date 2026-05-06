# Tips

This page gathers practical recommendations for day-to-day use.

## Input Data Tips

- Use realistic CdA/Crr values first, then calibrate progressively.
- Prefer GPX files with timestamps for replay analysis.
- For future simulations, choose a realistic ride duration when requesting GRIB files.

## GPX Processing Tips

- Enable stop filtering when timestamps are available.
- Inspect route statistics after preprocessing before launching simulations.
- If the route starts/ends in dense urban sections, consider cutting the first/last kilometers.

## Wind and GRIB Tips

- Use 1-hour GRIB step for short rides when you need finer temporal resolution.
- Use 3-hour GRIB step for longer horizons when data volume matters.
- Reuse cached GRIB files to speed up repeated runs.

## Simulation Tips

- Start with a no-wind baseline to understand route-only difficulty.
- Compare replay and future simulation on the same route to quantify wind impact.
- Keep cyclist behavior profile consistent across comparisons.

## Analysis Tips

- Check both average and max speed, not only one metric.
- Use virtual slope and wind-along metrics together for interpretation.
- Validate conclusions over multiple rides when possible.

## Output Language

Some examples and notebooks set an environment variable to control user-facing text output.

- Supported values are `en` and `fr` only.
- Recommended variable name: `OUTPUT_LANG`.
- If you still see `LANG_OUTPUT` in legacy snippets, treat it as an alias/legacy naming and prefer `OUTPUT_LANG`.

Example:

```python
import os
os.environ["OUTPUT_LANG"] = "en"  # or "fr"
```
