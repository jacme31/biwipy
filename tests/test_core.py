"""
Tests unitaires pour bike_physics.py et cyclist_params.py

Tests couvrant:
- Constantes physiques et downhill limiter
- Modes de comportement cycliste (realistic, conservative, aggressive)
- Calcul de vitesses et puissances
- Interpolation air et densité
"""

import unittest
import sys
import os
import math

# Put the package in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from biwipy.core import bike_physics
from biwipy.core.cyclist_params import CyclistBehavior


class TestCyclistBehavior(unittest.TestCase):
    """Tests pour la classe CyclistBehavior"""
    
    def test_behavior_creation_default(self):
        """Créer un profil par défaut (realistic)"""
        behavior = CyclistBehavior()
        self.assertEqual(behavior.mode_uphill, 'realistic')
        self.assertEqual(behavior.mode_downhill, 'realistic')
        self.assertEqual(behavior.mode_corner, 'realistic')
    
    def test_behavior_creation_mixed(self):
        """Créer un profil mixte"""
        behavior = CyclistBehavior(uphill='conservative', downhill='aggressive', corner='realistic')
        self.assertEqual(behavior.mode_uphill, 'conservative')
        self.assertEqual(behavior.mode_downhill, 'aggressive')
        self.assertEqual(behavior.mode_corner, 'realistic')
    
    def test_behavior_invalid_mode(self):
        """Rejeter un mode invalide"""
        with self.assertRaises(ValueError):
            CyclistBehavior(uphill='invalid_mode')
    
    def test_behavior_attributes_present(self):
        """Vérifier que tous les attributs clés sont présents"""
        behavior = CyclistBehavior()
        # Uphill
        self.assertTrue(hasattr(behavior, 'uphill_facteur_forte'))
        self.assertTrue(hasattr(behavior, 'uphill_facteur_moderee'))
        self.assertTrue(hasattr(behavior, 'uphill_facteur_legere'))
        # Downhill
        self.assertTrue(hasattr(behavior, 'downhill_facteur_legere'))
        self.assertTrue(hasattr(behavior, 'downhill_facteur_forte'))
        self.assertTrue(hasattr(behavior, 'downhill_vitesse_max_absolue'))
        # Corner
        self.assertTrue(hasattr(behavior, 'corner_speed_straight'))
        self.assertTrue(hasattr(behavior, 'corner_speed_slight'))
    
    def test_behavior_mode_differences(self):
        """Vérifier que les modes ont des paramètres différents"""
        realistic = CyclistBehavior(uphill='realistic')
        conservative = CyclistBehavior(uphill='conservative')
        aggressive = CyclistBehavior(uphill='aggressive')
        
        # En montée forte, les trois modes doivent différer
        self.assertNotEqual(realistic.uphill_facteur_forte, conservative.uphill_facteur_forte)
        self.assertNotEqual(realistic.uphill_facteur_forte, aggressive.uphill_facteur_forte)
    
    def test_behavior_get_corner_speed_limit(self):
        """Tester la méthode get_corner_speed_limit()"""
        behavior = CyclistBehavior()
        # < 5°: straight
        speed = behavior.get_corner_speed_limit(3)
        self.assertAlmostEqual(speed, behavior.corner_speed_straight)
        # 20°: slight
        speed = behavior.get_corner_speed_limit(20)
        self.assertAlmostEqual(speed, behavior.corner_speed_slight)


