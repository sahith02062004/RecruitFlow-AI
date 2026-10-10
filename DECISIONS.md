# Architecture & Design Decisions Log: RecruitFlow AI

## ADR-001: Flask Application Factory & Modular Blueprint Architecture
* **Date:** 2026-10-09
* **Status:** Accepted & Implemented
* **Context:** RecruitFlow AI is designed as an enterprise-grade AI resume screening and applicant tracking platform. To prevent monolithic code smells and facilitate independent feature scaling, modular encapsulation is required across 10 functional domains.
* **Decision:** Implemented the Flask Application Factory pattern (`create_app`) combined with modular Flask Blueprints (`main`, `auth`, `candidates`, `recruiters`, `jobs`, `applications`, `resumes`, `matching`, `interviews`, `reports`, `admin`).
* **Consequences:** Provides clean separation of concerns, test isolation, clear blueprint URL namespaces, and independent evolvability.

---

## ADR-002: Dual-Mode Database Architecture (MySQL 8 Primary with SQLite Test/Dev Isolation)
* **Date:** 2026-10-09
* **Status:** Accepted & Implemented
* **Context:** Production environments require MySQL 8 with UTF8mb4 character sets, connection pooling, and strict relational integrity. However, automated testing and developer machines without active local MySQL daemon instances must run reliably and deterministically without blocking.
* **Decision:** 
  - Standardized on SQLAlchemy 2.0 with Flask-SQLAlchemy and Flask-Migrate (Alembic).
  - Production & standard dev modes connect to MySQL 8 via `mysql+pymysql` driver.
  - Testing suite (`TestingConfig`) leverages isolated in-memory SQLite (`sqlite:///:memory:`) executed per test cycle.
  - Development configuration includes a transparent fallback flag (`USE_SQLITE_DEV_FALLBACK=True`) which uses a local file database when MySQL 8 is not yet provisioned on developer laptops.
* **Consequences:** Eliminates external service coupling during CI/CD test runs and local unit tests while retaining MySQL 8 schema compliance.

---

## ADR-003: Enterprise Design System and Truthful Empty States
* **Date:** 2026-10-09
* **Status:** Accepted & Implemented
* **Context:** Recruitment dashboards frequently suffer from visual clutter, poor contrast, and deceptive placeholder metrics.
* **Decision:**
  - Standardized on an enterprise recruitment palette: crisp clean light surfaces (`#f8fafc`, `#ffffff`), deep slate navy typography (`#0f172a`), deep navy primary action anchors (`#1e3a8a`), and subtle teal accents (`#0f766e`).
  - Implemented explicit empty states with custom Jinja2 reusable macros (`components/empty_state.html`). No fake candidate figures, mock percentages, or fabricated statistics are presented; counts reflect exact database state.
* **Consequences:** Elevated usability, WCAG accessible color contrast, and immediate visual clarity for recruiters.

---

## ADR-004: Security and Input Protection Baseline
* **Date:** 2026-10-09
* **Status:** Accepted & Implemented
* **Context:** Enterprise talent systems process sensitive personal data (PII) including candidate contact details, work histories, and recruiter notes.
* **Decision:**
  - Integrated `Flask-WTF` CSRF protection globally on all forms.
  - Password hashing utilizing Werkzeug scrypt/pbkdf2 via `User.set_password()` and `User.check_password()`.
  - Strong session protection enabled via `Flask-Login` (`login_manager.session_protection = 'strong'`).
  - Centralized HTTP error handlers delivering branded HTML views for browser users and JSON error structures for API consumers.
* **Consequences:** Strong foundational security against CSRF, brute-force session hijacking, and unhandled exceptions.

---

