# -*- coding: utf-8 -*-
"""
Analyse et visualisation des résultats de simulation avec vent
"""

import matplotlib.pyplot as plt
import numpy as np
import logging
from typing import List, Dict, Optional, Any, Tuple, cast
from copy import deepcopy
from matplotlib.projections.polar import PolarAxes


def smooth_segments(segments, window=5, keys=None):
    """
    Lisse les valeurs des segments avec une moyenne mobile.
    
    Args:
        segments: Liste des segments à lisser
        window: Taille de la fenêtre de lissage (nombre de segments, impair recommandé)
        keys: Liste des clés à lisser. Par défaut: ['speed_m_s', 'slope', 'wind_along']
    
    Returns:
        Liste des segments avec valeurs lissées (copie profonde)
    """
    if keys is None:
        keys = ['speed_m_s', 'slope', 'wind_along', 'effective_wind', 'crosswind']
    
    smoothed = deepcopy(segments)
    n = len(segments)
    half_window = window // 2
    
    for key in keys:
        # Extraire les valeurs
        values = np.array([seg.get(key, 0) for seg in segments])
        
        # Appliquer la moyenne mobile
        smoothed_values = np.copy(values)
        for i in range(n):
            start = max(0, i - half_window)
            end = min(n, i + half_window + 1)
            smoothed_values[i] = np.mean(values[start:end])
        
        # Mettre à jour les segments
        for i, seg in enumerate(smoothed):
            seg[key] = smoothed_values[i]
    
    return smoothed


def merge_short_segments(segments: List[Dict], 
                         min_distance: float = 50.0,
                         max_bearing_diff: float = 20.0,
                         max_slope_diff: float = 0.10,
                         max_slope: float = 0.15,
                         verbose: bool = True,
                         log_file: Optional[str] = None) -> Tuple[List[Dict], int]:
    """
    Regroupe intelligemment les segments courts AVANT les calculs de vent.
    Fusionne UNIQUEMENT si les critères de distance, bearing ET pente sont respectés.
    Plafonne les pentes aberrantes.
    
    Parameters:
    -----------
    segments : List[Dict]
        Liste des segments originaux (sera copiée, pas modifiée)
    min_distance : float, optional
        Distance minimale en mètres pour un segment (défaut: 50m)
    max_bearing_diff : float, optional
        Différence maximale de bearing en degrés pour permettre la fusion (défaut: 20°)
        Évite de fusionner des segments qui changent trop de direction
    max_slope_diff : float, optional
        Différence maximale de pente (ratio) pour permettre la fusion (défaut: 0.10 = 10%)
        Évite de fusionner montée et descente
    max_slope : float, optional
        Pente maximale en valeur absolue (ratio) pour plafonner les pentes aberrantes (défaut: 0.15 = 15%)
        Les pentes > max_slope seront limitées à ±max_slope
    verbose : bool, optional
        Afficher les statistiques de regroupement
        
    Returns:
    --------
    merged_segments : List[Dict]
        Nouvelle liste de segments regroupés
    n_merged : int
        Nombre de segments fusionnés
        
    Notes:
    ------
    La fusion se fait de manière séquentielle et intelligente :
    - Un segment court est candidat à la fusion
    - Il est fusionné avec le suivant SEULEMENT si bearing et pente sont similaires
    - Sinon, il est conservé tel quel (même s'il est court)
    - Cela préserve la précision du vent dans les virages
    """
    
    if not segments:
        return [], 0
    
    segments_copy = deepcopy(segments)
    merged = []
    i = 0
    n_original = len(segments_copy)
    n_merged = 0
    n_rejected = 0  # Segments courts non fusionnés (virage ou changement pente)
    n_capped = 0    # Pentes plafonnées
    
    while i < len(segments_copy):
        current = segments_copy[i]
        
        # Si c'est le dernier segment ou s'il est assez long, le garder
        if i == len(segments_copy) - 1 or current['distance'] >= min_distance:
            merged.append(current)
            i += 1
            continue
        
        # Segment trop court : essayer de fusionner avec le suivant
        next_seg = segments_copy[i + 1]
        
        # Vérifier les critères de similarité
        bearing_diff = abs(current['bearing'] - next_seg['bearing'])
        # Gérer le cas 359° vs 1° (différence de 2° pas 358°)
        if bearing_diff > 180:
            bearing_diff = 360 - bearing_diff
        
        slope_diff = abs(current['slope'] - next_seg['slope'])
        
        # Décider si on peut fusionner
        can_merge = (bearing_diff <= max_bearing_diff and slope_diff <= max_slope_diff)
        
        if not can_merge:
            # Ne pas fusionner : virage ou changement de pente important
            merged.append(current)
            n_rejected += 1
            i += 1
            continue
        
        # Fusionner les deux segments
        merged_seg = deepcopy(current)
        total_dist = current['distance'] + next_seg['distance']
        
        # Mettre à jour le point final
        merged_seg['lat2'] = next_seg['lat2']
        merged_seg['lon2'] = next_seg['lon2']
        merged_seg['ele2'] = next_seg['ele2']
        merged_seg['distance'] = total_dist
        
        # Timestamps GPX
        if 'gpxtime_end' in next_seg:
            merged_seg['gpxtime_end'] = next_seg['gpxtime_end']
        
        # Bearing moyen pondéré par les distances
        bearing_weighted = (current['bearing'] * current['distance'] + 
                          next_seg['bearing'] * next_seg['distance']) / total_dist
        merged_seg['bearing'] = bearing_weighted
        
        # Recalculer la pente globale
        delta_ele = merged_seg['ele2'] - merged_seg['ele1']
        merged_seg['slope'] = delta_ele / total_dist if total_dist > 0 else 0.0
        
        merged.append(merged_seg)
        n_merged += 1
        i += 2  # Sauter le segment fusionné
    
    # Plafonner les pentes aberrantes de tous les segments
    for seg in merged:
        if abs(seg['slope']) > max_slope:
            n_capped += 1
            seg['slope'] = max(min(seg['slope'], max_slope), -max_slope)
    
    if verbose or log_file:
        # Statistiques
        orig_distances = [s['distance'] for s in segments_copy]
        merged_distances = [s['distance'] for s in merged]
        orig_slopes = [abs(s['slope']) * 100 for s in segments_copy]
        merged_slopes = [abs(s['slope']) * 100 for s in merged]
        
        output = []
        output.append(f"\n{'='*70}")
        output.append(f"  📦 REGROUPEMENT INTELLIGENT DES SEGMENTS")
        output.append(f"{'='*70}")
        output.append(f"Critères de fusion:")
        output.append(f"  • Distance minimale: {min_distance}m")
        output.append(f"  • Différence de bearing max: {max_bearing_diff}°")
        output.append(f"  • Différence de pente max: {max_slope_diff*100:.1f}%")
        output.append(f"  • Pente maximale (plafonnement): ±{max_slope*100:.1f}%")
        output.append(f"\nRésultats:")
        output.append(f"  Segments originaux: {n_original}")
        output.append(f"  Segments après fusion: {len(merged)}")
        output.append(f"  Segments fusionnés: {n_merged}")
        output.append(f"  Segments courts conservés (virage/pente): {n_rejected}")
        output.append(f"  Pentes plafonnées (>{max_slope*100:.0f}%): {n_capped}")
        output.append(f"  Réduction: {(1 - len(merged)/n_original)*100:.1f}%")
        output.append(f"\n📏 Distance des segments:")
        output.append(f"  Avant: Min={np.min(orig_distances):.1f}m | "
              f"Moy={np.mean(orig_distances):.1f}m | "
              f"Max={np.max(orig_distances):.1f}m")
        output.append(f"  Après: Min={np.min(merged_distances):.1f}m | "
              f"Moy={np.mean(merged_distances):.1f}m | "
              f"Max={np.max(merged_distances):.1f}m")
        output.append(f"\n⛰️  Pente absolue:")
        output.append(f"  Avant: Min={np.min(orig_slopes):.1f}% | "
              f"Moy={np.mean(orig_slopes):.1f}% | "
              f"Max={np.max(orig_slopes):.1f}%")
        output.append(f"  Après: Min={np.min(merged_slopes):.1f}% | "
              f"Moy={np.mean(merged_slopes):.1f}% | "
              f"Max={np.max(merged_slopes):.1f}%")
        
        # Détail des segments courts conservés (virages)
        if n_rejected > 0:
            output.append(f"\n🔄 Segments courts NON fusionnés (virages/changement pente):")
            count = 0
            for i, seg in enumerate(segments_copy):
                if seg['distance'] < min_distance:
                    # Vérifier s'il a été conservé sans fusion
                    if i < len(segments_copy) - 1:
                        next_seg = segments_copy[i + 1]
                        bearing_diff = abs(seg['bearing'] - next_seg['bearing'])
                        if bearing_diff > 180:
                            bearing_diff = 360 - bearing_diff
                        slope_diff = abs(seg['slope'] - next_seg['slope'])
                        if bearing_diff > max_bearing_diff or slope_diff > max_slope_diff:
                            count += 1
                            output.append(f"  Seg #{i}: dist={seg['distance']:.1f}m, "
                                        f"pente={seg['slope']*100:.1f}%, bearing={seg['bearing']:.0f}° | "
                                        f"Δbearing={bearing_diff:.1f}°, Δpente={slope_diff*100:.1f}%")
                            if count >= 20:  # Limiter à 20 exemples
                                output.append(f"  ... et {n_rejected - count} autres")
                                break
        
        output.append(f"{'='*70}\n")
        
        text = "\n".join(output)
        
        if verbose:
            print(text)
        
        if log_file:
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write(text)
                f.write(f"\n\nDÉTAIL COMPLET DES SEGMENTS ORIGINAUX:\n")
                f.write("="*70 + "\n")
                for i, seg in enumerate(segments_copy):
                    f.write(f"\nSegment #{i}:\n")
                    f.write(f"  Distance: {seg['distance']:.2f}m\n")
                    f.write(f"  Bearing: {seg['bearing']:.1f}°\n")
                    f.write(f"  Pente: {seg['slope']*100:.2f}%\n")
                    f.write(f"  Alt: {seg['ele1']:.1f}m -> {seg['ele2']:.1f}m\n")
    n_merged=n_original-len(merged)
    return merged,n_merged


