# -*- coding: utf-8 -*-
"""
Interactive route visualization module with wind analysis.
Generates an HTML page with a Folium map and interactive elevation profiles.
"""

import folium
from folium import plugins
import numpy as np
from typing import List, Dict, Literal, Optional
import json
import logging
import locale
import os
from datetime import datetime, timedelta


logger = logging.getLogger(__name__)


def _detect_output_lang() -> str:
    """Detect output language: OUTPUT_LANG env var, then OS locale, default EN."""
    lang = os.environ.get("OUTPUT_LANG", "").strip().lower()
    if lang.startswith("fr"):
        return "fr"
    if lang.startswith("en"):
        return "en"

    loc = (locale.getdefaultlocale()[0] or "").lower()
    if loc.startswith("fr"):
        return "fr"
    return "en"


_UI_I18N = {
    "fr": {
        "page_title_default": "Analyse Interactive du Parcours Cycliste",
        "error_empty_segments": "La liste de segments est vide",
        "feature_group_name": "Tracé colorisé par vent",
        "start_marker": "🏁 Départ",
        "finish_marker": "🏁 Arrivée",
        "start_marker_short": "Départ",
        "finish_marker_short": "Arrivée",
        "start_marker_badge_letter": "D",
        "finish_marker_badge_letter": "A",
        "xaxis_from_finish": "Distance depuis l'arrivée (km)",
        "xaxis_distance": "Distance (km)",
        "distance_label_remaining": "Distance restante",
        "distance_label": "Distance",
        "stats_panel_title": "📊 Statistiques du parcours",
        "sec_distance_time": "📏 Distance et temps",
        "label_total_distance": "Distance totale:",
        "label_total_time": "Temps total:",
        "label_avg_speed": "Vitesse moyenne:",
        "sec_wind": "💨 Vent (TWS et TWD)",
        "label_avg": "Moyen:",
        "label_direction": "Direction:",
        "sec_gusts": "💨 Rafales",
        "label_average": "Moyenne:",
        "label_min_max": "Min - Max:",
        "sec_slope": "⛰️ Pente terrain",
        "label_mean": "Moyenne:",
        "label_deniv_pos": "Dénivelé +:",
        "label_deniv_neg": "Dénivelé -:",
        "sec_virtual": "🌬️ Dénivelé virtuel (vent)",
        "label_positive": "Positif:",
        "label_negative": "Négatif:",
        "sec_along": "🎯 Vent le long de la trajectoire",
        "label_headwind": "❌ Vent de face:",
        "label_tailwind": "✅ Vent de dos:",
        "popup_wind_head": "🔴 Vent de face",
        "popup_wind_tail": "🟢 Vent de dos",
        "popup_segment": "📍 Segment",
        "popup_km": "km",
        "popup_sec_wind": "💨 Vent",
        "popup_tws": "Vitesse vent (TWS)",
        "popup_gusts": "Rafales",
        "popup_sec_slope": "⛰️ Pente",
        "popup_terrain": "Terrain",
        "popup_virtual": "Virtuelle (vent)",
        "popup_effective": "Effective",
        "popup_sec_perf": "🚴 Performance",
        "popup_speed": "Vitesse",
        "popup_distance": "Distance",
        "popup_altitude": "Altitude",
        "btn_stats_title": "Afficher les statistiques",
        "btn_legend_title": "Afficher la légende vent",
        "legend_title": "💨 Légende Vent",
        "legend_head_gt15": "Vent de face > 15 km/h",
        "legend_head_10_15": "Vent de face 10-15 km/h",
        "legend_head_5_10": "Vent de face 5-10 km/h",
        "legend_head_2_5": "Vent de face 2-5 km/h",
        "legend_weak": "Vent faible ±2 km/h",
        "legend_tail_2_5": "Vent de dos 2-5 km/h",
        "legend_tail_5_10": "Vent de dos 5-10 km/h",
        "legend_tail_10_15": "Vent de dos 10-15 km/h",
        "legend_tail_gt15": "Vent de dos > 15 km/h",
        "btn_play": "▶ Lecture",
        "btn_pause": "⏸ Pause",
        "btn_reset": "⏮ Début",
        "arrival_time_label": "Heure arrivée",
        "popup_current_position": "📍 Position actuelle",
        "popup_passage_time_label": "Heure de passage",
        "popup_elapsed_time_label": "Temps écoulé",
        "popup_speed_label": "Vitesse",
        "popup_wind_label": "Vent",
        "popup_wind_head_short": "🔴 vent de face",
        "popup_wind_tail_short": "🟢 vent de dos",
        "trace_real": "Altitude réelle",
        "trace_virtual": "Altitude virtuelle (effet vent)",
        "hover_distance": "Distance",
        "hover_real_altitude": "Altitude réelle",
        "hover_virtual_altitude": "Altitude virtuelle",
        "profile_title": "Profil d'altitude : réel vs virtuel (effet vent) - Cliquez pour localiser sur la carte",
        "yaxis_altitude": "Altitude (m)",
    },
    "en": {
        "page_title_default": "Interactive Cycling Route Analysis",
        "error_empty_segments": "Segment list is empty",
        "feature_group_name": "Wind-colored route",
        "start_marker": "🏁 Start",
        "finish_marker": "🏁 Finish",
        "start_marker_short": "Start",
        "finish_marker_short": "Finish",
        "start_marker_badge_letter": "S",
        "finish_marker_badge_letter": "F",
        "xaxis_from_finish": "Distance to finish (km)",
        "xaxis_distance": "Distance (km)",
        "distance_label_remaining": "Remaining distance",
        "distance_label": "Distance",
        "stats_panel_title": "📊 Route statistics",
        "sec_distance_time": "📏 Distance and time",
        "label_total_distance": "Total distance:",
        "label_total_time": "Total time:",
        "label_avg_speed": "Average speed:",
        "sec_wind": "💨 Wind (TWS and TWD)",
        "label_avg": "Average:",
        "label_direction": "Direction:",
        "sec_gusts": "💨 Gusts",
        "label_average": "Average:",
        "label_min_max": "Min - Max:",
        "sec_slope": "⛰️ Terrain slope",
        "label_mean": "Average:",
        "label_deniv_pos": "Elevation gain:",
        "label_deniv_neg": "Elevation loss:",
        "sec_virtual": "🌬️ Virtual elevation (wind)",
        "label_positive": "Positive:",
        "label_negative": "Negative:",
        "sec_along": "🎯 Wind along trajectory",
        "label_headwind": "❌ Headwind:",
        "label_tailwind": "✅ Tailwind:",
        "popup_wind_head": "🔴 Headwind",
        "popup_wind_tail": "🟢 Tailwind",
        "popup_segment": "📍 Segment",
        "popup_km": "km",
        "popup_sec_wind": "💨 Wind",
        "popup_tws": "Wind speed (TWS)",
        "popup_gusts": "Gusts",
        "popup_sec_slope": "⛰️ Slope",
        "popup_terrain": "Terrain",
        "popup_virtual": "Virtual (wind)",
        "popup_effective": "Effective",
        "popup_sec_perf": "🚴 Performance",
        "popup_speed": "Speed",
        "popup_distance": "Distance",
        "popup_altitude": "Altitude",
        "btn_stats_title": "Show statistics",
        "btn_legend_title": "Show wind legend",
        "legend_title": "💨 Wind legend",
        "legend_head_gt15": "Headwind > 15 km/h",
        "legend_head_10_15": "Headwind 10-15 km/h",
        "legend_head_5_10": "Headwind 5-10 km/h",
        "legend_head_2_5": "Headwind 2-5 km/h",
        "legend_weak": "Light wind ±2 km/h",
        "legend_tail_2_5": "Tailwind 2-5 km/h",
        "legend_tail_5_10": "Tailwind 5-10 km/h",
        "legend_tail_10_15": "Tailwind 10-15 km/h",
        "legend_tail_gt15": "Tailwind > 15 km/h",
        "btn_play": "▶ Play",
        "btn_pause": "⏸ Pause",
        "btn_reset": "⏮ Start",
        "arrival_time_label": "Arrival time",
        "popup_current_position": "📍 Current position",
        "popup_passage_time_label": "Passage time",
        "popup_elapsed_time_label": "Elapsed time",
        "popup_speed_label": "Speed",
        "popup_wind_label": "Wind",
        "popup_wind_head_short": "🔴 headwind",
        "popup_wind_tail_short": "🟢 tailwind",
        "trace_real": "Real altitude",
        "trace_virtual": "Virtual altitude (wind effect)",
        "hover_distance": "Distance",
        "hover_real_altitude": "Real altitude",
        "hover_virtual_altitude": "Virtual altitude",
        "profile_title": "Altitude profile: real vs virtual (wind effect) - Click to locate on map",
        "yaxis_altitude": "Altitude (m)",
    },
}