## ADR-005: Role-Based Access Control (RBAC) & Multi-Tenant Organization Isolation (Phase 2)
* **Date:** 2026-10-09
* **Status:** Accepted & Implemented
* **Context:** Separate user roles (`candidate`, `recruiter`, `organization_admin`, `platform_admin`) must be strictly enforced on the server to prevent privilege escalation and unauthorized cross-account / cross-organization access.
* **Decision:**
  - Public registration only allows choosing between `candidate` and `recruiter`. Global `platform_admin` accounts can never be created via public registration and must be provisioned via the secure CLI command `flask create-admin`.
  - Recruiter registration automates organization onboarding with safe slug collision avoidance (`name-1`, `name-2`), creating an initial `OrganizationMembership(membership_role='admin')`. New organizations default to `is_verified=False` to truthfully represent unverified status.
  - Created reusable security decorators in `app/core/security.py`: `role_required`, `candidate_required`, `recruiter_required`, `platform_admin_required`, and `org_membership_required`.
  - Decorated endpoints reject unauthenticated access with redirects to login and unauthorized access with HTTP 403 Forbidden.
* **Consequences:** Comprehensive defense-in-depth preventing IDOR (Insecure Direct Object References) and cross-tenant data leakage.

---

## ADR-006: Cryptographic Single-Use Time-Limited Password Reset Tokens (Phase 2)
* **Date:** 2026-10-09
* **Status:** Accepted & Implemented
* **Context:** Password resets must protect account existence privacy, avoid exposing plain tokens in databases or server logs, and guard against token reuse or replay attacks.
* **Decision:**
  - Stored only a SHA-256 hash of tokens in the database (`PasswordResetToken.token_hash`), never raw tokens.
  - Set a 1-hour expiration timestamp (`expires_at`) using timezone-aware UTC.
  - Invalidated tokens upon successful use (`used_at = utc_now()`).
* **Consequences:** Secure, OWASP-compliant password reset workflow with zero token leakage.

---

## ADR-007: Job Lifecycle Management, Candidate Applications & Duplicate Prevention (Phase 3)
* **Date:** 2026-10-09
* **Status:** Accepted & Implemented
* **Context:** Phase 3 requires robust job requisition lifecycle management (`draft`, `published`/`active`, `closed`, `archived`) and candidate applications with strict single-submission enforcement, multi-tenant organization boundary checks, and application withdrawal capabilities.
* **Decision:**
  - Extended `Job` model with `organization_id`, `created_by_user_id`, `workplace_type`, `employment_type`, numeric `salary_min`/`salary_max`, `salary_currency`, `application_deadline`, `published_at`, and `closed_at`.
  - Enforced that candidates can only view published/active jobs and cannot view drafts or apply to closed/archived/deadline-expired requisitions.
  - Extended `Application` model with `candidate_user_id` and unique constraint `uq_job_candidate_application` on `(job_id, candidate_user_id)` to prevent duplicate application submissions.
  - Implemented application workflow states (`submitted`, `under_review`, `shortlisted`, `interview`, `offered`, `rejected`, `withdrawn`).
  - Added candidate withdrawal endpoint (`POST /applications/<id>/withdraw`).
  - Enforced strict organization tenancy: recruiters can only view or review applicants belonging to their authorized organization context, preventing cross-organization snooping.
* **Consequences:** Reliable, isolated applicant tracking workflows with zero duplicate submissions and strict multi-tenant integrity.

---

## ADR-008: Secure Resume Storage, Magic-Byte Inspection, Deterministic Extraction & Profile Sync (Phase 4)
* **Date:** 2026-10-09
* **Status:** Accepted & Implemented
* **Context:** Candidate resume uploads present significant security and data parsing challenges: potential malicious file uploads (executables, scripts disguised as PDFs), path traversal vulnerabilities, corrupted or scanned documents, and inconsistent unstructured text.
* **Decision:**
  - Enforced server-side file constraints: strict 5 MB file size limit and allowed extensions (`.pdf`, `.docx`).
  - Implemented magic-byte header inspection before storage (`%PDF-` for PDFs, `PK\x03\x04` + OpenXML validation for Word documents), immediately rejecting disguised malicious files.
  - Used UUIDv4 storage keys with safe file naming outside the web root (`uploads/resumes/<uuid>.<ext>`), strictly preventing directory traversal attacks via `is_relative_to` path assertions.
  - Built high-speed text extraction services using `PyMuPDF` (`pymupdf`) for PDFs and `python-docx` for Word documents, including page counting, table/cell extraction, and diagnostic warnings for scanned/image-only PDFs.
  - Implemented deterministic regex and dictionary-based extraction for candidate names, RFC-compliant emails, international phone formats, links (LinkedIn, GitHub, Portfolio), education degrees, and experience history without paid or flaky external LLM APIs.
  - Developed a comprehensive canonical skills taxonomy mapping 80+ canonical skills and their common abbreviations/aliases (e.g., "k8s" -> "Kubernetes", "postgres" -> "PostgreSQL", "JS" -> "JavaScript").
  - Provided candidates full control to review, edit, and correct parsed information via a dedicated review modal and one-click profile synchronization.
  - Enforced tenant-isolated access controls on downloads: candidates own their resumes, unauthorized recruiters receive HTTP 403 Forbidden, and recruiters gain access only when candidates apply to a job within their organization context.
