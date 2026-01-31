import uuid
from sqlalchemy import String, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geometry

from .base import Base, TimestampMixin


class POI(Base, TimestampMixin):
    """Point of Interest model representing destinations like shops, restrooms, etc."""
    __tablename__ = "pois"
    __table_args__ = (
        Index("ix_pois_floor_id", "floor_id"),
        Index("ix_pois_type", "type"),
        Index("ix_pois_name", "name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    floor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("floors.id", ondelete="CASCADE"),
        nullable=False
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(100), nullable=False)  # restroom, elevator, shop...

    # PostGIS point geometry with spatial index
    geometry: Mapped[bytes] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True)
    )

    # Additional metadata as JSON (using extra_data to avoid reserved word)
    extra_data: Mapped[dict] = mapped_column(
        "metadata",  # Column name in database
        JSONB,
        nullable=False,
        default=dict
    )

    # Relationships
    floor: Mapped["Floor"] = relationship("Floor", back_populates="pois")

    def __repr__(self) -> str:
        return f"<POI(id={self.id}, name='{self.name}', type='{self.type}', floor_id={self.floor_id})>"
