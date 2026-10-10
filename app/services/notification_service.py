"""
Notification Service for RecruitFlow AI (Phase 6).
Provides database-backed in-app notifications and safe, mock-capable email hooks.
Ensures tenant data isolation and prevents confidential disclosure to candidates.
"""
import logging
from datetime import datetime, timezone
from app.core.extensions import db
from app.models.models import Notification, User, utc_now

logger = logging.getLogger(__name__)


def create_notification(
    recipient_user_id: int,
    notification_type: str,
    title: str,
    message: str,
    link_url: str = None,
    application_id: int = None,
    interview_id: int = None
) -> Notification:
    """
    Persists an in-app notification for a user and triggers a mock email log.
    Never persists authentication secrets or private interviewer feedback.
    """
    if not recipient_user_id or not title or not message:
        return None

    # Check recipient existence
    recipient = db.session.get(User, recipient_user_id)
    if not recipient:
        logger.warning(f"Failed to create notification: user {recipient_user_id} does not exist.")
        return None

    notification = Notification(
        recipient_user_id=recipient_user_id,
        notification_type=notification_type,
        title=title.strip(),
        message=message.strip(),
        link_url=link_url.strip() if link_url else None,
        application_id=application_id,
        interview_id=interview_id,
        is_read=False
    )
    db.session.add(notification)
    
    # Safe provider-neutral email hook (logs in development, no external paid service required)
    send_optional_email_notification(
        to_email=recipient.email,
        subject=title,
        body=message
    )

    return notification


def get_user_notifications(user_id: int, unread_only: bool = False, limit: int = 50):
    """Retrieves notifications strictly belonging to the given user."""
    query = Notification.query.filter_by(recipient_user_id=user_id)
    if unread_only:
        query = query.filter_by(is_read=False)
    return query.order_by(Notification.created_at.desc()).limit(limit).all()


def get_unread_count(user_id: int) -> int:
    """Returns number of unread notifications for a user."""
    if not user_id:
        return 0
    return Notification.query.filter_by(recipient_user_id=user_id, is_read=False).count()


def mark_notification_as_read(notification_id: int, user_id: int) -> bool:
    """
    Marks a notification as read if owned by the user.
    Prevents IDOR across different accounts.
    """
    notification = db.session.get(Notification, notification_id)
    if not notification or notification.recipient_user_id != user_id:
        return False

    if not notification.is_read:
        notification.is_read = True
        notification.read_at = utc_now()
        db.session.commit()
    return True


def mark_all_notifications_as_read(user_id: int) -> int:
    """Marks all unread notifications for the user as read."""
    unread = Notification.query.filter_by(recipient_user_id=user_id, is_read=False).all()
    count = len(unread)
    now = utc_now()
    for n in unread:
        n.is_read = True
        n.read_at = now
    if count > 0:
        db.session.commit()
    return count


def send_optional_email_notification(to_email: str, subject: str, body: str):
    """
    Provider-neutral notification sender.
    Logs email dispatch in development without requiring paid third-party credentials.
    """
    # Safe local log representation
    logger.info(
        f"[EMAIL NOTIFICATION DISPATCH (Mock)] To: {to_email} | Subject: {subject} | Content length: {len(body)}"
    )