* **Consequences:** Safe, high-performance resume parsing pipeline that enriches candidate profiles while maintaining airtight application security and privacy.

---

## ADR-009: Explainable Candidate Matching, Dynamic Weight Redistribution & Deterministic Ranking Engine (Phase 5)
* **Date:** 2026-10-09
* **Status:** Accepted & Implemented
* **Context:** Automated applicant ranking systems frequently suffer from black-box obscurity, non-deterministic model drift, demographic bias, and unfair penalties when job requirements lack specific attributes (e.g. no preferred skills or education specified). Furthermore, LLM API calls are expensive, rate-limited, and non-deterministic for scoring.
* **Decision:**
  - Implemented a 100% deterministic, zero-external-API matching engine in pure Python.
  - Standardized on a modular category scoring formula summing to 1.0 (100%):
    - Required Skills: 50%
    - Preferred Skills: 20%
    - Experience Alignment: 20%
    - Educational Qualification: 10%
  - Implemented dynamic weight redistribution: When a requisition has no requirements for a category (e.g. no preferred skills or no minimum qualification stated), that category's weight is proportionally redistributed to the active categories without penalizing candidates.
  - Built a strict token-boundary skill normalizer preventing false-positive substring matches (`Java != JavaScript`, `C != C++/C#`) while resolving industry aliases (`js -> javascript`, `postgres -> postgresql`, `k8s -> kubernetes`).
  - Tracked explicit evidence coverage: If candidate resume evidence is absent, the system does not fabricate 0% or 100% scores; instead, the evidence coverage percentage reflects missing documentation and the category/overall score is reported as `None` ("Unavailable").
  - Implemented SHA-256 `input_hash` staleness tracking across job requirements, candidate resume data, candidate profile attributes, and scoring algorithm version (`1.0.0`) to immediately flag when scores are outdated and require re-evaluation.
  - Standardized deterministic 4-tier candidate ranking with strict tie-breaking: `overall_score DESC` -> `evidence_coverage DESC` -> `applied_at ASC` -> `id ASC`.
  - Enforced multi-tenant isolation: Recruiters can only access matching calculations and candidate rankings for jobs belonging to their authorized organization context. Candidates cannot view internal match scores or recalculate results.
* **Consequences:** Fully auditable, transparent, high-performance, and compliant candidate evaluation engine that gives hiring teams complete explainability while protecting candidate fairness.

---

