"""
Core Database Models for RecruitFlow AI - Phase 2.
Includes User, Organization, OrganizationMembership, CandidateProfile, RecruiterProfile,
PasswordResetToken, and existing Phase 1 entities (Job, Resume, Application, Interview).
Compatible with MySQL 8 (InnoDB utf8mb4) and SQLite.
"""
from datetime import datetime, timezone
import secrets
import hashlib
import json
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app.core.extensions import db, login_manager


def utc_now():
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    """
    Unified user authentication model.
    Enforces normalized email, secure hashing, global roles, and activation status.
    """
    __tablename__ = "users"

    VALID_ROLES = {"candidate", "recruiter", "organization_admin", "platform_admin"}

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(128), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(32), nullable=False, default="candidate", index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    recruiter_profile = db.relationship("RecruiterProfile", backref="user", uselist=False, cascade="all, delete-orphan")
    candidate_profile = db.relationship("CandidateProfile", backref="user", uselist=False, cascade="all, delete-orphan")
    memberships = db.relationship("OrganizationMembership", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    reset_tokens = db.relationship("PasswordResetToken", backref="user", lazy="dynamic", cascade="all, delete-orphan")

    def set_password(self, password):
        """Hashes password using werkzeug scrypt/pbkdf2."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verifies plaintext candidate password against stored hash."""
        return check_password_hash(self.password_hash, password)

    @property
    def first_name(self):
        parts = self.full_name.strip().split(" ")
        return parts[0] if parts else self.full_name

    @property
    def last_name(self):
        parts = self.full_name.strip().split(" ")
        return " ".join(parts[1:]) if len(parts) > 1 else ""

    def to_dict(self):
        """Safe dictionary representation omitting password_hash."""
        return {
            "id": self.id,
            "full_name": self.full_name,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active,
            "email_verified": self.email_verified,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@login_manager.user_loader
def load_user(user_id):
    """Flask-Login user loader."""
    try:
        return db.session.get(User, int(user_id))
    except Exception:
        return None


class Organization(db.Model):
    """
    Organization entity for multi-tenant recruiter isolation.
    """
    __tablename__ = "organizations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    slug = db.Column(db.String(128), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)  # Clearly labels unverified state
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    memberships = db.relationship("OrganizationMembership", backref="organization", lazy="dynamic", cascade="all, delete-orphan")
    jobs = db.relationship("Job", backref="organization", lazy="dynamic", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class OrganizationMembership(db.Model):
    """
    Links users to organizations with explicit roles (admin, recruiter, reviewer).
    """
    __tablename__ = "organization_memberships"
    __table_args__ = (
        db.UniqueConstraint("organization_id", "user_id", name="uq_org_user_membership"),
    )

    VALID_MEMBERSHIP_ROLES = {"admin", "recruiter", "reviewer"}

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    membership_role = db.Column(db.String(32), default="recruiter", nullable=False)  # admin, recruiter, reviewer
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)


class CandidateProfile(db.Model):
    """Profile data for job candidates."""
    __tablename__ = "candidate_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    headline = db.Column(db.String(255), nullable=True)
    professional_summary = db.Column(db.Text, nullable=True)
    phone = db.Column(db.String(32), nullable=True)
    location = db.Column(db.String(128), nullable=True)
    years_of_experience = db.Column(db.Float, default=0.0)
    skills = db.Column(db.Text, nullable=True)
    portfolio_url = db.Column(db.String(255), nullable=True)
    linkedin_url = db.Column(db.String(255), nullable=True)
    github_url = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Associated resumes and applications
    resumes = db.relationship("Resume", backref="candidate", lazy="dynamic", cascade="all, delete-orphan")
    applications = db.relationship("Application", backref="candidate", lazy="dynamic", cascade="all, delete-orphan")


class RecruiterProfile(db.Model):
    """Personal profile details for recruiters and hiring managers."""
    __tablename__ = "recruiter_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    job_title = db.Column(db.String(128), nullable=True)
    department = db.Column(db.String(64), nullable=True)
    phone = db.Column(db.String(32), nullable=True)
    company_name = db.Column(db.String(128), nullable=True, default="RecruitFlow Enterprise")
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Jobs authored by this recruiter
    jobs = db.relationship("Job", backref="recruiter", lazy="dynamic", cascade="all, delete-orphan")


class PasswordResetToken(db.Model):
    """
    Cryptographically secure, single-use, time-limited password reset tokens.
    Stores only SHA-256 hashed token representation.
    """
    __tablename__ = "password_reset_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = db.Column(db.String(64), nullable=False, index=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    used_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    @classmethod
    def create_token(cls, user_id, expires_in_seconds=3600):
        """Generates raw token for delivery and stores secure hash in DB."""
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        expires_at = datetime.fromtimestamp(datetime.now(timezone.utc).timestamp() + expires_in_seconds, tz=timezone.utc)
        
        db_token = cls(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at
        )
        db.session.add(db_token)
        return raw_token, db_token

    @classmethod
    def verify_token(cls, raw_token):
        """Verifies raw token against active, non-expired, unused token hashes."""
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        db_token = cls.query.filter_by(token_hash=token_hash).first()
        if not db_token:
            return None

        # Check if already used
        if db_token.used_at is not None:
            return None

        # Check expiration with timezone awareness
        now = datetime.now(timezone.utc)
        # Normalize db_token.expires_at to UTC if naive
        expires_at = db_token.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if now > expires_at:
            return None

        return db_token


# =========================================================================
# Domain Models (Preserved from Phase 1, extended with organization linkage)
# =========================================================================

class Job(db.Model):
    """
    Job requisitions and postings created by recruiters for an organization.
    Supports lifecycle: draft, published (active), closed, archived.
    """
    __tablename__ = "jobs"

    VALID_STATUSES = {"draft", "published", "active", "closed", "archived"}
    VALID_WORKPLACE_TYPES = {"onsite", "hybrid", "remote"}
    VALID_EMPLOYMENT_TYPES = {"full-time", "part-time", "contract", "internship"}

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    recruiter_id = db.Column(db.Integer, db.ForeignKey("recruiter_profiles.id", ondelete="CASCADE"), nullable=True)

    title = db.Column(db.String(128), nullable=False, index=True)
    department = db.Column(db.String(64), nullable=True)
    location = db.Column(db.String(128), nullable=True)
    workplace_type = db.Column(db.String(32), default="hybrid", nullable=False)
    employment_type = db.Column(db.String(32), default="full-time", nullable=False)
    status = db.Column(db.String(32), default="draft", index=True, nullable=False)

    description = db.Column(db.Text, nullable=False)
    responsibilities = db.Column(db.Text, nullable=True)
    required_skills = db.Column(db.Text, nullable=False)  # Comma-separated or line-separated skills
    preferred_skills = db.Column(db.Text, nullable=True)

    minimum_experience_years = db.Column(db.Float, default=0.0, nullable=False)
    maximum_experience_years = db.Column(db.Float, nullable=True)
    minimum_qualification = db.Column(db.String(128), nullable=True)

    salary_min = db.Column(db.Numeric(12, 2), nullable=True)
    salary_max = db.Column(db.Numeric(12, 2), nullable=True)
    salary_currency = db.Column(db.String(8), default="USD", nullable=False)
    salary_range = db.Column(db.String(64), nullable=True)  # Formatted text cache

    application_deadline = db.Column(db.DateTime(timezone=True), nullable=True)
    published_at = db.Column(db.DateTime(timezone=True), nullable=True)
    closed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    author = db.relationship("User", foreign_keys=[created_by_user_id], backref=db.backref("authored_jobs", lazy="dynamic"))
    applications = db.relationship("Application", backref="job", lazy="dynamic", cascade="all, delete-orphan")

    @property
    def min_experience_years(self):
        """Backward-compatibility alias."""
        return self.minimum_experience_years

    @min_experience_years.setter
    def min_experience_years(self, val):
        self.minimum_experience_years = val

    @property
    def qualification(self):
        """Backward-compatibility alias."""
        return self.minimum_qualification

    @qualification.setter
    def qualification(self, val):
        self.minimum_qualification = val

    @property
    def is_open(self):
        """Check if job is open for candidate submissions."""
        if self.status not in ("published", "active"):
            return False
        if self.application_deadline:
            now = datetime.now(timezone.utc)
            deadline = self.application_deadline
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)
            if now > deadline:
                return False
        return True


class Resume(db.Model):
    """Resume documents and parsed metadata for candidate ranking."""
    __tablename__ = "resumes"

    id = db.Column(db.Integer, primary_key=True)
    candidate_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    candidate_id = db.Column(db.Integer, db.ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=True, index=True)
    storage_key = db.Column(db.String(64), unique=True, nullable=True, index=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(512), nullable=False)
    file_type = db.Column(db.String(16), nullable=False)  # pdf, docx
    file_extension = db.Column(db.String(16), nullable=True)  # .pdf, .docx
    file_size = db.Column(db.Integer, nullable=False)  # backward compat
    file_size_bytes = db.Column(db.Integer, nullable=True)
    mime_type = db.Column(db.String(128), nullable=True)
    raw_text = db.Column(db.Text, nullable=True)
    parsed_skills = db.Column(db.Text, nullable=True)
    parsed_experience_years = db.Column(db.Float, nullable=True)
    parsing_status = db.Column(db.String(32), default="pending")  # backward compat
    processing_status = db.Column(db.String(32), default="uploaded", nullable=False, index=True)  # uploaded, processing, parsed, failed
    processing_error_code = db.Column(db.String(64), nullable=True)
    extracted_data = db.Column(db.Text, nullable=True)  # JSON payload
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    uploaded_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    processed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    candidate_user = db.relationship("User", foreign_keys=[candidate_user_id], backref=db.backref("uploaded_resumes", lazy="dynamic"))
    applications = db.relationship("Application", backref="resume", lazy="dynamic")

    @property
    def candidate_profile(self):
        if self.candidate_user and hasattr(self.candidate_user, "candidate_profile"):
            return self.candidate_user.candidate_profile
        return None

    def get_extracted_data(self):
        """Returns structured extracted data as a Python dictionary."""
        if not self.extracted_data:
            return {}
        try:
            return json.loads(self.extracted_data)
        except (ValueError, TypeError):
            return {}

    def set_extracted_data(self, data):
        """Serializes Python dictionary to extracted_data JSON and syncs model fields."""
        if not isinstance(data, dict):
            data = {}
        self.extracted_data = json.dumps(data)
        
        # Sync parsed_skills if available
        skills = data.get("skills")
        if isinstance(skills, list):
            self.parsed_skills = ", ".join(skills)
        elif isinstance(skills, str):
            self.parsed_skills = skills

        # Sync parsed_experience_years if available
        exp_years = data.get("total_experience_years") or data.get("experience_years")
        if exp_years is not None:
            try:
                self.parsed_experience_years = float(exp_years)
            except (ValueError, TypeError):
                pass

    @property
    def skills_list(self):
        """Returns a list of extracted skills."""
        data = self.get_extracted_data()
        skills = data.get("skills")
        if isinstance(skills, list):
            return skills
        if self.parsed_skills:
            return [s.strip() for s in self.parsed_skills.split(",") if s.strip()]
        return []

    @property
    def file_size_formatted(self):
        """Returns human-readable file size."""
        size = self.file_size_bytes or self.file_size or 0
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / (1024 * 1024):.2f} MB"