class TestBikePhysics(unittest.TestCase):
    """Tests pour le moteur de physique bike_physics"""
    
    def test_constants_loaded(self):
        """Vérifie que les constantes critiques sont présentes"""
        # Ces constantes ont été ajoutées/modifiées lors des corrections de descente (Jan 2026)
        self.assertTrue(hasattr(bike_physics, 'DESCENTE_VITESSE_MAX_REDUCTION_FACTOR'))
        self.assertTrue(hasattr(bike_physics, 'DESCENTE_VITESSE_MAX_REDUCTION_CAP'))
        self.assertTrue(hasattr(bike_physics, 'SEUIL_DESCENTE_MAX'))
        
        # Vérif des valeurs (selon instructions)
        self.assertAlmostEqual(bike_physics.DESCENTE_VITESSE_MAX_REDUCTION_FACTOR, 2.5)
        self.assertAlmostEqual(bike_physics.DESCENTE_VITESSE_MAX_REDUCTION_CAP, 0.40)

    def test_air_density_sea_level(self):
        """Densité de l'air au niveau de la mer"""
        rho = bike_physics.calculate_air_density(0)
        # ISA: 1.225 kg/m³ à 15°C, 0m
        self.assertAlmostEqual(rho, 1.225, places=2)
    
    def test_air_density_altitude(self):
        """Densité décroît avec l'altitude"""
        rho_0 = bike_physics.calculate_air_density(0)
        rho_1000 = bike_physics.calculate_air_density(1000)
        rho_2000 = bike_physics.calculate_air_density(2000)
        
        self.assertGreater(rho_0, rho_1000)
        self.assertGreater(rho_1000, rho_2000)

    def test_solve_speed_for_power_flat(self):
        """Test puissance sur le plat sans vent"""
        P = 200
        CdA = 0.35
        Cr = 0.005
        m = 85
        slope = 0.0
        wind = 0.0
        
        speed = bike_physics.solve_speed_for_power(P, CdA, Cr, m, slope, wind)
        # Vérif cohérence: ~9 m/s (32 km/h) pour 200W
        self.assertGreater(speed, 8.0)
        self.assertLess(speed, 10.0)

    def test_solve_speed_for_power_headwind(self):
        """Vent de face réduit la vitesse"""
        P = 200
        CdA = 0.35
        Cr = 0.005
        m = 85
        slope = 0.0
        
        speed_no_wind = bike_physics.solve_speed_for_power(P, CdA, Cr, m, slope, 0.0)
        speed_headwind = bike_physics.solve_speed_for_power(P, CdA, Cr, m, slope, 5.0)
        
        self.assertLess(speed_headwind, speed_no_wind)

    def test_solve_speed_for_power_uphill(self):
        """Pente montante réduit la vitesse"""
        P = 200
        CdA = 0.35
        Cr = 0.005
        m = 85
        wind = 0.0
        
        speed_flat = bike_physics.solve_speed_for_power(P, CdA, Cr, m, 0.0, wind)
        speed_uphill = bike_physics.solve_speed_for_power(P, CdA, Cr, m, 0.05, wind)
        
        self.assertLess(speed_uphill, speed_flat)

    def test_descent_limiter(self):
        """Vérifie que la vitesse en descente forte est limitée (Jan 2026 fix)"""
        P = 100
        CdA = 0.35
        Cr = 0.005
        m = 85
        slope = -0.10  # -10% descente
        wind = -5.0    # Vent arrière 5 m/s
        
        speed = bike_physics.solve_speed_for_power(P, CdA, Cr, m, slope, wind)
        
        # Le limiteur doit plafonner la vitesse en descente forte
        # Réaliste: ~20-22 m/s (72-79 km/h), pas 30+ m/s
        self.assertLess(speed, 30.0, "La vitesse en descente -10% excède 108 km/h, limiteur inactif ?")
        self.assertGreater(speed, 15.0, "La vitesse en descente -10% est anormalement basse")

    def test_solve_speed_dynamic_acceleration(self):
        """Test d'accélération dynamique"""
        P = 300
        CdA = 0.35
        Cr = 0.005
        m = 85
        slope = 0.0
        wind = 0.0
        v_init = 5.0  # 18 km/h
        dist = 500
        
        v_final, v_avg, duration = bike_physics.solve_speed_dynamic(P, CdA, Cr, m, slope, wind, v_init, dist)
        
        self.assertGreater(v_final, v_init, "Devrait accélérer avec 300W")
        self.assertGreater(v_avg, v_init)
        self.assertLess(v_avg, v_final)

    def test_calculate_adaptive_power_with_behavior(self):
        """Tester calculate_adaptive_power avec différents comportements"""
        P0 = 200
        slope = 0.08  # 8% montée
        
        behavior_realistic = CyclistBehavior(uphill='realistic')
        behavior_conservative = CyclistBehavior(uphill='conservative')
        behavior_aggressive = CyclistBehavior(uphill='aggressive')
        
        P_realistic = bike_physics.calculate_adaptive_power(P0, slope, behavior_realistic)
        P_conservative = bike_physics.calculate_adaptive_power(P0, slope, behavior_conservative)
        P_aggressive = bike_physics.calculate_adaptive_power(P0, slope, behavior_aggressive)
        
        # En montée, tous doivent être > P0 (réduction de vitesse = plus de puissance)
        self.assertGreater(P_realistic, P0)
        self.assertGreater(P_conservative, P0)
        self.assertGreater(P_aggressive, P0)
        
        # Aggressive applique PLUS de facteur que conservative (plus d'effort en montée)
        self.assertGreater(P_aggressive, P_conservative)

    def test_calculate_adaptive_power_downhill(self):
        """Tester calculate_adaptive_power en descente"""
        P0 = 200
        slope = -0.08  # -8% descente
        
        behavior = CyclistBehavior(downhill='realistic')
        P_adapted = bike_physics.calculate_adaptive_power(P0, slope, behavior)
        
        # En descente, la puissance devrait être fortement réduite
        self.assertLess(P_adapted, P0)

    def test_get_default_behavior(self):
        """Vérifier la fonction get_default_behavior()"""
        default_behavior = bike_physics.get_default_behavior()
        self.assertIsInstance(default_behavior, CyclistBehavior)
        self.assertEqual(default_behavior.mode_uphill, 'realistic')


