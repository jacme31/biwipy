from importlib import import_module
from typing import Any

__all__ = [
	"RouteAnalyzer",
	"GPXProcessingResult",
	"cut_segments_by_km",
	"gpx_tools",
	"anareswind",
	"gravel_detection",
	"tactical_analysis",
	"CLIMB_PROFILES",
	"get_climb_profile",
]


def __getattr__(name: str) -> Any:
	if name in {"RouteAnalyzer", "GPXProcessingResult", "cut_segments_by_km"}:
		module = import_module(".route_analyzer", __name__)
		return getattr(module, name)

	if name in {"gpx_tools", "anareswind", "gravel_detection", "tactical_analysis"}:
		return import_module(f".{name}", __name__)

	if name in {"CLIMB_PROFILES", "get_climb_profile"}:
		module = import_module(".anareswind", __name__)
		return getattr(module, name)

	raise AttributeError(f"module 'refwindcycle.analysis' has no attribute {name!r}")
