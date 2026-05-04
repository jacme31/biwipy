#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Feb 23 13:00:05 2025

@author: jacme
"""
# ===============
# gpx_tools.py 
# ===============
import math
from datetime import datetime
from typing import List, Dict, Any
import xml.etree.ElementTree as ET
import logging

# -------------------------------------------------
# Distance géodésique (Haversine)
# -------------------------------------------------
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# -------------------------------------------------
# Calcul du cap entre deux points (deg, 0 = nord)
# -------------------------------------------------
def bearing(lat1, lon1, lat2, lon2):
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    x = math.sin(dlambda) * math.cos(phi2)
    y = math.cos(phi1)*math.sin(phi2) - math.sin(phi1)*math.cos(phi2)*math.cos(dlambda)
    b = math.degrees(math.atan2(x, y))
    return (b + 360) % 360


############################
# Lecture  GPX
#############################

def load_gpx_points(gpx_file):
    """Charge les points GPX dans une liste propre.
    
    Détecte automatiquement le namespace GPX (1.0, 1.1, ou autre).
    """
    tree = ET.parse(gpx_file)
    root = tree.getroot()

    # Extrait le namespace du tag root de manière générique
    # Format: {http://www.topografix.com/GPX/1/1}gpx → http://www.topografix.com/GPX/1/1
    ns_match = root.tag.split('}')[0]  # Extrait {namespace
    if ns_match.startswith('{'):
        gpx_namespace = ns_match[1:]  # Enlève le {
    else:
        gpx_namespace = ""  # Pas de namespace
    
    # Crée une fonction helper pour trouver les éléments avec ou sans namespace
    def find_tag(element, tag_name):
        """Cherche un tag avec ou sans namespace."""
        if gpx_namespace:
            return element.find(f"{{{gpx_namespace}}}{tag_name}")
        else:
            return element.find(tag_name)
    
    def findall_tag(element, tag_name):
        """Cherche plusieurs tags avec ou sans namespace."""
        if gpx_namespace:
            return element.findall(f"{{{gpx_namespace}}}{tag_name}")
        else:
            return element.findall(tag_name)

    pts = []
    for trk in findall_tag(root, "trk"):
        for seg in findall_tag(trk, "trkseg"):
            for p in findall_tag(seg, "trkpt"):
                lat = float(p.attrib["lat"])
                lon = float(p.attrib["lon"])

                ele = find_tag(p, "ele")
                alt = float(ele.text) if ele is not None else 0.0
                t_node = find_tag(p, "time")
                if t_node is not None:
                    # format ISO GPX
                    t = datetime.fromisoformat(t_node.text.replace("Z", "+00:00"))
                else:
                    t = None

                pts.append({
                    "lat": lat,
                    "lon": lon,
                    "alt": alt,
                    "time": t
                })
    return pts

#############################
# Filtrage altitude (optionnel)
#############################

def smooth_altitude(points, window=9, methode="mediane"):
    """Filtre médian simple pour réduire le bruit d'altitude."""
    if window < 3 or window % 2 == 0:
        return points

    half = window // 2
    n = len(points)
    new_points = points.copy()

    for i in range(n):
        lo = max(0, i-half)
        hi = min(n, i+half+1)
        window_vals = [points[j]["alt"] for j in range(lo, hi)]
        if methode == "mediane":
            new_points[i]["alt"] = sorted(window_vals)[len(window_vals)//2]
        else:
            new_points[i]["alt"] = sum(window_vals) / len(window_vals)

    return new_points


# -------------------------------------------------
# Convertit une liste de points GPX en segments
# Chaque point = {lat, lon, ele?, time?}
# -------------------------------------------------
#def gpx_to_segments(points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
def gpx_to_segments(points, smooth=True, smoothing_window=11, smoothing_method="mediane"):
    if smooth:
        points = smooth_altitude(points, window=smoothing_window, methode=smoothing_method)
    segments = []
    dcumplus=0.0
    dcummoins=0.0
    for i in range(len(points) - 1):
        p1 = points[i]
        p2 = points[i+1]
        d = haversine(p1['lat'], p1['lon'], p2['lat'], p2['lon'])
        if d < 1:
            continue
        b = bearing(p1['lat'], p1['lon'], p2['lat'], p2['lon'])
        dz = p2.get('alt', 0) - p1.get('alt', 0)
        slope = dz / d
        dcumplus+= max(0,dz)
        dcummoins+= min(0,dz)
        points[i]['dcumplus']=dcumplus
        points[i]['dcummoins']=dcummoins


        seg = {
            'lat1': p1['lat'], 'lon1': p1['lon'],
            'lat2': p2['lat'], 'lon2': p2['lon'],
            'ele1': p1.get('alt', 0), 'ele2': p2.get('alt', 0),
            'distance': d,
            'bearing': b,
            'slope': slope,
            'dcumplus': dcumplus,
            'dcummoins': dcummoins
        }

        if 'time' in p1 and 'time' in p2:
            seg['gpxtime_start'] = p1['time']
            seg['gpxtime_end'] = p2['time']
            

        segments.append(seg)

    return segments

# -------------------------------------------------
# Calcul vitesse moyenne (décompte pauses)
# -------------------------------------------------
def compute_moving_average_from_gpx_segments(segments, speed_threshold=1.0):
    """
    Calcule la moving average (vitesse en déplacement) en utilisant les durées GPX,
    en excluant les segments dont la vitesse instantanée est trop faible.
    
    speed_threshold : vitesse minimale (m/s) pour considérer un segment comme "en mouvement".
    """
    moving_dist = 0.0
    moving_time = 0.0

    for seg in segments:
        dt = (seg['gpxtime_end'] - seg['gpxtime_start']).total_seconds()
        if dt <= 0:
            continue
        dist = seg['distance']
        v = dist / dt

        if v > speed_threshold:
            moving_dist += dist
            moving_time += dt

    if moving_time == 0:
        return 0.0

    return (moving_dist / moving_time) * 3.6

def filter_stopped_segments(segments, speed_threshold=1.0, verbose=True):
    """
    Filtre les segments arrêtés (vitesse < threshold) en utilisant les timestamps GPX.
    À appeler APRÈS gpx_to_segments() et AVANT les simulations.
    
    Parameters:
    -----------
    segments : List[Dict]
        Liste des segments GPX (doit contenir gpxtime_start et gpxtime_end)
    speed_threshold : float
        Vitesse minimale (m/s) pour considérer un segment comme "en mouvement" (défaut 1.0 m/s)
    verbose : bool
        Si True, affiche un résumé du filtrage
    
    Returns:
    --------
    List[Dict] : Segments filtrés (arrêts supprimés)
    """
    
    filtered_segments = []
    stopped_count = 0
    stopped_distance = 0.0
    stopped_time = 0.0
    
    for seg in segments:
        # Vérifier que les timestamps GPX sont présents
        if 'gpxtime_start' not in seg or 'gpxtime_end' not in seg:
            # Garder le segment si pas de timestamps (ne peut pas évaluer la vitesse)
            filtered_segments.append(seg)
            continue
        
        dt = (seg['gpxtime_end'] - seg['gpxtime_start']).total_seconds()
        if dt <= 0:
            # Segment invalide (temps négatif ou nul) → supprimer
            stopped_count += 1
            stopped_distance += seg.get('distance', 0)
            continue
        
        dist = seg['distance']
        v = dist / dt
        
        if v >= speed_threshold:
            # Segment en mouvement → garder
            filtered_segments.append(seg)
        else:
            # Segment arrêté → supprimer
            stopped_count += 1
            stopped_distance += dist
            stopped_time += dt
    
    # Log du résumé
    if verbose:
        logging.info(f"\n{'='*70}")
        logging.info(f"  FILTERING: Removing stopped segments (v < {speed_threshold*3.6:.1f} km/h)")
        logging.info(f"{'='*70}")
        logging.info(f"Before: {len(segments)} segments")
        logging.info(f"Removed: {stopped_count} stopped segments")
        logging.info(f"After: {len(filtered_segments)} segments")
        
        if stopped_count > 0:
            logging.info(f"Stopped distance: {stopped_distance:.1f} m ({stopped_distance/1000:.4f} km)")
            logging.info(f"Stopped time: {stopped_time:.1f} s ({stopped_time/60:.2f} min)")
        logging.info(f"{'='*70}\n")
    
    return filtered_segments

def detect_gps_altitude_noise(segments, max_dist=5.0, min_slope_threshold=0.10, 
                               normal_slope_threshold=0.05, log_file=None):
    """
    Détecte les segments aberrants causés par du bruit GPS en altitude.
    
    Critères d'identification:
    - Segment court (distance < max_dist, défaut 5m)
    - Pente anormale (|pente| > min_slope_threshold, défaut 10%)
    - Isolé entre deux segments avec pentes normales (|pente| < normal_slope_threshold, défaut 5%)
    
    Parameters:
    -----------
    segments : List[Dict]
        Liste des segments GPX
    max_dist : float
        Distance maximale (en mètres) pour considérer un segment comme "court"
    min_slope_threshold : float
        Pente minimale (en absolu) pour être considérée comme "anormale"
    normal_slope_threshold : float
        Pente maximale (en absolu) pour être considérée comme "normale"
    log_file : str or None
        Fichier log pour sauvegarder les résultats. Si None, log en console.
    
    Returns:
    --------
    List[Dict] : Liste des segments aberrants détectés
    """
    
    aberrants = []
    
    for i in range(len(segments)):
        seg = segments[i]
        dist = seg.get('distance', 0)
        slope = seg.get('slope', 0)
        
        # Critère 1 : segment court ET pente anormale
        if dist < max_dist and abs(slope) > min_slope_threshold:
            # Vérifier si c'est isolé (segments voisins ont pentes normales)
            is_isolated = True
            
            # Vérifier segment précédent
            if i > 0:
                slope_prev = abs(segments[i-1].get('slope', 0))
                if slope_prev > normal_slope_threshold:
                    is_isolated = False
            
            # Vérifier segment suivant
            if i < len(segments) - 1:
                slope_next = abs(segments[i+1].get('slope', 0))
                if slope_next > normal_slope_threshold:
                    is_isolated = False
            
            if is_isolated:
                aberrants.append({
                    'index': i,
                    'distance': dist,
                    'slope': slope,
                    'slope_pct': slope * 100,
                    'ele1': seg.get('ele1', 0),
                    'ele2': seg.get('ele2', 0),
                    'lat1': seg.get('lat1', 0),
                    'lon1': seg.get('lon1', 0),
                    'lat2': seg.get('lat2', 0),
                    'lon2': seg.get('lon2', 0),
                    'prev_slope_pct': abs(segments[i-1].get('slope', 0)) * 100 if i > 0 else None,
                    'next_slope_pct': abs(segments[i+1].get('slope', 0)) * 100 if i < len(segments) - 1 else None,
                })
    
    # Formatage des résultats
    msg_lines = [
        f"\n{'='*90}",
        f"  DETECTION OF ABNORMAL SEGMENTS (GPS ALTITUDE NOISE)",
        f"{'='*90}",
        f"Criteria: distance < {max_dist}m AND |slope| > {min_slope_threshold*100:.1f}% AND isolated between normal slopes",
        f"Total abnormal segments found: {len(aberrants)}\n"
    ]
    
    if aberrants:
        delta_ele_label = "ΔEle(m)"
        msg_lines.append(f"{'Index':<6} {'Dist(m)':<10} {'Slope%':<10} {delta_ele_label:<10} {'Prev%':<10} {'Next%':<10} {'Location':<40}")
        msg_lines.append("-" * 90)
        
        for ab in aberrants:
            prev_str = f"{ab['prev_slope_pct']:.1f}" if ab['prev_slope_pct'] is not None else "N/A"
            next_str = f"{ab['next_slope_pct']:.1f}" if ab['next_slope_pct'] is not None else "N/A"
            delta_ele = ab['ele2'] - ab['ele1']
            location = f"({ab['lat1']:.4f}, {ab['lon1']:.4f})"
            
            msg_lines.append(
                f"{ab['index']:<6} {ab['distance']:<10.1f} {ab['slope_pct']:<10.2f} "
                f"{delta_ele:<10.2f} {prev_str:<10} {next_str:<10} {location:<40}"
            )
    else:
        msg_lines.append("✓ Aucun segment aberrant détecté")
    
    msg_lines.append("=" * 90)
    
    # Affichage ou sauvegarde
    output = "\n".join(msg_lines)
    if log_file:
        try:
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write(output)
            logging.info(f"\u2713 Results saved to: {log_file}")
        except Exception as e:
            logging.error(f"Error saving log: {e}")
    
    logging.info(output)
    
    return aberrants


def remove_gps_altitude_noise(segments, max_dist=5.0, min_slope_threshold=0.10, 
                              normal_slope_threshold=0.05, verbose=True):
    """
    Supprime les segments aberrants causés par du bruit GPS en altitude.
    
    Les segments aberrants sont identifiés par les mêmes critères que detect_gps_altitude_noise:
    - Distance < max_dist
    - |pente| > min_slope_threshold
    - Isolés entre deux segments avec pentes normales
    
    Parameters:
    -----------
    segments : List[Dict]
        Liste des segments GPX
    max_dist : float
        Distance maximale pour considérer un segment comme "court" (défaut 5m)
    min_slope_threshold : float
        Pente minimale pour être "anormale" (défaut 10%)
    normal_slope_threshold : float
        Pente maximale pour être "normale" (défaut 5%)
    verbose : bool
        Si True, affiche un résumé de la suppression
    
    Returns:
    --------
    List[Dict] : Segments filtrés (bruits supprimés)
    """
    
    # Identifier les indices à supprimer
    indices_to_remove = set()
    
    for i in range(len(segments)):
        seg = segments[i]
        dist = seg.get('distance', 0)
        slope = seg.get('slope', 0)
        
        # Critère 1 : segment court ET pente anormale
        if dist < max_dist and abs(slope) > min_slope_threshold:
            # Vérifier si c'est isolé (segments voisins ont pentes normales)
            is_isolated = True
            
            # Vérifier segment précédent
            if i > 0:
                slope_prev = abs(segments[i-1].get('slope', 0))
                if slope_prev > normal_slope_threshold:
                    is_isolated = False
            
            # Vérifier segment suivant
            if i < len(segments) - 1:
                slope_next = abs(segments[i+1].get('slope', 0))
                if slope_next > normal_slope_threshold:
                    is_isolated = False
            
            if is_isolated:
                indices_to_remove.add(i)
    
    # Créer la nouvelle liste filtrée
    filtered_segments = [seg for i, seg in enumerate(segments) if i not in indices_to_remove]
    
    # Log du résumé
    if verbose:
        removed_count = len(indices_to_remove)
        logging.info(f"\n{'='*70}")
        logging.info(f"  FILTERING: Removing abnormal segments (GPS noise)")
        logging.info(f"{'='*70}")
        logging.info(f"Before: {len(segments)} segments")
        logging.info(f"Removed: {removed_count} segments (GPS noise)")
        logging.info(f"After: {len(filtered_segments)} segments")
        
        if removed_count > 0:
            # Statistiques des segments supprimés
            removed_dist = sum(segments[i].get('distance', 0) for i in indices_to_remove)
            logging.info(f"Removed distance: {removed_dist:.1f} m ({removed_dist/1000:.4f} km)")
        logging.info(f"{'='*70}\n")
    
    return filtered_segments


def diag_segments(segments, n=100,slope=False):
        logging.info("Total segments: %d", len(segments))
        total_dist = sum(seg.get('distance',0) for seg in segments)
        logging.info(f"Total distance (sum segments): {total_dist/1000:.3f} km")

        # GPX times presence, types and first/last
        have_times = all(('gpxtime_start' in s and 'gpxtime_end' in s) for s in segments)
        logging.info(f"GPX times present on all segments? {have_times}")
        if have_times:
            t0 = segments[0]['gpxtime_start']
            tN = segments[-1]['gpxtime_end']
            strlog="type gpxtime_start (UTC):"  + str(t0)
            logging.info(strlog)
            try:
                total_time_s = (tN - t0).total_seconds()
                strlog=f"Total time from GPX: {total_time_s/3600:.3f} h -> avg = {(total_dist/total_time_s)*3.6:.3f} km/h"
                logging.info(strlog)    
            except Exception as e:
                logging.info("Error computing total_time from gpxtimes:", e)

        # logging.info first n segments summary
        logging.info("\tindex\tdist-m\t\tslope\tgpxtime_start\t\tgpxtime_end")
        p=0
        for i, seg in enumerate(segments):
            if slope and seg.get('slope',0 )>0.0 :
                
                segstr="\t"+f"{i:03d}\t"+f"{seg.get('distance',0):7.1f}m\t"+ f"{seg.get('slope',0)*100:.2f}%\t"+  \
                 " t0:" + str(seg.get('gpxtime_start')) + \
                " t1:" + str(seg.get('gpxtime_end'))
                logging.info(segstr)
                p+=1
            if p>=n:
                break
        logging.info ("moving_average: %d km/h" % compute_moving_average_from_gpx_segments(segments, speed_threshold=1.0))
        logging.info ("cumulative positive elevation: %.1f m" % segments[-1].get('dcumplus',0))
        logging.info ("cumulative negative elevation: %.1f m" % segments[-1].get('dcummoins',0))

if __name__ == "__main__":

    
    # import 
    import logging
    from datetime import datetime, timedelta, timezone
    from zoneinfo import ZoneInfo
    import os

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    if os.name=='posix' :
        hdir="/mnt/nasdocker/grib/data/"
    
    else : 
        hdir="G:/grib/data/"
    gfsdir=hdir+'gfs/'
    gpxdir=hdir+'gpx/'
    

    # heure de départ 
    origin_tz = ZoneInfo("Europe/Paris")
    st_start="2025-12-20 14:14:00"
    #st_start="2025-07-19 09:28:00"
    filegpx=gpxdir+"M20250719-32K-0928.gpx"
    #filegpx=gpxdir+"M20250719-32K-0928.gpx"

    import logging

    t_start=datetime.fromisoformat(st_start).replace(tzinfo=origin_tz)
    ct_start=t_start.strftime("%b-%d")

    pgpx=load_gpx_points(filegpx)


    segments = gpx_to_segments(pgpx,smooth=True, smoothing_window=19)
    res = {k: max(d.get(k, float('-inf')) for d in segments) for k in {key for d in segments for key in d}}
    logging.info (res)
    diag_segments(segments, n=5000, slope=True)
    