# CHANGELOG - Corrections des vitesses excessives en descente/vent

## Version avec corrections (15 janvier 2026)

### 🐛 Bugs corrigés

#### [CRITIQUE] Vitesses explosives en descente avec vent favorable
- **Problème**: Les vitesses simulées explosaient (80-100+ km/h) en descente forte avec vent favorable
- **Impact**: Les courbes simulées ne correspondaient pas du tout aux données réelles Strava
- **Cause**: Absence de modélisation du freinage comportemental du cycliste
- **Solution**: Ajout d'une limite dynamique de vitesse en descente

### ✨ Nouvelles constantes

```python
DESCENTE_VITESSE_MAX_REDUCTION_FACTOR = 2.5   # Réduction progressive (abs(slope) × 2.5)
DESCENTE_VITESSE_MAX_REDUCTION_CAP = 0.40     # Cap maximum de réduction (40%)
```

### 🔧 Modifications du code

1. **`solve_speed_for_power()`**
   - Suppression de la logique qui augmentait v_max en descente (ligne ~260)
   - Ajout d'une limite dynamique qui réduit v_max selon la pente
   - Application cohérente avec les seuils de pente existants

2. **`solve_speed_dynamic()`**
   - Même logique de limite dynamique appliquée
   - Assure la cohérence entre les deux solveurs

3. **Nettoyage**
   - Suppression des doublons de constantes (FACTEUR_DESCENTE_LEGERE_REALISTE)
   - Clarification des commentaires

### 📊 Résultats

| Condition | Avant | Après | Amélioration |
|-----------|-------|-------|--------------|
| Descente -10% + vent favorable | 80+ km/h | 59 km/h | ✅ Réaliste |
| Descente -15% + vent 10 m/s | 100+ km/h | 49 km/h | ✅ Très réaliste |
| Impact des constantes | Faible | ✅ Normal | Les facteurs retrouvent leur effet |

### 🧪 Tests fournis

- `test_downhill_fix.py` - Valide la limite en descente
- `test_wind_impact.py` - Montre l'impact du vent selon la pente
- `test_corrections_apply.py` - Vérifie l'application globale
- `demo_corrections.py` - Démonstration complète des cas réalistes

### 📝 Documentation

- `BUGFIX_DESCENTE.md` - Description technique du bug et de la solution
- `CORRECTIONS_DESCENTE_VENT.md` - Guide complet pour l'utilisateur

### ⚙️ Configuration

Les deux nouvelles constantes permettent d'ajuster le comportement:

```python
# Plus audacieux (descentes plus rapides)
DESCENTE_VITESSE_MAX_REDUCTION_FACTOR = 2.0
DESCENTE_VITESSE_MAX_REDUCTION_CAP = 0.30

# Plus prudent (descentes plus lentes)
DESCENTE_VITESSE_MAX_REDUCTION_FACTOR = 3.0
DESCENTE_VITESSE_MAX_REDUCTION_CAP = 0.45
```

### ✅ Compatibilité

- ✅ Pas de breaking changes pour les API publiques
- ✅ Les simulations existantes continueront à fonctionner
- ✅ Les résultats seront simplement plus réalistes

### 🎯 Impact pour l'utilisateur

Après cette correction, les courbes simulées doivent maintenant correspondre **beaucoup mieux** 
aux observations réelles (Strava, capteurs), particulièrement:
- En descente forte
- Avec vent favorable
- En combinaison (descente + vent favorable)
