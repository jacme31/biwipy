# Makefile for Biwipy documentation build
# Supports multi-language build with Sphinx

.PHONY: help clean html en fr all open

SOURCEDIR = source
BUILDDIR  = build
SPHINXOPTS = -W --keep-going

help:
	@echo "Biwipy documentation build targets:"
	@echo "  make clean         - Remove build directory"
	@echo "  make en            - Build English documentation"
	@echo "  make fr            - Build French documentation"
	@echo "  make all           - Build all languages (default)"
	@echo "  make open          - Build and open in browser"

clean:
	rm -rf $(BUILDDIR)

en:
	@echo "Building English documentation..."
	sphinx-build -D language=en -b html $(SPHINXOPTS) $(SOURCEDIR) $(BUILDDIR)/html/en

fr:
	@echo "Building French documentation..."
	sphinx-build -D language=fr -b html $(SPHINXOPTS) $(SOURCEDIR) $(BUILDDIR)/html/fr

all: en fr html-index

html-index:
	@echo "Creating language index..."
	@mkdir -p $(BUILDDIR)/html
	@cat > $(BUILDDIR)/html/index.html << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>Biwipy Documentation</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        h1 { color: #333; }
        .languages { list-style: none; padding: 0; }
        .languages li { margin: 10px 0; }
        .languages a { font-size: 18px; text-decoration: none; color: #0066cc; }
        .languages a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <h1>Biwipy Documentation</h1>
    <p>Select a language:</p>
    <ul class="languages">
        <li><a href="en/index.html">🇬🇧 English</a></li>
        <li><a href="fr/index.html">🇫🇷 Français</a></li>
    </ul>
</body>
</html>
EOF
	@echo "Index created: $(BUILDDIR)/html/index.html"

open: all
	@echo "Opening documentation in browser..."
	@python -m webbrowser file://$(shell pwd)/$(BUILDDIR)/html/index.html

.DEFAULT_GOAL := all
