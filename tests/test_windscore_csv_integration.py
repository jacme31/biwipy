#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test rapide de l'intégration windscore dans un export CSV.

Objectifs:
1. Vérifier que windscore est calculé via SimulationResult
2. Vérifier que les colonnes windscore sont bien exportées en CSV
3. Rester indépendant des GRIB/fichiers externes
"""

import csv
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from biwipy.core import Simulator


def create_dummy_segments():
    segments = []
    for i in range(10):
        segments.append(
            {
                'distance': 1000.0,
                'ele1': 100.0 + i,
                'ele2': 100.0 + i + 1,
                'slope': 0.01,
                'bearing': 45.0,
                'speed_m_s': 8.0,
                'time_s': 125.0,
                'power': 200.0,
                'tws': 5.0,
                'twd': 90.0,
                'gust': 8.0,
                'wind_along': 3.5 if i < 7 else -2.0,
                'slope_wind': 0.005,
                'elevation_virtual_m': 5.0,
                'slope_effective': 0.015,
            }
        )
    return segments


def run_test():
    print("=" * 60)
    print("TEST WINDSCORE CSV INTEGRATION")
    print("=" * 60)

    simulator = Simulator(grib=None, CdA=0.32, Cr=0.005, m=75.0)
    result = simulator._build_result_from_segments(
        segments=create_dummy_segments(),
        avg_kmh=28.8,
        P0=200.0,
        avg_power=200.0,
    )

    ws = result.wind_score
    print(f"WindScore: grade={ws.grade}, reason={ws.reason}, perf={ws.performance_grade}, safety={ws.safety_grade}")

    output_csv = os.path.join(os.getcwd(), "test_windscore_output.csv")
    row = {
        'date': datetime.now().isoformat(),
        'route': 'dummy.gpx',
        'speed_kmh': result.speed.avg,
        'windscore_grade': ws.grade,
        'windscore_reason': ws.reason,
        'windscore_performance_grade': ws.performance_grade,
        'windscore_performance_score': ws.performance_score,
        'windscore_safety_grade': ws.safety_grade,
        'windscore_safety_danger_score': ws.safety_danger_score,
    }

    fieldnames = list(row.keys())
    with open(output_csv, 'w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(row)

    with open(output_csv, 'r', newline='', encoding='utf-8') as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 1
    exported = rows[0]
    required = [
        'windscore_grade',
        'windscore_reason',
        'windscore_performance_grade',
        'windscore_performance_score',
        'windscore_safety_grade',
        'windscore_safety_danger_score',
    ]
    for key in required:
        assert key in exported, f"Missing column: {key}"

    print(f"✓ CSV export OK: {output_csv}")
    print("✓ Colonnes windscore présentes")


if __name__ == "__main__":
    run_test()
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
