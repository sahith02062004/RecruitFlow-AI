"""
Pytest Fixtures for RecruitFlow AI Phase 2 Test Suite.
Configures isolated in-memory SQLite database, mock sessions, CSRF test configurations,
and pre-configured role test fixtures.
"""
import pytest
from app import create_app
from app.core.extensions import db
from app.models.models import (
    User,
    Organization,
    OrganizationMembership,
    CandidateProfile,
    RecruiterProfile
)


@pytest.fixture(scope="session")
def app():
    """Create and configure a clean testing app instance."""
    test_app = create_app("testing")
    with test_app.app_context():
        db.create_all()
        yield test_app
        db.drop_all()


@pytest.fixture(scope="function")
def client(app):
    """Test client for issuing requests."""
    return app.test_client()


@pytest.fixture(scope="function")
def runner(app):
    """CLI runner for testing commands."""
    return app.test_cli_runner()


@pytest.fixture(scope="function")
def session(app):
    """Provides a transactional database session rolled back after every test."""
    with app.app_context():
        db.session.rollback()
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()
        yield db.session
        db.session.rollback()


@pytest.fixture
def candidate_user(session):
    """Creates a test candidate user and profile."""
    user = User(
        full_name="Alex Candidate",
        email="alex.candidate@example.com",
        role="candidate",
        is_active=True,
        email_verified=True
    )
    user.set_password("CandidateSecret123!")
    session.add(user)
    session.flush()

    profile = CandidateProfile(
        user_id=user.id,
        headline="Full Stack Engineer",
        skills="Python, Flask, JavaScript"
    )
    session.add(profile)
    session.commit()
    return user


@pytest.fixture
def recruiter_user(session):
    """Creates a test recruiter user, organization, and membership."""
    user = User(
        full_name="Morgan Recruiter",
        email="morgan.recruiter@acme.com",
        role="recruiter",
        is_active=True,
        email_verified=True
    )
    user.set_password("RecruiterSecret123!")
    session.add(user)
    session.flush()

    org = Organization(
        name="Acme Corp",
        slug="acme-corp",
        is_active=True,
        is_verified=True
    )
    session.add(org)
    session.flush()

    membership = OrganizationMembership(
        organization_id=org.id,
        user_id=user.id,
        membership_role="admin",
        is_active=True
    )
    session.add(membership)

    profile = RecruiterProfile(
        user_id=user.id,
        company_name="Acme Corp",
        job_title="Senior Talent Acquisition"
    )
    session.add(profile)
    session.commit()
    return user


@pytest.fixture
def platform_admin_user(session):
    """Creates a platform administrator user."""
    user = User(
        full_name="Root Admin",
        email="admin@recruitflow.ai",
        role="platform_admin",
        is_active=True,
        email_verified=True
    )
    user.set_password("AdminMasterKey123!")
    session.add(user)
    session.commit()
    return user
