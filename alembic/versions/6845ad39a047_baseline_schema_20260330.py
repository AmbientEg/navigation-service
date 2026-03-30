"""baseline_schema_20260330

Revision ID: 6845ad39a047
Revises: 
Create Date: 2026-03-30 15:14:17.003311

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6845ad39a047'
down_revision: Union[str, Sequence[str], None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
