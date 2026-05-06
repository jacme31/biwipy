API Reference
=============

This reference intentionally focuses on the high-level public API used in
the official samples and notebooks.

Core Public API
---------------

Simulator
^^^^^^^^^

Primary entry point for replay and forward simulation.

.. autoclass:: biwipy.core.Simulator
   :members:
   :undoc-members:
   :show-inheritance:

Cyclist behavior
^^^^^^^^^^^^^^^^

Behavior profiles for climbing, descending and cornering.

.. autoclass:: biwipy.core.CyclistBehavior
   :members:
   :undoc-members:
   :show-inheritance:

.. autofunction:: biwipy.core.bike_physics.estimate_P0_from_v0

Route analysis
^^^^^^^^^^^^^^

High-level GPX preprocessing and segment generation.

.. autoclass:: biwipy.analysis.RouteAnalyzer
   :members:
   :undoc-members:
   :show-inheritance:

Weather provider
^^^^^^^^^^^^^^^^

High-level weather model wrapper for GRIB-backed simulations.

.. autoclass:: biwipy.weather.WeatherProvider
   :members:
   :undoc-members:
   :show-inheritance:

GRIB file planning helper
^^^^^^^^^^^^^^^^^^^^^^^^^

Plan and retrieve the GRIB files required for interpolation over a ride window.

.. autofunction:: biwipy.weather.grib_finder.build_grib_list

Visualization helpers
---------------------

.. autofunction:: biwipy.analysis.anareswind.print_summary_statistics

.. autofunction:: biwipy.analysis.anareswind.compare_scenarios

.. autofunction:: biwipy.analysis.anareswind.plot_segments_evolution

.. autofunction:: biwipy.analysis.anareswind.plot_elevation_profile

.. autofunction:: biwipy.analysis.anareswind.plot_wind_rose

.. autofunction:: biwipy.visualization.interactive_map.create_interactive_map

Notes
-----

Lower-level/internal modules remain available in the codebase but are not part
of this condensed public API reference.