def _ui_text(key: str) -> str:
    lang = _detect_output_lang()
    return _UI_I18N.get(lang, _UI_I18N["en"]).get(key, _UI_I18N["en"].get(key, key))


def _resolve_arrival_time(segments: List[Dict]) -> Optional[datetime]:
    """Return the most reliable arrival timestamp for the route.

    Prefer the actual end timestamp of the last segment when available, then fall
    back to the first segment start plus the cumulated duration.
    """
    for seg in reversed(segments):
        gpxtime_end = seg.get("gpxtime_end")
        if isinstance(gpxtime_end, datetime):
            return gpxtime_end

    route_start_dt = None
    for seg in segments:
        gpxtime_start = seg.get("gpxtime_start")
        if isinstance(gpxtime_start, datetime):
            route_start_dt = gpxtime_start
            break

    if route_start_dt is None:
        return None

    total_time_s = sum(seg.get("time_s", 0) for seg in segments)
    if total_time_s <= 0:
        return None

    return route_start_dt + timedelta(seconds=total_time_s)


def _generate_statistics_html(segments: List[Dict], ui: Optional[Dict[str, str]] = None) -> str:
    """
    Generate route statistics HTML for display in the panel.

    Parameters:
    -----------
    segments : List[Dict]
        List of segments with simulation data

    Returns:
    --------
    str : Statistics HTML
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

    if ui is None:
        ui = _UI_I18N.get(_detect_output_lang(), _UI_I18N["en"])

    # Générer le HTML
    html = f"""
    <div style="padding: 15px; font-family: Arial, sans-serif; font-size: 13px;">
        <h3 style="margin: 0 0 15px 0; color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 8px;">{ui['stats_panel_title']}</h3>

        <div style="margin-bottom: 15px;">
            <h4 style="margin: 10px 0 8px 0; color: #555;">{ui['sec_distance_time']}</h4>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 4px 0;">{ui['label_total_distance']}</td><td style="text-align: right; font-weight: bold;">{total_distance:.2f} km</td></tr>
                <tr><td style="padding: 4px 0;">{ui['label_total_time']}</td><td style="text-align: right; font-weight: bold;">{int(total_time//60)}h{int(total_time%60):02d}min</td></tr>
                <tr><td style="padding: 4px 0;">{ui['label_avg_speed']}</td><td style="text-align: right; font-weight: bold;">{avg_speed:.2f} km/h</td></tr>
            </table>
        </div>

        <div style="margin-bottom: 15px;">
            <h4 style="margin: 10px 0 8px 0; color: #555;">{ui['sec_wind']}</h4>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 4px 0;">{ui['label_avg']}</td><td style="text-align: right; font-weight: bold;">{avg_tws:.2f} km/h</td></tr>
                <tr><td style="padding: 4px 0;">{ui['label_direction']}</td><td style="text-align: right; font-weight: bold;">{avg_twd_deg:.0f}° ({twd_text})</td></tr>
            </table>
        </div>

        <div style="margin-bottom: 15px;">
            <h4 style="margin: 10px 0 8px 0; color: #555;">{ui['sec_gusts']}</h4>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 4px 0;">{ui['label_average']}</td><td style="text-align: right; font-weight: bold;">{avg_gust:.2f} km/h</td></tr>
                <tr><td style="padding: 4px 0;">{ui['label_min_max']}</td><td style="text-align: right; font-weight: bold;">{min_gust:.1f} - {max_gust:.1f} km/h</td></tr>
            </table>
        </div>

        <div style="margin-bottom: 15px;">
            <h4 style="margin: 10px 0 8px 0; color: #555;">{ui['sec_slope']}</h4>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 4px 0;">{ui['label_mean']}</td><td style="text-align: right; font-weight: bold;">{avg_slope:.2f} %</td></tr>
                <tr><td style="padding: 4px 0;">{ui['label_min_max']}</td><td style="text-align: right; font-weight: bold;">{min_slope:.1f} - {max_slope:.1f} %</td></tr>
                <tr><td style="padding: 4px 0;">{ui['label_deniv_pos']}</td><td style="text-align: right; font-weight: bold;">{deniv_pos:.0f} m</td></tr>
                <tr><td style="padding: 4px 0;">{ui['label_deniv_neg']}</td><td style="text-align: right; font-weight: bold;">{deniv_neg:.0f} m</td></tr>
            </table>
        </div>

        <div style="margin-bottom: 15px;">
            <h4 style="margin: 10px 0 8px 0; color: #555;">{ui['sec_virtual']}</h4>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 4px 0;">{ui['label_positive']}</td><td style="text-align: right; font-weight: bold;">{deniv_virt_pos:.0f} m</td></tr>
                <tr><td style="padding: 4px 0;">{ui['label_negative']}</td><td style="text-align: right; font-weight: bold;">{deniv_virt_neg:.0f} m</td></tr>
            </table>
        </div>

        <div style="margin-bottom: 15px;">
            <h4 style="margin: 10px 0 8px 0; color: #555;">{ui['sec_along']}</h4>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 4px 0;">{ui['label_headwind']}</td><td style="text-align: right; font-weight: bold;">{headwind_pct:.1f}% ({headwind_dist:.1f} km)</td></tr>
                <tr><td style="padding: 4px 0; padding-left: 15px;">{ui['label_average']}</td><td style="text-align: right;">{avg_headwind:.2f} km/h</td></tr>
                <tr><td style="padding: 4px 0;">{ui['label_tailwind']}</td><td style="text-align: right; font-weight: bold;">{tailwind_pct:.1f}% ({tailwind_dist:.1f} km)</td></tr>
                <tr><td style="padding: 4px 0; padding-left: 15px;">{ui['label_average']}</td><td style="text-align: right;">{avg_tailwind:.2f} km/h</td></tr>
            </table>
        </div>
    </div>
    """

    return html


def get_wind_color(wind_along_ms: float) -> str:
    """Return a color based on wind intensity along the trajectory."""
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


def create_popup_content(seg: Dict, seg_idx: int, cum_dist_km: float, ui: Optional[Dict[str, str]] = None) -> str:
    """
    Create HTML popup content for a segment.

    Parameters:
    -----------
    seg : Dict
        Segment with simulation data
    seg_idx : int
        Segment index
    cum_dist_km : float
        Cumulative distance in km

    Returns:
    --------
    str : Popup HTML content
    """
    if ui is None:
        ui = _UI_I18N.get(_detect_output_lang(), _UI_I18N["en"])

    wind_along_kmh = seg.get('wind_along', 0) * 3.6
    wind_type = ui["popup_wind_head"] if wind_along_kmh > 0 else ui["popup_wind_tail"]

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
            {ui['popup_segment']} #{seg_idx} - {ui['popup_km']} {cum_dist_km:.2f}
        </h4>

        <table style="width: 100%; border-collapse: collapse;">
            <tr style="background-color: #f0f0f0;">
                <td colspan="2" style="padding: 5px; font-weight: bold;">{ui['popup_sec_wind']}</td>
            </tr>
            <tr>
                <td style="padding: 3px;">{wind_type}</td>
                <td style="padding: 3px; text-align: right;">
                    <strong>{abs(wind_along_kmh):.1f} km/h</strong>
                </td>
            </tr>
            <tr>
                <td style="padding: 3px;">{ui['popup_tws']}</td>
                <td style="padding: 3px; text-align: right;">{tws:.1f} km/h</td>
            </tr>
            <tr>
                <td style="padding: 3px;">{ui['popup_gusts']}</td>
                <td style="padding: 3px; text-align: right;">{gust:.1f} km/h</td>
            </tr>

            <tr style="background-color: #f0f0f0;">
                <td colspan="2" style="padding: 5px; font-weight: bold;">{ui['popup_sec_slope']}</td>
            </tr>
            <tr>
                <td style="padding: 3px;">{ui['popup_terrain']}</td>
                <td style="padding: 3px; text-align: right;">{slope_terrain:.1f}%</td>
            </tr>
            <tr>
                <td style="padding: 3px;">{ui['popup_virtual']}</td>
                <td style="padding: 3px; text-align: right;">{slope_wind:.1f}%</td>
            </tr>
            <tr style="font-weight: bold;">
                <td style="padding: 3px;">{ui['popup_effective']}</td>
                <td style="padding: 3px; text-align: right;">{slope_effective:.1f}%</td>
            </tr>

            <tr style="background-color: #f0f0f0;">
                <td colspan="2" style="padding: 5px; font-weight: bold;">{ui['popup_sec_perf']}</td>
            </tr>
            <tr>
                <td style="padding: 3px;">{ui['popup_speed']}</td>
                <td style="padding: 3px; text-align: right;">{speed:.1f} km/h</td>
            </tr>
            <tr>
                <td style="padding: 3px;">{ui['popup_distance']}</td>
                <td style="padding: 3px; text-align: right;">{seg['distance']:.0f} m</td>
            </tr>
            <tr>
                <td style="padding: 3px;">{ui['popup_altitude']}</td>
                <td style="padding: 3px; text-align: right;">
                    {seg.get('ele1', 0):.0f} → {seg.get('ele2', 0):.0f} m
                </td>
            </tr>
        </table>
    </div>
    """
    return html


def _add_endpoint_markers(
    m: folium.Map,
    segments: List[Dict],
    ui: Dict[str, str],
    style: str,
) -> None:
    """Add start and finish markers to a Folium map with the chosen visual style.

    Parameters
    ----------
    m : folium.Map
    segments : List[Dict]
    ui : Dict[str, str]
        Localisation strings.
    style : str
        One of ``'circle'`` (default small dot), ``'badge'`` (letter inside a
        round badge), ``'pin'`` (standard Folium/Leaflet pin), ``'none'``
        (no markers at all).
    """
    if style == 'none':
        return

    start_ll = [segments[0]['lat1'], segments[0]['lon1']]
    finish_ll = [segments[-1]['lat2'], segments[-1]['lon2']]

    if style == 'circle':
        folium.CircleMarker(
            start_ll,
            radius=5,
            color='#2e7d32',
            fill=True,
            fill_color='#43a047',
            fill_opacity=0.95,
            weight=2,
            popup=ui['start_marker'],
            tooltip=ui['start_marker_short'],
        ).add_to(m)
        folium.CircleMarker(
            finish_ll,
            radius=5,
            color='#c62828',
            fill=True,
            fill_color='#e53935',
            fill_opacity=0.95,
            weight=2,
            popup=ui['finish_marker'],
            tooltip=ui['finish_marker_short'],
        ).add_to(m)

    elif style == 'badge':
        def _badge_icon(letter: str, bg: str) -> folium.DivIcon:
            return folium.DivIcon(
                html=(
                    f'<div style="'
                    f'background:{bg};color:white;border-radius:50%;'
                    f'width:22px;height:22px;display:flex;align-items:center;'
                    f'justify-content:center;font-size:11px;font-weight:bold;'
                    f'border:2px solid white;'
                    f'box-shadow:0 1px 4px rgba(0,0,0,0.45);'
                    f'font-family:Arial,sans-serif;'
                    f'">{letter}</div>'
                ),
                icon_size=(26, 26),
                icon_anchor=(13, 13),
            )
        folium.Marker(
            start_ll,
            popup=ui['start_marker'],
            tooltip=ui['start_marker_short'],
            icon=_badge_icon(ui['start_marker_badge_letter'], '#43a047'),
        ).add_to(m)
        folium.Marker(
            finish_ll,
            popup=ui['finish_marker'],
            tooltip=ui['finish_marker_short'],
            icon=_badge_icon(ui['finish_marker_badge_letter'], '#e53935'),
        ).add_to(m)

    elif style == 'pin':
        folium.Marker(
            start_ll,
            popup=ui['start_marker'],
            tooltip=ui['start_marker_short'],
            icon=folium.Icon(color='green', icon='play'),
        ).add_to(m)
        folium.Marker(
            finish_ll,
            popup=ui['finish_marker'],
            tooltip=ui['finish_marker_short'],
            icon=folium.Icon(color='red', icon='stop'),
        ).add_to(m)

    else:
        raise ValueError(
            f"marker_style must be 'circle', 'badge', 'pin' or 'none', got {style!r}"
        )


def create_interactive_map(segments: List[Dict],
                          output_file: str,
                          title: Optional[str] = None,
                          enable_animation: bool = True,
                          distance_from_finish: bool = False,
                          marker_style: Literal['circle', 'badge', 'pin', 'none'] = 'circle') -> str:
    """
    Create an interactive HTML map with a colorized trace and elevation profile.

    Features:
    - Map/profile sync: click the profile -> marker on the map
    - Time animation with a slider to replay the route

    Parameters:
    -----------
    segments : List[Dict]
        List of segments from simulate_with_weather
    output_file : str
        Output HTML file path
    title : str, optional
        Page title
    enable_animation : bool, optional
        Enable the time animation slider (default: True)
    distance_from_finish : bool, optional
        If True, the interactive elevation profile uses remaining distance
        to the finish on the x-axis.
    marker_style : str, optional
        Visual style of the start/finish markers. One of:
        ``'circle'`` (default – small discreet dot),
        ``'badge'`` – round badge with a letter (D/A or S/F),
        ``'pin'``   – standard large Leaflet pin,
        ``'none'``  – no start/finish markers.

    Returns:
    --------
    str : Generated file path
    """

    ui = _UI_I18N.get(_detect_output_lang(), _UI_I18N["en"])
    if title is None:
        title = ui["page_title_default"]

    if not segments:
        raise ValueError(ui["error_empty_segments"])

    # Calculer le centre et les bornes de la carte
    all_lats = [seg['lat1'] for seg in segments] + [segments[-1]['lat2']]
    all_lons = [seg['lon1'] for seg in segments] + [segments[-1]['lon2']]
    center_lat = np.mean(all_lats)
    center_lon = np.mean(all_lons)

    min_lat = min(all_lats)
    max_lat = max(all_lats)
    min_lon = min(all_lons)
    max_lon = max(all_lons)
    lat_margin = max((max_lat - min_lat) * 0.08, 0.01)
    lon_margin = max((max_lon - min_lon) * 0.08, 0.01)
    route_bounds = [[min_lat - lat_margin, min_lon - lon_margin], [max_lat + lat_margin, max_lon + lon_margin]]

    # Créer la carte Folium
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=12,
        tiles='OpenStreetMap',
        control_scale=True
    )

    # Ajouter d'autres fonds de carte avec attributions (fournisseurs gratuits sans clé API)
    # Stadia (Stamen Terrain) et CartoDB nécessitent désormais une clé API / un compte
    # (filigrane sinon) : on utilise des alternatives libres à la place.
    folium.TileLayer(
        tiles='https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
        attr='Map data: &copy; OpenStreetMap contributors, SRTM | Map style: &copy; OpenTopoMap (CC-BY-SA)',
        name='Terrain'
    ).add_to(m)

    # CyclOSM (openstreetmap.fr) is prone to outages (502); Esri is a more reliable
    # independent infrastructure with no API key required.
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
        attr='Tiles &copy; Esri &mdash; Source: Esri, HERE, Garmin, USGS, Intermap, INCREMENT P',
        name='Esri Street Map'
    ).add_to(m)

    # Light Gray Canvas: no-key alternative to CartoDB Positron, keeps the colored
    # route legible against a plain light background.
    folium.TileLayer(
        tiles='https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',
        attr='Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ',
        name='Light'
    ).add_to(m)

    # Créer les coordonnées pour la trace et les popups
    cum_dist = 0.0
    trace_coords = []
    segment_coords = []  # Pour la synchronisation et l'animation
    segment_times = []   # Pour l'animation temporelle

    route_start_dt = segments[0].get('gpxtime_start') if isinstance(segments[0].get('gpxtime_start'), datetime) else None

    # Groupe de features pour la trace
    feature_group = folium.FeatureGroup(name=ui['feature_group_name'])

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
        mid_time_s = cum_time + (seg_time / 2.0 if seg_time else 0.0)

        passage_time_iso = None
        gpx_start = seg.get('gpxtime_start')
        gpx_end = seg.get('gpxtime_end')
        if isinstance(gpx_start, datetime) and isinstance(gpx_end, datetime):
            passage_time_iso = (gpx_start + (gpx_end - gpx_start) / 2).isoformat()
        elif route_start_dt is not None:
            passage_time_iso = (route_start_dt + timedelta(seconds=mid_time_s)).isoformat()

        segment_times.append({
            'start': cum_time,
            'end': cum_time + seg_time,
            'mid_time_s': mid_time_s,
            'passage_time_iso': passage_time_iso,
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
                create_popup_content(seg, i, cum_dist_mid, ui),
                max_width=300
            )
        ).add_to(feature_group)

        cum_dist += seg['distance'] / 1000.0

    feature_group.add_to(m)

    m.fit_bounds(route_bounds, padding=(24, 24))

    _add_endpoint_markers(m, segments, ui, marker_style)

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
    arrival_time_dt = _resolve_arrival_time(segments)
    if distance_from_finish:
        distances_display_km = [total_distance_km - dist for dist in distances_km]
        segment_distances_display_km = [
            total_distance_km - item['distance_km'] for item in segment_times
        ]
        x_axis_label = ui['xaxis_from_finish']
        popup_distance_label = ui['distance_label_remaining']
    else:
        distances_display_km = distances_km
        segment_distances_display_km = [item['distance_km'] for item in segment_times]
        x_axis_label = ui['xaxis_distance']
        popup_distance_label = ui['distance_label']

    # Créer le HTML avec Plotly intégré pour le profil
    plotly_data = {
        'distances': distances_display_km,
        'elevations_real': elevations_real,
        'elevations_virtual': elevations_virtual,
        'route_bounds': route_bounds,
        'segment_coords': segment_coords,
        'segment_times': segment_times,
        'segment_distances': segment_distances_display_km,
        'speeds_kmh': speeds_kmh,
        'wind_along_kmh': wind_along_kmh,
        'total_time_s': cum_time,
        'arrival_time_iso': arrival_time_dt.isoformat() if arrival_time_dt is not None else None,
        'enable_animation': enable_animation,
        'x_axis_label': x_axis_label,
        'popup_distance_label': popup_distance_label,
        'distance_from_finish': bool(distance_from_finish),
        'route_start_iso': route_start_dt.isoformat() if route_start_dt is not None else None,
    }

    # Sauvegarder la carte
    m.save(output_file)

    # Ajouter le profil Plotly avec synchronisation et animation
    _add_plotly_profile(output_file, plotly_data, title, segments, ui)

    logger.info("Interactive map created: %s", output_file)
    logger.info("  - segments: %d", len(segments))
    logger.info("  - total distance: %.2f km", total_distance_km)
    logger.info("  - altitude range: %.0f - %.0f m", min(elevations_real), max(elevations_real))
    logger.info("  - total duration: %.1f min", cum_time / 60)
    if enable_animation:
        logger.info("  - time animation: enabled")

    return output_file


