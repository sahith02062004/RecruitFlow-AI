"""
Shortlisting Gap & Rejection Explanation Service for RecruitFlow AI (Phase 7).
Implements:
- Candidate-facing "Why Was My Resume Not Shortlisted?" system
- Clear separation between official recruiter-recorded reasons vs. objective requirement gaps
- Honest fallback disclaimer when no recruiter reason is recorded:
  "We cannot determine the recruiter's actual reason from the resume alone. The following findings identify possible gaps between your resume and this job's requirements."
- Never fabricates recruiter decisions or internal discussions
- Structured rejection reasons for recruiters with explicit candidate visibility controls
"""
import logging
from typing import Dict, Any, List, Optional
from app.models.models import Application, Job, Resume, CandidateProfile
from app.services.skill_normalizer import SkillNormalizer

logger = logging.getLogger(__name__)

# Structured recruiter rejection reason taxonomy
STRUCTURED_REJECTION_REASONS = {
    "skill_gap": "Required skill not demonstrated in application",
    "experience_gap": "Relevant experience requirement not met",
    "qualification_gap": "Qualification requirement not met",
    "role_changed": "Role requirements or hiring priorities changed",
    "position_filled": "Position has been filled by another candidate",
    "other": "Other recruitment consideration"
}


class ShortlistingGapService:
    """Explains objective candidate gaps and published recruiter feedback."""

    @classmethod
    def get_gap_explanation(
        cls,
        application: Application,
        candidate_user
    ) -> Dict[str, Any]:
        """
        Builds transparent, evidence-based gap explanation for candidate view.
        Ensures strict privacy: internal recruiter notes are never shown to candidates.
        """
        job = application.job
        resume = application.resume or (candidate_user.resumes.first() if hasattr(candidate_user, "resumes") else None)
        raw_text = (resume.raw_text or "").lower() if resume else ""
        extracted_data = resume.get_extracted_data() if resume else {}

        # 1. Determine Official Recruiter Feedback (if published)
        has_official_reason = bool(application.rejection_feedback_published and application.rejection_reason_code)
        official_reason = None
        if has_official_reason:
            official_reason = {
                "reason_code": application.rejection_reason_code,
                "reason_title": STRUCTURED_REJECTION_REASONS.get(application.rejection_reason_code, "Application Review Decision"),
                "recruiter_feedback": application.rejection_reason_text or "No additional feedback provided."
            }

        # 2. Objective Requirement Gap Findings
        gap_findings: List[Dict[str, Any]] = []

        # A. Required Skills Gaps
        if job.required_skills:
            job_req_skills = SkillNormalizer.parse_skills_input(job.required_skills)
            cand_skills = SkillNormalizer.parse_skills_input(resume.skills_list if resume else [])
            matched, missing = SkillNormalizer.match_skills(cand_skills, job_req_skills)

            if missing:
                gap_findings.append({
                    "title": f"Missing Required Skills ({len(missing)} of {len(job_req_skills)})",
                    "category": "skills",
                    "severity": "high",
                    "confidence": "high",
                    "evidence": f"Requisition requires: [{', '.join(missing)}]. Not detected in resume.",
                    "why_it_matters": f"This position explicitly specifies {', '.join(missing[:3])} as mandatory core competencies.",
                    "suggested_action": "If you possess verified project experience with these tools, explicitly add them with context in your skills section."
                })

        # B. Preferred Skills Gaps
        if job.preferred_skills:
            job_pref_skills = SkillNormalizer.parse_skills_input(job.preferred_skills)
            cand_skills = SkillNormalizer.parse_skills_input(resume.skills_list if resume else [])
            _, missing_pref = SkillNormalizer.match_skills(cand_skills, job_pref_skills)

            if missing_pref:
                gap_findings.append({
                    "title": f"Preferred / Bonus Skills Not Found ({len(missing_pref)} skills)",
                    "category": "skills",
                    "severity": "medium",
                    "confidence": "medium",
                    "evidence": f"Requisition preferred: [{', '.join(missing_pref)}].",
                    "why_it_matters": "While not strictly required, preferred skills provide competitive advantage when ranking applicants.",
                    "suggested_action": "Highlight any adjacent or introductory exposure you have to these preferred technologies."
                })

        # C. Experience Duration Alignment
        if job.min_experience_years and job.min_experience_years > 0:
            cand_exp = resume.parsed_experience_years if resume else 0.0
            if cand_exp is None:
                cand_exp = 0.0

            if cand_exp < job.min_experience_years:
                gap_findings.append({
                    "title": f"Experience Stated Below Requirement ({cand_exp:.1f} vs {job.min_experience_years} yrs)",
                    "category": "experience",
                    "severity": "high",
                    "confidence": "high",
                    "evidence": f"Job specifies minimum {job.min_experience_years} years; resume extracted {cand_exp:.1f} years.",
                    "why_it_matters": "Seniority benchmarks are often initial filters used by hiring committees.",
                    "suggested_action": "Ensure all relevant internships, contract roles, or freelance work with accurate dates are documented."
                })

        # D. Educational Qualification Alignment
        if job.qualification:
            cand_edu = extracted_data.get("education") or extracted_data.get("highest_education") or ""
            if isinstance(cand_edu, list):
                cand_edu = " ".join([str(e) for e in cand_edu])
            if not cand_edu:
                gap_findings.append({
                    "title": "Educational Background Could Not Be Verified",
                    "category": "education",
                    "severity": "medium",
                    "confidence": "medium",
                    "evidence": f"Job seeks '{job.qualification}'. No degree or educational credential extracted from resume.",
                    "why_it_matters": "Credentials cannot be evaluated when degree names or institutions are omitted or unparsed.",
                    "suggested_action": "Add an explicit 'Education' section listing your degree, major, university, and graduation year."
                })

        # E. Parsing & Quality Warning Gaps
        if resume and resume.file_type == "pdf" and len(resume.raw_text or "") < 100:
            gap_findings.append({
                "title": "Resume Text Parsing Failure (Scanned Image PDF)",
                "category": "parsing",
                "severity": "high",
                "confidence": "high",
                "evidence": f"Only {len(resume.raw_text or '')} characters were extracted from your uploaded document.",
                "why_it_matters": "Automated ATS filters could not read the text of your resume.",
                "suggested_action": "Upload a clean PDF exported directly from Word, Google Docs, or LaTeX with selectable text."
            })

        # Honest disclaimer text when no official reason is recorded
        disclaimer = None
        if not has_official_reason:
            disclaimer = (
                "We cannot determine the recruiter's actual reason from the resume alone. "
                "The following findings identify possible gaps between your resume and this job's requirements."
            )

        return {
            "application_id": application.id,
            "job_id": job.id,
            "job_title": job.title,
            "application_status": application.status,
            "has_official_reason": has_official_reason,
            "official_reason": official_reason,
            "disclaimer": disclaimer,
            "gap_findings": gap_findings,
            "total_gaps": len(gap_findings)
        }