class Application(db.Model):
    """
    Candidate job applications tracking stage, score, and recruitment workflow.
    Unique constraint ensures one application per candidate per job.
    """
    __tablename__ = "applications"
    __table_args__ = (
        db.UniqueConstraint("job_id", "candidate_user_id", name="uq_job_candidate_application"),
    )

    VALID_STATUSES = {
        "submitted",
        "under_review",
        "shortlisted",
        "interview",
        "interview_completed",
        "offered",
        "hired",
        "rejected",
        "withdrawn",
    }

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id = db.Column(db.Integer, db.ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=True)
    resume_id = db.Column(db.Integer, db.ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True)

    status = db.Column(db.String(32), default="submitted", index=True, nullable=False)
    cover_letter = db.Column(db.Text, nullable=True)
    match_score = db.Column(db.Float, default=0.0)
    match_breakdown = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)  # Internal recruiter notes
    rejection_reason_code = db.Column(db.String(64), nullable=True)  # skill_gap, experience_gap, qualification_gap, role_changed, position_filled, other
    rejection_reason_text = db.Column(db.Text, nullable=True)
    rejection_feedback_published = db.Column(db.Boolean, default=False, nullable=False)

    applied_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    withdrawn_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Relationships
    candidate_user = db.relationship("User", foreign_keys=[candidate_user_id], backref=db.backref("submitted_applications", lazy="dynamic"))
    interviews = db.relationship("Interview", backref="application", lazy="dynamic", cascade="all, delete-orphan")
    match_result = db.relationship("MatchResult", backref="application", uselist=False, cascade="all, delete-orphan")

    @property
    def stage(self):
        """Backward-compatibility alias for status."""
        return self.status

    @stage.setter
    def stage(self, val):
        self.status = val


