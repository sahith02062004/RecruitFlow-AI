"""
CLI Commands for RecruitFlow AI Administration.
Includes:
- flask create-admin: securely creates the initial platform administrator account
"""
import click
from flask.cli import with_appcontext
from app.core.extensions import db
from app.models.models import User, utc_now


@click.command("create-admin")
@click.option("--email", prompt="Admin Email Address", help="Email of the platform administrator.")
@click.option("--name", prompt="Full Name", help="Full name of the platform administrator.")
@click.password_option(prompt="Admin Password", confirmation_prompt=True, help="Secure password for administrator.")
@with_appcontext
def create_admin_command(email, name, password):
    """Securely creates the initial platform administrator account."""
    normalized_email = email.strip().lower()

    if len(password) < 8:
        click.echo(click.style("Error: Admin password must be at least 8 characters long.", fg="red"))
        return

    existing_user = User.query.filter_by(email=normalized_email).first()
    if existing_user:
        click.echo(click.style(f"Error: A user with email '{normalized_email}' already exists.", fg="red"))
        return

    click.echo(f"Creating Platform Administrator: {name} ({normalized_email})...")
    if not click.confirm("Do you want to proceed with creating this platform administrator?"):
        click.echo("Admin creation cancelled.")
        return

    admin_user = User(
        full_name=name.strip(),
        email=normalized_email,
        role="platform_admin",
        is_active=True,
        email_verified=True,
        created_at=utc_now(),
        updated_at=utc_now()
    )
    admin_user.set_password(password)

    db.session.add(admin_user)
    db.session.commit()

    click.echo(click.style(f"Success: Platform Administrator '{normalized_email}' created successfully!", fg="green"))
