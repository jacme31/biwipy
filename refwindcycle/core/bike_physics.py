# ==========================================
# bike_physics_v2.py (version complète)
# ==========================================

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from copy import deepcopy
import logging
import locale
import os
from .cyclist_params import CyclistBehavior


logger = logging.getLogger(__name__)


def _detect_output_lang() -> str:
    """Detect output language: env var OUTPUT_LANG → OS locale → default EN."""
    lang = os.environ.get("OUTPUT_LANG", "").lower()
    if lang in ("fr", "en"):
        return lang
    try:
        loc = locale.getlocale()[0] or locale.getdefaultlocale()[0] or ""
        if loc.startswith("fr"):
            return "fr"
    except Exception:
        pass
    return "en"


_I18N = {
    "cyclist_profile": {
        "fr": "\n  PROFIL CYCLISTE: {uphill} (montée) / {downhill} (descente) / {corner} (virages)",
        "en": "\n  CYCLIST PROFILE: {uphill} (uphill) / {downhill} (downhill) / {corner} (corners)",
    },
    "ref_power": {
        "fr": "Puissance de référence sur le plat: {p0:.1f} W\n",
        "en": "Reference power on flat: {p0:.1f} W\n",
    },
    "expected_power_by_slope": {
        "fr": "Puissances prévues selon la pente:",
        "en": "Expected power by slope:",
    },
    "dash_60": {"fr": "------------------------------------------------------------", "en": "------------------------------------------------------------"},
    "eq_70": {"fr": "======================================================================\n", "en": "======================================================================\n"},
    "power_line": {
        "fr": "{label:28s}: {power:5.1f} W ({ratio:5.1f}% | {sign}{variation:5.1f}W)",
        "en": "{label:28s}: {power:5.1f} W ({ratio:5.1f}% | {sign}{variation:5.1f}W)",
    },
    "slope_very_steep_down": {"fr": "Descente très forte -10%", "en": "Very steep descent -10%"},
    "slope_down5": {"fr": "Descente -5%", "en": "Descent -5%"},
    "slope_down2": {"fr": "Légère descente -2%", "en": "Slight descent -2%"},
    "slope_flat": {"fr": "Plat", "en": "Flat"},
    "slope_up2": {"fr": "Légère montée +2%", "en": "Slight climb +2%"},
    "slope_up5": {"fr": "Montée +5%", "en": "Climb +5%"},
    "slope_up8": {"fr": "Montée forte +8%", "en": "Strong climb +8%"},
    "slope_very_steep_up": {"fr": "Montée très forte +10%", "en": "Very steep climb +10%"},
}


def _t(key: str, **kwargs) -> str:
    lang = _detect_output_lang()
    labels = _I18N.get(key, {})
    template = labels.get(lang) or labels.get("en") or key
    return template.format(**kwargs) if kwargs else template


def _tp(key: str, **kwargs) -> None:
    print(_t(key, **kwargs))

# -------------------------------------------------
# Constantes physiques
# -------------------------------------------------
G = 9.80665
RHO_STD = 1.225  # kg/m³ au niveau de la mer (15°C, 101325 Pa)

# Constants for downhill safety/realism (Jan 2026 fix)
DESCENTE_VITESSE_MAX_REDUCTION_FACTOR = 2.5
DESCENTE_VITESSE_MAX_REDUCTION_CAP = 0.40
SEUIL_DESCENTE_MAX = 0.00


# -------------------------------------------------
# Densité de l'air en fonction de l'altitude
# -------------------------------------------------
def calculate_air_density(altitude_m: float, temperature_c: float = 15.0) -> float:
    """
    Calcule la densité de l'air en fonction de l'altitude et de la température.
    
    Utilise la formule barométrique simplifiée de l'atmosphère standard ISA.
    
    Parameters:
    -----------
    altitude_m : float
        Altitude en mètres
    temperature_c : float, optional
        Température en degrés Celsius (défaut: 15°C)
    
    Returns:
    --------
    float : Densité de l'air en kg/m³
    
    Exemples:
    ---------
    >>> calculate_air_density(0)      # Niveau de la mer
    1.225 kg/m³
    >>> calculate_air_density(1500)   # Kigali (Rwanda)
    1.049 kg/m³ (-14.4% résistance aéro)
    >>> calculate_air_density(2500)   # La Paz (Bolivie)
    0.948 kg/m³ (-22.6% résistance aéro)
    """
    # Température en Kelvin
    T0 = 288.15  # 15°C au niveau de la mer
    T = temperature_c + 273.15
    
    # Pression atmosphérique selon altitude (formule barométrique)
    # P = P0 * (1 - L*h/T0)^(g*M/(R*L))
    # Simplifié: P/P0 ≈ exp(-h/H) avec H ≈ 8400m (hauteur d'échelle)
    P_ratio = (1 - 0.0065 * altitude_m / T0) ** 5.255
    
    # Densité: rho = rho0 * (P/P0) * (T0/T)
    rho = RHO_STD * P_ratio * (T0 / T)
    
    return rho

# -------------------------------------------------
# Comportement cycliste par défaut
# -------------------------------------------------
# Utilisé si aucun CyclistBehavior n'est fourni
_DEFAULT_BEHAVIOR = None

def get_default_behavior() -> CyclistBehavior:
    """Retourne le comportement cycliste par défaut (realistic)"""
    global _DEFAULT_BEHAVIOR
    if _DEFAULT_BEHAVIOR is None:
        _DEFAULT_BEHAVIOR = CyclistBehavior(uphill='realistic', downhill='realistic', corner='realistic')
    return _DEFAULT_BEHAVIOR


# -------------------------------------------------
# Calibration : trouve CdA optimal pour matcher puissance cible
# -------------------------------------------------
def calibrate_cda_from_power(segments_in: List[Dict],
                             grib,
                             t_start,
                             target_power: float,
                             Cr: float = 0.005,
                             m: float = 100.0,
                             cda_min: float = 0.30,
                             cda_max: float = 0.60,
                             tolerance: float = 1.0,
                             max_iterations: int = 20,
                             behavior: Optional[CyclistBehavior] = None,
                             **sim_kwargs) -> Tuple[float, float, float]:
    """
    Trouve la valeur de CdA qui produit une puissance moyenne proche de target_power.
    
    IMPORTANT: En mode use_gpx_timestamps, V0/P0 n'influencent pas vitesse/temps.
    Le P0 retourné est donc obtenu via calibrage final (calibrate_p0=True)
    pour rester cohérent avec les simulations ultérieures.
    
    Utilise une recherche dichotomique (bisection) pour converger rapidement.
    
    Parameters:
    -----------
    segments_in : List[Dict]
        Segments du parcours
    grib : Grib
        Objet GRIB pour données météo
    t_start : datetime
        Heure de départ
    target_power : float
        Puissance moyenne cible (ex: 175 W de Strava)
    Cr : float
        Coefficient de roulement
    m : float
        Masse totale (kg)
    cda_min, cda_max : float
        Bornes de recherche pour CdA
    tolerance : float
        Tolérance acceptable (W)
    max_iterations : int
        Nombre max d'itérations
    behavior : CyclistBehavior, optional
        Profil comportemental cycliste utilisé pour calibrer le P0 final.
        Si fourni, le P0 retourné est recalibré via ``calibrate_p0=True``
        pour rester cohérent avec les simulations ultérieures.
    **sim_kwargs : dict
        Paramètres additionnels pour simulate_with_weather
    
    Returns:
    --------
    Tuple[float, float, float] : (CdA optimal, P0 optimal, puissance moyenne obtenue)
    
    Example:
    --------
    >>> cda_opt, p0_opt, power_opt = calibrate_cda_from_power(
    ...     segments, grib, t_start, 
    ...     target_power=175.0, Cr=0.0065, m=100
    ... )
    >>> print(f"CdA optimal: {cda_opt:.3f}, P0: {p0_opt:.1f}W → {power_opt:.1f} W")
    """
    
    logging.info(f"\n{'='*70}")
    logging.info(f"CALIBRATION CdA pour atteindre {target_power:.1f} W")
    logging.info(f"Paramètres: Cr={Cr:.4f}, m={m:.1f}kg")
    logging.info(f"Plage CdA: [{cda_min:.3f}, {cda_max:.3f}]")
    logging.info(f"⚠️  P0 retourné sera calibré en fin de recherche")
    logging.info(f"{'='*70}")
    
    # Valeurs initiales
    cda_low = cda_min
    cda_high = cda_max
    
    # Préparer les kwargs pour simulate_with_weather
    sim_params = {
        'passes': 2,
        'use_gpx_timestamps': True,
        'Cr': Cr,
        'm': m,
        'g': G,
    }
    if behavior is not None:
        sim_params['behavior'] = behavior
    sim_params.update(sim_kwargs)
    
    for iteration in range(max_iterations):
        # Test du milieu de l'intervalle
        cda_mid = (cda_low + cda_high) / 2

        # Simulation avec ce CdA et son P0 correspondant
        _, _, _, power_mid, _ = simulate_with_weather(
            segments_in, grib, t_start, CdA=cda_mid, **sim_params
        )
        
        error = power_mid - target_power
        
        logging.info(f"Iter {iteration+1:2d}: CdA={cda_mid:.4f} → P_avg={power_mid:6.1f}W (écart: {error:+6.1f}W)")
        
        # Convergence ?
        if abs(error) < tolerance:
            logging.info("   Recalibrage P0 final pour cohérence simulation...")
            _, _, p0_return, power_return, _ = simulate_with_weather(
                segments_in,
                grib,
                t_start,
                CdA=cda_mid,
                calibrate_p0=True,
                **sim_params,
            )

            logging.info(
                f"\n✅ Convergé ! CdA={cda_mid:.4f}, P0={p0_return:.1f}W → Puissance={power_return:.1f}W"
            )
            logging.info(f"   Écart avec cible ({target_power:.1f}W): {power_return - target_power:+.1f}W\n")
            return cda_mid, p0_return, power_return
        
        # Ajuster l'intervalle
        if power_mid < target_power:
            # Puissance trop faible → augmenter CdA
            cda_low = cda_mid
        else:
            # Puissance trop forte → réduire CdA
            cda_high = cda_mid
    
    # Max iterations atteintes
    cda_final = (cda_low + cda_high) / 2
    _, _, _, power_final, _ = simulate_with_weather(
        segments_in, grib, t_start, CdA=cda_final, **sim_params
    )

    p0_return = 0.0
    power_return = power_final
    logging.info("Recalibrage P0 final pour cohérence simulation...")
    _, _, p0_return, power_return, _ = simulate_with_weather(
        segments_in,
        grib,
        t_start,
        CdA=cda_final,
        calibrate_p0=True,
        **sim_params,
    )
    
    logging.warning(f"\n⚠️  Max iterations atteintes ({max_iterations})")
    logging.info(f"   Meilleur CdA trouvé: {cda_final:.4f}, P0={p0_return:.1f}W → {power_return:.1f}W")
    logging.info(f"   Écart restant: {power_return - target_power:+.1f}W\n")
    
    return cda_final, p0_return, power_return


