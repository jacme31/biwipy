# biwipy

biwipy is a Python library for cycling performance simulation and route analysis with wind-aware physics.

It combines GPX processing, GRIB weather interpolation, and cyclist physics to replay rides or simulate future scenarios.

## Features

- Physics-based speed and power simulation (CdA, Cr, slope, mass, wind)
- Route preprocessing and segment analysis from GPX files
- WindScore and scenario comparison utilities
- Optional GRIB weather integration (GFS/IFS workflows)
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

### With weather/GRIB support

`pygrib` is optional and provided through the `weather` extra:

```bash
pip install "biwipy[weather]"
```

### From source

```bash
pip install .
```

With optional weather support:

```bash
pip install ".[weather]"
```

## Quick start

```python
from biwipy.core import Simulator
from biwipy.analysis import RouteAnalyzer

analyzer = RouteAnalyzer()
gpx_result = analyzer.process_gpx("my_ride.gpx", verbose=False)

sim = Simulator(weather=None, CdA=0.53, Cr=0.0055, m=98.0)
result = sim.simulate_future(gpx_result.segments, t_start=None, P0=180)

print(result.speed.avg)
```

## Documentation

Build docs from repository root:

```bash
cd docs
make all
```

On Windows (PowerShell):

```powershell
cd docs
./build_docs.ps1 -Language all -Clean
```

Main docs entry point is generated at `docs/build/html/index.html`.

## Development

Install development extras:

```bash
pip install -e ".[dev]"
```

Build package artifacts:

```bash
python -m build
python -m twine check dist/*
```

## License

This project is released under the MIT License. See LICENSE.