## ADR-010: Multi-Round Interview Coordination, Feedback Privacy, Stage Machine & Event Notifications (Phase 6)
* **Date:** 2026-10-09
* **Status:** Accepted & Implemented
* **Context:** Collaborative hiring requires multi-round interview scheduling, conflict detection, structured interviewer evaluation rubrics, and kanban-style pipeline stage management. Crucially, internal interviewer ratings and feedback must remain strictly confidential from candidates to preserve candid evaluations, while candidates require clear interview schedule visibility, meeting links, and stage transparency. Furthermore, AI match scores from Phase 5 must never automatically change application stages without human recruiter intervention.
* **Decision:**
  - Standardized on a dedicated multi-round `Interview` model supporting sequential round types (`screening`, `technical`, `behavioral`, `system_design`, `culture_fit`, `final`) and formats (`virtual`, `in_person`, `phone`).
  - Implemented timezone-aware interviewer conflict detection with UTC normalization to proactively detect overlapping interview assignments.
  - Implemented structured 1-5 interview feedback rubrics across 4 core competencies (technical competency, problem solving, communication, and culture fit) with standardized hiring recommendations (`strong_hire`, `hire`, `neutral`, `do_not_hire`, `strong_no_hire`).
  - Enforced strict feedback confidentiality: Candidates cannot access internal interview scoring cards, notes, or rubrics (HTTP 403 Forbidden). Only candidate-facing feedback fields explicitly marked for candidates can be exposed.
  - Implemented an immutable `ApplicationStageHistory` audit log and explicit state machine (`VALID_STAGE_TRANSITIONS`) governing application progression.
  - Enforced human-in-the-loop governance: AI match scores never trigger stage transitions or autonomous hiring/rejection decisions. All stage changes must be initiated by authorized recruiters or candidate withdrawals.
  - Integrated in-app notifications (`Notification` model) with real-time unread badges, mark-as-read endpoints, and strict multi-tenant user isolation.
  - Built an interactive visual Kanban pipeline board (`/applications/pipeline`) grouped by stage with candidate cards and interview indicators.
* **Consequences:** End-to-end recruitment pipeline coordination that enables multi-interviewer collaboration, protects evaluation privacy, guarantees auditability, and provides candidates with a smooth interview experience.

---

## ADR-011: ATS Quality Heuristics, Dual Score Separation, Truthful Writing Assistance & Multi-Tenant Analytics (Phase 7)
* **Date:** 2026-10-09
* **Status:** Accepted & Implemented
* **Context:** Recruiters and candidates require transparent insights into ATS document quality, job compatibility, and pipeline health. However, conflating resume readability with job fitness creates confusion. Furthermore, automated resume suggestions must not encourage fabrication, candidate feedback must provide dignity without violating recruiter internal confidentiality, and recruiter CSV exports must be protected against formula injection vulnerabilities.
* **Decision:**
  - Implemented a dual-score architecture:
    - **Score A: ATS Resume Quality (0–100):** General ATS readability and completeness measured across 7 configurable categories summing strictly to 1.0 (Contact & Links 15%, Education Formatting 15%, Experience Formatting 20%, Skills Section 15%, Action Verbs 15%, Measurable Achievements 10%, File Structure & Readability 10%). Evaluates document health independent of any specific requisition.
    - **Score B: Job-Specific Match (0–100):** Leverages the Phase 5 engine (Required Skills 50%, Preferred Skills 20%, Experience 20%, Education 10% with dynamic redistribution) comparing the candidate's verified profile and resume against a target requisition.
  - Built an evidence-based side-by-side comparison view (`/resumes/<id>/compare`) comparing 10 criteria with strict token boundary matching (`Java != JavaScript`).
  - Added an evidence-based "Why Was My Resume Not Shortlisted?" diagnosis (`/resumes/<id>/why-not-shortlisted/<job_id>`) showing matched vs missing criteria, transparent disclaimers that shortlisting reflects the competitive applicant pool, and published recruiter rejection reasons without ever exposing internal notes or interview rubrics.
  - Designed the Resume Improvement Assistant (`/resumes/<id>/improvements`) with a 3-tier prioritized checklist (`high`, `medium`, `low`) and concrete before/after bullet rewrites. Enforced strict professional integrity: suggestions never fabricate unearned credentials, fictitious employers, or invented metrics.
  - Implemented multi-tenant hiring funnel metrics and KPI dashboards (`/reports/`) tracking stage drop-offs (`submitted` -> `under_review` -> `shortlisted` -> `interview` -> `offered` -> `hired`) with zero-division safety and Chart.js visualizations.
  - Sanitized CSV exports (`/reports/export/applications.csv`) by prepending a single quote (`'`) to any cell starting with `=`, `+`, `-`, or `@` to defend against spreadsheet formula injection attacks.
  - Added a production WSGI entry point (`wsgi.py`) for enterprise deployment.
* **Consequences:** Provides candidates with actionable, honest feedback to improve their career trajectory while equipping recruiters with compliant, secure, and privacy-preserving hiring funnel analytics.
