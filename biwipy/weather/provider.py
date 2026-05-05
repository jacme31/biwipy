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

    def purge_before(self, dt):
        """Remove all timesteps strictly before the given datetime."""
        return self.grib.purge_before(dt)

    def purge_between(self, dt1, dt2):
        """Remove all timesteps within the closed interval [dt1, dt2] inclusive."""
        return self.grib.purge_between(dt1, dt2)

    @classmethod
    def from_grib(cls, grib: Grib) -> "WeatherProvider":
        """Wrap an existing Grib instance without reloading files."""
        obj = cls.__new__(cls)
        obj.grib = grib
        return obj
