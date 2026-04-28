# Biwipy Documentation i18n Setup

This directory supports multi-language documentation for Biwipy using Sphinx and gettext.

## Directory Structure

```
docs/source/
├── en/              # English documentation source
│   ├── index.rst
│   ├── installation.rst
│   ├── api.rst
│   ├── user_guide/
│   └── ...
├── fr/              # French documentation source (translated)
│   ├── index.rst
│   ├── installation.rst
│   ├── api.rst
│   └── ...
├── locale/          # Translation files (.po, .mo)
│   ├── fr/
│   │   ├── LC_MESSAGES/
│   │   │   ├── biwipy.po
│   │   │   └── biwipy.mo
│   └── ...
├── conf.py          # Sphinx config (supports language switching)
└── ...
```

## Workflow

### 1. Add/Update English Documentation
- Edit files in `en/` directory
- Commit changes

### 2. Generate Translation Templates
```bash
cd docs
sphinx-build -b gettext source/ build/locale
```

### 3. Create French Translation Files
```bash
# Extract strings from English docs
sphinx-intl create -p build/locale -l fr

# Edit translations in source/locale/fr/LC_MESSAGES/
```

### 4. Build Localized HTML
```bash
# Build for French
sphinx-build -D language=fr -b html source/ build/html/fr/

# Build for English
sphinx-build -D language=en -b html source/ build/html/en/
```

## Configuration

`conf.py`:
- `language = 'en'` (default)
- `locale_dirs = ['locale/']` (translation file location)
- Language switching via `language` parameter at build time

## Translation Status

- **English (en/)**: ✅ Complete (source)
- **French (fr/)**: 🔄 In progress

## Tools

- **Sphinx**: Documentation generator
- **sphinx-intl**: Translation management
- **gettext (.po/.mo files)**: Translation format
