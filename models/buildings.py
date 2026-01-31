import uuid
from sqlalchemy import String, Integer, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geometry

from .base import Base, TimestampMixin


class Building(Base, TimestampMixin):
    """Building model representing a physical building with multiple floors."""
    __tablename__ = "buildings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String)

    floors_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Building footprint - PostGIS geometry
    geometry: Mapped[bytes] = mapped_column(
        Geometry(geometry_type="POLYGON", srid=4326, spatial_index=True)
    )

    # Relationships
    floors: Mapped[list["Floor"]] = relationship(
        "Floor", back_populates="building", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Building(id={self.id}, name='{self.name}', floors={self.floors_count})>"