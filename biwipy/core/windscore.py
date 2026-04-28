# -*- coding: utf-8 -*-
"""
WindScore Calculation Module
=============================

Computes wind impact scores for cycling routes based on:
1. Performance (speed impact proxy from headwind effect + wind balance)
2. Safety (absolute wind/gust thresholds)

Final score = max(safety_grade, performance_grade) where F > E > ... > A
(safety always imposes its grade if worse than performance)

Calibrated on multi-month simulations with ground-level wind (roughness 0.58).
"""

from typing import NamedTuple, Optional


# =============================================================================
# CALIBRATED PARAMETERS (adjustable)
# =============================================================================

# Performance proxy (Mar 2026):
# raw_score = -headwind_effect + WIND_BALANCE_WEIGHT * wind_balance_pct
# with:
#   headwind_effect = wind_headwind_avg_kmh * wind_headwind_pct / 100
#   wind_balance_pct = wind_tailwind_pct - wind_headwind_pct
WIND_BALANCE_WEIGHT = 0.03

# Performance grade thresholds on raw performance score
# Ordered ascending: lower score = harder conditions, higher score = easier conditions
PERF_THRESHOLDS = {
    "A": -5.241,  # P10 - hard headwind conditions
    "B": -3.214,  # P30
    "C": -2.289,  # P50 - neutral median
    "D": -1.195,  # P70
    "E": 1.105,   # P90 - very favorable/tailwind conditions
    # F: <= -5.241 ; A: > 1.105
}

# Safety thresholds (absolute values in km/h)
# Calibrated for ground-level wind with roughness 0.58
SAFETY_GUST_THRESHOLDS = (35, 28, 21)  # High/Medium/Low (P97/P92/P80)
SAFETY_WIND_THRESHOLDS = (18, 12)      # High/Medium (P96/P85)
SAFETY_CROSS_THRESHOLDS = (13, 9)      # High/Medium (P96/P85)

# =============================================================================
# OUTPUT DATA STRUCTURE
# =============================================================================

class WindScore(NamedTuple):
    """Wind score result with combined grade and reasoning."""
    grade: str                    # Final grade A-F
    reason: str                   # "safety", "performance", or "safety+performance"
    performance_grade: str        # Performance-only grade
    performance_score: float      # Raw performance score
    safety_grade: str             # Safety-only grade
    safety_danger_score: int      # Raw safety danger points (0-8)


# =============================================================================
# CORE FUNCTIONS
# =============================================================================

def compute_performance_grade(
    wind_headwind_avg_kmh: float,
    wind_headwind_pct: float,
    wind_tailwind_pct: Optional[float] = None,
) -> tuple[str, float]:
    """
    Compute performance grade from headwind effect and wind balance.
    
    Args:
        wind_headwind_avg_kmh: Average headwind component (km/h)
        wind_headwind_pct: Percentage of route facing headwind (0-100)
        wind_tailwind_pct: Percentage of route facing tailwind (0-100).
            If omitted, uses 100 - wind_headwind_pct for backward compatibility.
    
    Returns:
        (grade, raw_score) tuple
    """
    # Compute headwind effect
    headwind_effect = wind_headwind_avg_kmh * wind_headwind_pct / 100.0

    tailwind_pct = (100.0 - wind_headwind_pct) if wind_tailwind_pct is None else wind_tailwind_pct
    wind_balance_pct = tailwind_pct - wind_headwind_pct

    # Positive score => favorable conditions
    raw_score = -headwind_effect + WIND_BALANCE_WEIGHT * wind_balance_pct
    
    # Map to grade (low raw score = hard -> worse grade)
    if raw_score <= PERF_THRESHOLDS["A"]:
        grade = "F"
    elif raw_score <= PERF_THRESHOLDS["B"]:
        grade = "E"
    elif raw_score <= PERF_THRESHOLDS["C"]:
        grade = "D"
    elif raw_score <= PERF_THRESHOLDS["D"]:
        grade = "C"
    elif raw_score <= PERF_THRESHOLDS["E"]:
        grade = "B"
    else:
        grade = "A"
    
    return grade, raw_score


