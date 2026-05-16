Installation
============

Prerequisites
-------------

- Python 3.9 to 3.13
- **Windows**: Conda (Miniconda or Anaconda) for reliable `pygrib` installation
- A working environment with required scientific and weather dependencies

Install from PyPI (recommended)
-------------------------------

.. code-block:: bash

   pip install biwipy

``pygrib`` is a required dependency for ``biwipy``.

Windows Installation (Required: conda-forge)
---------------------------------------------

On Windows, ``pygrib`` **must** be installed via conda-forge before using pip,
because it requires the ECCODES C library which conda provides automatically.

**Step-by-step installation:**

.. code-block:: powershell

   # Create environment
   conda create -n biwipy-env python=3.13
   conda activate biwipy-env

   # Install pygrib from conda-forge FIRST
   conda install -c conda-forge pygrib

   # Then install biwipy
   pip install biwipy

**For development mode (with dev and doc extras):**

.. code-block:: powershell

   pip install -e ".[dev]"

   # To also build the documentation locally:
   pip install -e ".[dev,docs]"

**If you encounter ``boot.def`` errors**, define the environment variable:

.. code-block:: powershell

   conda env config vars set ECCODES_DEFINITION_PATH=$env:CONDA_PREFIX\Library\share\eccodes\definitions
   conda deactivate
   conda activate biwipy-env

Install from source
-------------------

From repository root:

.. code-block:: bash

   pip install .

Install documentation dependencies:

.. code-block:: bash

   pip install ".[docs]"

Build documentation
-------------------

From the ``docs`` directory:

.. code-block:: bash

   make html

On Windows (PowerShell):

.. code-block:: powershell

   ./build_docs.ps1              # Build
   ./build_docs.ps1 -Clean       # Clean and rebuild
   ./build_docs.ps1 -Open        # Build and open in browser
   ./build_docs.ps1 -Clean -Open # Clean, rebuild, and open

The generated HTML files are available in ``docs/build/html``.
