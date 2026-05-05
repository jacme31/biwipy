# ==========================================
# cyclist_params.py
# Cyclist behavior parameters
# ==========================================

import json
from pathlib import Path
from typing import Optional, Dict, Any


class CyclistBehavior:
    """
    Centralized cyclist behavior parameters.
    
    Groups:
    - Slope thresholds (uphill/downhill)
    - Turn thresholds
    - Uphill behavior factors (3 modes: realistic, conservative, aggressive)
    - Downhill behavior factors (3 modes)
    - Turn speed limits (3 modes)
    
    Usage:
    ------
    # Create mixed profile
    >>> params = CyclistBehavior(uphill='realistic', downhill='conservative', corner='aggressive')
    
    # Customize specific parameter
    >>> params.corner_speed_slight = 20.0  # m/s
    
    # Save
    >>> params.save('/path/to/configs', 'remco_profile.json')
    
    # Load
    >>> params = CyclistBehavior.load('/path/to/configs', 'remco_profile.json')
    """
    
    # ========================================================================
    # SLOPE THRESHOLDS (unique values, no variation by mode)
    # ========================================================================
    SEUIL_MONTEE_FORTE = 0.08       # ≥ 8% : steep uphill
    SEUIL_MONTEE_MODEREE = 0.03     # ≥ 3% : moderate uphill
    SEUIL_MONTEE_LEGERE = 0.01      # ≥ 1% : slight uphill
    SEUIL_PLAT = -0.02              # > -2% : considered flat
    SEUIL_DESCENTE_LEGERE = -0.05   # > -5% : slight downhill
    
    # ========================================================================
    # TURN THRESHOLDS (in degrees, unique values)
    # ========================================================================
    SEUIL_CORNER_STRAIGHT = 5       # < 5° : straight
    SEUIL_CORNER_SLIGHT = 20        # < 20° : slight turn
    SEUIL_CORNER_MODERATE = 45      # < 45° : moderate turn
    SEUIL_CORNER_SHARP = 90         # < 90° : sharp turn
    # > 90° : hairpin
    
    # ========================================================================
    # UPHILL BEHAVIOR PRESETS
    # ========================================================================
    UPHILL_PRESETS = {
        'realistic': {
            'facteur_forte': 3.5,      # +35% power per 10% slope
            'facteur_moderee': 2.5,    # +25% power per 10% slope
            'facteur_legere': 1.5,     # +15% power per 10% slope
        },
        'conservative': {
            'facteur_forte': 2.0,      # +20% power per 10% slope
            'facteur_moderee': 2.0,
            'facteur_legere': 2.0,
        },
        'aggressive': {
            'facteur_forte': 4.0,      # +40% power per 10% slope
            'facteur_moderee': 4.0,
            'facteur_legere': 4.0,
        },
    }
    
    # ========================================================================
    # DOWNHILL BEHAVIOR PRESETS
    # ========================================================================
    DOWNHILL_PRESETS = {
        'realistic': {
            'facteur_legere': 6.0,              # Moderate reduction on slight descent
            'facteur_forte': 20.0,              # Strong reduction on steep descent
            'puissance_min': 10,                # Minimum watts
            'vitesse_reduction_factor': 2.5,    # Progressive braking by slope (Jan 2026 fix)
            'vitesse_reduction_cap': 0.40,      # Reduction cap: 40% max
            'vitesse_max_absolue': 22.0,        # m/s = 79.2 km/h
            'corner_downhill_safety_factor': 0.90,  # Multiplier for turn+downhill
        },
        'conservative': {
            'facteur_legere': 3.0,              # Less reduction
            'facteur_forte': 3.0,
            'puissance_min': 10,
            'vitesse_reduction_factor': 10.0,   # Stronger braking
            'vitesse_reduction_cap': 0.70,
            'vitesse_max_absolue': 18.0,        # m/s = 64.8 km/h
            'corner_downhill_safety_factor': 0.85,  # Multiplier for turn+downhill
        },
        'aggressive': {
            'facteur_legere': 5.0,              # More reduction (racing descent)
            'facteur_forte': 5.0,
            'puissance_min': 10,
            'vitesse_reduction_factor': 1.0,    # Light braking
            'vitesse_reduction_cap': 0.10,      # Almost no limit
            'vitesse_max_absolue': 22.0,        # m/s = 79.2 km/h (pro level)
            'corner_downhill_safety_factor': 0.97,  # Multiplier for turn+downhill
        },
    }
    
    # ========================================================================
    # TURN BEHAVIOR PRESETS (max speeds in m/s)
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
            'slight': 22.0,        # 79 km/h (pro: no braking on slight turn)
            'moderate': 22.0,      # 79 km/h
            'sharp': 22.0,         # 79 km/h
            'hairpin': 22.0,       # 79 km/h (limite pour pro expérimenté)
        },
    }
    
    def __init__(self, uphill: str = 'realistic', 
                 downhill: str = 'realistic', 
                 corner: str = 'realistic'):
        """
        Initialize a cyclist behavior profile.
        
        Parameters:
        -----------
        uphill : str
            Uphill behavior mode: 'realistic', 'conservative', 'aggressive'
        downhill : str
            Downhill behavior mode: 'realistic', 'conservative', 'aggressive'
        corner : str
            Turn behavior mode: 'realistic', 'conservative', 'aggressive'
        """
        if uphill not in self.UPHILL_PRESETS:
            raise ValueError(f"Invalid uphill mode: {uphill}. Choose from {list(self.UPHILL_PRESETS.keys())}")
        if downhill not in self.DOWNHILL_PRESETS:
            raise ValueError(f"Invalid downhill mode: {downhill}. Choose from {list(self.DOWNHILL_PRESETS.keys())}")
        if corner not in self.CORNER_PRESETS:
            raise ValueError(f"Invalid corner mode: {corner}. Choose from {list(self.CORNER_PRESETS.keys())}")
        
        self.mode_uphill = uphill
        self.mode_downhill = downhill
        self.mode_corner = corner
        
        # Load presets
        self._load_uphill_preset(uphill)
        self._load_downhill_preset(downhill)
        self._load_corner_preset(corner)
    
    def _load_uphill_preset(self, mode: str):
        """Load uphill parameters from preset"""
        preset = self.UPHILL_PRESETS[mode]
        self.uphill_facteur_forte = preset['facteur_forte']
        self.uphill_facteur_moderee = preset['facteur_moderee']
        self.uphill_facteur_legere = preset['facteur_legere']
    
    def _load_downhill_preset(self, mode: str):
        """Load downhill parameters from preset"""
        preset = self.DOWNHILL_PRESETS[mode]
        self.downhill_facteur_legere = preset['facteur_legere']
        self.downhill_facteur_forte = preset['facteur_forte']
        self.downhill_puissance_min = preset['puissance_min']
        self.downhill_vitesse_reduction_factor = preset['vitesse_reduction_factor']
        self.downhill_vitesse_reduction_cap = preset['vitesse_reduction_cap']
        self.downhill_vitesse_max_absolue = preset['vitesse_max_absolue']
        self.downhill_corner_safety_factor = preset['corner_downhill_safety_factor']
    
    def _load_corner_preset(self, mode: str):
        """Load turn parameters from preset"""
        preset = self.CORNER_PRESETS[mode]
        self.corner_speed_straight = preset['straight']
        self.corner_speed_slight = preset['slight']
        self.corner_speed_moderate = preset['moderate']
        self.corner_speed_sharp = preset['sharp']
        self.corner_speed_hairpin = preset['hairpin']
    
    def display(self, verbose: bool = True):
        """
        Display current configuration with explanations.
        
        Parameters:
        -----------
        verbose : bool
            If True, display full details. If False, display summary only.
        """
    
        print("Behaviour profile:",end=" ")
        print(f"Uphill={self.mode_uphill.upper()}",end=" - ")
        print(f"Downhill={self.mode_downhill.upper()}",end=" - ")
        print(f"Corner={self.mode_corner.upper()}")

        
        if verbose:
            print("\n📈 UPHILL BEHAVIOR")
            print("-" * 80)
            print(f"  Steep uphill (≥{self.SEUIL_MONTEE_FORTE*100:.0f}%)    : factor {self.uphill_facteur_forte:.1f}  "
                  f"→ +{self.uphill_facteur_forte*10:.0f}% power per 10% slope")
            print(f"  Moderate uphill (≥{self.SEUIL_MONTEE_MODEREE*100:.0f}%)  : factor {self.uphill_facteur_moderee:.1f}  "
                  f"→ +{self.uphill_facteur_moderee*10:.0f}% power per 10% slope")
            print(f"  Slight uphill (≥{self.SEUIL_MONTEE_LEGERE*100:.0f}%)   : factor {self.uphill_facteur_legere:.1f}  "
                  f"→ +{self.uphill_facteur_legere*10:.0f}% power per 10% slope")
            
            print("\n📉 DOWNHILL BEHAVIOR")
            print("-" * 80)
            print(f"  Slight downhill (>{self.SEUIL_DESCENTE_LEGERE*100:.0f}%) : factor {self.downhill_facteur_legere:.1f}")
            print(f"  Steep downhill (<{self.SEUIL_DESCENTE_LEGERE*100:.0f}%)  : factor {self.downhill_facteur_forte:.1f}")
            print(f"  Minimum power               : {self.downhill_puissance_min} W")
            print(f"  Absolute max speed          : {self.downhill_vitesse_max_absolue:.1f} m/s ({self.downhill_vitesse_max_absolue*3.6:.1f} km/h)")
            print(f"  Progressive braking         : factor {self.downhill_vitesse_reduction_factor:.1f}, cap {self.downhill_vitesse_reduction_cap*100:.0f}%")
            print(f"  Turn+downhill safety        : x{self.downhill_corner_safety_factor:.2f}")
            
            print("\n🔄 TURN BEHAVIOR")
            print("-" * 80)
            print(f"  Straight line (<{self.SEUIL_CORNER_STRAIGHT}°)    : {self.corner_speed_straight:.1f} m/s ({self.corner_speed_straight*3.6:.0f} km/h)")
            print(f"  Slight turn (<{self.SEUIL_CORNER_SLIGHT}°)   : {self.corner_speed_slight:.1f} m/s ({self.corner_speed_slight*3.6:.0f} km/h)")
            print(f"  Moderate turn (<{self.SEUIL_CORNER_MODERATE}°)  : {self.corner_speed_moderate:.1f} m/s ({self.corner_speed_moderate*3.6:.0f} km/h)")
            print(f"  Sharp turn (<{self.SEUIL_CORNER_SHARP}°)   : {self.corner_speed_sharp:.1f} m/s ({self.corner_speed_sharp*3.6:.0f} km/h)")
            print(f"  Hairpin (>{self.SEUIL_CORNER_SHARP}°)       : {self.corner_speed_hairpin:.1f} m/s ({self.corner_speed_hairpin*3.6:.0f} km/h)")
        
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary for save.
        
        Returns:
        --------
        dict : Complete configuration
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
        
        print(f"✅ Configuration sauvegardée: {filepath}")
    
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
        
        print(f"✅ Configuration chargée: {filepath}")
        return instance
    
    def get_uphill_factor(self, slope: float) -> float:
        """
        Return appropriate power factor for given slope.
        
        Parameters:
        -----------
        slope : float
            Slope (ratio, e.g., 0.05 = 5%)
        
        Returns:
        --------
        float : Power multiplier factor
        """
        if slope >= self.SEUIL_MONTEE_FORTE:
            return self.uphill_facteur_forte
        elif slope >= self.SEUIL_MONTEE_MODEREE:
            return self.uphill_facteur_moderee
        elif slope >= self.SEUIL_MONTEE_LEGERE:
            return self.uphill_facteur_legere
        else:
            return 0.0  # No uphill
    
    def get_corner_speed_limit(self, bearing_change: float) -> float:
        """
        Return maximum speed for given turn.
        
        Parameters:
        -----------
        bearing_change : float
            Direction change in degrees (0-180)
        
        Returns:
        --------
        float : Maximum speed in m/s
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
    """Conservative amateur cyclist profile"""
    return CyclistBehavior(uphill='conservative', downhill='conservative', corner='conservative')

def create_competitive_profile() -> CyclistBehavior:
    """Competitive cyclist profile"""
    return CyclistBehavior(uphill='realistic', downhill='realistic', corner='realistic')

def create_pro_profile() -> CyclistBehavior:
    """Professional cyclist profile validated for pro races/high-speed training."""
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