class Interview(db.Model):
    """
    Scheduled interview sessions with multi-interviewer assignments,
    time zone support, format validation, and lifecycle states.
    """
    __tablename__ = "interviews"

    VALID_TYPES = {"online", "phone", "in_person", "technical", "cultural", "hr"}
    VALID_STATUSES = {"scheduled", "confirmed", "completed", "cancelled", "no_show"}

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=True, index=True)
    round_name = db.Column(db.String(64), default="Initial Screening", nullable=False)
    interview_type = db.Column(db.String(32), default="online", nullable=False)
    scheduled_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    end_time = db.Column(db.DateTime(timezone=True), nullable=True)
    timezone = db.Column(db.String(64), default="UTC", nullable=False)
    interviewer_name = db.Column(db.String(128), default="Hiring Team", nullable=False)  # Display cache
    meeting_link = db.Column(db.String(512), nullable=True)
    location = db.Column(db.String(255), nullable=True)
    instructions = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(32), default="scheduled", nullable=False, index=True)
    cancellation_reason = db.Column(db.Text, nullable=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    feedback = db.Column(db.Text, nullable=True)  # Backward compat
    rating = db.Column(db.Integer, nullable=True)  # Backward compat
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    job = db.relationship("Job", foreign_keys=[job_id])
    created_by = db.relationship("User", foreign_keys=[created_by_user_id])
    assignments = db.relationship("InterviewAssignment", backref="interview", cascade="all, delete-orphan", lazy="dynamic")
    feedback_records = db.relationship("InterviewFeedback", backref="interview", cascade="all, delete-orphan", lazy="dynamic")

    @property
    def start_time(self):
        return self.scheduled_at

    @property
    def assigned_interviewers(self):
        """Returns list of User objects assigned as interviewers."""
        return [a.interviewer for a in self.assignments if a.interviewer]

    @property
    def average_rating(self):
        """Computes average score across submitted feedback records."""
        records = [f for f in self.feedback_records if f.status == "submitted" and f.overall_score is not None]
        if not records:
            return None
        return round(sum(f.overall_score for f in records) / len(records), 1)


class InterviewAssignment(db.Model):
    """
    Links interviews to one or more authorized interviewer users.
    Enforces tenant boundaries during assignment.
    """
    __tablename__ = "interview_assignments"
    __table_args__ = (
        db.UniqueConstraint("interview_id", "interviewer_user_id", name="uq_interview_interviewer_assignment"),
    )

    id = db.Column(db.Integer, primary_key=True)
    interview_id = db.Column(db.Integer, db.ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False, index=True)
    interviewer_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    interviewer = db.relationship("User", foreign_keys=[interviewer_user_id], backref=db.backref("interview_assignments", cascade="all, delete-orphan", lazy="dynamic"))


class InterviewFeedback(db.Model):
    """
    Structured feedback submitted by an interviewer for an interview session.
    Strictly restricted from candidate access unless explicitly candidate-facing.
    """
    __tablename__ = "interview_feedback"
    __table_args__ = (
        db.UniqueConstraint("interview_id", "interviewer_user_id", name="uq_interview_user_feedback"),
    )

    VALID_RECOMMENDATIONS = {"strong_hire", "hire", "neutral", "no_hire", "strong_no_hire"}

    id = db.Column(db.Integer, primary_key=True)
    interview_id = db.Column(db.Integer, db.ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False, index=True)
    interviewer_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    technical_rating = db.Column(db.Integer, nullable=True)  # 1 to 5
    problem_solving_rating = db.Column(db.Integer, nullable=True)  # 1 to 5
    communication_rating = db.Column(db.Integer, nullable=True)  # 1 to 5
    role_relevant_rating = db.Column(db.Integer, nullable=True)  # 1 to 5
    overall_score = db.Column(db.Float, nullable=True)  # Mean of non-null ratings

    strengths = db.Column(db.Text, nullable=True)
    areas_for_improvement = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)  # Confidential recruiter notes
    overall_recommendation = db.Column(db.String(32), default="neutral", nullable=False)

    is_candidate_facing = db.Column(db.Boolean, default=False, nullable=False)
    candidate_feedback = db.Column(db.Text, nullable=True)

    status = db.Column(db.String(16), default="submitted", nullable=False)  # draft, submitted
    submitted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    interviewer = db.relationship("User", foreign_keys=[interviewer_user_id], backref=db.backref("submitted_feedback", cascade="all, delete-orphan", lazy="dynamic"))

    def calculate_overall_score(self):
        """Computes mean rating across all supplied categories."""
        ratings = [r for r in [self.technical_rating, self.problem_solving_rating, self.communication_rating, self.role_relevant_rating] if r is not None]
        if ratings:
            self.overall_score = round(sum(ratings) / len(ratings), 2)
        else:
            self.overall_score = None
        return self.overall_score


