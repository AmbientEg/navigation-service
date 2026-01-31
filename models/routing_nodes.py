import uuid
from sqlalchemy import ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geometry

from .base import Base, TimestampMixin


class RoutingNode(Base, TimestampMixin):
    """Routing node representing a waypoint in the navigation graph."""
    __tablename__ = "routing_nodes"
    __table_args__ = (
        Index("ix_routing_nodes_floor_id", "floor_id"),
        Index("ix_routing_nodes_node_type_id", "node_type_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    floor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("floors.id", ondelete="CASCADE"),
        nullable=False
    )

    node_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("node_types.id"),
        nullable=False
    )

    # PostGIS point geometry with spatial index
    geometry: Mapped[bytes] = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=True)
    )

    # Relationships
    floor: Mapped["Floor"] = relationship("Floor", back_populates="routing_nodes")
    node_type: Mapped["NodeType"] = relationship("NodeType", back_populates="routing_nodes")
    
    # Edge relationships
    edges_from: Mapped[list["RoutingEdge"]] = relationship(
        "RoutingEdge",
        foreign_keys="RoutingEdge.from_node_id",
        back_populates="from_node"
    )
    edges_to: Mapped[list["RoutingEdge"]] = relationship(
        "RoutingEdge",
        foreign_keys="RoutingEdge.to_node_id",
        back_populates="to_node"
    )

    def __repr__(self) -> str:
        return f"<RoutingNode(id={self.id}, floor_id={self.floor_id}, type={self.node_type_id})>"
