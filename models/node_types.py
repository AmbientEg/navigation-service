import uuid
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class NodeType(Base, TimestampMixin):
    """Node type lookup table for routing nodes (hallway, door, stairs, elevator, etc.)."""
    __tablename__ = "node_types"

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
    # examples: hallway, door, stairs, elevator, entrance, exit

    description: Mapped[str | None] = mapped_column(String(500))

    # Relationships
    routing_nodes: Mapped[list["RoutingNode"]] = relationship(
        "RoutingNode", back_populates="node_type"
    )

    def __repr__(self) -> str:
        return f"<NodeType(id={self.id}, code='{self.code}')>"
