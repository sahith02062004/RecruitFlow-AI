"""
Recruiter Blueprint Routes for RecruitFlow AI.
Includes:
- Recruiter overview & dashboard
- View and update own recruiter profile
- Organization context and settings
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for, abort
from flask_login import current_user
from app.core.extensions import db
from app.core.security import recruiter_required, org_membership_required
from app.models.models import RecruiterProfile, Organization, OrganizationMembership, Job, Application
from app.blueprints.auth.forms import RecruiterProfileForm

recruiters_bp = Blueprint("recruiters", __name__, url_prefix="/recruiters")


@recruiters_bp.route("/dashboard")
@recruiter_required
def dashboard():
    """Recruiter dashboard showing organization jobs and candidates."""
    recruiter_prof = current_user.recruiter_profile
    membership = current_user.memberships.first()
    organization = membership.organization if membership else None

    # Retrieve jobs associated with this organization
    if organization:
        jobs = organization.jobs.all()
        job_ids = [j.id for j in jobs]
        applications = Application.query.filter(Application.job_id.in_(job_ids)).all() if job_ids else []
    else:
        jobs = recruiter_prof.jobs.all() if recruiter_prof else []
        applications = []

    return render_template(
        "recruiters/dashboard.html",
        recruiter=recruiter_prof,
        organization=organization,
        membership=membership,
        jobs=jobs,
        applications=applications
    )


@recruiters_bp.route("/profile", methods=["GET", "POST"])
@recruiter_required
def profile():
    """View and edit personal recruiter profile."""
    profile_record = current_user.recruiter_profile
    if not profile_record:
        profile_record = RecruiterProfile(user_id=current_user.id)
        db.session.add(profile_record)
        db.session.commit()

    form = RecruiterProfileForm(obj=profile_record)

    if form.validate_on_submit():
        form.populate_obj(profile_record)
        db.session.commit()
        flash("Your recruiter profile has been updated.", "success")
        return redirect(url_for("recruiters.profile"))

    return render_template("recruiters/profile.html", form=form, profile=profile_record)


@recruiters_bp.route("/organization/<int:org_id>")
@recruiter_required
@org_membership_required()
def organization_settings(org_id):
    """View organization details for member recruiters."""
    org = db.session.get(Organization, org_id)
    if not org:
        abort(404)
    members = org.memberships.all()
    return render_template("recruiters/organization.html", organization=org, members=members)


@recruiters_bp.route("/")
@recruiter_required
def overview():
    """Recruiter directory for authorized users."""
    recruiters = RecruiterProfile.query.all()
    return render_template("recruiters/index.html", recruiters=recruiters)
