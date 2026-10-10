"""
Recruitment Analytics & Reporting Service for RecruitFlow AI (Phase 7).
Implements:
- Organization-scoped recruitment KPI metrics
- Hiring funnel distribution & stage-to-stage conversion rates with 0-division safety
- Job-level talent acquisition insights
- Filtered CSV exports with strict spreadsheet formula injection protection
"""
import io
import csv
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy import func
from app.core.extensions import db
from app.models.models import (
    Job, Application, Interview, ApplicationStageHistory,
    OrganizationMembership, User
)

logger = logging.getLogger(__name__)


class RecruitmentAnalyticsService:
    """Recruitment analytics, hiring funnel, and secure reporting."""

    @classmethod
    def get_organization_overview(
        cls,
        organization_id: int,
        job_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Calculates organizational recruitment overview KPIs.
        Strictly scoped to the provided organization_id.
        """
        # Base queries
        jobs_query = Job.query.filter_by(organization_id=organization_id)
        if job_id:
            jobs_query = jobs_query.filter(Job.id == job_id)

        apps_query = Application.query.join(Job).filter(Job.organization_id == organization_id)
        if job_id:
            apps_query = apps_query.filter(Application.job_id == job_id)
        if start_date:
            apps_query = apps_query.filter(Application.applied_at >= start_date)
        if end_date:
            apps_query = apps_query.filter(Application.applied_at <= end_date)

        total_jobs = jobs_query.count()
        published_jobs = jobs_query.filter(Job.status.in_(["published", "active"])).count()

        applications = apps_query.all()
        total_applications = len(applications)

        # Stage aggregations
        stage_counts = {
            "submitted": 0,
            "under_review": 0,
            "shortlisted": 0,
            "interview": 0,
            "interview_completed": 0,
            "offered": 0,
            "hired": 0,
            "rejected": 0,
            "withdrawn": 0
        }

        for app in applications:
            st = app.status or "submitted"
            if st in stage_counts:
                stage_counts[st] += 1
            else:
                stage_counts["submitted"] += 1

        awaiting_review = stage_counts["submitted"] + stage_counts["under_review"]
        shortlisted = stage_counts["shortlisted"]
        interviews_active = stage_counts["interview"]
        interviews_completed = stage_counts["interview_completed"]
        offered = stage_counts["offered"]
        hired = stage_counts["hired"]
        rejected = stage_counts["rejected"]

        # Interview counts
        interview_query = Interview.query.join(Application).join(Job).filter(
            Job.organization_id == organization_id
        )
        if job_id:
            interview_query = interview_query.filter(Job.id == job_id)
        total_interviews_scheduled = interview_query.count()

        # Funnel Calculation: Applied -> Reviewed -> Shortlisted -> Interview -> Offered -> Hired
        # We track total reaching or passing each progression benchmark
        funnel_stages = [
            {"stage": "Applied", "count": total_applications},
            {"stage": "Under Review", "count": total_applications - stage_counts["submitted"]},
            {"stage": "Shortlisted", "count": shortlisted + interviews_active + interviews_completed + offered + hired},
            {"stage": "Interview", "count": interviews_active + interviews_completed + offered + hired},
            {"stage": "Offered", "count": offered + hired},
            {"stage": "Hired", "count": hired}
        ]

        # Calculate step-by-step conversion rates safely
        funnel_with_rates = []
        for i, step in enumerate(funnel_stages):
            cnt = step["count"]
            if i == 0:
                conv_rate = 100.0 if total_applications > 0 else 0.0
            else:
                prev_cnt = funnel_stages[i - 1]["count"]
                conv_rate = round((cnt / prev_cnt) * 100.0, 1) if prev_cnt > 0 else 0.0

            overall_rate = round((cnt / total_applications) * 100.0, 1) if total_applications > 0 else 0.0
            funnel_with_rates.append({
                "stage": step["stage"],
                "count": cnt,
                "step_conversion_pct": conv_rate,
                "overall_conversion_pct": overall_rate
            })

        return {
            "total_jobs": total_jobs,
            "published_jobs": published_jobs,
            "total_applications": total_applications,
            "awaiting_review": awaiting_review,
            "shortlisted": shortlisted,
            "interviews_scheduled": total_interviews_scheduled,
            "interviews_active": interviews_active,
            "interviews_completed": interviews_completed,
            "offered": offered,
            "hired": hired,
            "rejected": rejected,
            "stage_counts": stage_counts,
            "funnel": funnel_with_rates
        }

    @classmethod
    def get_job_level_analytics(cls, organization_id: int) -> List[Dict[str, Any]]:
        """Returns per-job metrics breakdown for organization requisitions."""
        jobs = Job.query.filter_by(organization_id=organization_id).order_by(Job.created_at.desc()).all()
        results = []

        for job in jobs:
            apps = job.applications.all()
            total_apps = len(apps)
            scores = [a.match_score for a in apps if a.match_score is not None]
            avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0

            hired_count = sum(1 for a in apps if a.status == "hired")
            active_interviews = sum(1 for a in apps if a.status in ("interview", "interview_completed"))

            results.append({
                "job_id": job.id,
                "title": job.title,
                "department": job.department or "General",
                "status": job.status,
                "total_applications": total_apps,
                "average_match_score": avg_score,
                "interviews_count": active_interviews,
                "hired_count": hired_count,
                "created_at": job.created_at
            })

        return results

    @classmethod
    def sanitize_csv_cell(cls, val: Any) -> str:
        """
        Protects against CSV / Spreadsheet Formula Injection (CSV Injection).
        Neutralizes cells beginning with dangerous formula characters: '=', '+', '-', '@', tab, CR.
        """
        if val is None:
            return ""
        str_val = str(val).strip()
        if str_val and str_val[0] in ("=", "+", "-", "@", "\t", "\r"):
            return f"'{str_val}"
        return str_val

    @classmethod
    def generate_applications_csv(
        cls,
        organization_id: int,
        job_id: Optional[int] = None,
        status: Optional[str] = None
    ) -> str:
        """
        Generates organization-isolated, formula-injection-safe CSV export of applications.
        Excludes passwords, secret tokens, and internal confidential data.
        """
        query = Application.query.join(Job).filter(Job.organization_id == organization_id)
        if job_id:
            query = query.filter(Application.job_id == job_id)
        if status:
            query = query.filter(Application.status == status)

        applications = query.order_by(Application.applied_at.desc()).all()

        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

        # Header
        headers = [
            "Application ID",
            "Job Title",
            "Department",
            "Candidate Name",
            "Candidate Email",
            "Application Status",
            "AI Match Score (%)",
            "Applied Date (UTC)",
            "Last Updated Date (UTC)"
        ]
        writer.writerow(headers)

        for app in applications:
            cand_user = app.candidate_user
            job = app.job
            row = [
                cls.sanitize_csv_cell(app.id),
                cls.sanitize_csv_cell(job.title if job else ""),
                cls.sanitize_csv_cell(job.department if job else "General"),
                cls.sanitize_csv_cell(cand_user.full_name if cand_user else "Applicant"),
                cls.sanitize_csv_cell(cand_user.email if cand_user else ""),
                cls.sanitize_csv_cell(app.status),
                cls.sanitize_csv_cell(f"{app.match_score:.1f}" if app.match_score is not None else "N/A"),
                cls.sanitize_csv_cell(app.applied_at.strftime("%Y-%m-%d %H:%M:%S") if app.applied_at else ""),
                cls.sanitize_csv_cell(app.updated_at.strftime("%Y-%m-%d %H:%M:%S") if app.updated_at else "")
            ]
            writer.writerow(row)

        return output.getvalue()
