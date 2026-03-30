"""graph_versioning_managed

Revision ID: 7c24d182ba01
Revises: 6845ad39a047
Create Date: 2026-03-30 15:21:42.857801

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c24d182ba01'
down_revision: Union[str, Sequence[str], None] = '6845ad39a047'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS navigation_graph_versions (
            id UUID PRIMARY KEY,
            building_id UUID NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
            version_number INTEGER NOT NULL DEFAULT 1,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_navigation_graph_versions_building_id
            ON navigation_graph_versions (building_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_navigation_graph_versions_building_active
            ON navigation_graph_versions (building_id, is_active);
        """
    )

    op.execute("ALTER TABLE routing_nodes ADD COLUMN IF NOT EXISTS graph_version_id UUID;")
    op.execute("ALTER TABLE routing_edges ADD COLUMN IF NOT EXISTS graph_version_id UUID;")

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'fk_routing_nodes_graph_version_id'
            ) THEN
                ALTER TABLE routing_nodes
                ADD CONSTRAINT fk_routing_nodes_graph_version_id
                FOREIGN KEY (graph_version_id)
                REFERENCES navigation_graph_versions(id)
                ON DELETE CASCADE;
            END IF;
        END
        $$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'fk_routing_edges_graph_version_id'
            ) THEN
                ALTER TABLE routing_edges
                ADD CONSTRAINT fk_routing_edges_graph_version_id
                FOREIGN KEY (graph_version_id)
                REFERENCES navigation_graph_versions(id)
                ON DELETE CASCADE;
            END IF;
        END
        $$;
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_routing_nodes_graph_version_id
            ON routing_nodes (graph_version_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_routing_edges_graph_version_id
            ON routing_edges (graph_version_id);
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS ix_routing_edges_graph_version_id;")
    op.execute("DROP INDEX IF EXISTS ix_routing_nodes_graph_version_id;")
    op.execute("DROP INDEX IF EXISTS ix_navigation_graph_versions_building_active;")
    op.execute("DROP INDEX IF EXISTS ix_navigation_graph_versions_building_id;")

    op.execute("ALTER TABLE routing_edges DROP CONSTRAINT IF EXISTS fk_routing_edges_graph_version_id;")
    op.execute("ALTER TABLE routing_nodes DROP CONSTRAINT IF EXISTS fk_routing_nodes_graph_version_id;")

    op.execute("ALTER TABLE routing_edges DROP COLUMN IF EXISTS graph_version_id;")
    op.execute("ALTER TABLE routing_nodes DROP COLUMN IF EXISTS graph_version_id;")

    op.execute("DROP TABLE IF EXISTS navigation_graph_versions;")
