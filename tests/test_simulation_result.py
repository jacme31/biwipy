# -*- coding: utf-8 -*-
"""
Test de la structure SimulationResult

Valide que les classes se construisent correctement et la sérialisation JSON fonctionne.
"""

import json
import pytest
from biwipy.core import (
    SimulationResult,
    DistanceAnalysis,
    TimeAnalysis,
    SpeedAnalysis,
    PowerAnalysis,
    WindAnalysis,
    GustAnalysis,
    SlopeAnalysis,
    SlopeStats,
    WindAlongTrajectoryAnalysis,
    WindAlongSegment,
    NumericStats,
    CrosswindAnalysis,
    WindScore,
)


def test_numeric_stats():
    """Test NumericStats"""
    stats = NumericStats(avg=3.93, min=2.30, max=8.03, min_at_km=5.0, max_at_km=45.0)
    assert stats.avg == 3.93
    assert stats.min == 2.30
    d = stats.to_dict()
    assert d['avg'] == 3.93
    print("✓ NumericStats OK")


def test_slope_stats():
    """Test SlopeStats"""
    terrain = SlopeStats(
        avg_pct=0.18,
        min_pct=-6.45,
        max_pct=9.98,
        deniv_pos_m=195,
        deniv_neg_m=196,
    )
    d = terrain.to_dict()
    assert d['avg_pct'] == 0.18
    assert d['deniv_total_m'] == 391.0  # 195 + 196
    print("✓ SlopeStats OK")


def test_wind_along_segment():
    """Test WindAlongSegment"""
    headwind = WindAlongSegment(
        percentage=44.9,
        distance_km=23.08,
        avg_kmh=2.73,
        min_kmh=0.01,
        max_kmh=5.36,
        min_at_km=9.43,
        max_at_km=11.23,
    )
    d = headwind.to_dict()
    assert d['percentage'] == 44.9
    assert d['distance_km'] == 23.08
    print("✓ WindAlongSegment OK")


def test_crosswind_analysis():
    """Test CrosswindAnalysis"""
    crosswind = CrosswindAnalysis(
        avg_kmh=3.5,
        min_kmh=0.0,
        max_kmh=8.2,
        min_at_km=5.0,
        max_at_km=30.0,
    )
    assert crosswind.avg_kmh == 3.5
    d = crosswind.to_dict()
    assert d['avg_kmh'] == 3.5
    assert d['max_kmh'] == 8.2
    print("✓ CrosswindAnalysis OK")


def test_wind_score():
    """Test WindScore"""
    # Test with values
    score = WindScore(
        grade='B',
        reason='performance',
        performance_grade='B',
        performance_score=-1.5,
        safety_grade='A',
        safety_danger_score=0,
    )
    assert score.grade == 'B'
    assert score.reason == 'performance'
    d = score.to_dict()
    assert d['grade'] == 'B'
    assert d['performance_grade'] == 'B'
    
    # Test with None (placeholder)
    score_empty = WindScore()
    assert score_empty.grade is None
    assert score_empty.reason is None
    d_empty = score_empty.to_dict()
    assert d_empty['grade'] is None
    
    print("✓ WindScore OK")


