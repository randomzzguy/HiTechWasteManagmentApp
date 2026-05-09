"""add_performance_indexes

Revision ID: c1f01c09750d
Revises: a1b2c3d4e5f6
Create Date: 2026-05-07 09:11:29.064851

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1f01c09750d'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add performance indexes for common query patterns."""
    
    # Users table indexes
    op.create_index('ix_users_role', 'users', ['role'])
    op.create_index('ix_users_is_active', 'users', ['is_active'])
    op.create_index('ix_users_created_at', 'users', ['created_at'])
    
    # Clients table indexes
    op.create_index('ix_clients_industry_vertical', 'clients', ['industry_vertical'])
    op.create_index('ix_clients_created_at', 'clients', ['created_at'])
    
    # Jobs table indexes
    op.create_index('ix_jobs_created_at', 'jobs', ['created_at'])
    op.create_index('ix_jobs_status', 'jobs', ['status'])
    op.create_index('ix_jobs_client_id', 'jobs', ['client_id'])
    
    # Vehicles table indexes
    op.create_index('ix_vehicles_license_plate', 'vehicles', ['license_plate'])
    op.create_index('ix_vehicles_status', 'vehicles', ['status'])
    op.create_index('ix_vehicles_created_at', 'vehicles', ['created_at'])
    
    # ScheduledWasteBatch table indexes
    op.create_index('ix_scheduled_waste_batches_created_at', 'scheduled_waste_batches', ['created_at'])
    op.create_index('ix_scheduled_waste_batches_client_id', 'scheduled_waste_batches', ['client_id'])
    op.create_index('ix_scheduled_waste_batches_status', 'scheduled_waste_batches', ['status'])
    op.create_index('ix_scheduled_waste_batches_sw_code', 'scheduled_waste_batches', ['sw_code'])
    
    # RecyclableRecord table indexes
    op.create_index('ix_recyclable_records_created_at', 'recyclable_records', ['created_at'])
    op.create_index('ix_recyclable_records_client_id', 'recyclable_records', ['client_id'])
    op.create_index('ix_recyclable_records_material_type', 'recyclable_records', ['material_type'])
    
    # DestructionJob table indexes
    op.create_index('ix_destruction_jobs_created_at', 'destruction_jobs', ['created_at'])
    op.create_index('ix_destruction_jobs_status', 'destruction_jobs', ['status'])
    
    # Invoice table indexes
    op.create_index('ix_invoices_created_at', 'invoices', ['created_at'])
    op.create_index('ix_invoices_client_id', 'invoices', ['client_id'])
    op.create_index('ix_invoices_status', 'invoices', ['status'])
    
    # Document table indexes
    op.create_index('ix_documents_created_at', 'documents', ['created_at'])
    op.create_index('ix_documents_doc_type', 'documents', ['doc_type'])
    op.create_index('ix_documents_client_id', 'documents', ['client_id'])
    
    # AgentEvent table indexes
    op.create_index('ix_agent_events_created_at', 'agent_events', ['created_at'])
    op.create_index('ix_agent_events_agent_name', 'agent_events', ['agent_name'])
    op.create_index('ix_agent_events_is_read', 'agent_events', ['is_read'])
    op.create_index('ix_agent_events_severity', 'agent_events', ['severity'])


def downgrade() -> None:
    """Remove performance indexes."""
    
    # Users table indexes
    op.drop_index('ix_users_role', 'users')
    op.drop_index('ix_users_is_active', 'users')
    op.drop_index('ix_users_created_at', 'users')
    
    # Clients table indexes
    op.drop_index('ix_clients_industry_vertical', 'clients')
    op.drop_index('ix_clients_created_at', 'clients')
    
    # Jobs table indexes
    op.drop_index('ix_jobs_created_at', 'jobs')
    op.drop_index('ix_jobs_status', 'jobs')
    op.drop_index('ix_jobs_client_id', 'jobs')
    
    # Vehicles table indexes
    op.drop_index('ix_vehicles_license_plate', 'vehicles')
    op.drop_index('ix_vehicles_status', 'vehicles')
    op.drop_index('ix_vehicles_created_at', 'vehicles')
    
    # ScheduledWasteBatch table indexes
    op.drop_index('ix_scheduled_waste_batches_created_at', 'scheduled_waste_batches')
    op.drop_index('ix_scheduled_waste_batches_client_id', 'scheduled_waste_batches')
    op.drop_index('ix_scheduled_waste_batches_status', 'scheduled_waste_batches')
    op.drop_index('ix_scheduled_waste_batches_sw_code', 'scheduled_waste_batches')
    
    # RecyclableRecord table indexes
    op.drop_index('ix_recyclable_records_created_at', 'recyclable_records')
    op.drop_index('ix_recyclable_records_client_id', 'recyclable_records')
    op.drop_index('ix_recyclable_records_material_type', 'recyclable_records')
    
    # DestructionJob table indexes
    op.drop_index('ix_destruction_jobs_created_at', 'destruction_jobs')
    op.drop_index('ix_destruction_jobs_status', 'destruction_jobs')
    
    # Invoice table indexes
    op.drop_index('ix_invoices_created_at', 'invoices')
    op.drop_index('ix_invoices_client_id', 'invoices')
    op.drop_index('ix_invoices_status', 'invoices')
    
    # Document table indexes
    op.drop_index('ix_documents_created_at', 'documents')
    op.drop_index('ix_documents_doc_type', 'documents')
    op.drop_index('ix_documents_client_id', 'documents')
    
    # AgentEvent table indexes
    op.drop_index('ix_agent_events_created_at', 'agent_events')
    op.drop_index('ix_agent_events_agent_name', 'agent_events')
    op.drop_index('ix_agent_events_is_read', 'agent_events')
    op.drop_index('ix_agent_events_severity', 'agent_events')
