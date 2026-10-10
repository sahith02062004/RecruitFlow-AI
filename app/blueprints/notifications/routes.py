"""
Notifications Blueprint Routes for RecruitFlow AI (Phase 6).
Handles:
- In-app notification center for authenticated users
- Marking notifications as read
- Batch mark-all-as-read
- User data isolation (users cannot access or modify others' notifications)
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for, abort
from flask_login import current_user, login_required
from app.services.notification_service import (
    get_user_notifications,
    mark_notification_as_read,
    mark_all_notifications_as_read
)

notifications_bp = Blueprint("notifications", __name__, url_prefix="/notifications")


@notifications_bp.route("/")
@login_required
def index():
    """Renders the notification center for the current user."""
    unread_only = request.args.get("unread", "").lower() in ("1", "true")
    notifications = get_user_notifications(current_user.id, unread_only=unread_only)
    return render_template(
        "notifications/index.html",
        notifications=notifications,
        unread_only=unread_only
    )


@notifications_bp.route("/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_read(notification_id):
    """Marks a single notification as read."""
    success = mark_notification_as_read(notification_id, current_user.id)
    if not success:
        abort(404)

    redirect_to = request.form.get("redirect_to")
    if redirect_to and redirect_to.startswith("/"):
        return redirect(redirect_to)
    return redirect(url_for("notifications.index"))


@notifications_bp.route("/read-all", methods=["POST"])
@login_required
def read_all():
    """Marks all unread notifications as read for current user."""
    count = mark_all_notifications_as_read(current_user.id)
    flash(f"Marked {count} notifications as read.", "info")
    return redirect(url_for("notifications.index"))
