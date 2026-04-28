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
        return 'UNKNOWN', "Pas de données de vent"
    
    crosswind_kmh = abs(segment['crosswind']) * 3.6
    distance = segment.get('distance', 0)
    
    # Critères de bordure
    if crosswind_kmh >= 30 and distance >= min_distance_m:
        return 'HIGH', f"⚠️ BORDURE ASSURÉE ! Vent de côté {crosswind_kmh:.0f} km/h sur {distance/1000:.1f} km"
    elif crosswind_kmh >= 25 and distance >= min_distance_m:
        return 'HIGH', f"⚠️ Fort risque bordure - Crosswind {crosswind_kmh:.0f} km/h"
    elif crosswind_kmh >= 20 and distance >= min_distance_m:
        return 'MEDIUM', f"⚡ Attention crosswind {crosswind_kmh:.0f} km/h"
    elif crosswind_kmh >= 15 and distance >= 500:
        return 'MEDIUM', f"⚡ Crosswind modéré {crosswind_kmh:.0f} km/h"
    else:
        return 'LOW', f"Vent de côté faible ({crosswind_kmh:.0f} km/h)"


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
    
    print("\n" + "="*80)
    print("  🌪️  ANALYSE TACTIQUE - OPPORTUNITÉS DE BORDURES")
    print("="*80)
    
    if not zones:
        print("\n✅ Pas de zones de bordures détectées avec les critères actuels")
        print("="*80 + "\n")
        return
    
    high_risk = [z for z in zones if z['risk'] == 'HIGH']
    medium_risk = [z for z in zones if z['risk'] == 'MEDIUM']
    
    print(f"\n📊 Résumé :")
    print(f"   • {len(high_risk)} zone(s) à HAUT RISQUE")
    print(f"   • {len(medium_risk)} zone(s) à RISQUE MODÉRÉ")
    print(f"   • Total : {sum(z['distance_m'] for z in zones)/1000:.1f} km de route exposée")
    
    if high_risk:
        print("\n⚠️  ZONES CRITIQUES (Haut Risque) :")
        print("-" * 80)
        for zone in high_risk:
            print(f"  Km {zone['km_start']:5.1f} - {zone['km_end']:5.1f} "
                  f"({zone['distance_m']/1000:.1f} km)")
            print(f"     → Crosswind : {zone['crosswind_kmh']:.0f} km/h")
            print(f"     → Direction route : {zone['bearing']:.0f}° | Vent : {zone['wind_direction']:.0f}°")
            if merge_zones and zone.get('segments', 1) > 1:
                print(f"     → Zone longue : {zone['segments']} segments consécutifs")
            print()
    
    if medium_risk:
        print("\n⚡ ZONES À SURVEILLER (Risque Modéré) :")
        print("-" * 80)
        for zone in medium_risk:
            print(f"  Km {zone['km_start']:5.1f} - {zone['km_end']:5.1f} : "
                  f"Crosswind {zone['crosswind_kmh']:.0f} km/h")
    
    print("\n💡 Recommandations tactiques :")
    print("-" * 80)
    if high_risk:
        first_critical = high_risk[0]
        print(f"  • Km {first_critical['km_start']:.0f} : Placer équipe en tête AVANT cette zone")
        print(f"  • Accélération probable des favoris dans ces sections")
        print(f"  • Risque de division du peloton en échelons")
    if medium_risk:
        print(f"  • Rester vigilant dans les zones modérées")
        print(f"  • Économiser l'énergie pour les zones critiques")
    
    print("="*80 + "\n")


def export_echelon_zones_gpx(zones: List[Dict], output_file: str):
    """
    Exporte les zones de bordures au format GPX pour visualisation.
    (Fonction stub - à implémenter si besoin)
    """
    # TODO: Générer un fichier GPX avec waypoints pour chaque zone critique
    pass