def compute_safety_grade(
    gust_max_kmh: float,
    wind_tws_avg_kmh: float,
    crosswind_avg_kmh: float,
) -> tuple[str, int]:
    """
    Compute safety grade based on absolute wind thresholds.
    
    Independent of wind direction (affects safety regardless of performance benefit).
    
    Args:
        gust_max_kmh: Maximum gust on route (km/h)
        wind_tws_avg_kmh: Average true wind speed (km/h)
        crosswind_avg_kmh: Average crosswind component (km/h)
    
    Returns:
        (grade, danger_score) tuple where danger_score is cumulative penalty (0-8)
    """
    danger_score = 0
    
    # Gust penalty
    if gust_max_kmh > SAFETY_GUST_THRESHOLDS[0]:
        danger_score += 3  # Dangerous gusts
    elif gust_max_kmh > SAFETY_GUST_THRESHOLDS[1]:
        danger_score += 2
    elif gust_max_kmh > SAFETY_GUST_THRESHOLDS[2]:
        danger_score += 1
    
    # Wind average penalty
    if wind_tws_avg_kmh > SAFETY_WIND_THRESHOLDS[0]:
        danger_score += 2  # Very strong wind
    elif wind_tws_avg_kmh > SAFETY_WIND_THRESHOLDS[1]:
        danger_score += 1
    
    # Crosswind penalty
    if crosswind_avg_kmh > SAFETY_CROSS_THRESHOLDS[0]:
        danger_score += 2  # High instability
    elif crosswind_avg_kmh > SAFETY_CROSS_THRESHOLDS[1]:
        danger_score += 1
    
    # Map to grade (higher danger = worse grade)
    if danger_score == 0:
        grade = "A"
    elif danger_score <= 1:
        grade = "B"
    elif danger_score <= 2:
        grade = "C"
    elif danger_score <= 3:
        grade = "D"
    elif danger_score <= 4:
        grade = "E"
    else:
        grade = "F"
    
    return grade, danger_score


def compute_windscore(
    wind_headwind_avg_kmh: float,
    wind_headwind_pct: float,
    gust_max_kmh: float,
    wind_tws_avg_kmh: float,
    crosswind_avg_kmh: float,
    wind_tailwind_pct: Optional[float] = None,
) -> WindScore:
    """
    Compute combined wind score (performance + safety).
    
    Logic: Final grade = max(safety_grade, performance_grade)
    Safety always imposes its grade if worse (F > E > ... > A).
    
    Args:
        wind_headwind_avg_kmh: Average headwind component (km/h)
        wind_headwind_pct: Percentage of route facing headwind (0-100)
        gust_max_kmh: Maximum gust on route (km/h)
        wind_tws_avg_kmh: Average true wind speed (km/h)
        crosswind_avg_kmh: Average crosswind component (km/h)
        wind_tailwind_pct: Percentage of route facing tailwind (0-100).
            Optional for backward compatibility.
    
    Returns:
        WindScore namedtuple with combined result
    """
    # Compute individual scores
    perf_grade, perf_score = compute_performance_grade(
        wind_headwind_avg_kmh,
        wind_headwind_pct,
        wind_tailwind_pct,
    )
    safety_grade, danger_score = compute_safety_grade(
        gust_max_kmh, wind_tws_avg_kmh, crosswind_avg_kmh
    )
    
    # Grade ordering (F worst, A best)
    grade_order = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5}
    
    perf_rank = grade_order[perf_grade]
    safety_rank = grade_order[safety_grade]
    
    # Determine final grade and reason
    if safety_rank > perf_rank:
        final_grade = safety_grade
        reason = "safety"
    elif perf_rank > safety_rank:
        final_grade = perf_grade
        reason = "performance"
    else:
        final_grade = perf_grade  # Equal, both contribute
        reason = "safety+performance"
    
    return WindScore(
        grade=final_grade,
        reason=reason,
        performance_grade=perf_grade,
        performance_score=perf_score,
        safety_grade=safety_grade,
        safety_danger_score=danger_score,
    )


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def grade_description(grade: str) -> str:
    """Get human-readable description for a grade."""
    descriptions = {
        "A": "Excellent conditions (fast, safe)",
        "B": "Good conditions",
        "C": "Moderate conditions",
        "D": "Challenging conditions",
        "E": "Difficult conditions",
        "F": "Severe conditions (slow or dangerous)",
    }
    return descriptions.get(grade, "Unknown")


