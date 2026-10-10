"""
Administration Blueprint Routes for RecruitFlow AI.
Protected by platform_admin_required decorator.
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for, abort
from app.core.security import platform_admin_required
from app.core.extensions import db
from app.models.models import User, Organization

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/")
@platform_admin_required
def index():
    """Platform administration dashboard."""
    users = User.query.order_by(User.created_at.desc()).all()
    organizations = Organization.query.order_by(Organization.created_at.desc()).all()
    return render_template("admin/index.html", users=users, organizations=organizations)


@admin_bp.route("/user/<int:user_id>/toggle-status", methods=["POST"])
@platform_admin_required
def toggle_user_status(user_id):
    """Deactivates or activates a user account."""
    user = db.session.get(User, user_id)
    if not user:
        abort(404)

    user.is_active = not user.is_active
    db.session.commit()
    status_label = "activated" if user.is_active else "deactivated"
    flash(f"User {user.email} has been {status_label}.", "info")
    return redirect(url_for("admin.index"))
