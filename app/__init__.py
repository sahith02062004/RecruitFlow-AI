"""
RecruitFlow AI Application Factory.
Configures Flask, extensions, blueprints, error handlers, and database lifecycle.
"""
import os
from flask import Flask
from app.config.config import config_by_name
from app.core.extensions import db, migrate, login_manager, csrf
from app.core.logging import setup_logging
from app.core.errors import register_error_handlers


def create_app(config_name=None):
    """Application factory function."""
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development")

    app = Flask(__name__)
    config_class = config_by_name.get(config_name, config_by_name["default"])
    app.config.from_object(config_class)

    # Setup Logging
    setup_logging(app)

    # Initialize Extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Register Error Handlers
    register_error_handlers(app)

    # Register CLI Commands
    from app.core.commands import create_admin_command
    app.cli.add_command(create_admin_command)

    # Register Blueprints
    from app.blueprints.main import main_bp
    from app.blueprints.auth import auth_bp
    from app.blueprints.candidates import candidates_bp
    from app.blueprints.recruiters import recruiters_bp
    from app.blueprints.jobs import jobs_bp
    from app.blueprints.applications import applications_bp
    from app.blueprints.resumes import resumes_bp
    from app.blueprints.matching import matching_bp
    from app.blueprints.interviews import interviews_bp
    from app.blueprints.reports import reports_bp
    from app.blueprints.admin import admin_bp
    from app.blueprints.notifications import notifications_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(candidates_bp)
    app.register_blueprint(recruiters_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(applications_bp)
    app.register_blueprint(resumes_bp)
    app.register_blueprint(matching_bp)
    app.register_blueprint(interviews_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(notifications_bp)

    @app.context_processor
    def inject_notifications():
        from flask_login import current_user
        from app.services.notification_service import get_unread_count
        if current_user.is_authenticated:
            try:
                return {"unread_notifications_count": get_unread_count(current_user.id)}
            except Exception:
                return {"unread_notifications_count": 0}
        return {"unread_notifications_count": 0}

    # Ensure Uploads and Logs directory exist
    upload_folder = app.config.get("UPLOAD_FOLDER")
    if upload_folder:
        os.makedirs(upload_folder, exist_ok=True)

    # Create tables automatically for SQLite development/testing unless migrations are running
    with app.app_context():
        if not os.getenv("FLASK_SKIP_CREATE_ALL"):
            if "sqlite" in app.config.get("SQLALCHEMY_DATABASE_URI", ""):
                db.create_all()

    return app
