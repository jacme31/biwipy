# ==========================================
# cyclist_params.py
# Paramètres de comportement cycliste
# ==========================================

import json
from pathlib import Path
from typing import Optional, Dict, Any
import logging
import locale
import os


logger = logging.getLogger(__name__)


def _detect_output_lang() -> str:
    lang = os.environ.get("OUTPUT_LANG", "").strip().lower()
    if lang in ("fr", "en"):
        return lang
    try:
        loc = locale.getlocale()[0] or locale.getdefaultlocale()[0] or ""
        if loc.lower().startswith("fr"):
            return "fr"
    except Exception:
        pass
    return "en"


_I18N = {
    "behavior_profile": {
        "fr": "Behaviour profile: Uphill={uphill} - Downhill={downhill} - Corner={corner}",
        "en": "Behaviour profile: Uphill={uphill} - Downhill={downhill} - Corner={corner}",
    },
    "uphill_title": {"fr": "\n📈 COMPORTEMENT EN MONTEE", "en": "\n📈 UPHILL BEHAVIOR"},
    "downhill_title": {"fr": "\n📉 COMPORTEMENT EN DESCENTE", "en": "\n📉 DOWNHILL BEHAVIOR"},
    "corner_title": {"fr": "\n🔄 COMPORTEMENT EN VIRAGES", "en": "\n🔄 CORNER BEHAVIOR"},
    "uphill_strong": {
        "fr": "  Montee forte (>={th:.0f}%)    : facteur {factor:.1f}  -> +{boost:.0f}% puissance par 10% pente",
        "en": "  Strong climb (>={th:.0f}%)    : factor {factor:.1f}  -> +{boost:.0f}% power per 10% slope",
    },
    "uphill_moderate": {
        "fr": "  Montee moderee (>={th:.0f}%)  : facteur {factor:.1f}  -> +{boost:.0f}% puissance par 10% pente",
        "en": "  Moderate climb (>={th:.0f}%)  : factor {factor:.1f}  -> +{boost:.0f}% power per 10% slope",
    },
    "uphill_light": {
        "fr": "  Montee legere (>={th:.0f}%)   : facteur {factor:.1f}  -> +{boost:.0f}% puissance par 10% pente",
        "en": "  Slight climb (>={th:.0f}%)   : factor {factor:.1f}  -> +{boost:.0f}% power per 10% slope",
    },
    "downhill_light": {
        "fr": "  Descente legere (>{th:.0f}%) : facteur {factor:.1f}",
        "en": "  Slight descent (>{th:.0f}%) : factor {factor:.1f}",
    },
    "downhill_strong": {
        "fr": "  Descente forte (<{th:.0f}%)  : facteur {factor:.1f}",
        "en": "  Strong descent (<{th:.0f}%)  : factor {factor:.1f}",
    },
    "downhill_min_power": {
        "fr": "  Puissance minimale          : {value} W",
        "en": "  Minimum power              : {value} W",
    },
    "downhill_vmax": {
        "fr": "  Vitesse max absolue         : {ms:.1f} m/s ({kmh:.1f} km/h)",
        "en": "  Absolute max speed          : {ms:.1f} m/s ({kmh:.1f} km/h)",
    },
    "downhill_brake": {
        "fr": "  Freinage progressif         : facteur {factor:.1f}, cap {cap:.0f}%",
        "en": "  Progressive braking         : factor {factor:.1f}, cap {cap:.0f}%",
    },
    "downhill_corner_safety": {
        "fr": "  Securite virage+descente    : x{safety:.2f}",
        "en": "  Corner+downhill safety      : x{safety:.2f}",
    },
    "corner_straight": {
        "fr": "  Ligne droite (<{th} deg)    : {ms:.1f} m/s ({kmh:.0f} km/h)",
        "en": "  Straight (<{th} deg)       : {ms:.1f} m/s ({kmh:.0f} km/h)",
    },
    "corner_slight": {
        "fr": "  Virage leger (<{th} deg)   : {ms:.1f} m/s ({kmh:.0f} km/h)",
        "en": "  Slight corner (<{th} deg)  : {ms:.1f} m/s ({kmh:.0f} km/h)",
    },
    "corner_moderate": {
        "fr": "  Virage modere (<{th} deg)  : {ms:.1f} m/s ({kmh:.0f} km/h)",
        "en": "  Moderate corner (<{th} deg): {ms:.1f} m/s ({kmh:.0f} km/h)",
    },
    "corner_sharp": {
        "fr": "  Virage serre (<{th} deg)   : {ms:.1f} m/s ({kmh:.0f} km/h)",
        "en": "  Sharp corner (<{th} deg)   : {ms:.1f} m/s ({kmh:.0f} km/h)",
    },
    "corner_hairpin": {
        "fr": "  Epingle (>{th} deg)       : {ms:.1f} m/s ({kmh:.0f} km/h)",
        "en": "  Hairpin (>{th} deg)       : {ms:.1f} m/s ({kmh:.0f} km/h)",
    },
    "dash80": {"fr": "--------------------------------------------------------------------------------", "en": "--------------------------------------------------------------------------------"},
}