@pytest.fixture
def result():
    """Fixture pour créer un SimulationResult de test"""
    
    # Données de test (exemple TDF stage)
    segments = [
        {'distance': 100, 'speed_m_s': 25/3.6, 'slope': 0.01},
        {'distance': 100, 'speed_m_s': 26/3.6, 'slope': -0.02},
    ]
    
    return SimulationResult(
        segments=segments,
        distance=DistanceAnalysis(total_km=51.44, segment_count=4837),
        time=TimeAnalysis(
            total_seconds=7733.4,
            total_minutes=128.89,
            total_hours=2.15,
        ),
        speed=SpeedAnalysis(
            avg=23.95,
            min=0.50,
            max=68.30,
            moving_avg=24.12,
        ),
        power=PowerAnalysis(
            avg=185.5,
            min=10.0,
            max=1200.0,
            P0_calibrated=180.0,
        ),
        wind=WindAnalysis(
            tws=NumericStats(avg=1.092, min=0.637, max=2.231, min_at_km=0.0, max_at_km=40.0),
            twd_avg=161.0,
            twd_compass='SSE',
        ),
        gusts=GustAnalysis(
            avg=1.407,  # m/s
            min=0.830,
            max=2.539,
            min_at_km=39.92,
            max_at_km=0.00,
        ),
        slopes=SlopeAnalysis(
            terrain=SlopeStats(
                avg_pct=0.18,
                min_pct=-6.45,
                max_pct=9.98,
                deniv_pos_m=195,
                deniv_neg_m=196,
            ),
            virtual=SlopeStats(
                avg_pct=-0.00,
                min_pct=-1.69,
                max_pct=0.99,
                deniv_pos_m=92,
                deniv_neg_m=-100,
            ),
            effective=SlopeStats(
                avg_pct=0.17,
                min_pct=-15.55,
                max_pct=15.17,
                deniv_pos_m=287,
                deniv_neg_m=96,
            ),
        ),
        wind_along_trajectory=WindAlongTrajectoryAnalysis(
            headwind=WindAlongSegment(
                percentage=44.9,
                distance_km=23.08,
                avg_kmh=2.73,
                min_kmh=0.01,
                max_kmh=5.36,
                min_at_km=9.43,
                max_at_km=11.23,
            ),
            tailwind=WindAlongSegment(
                percentage=55.1,
                distance_km=28.36,
                avg_kmh=-2.08,
                min_kmh=-0.00,
                max_kmh=-8.19,
                min_at_km=24.71,
                max_at_km=0.50,
            ),
        ),
        crosswind=CrosswindAnalysis(
            avg_kmh=3.5,
            min_kmh=0.0,
            max_kmh=8.2,
            min_at_km=5.0,
            max_at_km=30.0,
        ),
        wind_score=WindScore(
            grade='B',
            reason='performance',
            performance_grade='B',
            performance_score=-1.5,
            safety_grade='A',
            safety_danger_score=0,
        ),
    )


def test_simulation_result_building(result):
    """Test construction complète de SimulationResult"""
    
    # Validations
    assert result.segment_count() == 2
    assert result.distance.total_km == 51.44
    assert result.speed.avg == 23.95
    assert result.power.P0_calibrated == 180.0
    assert result.wind.twd_compass == 'SSE'
    print("✓ SimulationResult construction OK")


def test_to_dict_serialization(result):
    """Test sérialisation to_dict()"""
    data = result.to_dict()
    
    # Segments NE DOIVENT PAS être inclus
    assert 'segments' not in data
    
    # Tous les domaines doivent être présents
    assert 'distance' in data
    assert 'time' in data
    assert 'speed' in data
    assert 'power' in data
    assert 'wind' in data
    assert 'gusts' in data
    assert 'slopes' in data
    assert 'wind_along_trajectory' in data
    assert 'crosswind' in data
    assert 'wind_score' in data
    
    # Vérifier structure imbriquée vent
    assert data['wind']['tws']['avg_kmh'] > 0
    assert data['wind']['twd']['compass'] == 'SSE'
    
    # Vérifier structure imbriquée pentes
    assert 'terrain' in data['slopes']
    assert 'virtual_wind' in data['slopes']
    assert 'effective' in data['slopes']
    
    # Vérifier crosswind
    assert data['crosswind']['avg_kmh'] == 3.5
    assert data['crosswind']['max_kmh'] == 8.2
    
    # Vérifier wind_score
    assert data['wind_score']['grade'] == 'B'
    assert data['wind_score']['reason'] == 'performance'
    
    print("✓ to_dict() structure OK")


def test_json_export(result):
    """Test export JSON complet"""
    data = result.to_dict()
    json_str = json.dumps(data, indent=2)
    
    # Doit être valide JSON
    reloaded = json.loads(json_str)
    assert reloaded['distance']['total_km'] == 51.44
    assert reloaded['speed']['avg_kmh'] == 23.95
    assert reloaded['slopes']['terrain']['deniv_pos_m'] == 195
    
    print("✓ JSON export OK")
    print("\nJSON Export sample (première 500 chars):")
    print(json_str[:500] + "...\n")


def test_segments_accessor(result):
    """Test que les segments sont accessibles mais pas sérialisés"""
    # Voir les segments
    segs = result.get_segments()
    assert len(segs) == 2
    
    # to_dict() ne les inclut pas
    data = result.to_dict()
    assert 'segments' not in data
    
    print("✓ Segments accessor OK")


if __name__ == '__main__':
    print("\n" + "="*70)
    print("TEST: SimulationResult Structure with Crosswind & WindScore")
    print("="*70 + "\n")
    
    test_numeric_stats()
    test_slope_stats()
    test_wind_along_segment()
    test_crosswind_analysis()
    test_wind_score()
    
    result = test_simulation_result_building()
    test_to_dict_serialization(result)
    test_json_export(result)
    test_segments_accessor(result)
    
    print("\n" + "="*70)
    print("✓ TOUS LES TESTS PASSENT (9/9)")
    print("="*70 + "\n")
