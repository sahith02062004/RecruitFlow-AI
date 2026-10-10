"""
Resume Processing Service for RecruitFlow AI (Phase 4).
Orchestrates secure validation, file persistence, PyMuPDF/python-docx parsing,
deterministic information extraction, database synchronization,
and optional candidate profile enrichment.
"""
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from flask import current_app
from app.core.extensions import db
from app.models.models import Resume, CandidateProfile, User
from app.services.resume_storage_service import ResumeStorageService, ResumeStorageError
from app.services.resume_parser_service import ResumeParserService, ResumeParserError
from app.services.resume_extraction_service import ResumeExtractionService


class ResumeProcessingService:
    """End-to-end processing pipeline for candidate resumes."""

    @classmethod
    def process_upload(
        cls,
        file_storage,
        user: User,
        sync_profile: bool = False
    ) -> Dict[str, Any]:
        """
        Executes complete ingestion pipeline:
        1. Validates and saves file to safe disk storage.
        2. Creates database Resume record with 'processing' status.
        3. Parses document to raw text.
        4. Extracts candidate info, skills, education, and experience.
        5. Persists extracted payload to Resume model with 'processed' status.
        6. Optionally enriches CandidateProfile fields.
        """
        # Step 1: Storage & Validation
        try:
            file_meta = ResumeStorageService.save_file(file_storage)
        except ResumeStorageError as e:
            return {
                "success": False,
                "error": str(e),
                "error_code": e.error_code,
                "resume": None,
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to store file: {str(e)}",
                "error_code": "storage_exception",
                "resume": None,
            }

        candidate_profile = getattr(user, "candidate_profile", None)
        candidate_profile_id = candidate_profile.id if candidate_profile else None

        # Step 2: Initialize Database Record
        resume = Resume(
            candidate_user_id=user.id,
            candidate_id=candidate_profile_id,
            storage_key=file_meta["storage_key"],
            filename=file_meta["filename"],
            original_filename=file_meta["original_filename"],
            file_path=file_meta["file_path"],
            file_type=file_meta["file_type"],
            file_extension=file_meta["file_extension"],
            file_size=file_meta["file_size_bytes"],
            file_size_bytes=file_meta["file_size_bytes"],
            mime_type=file_meta["mime_type"],
            processing_status="processing",
            parsing_status="processing",
        )
        db.session.add(resume)
        db.session.commit()

        # Step 3: Parse Document
        try:
            parse_result = ResumeParserService.parse_document(
                file_meta["file_path"],
                file_type=file_meta["file_type"]
            )
            raw_text = parse_result.get("raw_text", "")
            parser_warnings = parse_result.get("warnings", [])
        except (ResumeParserError, Exception) as e:
            error_msg = str(e)
            error_code = getattr(e, "error_code", "parsing_error")
            resume.processing_status = "failed"
            resume.parsing_status = "failed"
            resume.processing_error_code = error_code
            resume.set_extracted_data({
                "error": error_msg,
                "error_code": error_code,
                "warnings": [error_msg]
            })
            db.session.commit()
            return {
                "success": False,
                "error": f"Failed to parse document text: {error_msg}",
                "error_code": error_code,
                "resume": resume,
            }

        # Step 4: Extract Information
        try:
            extracted_payload = ResumeExtractionService.extract_all(
                raw_text=raw_text,
                fallback_name=user.full_name
            )
            # Merge parser warnings with extraction warnings
            all_warnings = list(set(parser_warnings + extracted_payload.get("warnings", [])))
            extracted_payload["warnings"] = all_warnings
            extracted_payload["page_count"] = parse_result.get("page_count", 1)
            extracted_payload["char_count"] = parse_result.get("char_count", len(raw_text))
            extracted_payload["word_count"] = parse_result.get("word_count", len(raw_text.split()))

            # Step 5: Update Resume Record
            resume.raw_text = raw_text
            resume.processing_status = "processed"
            resume.parsing_status = "completed"
            resume.processed_at = datetime.now(timezone.utc)
            resume.set_extracted_data(extracted_payload)
            db.session.commit()

        except Exception as e:
            resume.processing_status = "failed"
            resume.parsing_status = "failed"
            resume.processing_error_code = "extraction_error"
            db.session.commit()
            return {
                "success": False,
                "error": f"Information extraction failed: {str(e)}",
                "error_code": "extraction_error",
                "resume": resume,
            }

        # Step 6: Profile Enrichment (if requested and user has profile)
        if sync_profile and candidate_profile:
            cls.sync_extracted_data_to_profile(candidate_profile, extracted_payload)

        return {
            "success": True,
            "resume": resume,
            "extracted_data": extracted_payload,
            "warnings": all_warnings,
        }

    @classmethod
    def sync_extracted_data_to_profile(cls, profile: CandidateProfile, extracted: Dict[str, Any]) -> None:
        """
        Updates CandidateProfile fields with extracted information
        while preserving non-empty existing data unless blank.
        """
        if not profile or not extracted:
            return

        # Phone
        if extracted.get("phone") and not profile.phone:
            profile.phone = extracted["phone"]

        # Links
        links = extracted.get("links", {})
        if links.get("linkedin") and not profile.linkedin_url:
            profile.linkedin_url = links["linkedin"]
        if links.get("github") and not profile.github_url:
            profile.github_url = links["github"]
        if links.get("portfolio") and not profile.portfolio_url:
            profile.portfolio_url = links["portfolio"]

        # Skills
        extracted_skills = extracted.get("skills", [])
        if extracted_skills:
            existing_skills = [s.strip() for s in (profile.skills or "").split(",") if s.strip()]
            combined = sorted(list(set(existing_skills + extracted_skills)))
            profile.skills = ", ".join(combined)

        # Experience years
        exp_years = extracted.get("total_experience_years")
        if exp_years and (not profile.years_of_experience or profile.years_of_experience == 0.0):
            profile.years_of_experience = float(exp_years)

        # Summary
        if extracted.get("summary") and not profile.professional_summary:
            profile.professional_summary = extracted["summary"]

        db.session.commit()

    @classmethod
    def update_resume_extraction(
        cls,
        resume: Resume,
        updated_data: Dict[str, Any]
    ) -> Resume:
        """
        Allows candidate to correct or update parsed skills, experience, contact info,
        and synchronizes changes to the database.
        """
        current_data = resume.get_extracted_data()
        current_data.update(updated_data)
        current_data["updated_at"] = datetime.now(timezone.utc).isoformat()

        resume.set_extracted_data(current_data)
        resume.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        return resume
