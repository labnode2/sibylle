import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from sybille import clock
from sybille.db.base import Base, new_id


class Upload(Base):
    """An image attached to a prono, re-encoded as WebP; only the newsroom's members can read it."""

    __tablename__ = "uploads"
    __table_args__ = (CheckConstraint("mime = 'image/webp'", name="mime"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organisations.id"), index=True)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("memberships.id"))
    mime: Mapped[str] = mapped_column(Text, default="image/webp", server_default="image/webp")
    width: Mapped[int]
    height: Mapped[int]
    size_bytes: Mapped[int]
    storage_key: Mapped[str] = mapped_column(Text, unique=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: clock.now())
