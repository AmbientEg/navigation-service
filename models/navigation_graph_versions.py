import uuid
from sqlalchemy import Boolean, ForeignKey, Index, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class NavigationGraphVersion(Base, TimestampMixin):
    """Version record for derived navigation graphs per building."""

    __tablename__ = "navigation_graph_versions"
    __table_args__ = (
        Index("ix_navigation_graph_versions_building_id", "building_id"),
        Index("ix_navigation_graph_versions_building_active", "building_id", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    building_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("buildings.id", ondelete="CASCADE"),
        nullable=False,
    )

    version_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    def __repr__(self) -> str:
        return (
            f"<NavigationGraphVersion(id={self.id}, building_id={self.building_id}, "
            f"version={self.version_number}, active={self.is_active})>"
        )
