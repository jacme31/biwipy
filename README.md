# biwipy

**biwipy** is a cycling performance analysis python library that integrates physical modeling, real-world meteorological data (GRIB), and GPS tracks to simulate and analyze the impact of wind on cycling routes.

The project allows users to validate power models, analyze the influence of wind on an entire route or specific segments, and calibrate aerodynamic parameters (CdA).

The devlopement of Biwipy was largely assisted by AI (vibe coding) based on an initial conventionally designed wind model.

---

## 🚀 Main Features

* **Advanced Physical Simulation**: Complete model including gravity, rolling resistance (Cr), aerodynamics (CdA), and cornering dynamics.

* **GRIB Weather Integration**: Download and precise spatiotemporal interpolation of wind data (GFS or IFS model via GRIB2).

* **Ground Wind Calculation**: Including terrain roughness analysis.

* **"Intelligent" Descent and Corner Management**: Algorithm limiting speeds on descents and in corners to reflect real-world behavior (braking) rather than purely theoretical physics.

* **Behavior Profiles**: Configurable 'Realistic' (cyclo), 'Conservative' (cautious), and 'Aggressive' (pro) modes.

---
## 📂 Architecture

e :

```text
refwindcycle/
├── refwindcycle/
│   ├── core/              # Cœur du moteur physique
│   │   ├── bike_physics.py    # Calculs de forces et vitesses
│   │   └── cyclist_params.py  # Profils de comportement (CyclistBehavior)
│   ├── weather/           # Gestion météo
│   │   ├── grib_manager.py    # Lecture et interpolation fichiers GRIB
│   │   └── ...
│   ├── analysis/          # Outils d'analyse de traces
│   └── ...
├── tests/                 # Suite de tests unitaires (pytest)
├── scripts/               # Scripts utilitaires (legacy & demos)
└── windcli.py             # Point d'entrée ligne de commande
```

---

## 🛠 Installation

### Méthode 1 : Conda avec environment.yml (Recommandé)

**Avantages** : Installation simple, toutes les dépendances gérées automatiquement, cross-platform.

```bash
# Cloner/télécharger le projet
cd refwindcycle

# Créer l'environnement depuis le fichier
conda env create -f environment.yml

# Activer l'environnement
conda activate bikewind
```

### Méthode 2 : Conda ligne de commande

```bash
# Créer l'environnement avec toutes les dépendances
conda create -n bikewind python=3.10 -c conda-forge \
    pygrib numpy scipy matplotlib gpxpy stravalib folium \
    pytest black ruff

# Activer l'environnement
conda activate bikewind

# Installer le package en mode développement
pip install -e .
```

### Méthode 3 : Pip (Installation manuelle des prérequis système)

⚠️ **Attention** : PyGRIB nécessite eccodes installé au niveau système.

#### Linux (Debian/Ubuntu)
```bash
# Installer eccodes
sudo apt-get update
sudo apt-get install libeccodes-dev

# Créer environnement virtuel
python -m venv venv
source venv/bin/activate

# Installer les dépendances
pip install -e ".[dev]"
```

#### macOS (Homebrew)
```bash
# Installer eccodes
brew install eccodes

# Créer environnement virtuel
python -m venv venv
source venv/bin/activate

# Installer les dépendances
pip install -e ".[dev]"
```

#### Windows
```powershell
# Windows : Installation complexe, conda fortement recommandé
# Si nécessaire, installer eccodes via MSYS2 ou binaires pré-compilés
# Puis configurer ECCODES_DIR manuellement

python -m venv venv
venv\Scripts\activate
pip install -e ".[dev]"
```

**Note Windows** : L'installation pip sur Windows est **complexe** et **non recommandée**. Utilisez conda.

### Vérifier l'installation

```bash
# Activer l'environnement
conda activate bikewind

# Lancer les tests
pytest tests/ -v
```

---

## 🚦 Utilisation

### 1. Analyse en ligne de commande (CLI)

Le script `windcli.py` est le point d'entrée principal pour analyser un dossier de fichiers GPX.

```bash
# Exemple simple
python windcli.py --gpxdir "C:/MonDossierGPX" --csv-out "rapport.csv"

# Avec spécification du dossier GRIB racine
python windcli.py --gpxdir "./gpx" --grib-root "G:/grib/data"
```

### 2. Validation / Tests

Pour vérifier que l'installation fonctionne et que le moteur physique est stable :

```bash
# Lancer toute la suite de tests
pytest

# Vérifier spécifiquement les correctifs de descente
python test_corrections_apply.py
```

---

## ⚙️ Configuration

### Chemins de Données
Le projet cherche par défaut les fichiers GRIB et GPX dans des chemins configurés selon l'OS :
*   **Windows** : `G:/grib/data/` (ou configuré via CLI)
*   **Linux** : `/mnt/nasdocker/grib/data/`

### Profils Cyclistes
Les comportements sont définis dans `refwindcycle/core/cyclist_params.py`.
Vous pouvez ajuster les presets (`DOWNHILL_PRESETS`, `CORNER_PRESETS`) pour modifier l'agressivité du simulateur.

### Traçabilité WindScore (calibration)

Le module **canonique** du score vent est :
- `refwindcycle/windscore.py`

Le fichier `windscore.py` à la racine a été supprimé pour éviter les doublons.

#### Formule performance actuelle (Mars 2026)
- `raw_score = -headwind_effect + WIND_BALANCE_WEIGHT * wind_balance_pct`
- `headwind_effect = wind_headwind_avg_kmh * wind_headwind_pct / 100`
- `wind_balance_pct = wind_tailwind_pct - wind_headwind_pct`

#### Outils/scripts utilisés pour calibrer
- `run_wind_alldays_demo.py` : génération du dataset CSV de simulation (alldays/live)
- `run_windscore_formula_tool.py` : corrélations features ↔ `ecart_V_pct`, diagnostics runtime, export constants
- `run_windscore_csv_post_analysis.py` : post-analyse distribution + `--calibration-light` + `--print-windscore-constants`
- `tests/test_windscore_integration.py` : validation d'intégration Simulator ↔ WindScore

#### Workflow recommandé pour recalibrer
1. Générer/mettre à jour le CSV (ex: `resultats_comparaison_alldays.csv`) avec `run_wind_alldays_demo.py`.
2. Lancer :
    - `python run_windscore_formula_tool.py --skip-model-fit --print-windscore-constants --csv <CSV>`
    - (optionnel) `python run_windscore_csv_post_analysis.py --no-compare --calibration-light --print-windscore-constants --csv <CSV>`
3. Reporter les constantes proposées dans `refwindcycle/windscore.py`.
4. Valider avec `python tests/test_windscore_integration.py`.

> Note: la convention tailwind est normalisée en magnitude (`abs`) dans les outils de calibration pour éviter les inversions de signe historiques.

---

## 🚧 Statut du Projet

*   **Version** : Refactoring Phase 1 (Modularisation) complétée.
*   **Dernière mise à jour majeure** : Février 2026 (Fix "Descente réaliste", Tests unitaires).
*   **Prochaines étapes** : Voir `ROADMAP.md`.

---
*Auteur : Jacme*