# -------------------------------------------------
# Calibration : trouve P0 optimal pour matcher puissance observée (target_power)
# -------------------------------------------------
def calibrate_P0_from_observed_power(segments: List[Dict],
                                     target_power: Optional[float] = None,
                                     behavior: Optional[CyclistBehavior] = None,
                                     p0_min: float = 50.0,
                                     p0_max: float = 400.0,
                                     tolerance: float = 1.0,
                                     max_iterations: int = 20) -> float:
    """
    Trouve la valeur de P0 qui reproduit la puissance moyenne observée sur le parcours
    pour un profil comportemental donné.
    
    Utilisé avec segments ayant déjà des puissances physiques calculées depuis vitesses GPX.
    Permet de déduire la puissance de référence P0 du cycliste selon son comportement.
    
    Utilise une recherche dichotomique (bisection) pour converger rapidement.
    
    Parameters:
    -----------
    segments : List[Dict]
        Segments avec puissances physiques et pentes effectives déjà calculées
        Doit contenir : 'power', 'slope_effective', 'time_s', 'speed_m_s' pour chaque segment
    behavior : CyclistBehavior, optional
        Profil comportemental (realistic, aggressive, etc.). Si None, utilise défaut.
    p0_min, p0_max : float
        Bornes de recherche pour P0 (W)
    tolerance : float
        Tolérance acceptable (W)
    max_iterations : int
        Nombre max d'itérations
    
    Returns:
    --------
    float : P0 optimal (W)
    
    Example:
    --------
    >>> # Après simulate_with_weather avec use_gpx_timestamps
    >>> segments_with_power, _, _, power_observed = simulate_with_weather(
    ...     segments, grib, t_start, use_gpx_timestamps=True, CdA=0.35, Cr=0.0065, m=80
    ... )
    >>> 
    >>> # Calibrer P0 pour reproduire cette puissance avec un profil realistic
    >>> p0_opt, power_obs, power_model = calibrate_P0_from_observed_power(
    ...     segments_with_power,
    ...     behavior=CyclistBehavior('realistic', 'realistic', 'realistic')
    ... )
    >>> print(f"P0 calibré: {p0_opt:.1f}W pour reproduire {power_obs:.1f}W observés")
    """
    if behavior is None:
        behavior = get_default_behavior()

    # Filtrer segments en mouvement (vitesse > 1 m/s)
    moving_segments = [seg for seg in segments 
                       if seg.get('speed_m_s', 0) >= 1.0 
                       and seg.get('time_s', 0) > 0
                       and 'power' in seg]
    
    if not moving_segments:
        logging.error("Aucun segment en mouvement avec puissance trouvé !")
        return p0_min
    
    # Calculer la puissance moyenne OBSERVÉE (depuis vitesses GPX)
    total_power_time_obs = sum(seg['power'] * seg['time_s'] for seg in moving_segments)
    total_time = sum(seg['time_s'] for seg in moving_segments)
    target_power = total_power_time_obs / total_time
    
    logging.info(f"\n{'='*70}")
    logging.info(f"CALIBRATION P0 pour reproduire {target_power:.1f} W observés")
    logging.info(f"Profil: {behavior.mode_uphill}/{behavior.mode_downhill}/{behavior.mode_corner}")
    logging.info(f"Segments en mouvement: {len(moving_segments)}/{len(segments)}")
    logging.info(f"Plage P0: [{p0_min:.0f}, {p0_max:.0f}] W")
    logging.info(f"{'='*70}")
   
    def compute_avg_power_model(P0_test, b_keeppower=False) -> float:

        if (b_keeppower):
            # P0_test est le P0 convergé 
            # On est en fin d'itération on stocke les champs power_model pour analyse/debug
            for seg in segments:
                if seg.get('speed_m_s', 0) >= 1.0:
                    seg['power_model'] = calculate_adaptive_power(P0_test, seg.get('slope_effective', seg.get('slope', 0.0)), behavior)
                else:
                    seg['power_model'] = 0.0  # Segments à l'arrêt
            """Calcule la puissance moyenne MODÈLE pour un P0 donné"""
            return (P0_test)  
        else    :   
            # iteration normale     
            total_power_time = 0.0
            
            for seg in moving_segments:
                # IMPORTANT: Utiliser slope_terrain (pente physique) pour déterminer le comportement,
                # pas slope_effective (qui inclut l'effet du vent)
                # Le cycliste adapte sa puissance selon la PENTE RÉELLE, pas la pente "ressentie"
                slope_terrain = seg.get('slope_terrain', seg.get('slope', 0.0))
                time_s = seg['time_s']
                slope_effective = seg.get('slope_effective', slope_terrain)
                # Correctif : Pas d'accord avec le commentaire précédent
                # la puissance adaptée selon profil comportemental qui prend compte pente terrain +virtuel 
                # pente effective plutot qure terrain 
                P_seg = calculate_adaptive_power(P0_test, slope_effective, behavior)
                total_power_time += P_seg * time_s
                       
            return (total_power_time / total_time)
    
    # Bisection
    p0_low = p0_min
    p0_high = p0_max
    
    for iteration in range(max_iterations):
        p0_mid = (p0_low + p0_high) / 2
        power_model = compute_avg_power_model(p0_mid)
        error = power_model - target_power
        
        logging.info(f"Iter {iteration+1:2d}: P0={p0_mid:6.1f}W → P_modèle={power_model:6.1f}W vs P_obs={target_power:6.1f}W (écart: {error:+6.1f}W)")
        
        # Convergence ?
        if abs(error) < tolerance:
            logging.info(f"\n✅ Convergé ! P0={p0_mid:.1f}W reproduit {target_power:.1f}W observés")
            logging.info(f"   Puissance modèle: {power_model:.1f}W (écart: {error:+.1f}W)\n")
            # Ajouter power_model à TOUS les segments pour analyse/debug
            for seg in segments:  # Utiliser 'segments' pas 'moving_segments'
                if seg.get('speed_m_s', 0) >= 1.0:
                    seg['power_model'] = calculate_adaptive_power(p0_mid, seg.get('slope_effective', seg.get('slope', 0.0)), behavior)
                else:
                    seg['power_model'] = 0.0  # Segments à l'arrêt
            return p0_mid
        
        # Ajuster l'intervalle
        if power_model < target_power:
            # Puissance trop faible → augmenter P0
            p0_low = p0_mid
        else:
            # Puissance trop forte → réduire P0
            p0_high = p0_mid
    
    # Max iterations atteintes
    p0_final = (p0_low + p0_high) / 2
    power_final = compute_avg_power_model(p0_final,b_keeppower=True)
    
    logging.warning(f"\n⚠️  Max iterations atteintes ({max_iterations})")
    logging.info(f"   Meilleur P0 trouvé: {p0_final:.1f}W → {power_final:.1f}W")
    logging.info(f"   Puissance observée: {target_power:.1f}W (écart: {power_final - target_power:+.1f}W)\n")
    return p0_final


