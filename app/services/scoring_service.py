"""
Scoring Engine Service for RecruitFlow AI (Phase 5).
Computes deterministic, explainable category scores, dynamic weight redistribution,
evidence coverage percentages, and audit-ready matching explanations.
"""
import re
from typing import Dict, Any, List, Optional
from app.services.matching_config import (
    DEFAULT_WEIGHTS,
    QUALIFICATION_RANKS,
    validate_weights,
    SCORING_VERSION
)
from app.services.skill_normalizer import SkillNormalizer


class ScoringService:
    """Computes individual category scores and overall transparent match evaluation."""

    @classmethod
    def score_required_skills(
        cls,
        job_required_skills: Optional[str],
        candidate_skills: Optional[List[str]]
    ) -> Dict[str, Any]:
        """Evaluates alignment on required job skills."""
        target_skills = SkillNormalizer.parse_skills_input(job_required_skills)
        if not target_skills:
            return {
                "category": "required_skills",
                "is_applicable": False,
                "has_evidence": False,
                "score": None,
                "matched": [],
                "missing": [],
                "total_required": 0,
                "explanation": "No required skills specified in job requisition."
            }

        cand_skills = SkillNormalizer.parse_skills_input(candidate_skills)
        matched, missing = SkillNormalizer.match_skills(cand_skills, target_skills)

        score = round((len(matched) / len(target_skills)) * 100.0, 1)
        return {
            "category": "required_skills",
            "is_applicable": True,
            "has_evidence": True,
            "score": score,
            "matched": matched,
            "missing": missing,
            "total_required": len(target_skills),
            "explanation": f"Matched {len(matched)} of {len(target_skills)} required skills ({score}%)."
        }

    @classmethod
    def score_preferred_skills(
        cls,
        job_preferred_skills: Optional[str],
        candidate_skills: Optional[List[str]]
    ) -> Dict[str, Any]:
        """Evaluates alignment on preferred job skills."""
        target_skills = SkillNormalizer.parse_skills_input(job_preferred_skills)
        if not target_skills:
            return {
                "category": "preferred_skills",
                "is_applicable": False,
                "has_evidence": False,
                "score": None,
                "matched": [],
                "missing": [],
                "total_preferred": 0,
                "explanation": "No preferred skills specified in job requisition."
            }

        cand_skills = SkillNormalizer.parse_skills_input(candidate_skills)
        matched, missing = SkillNormalizer.match_skills(cand_skills, target_skills)

        score = round((len(matched) / len(target_skills)) * 100.0, 1)
        return {
            "category": "preferred_skills",
            "is_applicable": True,
            "has_evidence": True,
            "score": score,
            "matched": matched,
            "missing": missing,
            "total_preferred": len(target_skills),
            "explanation": f"Matched {len(matched)} of {len(target_skills)} preferred skills ({score}%)."
        }

    @classmethod
    def score_experience(
        cls,
        job_min_experience: Optional[float],
        job_max_experience: Optional[float],
        candidate_experience_years: Optional[float],
        has_evidence: bool = True
    ) -> Dict[str, Any]:
        """Evaluates relevant work experience alignment against job requirements."""
        req_min = float(job_min_experience) if job_min_experience is not None else 0.0

        if not has_evidence or candidate_experience_years is None:
            # If job is entry-level with 0 minimum experience requirement
            if req_min == 0.0:
                return {
                    "category": "experience",
                    "is_applicable": True,
                    "has_evidence": True,
                    "score": 100.0,
                    "candidate_years": 0.0,
                    "required_min_years": 0.0,
                    "explanation": "No prior experience required for this role; criteria met."
                }
            return {
                "category": "experience",
                "is_applicable": True,
                "has_evidence": False,
                "score": None,
                "candidate_years": None,
                "required_min_years": req_min,
                "explanation": "Candidate work experience history is not documented in resume."
            }

        cand_years = float(candidate_experience_years)
        if cand_years >= req_min:
            score = 100.0
            explanation = f"Candidate has {cand_years:.1f} years experience, meeting the required minimum of {req_min:.1f} years."
        else:
            if req_min > 0:
                score = round((cand_years / req_min) * 100.0, 1)
                explanation = f"Candidate has {cand_years:.1f} of {req_min:.1f} years required experience ({score}% alignment)."
            else:
                score = 100.0
                explanation = "Minimum experience requirement met."

        return {
            "category": "experience",
            "is_applicable": True,
            "has_evidence": True,
            "score": score,
            "candidate_years": cand_years,
            "required_min_years": req_min,
            "explanation": explanation
        }

    @classmethod
    def score_qualification(
        cls,
        job_min_qualification: Optional[str],
        candidate_degrees: Optional[List[str]],
        has_evidence: bool = True
    ) -> Dict[str, Any]:
        """Evaluates educational degree credentials against minimum stated requirements."""
        if not job_min_qualification or job_min_qualification.strip().lower() in ("", "none", "n/a"):
            return {
                "category": "qualification",
                "is_applicable": False,
                "has_evidence": False,
                "score": None,
                "candidate_highest": None,
                "required_qualification": None,
                "explanation": "No specific educational qualification required for this role."
            }

        req_str = job_min_qualification.strip()
        req_lower = req_str.lower()
        req_rank = QUALIFICATION_RANKS.get(req_lower)
        if req_rank is None:
            req_rank = 2  # default bachelor
            for k, r in QUALIFICATION_RANKS.items():
                if k in ("none", "high school"):
                    continue
                pattern = r"(?:^|\s|[.,\/\-])" + re.escape(k) + r"(?:$|\s|[.,\/\-])"
                if re.search(pattern, req_lower, re.IGNORECASE):
                    req_rank = r
                    break

        if not has_evidence or not candidate_degrees:
            return {
                "category": "qualification",
                "is_applicable": True,
                "has_evidence": False,
                "score": None,
                "candidate_highest": None,
                "required_qualification": req_str,
                "explanation": "Educational credential evidence not found in candidate resume."
            }

        # Calculate highest rank from candidate degrees
        cand_ranks = []
        for deg in candidate_degrees:
            clean_deg = deg.strip().lower() if isinstance(deg, str) else ""
            if clean_deg in QUALIFICATION_RANKS:
                cand_ranks.append((QUALIFICATION_RANKS[clean_deg], deg))
                continue

            matched_rank = 1
            for k, r in QUALIFICATION_RANKS.items():
                if k in ("none", "high school"):
                    continue
                pattern = r"(?:^|\s|[.,\/\-])" + re.escape(k) + r"(?:$|\s|[.,\/\-])"
                if re.search(pattern, clean_deg, re.IGNORECASE):
                    matched_rank = max(matched_rank, r)
            cand_ranks.append((matched_rank, deg))

        cand_ranks.sort(key=lambda x: x[0], reverse=True)
        highest_rank, highest_title = cand_ranks[0]

        if highest_rank >= req_rank:
            score = 100.0
            explanation = f"Candidate credential '{highest_title}' meets or exceeds required '{req_str}'."
        else:
            ratio = (highest_rank / req_rank) if req_rank > 0 else 1.0
            score = round(ratio * 100.0, 1)
            explanation = f"Candidate credential '{highest_title}' partially aligns with required '{req_str}' ({score}%)."

        return {
            "category": "qualification",
            "is_applicable": True,
            "has_evidence": True,
            "score": score,
            "candidate_highest": highest_title,
            "required_qualification": req_str,
            "explanation": explanation
        }

    @classmethod
    def calculate_overall_match(
        cls,
        job_data: Dict[str, Any],
        candidate_data: Dict[str, Any],
        weights: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Executes end-to-end transparent matching evaluation:
        - Evaluates required skills, preferred skills, experience, and qualification.
        - Applies dynamic weight redistribution across applicable categories with evidence.
        - Computes evidence coverage percentage.
        - Produces an audit-ready, explainable summary.
        """
        active_weights = validate_weights(weights or DEFAULT_WEIGHTS)

        # 1. Required Skills Score
        req_res = cls.score_required_skills(
            job_required_skills=job_data.get("required_skills"),
            candidate_skills=candidate_data.get("skills")
        )

        # 2. Preferred Skills Score
        pref_res = cls.score_preferred_skills(
            job_preferred_skills=job_data.get("preferred_skills"),
            candidate_skills=candidate_data.get("skills")
        )

        # 3. Experience Score
        exp_has_evidence = bool(
            candidate_data.get("has_experience_evidence") or
            candidate_data.get("total_experience_years") is not None or
            candidate_data.get("experience_years") is not None
        )
        cand_exp_years = candidate_data.get("total_experience_years")
        if cand_exp_years is None:
            cand_exp_years = candidate_data.get("experience_years")

        exp_res = cls.score_experience(
            job_min_experience=job_data.get("minimum_experience_years"),
            job_max_experience=job_data.get("maximum_experience_years"),
            candidate_experience_years=cand_exp_years,
            has_evidence=exp_has_evidence
        )

        # 4. Qualification Score
        edu_has_evidence = bool(
            candidate_data.get("has_education_evidence") or
            candidate_data.get("education_degrees") or
            candidate_data.get("education")
        )
        degrees = candidate_data.get("education_degrees")
        if not degrees and isinstance(candidate_data.get("education"), list):
            degrees = [e.get("degree") for e in candidate_data["education"] if isinstance(e, dict) and e.get("degree")]

        qual_res = cls.score_qualification(
            job_min_qualification=job_data.get("minimum_qualification"),
            candidate_degrees=degrees,
            has_evidence=edu_has_evidence
        )

        category_results = {
            "required_skills": req_res,
            "preferred_skills": pref_res,
            "experience": exp_res,
            "qualification": qual_res,
        }

        # Dynamic Normalization: calculate applicable and evidence weights
        applicable_weight_sum = sum(
            active_weights[cat] for cat, r in category_results.items() if r["is_applicable"]
        )

        evidence_weight_sum = sum(
            active_weights[cat] for cat, r in category_results.items()
            if r["is_applicable"] and r["has_evidence"] and r["score"] is not None
        )

        # Evidence Coverage percentage (0.0 to 100.0)
        if applicable_weight_sum > 0:
            evidence_coverage = round((evidence_weight_sum / applicable_weight_sum) * 100.0, 1)
        else:
            evidence_coverage = 100.0

        missing_evidence_warnings: List[str] = []
        for cat, r in category_results.items():
            if r["is_applicable"] and not r["has_evidence"]:
                missing_evidence_warnings.append(r["explanation"])

        # Overall Score Calculation
        if evidence_weight_sum > 0:
            weighted_points = sum(
                active_weights[cat] * r["score"]
                for cat, r in category_results.items()
                if r["is_applicable"] and r["has_evidence"] and r["score"] is not None
            )
            # Normalize to 0-100 range by dividing by sum of evaluated weights
            normalized_score = round(weighted_points / evidence_weight_sum, 1)
            # Clamp strictly within [0.0, 100.0]
            overall_score = max(0.0, min(100.0, normalized_score))
            status = "current"
        else:
            overall_score = None
            status = "unavailable"
            missing_evidence_warnings.append("Insufficient candidate resume evidence to compute a valid match score.")

        # Structured explanation text
        explanations = [
            f"Required Skills: {req_res['explanation']}",
            f"Preferred Skills: {pref_res['explanation']}",
            f"Work Experience: {exp_res['explanation']}",
            f"Education: {qual_res['explanation']}",
        ]
        if missing_evidence_warnings:
            explanations.append(f"Notice: Evidence coverage is {evidence_coverage}%.")

        summary_text = " | ".join(explanations)

        return {
            "overall_score": overall_score,
            "evidence_coverage": evidence_coverage,
            "status": status,
            "scoring_version": SCORING_VERSION,
            "scoring_weights_snapshot": active_weights,
            "category_scores": {
                cat: {
                    "score": r["score"],
                    "is_applicable": r["is_applicable"],
                    "has_evidence": r["has_evidence"],
                    "weight": active_weights[cat],
                    "explanation": r["explanation"]
                }
                for cat, r in category_results.items()
            },
            "matched_required_skills": req_res.get("matched", []),
            "missing_required_skills": req_res.get("missing", []),
            "matched_preferred_skills": pref_res.get("matched", []),
            "missing_preferred_skills": pref_res.get("missing", []),
            "experience_score": exp_res["score"],
            "experience_explanation": exp_res["explanation"],
            "qualification_score": qual_res["score"],
            "qualification_explanation": qual_res["explanation"],
            "missing_evidence": missing_evidence_warnings,
            "explanation_summary": summary_text,
        }
