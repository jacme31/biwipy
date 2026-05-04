from datetime import datetime
from typing import List, Optional

from .grib_manager import Grib


class WeatherProvider:
    """
    Stable public interface for weather data access (GRIB).

    - get_wind(): retrieve tws/twd/gust at a point
    - wind_impact(): project wind onto a segment
    - purge_before(dt): discard all timesteps before *dt* (memory management)
    - purge_between(dt1, dt2): discard timesteps in a closed interval
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

    def purge_before(self, dt: datetime) -> int:
        """
        Remove all forecast timesteps strictly before *dt*.

        Returns the number of timesteps removed.
        """
        return self.grib.purge_before(dt)

    def purge_between(self, dt1: datetime, dt2: datetime) -> int:
        """
        Remove forecast timesteps in the closed interval [*dt1*, *dt2*].

        Returns the number of timesteps removed.
        """
        return self.grib.purge_between(dt1, dt2)

    @classmethod
    def from_grib(cls, grib: Grib) -> "WeatherProvider":
        """Wrap an existing Grib instance without reloading files."""
        obj = cls.__new__(cls)
        obj.grib = grib
        return obj