class TestWindCalculations(unittest.TestCase):
    """Tests pour les calculs de vent"""
    
    def test_wind_projection_basic(self):
        """Projection basique du vent sur un segment"""
        # On teste via solve_speed_for_power avec différents vents
        P = 200
        CdA = 0.35
        Cr = 0.005
        m = 85
        slope = 0.0
        
        # Vent arrière négatif (tailwind) -> plus rapide
        # Vent de face positif (headwind) -> plus lent
        speed_tailwind = bike_physics.solve_speed_for_power(P, CdA, Cr, m, slope, -5.0)
        speed_headwind = bike_physics.solve_speed_for_power(P, CdA, Cr, m, slope, 5.0)
        
        self.assertGreater(speed_tailwind, speed_headwind)


class TestPhysicsCoherence(unittest.TestCase):
    """Tests de cohérence physique"""
    
    def test_higher_power_faster_speed(self):
        """Plus de puissance = plus vite (sur le plat)"""
        CdA = 0.35
        Cr = 0.005
        m = 85
        slope = 0.0
        wind = 0.0
        
        speed_200W = bike_physics.solve_speed_for_power(200, CdA, Cr, m, slope, wind)
        speed_300W = bike_physics.solve_speed_for_power(300, CdA, Cr, m, slope, wind)
        
        self.assertLess(speed_200W, speed_300W)
    
    def test_heavier_mass_slower_speed(self):
        """Plus lourd = plus lent (montée)"""
        P = 200
        CdA = 0.35
        Cr = 0.005
        slope = 0.05
        wind = 0.0
        
        speed_75kg = bike_physics.solve_speed_for_power(P, CdA, Cr, 75, slope, wind)
        speed_100kg = bike_physics.solve_speed_for_power(P, CdA, Cr, 100, slope, wind)
        
        self.assertGreater(speed_75kg, speed_100kg)


if __name__ == '__main__':
    unittest.main()