# -------------------------------------------------
# Limitation de vitesse dans les virages (vitesses absolues)
# -------------------------------------------------
def calculate_corner_speed_limit(bearing_change: float, behavior: Optional[CyclistBehavior] = None) -> float:
    """
    Calcule la vitesse maximale absolue (limite d'adhérence) dans un virage 
    en fonction du changement de direction.
    
    Basée sur v_max = sqrt(μ * g * R) : limite FIXE indépendante de la vitesse d'arrivée.
    
    Parameters:
    -----------
    bearing_change : float
        Changement de direction en degrés (0-180)
    
    Returns:
    --------
    float : Vitesse maximale absolue pour ce virage (m/s)
    
    Exemples:
    ---------
    >>> calculate_corner_speed_limit(0)    # Ligne droite
    22.0 m/s (79 km/h)
    >>> calculate_corner_speed_limit(45)   # Virage modéré
    14.0 m/s (50 km/h)
    >>> calculate_corner_speed_limit(90)   # Virage à 90°
    8.0 m/s (29 km/h)
    >>> calculate_corner_speed_limit(120)  # Épingle
    4.5 m/s (16 km/h)
    """
    if behavior is None:
        behavior = get_default_behavior()
    
    bearing_change = abs(bearing_change)
    return behavior.get_corner_speed_limit(bearing_change)

# -------------------------------------------------
# Calcul du dénivelé virtuel équivalent dû au vent
# -------------------------------------------------
def calculate_wind_equivalent_slope(v: float, 
                                   wind_along: float, 
                                   CdA: float, 
                                   m: float,
                                   rho: float = RHO_STD, 
                                   g: float = G) -> float:
    """
    Calcule le dénivelé virtuel (pente équivalente) correspondant à l'effet différentiel du vent.
    
    Cette fonction convertit l'effet ADDITIONNEL du vent (par rapport à une situation sans vent)
    en une pente équivalente, permettant d'utiliser les mécanismes existants d'adaptation de
    puissance aux côtes/descentes.
    
    Principe physique
    -----------------
    - Force aéro AVEC vent : F_aero_wind = 0.5 * rho * CdA * (v + wind_along)²
    - Force aéro SANS vent : F_aero_no_wind = 0.5 * rho * CdA * v²
    - Différence due au vent : ΔF_aero = F_aero_wind - F_aero_no_wind
    - Pente équivalente : slope_equivalent = ΔF_aero / (m * g)
    
    Cette approche permet d'isoler uniquement l'impact du vent, sans inclure
    la résistance aérodynamique de base du cycliste.
    
    Parameters:
    -----------
    v : float
        Vitesse du cycliste en m/s
    wind_along : float
        Composante du vent le long du segment en m/s
        - Positif : vent de face (headwind) → pente virtuelle positive (montée)
        - Négatif : vent de dos (tailwind) → pente virtuelle négative (descente)
        - Zéro : pas de vent → pente virtuelle nulle
    CdA : float
        Produit de la surface frontale et du coefficient de traînée (m²)
    m : float
        Masse totale (cycliste + vélo) en kg
    rho : float, optional
        Densité de l'air en kg/m³ (défaut: 1.225 kg/m³)
    g : float, optional
        Accélération gravitationnelle en m/s² (défaut: 9.80665 m/s²)
    
    Returns:
    --------
    float : Pente équivalente différentielle (ratio, ex: 0.05 pour 5%)
        - Positif : équivalent à une montée (vent de face augmente l'effort)
        - Négatif : équivalent à une descente (vent de dos réduit l'effort)
        - Zéro : pas de vent (aucun effet additionnel)
    
    Exemples:
    ---------
    >>> # Cycliste à 30 km/h (8.33 m/s), vent de face 20 km/h (5.56 m/s)
    >>> calculate_wind_equivalent_slope(8.33, 5.56, 0.35, 80)
    0.037  # Équivalent à une montée additionnelle de 3.7%
    
    >>> # Cycliste à 40 km/h (11.1 m/s), vent de dos 15 km/h (-4.17 m/s)
    >>> calculate_wind_equivalent_slope(11.1, -4.17, 0.35, 80)
    -0.012  # Équivalent à une descente de 1.2% (assistance)
    
    >>> # Sans vent
    >>> calculate_wind_equivalent_slope(10.0, 0.0, 0.35, 80)
    0.0  # Aucun effet additionnel
    
    Notes:
    ------
    - Cette fonction peut être utilisée pour adapter la puissance aux conditions
      de vent sans créer de nouveaux paramètres : on additionne simplement la
      pente réelle et la pente virtuelle du vent
    - Pour de très forts vents contraires, la pente virtuelle peut dépasser 10%
    - Pour de très forts vents de dos, la pente virtuelle peut être fortement négative
    """
    # Force aérodynamique AVEC vent
    v_rel_wind = v + wind_along
    if v_rel_wind < 0:
        v_rel_wind = 0  # Éviter valeurs négatives
    F_aero_with_wind = 0.5 * rho * CdA * v_rel_wind * v_rel_wind
    
    # Force aérodynamique SANS vent (référence)
    F_aero_no_wind = 0.5 * rho * CdA * v * v
    
    # Différence due uniquement au vent
    F_aero_diff = F_aero_with_wind - F_aero_no_wind
    
    # Pente équivalente différentielle
    slope_equivalent = F_aero_diff / (m * g)
    
    return slope_equivalent

# -------------------------------------------------
# Solveur : calcule la vitesse pour une puissance P donnée
# -------------------------------------------------
def solve_speed_for_power(P, CdA, Cr, m, slope, wind_along, rho=RHO_STD, g=G, v_max=22.0, behavior: Optional[CyclistBehavior] = None):
    """
    Calcule la vitesse pour une puissance donnée.
    
    Parameters:
    -----------
    v_max : float
        Vitesse maximale réaliste en m/s (défaut 22 m/s = 79 km/h)
        Cette limite évite les vitesses aberrantes en descente avec vent favorable
    behavior : CyclistBehavior, optional
        Profil de comportement cycliste. Si None, utilise le profil par défaut.
    
    Notes:
    ------
    En descente forte, applique une limite de sécurité basée sur la pente réelle.
    Cela modélise le freinage comportemental (sécurité, virage, confort).
    """
    if behavior is None:
        behavior = get_default_behavior()
    
    F_roll = Cr * m * g
    F_grav = m * g * slope
    
    # LIMITE DE SÉCURITÉ EN DESCENTE: Réduire v_max selon la pente pour modéliser le freinage
    # En descente, un cycliste ne va jamais aussi vite que la physique pure le permettrait
    # Il freine pour des raisons de sécurité, de contrôle, de courbes
    v_max_effective = v_max
    logging.debug(f"Initial v_max: {v_max_effective:.1f}m/s")
    if slope < behavior.SEUIL_DESCENTE_LEGERE:  # descente seuil    
        # Appliquer une réduction progressive de v_max avec la pente
        downhill_reduction = min(behavior.downhill_vitesse_reduction_cap, abs(slope) * behavior.downhill_vitesse_reduction_factor)
        v_max_effective = v_max * (1.0 - downhill_reduction)
        logging.debug(f"Downhill speed limit: slope={slope*100:.1f}% → reduction={downhill_reduction*100:.1f}% → v_max={v_max_effective:.1f}m/s")
    
    # LIMITE ABSOLUE RÉALISTE: même sur plat avec vent très favorable
    v_max_effective = min(v_max_effective, behavior.downhill_vitesse_max_absolue)
    
    a = 0.0
    b = v_max_effective
    
    for _ in range(40):
        v = (a + b)/2
        v_rel = v + wind_along
        if v_rel < 0:
            v_rel = 0
        F_aero = 0.5 * rho * CdA * v_rel*v_rel
        P_est = v * (F_aero + F_roll + F_grav)
        if P_est > P:
            b = v
        else:
            a = v
    
    # Limiter la vitesse finale avec v_max_effective (limite de descente appliquée)
    v_final = (a + b) / 2
    return min(v_final, v_max_effective)


# -------------------------------------------------
# Vitesse d'équilibre sur une pente sans vent
# -------------------------------------------------
def compute_speed_on_slope(power_w: float,
                           slope: float = 0.05,
                           CdA: float = 0.35,
                           Cr: float = 0.005,
                           m: float = 80.0,
                           rho: float = RHO_STD,
                           g: float = G,
                           v_max: float = 22.0) -> float:
    """
    Calcule la vitesse stabilisée sur une pente donnée (sans vent) pour une puissance fournie.

    Parameters
    ----------
    power_w : float
        Puissance constante fournie (W).
    slope : float, optional
        Pente (ratio, ex: 0.05 pour 5%).
    CdA : float, optional
        Surface frontale * coefficient de traînée (m²).
    Cr : float, optional
        Coefficient de roulement.
    m : float, optional
        Masse totale (cycliste + vélo) en kg.
    rho : float, optional
        Densité de l'air (kg/m³).
    g : float, optional
        Accélération gravitationnelle (m/s²).
    v_max : float, optional
        Vitesse maximale à considérer (m/s).

    Returns
    -------
    float
        Vitesse d'équilibre en m/s.
    """

    return solve_speed_for_power(
        power_w,
        CdA=CdA,
        Cr=Cr,
        m=m,
        slope=slope,
        wind_along=0.0,
        rho=rho,
        g=g,
        v_max=v_max,
    )

