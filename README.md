# RecruitFlow AI - AI-Assisted Resume Screening & Candidate Ranking Platform

RecruitFlow AI is an enterprise talent acquisition platform engineered to eliminate manual resume screening friction, improve candidate ranking accuracy, and provide clear hiring workflows.

---

## Technical Architecture (Phases 1 - 4)

- **Framework:** Python 3.12+ / Flask (Application Factory & Modular Blueprints)
- **Primary Database:** MySQL 8 with SQLAlchemy 2.0 and Flask-Migrate (Alembic)
- **Test Database:** In-memory isolated SQLite (`sqlite:///:memory:`)
- **Security & Authentication:** 
  - Flask-Login session management
  - Flask-WTF CSRF protection
  - Werkzeug secure password hashing
  - Server-side RBAC decorators (`@role_required`, `@candidate_required`, `@recruiter_required`, `@platform_admin_required`, `@org_membership_required`)
  - Cryptographically secure single-use time-limited SHA-256 hashed password reset tokens
  - Open redirect validation and account existence privacy
- **Resume Ingestion & Extraction Engine (Phase 4):**
  - PyMuPDF (`pymupdf`) for high-speed PDF text parsing with page inspection and scanned image detection
  - `python-docx` for structured Word document parsing including paragraph and table cell extraction
  - Magic byte inspection (`%PDF-` and `PK\x03\x04` OpenXML headers) to prevent disguised malicious file uploads
  - UUIDv4 storage keys with safe disk storage outside web root (`uploads/resumes/`) and path traversal defenses
  - Deterministic information extraction (regex + dictionary taxonomy) for candidate name, email, phone, links, education degrees, experience chronology/years, and canonical skills normalization
  - Candidate review & correction workflow with one-click `CandidateProfile` synchronization
  - Tenant-isolated recruiter authorization checks for resume viewing and downloads
- **Explainable Matching & Ranking Engine (Phase 5):**
  - Pure Python deterministic scoring engine (zero external LLM API dependency)
  - Configurable category weights summing strictly to 100%: Required Skills (50%), Preferred Skills (20%), Experience Alignment (20%), Educational Qualification (10%)
  - Dynamic weight redistribution: missing/unspecified job criteria automatically redistributed to active categories without candidate penalty
  - Strict skill normalizer with alias resolution (`js` -> `javascript`, `postgres` -> `postgresql`) and token-boundary matching (`Java != JavaScript`, `C != C++/C#`)
  - Explicit evidence coverage tracking: missing candidate data reports accurate coverage without inventing 0% or 100% scores
  - SHA-256 `input_hash` staleness tracking across job requirements, candidate data, and scoring version
  - 4-tier deterministic tie-breaking: `overall_score DESC` -> `evidence_coverage DESC` -> `applied_at ASC` -> `id ASC`
  - Fully auditable recruiter explanation interface with category percentages, matched/missing skill chips, and responsible AI safeguards
- **ATS Resume Quality & Job Match Analyzer (Phase 7):**
  - Dual-score evaluation architecture separating Resume Readability (0–100) from Job-Specific Match (0–100)
  - 7 configurable ATS quality categories summing strictly to 1.0 (100%): Contact & Links (15%), Education (15%), Experience (20%), Skills (15%), Action Verbs (15%), Measurable Achievements (10%), File Readability (10%)
  - Side-by-side comparison (`/resumes/<id>/compare`) evaluating 10 criteria with strict token boundary matching (`Java != JavaScript`)
  - Evidence-based "Why Was My Resume Not Shortlisted?" diagnosis (`/resumes/<id>/why-not-shortlisted/<job_id>`) with transparent disclaimers and candidate visibility controls on recruiter rejection reasons
  - Resume Improvement Assistant (`/resumes/<id>/improvements`) with 3-tier prioritized checklist (`high`, `medium`, `low`) and truthful before/after bullet rewrites
  - Recruiter Analytics & Hiring Funnel (`/reports/`) tracking stage drop-offs (`submitted` -> `under_review` -> `shortlisted` -> `interview` -> `offered` -> `hired`) with Chart.js and zero-division protection
  - OWASP formula injection protected CSV export (`/reports/export/applications.csv`) prepending `'` to trigger symbols
- **UI & Design System:** Responsive Bootstrap 5, Bootstrap Icons, Chart.js, custom enterprise styling (`Inter` font, deep slate navy `#0f172a`, primary navy `#1e3a8a`, refined teal `#0f766e`, truthful empty-state macros)


---

## Directory Structure

