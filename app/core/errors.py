"""
Centralized Error Handlers and Custom Exceptions.
Provides unified JSON error responses for API routes and branded error pages for HTML views.
"""
import logging
from flask import render_template, request, jsonify

logger = logging.getLogger(__name__)


def register_error_handlers(app):
    """Register custom error pages and API error payloads."""

    @app.errorhandler(400)
    def bad_request(error):
        if request.path.startswith("/api/") or request.is_json:
            return jsonify({
                "status": "error",
                "code": 400,
                "message": "Bad Request",
                "details": str(error)
            }), 400
        return render_template("errors/400.html", error=error), 400

    @app.errorhandler(403)
    def forbidden(error):
        if request.path.startswith("/api/") or request.is_json:
            return jsonify({
                "status": "error",
                "code": 403,
                "message": "Forbidden. You do not have permission to perform this action.",
                "details": str(error)
            }), 403
        return render_template("errors/403.html", error=error), 403

    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith("/api/") or request.is_json:
            return jsonify({
                "status": "error",
                "code": 404,
                "message": "Resource Not Found",
                "details": str(error)
            }), 404
        return render_template("errors/404.html", error=error), 404

    @app.errorhandler(500)
    def internal_server_error(error):
        logger.error(f"Internal server error occurred: {error}", exc_info=True)
        if request.path.startswith("/api/") or request.is_json:
            return jsonify({
                "status": "error",
                "code": 500,
                "message": "An internal server error occurred.",
            }), 500
        return render_template("errors/500.html", error=error), 500
