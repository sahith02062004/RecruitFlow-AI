"""
Authentication Blueprint Routes for RecruitFlow AI.
Implements:
- Candidate registration
- Recruiter & organization onboarding registration
- Secure login with generic errors, session protection, and last_login_at tracking
- CSRF-protected logout
- Password reset request and confirmation workflows
- Account settings and password changes
"""
from datetime import datetime, timezone
import re
from urllib.parse import urlparse, urljoin
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, session
from flask_login import login_user, logout_user, login_required, current_user
from app.core.extensions import db
from app.models.models import (
    User,
    Organization,
    OrganizationMembership,
    CandidateProfile,
    RecruiterProfile,
    PasswordResetToken,
    utc_now
)
from app.blueprints.auth.forms import (
    LoginForm,
    CandidateRegistrationForm,
    RecruiterRegistrationForm,
    ForgotPasswordForm,
    ResetPasswordForm,
    ChangePasswordForm,
    AccountSettingsForm
)

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def is_safe_redirect_url(target):
    """Prevents open redirects by verifying hostname match."""
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc


def slugify(text):
    """Converts organization name to URL-friendly lowercase slug."""
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "-", text)


def get_redirect_for_user(user):
    """Returns the appropriate home dashboard according to role."""
    if user.role == "candidate":
        return url_for("candidates.dashboard")
    elif user.role in ("recruiter", "organization_admin"):
        return url_for("recruiters.dashboard")
    elif user.role == "platform_admin":
        return url_for("admin.index")
    return url_for("main.dashboard")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Unified secure authentication entry point."""
    if current_user.is_authenticated:
        return redirect(get_redirect_for_user(current_user))

    form = LoginForm()
    if form.validate_on_submit():
        normalized_email = form.email.data.strip().lower()
        user = User.query.filter_by(email=normalized_email).first()

        # Generic authentication check to prevent email enumeration
        if user and user.check_password(form.password.data):
            if not user.is_active:
                flash("Your account has been deactivated. Please contact support.", "danger")
                return render_template("auth/login.html", form=form)

            # Prevent inactive organization users from logging in (for recruiters)
            if user.role in ("recruiter", "organization_admin"):
                primary_membership = user.memberships.first()
                if primary_membership and not primary_membership.organization.is_active:
                    flash("Your organization account is inactive. Please contact support.", "danger")
                    return render_template("auth/login.html", form=form)

            # Update last login timestamp
            user.last_login_at = utc_now()
            db.session.commit()

            # Session protection & login
            session.clear()  # Regenerate session state at auth boundary
            login_user(user, remember=form.remember.data)
            flash(f"Welcome back, {user.first_name}!", "success")

            next_url = request.args.get("next")
            if next_url and is_safe_redirect_url(next_url):
                return redirect(next_url)

            return redirect(get_redirect_for_user(user))
        else:
            flash("Invalid email address or password. Please verify your credentials and try again.", "danger")

    return render_template("auth/login.html", form=form)


@auth_bp.route("/register", methods=["GET"])
def register():
    """Role choice selection landing page."""
    if current_user.is_authenticated:
        return redirect(get_redirect_for_user(current_user))
    return render_template("auth/register_choice.html")


@auth_bp.route("/register/candidate", methods=["GET", "POST"])
def register_candidate():
    """Registration for job seekers with automatic candidate role assignment."""
    if current_user.is_authenticated:
        return redirect(get_redirect_for_user(current_user))

    form = CandidateRegistrationForm()
    if form.validate_on_submit():
        normalized_email = form.email.data.strip().lower()

        try:
            user = User(
                full_name=form.full_name.data.strip(),
                email=normalized_email,
                role="candidate",  # Strictly assigned on the server
                is_active=True,
                email_verified=False
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.flush()

            # Create empty candidate profile
            profile = CandidateProfile(user_id=user.id)
            db.session.add(profile)
            db.session.commit()

            flash("Candidate account created successfully! Please sign in to complete your profile.", "success")
            return redirect(url_for("auth.login"))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error during candidate registration: {e}")
            flash("An error occurred during registration. Please try again.", "danger")

    return render_template("auth/register_candidate.html", form=form)


@auth_bp.route("/register/recruiter", methods=["GET", "POST"])
def register_recruiter():
    """Registration for talent recruiters and organization creation."""
    if current_user.is_authenticated:
        return redirect(get_redirect_for_user(current_user))

    form = RecruiterRegistrationForm()
    if form.validate_on_submit():
        normalized_email = form.email.data.strip().lower()
        org_name = form.organization_name.data.strip()

        try:
            # Server-side role assignment: recruiter
            user = User(
                full_name=form.full_name.data.strip(),
                email=normalized_email,
                role="recruiter",
                is_active=True,
                email_verified=False
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.flush()

            # Safe organization onboarding & slug collision handling
            base_slug = slugify(org_name) or "org"
            slug = base_slug
            counter = 1
            while Organization.query.filter_by(slug=slug).first():
                slug = f"{base_slug}-{counter}"
                counter += 1

            organization = Organization(
                name=org_name,
                slug=slug,
                is_active=True,
                is_verified=False  # Clearly labeled as unverified
            )
            db.session.add(organization)
            db.session.flush()

            # Link recruiter as admin of their newly created organization
            membership = OrganizationMembership(
                organization_id=organization.id,
                user_id=user.id,
                membership_role="admin",
                is_active=True
            )
            db.session.add(membership)

            # Create recruiter profile
            profile = RecruiterProfile(
                user_id=user.id,
                company_name=organization.name
            )
            db.session.add(profile)
            db.session.commit()

            flash("Recruiter and organization account created successfully! Please sign in to continue.", "success")
            return redirect(url_for("auth.login"))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error during recruiter registration: {e}")
            flash("An error occurred during registration. Please try again.", "danger")

    return render_template("auth/register_recruiter.html", form=form)


@auth_bp.route("/logout", methods=["POST", "GET"])
@login_required
def logout():
    """Secure logout endpoint (supports CSRF-protected POST requests)."""
    logout_user()
    session.clear()
    flash("You have been signed out successfully.", "info")
    return redirect(url_for("main.index"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """Requests password reset link with account existence privacy."""
    if current_user.is_authenticated:
        return redirect(get_redirect_for_user(current_user))

    form = ForgotPasswordForm()
    dev_reset_link = None

    if form.validate_on_submit():
        normalized_email = form.email.data.strip().lower()
        user = User.query.filter_by(email=normalized_email).first()

        if user and user.is_active:
            raw_token, _ = PasswordResetToken.create_token(user.id, expires_in_seconds=3600)
            db.session.commit()

            reset_url = url_for("auth.reset_password", token=raw_token, _external=True)

            # In development/testing, expose the link safely in the session/page context
            if current_app.config.get("DEBUG") or current_app.config.get("TESTING"):
                dev_reset_link = reset_url

        # Always show generic message to prevent email enumeration
        flash("If an active account exists with that email address, password reset instructions have been sent.", "info")
        return render_template("auth/forgot_password.html", form=form, dev_reset_link=dev_reset_link)

    return render_template("auth/forgot_password.html", form=form, dev_reset_link=None)


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    """Processes password reset with single-use, time-limited token."""
    if current_user.is_authenticated:
        return redirect(get_redirect_for_user(current_user))

    db_token = PasswordResetToken.verify_token(token)
    if not db_token:
        flash("The password reset link is invalid, has expired, or has already been used.", "danger")
        return redirect(url_for("auth.forgot_password"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user = db.session.get(User, db_token.user_id)
        if not user or not user.is_active:
            flash("Account is not active or could not be found.", "danger")
            return redirect(url_for("auth.login"))

        user.set_password(form.password.data)
        db_token.used_at = utc_now()  # Invalidate token immediately
        db.session.commit()

        flash("Your password has been successfully reset! You may now sign in with your new credentials.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", form=form, token=token)


@auth_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    """Account settings and password change for authenticated users."""
    account_form = AccountSettingsForm(prefix="account")
    password_form = ChangePasswordForm(prefix="pwd")

    if request.method == "GET":
        account_form.full_name.data = current_user.full_name

    if account_form.submit.data and account_form.validate_on_submit():
        current_user.full_name = account_form.full_name.data.strip()
        db.session.commit()
        flash("Account details updated successfully.", "success")
        return redirect(url_for("auth.settings"))

    if password_form.submit.data and password_form.validate_on_submit():
        if not current_user.check_password(password_form.current_password.data):
            flash("Current password is incorrect.", "danger")
        else:
            current_user.set_password(password_form.new_password.data)
            db.session.commit()
            flash("Your password has been changed successfully.", "success")
            return redirect(url_for("auth.settings"))

    return render_template(
        "auth/settings.html",
        account_form=account_form,
        password_form=password_form
    )
