"""Compatibility stub for pre-existing DB revision marker.

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-03-30 15:18:00

"""
from typing import Sequence, Union


revision: str = "001_initial_schema"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op: existing databases may already be stamped with this revision id."""
    pass


def downgrade() -> None:
    """No-op compatibility revision."""
    pass
