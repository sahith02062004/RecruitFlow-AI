"""
Centralized Matching Engine Configuration for RecruitFlow AI (Phase 5).
Defines standard scoring weights, qualification hierarchy, scoring version,
and weight validation rules.
"""
from typing import Dict, Any


SCORING_VERSION = "1.0.0"

# Default category weights totaling exactly 1.00 (100%)
DEFAULT_WEIGHTS: Dict[str, float] = {
    "required_skills": 0.50,
    "preferred_skills": 0.20,
    "experience": 0.20,
    "qualification": 0.10,
}

# Qualification rank hierarchy: allows partial and full alignment evaluation
QUALIFICATION_RANKS: Dict[str, int] = {
    "none": 0,
    "high school": 0,
    "diploma": 1,
    "associate degree": 1,
    "associate": 1,
    "bachelor": 2,
    "bachelors": 2,
    "bachelor's": 2,
    "bachelor's degree": 2,
    "b.tech": 2,
    "btech": 2,
    "b.e.": 2,
    "be": 2,
    "b.s.": 2,
    "bs": 2,
    "b.sc": 2,
    "bsc": 2,
    "bca": 2,
    "master": 3,
    "masters": 3,
    "master's": 3,
    "master's degree": 3,
    "m.tech": 3,
    "mtech": 3,
    "m.s.": 3,
    "ms": 3,
    "m.sc": 3,
    "msc": 3,
    "mba": 3,
    "mca": 3,
    "doctorate": 4,
    "ph.d": 4,
    "ph.d.": 4,
    "phd": 4,
    "doctor of philosophy": 4,
}


class MatchingConfigError(ValueError):
    """Raised when scoring weights or parameters fail mathematical constraints."""
    pass


def validate_weights(weights: Dict[str, float]) -> Dict[str, float]:
    """
    Validates that category weights are non-negative, include all required categories,
    and sum exactly to 1.0 (with a small floating point tolerance of 1e-4).
    """
    if not isinstance(weights, dict):
        raise MatchingConfigError("Weights must be a dictionary of category: float pairs.")

    expected_categories = {"required_skills", "preferred_skills", "experience", "qualification"}
    missing = expected_categories - set(weights.keys())
    if missing:
        raise MatchingConfigError(f"Missing required weight categories: {missing}")

    for k, v in weights.items():
        if not isinstance(v, (int, float)):
            raise MatchingConfigError(f"Weight for '{k}' must be numeric.")
        if v < 0:
            raise MatchingConfigError(f"Weight for '{k}' cannot be negative.")

    total = sum(weights[k] for k in expected_categories)
    if abs(total - 1.0) > 1e-4:
        raise MatchingConfigError(f"Scoring weights must sum to 1.0 (100%). Found sum: {total:.4f}")

    return {k: float(weights[k]) for k in expected_categories}
