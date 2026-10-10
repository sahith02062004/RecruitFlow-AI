"""
Production WSGI Entry Point for RecruitFlow AI.
Usage:
    gunicorn --workers 4 --bind 0.0.0.0:5000 wsgi:application
"""
import os
from app import create_app

# Set production environment default
environment = os.getenv("FLASK_ENV", "production")
application = create_app(environment)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    application.run(host="0.0.0.0", port=port)
