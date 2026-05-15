# -*- coding: utf-8 -*-
"""
Analyse tactique pour cyclisme de compétition
Module optionnel - n'impacte pas les simulations standards

Usage:
    from biwipy.analysis.tactical_analysis import (
        analyze_echelon_opportunities,
        print_echelon_report,
    )
    
    zones = analyze_echelon_opportunities(results)
    print_echelon_report(zones)
"""

from typing import List, Dict, Tuple
import locale
import os


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
    "title": {
        "fr": "  🌪️  ANALYSE TACTIQUE - OPPORTUNITES DE BORDURES",
        "en": "  🌪️  TACTICAL ANALYSIS - ECHELON OPPORTUNITIES",
    },
    "no_zones": {
        "fr": "\n✅ Pas de zones de bordures detectees avec les criteres actuels",
        "en": "\n✅ No echelon zones detected with current criteria",
    },
    "summary": {"fr": "\n📊 Resume :", "en": "\n📊 Summary:"},
    "high_count": {"fr": "   • {count} zone(s) a HAUT RISQUE", "en": "   • {count} HIGH-RISK zone(s)"},
    "medium_count": {"fr": "   • {count} zone(s) a RISQUE MODERE", "en": "   • {count} MEDIUM-RISK zone(s)"},
    "total_exposed": {"fr": "   • Total : {km:.1f} km de route exposee", "en": "   • Total: {km:.1f} km of exposed road"},
    "critical_title": {"fr": "\n⚠️  ZONES CRITIQUES (Haut Risque) :", "en": "\n⚠️  CRITICAL ZONES (High Risk):"},
    "critical_line": {"fr": "  Km {start:5.1f} - {end:5.1f} ({dist:.1f} km)", "en": "  Km {start:5.1f} - {end:5.1f} ({dist:.1f} km)"},
    "crosswind": {"fr": "     -> Crosswind : {value:.0f} km/h", "en": "     -> Crosswind: {value:.0f} km/h"},
    "directions": {"fr": "     -> Direction route : {bearing:.0f} deg | Vent : {wind:.0f} deg", "en": "     -> Route direction: {bearing:.0f} deg | Wind: {wind:.0f} deg"},
    "long_zone": {"fr": "     -> Zone longue : {count} segments consecutifs", "en": "     -> Long zone: {count} consecutive segments"},
    "watch_title": {"fr": "\n⚡ ZONES A SURVEILLER (Risque Modere) :", "en": "\n⚡ ZONES TO WATCH (Moderate Risk):"},
    "watch_line": {"fr": "  Km {start:5.1f} - {end:5.1f} : Crosswind {wind:.0f} km/h", "en": "  Km {start:5.1f} - {end:5.1f}: Crosswind {wind:.0f} km/h"},
    "advice_title": {"fr": "\n💡 Recommandations tactiques :", "en": "\n💡 Tactical recommendations:"},
    "advice_head": {"fr": "  • Km {km:.0f} : Placer equipe en tete AVANT cette zone", "en": "  • Km {km:.0f}: Move team to the front BEFORE this zone"},
    "advice_accel": {"fr": "  • Acceleration probable des favoris dans ces sections", "en": "  • Likely acceleration from favorites in these sections"},
    "advice_split": {"fr": "  • Risque de division du peloton en echelons", "en": "  • Risk of peloton splits into echelons"},
    "advice_watch": {"fr": "  • Rester vigilant dans les zones moderees", "en": "  • Stay alert in moderate-risk zones"},
    "advice_save": {"fr": "  • Economiser l'energie pour les zones critiques", "en": "  • Save energy for critical zones"},
    "sep80_open": {"fr": "\n================================================================================", "en": "\n================================================================================"},
    "sep80": {"fr": "================================================================================", "en": "================================================================================"},
    "sep80_close": {"fr": "================================================================================\n", "en": "================================================================================\n"},
    "dash80": {"fr": "--------------------------------------------------------------------------------", "en": "--------------------------------------------------------------------------------"},
    "blank": {"fr": "", "en": ""},
    "no_wind_data": {"fr": "Pas de donnees de vent", "en": "No wind data available"},
    "risk_high_assured": {
        "fr": "⚠️ BORDURE ASSUREE ! Vent de cote {wind:.0f} km/h sur {km:.1f} km",
        "en": "⚠️ ECHELON GUARANTEED! Crosswind {wind:.0f} km/h over {km:.1f} km",
    },
    "risk_high": {
        "fr": "⚠️ Fort risque bordure - Crosswind {wind:.0f} km/h",
        "en": "⚠️ High echelon risk - Crosswind {wind:.0f} km/h",
    },
    "risk_medium_attention": {
        "fr": "⚡ Attention crosswind {wind:.0f} km/h",
        "en": "⚡ Watch crosswind {wind:.0f} km/h",
    },
    "risk_medium": {
        "fr": "⚡ Crosswind modere {wind:.0f} km/h",
        "en": "⚡ Moderate crosswind {wind:.0f} km/h",
    },
    "risk_low": {
        "fr": "Vent de cote faible ({wind:.0f} km/h)",
        "en": "Light crosswind ({wind:.0f} km/h)",
    },
}