```
recruitflow-ai/
├── run.py                          # Development entry point
├── wsgi.py                         # Production WSGI entry point (Gunicorn/uWSGI)
├── requirements.txt                # Python package specifications
├── pytest.ini                      # Pytest runner configuration
├── .env.example                    # Sample environment variables
├── .env                            # Active local configuration
├── .gitignore                      # Git exclusion rules
├── README.md                       # Platform documentation
├── DECISIONS.md                    # Architecture Decision Records (ADRs)
├── PROJECT_STATUS.md               # Milestones, test outcomes & phase tracking
├── migrations/                     # Flask-Migrate / Alembic version scripts
│   └── versions/
│       ├── 4e29201a8bf4_phase_2_baseline_schema.py
│       ├── e3ba5cc6eff2_phase_6_interview_scheduling_hiring_.py
│       └── c8d7e6f5a4b3_phase_7_ats_resume_analyses_and_rejection_schema.py
├── app/
│   ├── __init__.py                 # Flask create_app() factory
│   ├── config/                     # Environment configuration classes
│   │   ├── __init__.py
│   │   └── config.py
│   ├── core/                       # Shared extensions, logging, security & commands
│   │   ├── __init__.py
│   │   ├── extensions.py           # db, migrate, login_manager, csrf
│   │   ├── security.py             # RBAC decorators (@role_required, @org_membership_required)
│   │   ├── commands.py             # CLI commands (flask create-admin)
│   │   ├── logging.py              # File & console logging setup
│   │   └── errors.py               # Custom 400, 403, 404, 500 handlers
│   ├── models/                     # SQLAlchemy relational schema
│   │   ├── __init__.py
│   │   └── models.py               # User, Organization, Membership, Profiles, ResetTokens, Job, Resume, App, Interview, ResumeAnalysis
│   ├── services/                   # Business logic & algorithms
│   │   ├── __init__.py
│   │   ├── resume_parser_service.py # PyMuPDF & docx extraction
│   │   ├── scoring_service.py      # Deterministic job match scoring
│   │   ├── interview_service.py    # Multi-round interview coordination
│   │   ├── ats_analyzer_service.py # 7-category ATS quality scoring
│   │   ├── resume_improvement_service.py # Actionable writing suggestions
│   │   ├── shortlisting_gap_service.py # Gap diagnostics & rejection feedback
│   │   └── recruitment_analytics_service.py # Funnel metrics & secure CSV export
│   ├── blueprints/                 # 10 modular business domains
│   │   ├── main/                   # Landing page, dashboard, health check
│   │   ├── auth/                   # Candidate & Recruiter registration, login, logout, password reset, settings
│   │   ├── candidates/             # Candidate portal, personal dashboard, profile management
│   │   ├── recruiters/             # Recruiter portal, organization workspace, profile
│   │   ├── jobs/                   # Job posting, applicants review, status updates
│   │   ├── applications/           # Candidate pipeline tracking, Kanban board
│   │   ├── resumes/                # Document ingest, ATS analysis, comparison, improvements
│   │   ├── matching/               # Ranking and matching overview
│   │   ├── interviews/             # Scheduling & interview rubrics
│   │   ├── reports/                # Talent analytics & Chart.js funnel
│   │   └── admin/                  # Administrative controls
│   ├── static/
│   │   ├── css/style.css           # Enterprise design system
│   │   └── js/main.js              # Client interactivity (password toggles, alerts)
│   └── templates/
│       ├── layouts/base.html       # Master layout with responsive navbar & alerts
│       ├── components/empty_state.html # Reusable truthful zero-state macro
│       ├── errors/                 # 400, 403, 404, 500 views
│       └── [module]/               # Blueprint-specific templates
└── tests/
    ├── conftest.py                 # Pytest fixtures and isolated SQLite setup
    ├── test_basic.py               # Health-check, landing, dashboard empty-states
    ├── test_auth.py                # Candidate/recruiter signup, login, lockout, password reset
    ├── test_rbac.py                # RBAC decorators and tenant isolation
    ├── test_profiles.py            # Profile editing and password updates
    ├── test_jobs_applications.py   # Job workflows and duplicate checks
    ├── test_resumes.py             # Parsing, magic bytes, skills extraction
    ├── test_matching.py            # Deterministic scoring and weight redistribution
    ├── test_interviews_pipeline.py # Interviews, rubrics, Kanban and notifications
    └── test_phase7_ats_analytics.py # ATS scoring, comparisons, improvements, funnel & CSV export
```

---

## Setup & Running on Windows PowerShell

### 1. Set Workspace & Virtual Environment

