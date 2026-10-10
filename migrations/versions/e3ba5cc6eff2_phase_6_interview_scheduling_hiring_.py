"""Phase 6 interview scheduling hiring pipeline notifications schema

Revision ID: e3ba5cc6eff2
Revises: 5973b62681c5
Create Date: 2026-10-09 22:47:26.225414

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e3ba5cc6eff2'
down_revision = '5973b62681c5'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    interview_cols = [c['name'] for c in inspector.get_columns('interviews')]

    # 1. Alter interviews table to add Phase 6 metadata
    with op.batch_alter_table('interviews', schema=None) as batch_op:
        if 'job_id' not in interview_cols:
            batch_op.add_column(sa.Column('job_id', sa.Integer(), nullable=True))
        if 'round_name' not in interview_cols:
            batch_op.add_column(sa.Column('round_name', sa.String(length=64), nullable=False, server_default='Initial Screening'))
        if 'end_time' not in interview_cols:
            batch_op.add_column(sa.Column('end_time', sa.DateTime(timezone=True), nullable=True))
        if 'timezone' not in interview_cols:
            batch_op.add_column(sa.Column('timezone', sa.String(length=64), nullable=False, server_default='UTC'))
        if 'location' not in interview_cols:
            batch_op.add_column(sa.Column('location', sa.String(length=255), nullable=True))
        if 'instructions' not in interview_cols:
            batch_op.add_column(sa.Column('instructions', sa.Text(), nullable=True))
        if 'cancellation_reason' not in interview_cols:
            batch_op.add_column(sa.Column('cancellation_reason', sa.Text(), nullable=True))
        if 'created_by_user_id' not in interview_cols:
            batch_op.add_column(sa.Column('created_by_user_id', sa.Integer(), nullable=True))
        if 'updated_at' not in interview_cols:
            batch_op.add_column(sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')))
        batch_op.alter_column('interview_type',
               existing_type=sa.VARCHAR(length=32),
               nullable=False,
               server_default='online')
        batch_op.alter_column('status',
               existing_type=sa.VARCHAR(length=32),
               nullable=False,
               server_default='scheduled')
        batch_op.create_index(batch_op.f('ix_interviews_application_id'), ['application_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_interviews_job_id'), ['job_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_interviews_scheduled_at'), ['scheduled_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_interviews_status'), ['status'], unique=False)
        batch_op.create_foreign_key('fk_interviews_created_by_user', 'users', ['created_by_user_id'], ['id'], ondelete='SET NULL')
        batch_op.create_foreign_key('fk_interviews_job', 'jobs', ['job_id'], ['id'], ondelete='CASCADE')

    # 2. Create interview_assignments table if not existing
    if 'interview_assignments' not in tables:
        op.create_table(
            'interview_assignments',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('interview_id', sa.Integer(), nullable=False),
            sa.Column('interviewer_user_id', sa.Integer(), nullable=False),
            sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
            sa.ForeignKeyConstraint(['interview_id'], ['interviews.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['interviewer_user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('interview_id', 'interviewer_user_id', name='uq_interview_interviewer_assignment')
        )
        op.create_index('ix_interview_assignments_interview_id', 'interview_assignments', ['interview_id'], unique=False)
        op.create_index('ix_interview_assignments_interviewer_user_id', 'interview_assignments', ['interviewer_user_id'], unique=False)

    # 3. Create interview_feedback table if not existing
    if 'interview_feedback' not in tables:
        op.create_table(
            'interview_feedback',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('interview_id', sa.Integer(), nullable=False),
            sa.Column('interviewer_user_id', sa.Integer(), nullable=False),
            sa.Column('technical_rating', sa.Integer(), nullable=True),
            sa.Column('problem_solving_rating', sa.Integer(), nullable=True),
            sa.Column('communication_rating', sa.Integer(), nullable=True),
            sa.Column('role_relevant_rating', sa.Integer(), nullable=True),
            sa.Column('overall_score', sa.Float(), nullable=True),
            sa.Column('strengths', sa.Text(), nullable=True),
            sa.Column('areas_for_improvement', sa.Text(), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('overall_recommendation', sa.String(length=32), nullable=False, server_default='neutral'),
            sa.Column('is_candidate_facing', sa.Boolean(), nullable=False, server_default=sa.text('0')),
            sa.Column('candidate_feedback', sa.Text(), nullable=True),
            sa.Column('status', sa.String(length=16), nullable=False, server_default='submitted'),
            sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
            sa.ForeignKeyConstraint(['interview_id'], ['interviews.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['interviewer_user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('interview_id', 'interviewer_user_id', name='uq_interview_user_feedback')
        )
        op.create_index('ix_interview_feedback_interview_id', 'interview_feedback', ['interview_id'], unique=False)
        op.create_index('ix_interview_feedback_interviewer_user_id', 'interview_feedback', ['interviewer_user_id'], unique=False)

    # 4. Create application_stage_histories table if not existing
    if 'application_stage_histories' not in tables:
        op.create_table(
            'application_stage_histories',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('application_id', sa.Integer(), nullable=False),
            sa.Column('previous_stage', sa.String(length=32), nullable=True),
            sa.Column('new_stage', sa.String(length=32), nullable=False),
            sa.Column('changed_by_user_id', sa.Integer(), nullable=True),
            sa.Column('reason', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
            sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['changed_by_user_id'], ['users.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_application_stage_histories_application_id', 'application_stage_histories', ['application_id'], unique=False)

    # 5. Create notifications table if not existing
    if 'notifications' not in tables:
        op.create_table(
            'notifications',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('recipient_user_id', sa.Integer(), nullable=False),
            sa.Column('notification_type', sa.String(length=64), nullable=False),
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('message', sa.Text(), nullable=False),
            sa.Column('link_url', sa.String(length=255), nullable=True),
            sa.Column('application_id', sa.Integer(), nullable=True),
            sa.Column('interview_id', sa.Integer(), nullable=True),
            sa.Column('is_read', sa.Boolean(), nullable=False, server_default=sa.text('0')),
            sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
            sa.ForeignKeyConstraint(['recipient_user_id'], ['users.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['interview_id'], ['interviews.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_notifications_recipient_user_id', 'notifications', ['recipient_user_id'], unique=False)
        op.create_index('ix_notifications_notification_type', 'notifications', ['notification_type'], unique=False)
        op.create_index('ix_notifications_is_read', 'notifications', ['is_read'], unique=False)
        op.create_index('ix_notifications_created_at', 'notifications', ['created_at'], unique=False)


def downgrade():
    op.drop_table('notifications')
    op.drop_table('application_stage_histories')
    op.drop_table('interview_feedback')
    op.drop_table('interview_assignments')

    with op.batch_alter_table('interviews', schema=None) as batch_op:
        batch_op.drop_constraint('fk_interviews_job', type_='foreignkey')
        batch_op.drop_constraint('fk_interviews_created_by_user', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_interviews_status'))
        batch_op.drop_index(batch_op.f('ix_interviews_scheduled_at'))
        batch_op.drop_index(batch_op.f('ix_interviews_job_id'))
        batch_op.drop_index(batch_op.f('ix_interviews_application_id'))
        batch_op.alter_column('status',
               existing_type=sa.VARCHAR(length=32),
               nullable=True)
        batch_op.alter_column('interview_type',
               existing_type=sa.VARCHAR(length=32),
               nullable=True)
        batch_op.drop_column('updated_at')
        batch_op.drop_column('created_by_user_id')
        batch_op.drop_column('cancellation_reason')
        batch_op.drop_column('instructions')
        batch_op.drop_column('location')
        batch_op.drop_column('timezone')
        batch_op.drop_column('end_time')
        batch_op.drop_column('round_name')
        batch_op.drop_column('job_id')
