"""
ATS Resume Analyzer Service for RecruitFlow AI (Phase 7).
Evaluates resume quality across 7 configurable categories totaling 100%,
detects formatting and parsing issues, and calculates separate job match scores
using the deterministic Phase 5 matching engine.
"""
import re
import json
import hashlib
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from app.core.extensions import db
from app.models.models import Resume, Job, CandidateProfile, ResumeAnalysis, utc_now
from app.services.scoring_service import ScoringService
from app.services.skill_normalizer import SkillNormalizer

logger = logging.getLogger(__name__)

# Configurable ATS category weights totaling 1.0 (100%)
DEFAULT_ATS_CATEGORY_WEIGHTS = {
    "section_completeness": 0.20,
    "formatting_parsing_quality": 0.20,
    "skills_clarity": 0.15,
    "experience_bullet_clarity": 0.15,
    "contact_document_structure": 0.10,
    "spelling_grammar_indicators": 0.10,
    "consistency_readability": 0.10,
}

ANALYZER_VERSION = "1.0.0"

# Common resume spelling errors / typos
COMMON_TYPOS = {
    "teh": "the",
    "expereince": "experience",
    "managment": "management",
    "pythonn": "python",
    "recieved": "received",
    "seperate": "separate",
    "achivement": "achievement",
    "responisible": "responsible",
    "colaberation": "collaboration",
    "comunication": "communication",
    "devlopment": "development",
    "implimentation": "implementation",
    "architectur": "architecture",
    "knowlege": "knowledge",
}

# Strong action verbs recommended in professional ATS resumes
STRONG_ACTION_VERBS = {
    "architected", "built", "engineered", "designed", "developed", "led",
    "implemented", "spearheaded", "optimized", "orchestrated", "automated",
    "delivered", "launched", "scaled", "created", "refactored", "analyzed",
    "deployed", "mentored", "maintained", "integrated", "streamlined"
}


