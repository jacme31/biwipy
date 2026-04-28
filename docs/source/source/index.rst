Documentation
==========================

.. |pic1| image:: ./_static/logo.png
   :width: 25%

===================================
|pic1|  Welcome to  **biwipy** !
===================================


biwipy is a Python library that allows you to study the impact of wind on cycling routes described by GPS tracks.

.. note::

   Packaging transition (Phase 1): the published distribution name is
   ``biwipy`` while the Python import namespace remains ``refwindcycle`` for
   backward compatibility.

   Example:

   .. code-block:: python

      from refwindcycle.core import Simulator

It provides:

* retrospective analysis of actual routes already traveled (replay) in order to observe the impact of wind after the fact and measure the effort expended (power calculation)

*  simulation of planned routes up to the current date plus 16 days 

The biwipy library is based on a model of the physical laws of cycling , incorporating continuous wind calculations using weather forecast data files (GRIB files).

Among the most interesting features of this model are: 

* the physical model of cycling performance is highly configurable

*  the model introduces  the concept of virtual elevation gain (positive and negative)  which represents the equivalent “elevation gain” of wind effects.   

*  The result of a simulation is summarized by a “windscore,” a grade between A and F that incorporates safety and performance aspects. 

The library incorporates all the functions required for managing and downloading GRIB files, pre-processing GPX files, and analysing the simulation results.


The library also comes with a set of sample programs that allow you to quickly perform simulations and analyze cycling routes in a real-world context with wind.

This tool is designed to be as general as possible and usable by all types of cyclists exposed to wind conditions, regardless of their level or cycling practices (competition, leisure, cycle touring).

Some concrete examples of questions that biwipy can help you answer:

* For my usual ride next week, which day is the most favorable, and which days should I avoid ?

* I would like to analyze the effort and wind conditions of my previous rides. 

* I want to go out tomorrow, but the wind forecast is not favorable. Among the routes I am considering, I would like to identify the most favorable and least dangerous one. 

* I have a multi-stage bike trip planned for the next few days. What is the best day to leave for the best wind conditions ? 

* Professional runners sometimes seem to run in hellish winds. I would love to measure these conditions.  ? 





This documentation is organized for users and developers:

- Quick setup and installation
- User-oriented workflow guide
- Practical examples and sample scripts
- API reference generated from Python docstrings

.. toctree::
   :maxdepth: 2
   :caption: Contents

   installation
   user_guide
   core_guide
   examples
   api
   changelog
