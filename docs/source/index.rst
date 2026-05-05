.. |pic1| image:: ./_static/logo.png
   :width: 25%

===================================
|pic1|  Welcome to  **biwipy** !
===================================


biwipy is a Python library that allows you to study the impact of wind on cycling routes described by GPS tracks.

It provides:

* retrospective analysis of actual routes already traveled (replay) in order to observe the impact of wind after the fact and measure the effort expended (power calculation)

* simulation of planned routes up to the current date plus 16 days

The biwipy library is based on a model of the physical laws of cycling, incorporating continuous wind calculations using weather forecast data files (GRIB files).

Among the most interesting features of this model are:

* the physical model of cycling performance is highly configurable

* the model introduces the concept of virtual elevation gain (positive and negative) which represents the equivalent "elevation gain" of wind effects.

* The result of a simulation is summarized by a "windscore," a grade between A and F that incorporates safety and performance aspects.

The library incorporates all the functions required for managing and downloading GRIB files, pre-processing GPX files, and analyzing the simulation results.


The library also comes with a set of sample programs that allow you to quickly perform simulations and analyze cycling routes in a real-world context with wind.

This tool is designed to be as general as possible and usable by all types of cyclists exposed to wind conditions, regardless of their level or cycling practices (competition, leisure, cycle touring).

Some concrete examples of questions that biwipy can help you answer:

* For my usual ride next week, which day is the most favorable, and which days should I avoid? ( `example 1`_ )

.. _example 1: user_guide/Notebook-1.html

* Professional cyclists sometimes race in extreme wind conditions. How can I quantify and visualize those effects? ( `example 2`_ )

.. _example 2: user_guide/Notebook-2.html

* I would like to analyze the effort and wind conditions of my previous rides. ( `example 3`_ )

.. _example 3: user_guide/Notebook-3.html

Biwipy also offers tools to calibrate your Drag Coefficient (CdA). ( `example 4`_ )

.. _example 4: user_guide/Notebook-4.html

Biwipy is an open-source project, and we welcome contributions from the community. If you have suggestions for improvements, new features, or want to report issues, please visit our `GitHub repository <https://github.com/jacme31/biwipy>`_.


This documentation is organized for users and developers:

- Quick setup and installation
- User-oriented workflow guide
- Practical examples with sample notebooks
- API reference generated from Python docstrings

.. toctree::
   :maxdepth: 2
   :caption: Contents

   installation
   user_guide
   examples
   api
   changelog


