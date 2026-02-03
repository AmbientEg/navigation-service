"""Initial schema with models, indexes, and constraints

Revision ID: 001_initial_schema
Revises: 000_enable_postgis
Create Date: 2026-02-03 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from geoalchemy2 import Geometry

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, Sequence[str], None] = '000_enable_postgis'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables with indexes and constraints."""
    
    # Create node_types table
    op.create_table(
        'node_types',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', name='uq_node_types_code')
    )
    op.create_index('ix_node_types_code', 'node_types', ['code'])

    # Create edge_types table
    op.create_table(
        'edge_types',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('is_accessible', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', name='uq_edge_types_code')
    )
    op.create_index('ix_edge_types_code', 'edge_types', ['code'])

    # Create buildings table
    op.create_table(
        'buildings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('floors_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('geometry', Geometry(geometry_type='POLYGON', srid=4326, spatial_index=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_buildings_name', 'buildings', ['name'])

    # Create floors table
    op.create_table(
        'floors',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('building_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('level_number', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('height_meters', sa.Float(), nullable=False),
        sa.Column('floor_geojson', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['building_id'], ['buildings.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('height_meters > 0', name='check_height_positive'),
        sa.UniqueConstraint('building_id', 'level_number', name='uq_floors_building_level')
    )
    op.create_index('ix_floors_building_id', 'floors', ['building_id'])

    # Create pois table
    op.create_table(
        'pois',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('floor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('type', sa.String(100), nullable=False),
        sa.Column('geometry', Geometry(geometry_type='POINT', srid=4326, spatial_index=True), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['floor_id'], ['floors.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_pois_floor_id', 'pois', ['floor_id'])
    op.create_index('ix_pois_type', 'pois', ['type'])
    op.create_index('ix_pois_name', 'pois', ['name'])

    # Create routing_nodes table
    op.create_table(
        'routing_nodes',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('floor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('node_type_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('geometry', Geometry(geometry_type='POINT', srid=4326, spatial_index=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['floor_id'], ['floors.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['node_type_id'], ['node_types.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_routing_nodes_floor_id', 'routing_nodes', ['floor_id'])
    op.create_index('ix_routing_nodes_node_type_id', 'routing_nodes', ['node_type_id'])

    # Create routing_edges table
    op.create_table(
        'routing_edges',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('from_node_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('to_node_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('edge_type_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('distance', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['edge_type_id'], ['edge_types.id']),
        sa.ForeignKeyConstraint(['from_node_id'], ['routing_nodes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['to_node_id'], ['routing_nodes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('distance > 0', name='check_distance_positive'),
        sa.UniqueConstraint('from_node_id', 'to_node_id', name='uq_routing_edges_nodes')
    )
    op.create_index('ix_routing_edges_edge_type_id', 'routing_edges', ['edge_type_id'])
    op.create_index('ix_routing_edges_from_node_id', 'routing_edges', ['from_node_id'])
    op.create_index('ix_routing_edges_to_node_id', 'routing_edges', ['to_node_id'])


def downgrade() -> None:
    """Drop all tables."""
    
    # Drop tables in reverse order of creation
    op.drop_table('routing_edges')
    op.drop_table('routing_nodes')
    op.drop_table('pois')
    op.drop_table('floors')
    op.drop_table('buildings')
    op.drop_table('edge_types')
    op.drop_table('node_types')