def detect_real_climbs(
    segments: List[Dict[str, Any]],
    slope_threshold_pct: float,
    min_distance_m: float,
) -> List[Dict[str, Any]]:
    """
    Detect climbs as contiguous segment sequences where terrain slope is above threshold.

    A climb is detected when:
    - each segment in the sequence has slope >= slope_threshold_pct
    - cumulative sequence distance >= min_distance_m

    Parameters
    ----------
    segments : List[Dict[str, Any]]
        Route segments. Uses ``slope_terrain`` when available, else ``slope``.
    slope_threshold_pct : float
        Threshold in percent (e.g. 3.0 for 3%).
    min_distance_m : float
        Minimum cumulative climb length in meters.

    Returns
    -------
    List[Dict[str, Any]]
        One dict per detected climb with:
        - start_km, end_km
        - summit_lat, summit_lon
        - avg_slope_pct
        - distance_m, elevation_gain_m
    """
    if not segments:
        return []

    threshold_ratio = float(slope_threshold_pct) / 100.0
    climbs: List[Dict[str, Any]] = []

    cum_dist_m = 0.0
    i = 0
    n = len(segments)

    while i < n:
        seg = segments[i]
        slope = float(seg.get('slope_terrain', seg.get('slope', 0.0)))

        if slope < threshold_ratio:
            cum_dist_m += float(seg.get('distance', 0.0))
            i += 1
            continue

        # Start of a candidate climb
        start_idx = i
        start_km = cum_dist_m / 1000.0

        block_dist_m = 0.0
        weighted_slope_sum = 0.0
        elev_gain_m = 0.0

        # Summit tracking using maximum end elevation within the climb block
        summit_ele = float(seg.get('ele2', seg.get('ele1', 0.0)))
        summit_lat = float(seg.get('lat2', seg.get('lat1', 0.0)))
        summit_lon = float(seg.get('lon2', seg.get('lon1', 0.0)))

        while i < n:
            s = segments[i]
            s_slope = float(s.get('slope_terrain', s.get('slope', 0.0)))
            if s_slope < threshold_ratio:
                break

            dist = float(s.get('distance', 0.0))
            block_dist_m += dist
            weighted_slope_sum += s_slope * dist

            dz = float(s.get('ele2', 0.0)) - float(s.get('ele1', 0.0))
            if dz > 0:
                elev_gain_m += dz

            ele2 = float(s.get('ele2', s.get('ele1', 0.0)))
            if ele2 >= summit_ele:
                summit_ele = ele2
                summit_lat = float(s.get('lat2', s.get('lat1', 0.0)))
                summit_lon = float(s.get('lon2', s.get('lon1', 0.0)))

            i += 1

        end_km = (cum_dist_m + block_dist_m) / 1000.0

        if block_dist_m >= float(min_distance_m):
            avg_slope_pct = (weighted_slope_sum / block_dist_m) * 100.0 if block_dist_m > 0 else 0.0
            climbs.append(
                {
                    'start_km': start_km,
                    'end_km': end_km,
                    'summit_lat': summit_lat,
                    'summit_lon': summit_lon,
                    'avg_slope_pct': avg_slope_pct,
                    'distance_m': block_dist_m,
                    'elevation_gain_m': elev_gain_m,
                    'segment_start_idx': start_idx,
                    'segment_end_idx': i - 1,
                }
            )

        cum_dist_m += block_dist_m

    return climbs


