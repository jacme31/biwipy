# -*- coding: utf-8 -*-
"""
Module de visualisation interactive des parcours cyclistes avec analyse du vent.
Génère une page HTML avec carte Folium et profils d'altitude interactifs.
"""

import folium
from folium import plugins
import numpy as np
from typing import List, Dict, Optional
import json


def _generate_statistics_html(segments: List[Dict]) -> str:
    """
    Génère le HTML des statistiques du parcours pour affichage dans le panel.
    
    Parameters:
    -----------
    segments : List[Dict]
        Liste des segments avec données de simulation
    
    Returns:
    --------
    str : HTML des statistiques
    """
    try:
        from biwipy.analysis.anareswind import compute_average_twd_vectorial, twd_to_text
    except ImportError:
        # Fallback for legacy script usage outside the package context.
        from anareswind import compute_average_twd_vectorial, twd_to_text
    
    # Calculer les statistiques
    total_distance = sum(seg['distance'] for seg in segments) / 1000.0  # km
    total_time = sum(seg['time_s'] for seg in segments) / 60.0  # min
    avg_speed = (total_distance / total_time * 60) if total_time > 0 else 0  # km/h
    
    # Statistiques de vent
    avg_tws = np.mean([seg.get('tws', 0) for seg in segments]) * 3.6  # km/h
    avg_twd_deg, twd_text, _ = compute_average_twd_vectorial(segments)  # La fonction retourne un tuple
    
    avg_gust = np.mean([seg.get('gust', 0) for seg in segments]) * 3.6
    min_gust = min([seg.get('gust', 0) for seg in segments]) * 3.6
    max_gust = max([seg.get('gust', 0) for seg in segments]) * 3.6
    
    # Pentes
    avg_slope = np.mean([seg.get('slope', 0) for seg in segments]) * 100
    min_slope = min([seg.get('slope', 0) for seg in segments]) * 100
    max_slope = max([seg.get('slope', 0) for seg in segments]) * 100
    
    # Dénivelés
    deniv_pos = sum(seg.get('ele2', 0) - seg.get('ele1', 0) 
                    for seg in segments if seg.get('ele2', 0) > seg.get('ele1', 0))
    deniv_neg = sum(seg.get('ele1', 0) - seg.get('ele2', 0) 
                    for seg in segments if seg.get('ele1', 0) > seg.get('ele2', 0))
    
    # Dénivelé virtuel (vent)
    deniv_virt_pos = sum(seg.get('elevation_virtual_m', 0) 
                         for seg in segments if seg.get('elevation_virtual_m', 0) > 0)
    deniv_virt_neg = sum(seg.get('elevation_virtual_m', 0) 
                         for seg in segments if seg.get('elevation_virtual_m', 0) < 0)
    
    # Vent le long de la trajectoire
    headwind_segs = [seg for seg in segments if seg.get('wind_along', 0) > 0]
    tailwind_segs = [seg for seg in segments if seg.get('wind_along', 0) < 0]
    
    headwind_dist = sum(seg['distance'] for seg in headwind_segs) / 1000.0
    tailwind_dist = sum(seg['distance'] for seg in tailwind_segs) / 1000.0
    
    headwind_pct = (headwind_dist / total_distance * 100) if total_distance > 0 else 0
    tailwind_pct = (tailwind_dist / total_distance * 100) if total_distance > 0 else 0
    
    avg_headwind = np.mean([seg['wind_along'] * 3.6 for seg in headwind_segs]) if headwind_segs else 0
    avg_tailwind = np.mean([seg['wind_along'] * 3.6 for seg in tailwind_segs]) if tailwind_segs else 0
    
    # Générer le HTML
    html = f"""
    <div style="padding: 15px; font-family: Arial, sans-serif; font-size: 13px;">
        <h3 style="margin: 0 0 15px 0; color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 8px;">📊 Statistiques du parcours</h3>
        
        <div style="margin-bottom: 15px;">
            <h4 style="margin: 10px 0 8px 0; color: #555;">📏 Distance et temps</h4>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 4px 0;">Distance totale:</td><td style="text-align: right; font-weight: bold;">{total_distance:.2f} km</td></tr>
                <tr><td style="padding: 4px 0;">Temps total:</td><td style="text-align: right; font-weight: bold;">{int(total_time//60)}h{int(total_time%60):02d}min</td></tr>
                <tr><td style="padding: 4px 0;">Vitesse moyenne:</td><td style="text-align: right; font-weight: bold;">{avg_speed:.2f} km/h</td></tr>
            </table>
        </div>
        
        <div style="margin-bottom: 15px;">
            <h4 style="margin: 10px 0 8px 0; color: #555;">💨 Vent (TWS et TWD)</h4>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 4px 0;">Moyen:</td><td style="text-align: right; font-weight: bold;">{avg_tws:.2f} km/h</td></tr>
                <tr><td style="padding: 4px 0;">Direction:</td><td style="text-align: right; font-weight: bold;">{avg_twd_deg:.0f}° ({twd_text})</td></tr>
            </table>
        </div>
        
        <div style="margin-bottom: 15px;">
            <h4 style="margin: 10px 0 8px 0; color: #555;">💨 Rafales</h4>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 4px 0;">Moyenne:</td><td style="text-align: right; font-weight: bold;">{avg_gust:.2f} km/h</td></tr>
                <tr><td style="padding: 4px 0;">Min - Max:</td><td style="text-align: right; font-weight: bold;">{min_gust:.1f} - {max_gust:.1f} km/h</td></tr>
            </table>
        </div>
        
        <div style="margin-bottom: 15px;">
            <h4 style="margin: 10px 0 8px 0; color: #555;">⛰️ Pente terrain</h4>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 4px 0;">Moyenne:</td><td style="text-align: right; font-weight: bold;">{avg_slope:.2f} %</td></tr>
                <tr><td style="padding: 4px 0;">Min - Max:</td><td style="text-align: right; font-weight: bold;">{min_slope:.1f} - {max_slope:.1f} %</td></tr>
                <tr><td style="padding: 4px 0;">Dénivelé +:</td><td style="text-align: right; font-weight: bold;">{deniv_pos:.0f} m</td></tr>
                <tr><td style="padding: 4px 0;">Dénivelé -:</td><td style="text-align: right; font-weight: bold;">{deniv_neg:.0f} m</td></tr>
            </table>
        </div>
        
        <div style="margin-bottom: 15px;">
            <h4 style="margin: 10px 0 8px 0; color: #555;">🌬️ Dénivelé virtuel (vent)</h4>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 4px 0;">Positif:</td><td style="text-align: right; font-weight: bold;">{deniv_virt_pos:.0f} m</td></tr>
                <tr><td style="padding: 4px 0;">Négatif:</td><td style="text-align: right; font-weight: bold;">{deniv_virt_neg:.0f} m</td></tr>
            </table>
        </div>
        
        <div style="margin-bottom: 15px;">
            <h4 style="margin: 10px 0 8px 0; color: #555;">🎯 Vent le long de la trajectoire</h4>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 4px 0;">❌ Vent de face:</td><td style="text-align: right; font-weight: bold;">{headwind_pct:.1f}% ({headwind_dist:.1f} km)</td></tr>
                <tr><td style="padding: 4px 0; padding-left: 15px;">Moyenne:</td><td style="text-align: right;">{avg_headwind:.2f} km/h</td></tr>
                <tr><td style="padding: 4px 0;">✅ Vent de dos:</td><td style="text-align: right; font-weight: bold;">{tailwind_pct:.1f}% ({tailwind_dist:.1f} km)</td></tr>
                <tr><td style="padding: 4px 0; padding-left: 15px;">Moyenne:</td><td style="text-align: right;">{avg_tailwind:.2f} km/h</td></tr>
            </table>
        </div>
    </div>
    """
    
    return html