class ApplicationStageHistory(db.Model):
    """
    Immutable audit trail recording every application stage transition,
    the user who authorized the transition, timestamp, and optional reason.
    """
    __tablename__ = "application_stage_histories"

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    previous_stage = db.Column(db.String(32), nullable=True)
    new_stage = db.Column(db.String(32), nullable=False)
    changed_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    changed_by = db.relationship("User", foreign_keys=[changed_by_user_id])
    application = db.relationship("Application", foreign_keys=[application_id], backref=db.backref("stage_history", order_by="ApplicationStageHistory.created_at.desc()", lazy="dynamic", cascade="all, delete-orphan"))


class Notification(db.Model):
    """
    Database-backed in-app notifications for candidates, recruiters, and interviewers.
    Never stores authentication secrets or credentials.
    """
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    recipient_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    notification_type = db.Column(db.String(64), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    link_url = db.Column(db.String(255), nullable=True)
    application_id = db.Column(db.Integer, db.ForeignKey("applications.id", ondelete="SET NULL"), nullable=True)
    interview_id = db.Column(db.Integer, db.ForeignKey("interviews.id", ondelete="SET NULL"), nullable=True)
    is_read = db.Column(db.Boolean, default=False, nullable=False, index=True)
    read_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    recipient = db.relationship("User", foreign_keys=[recipient_user_id], backref=db.backref("notifications", order_by="Notification.created_at.desc()", lazy="dynamic", cascade="all, delete-orphan"))



class MatchResult(db.Model):
    """
    Persisted explainable match score and evidence breakdown for a candidate application.
    Supports versioning, staleness detection, and transparent auditability.
    """
    __tablename__ = "match_results"
    __table_args__ = (
        db.UniqueConstraint("application_id", name="uq_match_result_application"),
    )

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    resume_id = db.Column(db.Integer, db.ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True)

    overall_score = db.Column(db.Float, nullable=True)  # Normalized 0.0 - 100.0, None if unavailable
    evidence_coverage = db.Column(db.Float, default=100.0, nullable=False)  # 0.0 - 100.0
    status = db.Column(db.String(32), default="current", index=True, nullable=False)  # current, stale, unavailable, failed
    scoring_version = db.Column(db.String(32), default="1.0.0", nullable=False)

    scoring_weights_snapshot = db.Column(db.Text, nullable=False)  # JSON
    category_scores = db.Column(db.Text, nullable=False)  # JSON
    matched_required_skills = db.Column(db.Text, nullable=True)  # JSON list
    missing_required_skills = db.Column(db.Text, nullable=True)  # JSON list
    matched_preferred_skills = db.Column(db.Text, nullable=True)  # JSON list
    missing_preferred_skills = db.Column(db.Text, nullable=True)  # JSON list

    experience_score = db.Column(db.Float, nullable=True)
    experience_explanation = db.Column(db.Text, nullable=True)
    qualification_score = db.Column(db.Float, nullable=True)
    qualification_explanation = db.Column(db.Text, nullable=True)

    missing_evidence = db.Column(db.Text, nullable=True)  # JSON list of warning notes
    explanation_summary = db.Column(db.Text, nullable=True)
    input_hash = db.Column(db.String(64), nullable=True, index=True)

    calculated_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    job = db.relationship("Job", backref=db.backref("match_results", lazy="dynamic", cascade="all, delete-orphan"))
    candidate_user = db.relationship("User", foreign_keys=[candidate_user_id])
    resume = db.relationship("Resume", foreign_keys=[resume_id])

    def get_category_scores(self):
        """Returns deserialized category scores dict."""
        try:
            return json.loads(self.category_scores) if self.category_scores else {}
        except Exception:
            return {}

    def get_scoring_weights(self):
        """Returns deserialized scoring weights snapshot dict."""
        try:
            return json.loads(self.scoring_weights_snapshot) if self.scoring_weights_snapshot else {}
        except Exception:
            return {}

    def get_matched_required_skills(self):
        try:
            return json.loads(self.matched_required_skills) if self.matched_required_skills else []
        except Exception:
            return []

    def get_missing_required_skills(self):
        try:
            return json.loads(self.missing_required_skills) if self.missing_required_skills else []
        except Exception:
            return []

    def get_matched_preferred_skills(self):
        try:
            return json.loads(self.matched_preferred_skills) if self.matched_preferred_skills else []
        except Exception:
            return []

    def get_missing_preferred_skills(self):
        try:
            return json.loads(self.missing_preferred_skills) if self.missing_preferred_skills else []
        except Exception:
            return []

    def get_missing_evidence(self):
        try:
            return json.loads(self.missing_evidence) if self.missing_evidence else []
        except Exception:
            return []


class ResumeAnalysis(db.Model):
    """
    ATS Resume Analysis record for RecruitFlow AI (Phase 7).
    Stores:
    - Resume Quality / ATS Readability Score (0.0 to 100.0) across 7 configurable categories
    - Optional Job-Specific Match Score (0.0 to 100.0) using Phase 5 matching engine
    - Detected issues with severity (high, medium, low) and category
    - Positive findings and parsing warnings
    - Actionable recommendations with prioritized checklist tracking
    - SHA-256 input_hash for staleness detection
    """
    __tablename__ = "resume_analyses"

    id = db.Column(db.Integer, primary_key=True)
    resume_id = db.Column(db.Integer, db.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id = db.Column(db.Integer, db.ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=True, index=True)
    candidate_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True)

    resume_quality_score = db.Column(db.Float, nullable=True)  # 0.0 to 100.0
    job_match_score = db.Column(db.Float, nullable=True)       # 0.0 to 100.0 (if job selected)
    status = db.Column(db.String(32), default="completed", nullable=False, index=True)  # completed, stale, incomplete, failed
    analyzer_version = db.Column(db.String(32), default="1.0.0", nullable=False)

    category_scores = db.Column(db.Text, nullable=False)   # JSON dict
    category_weights = db.Column(db.Text, nullable=False)  # JSON dict
    positive_findings = db.Column(db.Text, nullable=True)  # JSON list
    detected_issues = db.Column(db.Text, nullable=True)    # JSON list of dicts
    recommendations = db.Column(db.Text, nullable=True)    # JSON list of dicts
    checklist_state = db.Column(db.Text, nullable=True)    # JSON dict of {rec_id: {completed: bool, completed_at: str}}
    parsing_warnings = db.Column(db.Text, nullable=True)   # JSON list of strings
    input_hash = db.Column(db.String(64), nullable=True, index=True)

    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    resume = db.relationship("Resume", backref=db.backref("analyses", lazy="dynamic", cascade="all, delete-orphan"))
    candidate = db.relationship("CandidateProfile", backref=db.backref("resume_analyses", lazy="dynamic"))
    candidate_user = db.relationship("User", foreign_keys=[candidate_user_id])
    job = db.relationship("Job", backref=db.backref("resume_analyses", lazy="dynamic"))

    def get_category_scores(self):
        try:
            return json.loads(self.category_scores) if self.category_scores else {}
        except Exception:
            return {}

    def get_category_weights(self):
        try:
            return json.loads(self.category_weights) if self.category_weights else {}
        except Exception:
            return {}

    def get_positive_findings(self):
        try:
            return json.loads(self.positive_findings) if self.positive_findings else []
        except Exception:
            return []

    def get_detected_issues(self):
        try:
            return json.loads(self.detected_issues) if self.detected_issues else []
        except Exception:
            return []

    def get_recommendations(self):
        try:
            return json.loads(self.recommendations) if self.recommendations else []
        except Exception:
            return []

    def get_checklist_state(self):
        try:
            return json.loads(self.checklist_state) if self.checklist_state else {}
        except Exception:
            return {}

    def get_parsing_warnings(self):
        try:
            return json.loads(self.parsing_warnings) if self.parsing_warnings else []
        except Exception:
            return []


