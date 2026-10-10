"""Phase 7 ATS Resume Analyses and Rejection Schema

Revision ID: c8d7e6f5a4b3
Revises: e3ba5cc6eff2
Create Date: 2026-10-09 23:12:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c8d7e6f5a4b3'
down_revision = 'e3ba5cc6eff2'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # 1. Add rejection reason fields to applications if not present
    if 'applications' in tables:
        app_cols = [c['name'] for c in inspector.get_columns('applications')]
        with op.batch_alter_table('applications', schema=None) as batch_op:
            if 'rejection_reason_code' not in app_cols:
                batch_op.add_column(sa.Column('rejection_reason_code', sa.String(length=64), nullable=True))
            if 'rejection_reason_text' not in app_cols:
                batch_op.add_column(sa.Column('rejection_reason_text', sa.Text(), nullable=True))
            if 'rejection_feedback_published' not in app_cols:
                batch_op.add_column(sa.Column('rejection_feedback_published', sa.Boolean(), nullable=False, server_default=sa.text('0')))

    # 2. Create resume_analyses table if not exists
    if 'resume_analyses' not in tables:
        op.create_table(
            'resume_analyses',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('resume_id', sa.Integer(), nullable=False),
            sa.Column('candidate_id', sa.Integer(), nullable=True),
            sa.Column('candidate_user_id', sa.Integer(), nullable=False),
            sa.Column('job_id', sa.Integer(), nullable=True),
            sa.Column('resume_quality_score', sa.Float(), nullable=True),
            sa.Column('job_match_score', sa.Float(), nullable=True),
            sa.Column('status', sa.String(length=32), nullable=False, server_default='completed'),
            sa.Column('analyzer_version', sa.String(length=32), nullable=False, server_default='1.0.0'),
            sa.Column('category_scores', sa.Text(), nullable=False),
            sa.Column('category_weights', sa.Text(), nullable=False),
            sa.Column('positive_findings', sa.Text(), nullable=True),
            sa.Column('detected_issues', sa.Text(), nullable=True),
            sa.Column('recommendations', sa.Text(), nullable=True),
            sa.Column('checklist_state', sa.Text(), nullable=True),
            sa.Column('parsing_warnings', sa.Text(), nullable=True),
            sa.Column('input_hash', sa.String(length=64), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
            sa.ForeignKeyConstraint(['candidate_id'], ['candidate_profiles.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['candidate_user_id'], ['users.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['resume_id'], ['resumes.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('resume_analyses', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_resume_analyses_candidate_id'), ['candidate_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_resume_analyses_candidate_user_id'), ['candidate_user_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_resume_analyses_input_hash'), ['input_hash'], unique=False)
            batch_op.create_index(batch_op.f('ix_resume_analyses_job_id'), ['job_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_resume_analyses_resume_id'), ['resume_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_resume_analyses_status'), ['status'], unique=False)


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'resume_analyses' in tables:
        op.drop_table('resume_analyses')

    if 'applications' in tables:
        app_cols = [c['name'] for c in inspector.get_columns('applications')]
        with op.batch_alter_table('applications', schema=None) as batch_op:
            if 'rejection_feedback_published' in app_cols:
                batch_op.drop_column('rejection_feedback_published')
            if 'rejection_reason_text' in app_cols:
                batch_op.drop_column('rejection_reason_text')
            if 'rejection_reason_code' in app_cols:
                batch_op.drop_column('rejection_reason_code')