def get_wind_color(wind_along_ms: float) -> str:
    """
    Retourne une couleur selon l'intensité du vent le long de la trajectoire.
    
    Parameters:
    -----------
    wind_along_ms : float
        Vent le long de la trajectoire en m/s (+ = face, - = dos)
    
    Returns:
    --------
    str : Code couleur hexadécimal
    """
    wind_kmh = wind_along_ms * 3.6
    
    # Vent de face (positif)
    if wind_kmh > 15:
        return '#8B0000'  # Rouge foncé
    elif wind_kmh > 10:
        return '#DC143C'  # Rouge
    elif wind_kmh > 5:
        return '#FF6347'  # Tomate
    elif wind_kmh > 2:
        return '#FFA500'  # Orange
    elif wind_kmh > -2:
        return '#FFD700'  # Jaune/or (vent faible)
    # Vent de dos (négatif)
    elif wind_kmh > -5:
        return '#90EE90'  # Vert clair
    elif wind_kmh > -10:
        return '#32CD32'  # Vert citron
    elif wind_kmh > -15:
        return '#228B22'  # Vert forêt
    else:
        return '#006400'  # Vert foncé


def create_popup_content(seg: Dict, seg_idx: int, cum_dist_km: float) -> str:
    """
    Crée le contenu HTML d'un popup pour un segment.
    
    Parameters:
    -----------
    seg : Dict
        Segment avec données de simulation
    seg_idx : int
        Index du segment
    cum_dist_km : float
        Distance cumulée en km
    
    Returns:
    --------
    str : Contenu HTML du popup
    """
    wind_along_kmh = seg.get('wind_along', 0) * 3.6
    wind_type = "🔴 Vent de face" if wind_along_kmh > 0 else "🟢 Vent de dos"
    
    tws = seg.get('tws', 0) * 3.6
    gust = seg.get('gust', 0) * 3.6
    speed = seg.get('speed_m_s', 0) * 3.6
    slope = seg.get('slope', 0) * 100
    slope_terrain = seg.get('slope_terrain', seg.get('slope', 0)) * 100
    slope_wind = seg.get('slope_wind', 0) * 100
    slope_effective = seg.get('slope_effective', slope) * 100
    
    html = f"""
    <div style="font-family: Arial; font-size: 12px; min-width: 250px;">
        <h4 style="margin: 0 0 10px 0; color: #333;">
            📍 Segment #{seg_idx} - km {cum_dist_km:.2f}
        </h4>
        
        <table style="width: 100%; border-collapse: collapse;">
            <tr style="background-color: #f0f0f0;">
                <td colspan="2" style="padding: 5px; font-weight: bold;">💨 Vent</td>
            </tr>
            <tr>
                <td style="padding: 3px;">{wind_type}</td>
                <td style="padding: 3px; text-align: right;">
                    <strong>{abs(wind_along_kmh):.1f} km/h</strong>
                </td>
            </tr>
            <tr>
                <td style="padding: 3px;">Vitesse vent (TWS)</td>
                <td style="padding: 3px; text-align: right;">{tws:.1f} km/h</td>
            </tr>
            <tr>
                <td style="padding: 3px;">Rafales</td>
                <td style="padding: 3px; text-align: right;">{gust:.1f} km/h</td>
            </tr>
            
            <tr style="background-color: #f0f0f0;">
                <td colspan="2" style="padding: 5px; font-weight: bold;">⛰️ Pente</td>
            </tr>
            <tr>
                <td style="padding: 3px;">Terrain</td>
                <td style="padding: 3px; text-align: right;">{slope_terrain:.1f}%</td>
            </tr>
            <tr>
                <td style="padding: 3px;">Virtuelle (vent)</td>
                <td style="padding: 3px; text-align: right;">{slope_wind:.1f}%</td>
            </tr>
            <tr style="font-weight: bold;">
                <td style="padding: 3px;">Effective</td>
                <td style="padding: 3px; text-align: right;">{slope_effective:.1f}%</td>
            </tr>
            
            <tr style="background-color: #f0f0f0;">
                <td colspan="2" style="padding: 5px; font-weight: bold;">🚴 Performance</td>
            </tr>
            <tr>
                <td style="padding: 3px;">Vitesse</td>
                <td style="padding: 3px; text-align: right;">{speed:.1f} km/h</td>
            </tr>
            <tr>
                <td style="padding: 3px;">Distance</td>
                <td style="padding: 3px; text-align: right;">{seg['distance']:.0f} m</td>
            </tr>
            <tr>
                <td style="padding: 3px;">Altitude</td>
                <td style="padding: 3px; text-align: right;">
                    {seg.get('ele1', 0):.0f} → {seg.get('ele2', 0):.0f} m
                </td>
            </tr>
        </table>
    </div>
    """
    return html


