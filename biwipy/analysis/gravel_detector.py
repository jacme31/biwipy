# ==========================================
#gravel detection.py
# ==========================================

import math
from datetime import datetime
from typing import List, Dict, Any
import xml.etree.ElementTree as ET
import locale
import os
from gpx_tools import load_gpx_points, gpx_to_segments


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
    "surface_breakdown": {
        "fr": "  Repartition temporelle des surfaces:",
        "en": "  Surface time breakdown:",
    },
    "urban_line": {
        "fr": "    Urbain : {minutes:.1f} min ({pct:.2f}%)",
        "en": "    Urban : {minutes:.1f} min ({pct:.2f}%)",
    },
    "gravel_line": {
        "fr": "    Gravel: {minutes:.1f} min ({pct:.2f}%)",
        "en": "    Gravel: {minutes:.1f} min ({pct:.2f}%)",
    },
    "len_mismatch_segments_classifications": {
        "fr": "segments et classifications doivent avoir la meme longueur",
        "en": "segments and classifications must have same length",
    },
    "len_mismatch_segments_classes": {
        "fr": "segments et classes doivent avoir la meme longueur",
        "en": "segments and classes must have same length",
    },
}


def _t(key: str, **kwargs) -> str:
    lang = _detect_output_lang()
    labels = _I18N.get(key, {})
    template = labels.get(lang) or labels.get("en") or key
    return template.format(**kwargs) if kwargs else template


def _tp(key: str, **kwargs) -> None:
    print(_t(key, **kwargs))





# ---------------------- Gravel Detection ----------------------