class ATSAnalyzerService:
    """Core deterministic ATS resume quality analyzer and job comparison engine."""

    @classmethod
    def validate_category_weights(cls, weights: Optional[Dict[str, float]] = None) -> Dict[str, float]:
        """Validates that category weights are non-negative and sum to 1.0."""
        target_weights = weights or DEFAULT_ATS_CATEGORY_WEIGHTS
        total = sum(target_weights.values())
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"ATS category weights must sum to 1.0 (got {total:.4f}).")
        return target_weights

    @classmethod
    def compute_input_hash(cls, resume: Resume, job: Optional[Job] = None) -> str:
        """Computes deterministic SHA-256 hash of resume data and job requirements."""
        data_pieces = [
            ANALYZER_VERSION,
            str(resume.id),
            str(resume.raw_text or ""),
            str(resume.extracted_data or ""),
            str(resume.updated_at.isoformat() if resume.updated_at else "")
        ]
        if job:
            data_pieces.extend([
                str(job.id),
                str(job.title or ""),
                str(job.required_skills or ""),
                str(job.preferred_skills or ""),
                str(job.min_experience_years or ""),
                str(job.qualification or ""),
                str(job.updated_at.isoformat() if job.updated_at else "")
            ])
        combined = "||".join(data_pieces)
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    @classmethod
    def analyze_resume_quality(
        cls,
        resume: Resume,
        weights: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Evaluates resume quality / ATS readability across 7 configurable categories:
        1. Resume section completeness (20%)
        2. Formatting and parsing quality (20%)
        3. Skills section clarity (15%)
        4. Experience/project bullet clarity (15%)
        5. Contact and document structure (10%)
        6. Spelling and grammar indicators (10%)
        7. Consistency and readability (10%)
        """
        active_weights = cls.validate_category_weights(weights)
        raw_text = (resume.raw_text or "").strip()
        extracted_data = resume.get_extracted_data() or {}
        text_length = len(raw_text)

        category_scores: Dict[str, float] = {}
        positive_findings: List[str] = []
        detected_issues: List[Dict[str, Any]] = []
        parsing_warnings: List[str] = []
        recommendations: List[Dict[str, Any]] = []

        rec_counter = 1

        # Check for empty / nearly empty or unreadable file
        is_empty = text_length < 50
        is_scanned_pdf = False
        if resume.file_type == "pdf" and text_length < 100:
            is_scanned_pdf = True
            parsing_warnings.append(
                "Document appears to be an image-only or scanned PDF with little to no extractable text. OCR is not enabled."
            )
            detected_issues.append({
                "title": "Scanned or Image-Based Document",
                "evidence": f"Only {text_length} characters extracted from PDF.",
                "why_it_matters": "Standard ATS parsers cannot read raster images or scanned graphics without OCR.",
                "severity": "high",
                "category": "formatting_parsing_quality",
                "suggestion": "Export your resume directly as a selectable text PDF from Microsoft Word, Google Docs, or LaTeX."
            })
            recommendations.append({
                "id": f"rec_{rec_counter}",
                "priority": "high",
                "title": "Use Native Text-Based PDF",
                "category": "formatting",
                "description": "Convert your scanned document to a searchable, vector-based PDF or DOCX file.",
                "before_text": "Image-only PDF",
                "after_text": "Selectable, standard text PDF",
                "rationale": "ATS software requires machine-readable text layers to parse skills and work history."
            })
            rec_counter += 1

        # -------------------------------------------------------------
        # 1. Section Completeness (Weight: 20%)
        # -------------------------------------------------------------
        sections_found = []
        sections_missing = []
        text_lower = raw_text.lower()

        section_indicators = {
            "Skills": ["skills", "technical skills", "technologies", "core competencies"],
            "Experience": ["experience", "work experience", "employment history", "professional experience"],
            "Education": ["education", "academic background", "degrees", "qualifications"],
            "Projects": ["projects", "personal projects", "key projects", "portfolio"],
            "Summary": ["summary", "professional summary", "about me", "profile"]
        }

        for sec_name, keywords in section_indicators.items():
            if any(re.search(r"(?:^|\n)\s*" + re.escape(kw) + r"\s*[:\n]", text_lower) for kw in keywords) or (sec_name.lower() in extracted_data and extracted_data[sec_name.lower()]):
                sections_found.append(sec_name)
            else:
                sections_missing.append(sec_name)

        sec_score = (len(sections_found) / len(section_indicators)) * 100.0
        category_scores["section_completeness"] = round(sec_score, 1)

        if "Skills" in sections_found and "Experience" in sections_found and "Education" in sections_found:
            positive_findings.append(f"Identified primary standard resume sections: {', '.join(sections_found)}.")
        if "Experience" in sections_missing:
            detected_issues.append({
                "title": "Missing Work Experience Section Header",
                "evidence": "No clear 'Experience' or 'Work History' heading found.",
                "why_it_matters": "Recruiting software indexes chronological roles by matching standard section headers.",
                "severity": "high",
                "category": "section_completeness",
                "suggestion": "Add a prominent 'Work Experience' or 'Professional Experience' heading."
            })
            recommendations.append({
                "id": f"rec_{rec_counter}",
                "priority": "high",
                "title": "Add Clear Work Experience Heading",
                "category": "sections",
                "description": "Use standard header 'Professional Experience' before listing job roles.",
                "before_text": "Ambiguous role listings",
                "after_text": "## Professional Experience",
                "rationale": "Enables automated ATS chronological parsers to capture company names and dates accurately."
            })
            rec_counter += 1

        if "Skills" in sections_missing:
            detected_issues.append({
                "title": "Missing Explicit Skills Section",
                "evidence": "No dedicated 'Skills' heading detected.",
                "why_it_matters": "Applicant tracking systems look for a dedicated skills section to match keyword criteria.",
                "severity": "high",
                "category": "section_completeness",
                "suggestion": "Add a dedicated 'Technical Skills' section categorizing your core tools and languages."
            })

        # -------------------------------------------------------------
        # 2. Formatting and Parsing Quality (Weight: 20%)
        # -------------------------------------------------------------
        if is_empty:
            category_scores["formatting_parsing_quality"] = 0.0
            parsing_warnings.append("Extracted text is empty or corrupted.")
        else:
            format_score = 100.0
            # Length check
            if text_length < 200:
                format_score -= 50.0
            elif text_length < 500:
                format_score -= 20.0
            
            # Non-printable characters / corrupted encoding
            non_printable_count = len(re.findall(r"[^\x20-\x7E\r\n\t]", raw_text))
            if non_printable_count > 50:
                format_score -= 25.0
                parsing_warnings.append(f"Detected {non_printable_count} non-printable or unexpected unicode characters.")
                detected_issues.append({
                    "title": "Unusual Encoding or Hidden Symbols",
                    "evidence": f"Found {non_printable_count} non-standard characters.",
                    "why_it_matters": "Special icons, complex table glyphs, and custom bullet fonts often produce garbage text in ATS parsers.",
                    "severity": "medium",
                    "category": "formatting_parsing_quality",
                    "suggestion": "Replace graphical bullet symbols and multi-column tables with standard bullet characters ('•' or '-')."
                })

            category_scores["formatting_parsing_quality"] = max(0.0, round(format_score, 1))
            if format_score >= 80.0:
                positive_findings.append(f"Document parsed cleanly with {text_length} characters of extractable text.")

        # -------------------------------------------------------------
        # 3. Skills Section Clarity (Weight: 15%)
        # -------------------------------------------------------------
        extracted_skills = resume.skills_list or []
        skills_count = len(extracted_skills)
        if skills_count >= 10:
            skills_score = 100.0
            positive_findings.append(f"Detected {skills_count} clearly delineated technical skills.")
        elif skills_count >= 5:
            skills_score = 80.0
            positive_findings.append(f"Detected {skills_count} extracted skills.")
        elif skills_count >= 2:
            skills_score = 50.0
            detected_issues.append({
                "title": "Limited Extracted Skills",
                "evidence": f"Only {skills_count} skills extracted ({', '.join(extracted_skills)}).",
                "why_it_matters": "A sparse skills section limits keyword matching against target job requisitions.",
                "severity": "medium",
                "category": "skills_clarity",
                "suggestion": "Include languages, frameworks, databases, developer tools, and cloud platforms."
            })
        else:
            skills_score = 15.0 if skills_count == 1 else 0.0
            detected_issues.append({
                "title": "No Clear Technical Skills Detected",
                "evidence": "0 skills parsed from document.",
                "why_it_matters": "Resume screening engines heavily weight explicit skill tokens.",
                "severity": "high",
                "category": "skills_clarity",
                "suggestion": "Create a clear bulleted skills list separated by category (e.g., Languages, Frameworks, Tools)."
            })
            recommendations.append({
                "id": f"rec_{rec_counter}",
                "priority": "high",
                "title": "Group Skills into Categorized Bullets",
                "category": "skills",
                "description": "Structure your competencies cleanly (e.g. Languages: Python, Go; Frameworks: Flask, React).",
                "before_text": "Unstructured paragraph mentions of skills",
                "after_text": "Languages: Python, SQL | Frameworks: Flask, FastAPI | Tools: Docker, Git",
                "rationale": "ATS tokenizers easily isolate individual technologies when formatted in labeled categories."
            })
            rec_counter += 1

        category_scores["skills_clarity"] = round(skills_score, 1)

        # -------------------------------------------------------------
        # 4. Experience & Project Bullet Clarity (Weight: 15%)
        # -------------------------------------------------------------
        bullet_score = 100.0
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        bullet_lines = [line for line in lines if line.startswith(("-", "*", "•", "–")) or re.match(r"^\d+\.", line)]

        # Check action verbs
        words_in_text = set(re.findall(r"\b[a-zA-Z]+\b", text_lower))
        found_action_verbs = words_in_text.intersection(STRONG_ACTION_VERBS)

        if not bullet_lines and len(lines) > 5:
            bullet_score -= 35.0
            detected_issues.append({
                "title": "Lack of Standard Bullet Points",
                "evidence": "Experience appears to be written in dense paragraphs without distinct bullet markers.",
                "why_it_matters": "Hiring managers and ATS parsers skim bulleted achievement statements significantly faster than blocks of text.",
                "severity": "medium",
                "category": "experience_bullet_clarity",
                "suggestion": "Convert paragraph blocks into 3-5 concise bullet points per role."
            })
            recommendations.append({
                "id": f"rec_{rec_counter}",
                "priority": "medium",
                "title": "Structure Role Accomplishments as Bullet Points",
                "category": "experience",
                "description": "Begin each bullet with a past-tense action verb followed by task context and verified outcome.",
                "before_text": "I was responsible for developing web applications and fixing bugs on the team.",
                "after_text": "• Engineered responsive REST API endpoints and resolved high-priority backend defects.",
                "rationale": "Clear bullets allow recruiters and parsing engines to index specific accomplishments."
            })
            rec_counter += 1

        if len(found_action_verbs) < 3:
            bullet_score -= 25.0
            detected_issues.append({
                "title": "Few Strong Action Verbs Identified",
                "evidence": f"Found only {len(found_action_verbs)} recognized action verbs ({', '.join(found_action_verbs) or 'none'}).",
                "why_it_matters": "Passive phrases ('responsible for', 'assisted with') convey less impact than decisive action verbs.",
                "severity": "low",
                "category": "experience_bullet_clarity",
                "suggestion": "Lead bullets with active verbs such as 'Architected', 'Implemented', 'Optimized', or 'Launched'."
            })
        else:
            positive_findings.append(f"Strong action-driven phrasing detected with verbs: {', '.join(list(found_action_verbs)[:4])}.")

        category_scores["experience_bullet_clarity"] = max(0.0, round(bullet_score, 1))

        # -------------------------------------------------------------
        # 5. Contact and Document Structure (Weight: 10%)
        # -------------------------------------------------------------
        contact_score = 0.0
        has_email = bool(extracted_data.get("email") or re.search(r"[\w\.-]+@[\w\.-]+\.\w+", raw_text))
        has_phone = bool(extracted_data.get("phone") or re.search(r"\+?\d[\d\s\-\(\)]{8,}\d", raw_text))
        has_links = bool(extracted_data.get("links") or re.search(r"(?:github\.com|linkedin\.com)", raw_text, re.IGNORECASE))

        if has_email:
            contact_score += 50.0
            positive_findings.append("Contact email found and validated.")
        else:
            detected_issues.append({
                "title": "Missing Contact Email",
                "evidence": "No valid email address extracted.",
                "why_it_matters": "Recruiters cannot invite candidates for interviews if contact email is unparsed.",
                "severity": "high",
                "category": "contact_document_structure",
                "suggestion": "Place your professional email clearly in the top header of the resume."
            })

        if has_phone:
            contact_score += 25.0
        else:
            detected_issues.append({
                "title": "Missing Phone Number",
                "evidence": "No telephone number detected.",
                "why_it_matters": "Recruiters frequently conduct initial telephone screens.",
                "severity": "low",
                "category": "contact_document_structure",
                "suggestion": "Include a standard international or local phone number in the header."
            })

        if has_links:
            contact_score += 25.0
            positive_findings.append("Professional profile links (GitHub / LinkedIn) detected.")
        else:
            detected_issues.append({
                "title": "No LinkedIn or Portfolio URL Detected",
                "evidence": "No professional links extracted.",
                "why_it_matters": "Recruiters and hiring managers check online portfolios and LinkedIn credentials.",
                "severity": "low",
                "category": "contact_document_structure",
                "suggestion": "Add clickable links to your LinkedIn profile and GitHub or personal portfolio."
            })

        category_scores["contact_document_structure"] = round(contact_score, 1)

        # -------------------------------------------------------------
        # 6. Spelling and Grammar Indicators (Weight: 10%)
        # -------------------------------------------------------------
        typos_found = []
        for word in words_in_text:
            if word in COMMON_TYPOS:
                typos_found.append((word, COMMON_TYPOS[word]))

        spelling_score = 100.0 - (len(typos_found) * 20.0)
        # Check all caps shouting lines
        all_caps_lines = [line for line in lines if len(line) > 15 and line.isupper() and not any(sec in line for sec in ["EDUCATION", "EXPERIENCE", "SKILLS", "PROJECTS"])]
        if len(all_caps_lines) > 3:
            spelling_score -= 15.0

        if typos_found:
            sample_typos = ", ".join([f"'{bad}' -> '{good}'" for bad, good in typos_found[:3]])
            detected_issues.append({
                "title": "Potential Spelling or Typing Mistakes",
                "evidence": f"Found typos: {sample_typos}",
                "why_it_matters": "Spelling errors in technical resumes can trigger negative screening heuristics.",
                "severity": "medium",
                "category": "spelling_grammar_indicators",
                "suggestion": "Run a spell checker and correct flagged words."
            })
            for bad, good in typos_found[:2]:
                recommendations.append({
                    "id": f"rec_{rec_counter}",
                    "priority": "high",
                    "title": f"Correct Typo: '{bad}'",
                    "category": "spelling",
                    "description": f"Replace misspelled word with correct spelling '{good}'.",
                    "before_text": bad,
                    "after_text": good,
                    "rationale": "Clean orthography demonstrates attention to detail."
                })
                rec_counter += 1
        else:
            positive_findings.append("No common technical typos or orthographic errors detected.")

        category_scores["spelling_grammar_indicators"] = max(0.0, round(spelling_score, 1))

        # -------------------------------------------------------------
        # 7. Consistency and Readability (Weight: 10%)
        # -------------------------------------------------------------
        consistency_score = 100.0
        # Check date patterns
        date_patterns = re.findall(r"\b(?:20\d{2}|19\d{2})\b", raw_text)
        if len(date_patterns) >= 2:
            positive_findings.append(f"Chronological timeline detected with {len(date_patterns)} year milestones.")
        elif len(date_patterns) == 0 and "Experience" in sections_found:
            consistency_score -= 30.0
            detected_issues.append({
                "title": "No Clear Date Milestones in Work History",
                "evidence": "No calendar years (e.g., 2021, 2023) detected in experience text.",
                "why_it_matters": "Recruiters cannot verify years of total relevant experience without dates.",
                "severity": "medium",
                "category": "consistency_readability",
                "suggestion": "Add start and end dates (Month Year - Month Year) for each job or project."
            })

        # Average line length (readability)
        if lines:
            avg_line_len = sum(len(l) for l in lines) / len(lines)
            if avg_line_len > 180:
                consistency_score -= 20.0
                detected_issues.append({
                    "title": "Dense Line Formatting",
                    "evidence": f"Average line length is {int(avg_line_len)} characters.",
                    "why_it_matters": "Very wide, unformatted text blocks are difficult for both human reviewers and parsers.",
                    "severity": "low",
                    "category": "consistency_readability",
                    "suggestion": "Break long descriptions into concise 1-2 line bullet points."
                })

        category_scores["consistency_readability"] = max(0.0, round(consistency_score, 1))

        # -------------------------------------------------------------
        # Compute Overall Resume Quality Score
        # -------------------------------------------------------------
        if is_empty:
            overall_quality_score = 0.0
            status = "incomplete"
        else:
            overall_quality_score = sum(
                category_scores.get(cat, 0.0) * weight
                for cat, weight in active_weights.items()
            )
            overall_quality_score = round(overall_quality_score, 1)
            status = "completed"

        # General recommendation if recommendations list is short
        if not recommendations:
            if detected_issues:
                for issue in detected_issues[:3]:
                    recommendations.append({
                        "id": f"rec_{rec_counter}",
                        "priority": issue["severity"],
                        "title": issue["title"],
                        "category": issue["category"],
                        "description": issue["suggestion"],
                        "before_text": issue["evidence"],
                        "after_text": issue["suggestion"],
                        "rationale": issue["why_it_matters"]
                    })
                    rec_counter += 1
            else:
                recommendations.append({
                    "id": f"rec_{rec_counter}",
                    "priority": "low",
                    "title": "Review Role-Specific Customization",
                    "category": "presentation",
                    "description": "Tailor top bullet points to echo specific keywords from each target job description.",
                    "before_text": "Generic technical experience",
                    "after_text": "Targeted technical achievements reflecting desired role competencies",
                    "rationale": "High-scoring resumes maintain competitive edge when aligned with individual requisitions."
                })
                rec_counter += 1
                recommendations.append({
                    "id": f"rec_{rec_counter}",
                    "priority": "low",
                    "title": "Quantify Verified Project Outcomes",
                    "category": "experience",
                    "description": "Where you have verified metrics (e.g. latency reduced, users served), add them to highlight engineering impact.",
                    "before_text": "Implemented scalable backend features",
                    "after_text": "Architected backend service serving measured volume with high availability",
                    "rationale": "Hiring committees prioritize demonstrated engineering impact."
                })
                rec_counter += 1

        return {
            "resume_quality_score": overall_quality_score,
            "status": status,
            "category_scores": category_scores,
            "category_weights": active_weights,
            "positive_findings": positive_findings,
            "detected_issues": detected_issues,
            "parsing_warnings": parsing_warnings,
            "recommendations": recommendations,
            "analyzer_version": ANALYZER_VERSION
        }

    @classmethod
    def evaluate_job_match(
        cls,
        resume: Resume,
        job: Job,
        candidate_profile: Optional[CandidateProfile] = None
    ) -> Dict[str, Any]:
        """
        Calculates job-specific match evaluation by reusing Phase 5 ScoringService.
        Keeps job match evaluation strictly isolated from resume quality score.
        """
        extracted_data = resume.get_extracted_data() or {}

        # Synthesize candidate data bundle for ScoringService
        candidate_skills = resume.skills_list
        if candidate_profile and candidate_profile.skills:
            profile_skills = [s.strip() for s in candidate_profile.skills.split(",") if s.strip()]
            candidate_skills = list(set(candidate_skills + profile_skills))

        # Determine experience years
        cand_exp = resume.parsed_experience_years
        if cand_exp is None and candidate_profile:
            cand_exp = candidate_profile.total_experience_years

        # Extract qualification text
        cand_qual = extracted_data.get("education") or extracted_data.get("highest_education") or ""
        if isinstance(cand_qual, list):
            cand_qual = " ".join([str(item) for item in cand_qual])

        candidate_data = {
            "skills": candidate_skills,
            "experience_years": cand_exp,
            "qualification": cand_qual,
            "raw_text": resume.raw_text or ""
        }

        job_data = {
            "required_skills": job.required_skills,
            "preferred_skills": job.preferred_skills,
            "min_experience_years": job.min_experience_years,
            "qualification": job.qualification
        }

        # Calculate using Phase 5 source of truth
        match_result = ScoringService.calculate_overall_match(
            job_data=job_data,
            candidate_data=candidate_data
        )

        return match_result

    @classmethod
    def run_ats_analysis(
        cls,
        resume: Resume,
        job: Optional[Job] = None,
        candidate_user=None,
        force_refresh: bool = False
    ) -> ResumeAnalysis:
        """
        Executes complete ATS quality analysis and optional job matching.
        Persists results to ResumeAnalysis with input_hash staleness tracking.
        """
        current_hash = cls.compute_input_hash(resume, job)

        # Check existing analysis if not forced
        if not force_refresh:
            query = ResumeAnalysis.query.filter_by(
                resume_id=resume.id,
                job_id=job.id if job else None
            )
            existing = query.first()
            if existing and existing.input_hash == current_hash and existing.status != "stale":
                return existing

        # Evaluate Resume Quality (Score A)
        quality_res = cls.analyze_resume_quality(resume)

        # Evaluate Job-Specific Match (Score B, when job provided)
        job_match_score = None
        cand_profile = resume.candidate_profile or (candidate_user.candidate_profile if candidate_user else None)
        if job:
            match_res = cls.evaluate_job_match(resume, job, candidate_profile=cand_profile)
            job_match_score = match_res.get("overall_score")

        # Find or create record
        analysis = ResumeAnalysis.query.filter_by(
            resume_id=resume.id,
            job_id=job.id if job else None
        ).first()

        candidate_profile_id = cand_profile.id if cand_profile else None
        candidate_user_id = resume.candidate_user_id

        if not analysis:
            analysis = ResumeAnalysis(
                resume_id=resume.id,
                candidate_id=candidate_profile_id,
                candidate_user_id=candidate_user_id,
                job_id=job.id if job else None
            )
            db.session.add(analysis)

        analysis.resume_quality_score = quality_res["resume_quality_score"]
        analysis.job_match_score = job_match_score
        analysis.status = quality_res["status"]
        analysis.analyzer_version = ANALYZER_VERSION
        analysis.category_scores = json.dumps(quality_res["category_scores"])
        analysis.category_weights = json.dumps(quality_res["category_weights"])
        analysis.positive_findings = json.dumps(quality_res["positive_findings"])
        analysis.detected_issues = json.dumps(quality_res["detected_issues"])
        analysis.recommendations = json.dumps(quality_res["recommendations"])
        analysis.parsing_warnings = json.dumps(quality_res["parsing_warnings"])
        analysis.input_hash = current_hash
        analysis.updated_at = utc_now()

        # Initialize empty checklist state if not set
        if not analysis.checklist_state:
            analysis.checklist_state = json.dumps({})

        db.session.commit()
        return analysis

    @classmethod
    def is_analysis_stale(cls, analysis: ResumeAnalysis, resume: Resume, job: Optional[Job] = None) -> bool:
        """Determines if the persisted analysis is outdated due to resume or job changes."""
        if not analysis or not analysis.input_hash:
            return True
        current_hash = cls.compute_input_hash(resume, job)
        return analysis.input_hash != current_hash
