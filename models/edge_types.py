import uuid
from sqlalchemy import String, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class EdgeType(Base, TimestampMixin):
    """Edge type lookup table for routing edges (hallway, stairs, elevator, etc.)."""
    __tablename__ = "edge_types"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True
    )
    # hallway, stairs, elevator, escalator, ramp

    is_accessible: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true"
    )

    description: Mapped[str | None] = mapped_column(String(500))

    # Relationships
    routing_edges: Mapped[list["RoutingEdge"]] = relationship(
        "RoutingEdge", back_populates="edge_type"
    )

    def __repr__(self) -> str:
        return f"<EdgeType(id={self.id}, code='{self.code}', accessible={self.is_accessible})>"
