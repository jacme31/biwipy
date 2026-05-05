# biwipy

[![Documentation](https://img.shields.io/badge/docs-online-brightgreen)](https://jacme31.github.io/biwipy/)

biwipy is a Python library for cycling performance simulation and route analysis with wind-aware physics.

It combines GPX processing, GRIB weather interpolation, and cyclist physics to replay rides or simulate future scenarios.

The devlopement of biwipy was largely assisted by AI based on an previous conventionally designed wind model.

## Features

- Physics-based speed and power simulation (CdA, Cr, slope, mass, wind)
- Route preprocessing and segment analysis from GPX files
- WindScore and scenario comparison utilities
- GRIB weather integration (GFS/IFS workflows)
- Interactive map visualization for route and wind exploration

## Project layout

```text
biwipy/
├── biwipy/
│   ├── core/
│   ├── analysis/
│   ├── weather/
│   └── visualization/
├── docs/
├── pyproject.toml
└── README.md
```

## Installation

### From PyPI

```bash
pip install biwipy
```

`pygrib` is a required dependency of `biwipy`.

### Windows Installation (Required: conda-forge)

On Windows, **you must install `pygrib` via conda-forge before using pip**. This is because `pygrib` requires the ECCODES C library which conda provides automatically.

**Step-by-step (Windows with Conda):**

```powershell
# 1. Create conda environment
conda create -n biwipy-env python=3.13
conda activate biwipy-env

# 2. Install pygrib from conda-forge (BEFORE pip)
conda install -c conda-forge pygrib

# 3. Install biwipy via pip
pip install biwipy
```

**For development (with tests/linting):**

```powershell
conda activate biwipy-env
pip install -e ".[dev]"
```

**If you encounter `boot.def` errors**, set this environment variable:

```powershell
conda env config vars set ECCODES_DEFINITION_PATH=$env:CONDA_PREFIX\Library\share\eccodes\definitions
conda deactivate
conda activate biwipy-env
```

### From source

```bash
pip install .
```

## Quick start

```python
from datetime import timedelta, datetime
from zoneinfo import ZoneInfo
import os

os.environ["OUTPUT_LANG"] = "en"

from biwipy.core import Simulator
from biwipy.core.cyclist_params import CyclistBehavior
from biwipy.weather import WeatherProvider
from biwipy.weather.grib_finder import build_grib_list
from biwipy.analysis import RouteAnalyzer

# Load and process GPX file
analyzer = RouteAnalyzer()
gpx_result = analyzer.process_gpx("my_ride.gpx")

# Set ride start time (UTC)
start_ride = datetime(2026, 5, 6, 4, 0, 0, tzinfo=ZoneInfo("UTC"))
duration_hours = 4

# Load weather data (GRIB files from current directory or will auto-download)
gribs_list = build_grib_list(".", start_ride, pas=1, duration_h=duration_hours)
weather = WeatherProvider(gribs_list)

# Create cyclist profile and simulator
behavior = CyclistBehavior(uphill='realistic', downhill='realistic', corner='realistic')
sim = Simulator(weather.grib, behavior=behavior, CdA=0.50, Cr=0.005, m=85.0)

# Simulate the ride (v0 in m/s: 30 km/h = 30/3.6 m/s)
result = sim.simulate_future(gpx_result.segments, start_ride, v0=30/3.6)

# Display results
print(f"Average speed: {result.speed.avg:.2f} km/h")
print(f"Average power: {result.power.avg:.2f} W")
print(f"Windscore: {result.wind_score.grade}")
```

## Documentation

Online documentation: https://jacme31.github.io/biwipy/

Build docs from repository root:

```bash
cd docs
make html
```

On Windows (PowerShell):

```powershell
./build_docs.ps1
```

**With options:**

```powershell
./build_docs.ps1 -Clean              # Clean and rebuild
./build_docs.ps1 -Open               # Build and open in browser
./build_docs.ps1 -Clean -Open        # Clean, rebuild, and open
```

Main docs entry point is generated at `docs/build/html/index.html`.

## Development

Install development extras:

```bash
pip install -e ".[dev]"
```

To also build the documentation locally:

```bash
pip install -e ".[dev,docs]"
```

Build package artifacts:

```bash
python -m build
python -m twine check dist/*
```

## License

This project is released under the MIT License. See LICENSE.