# -------------------------------------------------
# Solveur dynamique : calcule la vitesse finale en tenant compte de v_initial
# -------------------------------------------------
def solve_speed_dynamic(P, CdA, Cr, m, slope, wind_along, v_initial, distance,
                        rho=RHO_STD, g=G, v_max=22.0, dt=0.5, behavior: Optional[CyclistBehavior] = None):
    """
    Calcule la vitesse finale après avoir parcouru 'distance' mètres
    en partant de v_initial avec puissance P constante.
    
    Utilise l'équation dynamique : m*a = P/v - F_aero - F_roll - F_grav
    avec intégration numérique par pas de temps dt.
    
    Parameters:
    -----------
    P : float
        Puissance en Watts
    v_initial : float
        Vitesse initiale en m/s
    distance : float
        Distance du segment en mètres
    dt : float
        Pas de temps pour l'intégration (secondes)
    behavior : CyclistBehavior, optional
        Profil de comportement cycliste. Si None, utilise le profil par défaut.
    
    Returns:
    --------
    tuple: (v_final, v_avg, time_s)
        v_final : vitesse finale en m/s
        v_avg : vitesse moyenne sur le segment en m/s
        time_s : temps de parcours en secondes
    """
    if behavior is None:
        behavior = get_default_behavior()
    
    F_roll = Cr * m * g
    F_grav = m * g * slope
    
    # LIMITE DE SÉCURITÉ EN DESCENTE (même que dans solve_speed_for_power)
    v_max_effective = v_max
    if slope < behavior.SEUIL_DESCENTE_LEGERE:  # Toute descente
        downhill_reduction = min(behavior.downhill_vitesse_reduction_cap, abs(slope) * behavior.downhill_vitesse_reduction_factor)
        v_max_effective = v_max * (1.0 - downhill_reduction)
        logging.debug(f"Downhill speed limit: slope={slope*100:.1f}% → reduction={downhill_reduction*100:.1f}% → v_max={v_max_effective:.1f}m/s")
    
    # LIMITE ABSOLUE RÉALISTE
    v_max_effective = min(v_max_effective, behavior.downhill_vitesse_max_absolue)
    
    v = max(v_initial, 0.1)  # Éviter division par zéro
    dist_covered = 0.0
    time_elapsed = 0.0
    v_sum = 0.0
    n_steps = 0
    
    # Intégration numérique jusqu'à couvrir la distance
    max_iterations = int(distance / 0.1) + 1000  # Sécurité contre boucles infinies
    iteration = 0
    
    while dist_covered < distance and iteration < max_iterations:
        iteration += 1
        
        # Forces
        v_rel = v + wind_along
        if v_rel < 0:
            v_rel = 0
        F_aero = 0.5 * rho * CdA * v_rel * v_rel
        
        # Force nette
        if v > 0.1:
            F_net = P / v - F_aero - F_roll - F_grav
        else:
            # Si vitesse très faible, utiliser une petite vitesse pour éviter singularité
            F_net = P / 0.1 - F_aero - F_roll - F_grav
        
        # Accélération
        a = F_net / m
        
        # Mise à jour de la vitesse
        v_new = v + a * dt
        
        # Limiter la vitesse avec la limite de descente appliquée
        v_new = max(0.1, min(v_new, v_max_effective))
        
        # Vitesse moyenne pendant ce dt
        v_avg_step = (v + v_new) / 2
        
        # Distance parcourue pendant ce dt
        dx = v_avg_step * dt
        
        # Vérifier qu'on ne dépasse pas la distance totale
        if dist_covered + dx > distance:
            # Ajuster le dernier pas de temps
            remaining = distance - dist_covered
            dt_actual = remaining / v_avg_step if v_avg_step > 0.01 else dt
            dist_covered = distance
            time_elapsed += dt_actual
            v_sum += v_avg_step * dt_actual
        else:
            dist_covered += dx
            time_elapsed += dt
            v_sum += v_avg_step * dt
        
        n_steps += 1
        v = v_new
    
    # Vitesse moyenne pondérée par le temps
    v_avg = v_sum / time_elapsed if time_elapsed > 0 else v
    
    return v, v_avg, time_elapsed

# -------------------------------------------------
# Conversion CdA selon angle de vent (optionnel)
# -------------------------------------------------
def CdA_with_yaw(CdA, yaw_deg, k=0.02):
    return CdA * (1 + k * (abs(yaw_deg)/10.0))

# -------------------------------------------------
# Calcule P0 à partir d'une vitesse plate v0
# -------------------------------------------------
def estimate_P0_from_v0(v0, CdA=0.5, Cr=0.004, m=75.0, rho=RHO_STD, g=G):
    v_rel = v0
    F_aero = 0.5 * rho * CdA * v_rel*v_rel
    F_roll = Cr * m * g
    F_grav = 0
    return v0 * (F_aero + F_roll + F_grav)


# -------------------------------------------------
# Ajustement de la puissance selon la pente
# -------------------------------------------------
def calculate_adaptive_power(P0: float, slope: float, behavior: Optional[CyclistBehavior] = None) -> float:
    """
    Calcule la puissance adaptée selon la pente pour mieux correspondre au comportement réel.
    
    En montée : le cycliste augmente sa puissance pour maintenir un effort
    En descente : le cycliste réduit sa puissance (récupération, pédalage minimal)
    
    Parameters:
    -----------
    P0 : float
        Puissance de référence sur le plat (W)
    slope : float
        Pente du segment (décimal, ex: 0.05 = 5%)
    behavior : CyclistBehavior, optional
        Profil de comportement cycliste. Si None, utilise le profil par défaut.
    
    Returns:
    --------
    float : Puissance ajustée (W)
    
    Exemples:
    ---------
    >>> behavior = CyclistBehavior('realistic', 'realistic', 'realistic')
    >>> calculate_adaptive_power(120, 0.05, behavior)  # Montée 5%
    150.0  # +30W
    """
    if behavior is None:
        behavior = get_default_behavior()
    
    # Montée
    if slope >= behavior.SEUIL_MONTEE_FORTE:
        return P0 * (1 + slope * behavior.uphill_facteur_forte)
    elif slope >= behavior.SEUIL_MONTEE_MODEREE:
        return P0 * (1 + slope * behavior.uphill_facteur_moderee)
    elif slope >= behavior.SEUIL_MONTEE_LEGERE:
        return P0 * (1 + slope * behavior.uphill_facteur_legere)
    elif slope >= behavior.SEUIL_PLAT:
        return P0
    # Descente
    elif slope >= behavior.SEUIL_DESCENTE_LEGERE:
        return P0 * (1 + slope * behavior.downhill_facteur_legere)
    else:
        return max(behavior.downhill_puissance_min, P0 * (1 + slope * behavior.downhill_facteur_forte))


def print_power_model_info(P0: float, behavior: Optional[CyclistBehavior] = None):
    """
    Affiche un tableau résumé du modèle de puissance utilisé.
    Utile pour comprendre le comportement du modèle.
    """
    if behavior is None:
        behavior = get_default_behavior()
    
    _tp("cyclist_profile", uphill=behavior.mode_uphill.upper(), downhill=behavior.mode_downhill.upper(), corner=behavior.mode_corner.upper())
    _tp("ref_power", p0=P0)

    test_slopes = [
        (-0.10, "slope_very_steep_down"),
        (-0.05, "slope_down5"),
        (-0.02, "slope_down2"),
        (0.00, "slope_flat"),
        (0.02, "slope_up2"),
        (0.05, "slope_up5"),
        (0.08, "slope_up8"),
        (0.10, "slope_very_steep_up"),
    ]

    _tp("expected_power_by_slope")
    _tp("dash_60")
    for slope, key in test_slopes:
        label = _t(key)
        power = calculate_adaptive_power(P0, slope, behavior)
        ratio = (power / P0) * 100
        variation = power - P0
        sign = "+" if variation > 0 else ""
        _tp("power_line", label=label, power=power, ratio=ratio, sign=sign, variation=variation)
    _tp("eq_70")