def update_performance_thresholds(
    p10: float, p30: float, p50: float, p70: float, p90: float
) -> None:
    """
    Update performance grade thresholds (for recalibration).
    
    Args:
        p10, p30, p50, p70, p90: Percentile values from new calibration dataset
    """
    global PERF_THRESHOLDS
    PERF_THRESHOLDS = {
        "A": p10,
        "B": p30,
        "C": p50,
        "D": p70,
        "E": p90,
    }


def update_safety_thresholds(
    gust_high: float,
    gust_med: float,
    gust_low: float,
    wind_high: float,
    wind_med: float,
    cross_high: float,
    cross_med: float,
) -> None:
    """
    Update safety thresholds (for recalibration).
    
    Args:
        gust_high/med/low: Gust thresholds (km/h)
        wind_high/med: Wind average thresholds (km/h)
        cross_high/med: Crosswind thresholds (km/h)
    """
    global SAFETY_GUST_THRESHOLDS, SAFETY_WIND_THRESHOLDS, SAFETY_CROSS_THRESHOLDS
    SAFETY_GUST_THRESHOLDS = (gust_high, gust_med, gust_low)
    SAFETY_WIND_THRESHOLDS = (wind_high, wind_med)
    SAFETY_CROSS_THRESHOLDS = (cross_high, cross_med)


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    # Example 1: Favorable tailwind, safe conditions
    result1 = compute_windscore(
        wind_headwind_avg_kmh=-5.0,  # Tailwind
        wind_headwind_pct=80,
        gust_max_kmh=15.0,
        wind_tws_avg_kmh=8.0,
        crosswind_avg_kmh=3.0,
    )
    print("Example 1 (Tailwind):")
    print(f"  Grade: {result1.grade} - {grade_description(result1.grade)}")
    print(f"  Reason: {result1.reason}")
    print(f"  Performance: {result1.performance_grade} (score={result1.performance_score:.2f})")
    print(f"  Safety: {result1.safety_grade} (danger={result1.safety_danger_score})")
    print()
    
    # Example 2: Strong headwind, moderate safety
    result2 = compute_windscore(
        wind_headwind_avg_kmh=12.0,  # Strong headwind
        wind_headwind_pct=70,
        gust_max_kmh=25.0,
        wind_tws_avg_kmh=15.0,
        crosswind_avg_kmh=8.0,
    )
    print("Example 2 (Headwind):")
    print(f"  Grade: {result2.grade} - {grade_description(result2.grade)}")
    print(f"  Reason: {result2.reason}")
    print(f"  Performance: {result2.performance_grade} (score={result2.performance_score:.2f})")
    print(f"  Safety: {result2.safety_grade} (danger={result2.safety_danger_score})")
    print()
    
    # Example 3: Moderate performance but dangerous gusts (tempête Thil)
    result3 = compute_windscore(
        wind_headwind_avg_kmh=-8.0,  # Tailwind (fast)
        wind_headwind_pct=60,
        gust_max_kmh=55.0,   # Dangerous
        wind_tws_avg_kmh=35.0,
        crosswind_avg_kmh=20.0,
    )
    print("Example 3 (Tempête - safety override):")
    print(f"  Grade: {result3.grade} - {grade_description(result3.grade)}")
    print(f"  Reason: {result3.reason}")
    print(f"  Performance: {result3.performance_grade} (score={result3.performance_score:.2f})")
    print(f"  Safety: {result3.safety_grade} (danger={result3.safety_danger_score})")