def _t(key: str, **kwargs) -> str:
    lang = _detect_output_lang()
    labels = _I18N.get(key, {})
    template = labels.get(lang) or labels.get("en") or key
    return template.format(**kwargs) if kwargs else template


def _tp(key: str, **kwargs) -> None:
    print(_t(key, **kwargs))


class CyclistBehavior:
    """
    Classe centralisant tous les paramètres de comportement cycliste.
    
    Regroupe:
    - Seuils de pente (montée/descente)
    - Seuils de virages
    - Facteurs de comportement en montée (3 modes: realistic, conservative, aggressive)
    - Facteurs de comportement en descente (3 modes)
    - Limites de vitesse en virage (3 modes)
    
    Usage:
    ------
    # Créer un profil mixte
    >>> params = CyclistBehavior(uphill='realistic', downhill='conservative', corner='aggressive')
    
    # Customiser un paramètre spécifique
    >>> params.corner_speed_slight = 20.0  # m/s
    
    # Sauvegarder
    >>> params.save('/path/to/configs', 'remco_profile.json')
    
    # Restaurer
    >>> params = CyclistBehavior.load('/path/to/configs', 'remco_profile.json')
    """
    
    # ========================================================================
    # SEUILS DE PENTE (valeurs uniques, pas de variation par mode)
    # ========================================================================
    SEUIL_MONTEE_FORTE = 0.08       # ≥ 8% : montée forte
    SEUIL_MONTEE_MODEREE = 0.03     # ≥ 3% : montée modérée
    SEUIL_MONTEE_LEGERE = 0.01      # ≥ 1% : montée légère
    SEUIL_PLAT = -0.02              # > -2% : considéré comme plat
    SEUIL_DESCENTE_LEGERE = -0.05   # > -5% : descente légère
    
    # ========================================================================
    # SEUILS DE VIRAGES (en degrés, valeurs uniques)
    # ========================================================================
    SEUIL_CORNER_STRAIGHT = 5       # < 5° : ligne droite
    SEUIL_CORNER_SLIGHT = 20        # < 20° : virage léger
    SEUIL_CORNER_MODERATE = 45      # < 45° : virage modéré
    SEUIL_CORNER_SHARP = 90         # < 90° : virage serré
    # > 90° : épingle (hairpin)
    
    # ========================================================================
    # PRESETS DE COMPORTEMENT MONTÉE
    # ========================================================================
    UPHILL_PRESETS = {
        'realistic': {
            'facteur_forte': 3.5,      # +35% de puissance par 10% de pente
            'facteur_moderee': 2.5,    # +25% par 10% de pente
            'facteur_legere': 1.5,     # +15% par 10% de pente
        },
        'conservative': {
            'facteur_forte': 2.0,      # +20% par 10% de pente
            'facteur_moderee': 2.0,
            'facteur_legere': 2.0,
        },
        'aggressive': {
            'facteur_forte': 4.0,      # +40% par 10% de pente
            'facteur_moderee': 4.0,
            'facteur_legere': 4.0,
        },
    }
    
    # ========================================================================
    # PRESETS DE COMPORTEMENT DESCENTE
    # ========================================================================
    DOWNHILL_PRESETS = {
        'realistic': {
            'facteur_legere': 6.0,              # Réduction modérée en descente légère
            'facteur_forte': 20.0,              # Réduction importante en descente forte
            'puissance_min': 10,                # Watts minimum
            'vitesse_reduction_factor': 2.5,    # Freinage progressif selon pente (Jan 2026 fix)
            'vitesse_reduction_cap': 0.40,      # Cap de réduction: 40% max
            'vitesse_max_absolue': 22.0,        # m/s = 79.2 km/h
            'corner_downhill_safety_factor': 0.90,  # Multiplicateur en virage+descente
        },
        'conservative': {
            'facteur_legere': 3.0,              # Moins de réduction
            'facteur_forte': 3.0,
            'puissance_min': 10,
            'vitesse_reduction_factor': 10.0,   # Freinage plus fort
            'vitesse_reduction_cap': 0.70,
            'vitesse_max_absolue': 18.0,        # m/s = 64.8 km/h
            'corner_downhill_safety_factor': 0.85,  # Multiplicateur en virage+descente
        },
        'aggressive': {
            'facteur_legere': 5.0,              # Plus de réduction (on roule en descente)
            'facteur_forte': 5.0,
            'puissance_min': 10,
            'vitesse_reduction_factor': 1.0,    # Peu de freinage
            'vitesse_reduction_cap': 0.10,      # Presque pas de limite
            'vitesse_max_absolue': 22.0,        # m/s = 79.2 km/h (pro level)
            'corner_downhill_safety_factor': 0.97,  # Multiplicateur en virage+descente
        },
    }
    
    # ========================================================================
    # PRESETS DE COMPORTEMENT VIRAGES (vitesses max en m/s)
    # ========================================================================
    CORNER_PRESETS = {
        'realistic': {
            'straight': 22.0,      # 79 km/h
            'slight': 18.0,        # 65 km/h
            'moderate': 14.0,      # 50 km/h
            'sharp': 7.0,          # 25 km/h
            'hairpin': 4.5,        # 16 km/h
        },
        'conservative': {
            'straight': 20.0,      # 72 km/h
            'slight': 16.0,        # 58 km/h
            'moderate': 12.0,      # 43 km/h
            'sharp': 6.0,          # 22 km/h
            'hairpin': 4.0,        # 14 km/h
        },
        'aggressive': {
            'straight': 22.0,      # 79 km/h
            'slight': 22.0,        # 79 km/h (pro: pas de freinage virage léger)
            'moderate': 22.0,      # 79 km/h
            'sharp': 22.0,         # 79 km/h
            'hairpin': 22.0,       # 79 km/h (limite pour pro expérimenté)
        },
    }
    
    def __init__(self, uphill: str = 'realistic', 
                 downhill: str = 'realistic', 
                 corner: str = 'realistic'):
        """
        Initialise un profil de comportement cycliste.
        
        Parameters:
        -----------
        uphill : str
            Mode de comportement en montée: 'realistic', 'conservative', 'aggressive'
        downhill : str
            Mode de comportement en descente: 'realistic', 'conservative', 'aggressive'
        corner : str
            Mode de comportement en virage: 'realistic', 'conservative', 'aggressive'
        """
        if uphill not in self.UPHILL_PRESETS:
            raise ValueError(f"Mode montée invalide: {uphill}. Choisir parmi {list(self.UPHILL_PRESETS.keys())}")
        if downhill not in self.DOWNHILL_PRESETS:
            raise ValueError(f"Mode descente invalide: {downhill}. Choisir parmi {list(self.DOWNHILL_PRESETS.keys())}")
        if corner not in self.CORNER_PRESETS:
            raise ValueError(f"Mode virage invalide: {corner}. Choisir parmi {list(self.CORNER_PRESETS.keys())}")
        
        self.mode_uphill = uphill
        self.mode_downhill = downhill
        self.mode_corner = corner
        
        # Charger les presets
        self._load_uphill_preset(uphill)
        self._load_downhill_preset(downhill)
        self._load_corner_preset(corner)
    
    def _load_uphill_preset(self, mode: str):
        """Charge les paramètres de montée depuis un preset"""
        preset = self.UPHILL_PRESETS[mode]
        self.uphill_facteur_forte = preset['facteur_forte']
        self.uphill_facteur_moderee = preset['facteur_moderee']
        self.uphill_facteur_legere = preset['facteur_legere']
    
    def _load_downhill_preset(self, mode: str):
        """Charge les paramètres de descente depuis un preset"""
        preset = self.DOWNHILL_PRESETS[mode]
        self.downhill_facteur_legere = preset['facteur_legere']
        self.downhill_facteur_forte = preset['facteur_forte']
        self.downhill_puissance_min = preset['puissance_min']
        self.downhill_vitesse_reduction_factor = preset['vitesse_reduction_factor']
        self.downhill_vitesse_reduction_cap = preset['vitesse_reduction_cap']
        self.downhill_vitesse_max_absolue = preset['vitesse_max_absolue']
        self.downhill_corner_safety_factor = preset['corner_downhill_safety_factor']
    
    def _load_corner_preset(self, mode: str):
        """Charge les paramètres de virage depuis un preset"""
        preset = self.CORNER_PRESETS[mode]
        self.corner_speed_straight = preset['straight']
        self.corner_speed_slight = preset['slight']
        self.corner_speed_moderate = preset['moderate']
        self.corner_speed_sharp = preset['sharp']
        self.corner_speed_hairpin = preset['hairpin']
    
    def display(self, verbose: bool = True):
        """
        Affiche la configuration actuelle avec explications.
        
        Parameters:
        -----------
        verbose : bool
            Si True, affiche les détails complets. Si False, affiche seulement un résumé.
        """
        _tp(
            "behavior_profile",
            uphill=self.mode_uphill.upper(),
            downhill=self.mode_downhill.upper(),
            corner=self.mode_corner.upper(),
        )

        
        if verbose:
            _tp("uphill_title")
            _tp("dash80")
            _tp("uphill_strong", th=self.SEUIL_MONTEE_FORTE*100, factor=self.uphill_facteur_forte, boost=self.uphill_facteur_forte*10)
            _tp("uphill_moderate", th=self.SEUIL_MONTEE_MODEREE*100, factor=self.uphill_facteur_moderee, boost=self.uphill_facteur_moderee*10)
            _tp("uphill_light", th=self.SEUIL_MONTEE_LEGERE*100, factor=self.uphill_facteur_legere, boost=self.uphill_facteur_legere*10)
            
            _tp("downhill_title")
            _tp("dash80")
            _tp("downhill_light", th=self.SEUIL_DESCENTE_LEGERE*100, factor=self.downhill_facteur_legere)
            _tp("downhill_strong", th=self.SEUIL_DESCENTE_LEGERE*100, factor=self.downhill_facteur_forte)
            _tp("downhill_min_power", value=self.downhill_puissance_min)
            _tp("downhill_vmax", ms=self.downhill_vitesse_max_absolue, kmh=self.downhill_vitesse_max_absolue*3.6)
            _tp("downhill_brake", factor=self.downhill_vitesse_reduction_factor, cap=self.downhill_vitesse_reduction_cap*100)
            _tp("downhill_corner_safety", safety=self.downhill_corner_safety_factor)
            
            _tp("corner_title")
            _tp("dash80")
            _tp("corner_straight", th=self.SEUIL_CORNER_STRAIGHT, ms=self.corner_speed_straight, kmh=self.corner_speed_straight*3.6)
            _tp("corner_slight", th=self.SEUIL_CORNER_SLIGHT, ms=self.corner_speed_slight, kmh=self.corner_speed_slight*3.6)
            _tp("corner_moderate", th=self.SEUIL_CORNER_MODERATE, ms=self.corner_speed_moderate, kmh=self.corner_speed_moderate*3.6)
            _tp("corner_sharp", th=self.SEUIL_CORNER_SHARP, ms=self.corner_speed_sharp, kmh=self.corner_speed_sharp*3.6)
            _tp("corner_hairpin", th=self.SEUIL_CORNER_SHARP, ms=self.corner_speed_hairpin, kmh=self.corner_speed_hairpin*3.6)
        
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convertit la configuration en dictionnaire pour sauvegarde.
        
        Returns:
        --------
        dict : Configuration complète
        """
        return {
            'metadata': {
                'mode_uphill': self.mode_uphill,
                'mode_downhill': self.mode_downhill,
                'mode_corner': self.mode_corner,
            },
            'uphill': {
                'facteur_forte': self.uphill_facteur_forte,
                'facteur_moderee': self.uphill_facteur_moderee,
                'facteur_legere': self.uphill_facteur_legere,
            },
            'downhill': {
                'facteur_legere': self.downhill_facteur_legere,
                'facteur_forte': self.downhill_facteur_forte,
                'puissance_min': self.downhill_puissance_min,
                'vitesse_reduction_factor': self.downhill_vitesse_reduction_factor,
                'vitesse_reduction_cap': self.downhill_vitesse_reduction_cap,
                'vitesse_max_absolue': self.downhill_vitesse_max_absolue,
                'corner_downhill_safety_factor': self.downhill_corner_safety_factor,
            },
            'corner': {
                'speed_straight': self.corner_speed_straight,
                'speed_slight': self.corner_speed_slight,
                'speed_moderate': self.corner_speed_moderate,
                'speed_sharp': self.corner_speed_sharp,
                'speed_hairpin': self.corner_speed_hairpin,
            }
        }
    
    def save(self, dirpath: str, filename: str):
        """
        Sauvegarde la configuration dans un fichier JSON.
        
        Parameters:
        -----------
        dirpath : str
            Chemin du répertoire où sauvegarder
        filename : str
            Nom du fichier (ex: 'remco_profile.json')
        
        Example:
        --------
        >>> params.save('/home/user/configs', 'my_profile.json')
        """
        path = Path(dirpath)
        path.mkdir(parents=True, exist_ok=True)
        
        filepath = path / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        
        logger.info("Cyclist behavior configuration saved: %s", filepath)
    
    @classmethod
    def load(cls, dirpath: str, filename: str) -> 'CyclistBehavior':
        """
        Charge une configuration depuis un fichier JSON.
        
        Parameters:
        -----------
        dirpath : str
            Chemin du répertoire contenant le fichier
        filename : str
            Nom du fichier à charger
        
        Returns:
        --------
        CyclistBehavior : Instance avec la configuration chargée
        
        Example:
        --------
        >>> params = CyclistBehavior.load('/home/user/configs', 'my_profile.json')
        """
        filepath = Path(dirpath) / filename
        
        if not filepath.exists():
            raise FileNotFoundError(f"Fichier introuvable: {filepath}")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Créer instance avec les modes par défaut
        metadata = data.get('metadata', {})
        instance = cls(
            uphill=metadata.get('mode_uphill', 'realistic'),
            downhill=metadata.get('mode_downhill', 'realistic'),
            corner=metadata.get('mode_corner', 'realistic')
        )
        
        # Écraser avec les valeurs customisées
        uphill = data.get('uphill', {})
        if uphill:
            instance.uphill_facteur_forte = uphill.get('facteur_forte', instance.uphill_facteur_forte)
            instance.uphill_facteur_moderee = uphill.get('facteur_moderee', instance.uphill_facteur_moderee)
            instance.uphill_facteur_legere = uphill.get('facteur_legere', instance.uphill_facteur_legere)
        
        downhill = data.get('downhill', {})
        if downhill:
            instance.downhill_facteur_legere = downhill.get('facteur_legere', instance.downhill_facteur_legere)
            instance.downhill_facteur_forte = downhill.get('facteur_forte', instance.downhill_facteur_forte)
            instance.downhill_puissance_min = downhill.get('puissance_min', instance.downhill_puissance_min)
            instance.downhill_vitesse_reduction_factor = downhill.get('vitesse_reduction_factor', instance.downhill_vitesse_reduction_factor)
            instance.downhill_vitesse_reduction_cap = downhill.get('vitesse_reduction_cap', instance.downhill_vitesse_reduction_cap)
            instance.downhill_vitesse_max_absolue = downhill.get('vitesse_max_absolue', instance.downhill_vitesse_max_absolue)
            instance.downhill_corner_safety_factor = downhill.get('corner_downhill_safety_factor', instance.downhill_corner_safety_factor)
        
        corner = data.get('corner', {})
        if corner:
            instance.corner_speed_straight = corner.get('speed_straight', instance.corner_speed_straight)
            instance.corner_speed_slight = corner.get('speed_slight', instance.corner_speed_slight)
            instance.corner_speed_moderate = corner.get('speed_moderate', instance.corner_speed_moderate)
            instance.corner_speed_sharp = corner.get('speed_sharp', instance.corner_speed_sharp)
            instance.corner_speed_hairpin = corner.get('speed_hairpin', instance.corner_speed_hairpin)
        
        logger.info("Cyclist behavior configuration loaded: %s", filepath)
        return instance
    
    def get_uphill_factor(self, slope: float) -> float:
        """
        Retourne le facteur de puissance approprié pour une pente donnée.
        
        Parameters:
        -----------
        slope : float
            Pente (ratio, ex: 0.05 = 5%)
        
        Returns:
        --------
        float : Facteur multiplicateur de puissance
        """
        if slope >= self.SEUIL_MONTEE_FORTE:
            return self.uphill_facteur_forte
        elif slope >= self.SEUIL_MONTEE_MODEREE:
            return self.uphill_facteur_moderee
        elif slope >= self.SEUIL_MONTEE_LEGERE:
            return self.uphill_facteur_legere
        else:
            return 0.0  # Pas de montée
    
    def get_corner_speed_limit(self, bearing_change: float) -> float:
        """
        Retourne la vitesse maximale pour un virage donné.
        
        Parameters:
        -----------
        bearing_change : float
            Changement de direction en degrés (0-180)
        
        Returns:
        --------
        float : Vitesse maximale en m/s
        """
        bearing_change = abs(bearing_change)
        
        if bearing_change <= self.SEUIL_CORNER_STRAIGHT:
            return self.corner_speed_straight
        elif bearing_change <= self.SEUIL_CORNER_SLIGHT:
            return self.corner_speed_slight
        elif bearing_change <= self.SEUIL_CORNER_MODERATE:
            return self.corner_speed_moderate
        elif bearing_change <= self.SEUIL_CORNER_SHARP:
            return self.corner_speed_sharp
        else:
            return self.corner_speed_hairpin


# ========================================================================
# PROFILS PRÉDÉFINIS
# ========================================================================

def create_amateur_profile() -> CyclistBehavior:
    """Profil cycliste amateur prudent"""
    return CyclistBehavior(uphill='conservative', downhill='conservative', corner='conservative')

def create_competitive_profile() -> CyclistBehavior:
    """Profil cycliste compétiteur"""
    return CyclistBehavior(uphill='realistic', downhill='realistic', corner='realistic')

def create_pro_profile() -> CyclistBehavior:
    """Profil cycliste professionnel validé pour sorties pro/entraînement rapides."""
    profile = CyclistBehavior(uphill='aggressive', downhill='aggressive', corner='aggressive')

    # Paramètres validés sur le cas Seixas (vitesse max ~87 km/h) avec compromis réalisme/sécurité.
    profile.downhill_vitesse_max_absolue = 27.0
    profile.downhill_vitesse_reduction_factor = 0.3
    profile.downhill_vitesse_reduction_cap = 0.03
    profile.downhill_corner_safety_factor = 0.97

    profile.corner_speed_straight = 27.0
    profile.corner_speed_slight = 26.0
    profile.corner_speed_moderate = 25.0
    profile.corner_speed_sharp = 20.0
    profile.corner_speed_hairpin = 14.0

    return profile