def plot_elevation_profile(segments: List[Dict],
                           figsize: tuple = (14, 6),
                           title: Optional[str] = None,
                           show_virtual: bool = True,
                           distance_from_finish: bool = False):
    """
    Trace le profil d'altitude réel et virtuel (incluant l'effet du vent).
    
    Parameters:
    -----------
    segments : List[Dict]
        Liste des segments résultats de simulate_with_weather
    figsize : tuple, optional
        Taille de la figure (largeur, hauteur)
    title : str, optional
        Titre principal du graphique
    show_virtual : bool, optional
        Si True, affiche aussi le profil d'altitude virtuel (défaut: True)
    distance_from_finish : bool, optional
        Si True, l'axe des abscisses représente la distance restante jusqu'à
        l'arrivée. Le départ apparaît alors à la distance totale du parcours,
        et l'arrivée à 0 km.
        
    Returns:
    --------
    fig : matplotlib.figure.Figure
        La figure créée
    ax : matplotlib.axes.Axes
        L'axe créé
    """

    if not segments:
        raise ValueError("segments must not be empty")
    
    # Calcul des distances cumulées
    distances_km = np.zeros(len(segments) + 1)
    elevations_real = np.zeros(len(segments) + 1)
    elevations_virtual = np.zeros(len(segments) + 1)
    
    cum_dist = 0.0
    cum_elev_virtual = 0.0
    
    for i, seg in enumerate(segments):
        # Distance cumulée au début du segment
        distances_km[i] = cum_dist / 1000.0
        
        # Altitude réelle au début du segment
        elevations_real[i] = seg.get('ele1', 0)
        
        # Altitude virtuelle au début du segment
        elevations_virtual[i] = elevations_real[i] + cum_elev_virtual
        
        # Dénivelé virtuel de ce segment (effet du vent)
        elev_virt_seg = seg.get('elevation_virtual_m', 0)
        cum_elev_virtual += elev_virt_seg
        
        # Avance la distance
        cum_dist += seg['distance']
    
    # Dernier point (fin du dernier segment)
    distances_km[-1] = cum_dist / 1000.0
    elevations_real[-1] = segments[-1].get('ele2', 0)
    elevations_virtual[-1] = elevations_real[-1] + cum_elev_virtual

    if distance_from_finish:
        x_values_km = distances_km[-1] - distances_km
        x_label = "Distance depuis l'arrivée (km)"
    else:
        x_values_km = distances_km
        x_label = 'Distance (km)'
    
    # Création du graphique
    fig, ax = plt.subplots(figsize=figsize)
    
    # Profil d'altitude réel
    ax.plot(x_values_km, elevations_real, 
            label='Altitude réelle (terrain)', 
            color='sienna', linewidth=2, zorder=2)
    
    # Remplissage sous la courbe réelle
    ax.fill_between(x_values_km, 0, elevations_real, 
                     alpha=0.3, color='tan', zorder=1)
    
    if show_virtual and any(seg.get('elevation_virtual_m') is not None for seg in segments):
        # Profil d'altitude virtuel (incluant l'effet du vent)
        ax.plot(x_values_km, elevations_virtual, 
                label='Altitude virtuelle (terrain + effet vent)', 
                color='steelblue', linewidth=2, linestyle='--', zorder=3)
        
        # Statistiques pour le titre
        total_elev_real = elevations_real[-1] - elevations_real[0]
        total_elev_virtual = elevations_virtual[-1] - elevations_virtual[0]
        diff_elev = total_elev_virtual - total_elev_real
        
        # Afficher la différence dans une légende
        if diff_elev > 0:
            legend_text = f'Dénivelé virtuel supplémentaire : +{diff_elev:.0f} m (vent défavorable)'
        elif diff_elev < 0:
            legend_text = f'Dénivelé virtuel réduit : {diff_elev:.0f} m (vent favorable)'
        else:
            legend_text = 'Pas d\'effet de vent net'
        
        ax.text(0.02, 0.98, legend_text, 
                transform=ax.transAxes, 
                verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8),
                fontsize=10)
    
    # Configuration de l'axe
    ax.set_xlabel(x_label, fontsize=12)
    ax.set_ylabel('Altitude (m)', fontsize=12)
    if distance_from_finish:
        # Keep route progression left-to-right while showing remaining distance.
        ax.invert_xaxis()
    ax.grid(True, alpha=0.3)
    ax.legend(loc='upper right', fontsize=10)
    
    # Titre
    if title:
        ax.set_title(title, fontsize=14, fontweight='bold')
    else:
        ax.set_title('Profil d\'altitude : réel vs virtuel (effet vent)', 
                     fontsize=14, fontweight='bold')
    
    # Ligne de référence à 0m (niveau de la mer)
    ax.axhline(y=0, color='navy', linestyle=':', linewidth=1, alpha=0.5, label='Niveau de la mer')
    
    plt.tight_layout()
    
    return fig, ax


def plot_segments_evolution(segments: List[Dict], 
                            attributes: List[str],
                            x_axis: str = 'distance',
                            figsize: tuple = (14, 10),
                            title: Optional[str] = None,
                            distance_from_finish: bool = False):
    """
    Trace l'évolution des attributs des segments en fonction de la distance ou du temps.
    
    Parameters:
    -----------
    segments : List[Dict]
        Liste des segments résultats de simulate_with_weather
    attributes : List[str]
        Liste des attributs à tracer (ex: ['tws', 'twd', 'wind_along', 'speed_m_s'])
        Attributs disponibles:
        - 'tws': vitesse du vent (m/s)
        - 'twd': direction du vent (degrés)
        - 'wind_along': vent le long de la trajectoire (m/s)
        - 'gust': rafales (m/s)
        - 'headwind': vent de face (m/s)
        - 'gust_along': rafales le long de la trajectoire (m/s)
        - 'crosswind': vent de travers (m/s)
        - 'is_headwind': indicateur de vent de face (booléen)
        - 'speed_m_s': vitesse du cycliste (m/s)
        - 'slope': pente (ratio)
        - 'slope_terrain': pente du terrain (ratio)
        - 'slope_wind': pente virtuelle due au vent (ratio)
        - 'slope_effective': pente effective (terrain + vent) (ratio)
        - 'elevation_virtual_m': dénivelé virtuel en mètres
    x_axis : str, optional
        'distance' pour tracer en fonction des kilomètres (défaut)
        'time' pour tracer en fonction du temps (minutes)
    figsize : tuple, optional
        Taille de la figure (largeur, hauteur)
    title : str, optional
        Titre principal du graphique
    distance_from_finish : bool, optional
        Si True et si x_axis='distance', l'axe des abscisses représente la
        distance restante jusqu'à l'arrivée.
        
    Returns:
    --------
    fig : matplotlib.figure.Figure
        La figure créée
    axes : list
        Liste des axes créés
    """
    
    # Dictionnaire des labels et unités pour chaque attribut
    attr_info = {
        'tws': {'label': 'Vitesse du vent (TWS)', 'unit': 'km/h', 'convert': 3.6},
        'twd': {'label': 'Direction du vent (TWD)', 'unit': '°', 'convert': 1.0},
        'wind_along': {'label': 'Vent le long de la trajectoire', 'unit': 'km/h', 'convert': 3.6},
        'gust': {'label': 'Rafales', 'unit': 'km/h', 'convert': 3.6},
        'headwind': {'label': 'Vent de face', 'unit': 'km/h', 'convert': 3.6},
        'gust_along': {'label': 'Rafales le long de la trajectoire', 'unit': 'km/h', 'convert': 3.6},
        'crosswind': {'label': 'Vent de travers', 'unit': 'km/h', 'convert': 3.6},
        'is_headwind': {'label': 'Vent de face (indicateur)', 'unit': '', 'convert': 1.0},
        'speed_m_s': {'label': 'Vitesse du cycliste', 'unit': 'km/h', 'convert': 3.6},
        'slope': {'label': 'Pente', 'unit': '%', 'convert': 100.0},
        'slope_terrain': {'label': 'Pente terrain', 'unit': '%', 'convert': 100.0},
        'slope_wind': {'label': 'Pente virtuelle (vent)', 'unit': '%', 'convert': 100.0},
        'slope_effective': {'label': 'Pente effective (terrain+vent)', 'unit': '%', 'convert': 100.0},
        'elevation_virtual_m': {'label': 'Dénivelé virtuel', 'unit': 'm', 'convert': 1.0},
        'bearing': {'label': 'Cap', 'unit': '°', 'convert': 1.0},
    }
    
    # Calcul de l'axe X
    if x_axis == 'distance':
        # Distance cumulée en km
        x_values = np.zeros(len(segments))
        cum_dist = 0
        for i, seg in enumerate(segments):
            x_values[i] = cum_dist / 1000.0  # conversion en km
            cum_dist += seg['distance']
        if distance_from_finish:
            total_distance_km = cum_dist / 1000.0
            x_values = total_distance_km - x_values
            x_label = "Distance depuis l'arrivée (km)"
        else:
            x_label = 'Distance (km)'
    elif x_axis == 'time':
        # Temps cumulé en minutes
        x_values = np.zeros(len(segments))
        cum_time = 0
        for i, seg in enumerate(segments):
            x_values[i] = cum_time / 60.0  # conversion en minutes
            if seg['time_s'] is not None and seg['time_s'] != float('inf'):
                cum_time += seg['time_s']
        x_label = 'Temps (min)'
    else:
        raise ValueError("x_axis doit être 'distance' ou 'time'")
    
    # Création de la figure avec sous-graphiques
    n_plots = len(attributes)
    fig, axes = plt.subplots(n_plots, 1, figsize=figsize, sharex=True)
    
    # Si un seul attribut, axes n'est pas une liste
    if n_plots == 1:
        axes = [axes]
    
    # Titre principal
    if title:
        fig.suptitle(title, fontsize=14, fontweight='bold')
    
    # Tracer chaque attribut
    for idx, attr in enumerate(attributes):
        ax = axes[idx]
        
        # Extraire les valeurs
        y_values = []
        for seg in segments:
            value = seg.get(attr, None)
            if value is None:
                value = 0.0
            y_values.append(value)
        
        y_values = np.array(y_values)
        
        # Conversion d'unités
        if attr in attr_info:
            info = attr_info[attr]
            y_values = y_values * info['convert']
            ylabel = f"{info['label']} ({info['unit']})" if info['unit'] else info['label']
        else:
            ylabel = attr
        
        # Tracer
        if attr == 'is_headwind':
            # Pour les booléens, utiliser un style différent
            ax.fill_between(x_values, 0, y_values, alpha=0.3, label=ylabel)
            ax.plot(x_values, y_values, 'o-', markersize=3, linewidth=1.5)
        else:
            ax.plot(x_values, y_values, 'o-', markersize=3, linewidth=1.5, label=ylabel)
        
        # Ajouter une ligne horizontale à zéro pour les vents
        if attr in ['wind_along', 'headwind', 'gust_along', 'crosswind']:
            ax.axhline(y=0, color='red', linestyle='--', alpha=0.3, linewidth=1)
        
        ax.set_ylabel(ylabel, fontsize=10)
        ax.grid(True, alpha=0.3)
        ax.legend(loc='upper right', fontsize=9)
        
        # Afficher des statistiques
        if attr != 'is_headwind':
            mean_val = np.mean(y_values)
            min_val = np.min(y_values)
            max_val = np.max(y_values)
            stats_text = f'Moy: {mean_val:.1f} | Min: {min_val:.1f} | Max: {max_val:.1f}'
            ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, 
                   fontsize=8, verticalalignment='top',
                   bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    # Label de l'axe X sur le dernier graphique
    axes[-1].set_xlabel(x_label, fontsize=10)
    if x_axis == 'distance' and distance_from_finish:
        for ax in axes:
            # Keep route progression left-to-right while showing remaining distance.
            ax.invert_xaxis()
    
    plt.tight_layout()
    return fig, axes


