"""add_document_file_size_ingestion_error

Revision ID: a1b2c3d4e5f6
Revises: 6038e5e1e9dd
Create Date: 2026-04-22 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '6038e5e1e9dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add file_size_bytes and ingestion_error columns to documents table."""
    op.add_column('documents', sa.Column('file_size_bytes', sa.BigInteger(), nullable=True))
    op.add_column('documents', sa.Column('ingestion_error', sa.Text(), nullable=True))


def downgrade() -> None:
    """Drop file_size_bytes and ingestion_error columns from documents table."""
    op.drop_column('documents', 'ingestion_error')
    op.drop_column('documents', 'file_size_bytes')
