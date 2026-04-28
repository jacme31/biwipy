import os
import sys

sys.path.insert(0, os.path.abspath("../.."))

project = "biwipy"
copyright = "2026, Jacques"
author = "Jacques"
release = "0.1.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.autosummary",
    "nbsphinx",
    "sphinx_copybutton",
    "myst_parser",
]
# MyST Docs: https://myst-parser.readthedocs.io/en/latest/syntax/optional.html
myst_enable_extensions = [
    "linkify",  # Autodetects URL links in Markdown files
    
]




templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

language = "en"


html_theme = "pydata_sphinx_theme"
html_static_path = ["_static"]

autosummary_generate = True
autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
}

# Mock imports for modules not available in doc build environment
autodoc_mock_imports = [
    "numpy",
    "scipy",
    "pandas",
    "matplotlib",
    "gpxpy",
    "pygrib",
    "stravalib",
    "geopy",
]

napoleon_google_docstring = True
napoleon_numpy_docstring = True

myst_heading_anchors=3
