"""phase2 compliance and integrations

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-05 02:50:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Update organization_settings
    with op.batch_alter_table('organization_settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('fbr_pos_id', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('fbr_api_token', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('fbr_base_url', sa.String(length=255), nullable=True))

    # 2. Update credit_notes
    with op.batch_alter_table('credit_notes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('fbr_invoice_number', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('fbr_qr_data', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('fbr_submission_date', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('fbr_environment', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('fbr_provider', sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column('fbr_is_simulated', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('correlation_id', sa.String(length=50), nullable=True))
        batch_op.create_index(batch_op.f('ix_credit_notes_fbr_invoice_number'), ['fbr_invoice_number'], unique=False)
        batch_op.create_index(batch_op.f('ix_credit_notes_correlation_id'), ['correlation_id'], unique=False)

    # 3. Update debit_notes
    with op.batch_alter_table('debit_notes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('fbr_invoice_number', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('fbr_qr_data', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('fbr_submission_date', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('fbr_environment', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('fbr_provider', sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column('fbr_is_simulated', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('correlation_id', sa.String(length=50), nullable=True))
        batch_op.create_index(batch_op.f('ix_debit_notes_fbr_invoice_number'), ['fbr_invoice_number'], unique=False)
        batch_op.create_index(batch_op.f('ix_debit_notes_correlation_id'), ['correlation_id'], unique=False)

    # 4. Update invoice_submission_jobs
    with op.batch_alter_table('invoice_submission_jobs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('batch_job_id', sa.String(length=36), nullable=True))
        batch_op.create_index(batch_op.f('ix_invoice_submission_jobs_batch_job_id'), ['batch_job_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('invoice_submission_jobs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_invoice_submission_jobs_batch_job_id'))
        batch_op.drop_column('batch_job_id')

    with op.batch_alter_table('debit_notes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_debit_notes_correlation_id'))
        batch_op.drop_index(batch_op.f('ix_debit_notes_fbr_invoice_number'))
        batch_op.drop_column('correlation_id')
        batch_op.drop_column('fbr_is_simulated')
        batch_op.drop_column('fbr_provider')
        batch_op.drop_column('fbr_environment')
        batch_op.drop_column('fbr_submission_date')
        batch_op.drop_column('fbr_qr_data')
        batch_op.drop_column('fbr_invoice_number')

    with op.batch_alter_table('credit_notes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_credit_notes_correlation_id'))
        batch_op.drop_index(batch_op.f('ix_credit_notes_fbr_invoice_number'))
        batch_op.drop_column('correlation_id')
        batch_op.drop_column('fbr_is_simulated')
        batch_op.drop_column('fbr_provider')
        batch_op.drop_column('fbr_environment')
        batch_op.drop_column('fbr_submission_date')
        batch_op.drop_column('fbr_qr_data')
        batch_op.drop_column('fbr_invoice_number')

    with op.batch_alter_table('organization_settings', schema=None) as batch_op:
        batch_op.drop_column('fbr_base_url')
        batch_op.drop_column('fbr_api_token')
        batch_op.drop_column('fbr_pos_id')
