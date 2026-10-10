"""
Candidate Ranking Service for RecruitFlow AI (Phase 5).
Sorts applicants deterministically with transparent tie-breaking rules,
staleness checks, pagination, and multi-tenant organization scoping.
"""
from typing import List, Dict, Any, Optional
from sqlalchemy import desc, asc, nullslast
from app.core.extensions import db
from app.models.models import Job, Application, MatchResult, User
from app.services.matching_service import MatchingService


class RankingService:
    """Provides deterministic ranking and filtering for job applicants."""

    @classmethod
    def get_ranked_candidates(
        cls,
        job: Job,
        status_filter: Optional[str] = None,
        search_query: Optional[str] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Dict[str, Any]:
        """
        Retrieves and ranks applicants for an authorized job.
        Tie-breaking policy:
        1. Overall score DESC (highest match first).
        2. Evidence coverage DESC (more complete evidence preferred over equal partial score).
        3. Application submission time ASC (earlier applicant breaks tie).
        4. Application ID ASC (stable unique identifier).
        Applications with unavailable scores (null overall_score) are placed at the end.
        """
        # Base query joined with User and MatchResult
        query = (
            db.session.query(Application, MatchResult)
            .outerjoin(MatchResult, Application.id == MatchResult.application_id)
            .join(User, Application.candidate_user_id == User.id)
            .filter(
                Application.job_id == job.id,
                Application.status != "withdrawn"
            )
        )

        # Optional pipeline status filter
        if status_filter and status_filter != "all":
            query = query.filter(Application.status == status_filter)

        # Optional name/email search
        if search_query:
            term = f"%{search_query.strip()}%"
            query = query.filter(
                db.or_(
                    User.full_name.ilike(term),
                    User.email.ilike(term)
                )
            )

        # Deterministic sorting query
        # In SQLite/MySQL: we sort by whether score is not null, then score desc, coverage desc, applied_at asc, id asc
        # CASE statement puts scored applicants first, unavailable last
        score_sort_priority = db.case(
            (MatchResult.overall_score.isnot(None), 1),
            else_=0
        )

        query = query.order_by(
            desc(score_sort_priority),
            desc(MatchResult.overall_score),
            desc(MatchResult.evidence_coverage),
            asc(Application.applied_at),
            asc(Application.id)
        )

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        ranked_items = []
        rank_counter = (page - 1) * per_page + 1

        for app, match in pagination.items:
            # Check staleness if match exists
            is_stale = False
            if match:
                is_stale = MatchingService.check_staleness(match)

            has_valid_score = (match is not None and match.overall_score is not None)
            assigned_rank = rank_counter if has_valid_score else None
            if has_valid_score:
                rank_counter += 1

            ranked_items.append({
                "rank": assigned_rank,
                "application": app,
                "match_result": match,
                "candidate_user": app.candidate_user,
                "overall_score": match.overall_score if match else None,
                "evidence_coverage": match.evidence_coverage if match else 0.0,
                "status": "stale" if is_stale else (match.status if match else "unscored"),
                "is_stale": is_stale,
                "matched_required": match.get_matched_required_skills() if match else [],
                "missing_required": match.get_missing_required_skills() if match else [],
                "matched_preferred": match.get_matched_preferred_skills() if match else [],
                "missing_preferred": match.get_missing_preferred_skills() if match else [],
                "experience_explanation": match.experience_explanation if match else "Not scored",
                "qualification_explanation": match.qualification_explanation if match else "Not scored",
                "calculated_at": match.calculated_at if match else None,
            })

        return {
            "job": job,
            "items": ranked_items,
            "pagination": pagination,
            "total_count": pagination.total,
            "scored_count": sum(1 for it in ranked_items if it["overall_score"] is not None),
            "status_filter": status_filter or "all",
            "search_query": search_query or "",
        }
