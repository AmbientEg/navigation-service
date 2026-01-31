import uuid
from sqlalchemy import Float, ForeignKey, Index, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class RoutingEdge(Base, TimestampMixin):
    """Routing edge representing a connection between two routing nodes."""
    __tablename__ = "routing_edges"
    __table_args__ = (
        Index("ix_routing_edges_from_node_id", "from_node_id"),
        Index("ix_routing_edges_to_node_id", "to_node_id"),
        Index("ix_routing_edges_edge_type_id", "edge_type_id"),
        Index("ix_routing_edges_nodes", "from_node_id", "to_node_id", unique=True),
        CheckConstraint("distance > 0", name="check_distance_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    from_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("routing_nodes.id", ondelete="CASCADE"),
        nullable=False
    )

    to_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("routing_nodes.id", ondelete="CASCADE"),
        nullable=False
    )

    edge_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("edge_types.id"),
        nullable=False
    )

    distance: Mapped[float] = mapped_column(Float, nullable=False)

    # Relationships
    edge_type: Mapped["EdgeType"] = relationship("EdgeType", back_populates="routing_edges")
    from_node: Mapped["RoutingNode"] = relationship(
        "RoutingNode",
        foreign_keys=[from_node_id],
        back_populates="edges_from"
    )
    to_node: Mapped["RoutingNode"] = relationship(
        "RoutingNode",
        foreign_keys=[to_node_id],
        back_populates="edges_to"
    )

    def __repr__(self) -> str:
        return f"<RoutingEdge(id={self.id}, from={self.from_node_id}, to={self.to_node_id}, distance={self.distance})>"
