"""
Role-Based Access Control and Security Decorators for RecruitFlow AI.
Provides reusable decorators:
- role_required(*roles)
- candidate_required
- recruiter_required
- org_admin_required
- platform_admin_required
- org_membership_required
"""
from functools import wraps
from flask import abort, flash, redirect, url_for, request
from flask_login import current_user
from app.models.models import OrganizationMembership


def role_required(*allowed_roles):
    """
    Ensures the authenticated user has one of the specified global roles.
    If not authenticated, Flask-Login redirects to login.
    If authenticated but role not permitted, returns HTTP 403 Forbidden.
    """
    def decorator(fn):
        @wraps(fn)
        def decorated_view(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login", next=request.path))
            
            if not current_user.is_active:
                flash("Your account has been deactivated. Please contact support.", "danger")
                return redirect(url_for("auth.logout"))

            if current_user.role not in allowed_roles:
                abort(403)

            return fn(*args, **kwargs)
        return decorated_view
    return decorator


def candidate_required(fn):
    """Decorator ensuring current user is an active candidate."""
    return role_required("candidate")(fn)


def recruiter_required(fn):
    """Decorator ensuring current user is a recruiter, organization_admin, or platform_admin."""
    return role_required("recruiter", "organization_admin", "platform_admin")(fn)


def org_admin_required(fn):
    """Decorator ensuring current user is an organization_admin or platform_admin."""
    return role_required("organization_admin", "platform_admin")(fn)


def platform_admin_required(fn):
    """Decorator ensuring current user has the platform_admin role."""
    return role_required("platform_admin")(fn)


def org_membership_required(membership_roles=None):
    """
    Validates that current_user has an active membership in the target organization.
    Checks org_id from kwargs ('org_id' or 'organization_id') or returns 403.
    """
    def decorator(fn):
        @wraps(fn)
        def decorated_view(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login", next=request.path))

            if current_user.role == "platform_admin":
                # Platform admins have global administrative bypass
                return fn(*args, **kwargs)

            org_id = kwargs.get("org_id") or kwargs.get("organization_id")
            if not org_id:
                abort(400)

            membership = OrganizationMembership.query.filter_by(
                user_id=current_user.id,
                organization_id=org_id,
                is_active=True
            ).first()

            if not membership or not membership.organization.is_active:
                abort(403)

            if membership_roles and membership.membership_role not in membership_roles:
                abort(403)

            return fn(*args, **kwargs)
        return decorated_view
    return decorator
