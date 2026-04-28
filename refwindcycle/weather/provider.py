from typing import List, Optional

from .grib_manager import Grib


class WeatherProvider:
    """
    Interface publique stable pour l'accès météo (GRIB).

    - get_wind(): récupère tws/twd/gust à un point
    - wind_impact(): projection du vent sur un segment
    """

    def __init__(
        self,
        lfile: List[str],
        bcache: bool = True,
        model: str = "GFS",
        resolution: float = 0.25,
        grib_limit: tuple = (0.0, 359.75, -90.0, 90.0),
    ) -> None:
        self.grib = Grib(
            lfile=lfile,
            bcache=bcache,
            model=model,
            resolution=resolution,
            grib_limit=grib_limit,
        )

    def get_wind(self, tp, lat: float, lon: float):
        return self.grib.get_wind_at(tp, lat, lon)

    def wind_impact(
        self,
        tp,
        lat: float,
        lon: float,
        bearing: float,
        ratio_wind: float = 0.10,
        rugosite: Optional[float] = None,
    ):
        return self.grib.calculate_cycling_wind_impact(
            tp,
            lat,
            lon,
            bearing,
            ratio_wind=ratio_wind,
            rugosite=rugosite,
        )

    @classmethod
    def from_grib(cls, grib: Grib) -> "WeatherProvider":
        """Wrap an existing Grib instance without reloading files."""
        obj = cls.__new__(cls)
        obj.grib = grib
        return obj