# -------------------------------------------------
# Moteur complet de simulation avec météo + timestamps GPX
# -------------------------------------------------
def simulate_with_weather(segments_in: List[Dict],
                          grib,
                          t_start=None,
                          v0: Optional[float] = None,
                          P0: Optional[float] = None,
                          passes: int = 2,
                          use_gpx_timestamps: bool = False,
                          calibrate_p0: bool = False,
                          CdA: float = 0.5,
                          Cr: float = 0.004,
                          m: float = 75.0,
                          g: float = G,
                          clip_wind: float = 40.0,
                          use_yaw_cdA: bool = True,
                          ratio_wind: float = 0.25,
                          yaw_k: float = 0.02,
                          v_max: float = 22.0,
                          use_dynamic: bool = True,
                          limit_speed_in_corners: bool = True,
                          rho_forced: Optional[float] = None,
                          behavior: Optional[CyclistBehavior] = None) -> Tuple[List[Dict], float, float, float, datetime]:
    """
    Parameters:
    -----------
    t_start : datetime, optional
        Start time for simulation. 
        If use_gpx_timestamps=True and t_start is None, will be extracted from first GPX timestamp.
        If use_gpx_timestamps=False, must be provided.
    use_gpx_timestamps : bool
        Si True, utilise les timestamps GPX pour calculer vitesses et temps (pas de simulation).
        Les puissances physiques sont calculées depuis les vitesses observées.
    calibrate_p0 : bool
        Si True ET use_gpx_timestamps=True, calibre P0 à partir de la puissance observée
        selon le profil comportemental. Le P0 retourné devient cohérent avec les données.
        Désactivé par défaut pour rétrocompatibilité.
    use_dynamic : bool
        Si True, utilise la simulation dynamique avec inertie (défaut).
        Si False, utilise l'ancienne méthode (vitesse d'équilibre par segment).
    limit_speed_in_corners : bool
        Si True (défaut), réduit automatiquement la vitesse maximale dans les virages.
        Critique en descente pour modéliser le freinage dans les virages.
    rho_forced : Optional[float]
        Si fourni, force l'utilisation de cette densité d'air (kg/m³) pour tous les segments.
        Utile pour tester l'impact de l'altitude : comparer avec rho niveau mer vs altitude.
        Si None (défaut), calcul automatique depuis altitudes GPX si disponibles, sinon RHO_STD.
    behavior : CyclistBehavior, optional
        Profil de comportement cycliste. Si None, utilise le profil par défaut.
    
    Returns:
    --------
    Tuple[List[Dict], float, float, float, datetime]:
        - segments : liste des segments avec données calculées
        - avg_kmh : vitesse moyenne en km/h
        - P0 : puissance de référence (W)
                * Mode timestamps + calibrate_p0=True : P0 calibré selon profil
                * Mode timestamps + calibrate_p0=False : P0 fourni ou 120W défaut (informatif)
                * Mode simulation : P0 utilisé pour calcul
        - avg_power : puissance moyenne réelle pondérée par le temps (W)
        - t_start_extracted : datetime extracted from GPX (replay mode) or provided t_start (simulation mode)
```
    
    Notes & Simplifications:
    ------------------------
    - Le modèle intègre le ralentissement DANS les virages (corner_speed_limit)
    - Le ralentissement ANTICIPÉ AVANT les virages est NÉGLIGÉ (simplification acceptable)
      car implémenter un lookahead de freinage préventif serait complexe et ajouterait
      peu de précision comparé aux autres facteurs (gravité, pente, vent)
    """
    if behavior is None:
        behavior = get_default_behavior()
    
    if limit_speed_in_corners:
        logging.info("Corner speed limiting: ENABLED (reduces speed in turns, especially in descents)")
    else:
        logging.info("Corner speed limiting: DISABLED")
    
    segments = deepcopy(segments_in)

    for seg in segments:
        seg.setdefault('tws', None)
        seg.setdefault('twd', None)
        seg.setdefault('wind_along', None)
        seg.setdefault('speed_m_s', None)
        seg.setdefault('time_s', None)
        seg.setdefault('cum_t_start', None)
        seg.setdefault('cum_t_end', None)
        seg.setdefault('slope_terrain', seg.get('slope', 0.0))  # Initialiser slope_terrain à partir de slope

    def _resolve_segment_roughness(current_seg: Dict, lat: float, lon: float) -> Optional[float]:
        """Return z0 for segment if available, otherwise None (implicit fallback in grib manager)."""
        seg_rugosite = current_seg.get('rugosite')
        if seg_rugosite is not None and seg_rugosite > 0:
            return float(seg_rugosite)

        seg_z0 = current_seg.get('z0')
        if seg_z0 is not None and seg_z0 > 0:
            return float(seg_z0)

        if grib is None:
            return None

        roughness_provider = getattr(grib, 'roughness_provider', None)
        if roughness_provider is None:
            return None

        try:
            z0 = roughness_provider.get_z0(lat, lon)
        except Exception as exc:
            logging.warning(f"Roughness lookup failed at lat={lat:.5f}, lon={lon:.5f}: {exc}")
            return None

        if z0 is not None and z0 > 0:
            current_seg['rugosite'] = float(z0)
            return float(z0)
        return None

    # -------------------------------------------------
    # Si on utilise les timestamps GPX → désactive passes itératives
    # -------------------------------------------------
    if use_gpx_timestamps:
        # ===== EXTRACTION AUTOMATIQUE DU T_START SI NON FOURNI =====
        if t_start is None:
            # Vérifier qu'on a des segments avec timestamps
            if not segments or 'gpxtime_start' not in segments[0]:
                raise ValueError(
                    "Mode replay (use_gpx_timestamps=True) requires t_start parameter or "
                    "GPX timestamps in segments. First segment must have 'gpxtime_start' field."
                )
            
            # Extraire t_start du premier segment
            t_start = segments[0]['gpxtime_start']
            logging.info(f"✅ T_start auto-extracted from GPX: {t_start}")
        else:
            # ===== VALIDATION T_START VS TIMESTAMPS GPX =====
            # Vérifier que le t_start fourni correspond au premier timestamp GPX
            if 'gpxtime_start' in segments[0]:
                gpx_start = segments[0]['gpxtime_start']
                time_diff = abs((t_start - gpx_start).total_seconds())
                
                if time_diff > 60:  # Plus de 1 minute de différence
                    raise ValueError(
                        f"Replay mode: t_start mismatch with GPX timestamps!\n"
                        f"  Provided t_start: {t_start}\n"
                        f"  GPX first timestamp: {gpx_start}\n"
                        f"  Difference: {time_diff:.0f} seconds\n"
                        f"In replay mode, t_start must match GPX timestamps or be omitted for auto-extraction."
                    )
                elif time_diff > 1:  # Entre 1s et 60s : warning + utiliser GPX
                    logging.warning(
                        f"⚠️  t_start differs from GPX first timestamp by {time_diff:.1f}s\n"
                        f"   Provided: {t_start}\n"
                        f"   GPX: {gpx_start}\n"
                        f"   → Using GPX timestamp for consistency"
                    )
                    t_start = gpx_start  # Utiliser le timestamp GPX
                elif time_diff > 0.01:  # Petite différence (< 1s) : utiliser GPX silencieusement
                    logging.debug(f"Small t_start diff ({time_diff:.2f}s), using GPX timestamp")
                    t_start = gpx_start
                
                logging.info(f"T_start validated: {t_start}")
            else:
                logging.info(f"T_start provided: {t_start} (no GPX timestamps to validate)")
        
        t_start_extracted = t_start
        
        # En mode timestamps, P0/v0 sont optionnels (utilisés uniquement pour calcul informatif de puissance)
        if P0 is not None or v0 is not None:
            logging.warning("⚠️  Mode use_gpx_timestamps: P0 ou v0 fournis mais INUTILISÉS pour le calcul de vitesse/temps")
            logging.warning("   (vitesses calculées depuis timestamps GPX, P0 sert uniquement au calcul informatif de puissance)")
        
        # Calculer ou utiliser P0 pour le calcul informatif de puissance
        if P0 is None:
            if v0 is not None:
                P0 = estimate_P0_from_v0(v0, CdA=CdA, Cr=Cr, m=m, rho=rho_forced if rho_forced is not None else RHO_STD, g=g)
            else:
                # Valeur par défaut raisonnable (cycliste moyen)
                P0 = 120.0  # W
                logging.info(f"Mode timestamps: P0 non fourni, utilisation de {P0:.0f}W par défaut pour calcul informatif")
        
        logging.info(f"Using CYCLIST BEHAVIOR: {behavior.mode_uphill}/{behavior.mode_downhill}/{behavior.mode_corner} (timestamps mode, P0={P0:.1f}W informatif)")
        
        # Validation des timestamps GPX AVANT traitement
        logging.info("Validation des timestamps GPX...")
        max_reasonable_duration = 24 * 3600  # 24 heures max
        invalid_timestamps = []
        
        for i, seg in enumerate(segments):
            if 'gpxtime_start' not in seg or 'gpxtime_end' not in seg:
                raise ValueError(f"Segment {i}: gpxtime_start ou gpxtime_end manquant.")
            
            # Vérifier cohérence temporelle
            seg_duration = (seg['gpxtime_end'] - seg['gpxtime_start']).total_seconds()
            if seg_duration < 0:
                invalid_timestamps.append(f"Segment {i}: durée négative ({seg_duration:.1f}s)")
            elif seg_duration > 3600:  # 1 heure pour un segment = suspect
                invalid_timestamps.append(f"Segment {i}: durée excessive ({seg_duration/60:.1f} min)")
            
            # Vérifier écart avec t_start
            elapsed = (seg['gpxtime_start'] - t_start).total_seconds()
            if elapsed < 0:
                invalid_timestamps.append(f"Segment {i}: avant heure départ ({elapsed/60:.1f} min)")
            elif elapsed > max_reasonable_duration:
                invalid_timestamps.append(f"Segment {i}: {elapsed/3600:.1f}h après départ (suspect)")
        
        if invalid_timestamps:
            logging.error(f"\n⚠️  {len(invalid_timestamps)} timestamps GPX aberrants détectés:")
            for msg in invalid_timestamps[:10]:  # Afficher max 10
                logging.error(f"   - {msg}")
            if len(invalid_timestamps) > 10:
                logging.error(f"   ... et {len(invalid_timestamps)-10} autres")
            raise ValueError(f"Timestamps GPX corrompus détectés. Vérifier le fichier GPX source.")
        
        logging.info(f"✅ Timestamps validés : {len(segments)} segments OK")
        
        for i, seg in enumerate(segments):
            t_mid = seg['gpxtime_start'] + (seg['gpxtime_end'] - seg['gpxtime_start'])/2
            lat_m = 0.5*(seg['lat1'] + seg['lat2'])
            lon_m = 0.5*(seg['lon1'] + seg['lon2'])
            if grib is None:
                impact = {
                    'tws_m_s': 0.0,
                    'twd_deg': 0.0,
                    'gust_m_s': 0.0,
                    'headwind_m_s': 0.0,
                    'gust_along_m_s': 0.0,
                    'effective_wind_m_s': 0.0,
                    'crosswind_m_s': 0.0,
                    'is_headwind': False
                }
            else:
                rugosite_seg = _resolve_segment_roughness(seg, lat_m, lon_m)
                impact=grib.calculate_cycling_wind_impact(
                    t_mid,
                    lat_m,
                    lon_m,
                    seg['bearing'],
                    ratio_wind=ratio_wind,
                    rugosite=rugosite_seg,
                )
                if impact is None:
                    raise ValueError(f"Wind impact calculation failed at time {t_mid}, lat {lat_m}, lon {lon_m}")
                    return None
            tws, twd = impact['tws_m_s'], impact['twd_deg']
            if tws is None:
                tws, twd = 0.0, 0.0

            if abs(tws) > clip_wind:
                tws = max(min(tws, clip_wind), -clip_wind)
            seg['tws'] = tws
            seg['twd'] = twd
            seg['wind_along'] = impact['effective_wind_m_s']
            seg['gust'] = impact['gust_m_s']
            seg['headwind'] = impact['headwind_m_s']
            seg['gust_along'] = impact['gust_along_m_s']
            seg['crosswind'] = impact['crosswind_m_s']
            seg['is_headwind'] = impact['is_headwind']

            dist = seg['distance']
            ts = (seg['gpxtime_end'] - seg['gpxtime_start']).total_seconds()
            
            # When using GPX timestamps, calculate speed from actual time and distance
            v_seg = dist / ts if ts > 0 else 0.0
            seg['speed_m_s'] = v_seg
            seg['time_s'] = ts
            
            # ===== APPROCHE 1 : ENRICHISSEMENT AVEC DÉNIVELÉ VIRTUEL =====
            # Conserver les timestamps GPX, mais calculer slope_wind et puissance adaptée
            
            # Récupérer ou calculer la densité de l'air selon l'altitude
            if rho_forced is not None:
                rho_segment = rho_forced
                seg['rho'] = rho_forced
                seg['rho_forced'] = True
            elif 'ele1' in seg and 'ele2' in seg:
                altitude = (seg['ele1'] + seg['ele2']) / 2.0
                rho_segment = calculate_air_density(altitude)
                seg['rho'] = rho_segment
                seg['altitude_m'] = altitude
            else:
                rho_segment = RHO_STD
                seg['rho'] = RHO_STD
            
            # Récupérer la pente du terrain
            slope_terrain = seg.get('slope', 0.0)
            seg['slope_terrain'] = slope_terrain  # S'assurer que c'est renseigné
            
            # Calculer le dénivelé virtuel dû au vent
            wind_al = seg['wind_along']
            slope_wind = calculate_wind_equivalent_slope(
                v=v_seg,
                wind_along=wind_al,
                CdA=CdA,
                m=m,
                rho=rho_segment,
                g=g
            )
            
            # Pente effective = terrain + effet vent
            slope_effective = slope_terrain + slope_wind
            
            # Stocker pour visualisation et diagnostic
            seg['slope_wind'] = slope_wind
            seg['slope_effective'] = slope_effective
            seg['elevation_virtual_m'] = dist * slope_wind  # Dénivelé virtuel sur ce segment
            
            # Calculer la puissance PHYSIQUE nécessaire pour maintenir v_seg
            # Basée sur la vitesse réelle GPX (pas de modèle comportemental)
            # Utilisable pour comparaison avec puissance Strava
            v_rel = v_seg + wind_al
            if v_rel < 0:
                v_rel = 0
            CdA_eff = CdA
            if use_yaw_cdA:
                yaw = abs((seg['twd'] - seg['bearing'] + 180) % 360 - 180)
                CdA_eff = CdA_with_yaw(CdA, yaw, yaw_k)

            F_aero = 0.5 * rho_segment * CdA_eff * v_rel * v_rel
            F_roll = Cr * m * g
            F_grav = m * g * slope_terrain  # Pente réelle uniquement (pas effective, évite double comptage)
            
            # ===== CALCUL DYNAMIQUE DE LA PUISSANCE (avec inertie) =====
            # Formule physique complète : P = (ΔE_cinétique + Travail_forces) / Δt
            
            # LISSAGE DES VITESSES pour filtrer le bruit GPS
            # Le bruit GPS (±1-2 km/h) crée des ΔE_cinétiques artificiels énormes
            # Moyenne glissante sur fenêtre de 5 segments = filtre passe-bas
            window_size = 5
            half_window = window_size // 2
            
            # Collecter les vitesses dans la fenêtre [i-half_window : i] (PASSÉ uniquement)
            # On ne peut pas lire le futur (segments pas encore traités)
            v_window = []
            for j in range(max(0, i - window_size + 1), i + 1):
                v_j = segments[j].get('speed_m_s', None)
                if v_j is not None and v_j > 0.01:  # Exclure segments arrêtés
                    v_window.append(v_j)
            
            # Vitesse lissée = moyenne de la fenêtre
            if v_window:
                v_seg_smoothed = sum(v_window) / len(v_window)
            else:
                v_seg_smoothed = v_seg
            
            seg['speed_m_s_smoothed'] = v_seg_smoothed  # Pour diagnostic
            
            # 1. Variation d'énergie cinétique entre ce segment et le précédent (VITESSES LISSÉES)
            if i > 0 and segments[i-1].get('speed_m_s', 0) > 0.01:
                # Lisser aussi la vitesse du segment précédent (fenêtre passée uniquement)
                v_prev_window = []
                for j in range(max(0, i-1 - window_size + 1), i):
                    v_j = segments[j].get('speed_m_s', None)
                    if v_j is not None and v_j > 0.01:
                        v_prev_window.append(v_j)
                
                if v_prev_window:
                    v_prev_seg_smoothed = sum(v_prev_window) / len(v_prev_window)
                else:
                    v_prev_seg_smoothed = segments[i-1]['speed_m_s']
                
                delta_E_kinetic_raw = 0.5 * m * (v_seg_smoothed**2 - v_prev_seg_smoothed**2)
                
                # PLAFONNEMENT INTELLIGENT : limiter l'accélération à une puissance musculaire réaliste
                # Un cycliste peut fournir ~400W pour accélérer, mais pas instantanément des kW
                max_accel_power = 500.0  # W - puissance d'accélération musculaire max (augmenté pour sprints)
                max_delta_E = max_accel_power * ts if ts > 0 else 0.0
                
                # Plafonner mais permettre décélération libre (freinage peut être fort)
                if delta_E_kinetic_raw > max_delta_E:
                    delta_E_kinetic = max_delta_E
                    seg['kinetic_capped'] = True
                    seg['kinetic_raw'] = delta_E_kinetic_raw
                elif delta_E_kinetic_raw < -max_delta_E * 2:  # Décélération : plafond plus large (freinage)
                    delta_E_kinetic = -max_delta_E * 2
                    seg['kinetic_capped'] = True
                    seg['kinetic_raw'] = delta_E_kinetic_raw
                else:
                    delta_E_kinetic = delta_E_kinetic_raw
                    seg['kinetic_capped'] = False
            else:
                # Premier segment ou segment précédent arrêté : vitesse initiale inconnue
                delta_E_kinetic = 0.0
                seg['kinetic_capped'] = False
            
            # 2. Travail des forces dissipatives sur la distance
            W_aero = F_aero * dist    # Travail contre résistance aéro
            W_roll = F_roll * dist    # Travail contre roulement
            W_grav = F_grav * dist    # Travail contre gravité (négatif en descente)
            
            # 3. Puissance = Énergie totale / temps
            # En descente avec forte vitesse : delta_E_kinetic > 0 (accélération par gravité)
            # La puissance peut être négative (freinage) ou faible (roue libre)
            if ts > 0:
                P_dynamic = (delta_E_kinetic + W_aero + W_roll + W_grav) / ts
                # PLAFOND ADAPTATIF selon le contexte
                # En descente forte : accélération naturelle par gravité → plafond élevé
                # Sur plat/montée : accélération = effort musculaire → plafond strict
                if slope_terrain < -0.03 and delta_E_kinetic > 0:
                    # Descente > 3% avec accélération : gravité aide
                    P_max = 500.0  # Sprint + inertie
                elif delta_E_kinetic > 0:
                    # Plat/montée avec accélération : effort musculaire pur
                    P_max = 400.0  # Sprint réaliste
                else:
                    # Décélération ou vitesse stable : pas de plafond strict
                    P_max = 800.0  # Large pour éviter faux positifs
                if P_dynamic > P_max:
                    seg['power'] = P_max
                    seg['power_capped'] = True
                    seg['power_raw'] = P_dynamic              
                elif P_dynamic < -200.0:
                    # Freinage très fort (acceptable en descente)
                    seg['power'] = P_dynamic
                    seg['power_capped'] = False              
                else:
                    seg['power'] = P_dynamic
                    seg['power_capped'] = False
            else:
                P_dynamic = 0.0
                seg['power'] = 0.0
                seg['power_capped'] = False
            
            # Stocker la puissance dynamique (peut être négative = freinage)
            seg['delta_E_kinetic'] = delta_E_kinetic  # Pour diagnostic
            
            # Diagnostic : identifier les cas de freinage (puissance négative)
            P_val = seg['power']
            if P_val < 0:
                seg['power_negative'] = True
                seg['power_mode'] = 'braking'
            elif P_val < 50 and slope_terrain < -0.02:
                seg['power_mode'] = 'coasting'  # Roue libre en descente
            else:
                seg['power_negative'] = False
                seg['power_mode'] = 'pedaling'
            
            
        total_dist = sum(seg['distance'] for seg in segments)
        # Calculer le temps total en sommant les durées individuelles de chaque segment
        # (évite de compter les "trous" si des segments ont été supprimés en amont)
        total_time_s = sum(seg['time_s'] for seg in segments if seg['time_s'] not in (None, float('inf')))
       # avg_kmh = (total_dist / total_time_s)*3.6 if total_time_s>0 else 0
        
        # Calcul de la puissance moyenne pondérée par le temps
        # IMPORTANT: Exclure les pauses (vitesse < 1 m/s = 3.6 km/h) du calcul de puissance et de vitesse moyenne 
        # car use_gpx_timestamps inclut les temps d'arrêt dans les segments
        moving_threshold = 1.0  # m/s
        total_power_time = sum(seg.get('power', P0) * seg['time_s'] 
                               for seg in segments 
                               if seg['time_s'] not in (None, float('inf')) and seg['speed_m_s'] >= moving_threshold)
        moving_time = sum(seg['time_s'] 
                         for seg in segments 
                         if seg['time_s'] not in (None, float('inf')) and seg['speed_m_s'] >= moving_threshold)
        avg_kmh = (total_dist / moving_time)*3.6 if moving_time>0 else 0
    
        avg_power = (total_power_time / moving_time)  if moving_time > 0 else P0

        
        # CALIBRATION OPTIONNELLE de P0 selon profil comportemental
        if calibrate_p0:
            logging.info("\n🔧 Calibration P0 depuis puissance observée...")
            P0_calibrated  = calibrate_P0_from_observed_power(
                segments, 
                avg_power,
                behavior=behavior
            )
            P0 = P0_calibrated
        
            logging.warning(f"✅ P0 calibré: {P0:.1f}W (reproduit {avg_power:.1f}W observés)")
        
        assert P0 is not None
        return segments, avg_kmh, P0, avg_power, t_start_extracted

    # -------------------------------------------------
    # Cas normal : simulation itérative (passes)
    # -------------------------------------------------
    
    # En mode simulation, t_start est obligatoire
    if t_start is None:
        raise ValueError(
            "Simulation mode (use_gpx_timestamps=False) requires t_start parameter. "
            "Provide the start time for the simulation."
        )
    t_start_extracted = t_start
    
    # Validation obligatoire de P0 ou v0 pour le mode simulation
    if P0 is None:
        if v0 is None:
            raise ValueError("Mode simulation: fournir v0 (m/s) ou P0 (W)")
        P0 = estimate_P0_from_v0(v0, CdA=CdA, Cr=Cr, m=m, rho=rho_forced if rho_forced is not None else RHO_STD, g=g)
    assert P0 is not None
    
    logging.info(f"Using CYCLIST BEHAVIOR: {behavior.mode_uphill}/{behavior.mode_downhill}/{behavior.mode_corner} (P0={P0:.1f} W, dynamic={use_dynamic})")
    
    for seg in segments:
        if seg['tws'] is None:
            lat_m = 0.5*(seg['lat1'] + seg['lat2'])
            lon_m = 0.5*(seg['lon1'] + seg['lon2'])
            if grib is None:
                impact = {
                    'tws_m_s': 0.0,
                    'twd_deg': 0.0,
                    'gust_m_s': 0.0,
                    'headwind_m_s': 0.0,
                    'gust_along_m_s': 0.0,
                    'effective_wind_m_s': 0.0,
                    'crosswind_m_s': 0.0,
                    'is_headwind': False
                }
            else:
                rugosite_seg = _resolve_segment_roughness(seg, lat_m, lon_m)
                impact=grib.calculate_cycling_wind_impact(
                    t_start,
                    lat_m,
                    lon_m,
                    seg['bearing'],
                    ratio_wind=ratio_wind,
                    rugosite=rugosite_seg,
                )
                if impact is None:
                    raise ValueError(f"Wind impact calculation failed at time {t_start}, lat {lat_m}, lon {lon_m}")
            tws, twd = impact['tws_m_s'], impact['twd_deg']
            if tws is None:
                logging.debug("tws is None, defaulting to calm wind")
                tws, twd = 0.0, 0.0
            seg['tws'] = tws
            seg['twd'] = twd
            seg['wind_along'] = impact['effective_wind_m_s']
            seg['gust'] = impact['gust_m_s']
            seg['headwind'] = impact['headwind_m_s']
            seg['gust_along'] = impact['gust_along_m_s']
            seg['crosswind'] = impact['crosswind_m_s']
            seg['is_headwind'] = impact['is_headwind']

    for it in range(passes):
        cum = 0.0
        v_prev = None  # Vitesse du segment précédent
        bearing_prev = None  # Direction du segment précédent
        
        for i, seg in enumerate(segments):
            dist = seg['distance']
            slope_terrain = seg['slope']
            wind_al = seg['wind_along']
            
            # Calculer la densité de l'air selon l'altitude du segment
            # Si rho_forced est fourni, utiliser toujours cette valeur (ignore les altitudes GPX)
            # Sinon, calculer depuis les altitudes GPX si disponibles
            if rho_forced is not None:
                # Force le rho fourni (pour tests d'impact altitude)
                rho_segment = rho_forced
                seg['rho'] = rho_forced
                seg['rho_forced'] = True  # Marquer pour diagnostic
            elif 'ele1' in seg and 'ele2' in seg:
                # Altitude moyenne du segment
                altitude = (seg['ele1'] + seg['ele2']) / 2.0
                rho_segment = calculate_air_density(altitude)
                seg['rho'] = rho_segment
                seg['altitude_m'] = altitude  # Stocker pour diagnostic
            else:
                # Pas d'altitude : utiliser le rho standard
                rho_segment = RHO_STD
                seg['rho'] = RHO_STD
            
            # Calculer le changement de direction (virage)
            bearing_change = 0.0
            if bearing_prev is not None:
                bearing_diff = abs(seg['bearing'] - bearing_prev)
                # Normaliser l'angle entre 0 et 180°
                bearing_change = min(bearing_diff, 360 - bearing_diff)
            bearing_prev = seg['bearing']
            
            # Ajuster v_max en fonction du virage (tous les contextes : montée, plat, descente)
            v_max_segment = v_max
            if limit_speed_in_corners and bearing_change > 5:  # Tout virage > 5°
                v_max_segment = calculate_corner_speed_limit(bearing_change, behavior)
                seg['corner_limit'] = v_max_segment  # Pour le diagnostic
                
                # En descente SUPPLÉMENTAIRE : appliquer une réduction de sécurité additionnelle
                if slope_terrain < -0.01:  # Descente (< -1% de pente)
                    v_max_segment *= behavior.downhill_corner_safety_factor
                    seg['corner_limit_downhill_adjusted'] = v_max_segment
            else:
                seg['corner_limit'] = v_max
            
            # Calculer la pente virtuelle due au vent (nécessite une estimation de vitesse)
            # Pour le calcul de slope_wind, utiliser soit la vitesse du segment précédent,
            # soit une vitesse typique (~8 m/s = 29 km/h) pour le premier segment
            if v_prev is None:
                v_estimate = 8.0  # m/s (~29 km/h) - vitesse moyenne typique pour estimation
            else:
                v_estimate = v_prev  # Utiliser la vitesse réelle du segment précédent
            
            # Calculer la pente virtuelle due au vent
            slope_wind = calculate_wind_equivalent_slope(
                v=v_estimate,
                wind_along=wind_al,
                CdA=CdA_eff if 'CdA_eff' in locals() else CdA,
                m=m,
                rho=rho_segment,
                g=g
            )
            
            # Pente effective = terrain + effet vent
            slope_effective = slope_terrain + slope_wind
            
            # Stocker pour visualisation et diagnostic
            seg['slope_terrain'] = slope_terrain
            seg['slope_wind'] = slope_wind
            seg['slope_effective'] = slope_effective
            
            # Calculer l'élévation virtuelle (pour visualisation sur profil)
            # elevation_virtual = distance × slope_wind
            seg['elevation_virtual_m'] = dist * slope_wind
            
            # Ajuster la puissance selon la pente EFFECTIVE (terrain + vent)
            P_segment = calculate_adaptive_power(P0, slope_effective, behavior)

            CdA_eff = CdA
            if use_yaw_cdA:
                yaw = abs((seg['twd'] - seg['bearing'] + 180) % 360 - 180)
                CdA_eff = CdA_with_yaw(CdA, yaw, yaw_k)

            if use_dynamic:
                # Simulation dynamique avec inertie
                if v_prev is None:
                    # Premier segment : démarrer à vitesse très faible (~0.2 m/s) pour modéliser l'accélération initiale
                    v_initial = 0.2  # m/s (~0.7 km/h)
                else:
                    # Segments suivants : partir de la vitesse finale du segment précédent
                    v_initial = v_prev
                
                v_final, v_avg, t_seg = solve_speed_dynamic(
                    P_segment, CdA_eff, Cr, m, slope_effective, 0.0, v_initial, dist, rho_segment, g, v_max_segment, behavior=behavior
                )
                
                seg['speed_m_s'] = v_avg  # Vitesse moyenne pour ce segment
                seg['v_initial'] = v_initial  # Vitesse en début de segment
                seg['v_final'] = v_final  # Vitesse en fin de segment
                seg['time_s'] = t_seg
                seg['power'] = P_segment  # Stocker la puissance utilisée
                v_prev = v_final  # Propager pour le prochain segment
            else:
                # Ancienne méthode : vitesse d'équilibre sans inertie
                v_seg = solve_speed_for_power(P_segment, CdA_eff, Cr, m, slope_effective, 0.0, rho_segment, g, v_max_segment, behavior=behavior)
                t_seg = dist / v_seg if v_seg > 1e-6 else float('inf')
                seg['speed_m_s'] = v_seg
                seg['time_s'] = t_seg
                seg['power'] = P_segment  # Stocker la puissance utilisée
                v_prev = v_seg
            
            seg['cum_t_start'] = cum
            seg['cum_t_end'] = cum + t_seg
            cum += t_seg

        if it == passes - 1:
            break

        for seg in segments:
            t_mid = t_start + timedelta(seconds=(seg['cum_t_start'] + seg['cum_t_end'])/2)
            lat_m = 0.5*(seg['lat1'] + seg['lat2'])
            lon_m = 0.5*(seg['lon1'] + seg['lon2'])
            if grib is None:
                impact = {
                    'tws_m_s': 0.0,
                    'twd_deg': 0.0,
                    'gust_m_s': 0.0,
                    'headwind_m_s': 0.0,
                    'gust_along_m_s': 0.0,
                    'effective_wind_m_s': 0.0,
                    'crosswind_m_s': 0.0,
                    'is_headwind': False
                }
            else:
                rugosite_seg = _resolve_segment_roughness(seg, lat_m, lon_m)
                impact=grib.calculate_cycling_wind_impact(
                    t_mid,
                    lat_m,
                    lon_m,
                    seg['bearing'],
                    ratio_wind=ratio_wind,
                    rugosite=rugosite_seg,
                )
                if impact is None:
                    raise ValueError(f"Wind impact calculation failed at time {t_mid}, lat {lat_m}, lon {lon_m}")
            tws, twd = impact['tws_m_s'], impact['twd_deg']
            if tws is None:
                tws, twd = 0.0, 0.0
            if abs(tws) > clip_wind:
                tws = max(min(tws, clip_wind), -clip_wind)
            seg['tws'] = tws
            seg['twd'] = twd
            seg['wind_along'] = impact['effective_wind_m_s']
            seg['gust'] = impact['gust_m_s']
            seg['headwind'] = impact['headwind_m_s']
            seg['gust_along'] = impact['gust_along_m_s']
            seg['crosswind'] = impact['crosswind_m_s']
            seg['is_headwind'] = impact['is_headwind']

    total_dist = sum(seg['distance'] for seg in segments)
    total_time = sum(seg['time_s'] for seg in segments if seg['time_s'] not in (None, float('inf')))
    avg_kmh = (total_dist/total_time)*3.6 if total_time>0 else 0
    
    # Calcul de la puissance moyenne pondérée par le temps
    total_power_time = sum(seg.get('power', P0) * seg['time_s'] 
                           for seg in segments 
                           if seg['time_s'] not in (None, float('inf')))
    avg_power = total_power_time / total_time if total_time > 0 else P0

    assert P0 is not None
    return segments, avg_kmh, P0, avg_power, t_start_extracted


