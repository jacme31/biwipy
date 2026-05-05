
import unittest
import numpy as np
from datetime import datetime, timezone
import sys
import os

# Put the package in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from biwipy.weather.grib_manager import Grib
    HAS_GRIB = True
except ImportError:
    HAS_GRIB = False
    Grib = object  # Placeholder

@unittest.skipIf(not HAS_GRIB, "PyGRIB not available on this platform")
class MockGrib(Grib if HAS_GRIB else object):
    """
    Sous-classe de Grib pour simuler des données sans fichiers.
    On surcharge __init__ pour ne pas lire de fichiers, et on remplit manuellement les listes.
    """
    def __init__(self, resolution=0.25):
        self.model = "MOCK"
        self.resolution = resolution
        self.inv_res = 1.0 / self.resolution
        self.grib_limit = (0.0, 359.75, -90.0, 90.0) # Default
        
        # Grid bounds
        self.grid_lon_min = 0.0
        self.grid_lon_max = 359.75
        self.grid_lat_min = -90.0
        self.grid_lat_max = 90.0
        
        # Stats initialization (usually done in Grib.__init__)
        self.Tot_time_pointvalidity = 0.0
        self.Tot_time_interpol = 0.0

        self.lst_gribtimes = [datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)]
        self.lst_u10 = []
        self.lst_v10 = []
        self.lst_gust = []
        
        # Generation de la grille commme dans Grib
        step_inv = int(self.inv_res)
        self.nlatitude = int(180 * step_inv) + 1
        self.nlongitude = int(360 * step_inv)

        # Création de données synthétiques
        # Convention GFS/Grib habituelle : Index 0 = Nord (+90), Index Max = Sud (-90)
        # On va remplir u10 avec la valeur de la latitude pour vérifier l'indexation
        
        # Grille latitudes (Nord vers Sud pour le stockage des données)
        lats_axis = np.linspace(90, -90, self.nlatitude)
        # Grille longitudes (0 à 360)
        lons_axis = np.linspace(0, 360 - self.resolution, self.nlongitude)
        
        # On crée une grille où U10 = latitude du point
        # V10 = longitude du point
        u10_grid = np.zeros((self.nlatitude, self.nlongitude))
        v10_grid = np.zeros((self.nlatitude, self.nlongitude))
        
        # Remplissage par broadcasting
        # u10_grid: chaque ligne i (correspondant à une lat) reçoit cette lat
        for i in range(self.nlatitude):
            u10_grid[i, :] = lats_axis[i] 
            
        # v10_grid: chaque colonne j (correspondant à une lon) reçoit cette lon
        for j in range(self.nlongitude):
            v10_grid[:, j] = lons_axis[j] 

        self.lst_u10.append(u10_grid)
        self.lst_v10.append(v10_grid)
        self.lst_gust.append(np.zeros((self.nlatitude, self.nlongitude))) 
        
        # Initialisation des tables internes utilisées par Grib (pour compatibilité)
        self.table_latitude = []
        self.table_longitude = []
        # Note: Grib.__init__ génère table_latitude de -90 à +90 (South->North)
        # Mais le stockage des données (lst_u10) est souvent North->South dans les GRIBs
        # Validation_logic: testons si grib_uvgust utilise bien (90-y)
        lat_points = int(180 * step_inv) + 1
        lon_points = int(360 * step_inv)
        for i in range(0, lat_points):
            self.table_latitude.append(float((i/step_inv-90)))
        for i in range(0, lon_points):
            self.table_longitude.append(float((i/step_inv)))