def _t(key: str, **kwargs) -> str:
    lang = _detect_output_lang()
    labels = _I18N.get(key, {})
    template = labels.get(lang) or labels.get("en") or key
    return template.format(**kwargs) if kwargs else template


def _tp(key: str, **kwargs) -> None:
    print(_t(key, **kwargs))


def analyze_echelon_risk(segment: Dict, 
                         min_crosswind_kmh: float = 20.0,
                         min_distance_m: float = 1000.0) -> Tuple[str, str]:
    """
    Évalue le risque de bordure/échelon pour un segment.
    
    Parameters:
    -----------
    segment : dict
        Segment avec 'crosswind' (m/s), 'distance' (m), etc.
    min_crosswind_kmh : float
        Vent de côté minimum pour risque (km/h)
    min_distance_m : float
        Distance minimum de la zone exposée (m)
    
    Returns:
    --------
    tuple: (risk_level, description)
        risk_level : 'HIGH', 'MEDIUM', 'LOW'
        description : Message descriptif
    """
    if 'crosswind' not in segment:
        return 'UNKNOWN', _t("no_wind_data")
    
    crosswind_kmh = abs(segment['crosswind']) * 3.6
    distance = segment.get('distance', 0)
    
    # Critères de bordure
    if crosswind_kmh >= 30 and distance >= min_distance_m:
        return 'HIGH', _t("risk_high_assured", wind=crosswind_kmh, km=distance/1000)
    elif crosswind_kmh >= 25 and distance >= min_distance_m:
        return 'HIGH', _t("risk_high", wind=crosswind_kmh)
    elif crosswind_kmh >= 20 and distance >= min_distance_m:
        return 'MEDIUM', _t("risk_medium_attention", wind=crosswind_kmh)
    elif crosswind_kmh >= 15 and distance >= 500:
        return 'MEDIUM', _t("risk_medium", wind=crosswind_kmh)
    else:
        return 'LOW', _t("risk_low", wind=crosswind_kmh)


def analyze_echelon_opportunities(segments: List[Dict],
                                   min_crosswind_kmh: float = 20.0,
                                   min_distance_m: float = 1000.0) -> List[Dict]:
    """
    Analyse tous les segments et identifie les zones de bordures potentielles.
    
    Parameters:
    -----------
    segments : list
        Liste des segments simulés avec données de vent
    min_crosswind_kmh : float
        Seuil de vent de côté (km/h)
    min_distance_m : float
        Distance minimum de la zone exposée (m)
    
    Returns:
    --------
    list : Liste des zones à risque avec leurs caractéristiques
    """
    zones = []
    cum_distance = 0
    
    for i, seg in enumerate(segments):
        cum_distance += seg['distance']
        risk, msg = analyze_echelon_risk(seg, min_crosswind_kmh, min_distance_m)
        
        if risk in ['HIGH', 'MEDIUM']:
            zone = {
                'segment_id': i,
                'km': cum_distance / 1000,
                'km_start': (cum_distance - seg['distance']) / 1000,
                'km_end': cum_distance / 1000,
                'risk': risk,
                'message': msg,
                'crosswind_kmh': abs(seg['crosswind']) * 3.6,
                'headwind_kmh': seg.get('headwind', 0) * 3.6,
                'bearing': seg['bearing'],
                'wind_direction': seg.get('twd', 0),
                'distance_m': seg['distance']
            }
            zones.append(zone)
    
    return zones