def plot_wind_rose(segments: List[Dict], 
                   figsize: tuple = (10, 10),
                   title: Optional[str] = None):
    """
    Trace une rose des vents basée sur les segments.
    
    Parameters:
    -----------
    segments : List[Dict]
        Liste des segments résultats
    figsize : tuple, optional
        Taille de la figure
    title : str, optional
        Titre du graphique
        
    Returns:
    --------
    fig : matplotlib.figure.Figure
        La figure créée
    ax : matplotlib.axes.Axes
        L'axe créé
    """
    
    # Extraire les directions et vitesses du vent
    twd_list = []
    tws_list = []
    
    for seg in segments:
        twd = seg.get('twd', None)
        tws = seg.get('tws', None)
        if twd is not None and tws is not None:
            twd_list.append(twd)
            tws_list.append(tws * 3.6)  # conversion en km/h
    
    if not twd_list:
        print("Aucune donnée de vent disponible")
        return None, None
    
    twd_array = np.array(twd_list)
    tws_array = np.array(tws_list)
    
    # Créer la figure en coordonnées polaires
    fig, ax = plt.subplots(figsize=figsize, subplot_kw=dict(projection='polar'))
    ax = cast(PolarAxes, ax)
    
    # Convertir les directions en radians (attention: 0° = Nord)
    theta = np.radians(twd_array)
    
    # Tracer
    scatter = ax.scatter(theta, tws_array, c=tws_array, s=50, alpha=0.6, 
                        cmap='viridis', edgecolors='black', linewidth=0.5)
    
    # Configuration
    ax.set_theta_zero_location('N')
    ax.set_theta_direction(-1)
    ax.set_title(title or 'Rose des vents', fontsize=14, fontweight='bold', pad=20)
    ax.set_ylabel('Vitesse du vent (km/h)', fontsize=10)
    
    # Colorbar
    cbar = plt.colorbar(scatter, ax=ax, pad=0.1)
    cbar.set_label('Vitesse du vent (km/h)', fontsize=10)
    
    plt.tight_layout()
    return fig, ax


