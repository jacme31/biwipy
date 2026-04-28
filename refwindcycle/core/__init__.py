from importlib import import_module
from typing import Any

__all__ = [
	"simulate_with_weather",
	"simulate_future_route",
	"simulate_replay_route",
	"estimate_P0_from_v0",
	"solve_speed_dynamic",
	"CyclistBehavior",
	"create_competitive_profile",
	"Simulator",
	"SimulationResult",
	"DistanceAnalysis",
	"TimeAnalysis",
	"SpeedAnalysis",
	"PowerAnalysis",
	"WindAnalysis",
	"GustAnalysis",
	"SlopeAnalysis",
	"SlopeStats",
	"WindAlongTrajectoryAnalysis",
	"WindAlongSegment",
	"NumericStats",
	"CrosswindAnalysis",
	"WindScore",
]


def __getattr__(name: str) -> Any:
	if name in {
		"simulate_with_weather",
		"simulate_future_route",
		"simulate_replay_route",
		"estimate_P0_from_v0",
		"solve_speed_dynamic",
	}:
		module = import_module(".bike_physics", __name__)
		return getattr(module, name)

	if name in {"CyclistBehavior", "create_competitive_profile"}:
		module = import_module(".cyclist_params", __name__)
		return getattr(module, name)

	if name == "Simulator":
		module = import_module(".simulator", __name__)
		return getattr(module, name)

	if name in {
		"SimulationResult",
		"DistanceAnalysis",
		"TimeAnalysis",
		"SpeedAnalysis",
		"PowerAnalysis",
		"WindAnalysis",
		"GustAnalysis",
		"SlopeAnalysis",
		"SlopeStats",
		"WindAlongTrajectoryAnalysis",
		"WindAlongSegment",
		"NumericStats",
		"CrosswindAnalysis",
		"WindScore",
	}:
		module = import_module(".simulation_result", __name__)
		return getattr(module, name)

	raise AttributeError(f"module 'refwindcycle.core' has no attribute {name!r}")