Open **Windows PowerShell** in the project directory:

```powershell
# Navigate into the project folder
cd C:\Users\sahit\.gemini\antigravity\scratch\recruitflow-ai

# Optional: Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 2. Install Dependencies

```powershell
pip install -r requirements.txt
```

### 3. Configure Database (MySQL 8 or Local Development SQLite)

#### Option A: Running with Local MySQL 8
If you have MySQL 8 installed locally on your Windows machine:

1. Open MySQL Shell or Command Line client:
```sql
CREATE DATABASE recruitflow_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'recruitflow_user'@'localhost' IDENTIFIED BY 'recruitflow_password';
GRANT ALL PRIVILEGES ON recruitflow_db.* TO 'recruitflow_user'@'localhost';
FLUSH PRIVILEGES;
```

2. Update your `.env` file:
```ini
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=recruitflow_user
DB_PASSWORD=recruitflow_password
DB_NAME=recruitflow_db
USE_SQLITE_DEV_FALLBACK=False
```

3. Run migrations:
```powershell
flask db upgrade
```

#### Option B: Zero-Config Local Development Fallback
By default, `USE_SQLITE_DEV_FALLBACK=True` in `.env`. If you do not have MySQL running, RecruitFlow AI will automatically use a local SQLite file (`recruitflow_dev.db`) and auto-apply migrations without blocking development.

### 4. Create Initial Platform Administrator Account

Global administrators cannot be created via public registration. Use the secure CLI command:

```powershell
flask create-admin
```
Follow the interactive prompt to set the admin email, name, and password.

### 5. Run Automated Tests

Execute the full suite of automated unit and integration tests:

```powershell
pytest
```

*(Result: 85 passed in ~26 seconds with 0 failures)*

### 6. Launch the Application

For development:
```powershell
python run.py
```

For production-style WSGI execution:
```powershell
# On Linux/macOS or with Gunicorn on production:
gunicorn -w 4 -b 0.0.0.0:5000 wsgi:application

# Or on Windows with Waitress:
pip install waitress
waitress-serve --port=5000 wsgi:application
```

The web application will start at:
👉 **http://127.0.0.1:5000**

- **Health Check Endpoint:** http://127.0.0.1:5000/health
- **Candidate Registration:** http://127.0.0.1:5000/auth/register/candidate
- **Recruiter Registration:** http://127.0.0.1:5000/auth/register/recruiter
- **Login Portal:** http://127.0.0.1:5000/auth/login
- **Password Reset:** http://127.0.0.1:5000/auth/forgot-password
- **Candidate Dashboard:** http://127.0.0.1:5000/candidates/dashboard
- **Candidate Interviews:** http://127.0.0.1:5000/interviews/my-interviews
- **Notification Center:** http://127.0.0.1:5000/notifications/
- **ATS Resume Analyzer:** http://127.0.0.1:5000/resumes/<id>/analyze
- **Resume vs Job Comparison:** http://127.0.0.1:5000/resumes/<id>/compare?job_id=<job_id>
- **Resume Improvement Assistant:** http://127.0.0.1:5000/resumes/<id>/improvements
- **Why Was My Resume Not Shortlisted?:** http://127.0.0.1:5000/resumes/<id>/why-not-shortlisted/<job_id>
- **Recruiter Dashboard:** http://127.0.0.1:5000/recruiters/dashboard
- **Recruiter Job Openings:** http://127.0.0.1:5000/jobs/
- **Recruiter Kanban Pipeline Board:** http://127.0.0.1:5000/applications/pipeline
- **Recruiter Interview Management:** http://127.0.0.1:5000/interviews/
- **Recruiter Analytics & Hiring Funnel:** http://127.0.0.1:5000/reports/
- **Sanitized Applications CSV Export:** http://127.0.0.1:5000/reports/export/applications.csv
- **Resume Upload & Ingestion:** http://127.0.0.1:5000/resumes/upload
- **Resume Repository:** http://127.0.0.1:5000/resumes/
- **Recruiter Requisitions & Matching:** http://127.0.0.1:5000/matching/
- **Platform Administration:** http://127.0.0.1:5000/admin/

---

## Health Check API Specification

* **Endpoint:** `GET /health`
* **Response Status:** `200 OK` (when operational) or `503 Service Unavailable`
* **JSON Payload:**
```json
{
  "database": {
    "engine": "sqlite",
    "error": null,
    "status": "healthy"
  },
  "service": "RecruitFlow AI",
  "status": "UP",
  "version": "1.0.0-phase1"
}
```