# -------------------------------------------------
# Interfaces publiques stables (wrappers)
# -------------------------------------------------
def simulate_future_route(segments_in: List[Dict],
                          grib,
                          t_start,
                          v0: Optional[float] = None,
                          P0: Optional[float] = None,
                          passes: int = 2,
                          CdA: float = 0.5,
                          Cr: float = 0.004,
                          m: float = 75.0,
                          g: float = G,
                          clip_wind: float = 40.0,
                          use_yaw_cdA: bool = True,
                          ratio_wind: float = 0.25,
                          yaw_k: float = 0.02,
                          v_max: float = 22.0,
                          use_dynamic: bool = True,
                          limit_speed_in_corners: bool = True,
                          rho_forced: Optional[float] = None,
                          behavior: Optional[CyclistBehavior] = None) -> Tuple[List[Dict], float, float, float, datetime]:
    """
    Simulation prospective (parcours futur) : calcule vitesses et puissances
    à partir d'un P0/v0 sans utiliser les timestamps GPX.
    
    Parameters:
    -----------
    t_start : datetime, required
        Start time for the simulation (mandatory in future simulation mode).
    
    Returns:
    --------
    Tuple[List[Dict], float, float, float, datetime]:
        - segments, avg_kmh, P0, avg_power, t_start
    """
    return simulate_with_weather(
        segments_in,
        grib,
        t_start,
        v0=v0,
        P0=P0,
        passes=passes,
        use_gpx_timestamps=False,
        calibrate_p0=False,
        CdA=CdA,
        Cr=Cr,
        m=m,
        g=g,
        clip_wind=clip_wind,
        use_yaw_cdA=use_yaw_cdA,
        ratio_wind=ratio_wind,
        yaw_k=yaw_k,
        v_max=v_max,
        use_dynamic=use_dynamic,
        limit_speed_in_corners=limit_speed_in_corners,
        rho_forced=rho_forced,
        behavior=behavior,
    )