def _add_plotly_profile(html_file: str, data: Dict, title: str, segments: List[Dict], ui: Optional[Dict[str, str]] = None):
    """
    Add an interactive Plotly elevation profile to the Folium HTML file.

    Features:
    - Map/profile sync: click/hover profile -> marker on the map
    - Time animation with a slider to replay the route
    - Statistics panel accessible via a floating button

    Parameters:
    -----------
    html_file : str
        HTML file path
    data : Dict
        Distance, elevation, coordinates, and time data
    title : str
        Plot title
    segments : List[Dict]
        List of original segments to generate statistics
    """

    if ui is None:
        ui = _UI_I18N.get(_detect_output_lang(), _UI_I18N["en"])

    js_ui = {
        "popupCurrentPosition": ui["popup_current_position"],
        "popupPassageTimeLabel": ui["popup_passage_time_label"],
        "popupElapsedTimeLabel": ui["popup_elapsed_time_label"],
        "arrivalTimeLabel": ui["arrival_time_label"],
        "popupSpeedLabel": ui["popup_speed_label"],
        "popupWindLabel": ui["popup_wind_label"],
        "popupWindHead": ui["popup_wind_head_short"],
        "popupWindTail": ui["popup_wind_tail_short"],
        "traceReal": ui["trace_real"],
        "traceVirtual": ui["trace_virtual"],
        "hoverDistance": ui["hover_distance"],
        "hoverRealAltitude": ui["hover_real_altitude"],
        "hoverVirtualAltitude": ui["hover_virtual_altitude"],
        "profileTitle": ui["profile_title"],
        "yAxisAltitude": ui["yaxis_altitude"],
    }

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
    autorange_value = "\"reversed\"" if data.get('distance_from_finish') else "true"

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
        width: calc(100% - 320px);
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
        width: calc(100% - 320px);
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
    #position-info-panel {{
        position: fixed;
        right: 12px;
        bottom: 12px;
        width: 292px;
        max-height: calc({profile_height}px - 24px);
        overflow-y: auto;
        background: white;
        border: 1px solid #d0d7de;
        border-radius: 10px;
        box-shadow: 0 6px 18px rgba(0,0,0,0.18);
        z-index: 10000;
        padding: 12px 14px;
        box-sizing: border-box;
    }}
    .position-info-title {{
        font-size: 14px;
        font-weight: bold;
        color: #222;
        margin: 0 0 8px 0;
    }}
    .position-info-row {{
        font-size: 13px;
        color: #333;
        margin: 5px 0;
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
    #recenter-toggle-label {{
        margin-left: 4px;
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

        #position-info-panel {{
            left: 8px !important;
            right: 8px !important;
            width: auto !important;
            bottom: calc(302px + env(safe-area-inset-bottom)) !important;
            max-height: 76px !important;
            padding: 7px 9px !important;
            overflow: hidden !important;
            border-radius: 8px !important;
        }}

        .position-info-title {{
            display: none !important;
        }}

        .position-info-row {{
            display: inline-block !important;
            margin: 0 10px 4px 0 !important;
            font-size: 11px !important;
            line-height: 1.2 !important;
            white-space: nowrap !important;
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

        #position-info-panel {{
            left: 8px !important;
            right: 8px !important;
            width: auto !important;
            bottom: calc(214px + env(safe-area-inset-bottom)) !important;
            max-height: 56px !important;
            padding: 6px 8px !important;
            overflow: hidden !important;
            border-radius: 8px !important;
        }}

        .position-info-title {{
            display: none !important;
        }}

        .position-info-row {{
            display: inline-block !important;
            margin: 0 8px 2px 0 !important;
            font-size: 10px !important;
            line-height: 1.15 !important;
            white-space: nowrap !important;
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

        #position-info-panel {{
            left: 6px !important;
            right: 6px !important;
            width: auto !important;
            bottom: calc(282px + env(safe-area-inset-bottom)) !important;
            max-height: 74px !important;
            padding: 6px 8px !important;
            overflow: hidden !important;
        }}

        .position-info-row {{
            margin: 0 7px 3px 0 !important;
            font-size: 10px !important;
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
    <button id="stats-button" title="{ui['btn_stats_title']}">📊</button>

    <!-- Bouton flottant pour la légende -->
    <button id="legend-button" title="{ui['btn_legend_title']}">🎨</button>

    <!-- Panel de statistiques -->
    <div id="stats-panel">
        <button id="stats-close">✖</button>
        {_generate_statistics_html(segments, ui)}
    </div>

    <!-- Panel de légende -->
    <div id="legend-panel">
        <button id="legend-close">✖</button>
        <div class="wind-legend-content">
            <h3 style="margin: 0 0 15px 0; color: #333; border-bottom: 2px solid #FF9800; padding-bottom: 8px;">{ui['legend_title']}</h3>
            <p style="margin: 8px 0;"><span style="color: #8B0000; font-size: 20px;">█</span> {ui['legend_head_gt15']}</p>
            <p style="margin: 8px 0;"><span style="color: #DC143C; font-size: 20px;">█</span> {ui['legend_head_10_15']}</p>
            <p style="margin: 8px 0;"><span style="color: #FF6347; font-size: 20px;">█</span> {ui['legend_head_5_10']}</p>
            <p style="margin: 8px 0;"><span style="color: #FFA500; font-size: 20px;">█</span> {ui['legend_head_2_5']}</p>
            <p style="margin: 8px 0;"><span style="color: #FFD700; font-size: 20px;">█</span> {ui['legend_weak']}</p>
            <p style="margin: 8px 0;"><span style="color: #90EE90; font-size: 20px;">█</span> {ui['legend_tail_2_5']}</p>
            <p style="margin: 8px 0;"><span style="color: #32CD32; font-size: 20px;">█</span> {ui['legend_tail_5_10']}</p>
            <p style="margin: 8px 0;"><span style="color: #228B22; font-size: 20px;">█</span> {ui['legend_tail_10_15']}</p>
            <p style="margin: 8px 0;"><span style="color: #006400; font-size: 20px;">█</span> {ui['legend_tail_gt15']}</p>
        </div>
    </div>

    <!-- Conteneur pour les contrôles d'animation -->
    <div id="animation-controls">
        <button id="play-btn" class="anim-button">{ui['btn_play']}</button>
        <button id="pause-btn" class="anim-button" style="display:none;">{ui['btn_pause']}</button>
        <input type="range" id="time-slider" min="0" max="{int(data.get('total_time_s', 0))}" value="0" step="1">
        <div id="time-display">00:00 / {int(data.get('total_time_s', 0) // 60):02d}:{int(data.get('total_time_s', 0) % 60):02d}</div>
        <div id="arrival-time" style="font-family:monospace;font-size:13px;color:#555;white-space:nowrap;"></div>
        <button id="reset-btn" class="anim-button">{ui['btn_reset']}</button>
    </div>

    <div id="position-info-panel" style="display:none;"></div>

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
    var routeBounds = {json.dumps(data.get('route_bounds'))};
    var segmentCoords = {json.dumps(data['segment_coords'])};
    var segmentTimes = {json.dumps(data['segment_times'])};
    var segmentDistances = {json.dumps(data['segment_distances'])};
    var speedsKmh = {json.dumps(data.get('speeds_kmh', []))};
    var windAlongKmh = {json.dumps(data.get('wind_along_kmh', []))};
    var totalTimeS = {data.get('total_time_s', 0)};
    var routeStartIso = {json.dumps(data.get('route_start_iso'))};
    var arrivalTimeIso = {json.dumps(data.get('arrival_time_iso'))};
    var xAxisLabel = {json.dumps(data.get('x_axis_label', 'Distance (km)'))};    
    var popupDistanceLabel = {json.dumps(data.get('popup_distance_label', 'Distance'))};
    var ui = {json.dumps(js_ui, ensure_ascii=False)};

    function isMobileUi() {{
        var isTouchDevice = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0);
        var isSmallWidth = window.innerWidth <= 768;
        var isLandscapeMobile = window.innerHeight <= 600 && window.innerWidth <= 1024;
        return isTouchDevice && (isSmallWidth || isLandscapeMobile);
    }}

    function formatElapsedTime(totalSeconds) {{
        if (totalSeconds === undefined || totalSeconds === null || isNaN(totalSeconds)) {{
            return null;
        }}

        var safeSeconds = Math.max(0, Math.floor(totalSeconds));
        var hours = Math.floor(safeSeconds / 3600);
        var mins = Math.floor((safeSeconds % 3600) / 60);
        var secs = safeSeconds % 60;
        return hours.toString().padStart(2, '0') + ':' + mins.toString().padStart(2, '0') + ':' + secs.toString().padStart(2, '0');
    }}

    function formatPassageTime(isoText) {{
        if (!isoText) return null;

        var dt = new Date(isoText);
        if (isNaN(dt.getTime())) return null;
        return dt.toLocaleTimeString([], {{ hour: '2-digit', minute: '2-digit', second: '2-digit' }});
    }}

    function getPassageTimeText(segIdx) {{
        if (segIdx < 0 || segIdx >= segmentTimes.length) return null;

        if (segmentTimes[segIdx].passage_time_iso) {{
            return formatPassageTime(segmentTimes[segIdx].passage_time_iso);
        }}

        if (routeStartIso && segmentTimes[segIdx].mid_time_s !== undefined) {{
            var startDt = new Date(routeStartIso);
            if (!isNaN(startDt.getTime())) {{
                var estimate = new Date(startDt.getTime() + (segmentTimes[segIdx].mid_time_s * 1000));
                return estimate.toLocaleTimeString([], {{ hour: '2-digit', minute: '2-digit', second: '2-digit' }});
            }}
        }}

        return null;
    }}

    function fitRouteInVisibleMapArea() {{
        if (!leafletMap || !routeBounds || routeBounds.length !== 2) return;

        var profileDiv = document.getElementById('elevation-profile');
        var controlsDiv = document.getElementById('animation-controls');
        var profileHeight = profileDiv ? profileDiv.offsetHeight : 0;
        var controlsHeight = 0;
        if (controlsDiv && controlsDiv.style.display !== 'none') {{
            controlsHeight = controlsDiv.offsetHeight;
        }}

        // Shift route to the upper visible area by reserving space at the bottom.
        var bottomReserved = profileHeight + controlsHeight + 40;

        leafletMap.invalidateSize();
        leafletMap.fitBounds(routeBounds, {{
            paddingTopLeft: [24, 24],
            paddingBottomRight: [24, bottomReserved],
            maxZoom: 15
        }});
    }}

    function updatePositionInfoPanel(distanceKm, speed, windAlong, passageTimeText, elapsedTimeS) {{
        var panel = document.getElementById('position-info-panel');
        if (!panel) return;

        var html = '<div class="position-info-title">' + ui.popupCurrentPosition + '</div>';
        html += '<div class="position-info-row"><b>' + popupDistanceLabel + ':</b> ' + distanceKm.toFixed(2) + ' km</div>';

        if (passageTimeText) {{
            html += '<div class="position-info-row"><b>' + ui.popupPassageTimeLabel + ':</b> ' + passageTimeText + '</div>';
        }}

        if (elapsedTimeS !== undefined && elapsedTimeS !== null && !isNaN(elapsedTimeS)) {{
            html += '<div class="position-info-row"><b>' + ui.popupElapsedTimeLabel + ':</b> ' + formatElapsedTime(elapsedTimeS) + '</div>';
        }}

        if (speed !== undefined && !isNaN(speed)) {{
            html += '<div class="position-info-row"><b>' + ui.popupSpeedLabel + ':</b> ' + speed.toFixed(1) + ' km/h</div>';
        }}

        if (windAlong !== undefined && !isNaN(windAlong)) {{
            var windType = windAlong > 0 ? ui.popupWindHead : ui.popupWindTail;
            html += '<div class="position-info-row"><b>' + ui.popupWindLabel + ':</b> ' + Math.abs(windAlong).toFixed(1) + ' km/h ' + windType + '</div>';
        }}

        panel.innerHTML = html;
        panel.style.display = 'block';
    }}

    function getAdjustedCenterForProfile(lat, lon) {{
        if (!leafletMap) return [lat, lon];

        var profileDiv = document.getElementById('elevation-profile');
        var profileHeight = profileDiv ? profileDiv.offsetHeight : 0;
        var popupHeight = 0;

        if (currentMarker && currentMarker.getPopup && currentMarker.getPopup()) {{
            var popupEl = currentMarker.getPopup().getElement();
            if (popupEl) {{
                popupHeight = popupEl.offsetHeight || 0;
            }}
        }}

        var offsetPx = 0;
        if (profileHeight > 0) {{
            offsetPx += Math.max(40, Math.round(profileHeight * 0.26));
        }}
        if (popupHeight > 0) {{
            offsetPx += Math.max(35, Math.round(popupHeight * 0.55));
        }}
        if (offsetPx === 0) {{
            offsetPx = 70;
        }}

        var point = leafletMap.project([lat, lon], leafletMap.getZoom());
        var adjustedPoint = leafletMap.unproject([point.x, point.y - offsetPx], leafletMap.getZoom());
        return [adjustedPoint.lat, adjustedPoint.lng];
    }}

    // Fonction pour créer/déplacer le marqueur de position sur la carte
    function updateMarkerOnMap(lat, lon, distanceKm, speed, windAlong, passageTimeText, elapsedTimeS) {{

        if (!leafletMap) {{
            console.warn('⚠️ Carte non disponible');
            return;
        }}

        if (typeof L === 'undefined') {{
            console.warn('⚠️ Leaflet non chargé');
            return;
        }}

        var popupContent = '<div style="font-family: Arial; min-width: 180px; padding: 5px;">' +
                          '<h4 style="margin: 0 0 10px 0; color: #FF4500;">' + ui.popupCurrentPosition + '</h4>' +
                          '<p style="margin: 4px 0; font-size: 13px;"><b>' + popupDistanceLabel + ':</b> ' + distanceKm.toFixed(2) + ' km</p>';

        if (passageTimeText) {{
            popupContent += '<p style="margin: 4px 0; font-size: 13px;"><b>' + ui.popupPassageTimeLabel + ':</b> ' + passageTimeText + '</p>';
        }}

        var elapsedText = formatElapsedTime(elapsedTimeS);
        if (elapsedText) {{
            popupContent += '<p style="margin: 4px 0; font-size: 13px;"><b>' + ui.popupElapsedTimeLabel + ':</b> ' + elapsedText + '</p>';
        }}

        if (speed !== undefined && !isNaN(speed)) {{
            popupContent += '<p style="margin: 4px 0; font-size: 13px;"><b>' + ui.popupSpeedLabel + ':</b> ' + speed.toFixed(1) + ' km/h</p>';
        }}
        if (windAlong !== undefined && !isNaN(windAlong)) {{
            var windType = windAlong > 0 ? ui.popupWindHead : ui.popupWindTail;
            popupContent += '<p style="margin: 4px 0; font-size: 13px;"><b>' + ui.popupWindLabel + ':</b> ' + Math.abs(windAlong).toFixed(1) + ' km/h ' + windType + '</p>';
        }}
        popupContent += '</div>';

        updatePositionInfoPanel(distanceKm, speed, windAlong, passageTimeText, elapsedTimeS);
        var showMapPopup = !isMobileUi();

        if (currentMarker) {{
            // Déplacer le marqueur existant
            currentMarker.setLatLng([lat, lon]);
            if (showMapPopup) {{
                if (currentMarker.getPopup()) {{
                    currentMarker.setPopupContent(popupContent);
                }} else {{
                    currentMarker.bindPopup(popupContent, {{
                        autoPan: false,
                        closeButton: true
                    }});
                }}
            }} else if (currentMarker.getPopup()) {{
                currentMarker.unbindPopup();
            }}
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

            if (showMapPopup) {{
                currentMarker.bindPopup(popupContent, {{
                    autoPan: false,
                    closeButton: true
                }});
            }}
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
        var passageTime = getPassageTimeText(segIdx);

        updateMarkerOnMap(coord[0], coord[1], dist, speed, wind, passageTime, timeS);

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

    // Afficher l'heure d'arrivée estimée
    document.addEventListener('DOMContentLoaded', function() {{
        var arrivalDiv = document.getElementById('arrival-time');
        if (arrivalDiv) {{
            if (arrivalTimeIso) {{
                var arrivalDt = new Date(arrivalTimeIso);
                if (!isNaN(arrivalDt.getTime())) {{
                    arrivalDiv.textContent = ui.arrivalTimeLabel + ': ' +
                        arrivalDt.toLocaleTimeString([], {{hour: '2-digit', minute: '2-digit'}});
                    return;
                }}
            }}

            if (routeStartIso && totalTimeS > 0) {{
                var startDt = new Date(routeStartIso);
                if (!isNaN(startDt.getTime())) {{
                    var arrivalDt = new Date(startDt.getTime() + totalTimeS * 1000);
                    arrivalDiv.textContent = ui.arrivalTimeLabel + ': ' +
                        arrivalDt.toLocaleTimeString([], {{hour: '2-digit', minute: '2-digit'}});
                }}
            }}
        }}
    }});

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
        var mobileMode = isMobileUi();

        var traceReal = {{
            customdata: distances.map(function(v) {{
                return ui.hoverDistance + ' : ' + v.toFixed(2) + ' km';
            }}),
            x: distances,
            y: elevationsReal,
            mode: 'lines',
            name: ui.traceReal,
            line: {{color: 'sienna', width: 2}},
            fill: 'tozeroy',
            fillcolor: 'rgba(210, 180, 140, 0.3)',
            hovertemplate: '<b>%{{customdata}}</b><br><b>' + ui.hoverRealAltitude + ':</b> %{{y:.0f}} m<extra></extra>'
        }};

        var traceVirtual = {{
            x: distances,
            y: elevationsVirtual,
            mode: 'lines',
            name: ui.traceVirtual,
            line: {{color: 'steelblue', width: 2, dash: 'dash'}},
            hovertemplate: '<b>' + ui.hoverVirtualAltitude + ':</b> %{{y:.0f}} m<extra></extra>'
        }};

        var layout = {{
            title: {{
                text: ui.profileTitle,
                font: {{size: 14}}
            }},
            xaxis: {{
                title: xAxisLabel,
                gridcolor: '#e0e0e0',
                automargin: false,
                hoverformat: '.2f',
                autorange: {autorange_value}
            }},
            yaxis: {{
                title: ui.yAxisAltitude,
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
            dragmode: mobileMode ? false : 'zoom'
        }};

        if (mobileMode) {{
            layout.xaxis.fixedrange = true;
            layout.yaxis.fixedrange = true;
        }}

        var config = {{
            responsive: true,
            displayModeBar: !mobileMode,  // Masquer toolbar sur mobile
            modeBarButtonsToRemove: mobileMode
                ? ['lasso2d', 'select2d', 'zoom2d', 'pan2d', 'zoomIn2d', 'zoomOut2d', 'autoScale2d', 'resetScale2d']
                : ['lasso2d', 'select2d'],
            displaylogo: false,
            // 📱 Désactiver le zoom mais GARDER les événements click/hover
            doubleClick: false,
            scrollZoom: false
        }};

        Plotly.newPlot('elevation-profile', [traceReal, traceVirtual], layout, config);

        // 📱 Empêcher le zoom sur mobile (portrait ET paysage)
        var plotlyDiv = document.getElementById('elevation-profile');

        if (mobileMode) {{
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
        if (mobileMode) {{
            Plotly.relayout('elevation-profile', {{
                'margin.l': 35,
                'margin.r': 5,
                'margin.t': 30,
                'margin.b': 35,
                'xaxis.fixedrange': true,
                'yaxis.fixedrange': true,
                'xaxis.title.font.size': 10,
                'yaxis.title.font.size': 10,
                'title.font.size': 11
            }});
        }}

        // 📱 Ré-adapter lors de la rotation d'écran
        window.addEventListener('resize', function() {{
            Plotly.Plots.resize('elevation-profile');

            // Redétecter si mobile après rotation
            var isMobileNow = isMobileUi();
            Plotly.relayout('elevation-profile', {{
                'dragmode': isMobileNow ? false : 'zoom'
            }});

            if (isMobileNow) {{
                Plotly.relayout('elevation-profile', {{
                    'margin.l': 35,
                    'margin.r': 5,
                    'margin.t': 30,
                    'margin.b': 35,
                    'xaxis.fixedrange': true,
                    'yaxis.fixedrange': true
                }});
            }} else {{
                Plotly.relayout('elevation-profile', {{
                    'margin.l': 60,
                    'margin.r': 40,
                    'margin.t': 50,
                    'margin.b': 50,
                    'xaxis.fixedrange': false,
                    'yaxis.fixedrange': false
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
                var elapsedTimeS = segmentTimes[closestSegIdx] ? segmentTimes[closestSegIdx].mid_time_s : null;
                var passageTime = getPassageTimeText(closestSegIdx);

                waitForMap(function() {{
                    updateMarkerOnMap(coord[0], coord[1], distanceKm, speed, wind, passageTime, elapsedTimeS);
                    if (!isMobileUi() && currentMarker && leafletMap) {{
                        currentMarker.openPopup();
                        console.log('✅ Marqueur créé/déplacé et panneau d’infos mis à jour');
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
                var elapsedTimeS = segmentTimes[closestSegIdx] ? segmentTimes[closestSegIdx].mid_time_s : null;
                var passageTime = getPassageTimeText(closestSegIdx);

                waitForMap(function() {{
                    updateMarkerOnMap(coord[0], coord[1], distanceKm, speed, wind, passageTime, elapsedTimeS);
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
            fitRouteInVisibleMapArea();
            // Test de création du marqueur au premier point
            if (segmentCoords.length > 0 && speedsKmh.length > 0) {{
                var firstCoord = segmentCoords[0];
                var firstSpeed = speedsKmh[0];
                var firstWind = windAlongKmh[0];
                var firstElapsed = segmentTimes[0] ? segmentTimes[0].mid_time_s : 0;
                var firstPassage = getPassageTimeText(0);
                updateMarkerOnMap(firstCoord[0], firstCoord[1], segmentDistances[0], firstSpeed, firstWind, firstPassage, firstElapsed);
                console.log('✅ Marqueur initial créé au point de départ');
            }}
        }});

        window.addEventListener('resize', function() {{
            if (!leafletMap) return;
            fitRouteInVisibleMapArea();
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
    logger.info("interactive_map.py module - Interactive cycling route visualization")
    logger.info("Usage: from interactive_map import create_interactive_map")
