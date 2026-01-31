import uuid
from sqlalchemy import String, Integer, Float, ForeignKey, Index, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class Floor(Base, TimestampMixin):
    """Floor model representing a single floor within a building."""
    __tablename__ = "floors"
    __table_args__ = (
        Index("ix_floors_building_id", "building_id"),
        Index("ix_floors_building_level", "building_id", "level_number", unique=True),
        CheckConstraint("height_meters > 0", name="check_height_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    building_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("buildings.id", ondelete="CASCADE"),
        nullable=False
    )

    level_number: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # -1 (basement), 0 (ground), 1, 2...
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    height_meters: Mapped[float] = mapped_column(Float, nullable=False)

    # Entire indoor map as GeoJSON
    floor_geojson: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Relationships
    building: Mapped["Building"] = relationship(
        "Building", back_populates="floors"
    )
    pois: Mapped[list["POI"]] = relationship(
        "POI", back_populates="floor", cascade="all, delete-orphan"
    )
    routing_nodes: Mapped[list["RoutingNode"]] = relationship(
        "RoutingNode", back_populates="floor", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Floor(id={self.id}, building_id={self.building_id}, level={self.level_number}, name='{self.name}')>"
