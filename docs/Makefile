# Makefile for Biwipy documentation

.PHONY: help clean html open

SOURCEDIR = source
BUILDDIR  = build
SPHINXOPTS = -W --keep-going

help:
	@echo "Biwipy documentation build targets:"
	@echo "  make clean         - Remove build directory"
	@echo "  make html          - Build documentation"
	@echo "  make open          - Build and open in browser"

clean:
	rm -rf $(BUILDDIR)

html:
	@echo "Building documentation..."
	sphinx-build -b html $(SPHINXOPTS) $(SOURCEDIR) $(BUILDDIR)/html

open: html
	@echo "Opening documentation in browser..."
	@python -m webbrowser file://$(shell pwd)/$(BUILDDIR)/html/index.html

.DEFAULT_GOAL := html
