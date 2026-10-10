"""
Application Configuration Module for RecruitFlow AI.
Supports Development, Testing, and Production configurations with MySQL 8 primary
and SQLite isolated test suite support.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


class Config:
    """Base application configuration."""
    SECRET_KEY = os.getenv("SECRET_KEY", "recruitflow-default-secret-key-change-me")
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600
    
    # SQLAlchemy default settings
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

    # Uploads
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", str(BASE_DIR / "uploads"))
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 16 * 1024 * 1024))  # 16 MB max
    ALLOWED_EXTENSIONS = {"pdf", "docx", "doc", "txt"}

    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", str(BASE_DIR / "logs" / "recruitflow.log"))


class DevelopmentConfig(Config):
    """Development environment configuration."""
    DEBUG = True
    TESTING = False
    
    # Database connection logic
    use_sqlite_fallback = os.getenv("USE_SQLITE_DEV_FALLBACK", "True").lower() in ("true", "1", "yes")
    db_user = os.getenv("DB_USER", "recruitflow_user")
    db_pass = os.getenv("DB_PASSWORD", "recruitflow_password")
    db_host = os.getenv("DB_HOST", "127.0.0.1")
    db_port = os.getenv("DB_PORT", "3306")
    db_name = os.getenv("DB_NAME", "recruitflow_db")
    
    # Allow explicit override via DATABASE_URL
    explicit_db_url = os.getenv("DATABASE_URL")
    if explicit_db_url:
        SQLALCHEMY_DATABASE_URI = explicit_db_url
    elif use_sqlite_fallback:
        # Development fallback SQLite if local MySQL 8 server is not provisioned
        sqlite_file = os.getenv("SQLITE_DB_PATH", "recruitflow_dev.db")
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{BASE_DIR / sqlite_file}"
    else:
        SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}?charset=utf8mb4"


class TestingConfig(Config):
    """Testing environment configuration using SQLite in-memory database."""
    TESTING = True
    DEBUG = False
    WTF_CSRF_ENABLED = False  # Simplify automated form submissions in tests
    SQLALCHEMY_DATABASE_URI = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")
    SQLALCHEMY_ENGINE_OPTIONS = {}  # In-memory SQLite needs clean connection defaults


class ProductionConfig(Config):
    """Production configuration requiring production MySQL 8."""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    db_user = os.getenv("DB_USER")
    db_pass = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST", "127.0.0.1")
    db_port = os.getenv("DB_PORT", "3306")
    db_name = os.getenv("DB_NAME", "recruitflow_prod")
    
    explicit_db_url = os.getenv("DATABASE_URL")
    if explicit_db_url:
        SQLALCHEMY_DATABASE_URI = explicit_db_url
    else:
        SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}?charset=utf8mb4"


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