def compare_scenarios(segments_list: List[List[Dict]],
                     labels: List[str],
                     attribute: str,
                     x_axis: str = 'distance',
                     figsize: tuple = (14, 6),
                     title: Optional[str] = None,
                     distance_from_finish: bool = False):
    """
    Compare plusieurs scénarios (ex: avec/sans vent) pour un attribut donné.
    
    Parameters:
    -----------
    segments_list : List[List[Dict]]
        Liste de listes de segments (un par scénario)
    labels : List[str]
        Labels pour chaque scénario
    attribute : str
        Attribut à comparer
    x_axis : str, optional
        'distance' ou 'time'
    figsize : tuple, optional
        Taille de la figure
    title : str, optional
        Titre du graphique
    distance_from_finish : bool, optional
        Si True et si x_axis='distance', l'axe des abscisses représente la
        distance restante jusqu'à l'arrivée.
        
    Returns:
    --------
    fig : matplotlib.figure.Figure
        La figure créée
    ax : matplotlib.axes.Axes
        L'axe créé
    """
    
    # Dictionnaire des labels et unités
    attr_info = {
        'tws': {'label': 'Vitesse du vent (TWS)', 'unit': 'km/h', 'convert': 3.6},
        'speed_m_s': {'label': 'Vitesse du cycliste', 'unit': 'km/h', 'convert': 3.6},
        'wind_along': {'label': 'Vent le long de la trajectoire', 'unit': 'km/h', 'convert': 3.6},
        'slope': {'label': 'Pente', 'unit': '%', 'convert': 100.0},
    }
    
    fig, ax = plt.subplots(figsize=figsize)
    
    for segments, label in zip(segments_list, labels):
        # Calcul de l'axe X
        if x_axis == 'distance':
            x_values = np.zeros(len(segments))
            cum_dist = 0
            for i, seg in enumerate(segments):
                x_values[i] = cum_dist / 1000.0
                cum_dist += seg['distance']
            if distance_from_finish:
                total_distance_km = cum_dist / 1000.0
                x_values = total_distance_km - x_values
                x_label = "Distance depuis l'arrivée (km)"
            else:
                x_label = 'Distance (km)'
        else:  # time
            x_values = np.zeros(len(segments))
            cum_time = 0
            for i, seg in enumerate(segments):
                x_values[i] = cum_time / 60.0
                if seg['time_s'] is not None and seg['time_s'] != float('inf'):
                    cum_time += seg['time_s']
            x_label = 'Temps (min)'
        
        # Extraire les valeurs
        y_values = []
        for seg in segments:
            value = seg.get(attribute, None)
            if value is None:
                value = 0.0
            y_values.append(value)
        
        y_values = np.array(y_values)
        
        # Conversion d'unités
        if attribute in attr_info:
            info = attr_info[attribute]
            y_values = y_values * info['convert']
            ylabel = f"{info['label']} ({info['unit']})" if info['unit'] else info['label']
        else:
            ylabel = attribute
        
        # Tracer
        ax.plot(x_values, y_values, 'o-', markersize=3, linewidth=1.5, label=label, alpha=0.7)
    
    ax.set_xlabel(x_label, fontsize=10)
    ax.set_ylabel(ylabel, fontsize=10)
    if x_axis == 'distance' and distance_from_finish:
        # Keep route progression left-to-right while showing remaining distance.
        ax.invert_xaxis()
    ax.set_title(title or f'Comparaison: {ylabel}', fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.legend(loc='best', fontsize=10)
    
    plt.tight_layout()
    return fig, ax


def print_summary_statistics(
    data,
    label: str = "Simulation",
    terrain_smoothing_window_m: float = 100.0,
):
    """
    Affiche les statistiques résumées des résultats de simulation.
    
    Parameters:
    -----------
    data : SimulationResult | List[Dict]
        Résultat structuré (recommandé) ou liste de segments (legacy)
    label : str, optional
        Label pour identifier la simulation
    terrain_smoothing_window_m : float, optional
        Fenêtre de lissage (en mètres) pour les extrêmes de pente terrain,
        virtuelle et effective. Nom conservé pour compatibilité.
        Doit être comprise entre 50m et 2000m.
    """

    if not (50.0 <= float(terrain_smoothing_window_m) <= 2000.0):
        raise ValueError(
            "terrain_smoothing_window_m must be between 50 and 2000 meters"
        )
    
    print(f"\n{'='*60}")
    print(f"  STATISTIQUES - {label}")
    print(f"{'='*60}")
    
    def _format_hms(total_seconds: float) -> str:
        total_seconds_int = int(round(total_seconds))
        hours, remainder = divmod(total_seconds_int, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _slope_extremes_with_km(
        segments: List[Dict],
        slope_getter,
        window_m: float = 100.0,
    ):
        """Return raw and distance-smoothed slope extremes with km positions."""
        if not segments:
            return None

        rows = []
        cum_km = 0.0
        for seg in segments:
            d = float(seg.get('distance', 0.0) or 0.0)
            slope = float(slope_getter(seg, d) or 0.0)
            rows.append({
                'dist_m': d,
                'slope': slope,
                'km_mid': cum_km + d / 2000.0,
            })
            cum_km += d / 1000.0

        if not rows:
            return None

        raw_min = min(rows, key=lambda r: r['slope'])
        raw_max = max(rows, key=lambda r: r['slope'])

        dist_arr = np.array([r['dist_m'] for r in rows], dtype=float)
        slope_arr = np.array([r['slope'] for r in rows], dtype=float)

        if np.sum(dist_arr) <= 0.0:
            return {
                'raw_min_pct': raw_min['slope'] * 100.0,
                'raw_min_km': raw_min['km_mid'],
                'raw_max_pct': raw_max['slope'] * 100.0,
                'raw_max_km': raw_max['km_mid'],
                'smooth_min_pct': raw_min['slope'] * 100.0,
                'smooth_min_km': raw_min['km_mid'],
                'smooth_max_pct': raw_max['slope'] * 100.0,
                'smooth_max_km': raw_max['km_mid'],
                'window_m': window_m,
            }

        best_max = -1e9
        best_min = 1e9
        best_max_km = 0.0
        best_min_km = 0.0
        left = 0
        w_dist = 0.0
        w_slope_dist = 0.0
        cum_km_left = 0.0
        cum_km_right = 0.0

        for right in range(len(rows)):
            d_r = dist_arr[right]
            w_dist += d_r
            w_slope_dist += slope_arr[right] * d_r
            cum_km_right += d_r / 1000.0

            while left <= right and w_dist - dist_arr[left] >= window_m:
                d_l = dist_arr[left]
                w_dist -= d_l
                w_slope_dist -= slope_arr[left] * d_l
                cum_km_left += d_l / 1000.0
                left += 1

            if w_dist > 0:
                w_avg = w_slope_dist / w_dist
                km_mid = (cum_km_left + cum_km_right) / 2.0
                if w_avg > best_max:
                    best_max = w_avg
                    best_max_km = km_mid
                if w_avg < best_min:
                    best_min = w_avg
                    best_min_km = km_mid

        return {
            'raw_min_pct': raw_min['slope'] * 100.0,
            'raw_min_km': raw_min['km_mid'],
            'raw_max_pct': raw_max['slope'] * 100.0,
            'raw_max_km': raw_max['km_mid'],
            'smooth_min_pct': best_min * 100.0,
            'smooth_min_km': best_min_km,
            'smooth_max_pct': best_max * 100.0,
            'smooth_max_km': best_max_km,
            'window_m': window_m,
        }

    def _terrain_slope_getter(seg: Dict, distance_m: float) -> float:
        e1 = float(seg.get('ele1', 0.0) or 0.0)
        e2 = float(seg.get('ele2', 0.0) or 0.0)
        return ((e2 - e1) / distance_m) if distance_m > 0.5 else 0.0

    def _segment_slope_getter(key: str, fallback_key: Optional[str] = None):
        def _getter(seg: Dict, _distance_m: float) -> float:
            value = seg.get(key)
            if value is None and fallback_key is not None:
                value = seg.get(fallback_key)
            return float(value or 0.0)

        return _getter

    def _print_smoothed_slope_extremes(prefix: str, extremes: Optional[Dict], raw_min: float, raw_max: float):
        if extremes is not None:
            print(
                f"   Min (lissé {int(extremes['window_m'])}m): "
                f"{extremes['smooth_min_pct']:.2f}% (au km {extremes['smooth_min_km']:.2f})"
            )
            print(
                f"   Max (lissé {int(extremes['window_m'])}m): "
                f"{extremes['smooth_max_pct']:.2f}% (au km {extremes['smooth_max_km']:.2f})"
            )
            logging.getLogger(__name__).debug(
                "%s raw extremes: min=%.2f%% at km %.2f, max=%.2f%% at km %.2f",
                prefix,
                extremes['raw_min_pct'],
                extremes['raw_min_km'],
                extremes['raw_max_pct'],
                extremes['raw_max_km'],
            )
            return

        print(f"   Min: {raw_min:.2f}%")
        print(f"   Max: {raw_max:.2f}%")

    # Chemin recommandé: lecture directe depuis SimulationResult (sans recalcul)
    if hasattr(data, 'distance') and hasattr(data, 'time') and hasattr(data, 'speed'):
        result = data

        print(f"\n📏 Distance totale: {result.distance.total_km:.2f} km")
        print(f"⏱️  Temps total: {_format_hms(result.time.total_seconds)}")
        print(f"🚴  Vitesse moyenne: {result.speed.avg:.2f} km/h (max={result.speed.max:.2f} km/h)")
    
        if hasattr(result, 'power') and result.power is not None:
            print(f"⚡  Puissance moyenne: {result.power.avg:.1f} W")

        print(f"\n💨 Vent (TWS et TWD):")
        print(f"   Moyen: {result.wind.tws.avg * 3.6:.2f} km/h - Direction: {result.wind.twd_avg:.0f}° ({result.wind.twd_compass})")
        print(f"   Min: {result.wind.tws.min * 3.6:.2f} km/h")
        print(f"   Max: {result.wind.tws.max * 3.6:.2f} km/h")

        print(f"\n💨 Rafales (Gust):")
        print(f"   Moyenne: {result.gusts.avg * 3.6:.2f} km/h")
        print(f"   Min: {result.gusts.min * 3.6:.2f} km/h (au km {result.gusts.min_at_km:.2f})")
        print(f"   Max: {result.gusts.max * 3.6:.2f} km/h (au km {result.gusts.max_at_km:.2f})")

        print(f"\n⛰️ Pente terrain:")
        print(f"   Moyenne: {result.slopes.terrain.avg_pct:.2f} %")
        terrain_ext = _slope_extremes_with_km(
            result.get_segments(),
            _terrain_slope_getter,
            window_m=float(terrain_smoothing_window_m),
        )
        _print_smoothed_slope_extremes(
            "Terrain",
            terrain_ext,
            result.slopes.terrain.min_pct,
            result.slopes.terrain.max_pct,
        )
        print(f"   Dénivelé positif: {result.slopes.terrain.deniv_pos_m:.0f} m")
        print(f"   Dénivelé négatif: {result.slopes.terrain.deniv_neg_m:.0f} m")

        print(f"\n🌬️ Pente virtuelle (vent):")
        print(f"   Moyenne: {result.slopes.virtual.avg_pct:.2f}%")
        virtual_ext = _slope_extremes_with_km(
            result.get_segments(),
            _segment_slope_getter('slope_wind'),
            window_m=float(terrain_smoothing_window_m),
        )
        _print_smoothed_slope_extremes(
            "Virtual",
            virtual_ext,
            result.slopes.virtual.min_pct,
            result.slopes.virtual.max_pct,
        )
        print(f"   Dénivelé virtuel positif: {result.slopes.virtual.deniv_pos_m:.0f} m")
        print(f"   Dénivelé virtuel négatif: {result.slopes.virtual.deniv_neg_m:.0f} m")

        print(f"\n📊 Pente effective (terrain + vent):")
        print(f"   Moyenne: {result.slopes.effective.avg_pct:.2f}%")
        effective_ext = _slope_extremes_with_km(
            result.get_segments(),
            _segment_slope_getter('slope_effective', fallback_key='slope'),
            window_m=float(terrain_smoothing_window_m),
        )
        _print_smoothed_slope_extremes(
            "Effective",
            effective_ext,
            result.slopes.effective.min_pct,
            result.slopes.effective.max_pct,
        )
        print(f"   Dénivelé effectif positif: {result.slopes.effective.deniv_pos_m:.0f} m")
        print(f"   Dénivelé effectif négatif: {result.slopes.effective.deniv_neg_m:.0f} m")

        print(f"\n🎯 Vent le long de la trajectoire:")
        print(
            f"   Vent de face: {result.wind_along_trajectory.headwind.percentage:.1f}% "
            f"({result.wind_along_trajectory.headwind.distance_km:.2f} km) - "
            f"Moyenne: {result.wind_along_trajectory.headwind.avg_kmh:.2f} km/h"
        )
        print(
            f"   Vent de dos: {result.wind_along_trajectory.tailwind.percentage:.1f}% "
            f"({result.wind_along_trajectory.tailwind.distance_km:.2f} km) - "
            f"Moyenne: {result.wind_along_trajectory.tailwind.avg_kmh:.2f} km/h"
        )
        print(
            f"   Vent de face Min: {result.wind_along_trajectory.headwind.min_kmh:.2f} km/h "
            f"(au km {result.wind_along_trajectory.headwind.min_at_km:.2f})"
        )
        print(
            f"   Vent de face Max: {result.wind_along_trajectory.headwind.max_kmh:.2f} km/h "
            f"(au km {result.wind_along_trajectory.headwind.max_at_km:.2f})"
        )
        print(
            f"   Vent de dos Min: {result.wind_along_trajectory.tailwind.min_kmh:.2f} km/h "
            f"(au km {result.wind_along_trajectory.tailwind.min_at_km:.2f})"
        )
        print(
            f"   Vent de dos Max: {result.wind_along_trajectory.tailwind.max_kmh:.2f} km/h "
            f"(au km {result.wind_along_trajectory.tailwind.max_at_km:.2f})"
        )

        if hasattr(result, 'wind_score') and result.wind_score is not None:
            print(f"\n🏁 WindScore:")
            print(f"   Grade final: {result.wind_score.grade}")
            print(f"   Raison: {result.wind_score.reason}")
            print(
                f"   Performance: {result.wind_score.performance_grade} "
                f"(score={result.wind_score.performance_score:+.3f})"
            )
            print(
                f"   Sécurité: {result.wind_score.safety_grade} "
                f"(danger={result.wind_score.safety_danger_score})"
            )

        print(f"\n{'='*60}\n")
        return

    segments = data

    # Distance et temps totaux (legacy: recalcul depuis segments)
    total_dist = sum(seg['distance'] for seg in segments) / 1000.0  # km
    total_seconds = sum(seg.get('time_s', 0) for seg in segments
                       if seg.get('time_s') not in (None, float('inf')))
    total_time = total_seconds / 60.0  # min
    
    print(f"\n📏 Distance totale: {total_dist:.2f} km")
    print(f"⏱️  Temps total: {_format_hms(total_seconds)}")
    
    if total_time > 0:
        avg_speed = (total_dist / (total_time/60))  # km/h
        print(f"🚴 Vitesse moyenne: {avg_speed:.2f} km/h")
        power_values = [seg.get('power') for seg in segments if seg.get('power') is not None]
        if power_values:
            print(f"⚡ Puissance moyenne: {np.mean(power_values):.1f} W")
    
    # Statistiques de vent
    tws_values = [seg.get('tws', 0) * 3.6 for seg in segments]  # km/h
    wind_along_values = [seg.get('wind_along', 0) * 3.6 for seg in segments]  # km/h
    gust_values = [seg.get('gust', 0) * 3.6 for seg in segments]  # km/h
    
    if tws_values:
        # Calcul de la direction moyenne du vent (TWD) par méthode vectorielle
        avg_twd_deg, avg_twd_text, avg_tws_kmh = compute_average_twd_vectorial(segments)
        
        print(f"\n💨 Vent (TWS et TWD):")
        print(f"   Moyen: {np.mean(tws_values):.2f} km/h - Direction: {avg_twd_deg:.0f}° ({avg_twd_text})")
        print(f"   Min: {np.min(tws_values):.2f} km/h")
        print(f"   Max: {np.max(tws_values):.2f} km/h")
    
    # Statistiques de rafales
    if gust_values:
        # Calcul des distances cumulées pour associer min/max à des kilomètres
        cumulative_dist = 0
        cumulative_dists = []
        for seg in segments:
            cumulative_dists.append(cumulative_dist + seg['distance'] / 2000.0)  # km, milieu du segment
            cumulative_dist += seg['distance'] / 1000.0
        
        min_gust = np.min(gust_values)
        max_gust = np.max(gust_values)
        min_idx = np.argmin(gust_values)
        max_idx = np.argmax(gust_values)
        
        print(f"\n💨 Rafales (Gust):")
        print(f"   Moyenne: {np.mean(gust_values):.2f} km/h")
        print(f"   Min: {min_gust:.2f} km/h (au km {cumulative_dists[min_idx]:.2f})")
        print(f"   Max: {max_gust:.2f} km/h (au km {cumulative_dists[max_idx]:.2f})")
    
     # Statistiques de pente terrain 
    slopes = [seg.get('slope', 0) * 100 for seg in segments]  # %
    if slopes:
        # Calcul des dénivellés positifs et négatifs
        """
        deniv_pos = sum(seg['slope'] * seg['distance'] 
                       for seg in segments if seg.get('slope', 0) > 0)  # m
        deniv_neg = abs(sum(seg['slope'] * seg['distance'] 
                           for seg in segments if seg.get('slope', 0) < 0))  # m
        """
        deniv_pos= sum(seg['ele2'] - seg['ele1'] for seg in segments if (seg['ele2'] - seg['ele1'])>0)
        deniv_neg= sum(seg['ele2'] - seg['ele1'] for seg in segments if (seg['ele2'] - seg['ele1'])<0)  # Négatif = perte d'altitude
        terrain_ext = _slope_extremes_with_km(
            segments,
            _terrain_slope_getter,
            window_m=float(terrain_smoothing_window_m),
        )
        print(f"\n⛰️  Pente terrain:")
        print(f"   Moyenne: {np.mean(slopes):.2f} %")
        _print_smoothed_slope_extremes(
            "Terrain",
            terrain_ext,
            float(np.min(slopes)),
            float(np.max(slopes)),
        )
        print(f"   Dénivelé positif: {deniv_pos:.0f} m")
        print(f"   Dénivelé négatif: {deniv_neg:.0f} m")

    # Statistiques de pente virtuelle 
    slope_terrain_values = [seg.get('slope_terrain', 0) * 100 for seg in segments]  # %
    slope_wind_values = [seg.get('slope_wind', 0) * 100 for seg in segments]  # %
    slope_effective_values = [seg.get('slope_effective', 0) * 100 for seg in segments]  # %
    elevation_virtual_values = [seg.get('elevation_virtual_m', 0) for seg in segments]  # m
    
    
    if any(seg.get('slope_wind') is not None for seg in segments):
        #total_elev_virtual = np.sum(elevation_virtual_values)
        total_elev_virtual_positive= np.where(np.array(elevation_virtual_values)>0,np.array(elevation_virtual_values),0).sum()
        total_elev_virtual_negative= np.where(np.array(elevation_virtual_values)<0,np.array(elevation_virtual_values),0).sum()
        virtual_ext = _slope_extremes_with_km(
            segments,
            _segment_slope_getter('slope_wind'),
            window_m=float(terrain_smoothing_window_m),
        )
        print(f"\n🌬️  Pente virtuelle (vent):")
        print(f"   Moyenne: {np.mean(slope_wind_values):.2f}%")
        _print_smoothed_slope_extremes(
            "Virtual",
            virtual_ext,
            float(np.min(slope_wind_values)),
            float(np.max(slope_wind_values)),
        )
        print(f"   Dénivelé virtuel positif: {total_elev_virtual_positive:.0f} m")
        print(f"   Dénivelé virtuel négatif: {total_elev_virtual_negative:.0f} m") 
    
    if any(seg.get('slope_effective') is not None for seg in segments):
        total_elev_effective_positive=float(total_elev_virtual_positive)+ deniv_pos
        total_elev_effective_negative= float(total_elev_virtual_negative) + deniv_neg    
        effective_ext = _slope_extremes_with_km(
            segments,
            _segment_slope_getter('slope_effective', fallback_key='slope'),
            window_m=float(terrain_smoothing_window_m),
        )
        print(f"\n📊 Pente effective (terrain + vent):")
        print(f"   Moyenne: {np.mean(slope_effective_values):.2f}%")
        _print_smoothed_slope_extremes(
            "Effective",
            effective_ext,
            float(np.min(slope_effective_values)),
            float(np.max(slope_effective_values)),
        )
        print(f"   Dénivelé effectif positif: {total_elev_effective_positive:.0f} m")
        print(f"   Dénivelé effectif négatif: {total_elev_effective_negative:.0f} m") 
    
    # Statistiques du vent le long de la trajectoire
    if wind_along_values:
        # Calcul des distances cumulées
        cumulative_dist = 0
        cumulative_dists = []
        for seg in segments:
            cumulative_dists.append(cumulative_dist + seg['distance'] / 2000.0)  # km, milieu du segment
            cumulative_dist += seg['distance'] / 1000.0
        
        # Calculer les distances avec vent de face et vent de dos
        dist_headwind = 0  # distance avec vent de face
        dist_tailwind = 0  # distance avec vent de dos
        sum_headwind_weighted = 0  # pour la moyenne pondérée
        sum_tailwind_weighted = 0  # pour la moyenne pondérée
        total_dist_m = sum(seg['distance'] for seg in segments)
        
        for i, seg in enumerate(segments):
            wind_along = seg.get('wind_along', 0) * 3.6  # km/h
            if wind_along > 0:
                dist_headwind += seg['distance']
                sum_headwind_weighted += wind_along * seg['distance']
            elif wind_along < 0:
                dist_tailwind += seg['distance']
                sum_tailwind_weighted += wind_along * seg['distance']
        
        # Ratios en pourcentage basés sur la distance
        ratio_headwind = (dist_headwind / total_dist_m * 100) if total_dist_m > 0 else 0
        ratio_tailwind = (dist_tailwind / total_dist_m * 100) if total_dist_m > 0 else 0
        
        # Moyennes pondérées par la distance
        avg_headwind = (sum_headwind_weighted / dist_headwind) if dist_headwind > 0 else 0
        avg_tailwind = (sum_tailwind_weighted / dist_tailwind) if dist_tailwind > 0 else 0
        
        print(f"\n🎯 Vent le long de la trajectoire:")
        print(f"   Vent de face: {ratio_headwind:.1f}% ({dist_headwind/1000:.2f} km) - Moyenne: {avg_headwind:.2f} km/h")
        print(f"   Vent de dos: {ratio_tailwind:.1f}% ({dist_tailwind/1000:.2f} km) - Moyenne: {avg_tailwind:.2f} km/h")
        
        # Min et Max du vent de face
        headwind_values = [v for v in wind_along_values if v > 0]  # vent de face (positif)
        if headwind_values:
            min_headwind = min(headwind_values)
            max_headwind = max(headwind_values)
            min_hw_idx = wind_along_values.index(min_headwind)
            max_hw_idx = wind_along_values.index(max_headwind)
            print(f"   Vent de face Min: {min_headwind:.2f} km/h (au km {cumulative_dists[min_hw_idx]:.2f})")
            print(f"   Vent de face Max: {max_headwind:.2f} km/h (au km {cumulative_dists[max_hw_idx]:.2f})")
        
        # Min et Max du vent de dos (valeurs négatives)
        tailwind_values = [v for v in wind_along_values if v < 0]  # vent de dos (négatif)
        if tailwind_values:
            min_tailwind = max(tailwind_values)  # max car valeurs négatives
            max_tailwind = min(tailwind_values)  # min car valeurs négatives
            min_tw_idx = wind_along_values.index(min_tailwind)
            max_tw_idx = wind_along_values.index(max_tailwind)
            print(f"   Vent de dos Min: {min_tailwind:.2f} km/h (au km {cumulative_dists[min_tw_idx]:.2f})")
            print(f"   Vent de dos Max: {max_tailwind:.2f} km/h (au km {cumulative_dists[max_tw_idx]:.2f})")
    
    
   
    
    print(f"\n{'='*60}\n")


def detect_outliers(segments: List[Dict], 
                   v_threshold: float = 60.0,
                   slope_threshold: float = 0.15,
                   show_details: bool = True,
                   log_file: Optional[str] = None) -> List[int]:
    """
    Détecte les segments avec des valeurs potentiellement aberrantes.
    
    Parameters:
    -----------
    segments : List[Dict]
        Liste des segments résultats
    v_threshold : float, optional
        Seuil de vitesse en km/h au-delà duquel un segment est considéré aberrant (défaut: 60 km/h)
    slope_threshold : float, optional
        Seuil de pente (ratio) au-delà duquel un segment est considéré aberrant (défaut: 0.15 = 15%)
    show_details : bool, optional
        Afficher les détails des segments aberrants
        
    Returns:
    --------
    outlier_indices : List[int]
        Liste des indices des segments aberrants
    """
    
    outliers = []
    
    for i, seg in enumerate(segments):
        speed_kmh = seg.get('speed_m_s', 0) * 3.6
        slope = seg.get('slope', 0)
        wind_along = seg.get('wind_along', 0) * 3.6
        distance = seg.get('distance', 0)
        
        is_outlier = False
        reasons = []
        
        # Vérifier vitesse aberrante
        if speed_kmh > v_threshold:
            is_outlier = True
            reasons.append(f"vitesse élevée: {speed_kmh:.1f} km/h")
        
        # Vérifier pente aberrante
        if abs(slope) > slope_threshold:
            is_outlier = True
            reasons.append(f"pente extrême: {slope*100:.1f}%")
        
        # Vérifier segment très court SEULEMENT s'il a déjà une anomalie
        # (pas besoin de signaler les segments courts avec vitesse normale)
        if distance < 10 and is_outlier:  # moins de 10 mètres ET anomalie
            reasons.append(f"segment très court: {distance:.1f}m")
        
        if is_outlier:
            outliers.append({
                'index': i,
                'speed_kmh': speed_kmh,
                'slope_pct': slope * 100,
                'wind_along_kmh': wind_along,
                'distance_m': distance,
                'reasons': reasons,
                'segment': seg
            })
    
    if (show_details or log_file) and outliers:
        output = []
        output.append(f"\n{'='*70}")
        output.append(f"  ⚠️  SEGMENTS ABERRANTS DÉTECTÉS: {len(outliers)}")
        output.append(f"{'='*70}")
        
        for outlier in outliers:
            output.append(f"\n🔍 Segment #{outlier['index']}:")
            output.append(f"   Vitesse: {outlier['speed_kmh']:.1f} km/h")
            output.append(f"   Pente: {outlier['slope_pct']:.1f}%")
            output.append(f"   Vent le long: {outlier['wind_along_kmh']:.1f} km/h")
            output.append(f"   Distance: {outlier['distance_m']:.1f} m")
            output.append(f"   Raisons: {', '.join(outlier['reasons'])}")
            
            # Détails supplémentaires pour le fichier
            if log_file:
                seg = outlier['segment']
                output.append(f"   Bearing: {seg.get('bearing', 0):.1f}°")
                output.append(f"   TWS: {seg.get('tws', 0)*3.6:.1f} km/h")
                output.append(f"   TWD: {seg.get('twd', 0):.1f}°")
                output.append(f"   Alt: {seg.get('ele1', 0):.1f}m -> {seg.get('ele2', 0):.1f}m")
        
        output.append(f"\n{'='*70}\n")
        
        text = "\n".join(output)
        
        if show_details:
            print(text)
        
        if log_file:
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write(text)
    
    elif not outliers:
        msg = "\n✅ Aucun segment aberrant détecté.\n"
        if show_details:
            print(msg)
        if log_file:
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write(msg)
    
    return [o['index'] for o in outliers]


def twd_to_text(twd_deg: float) -> str:
    """
    Convertit une direction de vent (True Wind Direction) en texte (16 directions cardinales).
    
    Parameters:
    -----------
    twd_deg : float
        Direction du vent en degrés (0-360°, convention météo: 0°=Nord, 90°=Est)
    
    Returns:
    --------
    str
        Direction cardinale (N, NNE, NE, ENE, E, ESE, SE, SSE, S, SSO, SO, OSO, O, ONO, NO, NNO)
    
    Examples:
    ---------
    >>> twd_to_text(0)
    'N'
    >>> twd_to_text(90)
    'E'
    >>> twd_to_text(225)
    'SO'
    """
    directions = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 
                  'S', 'SSO', 'SO', 'OSO', 'O', 'ONO', 'NO', 'NNO']
    idx = int((twd_deg + 11.25) / 22.5) % 16
    return directions[idx]


def compute_average_twd_vectorial(segments: List[Dict]) -> tuple:
    """
    Calcule la direction moyenne du vent (TWD) par méthode vectorielle.
    
    Cette méthode évite le problème de moyenner des angles (ex: 359° + 1° ≠ 180°)
    en décomposant les directions en composantes U/V, puis en reconstruisant l'angle moyen.
    
    Parameters:
    -----------
    segments : List[Dict]
        Liste des segments contenant 'twd', 'distance', et optionnellement 'tws'
    
    Returns:
    --------
    tuple : (avg_twd_deg, avg_twd_text, avg_tws_kmh)
        - avg_twd_deg : float - Direction moyenne en degrés (0-360°)
        - avg_twd_text : str - Direction cardinale (ex: 'NO', 'S')
        - avg_tws_kmh : float - Vitesse moyenne du vent (True Wind Speed) en km/h
    
    Notes:
    ------
    La moyenne est pondérée par la distance parcourue sur chaque segment.
    Les segments sans 'twd' ou 'distance' sont ignorés.
    
    Examples:
    ---------
    >>> segs = [
    ...     {'twd': 10, 'distance': 1000, 'tws': 5},
    ...     {'twd': 350, 'distance': 1000, 'tws': 4}
    ... ]
    >>> avg_deg, avg_text, avg_tws = compute_average_twd_vectorial(segs)
    >>> avg_deg  # Proche de 0° (moyenne vectorielle de 10° et 350°)
    0.0
    >>> avg_text
    'N'
    """
    tot_twd_u = 0  # Composante Est-Ouest (sin)
    tot_twd_v = 0  # Composante Nord-Sud (cos)
    tot_tws = 0
    tot_km = 0
    
    for seg in segments:
        twd = seg.get('twd')
        distance = seg.get('distance', 0)
        tws = seg.get('tws', 0)
        
        if twd is None or distance <= 0:
            continue
        
        # Décomposition vectorielle de la direction
        twd_rad = np.radians(twd)
        tot_twd_u += np.sin(twd_rad) * distance
        tot_twd_v += np.cos(twd_rad) * distance
        
        # Somme pondérée de TWS
        tot_tws += tws * distance
        tot_km += distance
    
    if tot_km == 0:
        return 0.0, 'N/A', 0.0
    
    # Reconstruction de l'angle moyen
    avg_twd_deg = np.degrees(np.arctan2(tot_twd_u / tot_km, tot_twd_v / tot_km)) % 360
    avg_twd_text = twd_to_text(avg_twd_deg)
    avg_tws_kmh = (tot_tws / tot_km) * 3.6  # m/s → km/h
    
    return avg_twd_deg, avg_twd_text, avg_tws_kmh