class TestGridLogic(unittest.TestCase):
    
    def test_resolution_025_standard(self):
        """Test de la résolution standard 0.25°"""
        res = 0.25
        mgrb = MockGrib(resolution=res)
        
        # Ajoutons une frame identique +1h pour interpolation temporelle
        mgrb.lst_gribtimes.append(datetime(2026, 1, 1, 13, 0, 0, tzinfo=timezone.utc))
        mgrb.lst_u10.append(mgrb.lst_u10[0])
        mgrb.lst_v10.append(mgrb.lst_v10[0])
        mgrb.lst_gust.append(mgrb.lst_gust[0])

        # Test direct de l'indexation via grib_uvgust
        accessor = mgrb.grib_uvgust(0) # frame 0
        
        # Cas 1: 45N, 0E. Attendu: u=45, v=0
        # grib_uvgust(x, y) -> access [int((90-y)*inv_res)][int(inv_res*x)]
        # Si y=45, index_lat = (90-45)*4 = 180.
        # Dans notre Mock, index 0 = 90N. Index 180 correspond bien à 45N ?
        # 180 steps * 0.25 = 45 deg de delta. 90 - 45 = 45. OUI.
        
        u, v, g = accessor(0, 45) 
        self.assertAlmostEqual(u, 45.0, msg="Echec indexation Latitude 45N (0.25)")
        self.assertAlmostEqual(v, 0.0, msg="Echec indexation Longitude 0E (0.25)")

        # Cas 2: -45S, 10E. Attendu: u=-45, v=10
        # y=-45. index_lat = (90 - (-45))*4 = 135 * 4 = 540.
        # 540 steps * 0.25 = 135 deg delta from 90N. 90 - 135 = -45. OUI.
        u, v, g = accessor(10, -45)
        self.assertAlmostEqual(u, -45.0, msg="Echec indexation Latitude 45S (0.25)")
        self.assertAlmostEqual(v, 10.0, msg="Echec indexation Longitude 10E (0.25)")
        
        print("\n[OK] Validation Résolution 0.25° (Standard)")

    def test_resolution_050_custom(self):
        """Test d'une résolution non-standard 0.5°"""
        res = 0.5
        mgrb = MockGrib(resolution=res)
        
        # Vérif dimensions
        expected_lat_points = 180 * 2 + 1 # 361
        self.assertEqual(mgrb.nlatitude, expected_lat_points, "Mauvaise dimension lat pour 0.5°")
        
        accessor = mgrb.grib_uvgust(0)

        # Cas 1: 90N (Pole Nord). Index 0. Attendu u=90.
        u, v, g = accessor(0, 90)
        self.assertAlmostEqual(u, 90.0, msg="Echec indexation Pole Nord (0.5)")

        # Cas 2: -90S (Pole Sud). Index max. Attendu u=-90.
        u, v, g = accessor(0, -90)
        self.assertAlmostEqual(u, -90.0, msg="Echec indexation Pole Sud (0.5)")

        # Cas 3: 45.5N. C'est sur la grille (45.5 * 2 = 91 entier).
        # index = (90 - 45.5) * 2 = 44.5 * 2 = 89.
        # 89 steps * 0.5 = 44.5 deg delta. 90 - 44.5 = 45.5. OUI.
        u, v, g = accessor(0, 45.5)
        self.assertAlmostEqual(u, 45.5, msg="Echec indexation 45.5N (0.5)")

        print("\n[OK] Validation Résolution 0.5° (Custom)")

    def test_interpolation_spatiale(self):
        """Vérifie que get_wind_at utilise bien les bons points pour interpoler"""
        res = 1.0
        mgrb = MockGrib(resolution=res)
        mgrb.lst_gribtimes.append(datetime(2026, 1, 1, 13, 0, 0, tzinfo=timezone.utc))
        mgrb.lst_u10.append(mgrb.lst_u10[0])
        mgrb.lst_v10.append(mgrb.lst_v10[0])
        mgrb.lst_gust.append(mgrb.lst_gust[0])
        
        # Hack V=0
        mgrb.lst_v10[0][:] = 0
        mgrb.lst_v10[1][:] = 0
        
        # Point cible: 45.5N (entre 45 et 46), 10.0E (sur grille)
        # U à 45N = 45. U à 46N = 46.
        # Interpolation linéaire attendue: 45.5
        
        tws, twd, _, _ = mgrb.get_wind_at(datetime(2026, 1, 1, 12, 30, 0, tzinfo=timezone.utc), 
                                          lat_point=45.5, lon_point=10.0, return_raw=True)
        
        self.assertAlmostEqual(tws, 45.5, delta=0.01, msg="Echec interpolation bilinéaire Latitude")
        
        print("\n[OK] Validation Interpolation Spatiale")

if __name__ == '__main__':
    unittest.main()
