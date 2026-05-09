"""initial_schema

Revision ID: 6038e5e1e9dd
Revises: 
Create Date: 2026-04-22 00:34:14.829230

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '6038e5e1e9dd'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables for Hi-Tech Waste Management platform."""
    # Create UUID extension
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    
    # =============================================================
    # Core Tables
    # =============================================================
    
    # Users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('uuid_generate_v4()')),
        sa.Column('email', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('role', sa.String(50), nullable=False, default='client'),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    
    # Clients table
    op.create_table(
        'clients',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('uuid_generate_v4()')),
        sa.Column('company_name', sa.String(255), nullable=False, index=True),
        sa.Column('industry_vertical', sa.String(100), nullable=True),
        sa.Column('ssm_number', sa.String(50), nullable=True, unique=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('state', sa.String(100), nullable=True),
        sa.Column('pic_name', sa.String(255), nullable=True),
        sa.Column('pic_email', sa.String(255), nullable=True),
        sa.Column('pic_phone', sa.String(50), nullable=True),
        sa.Column('portal_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('contract_start', sa.Date(), nullable=True),
        sa.Column('contract_end', sa.Date(), nullable=True),
        sa.Column('sla_diversion_target', sa.Numeric(5, 2), nullable=True),
        sa.Column('billing_model', sa.String(50), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    
    # Client waste streams table
    op.create_table(
        'client_waste_streams',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('uuid_generate_v4()')),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('waste_type', sa.String(100), nullable=False),
        sa.Column('estimated_kg_per_month', sa.Numeric(12, 2), nullable=True),
        sa.Column('collection_frequency', sa.String(50), nullable=True),
        sa.Column('special_handling_notes', sa.Text(), nullable=True),
    )
    
    # Vehicles table
    op.create_table(
        'vehicles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('uuid_generate_v4()')),
        sa.Column('registration', sa.String(30), nullable=False, unique=True, index=True),
        sa.Column('vehicle_type', sa.String(30), nullable=False),
        sa.Column('make', sa.String(100), nullable=True),
        sa.Column('model', sa.String(100), nullable=True),
        sa.Column('year', sa.Integer(), nullable=True),
        sa.Column('capacity_kg', sa.Numeric(10, 2), nullable=True),
        sa.Column('gps_device_id', sa.String(100), nullable=True),
        sa.Column('assigned_driver_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('last_service_date', sa.Date(), nullable=True),
        sa.Column('next_service_date', sa.Date(), nullable=True, index=True),
        sa.Column('odometer_km', sa.Numeric(12, 2), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, default='available', index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    
    # Jobs table
    op.create_table(
        'jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('uuid_generate_v4()')),
        sa.Column('job_number', sa.String(50), nullable=False, unique=True, index=True),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clients.id', ondelete='RESTRICT'), nullable=False, index=True),
        sa.Column('job_type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(30), nullable=False, default='draft', index=True),
        sa.Column('scheduled_date', sa.Date(), nullable=True),
        sa.Column('scheduled_time_start', sa.Time(), nullable=True),
        sa.Column('collection_address', sa.Text(), nullable=True),
        sa.Column('assigned_vehicle_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('vehicles.id', ondelete='SET NULL'), nullable=True),
        sa.Column('assigned_driver_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('assigned_supervisor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('estimated_weight_kg', sa.Numeric(12, 3), nullable=True),
        sa.Column('actual_weight_kg', sa.Numeric(12, 3), nullable=True),
        sa.Column('disposal_route', sa.String(255), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), onupdate=sa.text('now()')),
    )
    
    # Trips table
    op.create_table(
        'trips',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('uuid_generate_v4()')),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('jobs.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('vehicle_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('vehicles.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('driver_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('start_odometer', sa.Numeric(12, 2), nullable=True),
        sa.Column('end_odometer', sa.Numeric(12, 2), nullable=True),
        sa.Column('distance_km', sa.Numeric(10, 2), nullable=True),
        sa.Column('fuel_litres', sa.Numeric(8, 3), nullable=True),
        sa.Column('departure_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('arrival_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('gps_track', postgresql.JSON(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
    )
    
    # Weighbridge records table
    op.create_table(
        'weighbridge_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), default=sa.text('uuid_generate_v4()')),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('jobs.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clients.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('gross_weight_kg', sa.Numeric(12, 3), nullable=True),
        sa.Column('tare_weight_kg', sa.Numeric(12, 3), nullable=True),
        sa.Column('net_weight_kg', sa.Numeric(12, 3), nullable=True),
        sa.Column('waste_type_breakdown', postgresql.JSON(), nullable=True),
        sa.Column('operator_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id', 'recorded_at'),
    )
    
    # Convert to TimescaleDB hypertable
    op.execute("SELECT create_hypertable('weighbridge_records', 'recorded_at', if_not_exists => TRUE)")
    
    # Scheduled waste batches table
    op.create_table(
        'scheduled_waste_batches',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('uuid_generate_v4()')),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('jobs.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clients.id', ondelete='RESTRICT'), nullable=False, index=True),
        sa.Column('sw_code', sa.String(20), nullable=False, index=True),
        sa.Column('waste_description', sa.String(500), nullable=False),
        sa.Column('quantity_kg', sa.Numeric(12, 3), nullable=False),
        sa.Column('physical_state', sa.String(20), nullable=False, default='solid'),
        sa.Column('container_type', sa.String(100), nullable=True),
        sa.Column('container_count', sa.Integer(), nullable=True),
        sa.Column('storage_start_date', sa.Date(), nullable=False),
        sa.Column('storage_deadline', sa.Date(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, default='in_storage', index=True),
        sa.Column('consignment_note_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    
    # Consignment notes table
    op.create_table(
        'consignment_notes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('uuid_generate_v4()')),
        sa.Column('batch_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('scheduled_waste_batches.id', ondelete='RESTRICT'), nullable=False, unique=True, index=True),
        sa.Column('note_number', sa.String(50), nullable=False, unique=True, index=True),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('cenviro_reference', sa.String(100), nullable=True),
        sa.Column('transport_date', sa.Date(), nullable=True),
        sa.Column('transporter_name', sa.String(255), nullable=True),
        sa.Column('vehicle_registration', sa.String(20), nullable=True),
        sa.Column('processing_facility', sa.String(255), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, default='draft', index=True),
        sa.Column('pdf_path', sa.Text(), nullable=True),
        sa.Column('signed_by_hitech', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('signed_by_client', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
    )
    
    # Recyclable records table
    op.create_table(
        'recyclable_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('uuid_generate_v4()')),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('jobs.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clients.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('material_breakdown', postgresql.JSON(), nullable=False),
        sa.Column('total_recyclable_kg', sa.Numeric(12, 3), nullable=True),
        sa.Column('buyer_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('sale_value_myr', sa.Numeric(12, 2), nullable=True),
        sa.Column('certificate_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    
    # Downstream buyers table
    op.create_table(
        'downstream_buyers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('uuid_generate_v4()')),
        sa.Column('company_name', sa.String(200), nullable=False),
        sa.Column('material_types', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('contact_name', sa.String(150), nullable=True),
        sa.Column('contact_phone', sa.String(30), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('license_number', sa.String(100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True, server_default='true'),
    )
    
    # Destruction jobs table
    op.create_table(
        'destruction_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('uuid_generate_v4()')),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('goods_description', sa.Text(), nullable=False),
        sa.Column('quantity_units', sa.Integer(), nullable=True),
        sa.Column('weight_kg', sa.Numeric(12, 3), nullable=True),
        sa.Column('destruction_method', sa.String(100), nullable=True),
        sa.Column('destruction_date', sa.Date(), nullable=True),
        sa.Column('destruction_location', sa.Text(), nullable=True),
        sa.Column('witness_hitech_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('witness_client_name', sa.String(150), nullable=True),
        sa.Column('witness_client_designation', sa.String(100), nullable=True),
        sa.Column('media_files', postgresql.JSON(), nullable=True),
        sa.Column('certificate_issued', sa.Boolean(), nullable=False, default=False, server_default='false'),
        sa.Column('certificate_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('reason_codes', postgresql.ARRAY(sa.String()), nullable=True),
    )
    
    # BSF batches table
    op.create_table(
        'bsf_batches',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('uuid_generate_v4()')),
        sa.Column('intake_date', sa.Date(), nullable=False),
        sa.Column('source_job_ids', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True),
        sa.Column('food_waste_kg', sa.Numeric(12, 3), nullable=True),
        sa.Column('client_sources', postgresql.JSON(), nullable=True),
        sa.Column('contamination_level', sa.String(20), nullable=True),
        sa.Column('larvae_output_kg', sa.Numeric(12, 3), nullable=True),
        sa.Column('conversion_ratio', sa.Numeric(5, 3), nullable=True),
        sa.Column('livestock_recipient', sa.String(200), nullable=True),
        sa.Column('batch_start', sa.Date(), nullable=True),
        sa.Column('batch_end', sa.Date(), nullable=True),
        sa.Column('status', sa.String(30), nullable=False, default='active'),
    )
    
    # Carbon records table
    op.create_table(
        'carbon_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('uuid_generate_v4()')),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('jobs.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clients.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('calculated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('transport_emissions_kgco2e', sa.Numeric(12, 3), nullable=True),
        sa.Column('landfill_avoidance_kgco2e', sa.Numeric(12, 3), nullable=True),
        sa.Column('recycling_credit_kgco2e', sa.Numeric(12, 3), nullable=True),
        sa.Column('wte_credit_kgco2e', sa.Numeric(12, 3), nullable=True),
        sa.Column('net_carbon_impact_kgco2e', sa.Numeric(12, 3), nullable=True),
        sa.Column('methodology_notes', sa.Text(), nullable=True),
    )
    
    # Certificates table
    op.create_table(
        'certificates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('uuid_generate_v4()')),
        sa.Column('cert_type', sa.String(30), nullable=False, index=True),
        sa.Column('reference_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clients.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('issued_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), index=True),
        sa.Column('issued_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('pdf_path', sa.Text(), nullable=True),
        sa.Column('is_void', sa.Boolean(), nullable=False, default=False, server_default='false'),
    )
    
    # Invoices table
    op.create_table(
        'invoices',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('uuid_generate_v4()')),
        sa.Column('invoice_number', sa.String(50), nullable=False, unique=True, index=True),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clients.id', ondelete='RESTRICT'), nullable=False, index=True),
        sa.Column('job_ids', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True),
        sa.Column('issue_date', sa.Date(), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=True, index=True),
        sa.Column('line_items', postgresql.JSON(), nullable=True),
        sa.Column('subtotal_myr', sa.Numeric(14, 2), nullable=False, default=0, server_default='0.00'),
        sa.Column('tax_myr', sa.Numeric(14, 2), nullable=False, default=0, server_default='0.00'),
        sa.Column('total_myr', sa.Numeric(14, 2), nullable=False, default=0, server_default='0.00'),
        sa.Column('status', sa.String(20), nullable=False, default='unpaid', index=True),
        sa.Column('paid_amount_myr', sa.Numeric(14, 2), nullable=False, default=0, server_default='0.00'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('pdf_path', sa.Text(), nullable=True),
        sa.Column('is_void', sa.Boolean(), nullable=False, default=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), onupdate=sa.text('now()')),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
    )
    
    # Agent events table
    op.create_table(
        'agent_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('uuid_generate_v4()')),
        sa.Column('agent_name', sa.String(100), nullable=False, index=True),
        sa.Column('event_type', sa.String(30), nullable=False, index=True),
        sa.Column('severity', sa.String(20), nullable=False, default='info', index=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('reference_type', sa.String(100), nullable=True),
        sa.Column('reference_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('is_read', sa.Boolean(), nullable=False, default=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), index=True),
    )
    
    # Documents table
    op.create_table(
        'documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('uuid_generate_v4()')),
        sa.Column('title', sa.String(500), nullable=False, index=True),
        sa.Column('doc_type', sa.String(30), nullable=False, index=True),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clients.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('file_path', sa.Text(), nullable=True),
        sa.Column('mime_type', sa.String(100), nullable=True),
        sa.Column('ingested_into_rag', sa.Boolean(), nullable=False, default=False, server_default='false'),
        sa.Column('milvus_collection', sa.String(100), nullable=True),
        sa.Column('uploaded_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), index=True),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('ingestion_error', sa.Text(), nullable=True),
    )
    
    # Recurring job templates table (NEW - replaces in-memory dict)
    op.create_table(
        'recurring_job_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('uuid_generate_v4()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('job_type', sa.String(50), nullable=False),
        sa.Column('collection_address', sa.Text(), nullable=True),
        sa.Column('assigned_vehicle_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('vehicles.id', ondelete='SET NULL'), nullable=True),
        sa.Column('assigned_driver_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('assigned_supervisor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('estimated_weight_kg', sa.Numeric(12, 3), nullable=True),
        sa.Column('disposal_route', sa.String(100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('recurrence_rule', sa.String(255), nullable=False, comment='iCal RRULE string'),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), onupdate=sa.text('now()')),
    )
    
    # Create indexes for performance
    op.create_index('idx_jobs_status_scheduled_date', 'jobs', ['status', 'scheduled_date'])
    op.create_index('idx_jobs_client_id_status', 'jobs', ['client_id', 'status'])
    op.create_index('idx_sw_batches_storage_deadline', 'scheduled_waste_batches', ['storage_deadline'])
    op.create_index('idx_invoices_client_id_status', 'invoices', ['client_id', 'status'])
    op.create_index('idx_carbon_records_client_id', 'carbon_records', ['client_id'])
    
    # =============================================================
    # Operational Field Tables (Compactors, Containers, Labour)
    # =============================================================
    
    # Compaction machines table
    op.create_table(
        'compaction_machines',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('uuid_generate_v4()')),
        sa.Column('machine_code', sa.String(50), nullable=False, unique=True),
        sa.Column('machine_type', sa.String(50), nullable=False),
        sa.Column('location_site', sa.String(255), nullable=True),
        sa.Column('status', sa.String(30), nullable=False, default='operational'),
        sa.Column('serial_number', sa.String(100), nullable=True),
        sa.Column('purchase_date', sa.Date(), nullable=True),
        sa.Column('last_maintenance', sa.Date(), nullable=True),
        sa.Column('next_maintenance', sa.Date(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    
    # Containers table
    op.create_table(
        'containers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('uuid_generate_v4()')),
        sa.Column('container_code', sa.String(50), nullable=False, unique=True),
        sa.Column('container_type', sa.String(50), nullable=False),
        sa.Column('capacity_litres', sa.Numeric(10, 2), nullable=True),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clients.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('location_address', sa.Text(), nullable=True),
        sa.Column('status', sa.String(30), nullable=False, default='in_use'),
        sa.Column('deployment_date', sa.Date(), nullable=True),
        sa.Column('last_emptied', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    
    # Staff profiles table
    op.create_table(
        'staff_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('employee_id', sa.String(50), nullable=True, unique=True),
        sa.Column('department', sa.String(100), nullable=True),
        sa.Column('designation', sa.String(100), nullable=True),
        sa.Column('hire_date', sa.Date(), nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('emergency_contact', sa.String(255), nullable=True),
        sa.Column('license_number', sa.String(100), nullable=True),
        sa.Column('license_expiry', sa.Date(), nullable=True),
        sa.Column('medical_cert_valid', sa.Date(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), onupdate=sa.text('now()')),
    )
    
    # Disruption logs table
    op.create_table(
        'disruption_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('uuid_generate_v4()')),
        sa.Column('disruption_type', sa.String(50), nullable=False),
        sa.Column('severity', sa.String(20), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('reported_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('reported_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('location', sa.String(255), nullable=True),
        sa.Column('affected_area', sa.String(255), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(30), nullable=False, default='open'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    
    # Disruption job impacts table
    op.create_table(
        'disruption_job_impacts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('uuid_generate_v4()')),
        sa.Column('disruption_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('disruption_logs.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('impact_type', sa.String(50), nullable=False),
        sa.Column('delay_minutes', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    
    # Recycler deliveries table
    op.create_table(
        'recycler_deliveries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('uuid_generate_v4()')),
        sa.Column('delivery_date', sa.Date(), nullable=False, index=True),
        sa.Column('buyer_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('vehicle_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('vehicles.id', ondelete='SET NULL'), nullable=True),
        sa.Column('driver_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('material_type', sa.String(50), nullable=False),
        sa.Column('weight_kg', sa.Numeric(12, 3), nullable=False),
        sa.Column('sale_price_myr', sa.Numeric(10, 2), nullable=True),
        sa.Column('total_value_myr', sa.Numeric(12, 2), nullable=True),
        sa.Column('do_number', sa.String(100), nullable=True),
        sa.Column('receipt_reference', sa.String(100), nullable=True),
        sa.Column('status', sa.String(30), nullable=False, default='scheduled'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )


def downgrade() -> None:
    """Drop all tables."""
    tables = [
        'recycler_deliveries',
        'disruption_job_impacts',
        'disruption_logs',
        'staff_profiles',
        'containers',
        'compaction_machines',
        'recurring_job_templates',
        'documents',
        'agent_events',
        'invoices',
        'certificates',
        'carbon_records',
        'bsf_batches',
        'destruction_jobs',
        'downstream_buyers',
        'recyclable_records',
        'consignment_notes',
        'scheduled_waste_batches',
        'weighbridge_records',
        'trips',
        'jobs',
        'vehicles',
        'client_waste_streams',
        'clients',
        'users',
    ]
    
    for table in tables:
        op.drop_table(table, if_exists=True)
    
    op.execute('DROP EXTENSION IF EXISTS "uuid-ossp"')