def simulate_replay_route(segments_in: List[Dict],
                          grib,
                          t_start=None,
                          P0: Optional[float] = None,
                          passes: int = 2,
                          CdA: float = 0.5,
                          Cr: float = 0.004,
                          m: float = 75.0,
                          g: float = G,
                          clip_wind: float = 40.0,
                          use_yaw_cdA: bool = True,
                          ratio_wind: float = 0.25,
                          yaw_k: float = 0.02,
                          v_max: float = 22.0,
                          limit_speed_in_corners: bool = True,
                          rho_forced: Optional[float] = None,
                          behavior: Optional[CyclistBehavior] = None) -> Tuple[List[Dict], float, float, float, datetime]:
    """
    Rejeu (post-ride) : utilise les timestamps GPX pour calculer puissances
    depuis les vitesses observées. P0 est automatiquement calibré depuis les données réelles.
    
    Parameters:
    -----------
    t_start : datetime, optional
        Start time. If None, will be auto-extracted from first segment's gpxtime_start.
        GPX segments must contain timestamps (gpxtime_start, gpxtime_end).
    P0 : Optional[float]
        Ignored in replay mode. P0 is always auto-calibrated from observed power.
        Kept for API compatibility but has no effect.
    
    Returns:
    --------
    Tuple[List[Dict], float, float, float, datetime]:
        - segments: processed segments with calculated data
        - avg_kmh: average speed in km/h
        - P0: calibrated reference power (W) matching observed performance
        - avg_power: average power weighted by time (W)
        - t_start_extracted: start time from GPX or provided parameter
    """
    return simulate_with_weather(
        segments_in,
        grib,
        t_start,
        v0=None,
        P0=P0,
        passes=passes,
        use_gpx_timestamps=True,
        calibrate_p0=True,  # Always calibrate P0 in replay mode
        CdA=CdA,
        Cr=Cr,
        m=m,
        g=g,
        clip_wind=clip_wind,
        use_yaw_cdA=use_yaw_cdA,
        ratio_wind=ratio_wind,
        yaw_k=yaw_k,
        v_max=v_max,
        use_dynamic=True,
        limit_speed_in_corners=limit_speed_in_corners,
        rho_forced=rho_forced,
        behavior=behavior,
    )