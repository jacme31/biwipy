Installation
============

Prerequisites
-------------

- Python 3.9+
- A working environment with required scientific and weather dependencies

Install from PyPI (recommended)
-------------------------------

.. code-block:: bash

   pip install biwipy

Compatibility note
------------------

The installable distribution name and Python import namespace are both
``biwipy``.

.. code-block:: python

   from biwipy.core import Simulator

Install from source
-------------------

From repository root:

.. code-block:: bash

   pip install .

Install documentation dependencies

.. code-block:: bash

   pip install .[docs]

Build documentation
-------------------

From the ``docs`` directory:

.. code-block:: bash

   make html

On Windows:

.. code-block:: bat

   make.bat html

The generated HTML files are available in ``docs/build/html``.