def merge_adjacent_zones(zones: List[Dict], max_gap_km: float = 2.0) -> List[Dict]:
    """
    Fusionne les zones adjacentes pour identifier les longues sections exposées.
    
    Parameters:
    -----------
    zones : list
        Zones de risque individuelles
    max_gap_km : float
        Distance max entre zones pour les fusionner (km)
    
    Returns:
    --------
    list : Zones fusionnées
    """
    if not zones:
        return []
    
    merged = []
    current = zones[0].copy()
    current['segments'] = 1
    
    for zone in zones[1:]:
        gap = zone['km_start'] - current['km_end']
        
        if gap <= max_gap_km and zone['risk'] == current['risk']:
            # Fusionner
            current['km_end'] = zone['km_end']
            current['distance_m'] += zone['distance_m']
            current['segments'] += 1
            current['crosswind_kmh'] = max(current['crosswind_kmh'], zone['crosswind_kmh'])
        else:
            # Nouvelle zone
            merged.append(current)
            current = zone.copy()
            current['segments'] = 1
    
    merged.append(current)
    return merged


def print_echelon_report(zones: List[Dict], merge_zones: bool = True):
    """
    Affiche un rapport tactique des zones de bordures.
    
    Parameters:
    -----------
    zones : list
        Zones de risque identifiées
    merge_zones : bool
        Si True, fusionne les zones adjacentes
    """
    if merge_zones:
        zones = merge_adjacent_zones(zones)

    _tp("sep80_open")
    _tp("title")
    _tp("sep80")

    if not zones:
        _tp("no_zones")
        _tp("sep80_close")
        return

    high_risk = [z for z in zones if z['risk'] == 'HIGH']
    medium_risk = [z for z in zones if z['risk'] == 'MEDIUM']

    _tp("summary")
    _tp("high_count", count=len(high_risk))
    _tp("medium_count", count=len(medium_risk))
    _tp("total_exposed", km=sum(z['distance_m'] for z in zones)/1000)

    if high_risk:
        _tp("critical_title")
        _tp("dash80")
        for zone in high_risk:
            _tp("critical_line", start=zone['km_start'], end=zone['km_end'], dist=zone['distance_m']/1000)
            _tp("crosswind", value=zone['crosswind_kmh'])
            _tp("directions", bearing=zone['bearing'], wind=zone['wind_direction'])
            if merge_zones and zone.get('segments', 1) > 1:
                _tp("long_zone", count=zone['segments'])
            _tp("blank")

    if medium_risk:
        _tp("watch_title")
        _tp("dash80")
        for zone in medium_risk:
            _tp("watch_line", start=zone['km_start'], end=zone['km_end'], wind=zone['crosswind_kmh'])

    _tp("advice_title")
    _tp("dash80")
    if high_risk:
        first_critical = high_risk[0]
        _tp("advice_head", km=first_critical['km_start'])
        _tp("advice_accel")
        _tp("advice_split")
    if medium_risk:
        _tp("advice_watch")
        _tp("advice_save")

    _tp("sep80_close")


def export_echelon_zones_gpx(zones: List[Dict], output_file: str):
    """
    Export echelon zones to GPX for visualization.
    (Stub function - implement if needed)
    """
    # TODO: Générer un fichier GPX avec waypoints pour chaque zone critique
    pass