def detect_gravel_segments(segments: List[Dict], window_s=8, speed_drop_threshold=0.75, roughness_threshold=0.5, zigzag_threshold=10.0):
    """
    Detect gravel segments in a GPX.
    Returns a list of per-segment classifications: 'road' or 'gravel'.
    window_s : sliding window in seconds for the calculation.
    Thresholds can be adjusted based on bike and GPS.
    """
    classifications = []

    # Pré-calcul des vitesses instantanées et roughness
    for seg in segments:
        dt = (seg['gpxtime_end'] - seg['gpxtime_start']).total_seconds()
        dt = max(dt, 1e-6)  # éviter div zero
        seg['speed_m_s'] = seg['distance'] / dt


    # Roughness: RMS des variations d'altitude (utilise ele2-ele1)
    n = len(segments)
    for i, seg in enumerate(segments):
        window = segments[max(0, i-1):min(n, i+2)]
        dzs = [(w['ele2'] - w['ele1']) for w in window]
        if dzs:
            seg['roughness'] = math.sqrt(sum(d*d for d in dzs) / len(dzs))
        else:
            seg['roughness'] = 0.0

    # Zigzag: variation angulaire
    for i, seg in enumerate(segments):
        if i == 0:
            seg['zigzag'] = 0
        else:
            da = abs(seg['bearing'] - segments[i-1]['bearing'])
            da = min(da, 360 - da)
            seg['zigzag'] = da

    # Classification
    # On compare la vitesse locale à une vitesse de référence lissée (fenêtre glissante)
    speeds = [seg['speed_m_s'] for seg in segments]

    for i, seg in enumerate(segments):
        # vitesse de référence locale (médiane sur fenêtre)
        i0 = max(0, i-3)
        i1 = min(len(speeds), i+4)
        ref_speed = sorted(speeds[i0:i1])[len(speeds[i0:i1])//2]

        score = 0
        # chute de vitesse anormale
        if ref_speed > 0 and seg['speed_m_s'] < speed_drop_threshold * ref_speed:
            score += 1
        # rugosité verticale
        if seg.get('roughness', 0.0) > roughness_threshold:
            score += 1
        # zigzag GPS
        if seg.get('zigzag', 0.0) > zigzag_threshold:
            score += 1

        classifications.append('gravel' if score >= 2 else 'road')

    return classifications


def compute_gravel_score(classifications: List[str]) -> float:
    """Return percentage of gravel segments (by segment count)"""
    n = len(classifications)
    if n == 0:
        return 0.0
    n_gravel = sum(1 for c in classifications if c == 'gravel')
    return 100.0 * n_gravel / n

def compute_gravel_score_by_time(classifications: List[str], segments: List[Dict]) -> float:
    """Return percentage of gravel time (more relevant for physics)"""
    if len(segments) != len(classifications):
        raise ValueError(_t("len_mismatch_segments_classifications"))
    
    time_gravel = 0.0
    time_total = 0.0
    
    for seg, cls in zip(segments, classifications):
        # Calculer le temps du segment à partir des timestamps
        if 'gpxtime_start' in seg and 'gpxtime_end' in seg:
            dt = (seg['gpxtime_end'] - seg['gpxtime_start']).total_seconds()
        elif 'time_s' in seg:
            dt = seg['time_s']
        else:
            # Fallback: calculer depuis distance et vitesse
            dt = seg['distance'] / max(seg.get('speed_m_s', 1.0), 0.1)
        
        time_total += dt
        if cls == 'gravel':
            time_gravel += dt
    
    return 100.0 * time_gravel / time_total if time_total > 0 else 0.0

def smooth_gravel_by_distance(segments, classes, min_gravel_length=50.0):
    smoothed = classes.copy()
    i = 0
    n = len(classes)

    while i < n:
        if classes[i] == 'gravel':
            j = i
            dist = 0.0
            while j < n and classes[j] == 'gravel':
                dist += segments[j]['distance']
                j += 1

            if dist < min_gravel_length:
                # trop court → on efface
                for k in range(i, j):
                    smoothed[k] = 'road'

            i = j
        else:
            i += 1

    return smoothed

def propagate_gravel(segments, classes,
                     window_dist=30.0,
                     min_gravel_in_window=3):
    """
    Spatial propagation of gravel labels.
    window_dist : total window distance (m)
    """
    n = len(classes)
    smoothed = classes.copy()

    for i in range(n):
        dist = 0.0
        gravel_count = 0
        j = i

        # regarde vers l'avant
        while j < n and dist < window_dist:
            dist += segments[j]['distance']
            if classes[j] == 'gravel':
                gravel_count += 1
            j += 1

        # regarde vers l'arrière
        dist = 0.0
        j = i - 1
        while j >= 0 and dist < window_dist:
            dist += segments[j]['distance']
            if classes[j] == 'gravel':
                gravel_count += 1
            j -= 1

        if gravel_count >= min_gravel_in_window:
            smoothed[i] = 'gravel'

    return smoothed


# ---------------------- Urban vs Gravel classifier ----------------------

def detect_surface_segments(
    segments: List[Dict],
    window_ref=3,
    speed_drop_threshold=0.75,
    roughness_threshold=0.5,
    zigzag_threshold=10.0,
    pause_speed_threshold=0.5,
    turn_angle_threshold=30.0,
    density_window_dist=200.0,
):
    """
    Classify segments as 'road', 'urban', or 'gravel'.
    - 'urban' captures stop-and-go, frequent turns, traffic slowdowns
    - 'gravel' captures degraded surface, roughness, slowdowns without stops

    This function is non-destructive relative to detect_gravel_segments.
    It reuses the same features and adds urban indicators.
    """

    if not segments:
        return []

    n = len(segments)

    # vitesses et durées
    speeds = []
    dts = []
    for seg in segments:
        if 'gpxtime_start' in seg and 'gpxtime_end' in seg:
            dt = (seg['gpxtime_end'] - seg['gpxtime_start']).total_seconds()
        elif 'time_s' in seg:
            dt = seg['time_s']
        else:
            # fallback approximatif
            dt = max(seg.get('distance', 0.0) / max(seg.get('speed_m_s', 1.0), 0.1), 1e-6)
        dts.append(dt)
        spd = seg.get('speed_m_s')
        if spd is None:
            spd = seg.get('distance', 0.0) / max(dt, 1e-6)
            seg['speed_m_s'] = spd
        speeds.append(spd)

    # roughness locale (RMS des dz sur une petite fenêtre)
    for i, seg in enumerate(segments):
        window = segments[max(0, i-1):min(n, i+2)]
        dzs = [(w.get('ele2', 0.0) - w.get('ele1', 0.0)) for w in window]
        if dzs:
            seg['roughness'] = math.sqrt(sum(d*d for d in dzs) / len(dzs))
        else:
            seg['roughness'] = 0.0

    # zigzag (variation angulaire)
    for i, seg in enumerate(segments):
        if i == 0:
            seg['zigzag'] = 0.0
        else:
            b1 = segments[i-1].get('bearing', 0.0)
            b2 = seg.get('bearing', 0.0)
            da = abs(b2 - b1)
            seg['zigzag'] = min(da, 360.0 - da)

    # densités locales dans une fenêtre en distance
    def window_indices_by_distance(center_idx: int, max_dist: float):
        # vers l'avant
        dist = 0.0
        j = center_idx
        fwd = []
        while j < n and dist < max_dist:
            fwd.append(j)
            dist += segments[j].get('distance', 0.0)
            j += 1
        # vers l'arrière
        dist = 0.0
        j = center_idx - 1
        back = []
        while j >= 0 and dist < max_dist:
            back.append(j)
            dist += segments[j].get('distance', 0.0)
            j -= 1
        idxs = list(reversed(back)) + fwd
        return idxs

    classifications = []
    for i, seg in enumerate(segments):
        # Vitesse de référence locale (médiane sur petite fenêtre d'indices)
        i0 = max(0, i - window_ref)
        i1 = min(n, i + window_ref + 1)
        local_speeds = sorted(speeds[i0:i1])
        ref_speed = local_speeds[len(local_speeds)//2] if local_speeds else speeds[i]

        # Fenêtre par distance pour densités
        idxs = window_indices_by_distance(i, density_window_dist)
        if not idxs:
            idxs = [i]
        dist_win = sum(segments[k].get('distance', 0.0) for k in idxs)
        turns = sum(1 for k in idxs[1:] if segments[k]['zigzag'] > turn_angle_threshold)
        turn_density_per_km = (turns / max(dist_win, 1e-3)) * 1000.0

        low_speed_segments = sum(1 for k in idxs if speeds[k] < pause_speed_threshold)
        pause_density = low_speed_segments / len(idxs)

        # Scores
        gravel_score = 0
        urban_score = 0

        # Ralentissement par rapport à la référence
        if ref_speed > 0 and seg['speed_m_s'] < speed_drop_threshold * ref_speed:
            # affecte les deux contextes
            gravel_score += 1
            urban_score += 1

        # Rugosité → gravel
        if seg.get('roughness', 0.0) > roughness_threshold:
            gravel_score += 1

        # Zigzag + pauses → urban
        if seg.get('zigzag', 0.0) > zigzag_threshold:
            urban_score += 1

        if pause_density > 0.15:  # >15% de segments très lents dans la fenêtre
            urban_score += 1

        if turn_density_per_km > 4.0:  # >4 virages marqués / km
            urban_score += 1

        # Décision
        if urban_score >= 2 and urban_score > gravel_score:
            cls = 'urban'
        elif gravel_score >= 2 and gravel_score > urban_score:
            cls = 'gravel'
        elif gravel_score >= 2 and urban_score >= 2:
            # tie-breaker: forte rugosité et faible pauses → gravel, sinon urban
            if seg.get('roughness', 0.0) > roughness_threshold * 1.2 and pause_density < 0.10:
                cls = 'gravel'
            else:
                cls = 'urban'
        else:
            cls = 'road'

        classifications.append(cls)

    return classifications


# ---------------------- Time-based shares ----------------------

def _segment_duration_seconds(seg: Dict) -> float:
    """Internal: robust duration in seconds for a segment."""
    if 'gpxtime_start' in seg and 'gpxtime_end' in seg:
        try:
            return (seg['gpxtime_end'] - seg['gpxtime_start']).total_seconds()
        except Exception:
            pass
    if 'time_s' in seg:
        return float(seg['time_s'])
    # Fallback from distance/speed
    dist = float(seg.get('distance', 0.0))
    spd = float(seg.get('speed_m_s', 0.0))
    if spd <= 0.0:
        spd = 0.1
    return dist / spd


def compute_time_by_class(classifications: List[str], segments: List[Dict]) -> Dict[str, float]:
    """
    Returns total time in seconds spent per class label.
    Includes 'total_time' key for convenience.
    """
    if len(classifications) != len(segments):
        raise ValueError("classifications and segments must have same length")
    times: Dict[str, float] = {}
    total = 0.0
    for cls, seg in zip(classifications, segments):
        dt = _segment_duration_seconds(seg)
        total += dt
        times[cls] = times.get(cls, 0.0) + dt
    times['total_time'] = total
    return times


def compute_time_percent_by_class(classifications: List[str], segments: List[Dict]) -> Dict[str, float]:
    """Returns percentage (0-100) of time per class label."""
    t = compute_time_by_class(classifications, segments)
    total = t.get('total_time', 0.0)
    if total <= 0:
        return {k: 0.0 for k in t.keys() if k != 'total_time'}
    return {k: (v / total) * 100.0 for k, v in t.items() if k != 'total_time'}


def report_urban_gravel_times(segments: List[Dict], classifications: List[str] = None) -> Dict[str, float]:
    """
    Convenience: compute and print only urban/gravel time shares.
    If classifications not provided, uses detect_surface_segments.
    Returns a dict with 'urban_time_s', 'gravel_time_s', 'total_time_s',
    and their percentages 'urban_pct', 'gravel_pct'.
    """
    if classifications is None:
        classifications = detect_surface_segments(segments)
    times = compute_time_by_class(classifications, segments)
    total = times.get('total_time', 0.0)
    urban_t = times.get('urban', 0.0)
    gravel_t = times.get('gravel', 0.0)
    urban_pct = (urban_t / total) * 100.0 if total > 0 else 0.0
    gravel_pct = (gravel_t / total) * 100.0 if total > 0 else 0.0

    # Simple stdout report (caller can disable/ignore output if needed)
    _tp("surface_breakdown")
    _tp("urban_line", minutes=urban_t/60, pct=urban_pct)
    _tp("gravel_line", minutes=gravel_t/60, pct=gravel_pct)

    return {
        'urban_time_s': urban_t,
        'gravel_time_s': gravel_t,
        'total_time_s': total,
        'urban_pct': urban_pct,
        'gravel_pct': gravel_pct,
    }
# ---------------------- GPX colorization ----------------------

def export_colorized_gpx(points: List[Dict], segments: List[Dict], classifications: List[str], output_file: str):
    """
    Export a colorized GPX: gravel=red (#FF0000), road=blue (#0000FF).
    Classification is at the segment level; each point inherits the
    classification of the following segment.
    """
    if len(segments) != len(classifications):
        raise ValueError(_t("len_mismatch_segments_classifications"))

    # Création de l'arbre XML
    gpx = ET.Element('gpx', version='1.1', creator='gpx_tools_v3', xmlns='http://www.topografix.com/GPX/1/1')
    trk = ET.SubElement(gpx, 'trk')
    name = ET.SubElement(trk, 'name')
    name.text = 'GPX Colorized'
    trkseg = ET.SubElement(trk, 'trkseg')

    # Pour chaque point, on prend la classe du segment suivant
    for i, p in enumerate(points):
        if i == 0:
            cls = classifications[0]
        elif i-1 < len(classifications):
            cls = classifications[i-1]
        else:
            cls = classifications[-1]

        trkpt = ET.SubElement(trkseg, 'trkpt', lat=str(p['lat']), lon=str(p['lon']))
        if 'ele' in p:
            ele = ET.SubElement(trkpt, 'ele')
            ele.text = f"{p['ele']:.2f}"

        #ele = ET.SubElement(trkpt, 'ele')
        #ele.text = f"{p['ele']:.2f}"
        time = ET.SubElement(trkpt, 'time')
        if isinstance(p['time'], datetime):
            time.text = p['time'].isoformat()
        else:
            time.text = str(p['time'])
        ext = ET.SubElement(trkpt, 'extensions')
        color = ET.SubElement(ext, 'color')
        color.text = '#FF000000' if cls == 'gravel' else '#0000FF'
        

    tree = ET.ElementTree(gpx)
    tree.write(output_file, encoding='utf-8', xml_declaration=True)


# ---------------------- Utility ----------------------

def check_is_pure_road(gpx_file: str, 
                       window_s=8,
                       distance_threshold=150.0,
                       min_gravel_in_window=3) -> (List[str], float, float, List[Dict], List[Dict]):
    points = load_gpx_points(gpx_file)
    segments = gpx_to_segments(points)
    classe0 = detect_gravel_segments(segments, window_s=window_s)
    classifications =propagate_gravel( segments, classe0,window_dist=distance_threshold,min_gravel_in_window=min_gravel_in_window)
    score_by_segments = compute_gravel_score(classifications)
    score_by_time = compute_gravel_score_by_time(classifications, segments)
    return classifications, score_by_segments, score_by_time, segments, points




def export_gpx_multitrack_garmin(points, segments, classes, output_file):
    """
    Export GPX compatible with GPXSee using Garmin colors:
    - road  -> green
    - gravel -> red
    One GPX, multiple <trk>, Garmin extensions.
    """

    if len(segments) != len(classes):
        raise ValueError(_t("len_mismatch_segments_classes"))

    NS_GPX = "http://www.topografix.com/GPX/1/1"
    NS_GPXX = "http://www.garmin.com/xmlschemas/GpxExtensions/v3"

    ET.register_namespace("", NS_GPX)
    ET.register_namespace("gpxx", NS_GPXX)

    gpx = ET.Element(
        "gpx",
        version="1.1",
        creator="gpx_tools"
    )

    def start_new_track(track_type, idx):
        trk = ET.SubElement(gpx, "trk")

        name = ET.SubElement(trk, "name")
        name.text = f"{track_type.capitalize()} #{idx}"

        ext = ET.SubElement(trk, "extensions")
        trk_ext = ET.SubElement(ext, f"{{{NS_GPXX}}}TrackExtension")
        color = ET.SubElement(trk_ext, f"{{{NS_GPXX}}}DisplayColor")
        color.text = "Green" if track_type == "road" else "Red"

        return ET.SubElement(trk, "trkseg")

    def add_point(trkseg, p):
        trkpt = ET.SubElement(
            trkseg,
            "trkpt",
            lat=str(p["lat"]),
            lon=str(p["lon"])
        )
        if "ele" in p:
            ele = ET.SubElement(trkpt, "ele")
            ele.text = f"{p['ele']:.2f}"
        if "time" in p and isinstance(p["time"], datetime):
            t = ET.SubElement(trkpt, "time")
            t.text = p["time"].isoformat()

    # --- Construction des tracks ---
    current_class = classes[0]
    trk_index = 1
    trkseg = start_new_track(current_class, trk_index)
    add_point(trkseg, points[0])

    for i, cls in enumerate(classes):
        if cls != current_class:
            current_class = cls
            trk_index += 1
            trkseg = start_new_track(current_class, trk_index)

        add_point(trkseg, points[i + 1])

    # --- Indentation pour lisibilité ---
    indent_xml(gpx)

    ET.ElementTree(gpx).write(
        output_file,
        encoding="utf-8",
        xml_declaration=True
    )


def indent_xml(elem, level=0):
    """
    Add line breaks and indentation (pretty print XML).
    Compatible with standard ElementTree.
    """
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for child in elem:
            indent_xml(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = i
    if level and (not elem.tail or not elem.tail.strip()):
        elem.tail = i