def create_interactive_map(segments: List[Dict], 
                          output_file: str,
                          title: str = "Analyse Interactive du Parcours Cycliste",
                          enable_animation: bool = True,
                          distance_from_finish: bool = False) -> str:
    """
    Crée une carte interactive HTML avec tracé colorisé et profil d'altitude.
    
    Fonctionnalités :
    - Synchronisation carte ↔ profil : clic sur profil → marqueur animé sur carte
    - Animation temporelle avec slider pour rejouer le parcours
    
    Parameters:
    -----------
    segments : List[Dict]
        Liste des segments résultats de simulate_with_weather
    output_file : str
        Chemin du fichier HTML de sortie
    title : str, optional
        Titre de la page
    enable_animation : bool, optional
        Activer le slider d'animation temporelle (défaut: True)
    distance_from_finish : bool, optional
        Si True, le profil d'altitude interactif utilise la distance restante
        jusqu'à l'arrivée sur l'axe des abscisses.
    
    Returns:
    --------
    str : Chemin du fichier généré
    """
    
    if not segments:
        raise ValueError("La liste de segments est vide")
    
    # Calculer le centre de la carte
    all_lats = [seg['lat1'] for seg in segments] + [segments[-1]['lat2']]
    all_lons = [seg['lon1'] for seg in segments] + [segments[-1]['lon2']]
    center_lat = np.mean(all_lats)
    center_lon = np.mean(all_lons)
    
    # Créer la carte Folium
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=12,
        tiles='OpenStreetMap',
        control_scale=True
    )
    
    # Ajouter d'autres fonds de carte avec attributions
    folium.TileLayer(
        tiles='https://tiles.stadiamaps.com/tiles/stamen_terrain/{z}/{x}/{y}.jpg',
        attr='Map tiles by Stamen Design, under CC BY 3.0. Data by OpenStreetMap, under ODbL',
        name='Terrain'
    ).add_to(m)
    
    folium.TileLayer(
        tiles='CartoDB positron',
        name='CartoDB'
    ).add_to(m)
    
    # Créer les coordonnées pour la trace et les popups
    cum_dist = 0.0
    trace_coords = []
    segment_coords = []  # Pour la synchronisation et l'animation
    segment_times = []   # Pour l'animation temporelle
    
    # Groupe de features pour la trace
    feature_group = folium.FeatureGroup(name='Tracé colorisé par vent')
    
    cum_time = 0.0  # Temps cumulé en secondes
    
    for i, seg in enumerate(segments):
        lat1, lon1 = seg['lat1'], seg['lon1']
        lat2, lon2 = seg['lat2'], seg['lon2']
        
        # Coordonnées du segment
        coords = [[lat1, lon1], [lat2, lon2]]
        trace_coords.extend(coords)
        
        # Stocker les coordonnées pour la synchronisation (milieu du segment)
        mid_lat = (lat1 + lat2) / 2
        mid_lon = (lon1 + lon2) / 2
        segment_coords.append([mid_lat, mid_lon])
        
        # Stocker le temps pour l'animation
        seg_time = seg.get('time_s', 0)
        segment_times.append({
            'start': cum_time,
            'end': cum_time + seg_time,
            'lat': mid_lat,
            'lon': mid_lon,
            'distance_km': cum_dist + seg['distance'] / 2000.0
        })
        cum_time += seg_time
        
        # Couleur selon le vent
        color = get_wind_color(seg.get('wind_along', 0))
        
        # Distance cumulée au milieu du segment
        cum_dist_mid = cum_dist + seg['distance'] / 2000.0  # km
        
        # Créer le segment colorisé avec attribut data-segment-id
        folium.PolyLine(
            coords,
            color=color,
            weight=5,
            opacity=0.8,
            popup=folium.Popup(
                create_popup_content(seg, i, cum_dist_mid),
                max_width=300
            )
        ).add_to(feature_group)
        
        cum_dist += seg['distance'] / 1000.0
    
    feature_group.add_to(m)
    
    # Marqueurs de départ et arrivée
    folium.Marker(
        [segments[0]['lat1'], segments[0]['lon1']],
        popup='🏁 Départ',
        icon=folium.Icon(color='green', icon='play')
    ).add_to(m)
    
    folium.Marker(
        [segments[-1]['lat2'], segments[-1]['lon2']],
        popup='🏁 Arrivée',
        icon=folium.Icon(color='red', icon='stop')
    ).add_to(m)
    
    # Légende pour les couleurs de vent (positionnée à droite du profil d'altitude)
    legend_html = '''
    <div class="wind-legend">
        <p style="margin: 0 0 12px 0; font-weight: bold; font-size: 15px;">💨 Légende Vent</p>
        <p style="margin: 5px 0;"><span style="color: #8B0000;">█</span> Vent de face > 15 km/h</p>
        <p style="margin: 5px 0;"><span style="color: #DC143C;">█</span> Vent de face 10-15 km/h</p>
        <p style="margin: 5px 0;"><span style="color: #FF6347;">█</span> Vent de face 5-10 km/h</p>
        <p style="margin: 5px 0;"><span style="color: #FFA500;">█</span> Vent de face 2-5 km/h</p>
        <p style="margin: 5px 0;"><span style="color: #FFD700;">█</span> Vent faible ±2 km/h</p>
        <p style="margin: 5px 0;"><span style="color: #90EE90;">█</span> Vent de dos 2-5 km/h</p>
        <p style="margin: 5px 0;"><span style="color: #32CD32;">█</span> Vent de dos 5-10 km/h</p>
        <p style="margin: 5px 0;"><span style="color: #228B22;">█</span> Vent de dos 10-15 km/h</p>
        <p style="margin: 5px 0;"><span style="color: #006400;">█</span> Vent de dos > 15 km/h</p>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Contrôle des couches
    folium.LayerControl().add_to(m)
    
    # Plugin de mesure de distance
    plugins.MeasureControl(position='topleft', primary_length_unit='kilometers').add_to(m)
    
    # Plugin de plein écran
    plugins.Fullscreen(position='topleft').add_to(m)
    
    # Préparer les données pour le profil d'altitude (à intégrer avec Plotly)
    distances_km = [0]
    elevations_real = [segments[0].get('ele1', 0)]
    elevations_virtual = [segments[0].get('ele1', 0)]
    speeds_kmh = []
    wind_along_kmh = []
    
    cum_dist = 0.0
    cum_elev_virtual = 0.0
    
    for seg in segments:
        cum_dist += seg['distance'] / 1000.0
        distances_km.append(cum_dist)
        
        elevations_real.append(seg.get('ele2', 0))
        
        elev_virt_seg = seg.get('elevation_virtual_m', 0)
        cum_elev_virtual += elev_virt_seg
        elevations_virtual.append(seg.get('ele2', 0) + cum_elev_virtual)
        
        # Données supplémentaires pour l'animation
        speeds_kmh.append(seg.get('speed_m_s', 0) * 3.6)
        wind_along_kmh.append(seg.get('wind_along', 0) * 3.6)

    total_distance_km = distances_km[-1]
    if distance_from_finish:
        distances_display_km = [total_distance_km - dist for dist in distances_km]
        segment_distances_display_km = [
            total_distance_km - item['distance_km'] for item in segment_times
        ]
        x_axis_label = "Distance depuis l'arrivée (km)"
        popup_distance_label = "Distance restante"
    else:
        distances_display_km = distances_km
        segment_distances_display_km = [item['distance_km'] for item in segment_times]
        x_axis_label = 'Distance (km)'
        popup_distance_label = 'Distance'
    
    # Créer le HTML avec Plotly intégré pour le profil
    plotly_data = {
        'distances': distances_display_km,
        'elevations_real': elevations_real,
        'elevations_virtual': elevations_virtual,
        'segment_coords': segment_coords,
        'segment_times': segment_times,
        'segment_distances': segment_distances_display_km,
        'speeds_kmh': speeds_kmh,
        'wind_along_kmh': wind_along_kmh,
        'total_time_s': cum_time,
        'enable_animation': enable_animation,
        'x_axis_label': x_axis_label,
        'popup_distance_label': popup_distance_label,
        'distance_from_finish': bool(distance_from_finish),
    }
    
    # Sauvegarder la carte
    m.save(output_file)
    
    # Ajouter le profil Plotly avec synchronisation et animation
    _add_plotly_profile(output_file, plotly_data, title, segments)
    
    print(f"✅ Carte interactive créée : {output_file}")
    print(f"   - {len(segments)} segments tracés")
    print(f"   - Distance totale : {total_distance_km:.2f} km")
    print(f"   - Altitude : {min(elevations_real):.0f} - {max(elevations_real):.0f} m")
    print(f"   - Durée totale : {cum_time/60:.1f} min")
    if enable_animation:
        print(f"   - Animation temporelle activée")
    
    return output_file


def _add_plotly_profile(html_file: str, data: Dict, title: str, segments: List[Dict]):
    """
    Ajoute un profil d'altitude Plotly interactif dans le fichier HTML Folium.
    
    Fonctionnalités :
    - Synchronisation carte ↔ profil : clic/survol sur profil → marqueur sur carte
    - Animation temporelle avec slider pour rejouer le parcours
    - Panel de statistiques accessible via bouton flottant
    
    Parameters:
    -----------
    html_file : str
        Chemin du fichier HTML
    data : Dict
        Données de distance, altitude, coordonnées et temps
    title : str
        Titre du graphique
    segments : List[Dict]
        Liste des segments originaux pour générer les statistiques
    """
    
    # Lire le fichier HTML existant
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Injecter le viewport meta tag si absent
    if '<meta name="viewport"' not in html_content:
        html_content = html_content.replace(
            '<head>',
            '<head>\n    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">'
        )
    
    # Déterminer la hauteur du profil selon si l'animation est activée
    profile_height = 400 if data.get('enable_animation', True) else 350
    map_height = f"calc(100vh - {profile_height}px)"
    
    # Créer le script Plotly avec synchronisation et animation
    plotly_script = f"""
    <!-- Plotly CDN -->
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    
    <style>
    body {{
        margin: 0;
        padding: 0;
    }}
    #map {{
        height: {map_height} !important;
    }}
    #elevation-profile {{
        width: 100%;  /* Pleine largeur maintenant que la légende est en panel */
        height: {profile_height}px;
        position: fixed;
        bottom: 0;
        left: 0;
        background: white;
        border-top: 3px solid #333;
        z-index: 9998;
        box-shadow: 0 -2px 10px rgba(0,0,0,0.1);
    }}
    #animation-controls {{
        width: 100%;  /* Pleine largeur comme le profil */
        position: fixed;
        bottom: {profile_height}px;
        left: 0;
        background: linear-gradient(to bottom, rgba(255,255,255,0.95), rgba(255,255,255,1));
        padding: 10px 20px;
        border-top: 1px solid #ddd;
        z-index: 9999;
        display: {'flex' if data.get('enable_animation', True) else 'none'};
        align-items: center;
        gap: 15px;
        box-shadow: 0 -1px 5px rgba(0,0,0,0.05);
    }}
    #time-slider {{
        flex: 1;
        height: 8px;
        -webkit-appearance: none;
        background: #ddd;
        outline: none;
        border-radius: 4px;
    }}
    #time-slider::-webkit-slider-thumb {{
        -webkit-appearance: none;
        appearance: none;
        width: 18px;
        height: 18px;
        background: #4CAF50;
        cursor: pointer;
        border-radius: 50%;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }}
    #time-slider::-moz-range-thumb {{
        width: 18px;
        height: 18px;
        background: #4CAF50;
        cursor: pointer;
        border-radius: 50%;
        border: none;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }}
    .anim-button {{
        padding: 8px 16px;
        background: #4CAF50;
        color: white;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        font-size: 14px;
        font-weight: bold;
        transition: background 0.3s;
    }}
    .anim-button:hover {{
        background: #45a049;
    }}
    .anim-button:disabled {{
        background: #ccc;
        cursor: not-allowed;
    }}
    #time-display {{
        min-width: 150px;
        font-family: monospace;
        font-size: 14px;
        font-weight: bold;
        color: #333;
    }}
    
    /* Bouton flottant pour les statistiques */
    #stats-button {{
        position: fixed;
        top: 80px;
        right: 20px;
        width: 56px;
        height: 56px;
        background: #2196F3;
        color: white;
        border: none;
        border-radius: 50%;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        cursor: pointer;
        font-size: 24px;
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10000;
        transition: all 0.3s;
    }}
    #stats-button:hover {{
        background: #1976D2;
        transform: scale(1.05);
    }}
    
    /* 🎨 Bouton flottant pour la légende */
    #legend-button {{
        position: fixed;
        top: 150px;
        right: 20px;
        width: 56px;
        height: 56px;
        background: #FF9800;
        color: white;
        border: none;
        border-radius: 50%;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        cursor: pointer;
        font-size: 24px;
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10000;
        transition: all 0.3s;
    }}
    #legend-button:hover {{
        background: #F57C00;
        transform: scale(1.05);
    }}
    
    /* 📊 Panel de statistiques */
    #stats-panel {{
        position: fixed;
        left: -350px;
        top: 0;
        width: 350px;
        height: 100vh;
        background: white;
        box-shadow: 2px 0 15px rgba(0,0,0,0.3);
        z-index: 10001;
        overflow-y: auto;
        transition: left 0.3s ease-in-out;
    }}
    #stats-panel.open {{
        left: 0;
    }}
    #stats-close {{
        position: sticky;
        top: 0;
        right: 0;
        background: #f5f5f5;
        border: none;
        padding: 15px;
        cursor: pointer;
        font-size: 24px;
        width: 100%;
        text-align: right;
        border-bottom: 2px solid #ddd;
        z-index: 1;
    }}
    #stats-close:hover {{
        background: #e0e0e0;
    }}
    
    /* 🎨 Panel de légende */
    #legend-panel {{
        position: fixed;
        left: -350px;
        top: 0;
        width: 350px;
        height: 100vh;
        background: white;
        box-shadow: 2px 0 15px rgba(0,0,0,0.3);
        z-index: 10001;
        overflow-y: auto;
        transition: left 0.3s ease-in-out;
    }}
    #legend-panel.open {{
        left: 0;
    }}
    #legend-close {{
        position: sticky;
        top: 0;
        right: 0;
        background: #f5f5f5;
        border: none;
        padding: 15px;
        cursor: pointer;
        font-size: 24px;
        width: 100%;
        text-align: right;
        border-bottom: 2px solid #ddd;
        z-index: 1;
    }}
    #legend-close:hover {{
        background: #e0e0e0;
    }}
    
    .wind-legend-content {{
        padding: 15px;
        font-size: 13px;
    }}
    
    .wind-legend {{
        /* Masquée par défaut - accessible via bouton */
        display: none;
    }}
    
    /* 📱 ADAPTATION MOBILE PORTRAIT */
    @media only screen and (max-width: 768px) and (orientation: portrait) {{
        #map {{
            /* Utiliser dvh (dynamic viewport height) pour tenir compte des barres d'adresse */
            height: calc(100dvh - 240px - 50px) !important;
        }}
        
        #elevation-profile {{
            width: 100% !important;
            height: 240px !important;
            bottom: 0 !important;
        }}
        
        #animation-controls {{
            width: 100% !important;
            bottom: 240px !important;
            padding: 6px 8px !important;
            gap: 6px !important;
        }}
        
        #stats-button {{
            top: 70px !important;
            right: 15px !important;
            width: 48px !important;
            height: 48px !important;
            font-size: 20px !important;
        }}
        
        #legend-button {{
            top: 130px !important;
            right: 15px !important;
            width: 48px !important;
            height: 48px !important;
            font-size: 20px !important;
        }}
        
        #stats-panel {{
            width: 100% !important;
            left: -100% !important;
        }}
        #stats-panel.open {{
            left: 0 !important;
        }}
        
        #legend-panel {{
            width: 100% !important;
            left: -100% !important;
        }}
        #legend-panel.open {{
            left: 0 !important;
        }}
        
        .anim-button {{
            padding: 6px 10px !important;
            font-size: 12px !important;
        }}
        
        #time-display {{
            min-width: 100px !important;
            font-size: 12px !important;
        }}
    }}
    
    /* 📱 ADAPTATION MOBILE PAYSAGE (landscape) */
    @media only screen and (max-height: 600px) and (orientation: landscape) {{
        #map {{
            height: calc(100dvh - 160px - 45px) !important;
        }}
        
        #elevation-profile {{
            width: 100% !important;
            height: 160px !important;
            bottom: 0 !important;
        }}
        
        #animation-controls {{
            width: 100% !important;
            bottom: 160px !important;
            padding: 4px 6px !important;
            gap: 5px !important;
        }}
        
        #stats-button {{
            top: 10px !important;
            right: 10px !important;
            width: 44px !important;
            height: 44px !important;
            font-size: 18px !important;
        }}
        
        #legend-button {{
            top: 65px !important;
            right: 10px !important;
            width: 44px !important;
            height: 44px !important;
            font-size: 18px !important;
        }}
        
        #stats-panel {{
            width: 350px !important;
            left: -350px !important;
        }}
        #stats-panel.open {{
            left: 0 !important;
        }}
        
        #legend-panel {{
            width: 350px !important;
            left: -350px !important;
        }}
        #legend-panel.open {{
            left: 0 !important;
        }}
        
        .anim-button {{
            padding: 4px 8px !important;
            font-size: 11px !important;
        }}
        
        #time-display {{
            min-width: 80px !important;
            font-size: 11px !important;
        }}
        
        /* Masquer la légende en paysage mobile aussi */
        .wind-legend {{
            display: none !important;
        }}
    }}
    
    /* 📱 TRÈS PETITS ÉCRANS PORTRAIT */
    @media only screen and (max-width: 480px) and (orientation: portrait) {{
        #map {{
            height: calc(100dvh - 220px - 45px) !important;
        }}
        
        #elevation-profile {{
            height: 220px !important;
        }}
        
        #animation-controls {{
            bottom: 220px !important;
            padding: 5px 6px !important;
            flex-wrap: wrap !important;
        }}
        
        #stats-button {{
            top: 60px !important;
            right: 10px !important;
            width: 44px !important;
            height: 44px !important;
            font-size: 18px !important;
        }}
        
        #legend-button {{
            top: 115px !important;
            right: 10px !important;
            width: 44px !important;
            height: 44px !important;
            font-size: 18px !important;
        }}
        
        .anim-button {{
            padding: 5px 8px !important;
            font-size: 11px !important;
        }}
        
        #time-display {{
            font-size: 11px !important;
            min-width: 90px !important;
        }}
    }}
    </style>
    
    <!-- Bouton flottant pour les statistiques -->
    <button id="stats-button" title="Afficher les statistiques">📊</button>
    
    <!-- Bouton flottant pour la légende -->
    <button id="legend-button" title="Afficher la légende vent">🎨</button>
    
    <!-- Panel de statistiques -->
    <div id="stats-panel">
        <button id="stats-close">✖</button>
        {_generate_statistics_html(segments)}
    </div>
    
    <!-- Panel de légende -->
    <div id="legend-panel">
        <button id="legend-close">✖</button>
        <div class="wind-legend-content">
            <h3 style="margin: 0 0 15px 0; color: #333; border-bottom: 2px solid #FF9800; padding-bottom: 8px;">💨 Légende Vent</h3>
            <p style="margin: 8px 0;"><span style="color: #8B0000; font-size: 20px;">█</span> Vent de face > 15 km/h</p>
            <p style="margin: 8px 0;"><span style="color: #DC143C; font-size: 20px;">█</span> Vent de face 10-15 km/h</p>
            <p style="margin: 8px 0;"><span style="color: #FF6347; font-size: 20px;">█</span> Vent de face 5-10 km/h</p>
            <p style="margin: 8px 0;"><span style="color: #FFA500; font-size: 20px;">█</span> Vent de face 2-5 km/h</p>
            <p style="margin: 8px 0;"><span style="color: #FFD700; font-size: 20px;">█</span> Vent faible ±2 km/h</p>
            <p style="margin: 8px 0;"><span style="color: #90EE90; font-size: 20px;">█</span> Vent de dos 2-5 km/h</p>
            <p style="margin: 8px 0;"><span style="color: #32CD32; font-size: 20px;">█</span> Vent de dos 5-10 km/h</p>
            <p style="margin: 8px 0;"><span style="color: #228B22; font-size: 20px;">█</span> Vent de dos 10-15 km/h</p>
            <p style="margin: 8px 0;"><span style="color: #006400; font-size: 20px;">█</span> Vent de dos > 15 km/h</p>
        </div>
    </div>
    
    <!-- Conteneur pour les contrôles d'animation -->
    <div id="animation-controls">
        <button id="play-btn" class="anim-button">▶ Lecture</button>
        <button id="pause-btn" class="anim-button" style="display:none;">⏸ Pause</button>
        <input type="range" id="time-slider" min="0" max="{int(data.get('total_time_s', 0))}" value="0" step="1">
        <div id="time-display">00:00 / {int(data.get('total_time_s', 0) // 60):02d}:{int(data.get('total_time_s', 0) % 60):02d}</div>
        <button id="reset-btn" class="anim-button">⏮ Début</button>
    </div>
    
    <!-- Conteneur pour le profil -->
    <div id="elevation-profile"></div>
    
    <script>
    // Variables globales
    var leafletMap = null;
    var currentMarker = null;
    var animationRunning = false;
    var animationInterval = null;
    
    // 📊 Gestion du panel de statistiques
    var statsButton = document.getElementById('stats-button');
    var statsPanel = document.getElementById('stats-panel');
    var statsClose = document.getElementById('stats-close');
    
    statsButton.addEventListener('click', function() {{
        statsPanel.classList.toggle('open');
        // Fermer la légende si ouverte
        legendPanel.classList.remove('open');
    }});
    
    statsClose.addEventListener('click', function() {{
        statsPanel.classList.remove('open');
    }});
    
    // 🎨 Gestion du panel de légende
    var legendButton = document.getElementById('legend-button');
    var legendPanel = document.getElementById('legend-panel');
    var legendClose = document.getElementById('legend-close');
    
    legendButton.addEventListener('click', function() {{
        legendPanel.classList.toggle('open');
        // Fermer les stats si ouvertes
        statsPanel.classList.remove('open');
    }});
    
    legendClose.addEventListener('click', function() {{
        legendPanel.classList.remove('open');
    }});
    
    // Fermer les panels en cliquant en dehors
    document.addEventListener('click', function(e) {{
        if (!statsPanel.contains(e.target) && e.target !== statsButton) {{
            statsPanel.classList.remove('open');
        }}
        if (!legendPanel.contains(e.target) && e.target !== legendButton) {{
            legendPanel.classList.remove('open');
        }}
    }});
    
    // Fonction pour trouver la carte Leaflet dans les variables globales
    function findLeafletMap() {{
        // Méthode 1: Chercher dans les variables globales commençant par 'map_'
        for (var key in window) {{
            if (key.startsWith('map_') && window[key] && window[key]._container) {{
                console.log('✅ Carte Leaflet trouvée via:', key);
                return window[key];
            }}
        }}
        
        // Méthode 2: Chercher via le conteneur DOM
        var mapContainer = document.getElementById('map');
        if (mapContainer && mapContainer._leaflet_id) {{
            var mapId = mapContainer._leaflet_id;
            for (var key in window) {{
                if (window[key] && window[key]._leaflet_id === mapId) {{
                    console.log('✅ Carte Leaflet trouvée via container ID');
                    return window[key];
                }}
            }}
        }}
        
        return null;
    }}
    
    // Attendre que Leaflet et la carte soient chargés
    function waitForMap(callback) {{
        if (typeof L === 'undefined') {{
            console.log('⏳ Attente de Leaflet...');
            setTimeout(function() {{ waitForMap(callback); }}, 100);
            return;
        }}
        
        var map = findLeafletMap();
        if (map) {{
            leafletMap = map;
            console.log('✅ Carte prête pour synchronisation');
            callback();
        }} else {{
            setTimeout(function() {{ waitForMap(callback); }}, 100);
        }}
    }}
    
    // Données du parcours
    var distances = {json.dumps(data['distances'])};
    var elevationsReal = {json.dumps(data['elevations_real'])};
    var elevationsVirtual = {json.dumps(data['elevations_virtual'])};
    var segmentCoords = {json.dumps(data['segment_coords'])};
    var segmentTimes = {json.dumps(data['segment_times'])};
    var segmentDistances = {json.dumps(data['segment_distances'])};
    var speedsKmh = {json.dumps(data.get('speeds_kmh', []))};
    var windAlongKmh = {json.dumps(data.get('wind_along_kmh', []))};
    var totalTimeS = {data.get('total_time_s', 0)};
    var xAxisLabel = {json.dumps(data.get('x_axis_label', 'Distance (km)'))};
    var popupDistanceLabel = {json.dumps(data.get('popup_distance_label', 'Distance'))};
    
    // Fonction pour créer/déplacer le marqueur de position sur la carte
    function updateMarkerOnMap(lat, lon, distanceKm, speed, windAlong) {{
        if (!leafletMap) {{
            console.warn('⚠️ Carte non disponible');
            return;
        }}
        
        if (typeof L === 'undefined') {{
            console.warn('⚠️ Leaflet non chargé');
            return;
        }}
        
        var popupContent = '<div style="font-family: Arial; min-width: 180px; padding: 5px;">' +
                          '<h4 style="margin: 0 0 10px 0; color: #FF4500;">📍 Position actuelle</h4>' +
                          '<p style="margin: 4px 0; font-size: 13px;"><b>' + popupDistanceLabel + ':</b> ' + distanceKm.toFixed(2) + ' km</p>';
        
        if (speed !== undefined && !isNaN(speed)) {{
            popupContent += '<p style="margin: 4px 0; font-size: 13px;"><b>Vitesse:</b> ' + speed.toFixed(1) + ' km/h</p>';
        }}
        if (windAlong !== undefined && !isNaN(windAlong)) {{
            var windType = windAlong > 0 ? '🔴 vent de face' : '🟢 vent de dos';
            popupContent += '<p style="margin: 4px 0; font-size: 13px;"><b>Vent:</b> ' + Math.abs(windAlong).toFixed(1) + ' km/h ' + windType + '</p>';
        }}
        popupContent += '</div>';
        
        if (currentMarker) {{
            // Déplacer le marqueur existant
            currentMarker.setLatLng([lat, lon]);
            currentMarker.setPopupContent(popupContent);
        }} else {{
            // Créer un nouveau marqueur avec icône personnalisée
            var pulsingIcon = L.divIcon({{
                className: 'pulsing-marker',
                html: '<div style="' +
                      'background: #FF4500;' +
                      'width: 20px;' +
                      'height: 20px;' +
                      'border-radius: 50%;' +
                      'border: 4px solid white;' +
                      'box-shadow: 0 0 0 0 rgba(255, 69, 0, 0.8), 0 2px 8px rgba(0,0,0,0.4);' +
                      'animation: pulse 2s infinite;' +
                      '"></div>' +
                      '<style>' +
                      '@keyframes pulse {{' +
                      '0% {{ box-shadow: 0 0 0 0 rgba(255, 69, 0, 0.7), 0 2px 8px rgba(0,0,0,0.4); }}' +
                      '50% {{ box-shadow: 0 0 0 15px rgba(255, 69, 0, 0), 0 2px 8px rgba(0,0,0,0.4); }}' +
                      '100% {{ box-shadow: 0 0 0 0 rgba(255, 69, 0, 0), 0 2px 8px rgba(0,0,0,0.4); }}' +
                      '}}' +
                      '</style>',
                iconSize: [28, 28],
                iconAnchor: [14, 14]
            }});
            
            currentMarker = L.marker([lat, lon], {{
                icon: pulsingIcon,
                zIndexOffset: 10000
            }}).addTo(leafletMap);
            
            currentMarker.bindPopup(popupContent);
            console.log('✅ Marqueur créé à', lat, lon);
        }}
        
        // Pas de recentrage automatique pendant l'animation - l'utilisateur garde le contrôle
        // Le marqueur suit simplement le parcours sur la carte visible
    }}
    
    // Fonction pour trouver le segment à un temps donné
    function findSegmentAtTime(timeS) {{
        for (var i = 0; i < segmentTimes.length; i++) {{
            if (timeS >= segmentTimes[i].start && timeS <= segmentTimes[i].end) {{
                return i;
            }}
        }}
        return segmentTimes.length - 1;
    }}
    
    // Fonction pour mettre à jour la position selon le temps
    function updatePositionAtTime(timeS) {{
        var segIdx = findSegmentAtTime(timeS);
        if (segIdx < 0 || segIdx >= segmentCoords.length) return;
        
        var coord = segmentCoords[segIdx];
        var dist = segmentDistances[segIdx];
        var speed = speedsKmh[segIdx];
        var wind = windAlongKmh[segIdx];
        
        updateMarkerOnMap(coord[0], coord[1], dist, speed, wind);
        
        // Mettre à jour la ligne verticale sur le graphique
        if (typeof Plotly !== 'undefined') {{
            var xPos = dist;
            Plotly.relayout('elevation-profile', {{
                shapes: [{{
                    type: 'line',
                    x0: xPos,
                    x1: xPos,
                    y0: 0,
                    y1: 1,
                    yref: 'paper',
                    line: {{
                        color: '#FF4500',
                        width: 2,
                        dash: 'dot'
                    }}
                }}]
            }});
        }}
    }}
    
    // Contrôles d'animation
    document.addEventListener('DOMContentLoaded', function() {{
        var playBtn = document.getElementById('play-btn');
        var pauseBtn = document.getElementById('pause-btn');
        var resetBtn = document.getElementById('reset-btn');
        var timeSlider = document.getElementById('time-slider');
        var timeDisplay = document.getElementById('time-display');
        
        function formatTime(seconds) {{
            var mins = Math.floor(seconds / 60);
            var secs = Math.floor(seconds % 60);
            return mins.toString().padStart(2, '0') + ':' + secs.toString().padStart(2, '0');
        }}
        
        function updateTimeDisplay(currentTime) {{
            var totalMins = Math.floor(totalTimeS / 60);
            var totalSecs = Math.floor(totalTimeS % 60);
            timeDisplay.textContent = formatTime(currentTime) + ' / ' + 
                                     totalMins.toString().padStart(2, '0') + ':' + 
                                     totalSecs.toString().padStart(2, '0');
        }}
        
        // Lecture
        playBtn.addEventListener('click', function() {{
            if (!animationRunning) {{
                animationRunning = true;
                playBtn.style.display = 'none';
                pauseBtn.style.display = 'inline-block';
                
                animationInterval = setInterval(function() {{
                    var currentTime = parseInt(timeSlider.value);
                    if (currentTime >= totalTimeS) {{
                        // Fin de l'animation
                        clearInterval(animationInterval);
                        animationRunning = false;
                        playBtn.style.display = 'inline-block';
                        pauseBtn.style.display = 'none';
                        return;
                    }}
                    
                    currentTime += 1;  // Avancer de 1 seconde
                    timeSlider.value = currentTime;
                    updateTimeDisplay(currentTime);
                    updatePositionAtTime(currentTime);
                }}, 50);  // Mise à jour toutes les 50ms (vitesse x20)
            }}
        }});
        
        // Pause
        pauseBtn.addEventListener('click', function() {{
            if (animationRunning) {{
                clearInterval(animationInterval);
                animationRunning = false;
                playBtn.style.display = 'inline-block';
                pauseBtn.style.display = 'none';
            }}
        }});
        
        // Reset
        resetBtn.addEventListener('click', function() {{
            if (animationRunning) {{
                clearInterval(animationInterval);
                animationRunning = false;
                playBtn.style.display = 'inline-block';
                pauseBtn.style.display = 'none';
            }}
            timeSlider.value = 0;
            updateTimeDisplay(0);
            updatePositionAtTime(0);
        }});
        
        // Slider manuel
        timeSlider.addEventListener('input', function() {{
            var currentTime = parseInt(this.value);
            updateTimeDisplay(currentTime);
            updatePositionAtTime(currentTime);
        }});
    }});
    
    // Attendre que Plotly soit chargé
    window.addEventListener('load', function() {{
        // 📱 Fonction pour détecter si on est sur mobile (incluant paysage)
        function isMobileDevice() {{
            // Détection basée sur taille ET capacités tactiles
            var isTouchDevice = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0);
            var isSmallWidth = window.innerWidth <= 768;
            var isLandscapeMobile = window.innerHeight <= 600 && window.innerWidth <= 1024;
            return isTouchDevice && (isSmallWidth || isLandscapeMobile);
        }}
        
        var traceReal = {{
            customdata: distances.map(function(v) {{
                return popupDistanceLabel + ' : ' + v.toFixed(2) + ' km';
            }}),
            x: distances,
            y: elevationsReal,
            mode: 'lines',
            name: 'Altitude réelle',
            line: {{color: 'sienna', width: 2}},
            fill: 'tozeroy',
            fillcolor: 'rgba(210, 180, 140, 0.3)',
            hovertemplate: '<b>%{{customdata}}</b><br><b>Altitude réelle :</b> %{{y:.0f}} m<extra></extra>'
        }};
        
        var traceVirtual = {{
            x: distances,
            y: elevationsVirtual,
            mode: 'lines',
            name: 'Altitude virtuelle (effet vent)',
            line: {{color: 'steelblue', width: 2, dash: 'dash'}},
            hovertemplate: '<b>Altitude virtuelle:</b> %{{y:.0f}} m<extra></extra>'
        }};
        
        var layout = {{
            title: {{
                text: 'Profil d\\'altitude : réel vs virtuel (effet vent) - Cliquez pour localiser sur la carte',
                font: {{size: 14}}
            }},
            xaxis: {{
                title: xAxisLabel,
                gridcolor: '#e0e0e0',
                automargin: false,
                hoverformat: '.2f',
                autorange: {'"reversed"' if data.get('distance_from_finish') else 'true'}
            }},
            yaxis: {{
                title: 'Altitude (m)',
                gridcolor: '#e0e0e0',
                automargin: false
            }},
            margin: {{l: 60, r: 5, t: 50, b: 50}},  // Marges desktop (r=5 car légende en panel)
            // Use non-unified hover to avoid the extra unlabeled x-value header.
            hovermode: 'x',
            showlegend: true,
            legend: {{
                x: 0.01,
                y: 0.01,  // En bas à gauche au lieu de en haut
                xanchor: 'left',
                yanchor: 'bottom',
                bgcolor: 'rgba(255, 255, 255, 0.8)',
                bordercolor: '#333',
                borderwidth: 1
            }},
            plot_bgcolor: '#fafafa',
            paper_bgcolor: 'white',
            // 📱 Désactiver le drag sur mobile (portrait ET paysage)
            dragmode: isMobileDevice() ? false : 'zoom'
        }};
        
        var config = {{
            responsive: true,
            displayModeBar: !isMobileDevice(),  // Masquer toolbar sur mobile
            modeBarButtonsToRemove: ['lasso2d', 'select2d'],
            displaylogo: false,
            // 📱 Désactiver le zoom mais GARDER les événements click/hover
            doubleClick: false,
            scrollZoom: false
        }};
        
        Plotly.newPlot('elevation-profile', [traceReal, traceVirtual], layout, config);
        
        // 📱 Empêcher le zoom sur mobile (portrait ET paysage)
        var plotlyDiv = document.getElementById('elevation-profile');
        
        if (isMobileDevice()) {{
            // Empêcher le pinch-to-zoom (2+ doigts)
            plotlyDiv.addEventListener('touchstart', function(e) {{
                if (e.touches.length > 1) {{
                    e.preventDefault();
                }}
            }}, {{ passive: false }});
            
            // Empêcher le menu contextuel long press (mais pas le tap simple)
            plotlyDiv.addEventListener('contextmenu', function(e) {{
                e.preventDefault();
            }});
            
            // Empêcher le zoom par geste iOS
            plotlyDiv.addEventListener('gesturestart', function(e) {{
                e.preventDefault();
            }});
        }}
        
        // 📱 Adapter les marges pour mobile
        if (isMobileDevice()) {{
            Plotly.relayout('elevation-profile', {{
                'margin.l': 35,
                'margin.r': 5,
                'margin.t': 30,
                'margin.b': 35,
                'xaxis.title.font.size': 10,
                'yaxis.title.font.size': 10,
                'title.font.size': 11
            }});
        }}
        
        // 📱 Ré-adapter lors de la rotation d'écran
        window.addEventListener('resize', function() {{
            Plotly.Plots.resize('elevation-profile');
            
            // Redétecter si mobile après rotation
            var isMobileNow = isMobileDevice();
            Plotly.relayout('elevation-profile', {{
                'dragmode': isMobileNow ? false : 'zoom'
            }});
            
            if (isMobileNow) {{
                Plotly.relayout('elevation-profile', {{
                    'margin.l': 35,
                    'margin.r': 5,
                    'margin.t': 30,
                    'margin.b': 35
                }});
            }} else {{
                Plotly.relayout('elevation-profile', {{
                    'margin.l': 60,
                    'margin.r': 40,
                    'margin.t': 50,
                    'margin.b': 50
                }});
            }}
        }});
        
        // Synchronisation : clic sur le profil → marqueur sur la carte
        var profileDiv = document.getElementById('elevation-profile');
        
        profileDiv.on('plotly_click', function(data) {{
            console.log('🖱️ Clic sur profil détecté');
            if (data.points && data.points.length > 0) {{
                var distanceKm = data.points[0].x;
                console.log('📍 Distance cliquée:', distanceKm.toFixed(2), 'km');
                
                // Trouver le segment le plus proche
                var closestSegIdx = 0;
                var minDiff = Math.abs(segmentDistances[0] - distanceKm);
                
                for (var i = 1; i < segmentTimes.length; i++) {{
                    var diff = Math.abs(segmentDistances[i] - distanceKm);
                    if (diff < minDiff) {{
                        minDiff = diff;
                        closestSegIdx = i;
                    }}
                }}
                
                console.log('🎯 Segment trouvé:', closestSegIdx);
                var coord = segmentCoords[closestSegIdx];
                var speed = speedsKmh[closestSegIdx];
                var wind = windAlongKmh[closestSegIdx];
                
                waitForMap(function() {{
                    updateMarkerOnMap(coord[0], coord[1], distanceKm, speed, wind);
                    if (currentMarker && leafletMap) {{
                        currentMarker.openPopup();
                        leafletMap.setView([coord[0], coord[1]], leafletMap.getZoom());
                        console.log('✅ Marqueur créé/déplacé et popup ouvert');
                    }}
                }});
            }}
        }});
        
        // Survol du profil pour prévisualisation
        profileDiv.on('plotly_hover', function(data) {{
            if (data.points && data.points.length > 0) {{
                var distanceKm = data.points[0].x;
                
                // Trouver le segment le plus proche
                var closestSegIdx = 0;
                var minDiff = Math.abs(segmentDistances[0] - distanceKm);
                
                for (var i = 1; i < segmentTimes.length; i++) {{
                    var diff = Math.abs(segmentDistances[i] - distanceKm);
                    if (diff < minDiff) {{
                        minDiff = diff;
                        closestSegIdx = i;
                    }}
                }}
                
                var coord = segmentCoords[closestSegIdx];
                var speed = speedsKmh[closestSegIdx];
                var wind = windAlongKmh[closestSegIdx];
                
                waitForMap(function() {{
                    updateMarkerOnMap(coord[0], coord[1], distanceKm, speed, wind);
                }});
            }}
        }});
        
        // Redimensionner lors du changement de taille de fenêtre
        window.addEventListener('resize', function() {{
            Plotly.Plots.resize('elevation-profile');
        }});
        
        // Initialiser la carte après chargement complet
        console.log('🚀 Initialisation de la synchronisation carte-profil...');
        waitForMap(function() {{
            console.log('✅ Synchronisation activée - Cliquez sur le profil pour localiser');
            // Test de création du marqueur au premier point
            if (segmentCoords.length > 0 && speedsKmh.length > 0) {{
                var firstCoord = segmentCoords[0];
                var firstSpeed = speedsKmh[0];
                var firstWind = windAlongKmh[0];
                updateMarkerOnMap(firstCoord[0], firstCoord[1], segmentDistances[0], firstSpeed, firstWind);
                console.log('✅ Marqueur initial créé au point de départ');
            }}
        }});
    }});
    </script>
    """
    
    # Insérer avant la balise </body>
    html_content = html_content.replace('</body>', plotly_script + '\n</body>')
    
    # Réécrire le fichier
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_content)


if __name__ == "__main__":
    print("Module interactive_map.py - Visualisation interactive des parcours cyclistes")
    print("Utilisation: from interactive_map import create_interactive_map")
