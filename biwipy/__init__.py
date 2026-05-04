from typing import Any

__all__ = ["Simulator", "RouteAnalyzer", "WeatherProvider"]


def __getattr__(name: str) -> Any:
	if name == "Simulator":
		from .core import Simulator

		return Simulator
	if name == "RouteAnalyzer":
		from .analysis import RouteAnalyzer

		return RouteAnalyzer
	if name == "WeatherProvider":
		from .weather import WeatherProvider

		return WeatherProvider
	raise AttributeError(f"module 'biwipy' has no attribute {name!r}")
