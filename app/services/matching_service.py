"""
Matching Service for RecruitFlow AI (Phase 5).
Orchestrates candidate scoring evaluation, staleness hashing,
database persistence, and application synchronization.
"""
import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from app.core.extensions import db
from app.models.models import Job, Application, Resume, MatchResult, CandidateProfile
from app.services.matching_config import SCORING_VERSION, DEFAULT_WEIGHTS
from app.services.scoring_service import ScoringService


class MatchingService:
    """Orchestrates job-candidate evaluations, input hashing, and MatchResult persistence."""

    @classmethod
    def compute_input_hash(cls, job: Job, resume: Optional[Resume], profile: Optional[CandidateProfile] = None) -> str:
        """
        Generates a deterministic SHA-256 fingerprint of the inputs used for matching:
        - Job requirements (skills, experience, qualification)
        - Candidate data version (resume updated timestamp or profile state)
        - Scoring algorithm version
        """
        hasher = hashlib.sha256()

        # Job requirements fingerprint
        job_signature = f"{job.required_skills or ''}|{job.preferred_skills or ''}|{job.minimum_experience_years}|{job.minimum_qualification or ''}"
        hasher.update(job_signature.encode("utf-8"))

        # Candidate resume / profile fingerprint
        if resume:
            res_signature = f"resume:{resume.id}:{resume.updated_at.isoformat() if resume.updated_at else ''}:{resume.processing_status}"
            hasher.update(res_signature.encode("utf-8"))
        elif profile:
            prof_signature = f"profile:{profile.id}:{profile.updated_at.isoformat() if profile.updated_at else ''}:{profile.skills or ''}:{profile.years_of_experience}"
            hasher.update(prof_signature.encode("utf-8"))
        else:
            hasher.update(b"no_candidate_document_or_profile")

        # Version
        hasher.update(SCORING_VERSION.encode("utf-8"))
        return hasher.hexdigest()

    @classmethod
    def prepare_job_data(cls, job: Job) -> Dict[str, Any]:
        """Extracts structured matching inputs from Job entity."""
        return {
            "required_skills": job.required_skills,
            "preferred_skills": job.preferred_skills,
            "minimum_experience_years": job.minimum_experience_years,
            "maximum_experience_years": job.maximum_experience_years,
            "minimum_qualification": job.minimum_qualification,
        }

    @classmethod
    def prepare_candidate_data(cls, application: Application) -> Dict[str, Any]:
        """
        Extracts structured matching inputs from candidate's attached resume
        or candidate profile fallback.
        """
        resume = application.resume
        profile = application.candidate or application.candidate_user.candidate_profile

        skills: List[str] = []
        experience_years: Optional[float] = None
        has_experience_evidence = False
        degrees: List[str] = []
        has_education_evidence = False

        if resume and resume.processing_status == "processed":
            extracted = resume.get_extracted_data()
            skills = resume.skills_list
            experience_years = resume.parsed_experience_years
            has_experience_evidence = (experience_years is not None)

            # Degrees from extracted education
            edu_records = extracted.get("education", [])
            for e in edu_records:
                if isinstance(e, dict) and e.get("degree"):
                    degrees.append(e["degree"])
            has_education_evidence = (len(degrees) > 0)

        # Fallback to CandidateProfile if resume has gaps or is absent
        if not skills and profile and profile.skills:
            skills = [s.strip() for s in profile.skills.split(",") if s.strip()]

        if experience_years is None and profile and profile.years_of_experience:
            experience_years = profile.years_of_experience
            has_experience_evidence = True

        return {
            "skills": skills,
            "total_experience_years": experience_years,
            "has_experience_evidence": has_experience_evidence,
            "education_degrees": degrees,
            "has_education_evidence": has_education_evidence,
        }

    @classmethod
    def evaluate_application(
        cls,
        application: Application,
        weights: Optional[Dict[str, float]] = None,
        commit: bool = True
    ) -> MatchResult:
        """
        Scores a single application against its parent job requisition,
        persists the MatchResult, and updates Application.match_score.
        """
        job = application.job
        resume = application.resume
        profile = application.candidate or application.candidate_user.candidate_profile

        job_data = cls.prepare_job_data(job)
        candidate_data = cls.prepare_candidate_data(application)

        # Compute match evaluation
        eval_result = ScoringService.calculate_overall_match(job_data, candidate_data, weights)
        input_hash = cls.compute_input_hash(job, resume, profile)

        # Retrieve or initialize MatchResult
        match_result = MatchResult.query.filter_by(application_id=application.id).first()
        if not match_result:
            match_result = MatchResult(
                application_id=application.id,
                job_id=job.id,
                candidate_user_id=application.candidate_user_id,
                resume_id=resume.id if resume else None,
            )
            db.session.add(match_result)

        # Update MatchResult attributes
        match_result.overall_score = eval_result["overall_score"]
        match_result.evidence_coverage = eval_result["evidence_coverage"]
        match_result.status = eval_result["status"]
        match_result.scoring_version = eval_result["scoring_version"]
        match_result.scoring_weights_snapshot = json.dumps(eval_result["scoring_weights_snapshot"])
        match_result.category_scores = json.dumps(eval_result["category_scores"])
        match_result.matched_required_skills = json.dumps(eval_result["matched_required_skills"])
        match_result.missing_required_skills = json.dumps(eval_result["missing_required_skills"])
        match_result.matched_preferred_skills = json.dumps(eval_result["matched_preferred_skills"])
        match_result.missing_preferred_skills = json.dumps(eval_result["missing_preferred_skills"])
        match_result.experience_score = eval_result["experience_score"]
        match_result.experience_explanation = eval_result["experience_explanation"]
        match_result.qualification_score = eval_result["qualification_score"]
        match_result.qualification_explanation = eval_result["qualification_explanation"]
        match_result.missing_evidence = json.dumps(eval_result["missing_evidence"])
        match_result.explanation_summary = eval_result["explanation_summary"]
        match_result.input_hash = input_hash
        match_result.calculated_at = datetime.now(timezone.utc)
        match_result.resume_id = resume.id if resume else None

        # Synchronize back to Application entity
        application.match_score = eval_result["overall_score"] or 0.0
        application.match_breakdown = eval_result["explanation_summary"]

        if commit:
            db.session.commit()

        return match_result

    @classmethod
    def evaluate_job_applications(
        cls,
        job: Job,
        weights: Optional[Dict[str, float]] = None,
        force_recalculate: bool = False
    ) -> Dict[str, Any]:
        """
        Evaluates all submitted (non-withdrawn) applications for a job.
        Skips recalculation if input_hash has not changed unless force_recalculate is True.
        """
        applications = job.applications.filter(Application.status != "withdrawn").all()
        evaluated_count = 0
        skipped_count = 0
        unavailable_count = 0

        for app in applications:
            profile = app.candidate or (app.candidate_user.candidate_profile if app.candidate_user else None)
            current_hash = cls.compute_input_hash(job, app.resume, profile)
            existing_match = MatchResult.query.filter_by(application_id=app.id).first()

            if not force_recalculate and existing_match and existing_match.input_hash == current_hash and existing_match.status != "stale":
                skipped_count += 1
                if existing_match.overall_score is None:
                    unavailable_count += 1
                continue

            mr = cls.evaluate_application(app, weights=weights, commit=False)
            evaluated_count += 1
            if mr.overall_score is None:
                unavailable_count += 1

        db.session.commit()
        return {
            "total_applications": len(applications),
            "evaluated": evaluated_count,
            "skipped_up_to_date": skipped_count,
            "unavailable_evidence": unavailable_count,
        }

    @classmethod
    def check_staleness(cls, match_result: MatchResult) -> bool:
        """
        Verifies if an existing MatchResult is stale compared to current job/resume data.
        If stale, updates match_result.status to 'stale'.
        """
        job = match_result.job
        app = match_result.application
        resume = app.resume if app else None
        profile = (app.candidate or (app.candidate_user.candidate_profile if app.candidate_user else None)) if app else None

        current_hash = cls.compute_input_hash(job, resume, profile)
        if match_result.input_hash != current_hash:
            match_result.status = "stale"
            db.session.commit()
            return True
        return False
