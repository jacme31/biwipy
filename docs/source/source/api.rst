API Reference
=============

This reference intentionally focuses on the high-level public API used in
the official samples and notebooks.

Core Public API
---------------

Simulator
^^^^^^^^^

Primary entry point for replay and forward simulation.

.. autoclass:: refwindcycle.core.Simulator
   :members:
   :undoc-members:
   :show-inheritance:

Cyclist behavior
^^^^^^^^^^^^^^^^

Behavior profiles for climbing, descending and cornering.

.. autoclass:: refwindcycle.core.CyclistBehavior
   :members:
   :undoc-members:
   :show-inheritance:

.. autofunction:: refwindcycle.core.bike_physics.estimate_P0_from_v0

Route analysis
^^^^^^^^^^^^^^

High-level GPX preprocessing and segment generation.

.. autoclass:: refwindcycle.analysis.RouteAnalyzer
   :members:
   :undoc-members:
   :show-inheritance:

Weather provider
^^^^^^^^^^^^^^^^

High-level weather model wrapper for GRIB-backed simulations.

.. autoclass:: refwindcycle.weather.WeatherProvider
   :members:
   :undoc-members:
   :show-inheritance:

Visualization helpers
---------------------

.. autofunction:: refwindcycle.analysis.anareswind.print_summary_statistics

.. autofunction:: refwindcycle.analysis.anareswind.compare_scenarios

.. autofunction:: refwindcycle.analysis.anareswind.plot_segments_evolution

.. autofunction:: refwindcycle.analysis.anareswind.plot_elevation_profile

.. autofunction:: refwindcycle.analysis.anareswind.plot_wind_rose

.. autofunction:: refwindcycle.visualization.interactive_map.create_interactive_map

Notes
-----

Lower-level/internal modules remain available in the codebase but are not part
of this condensed public API reference.
