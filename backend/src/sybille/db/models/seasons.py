from datetime import datetime

from sqlalchemy import CheckConstraint, Identity, SmallInteger, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from sybille.db.base import Base


class Season(Base):
    __tablename__ = "seasons"
    __table_args__ = (
        UniqueConstraint("year", "name"),
        CheckConstraint("name IN ('spring', 'summer', 'autumn', 'winter')", name="name"),
    )

    id: Mapped[int] = mapped_column(SmallInteger, Identity(), primary_key=True)
    year: Mapped[int] = mapped_column(SmallInteger)
    name: Mapped[str] = mapped_column(Text)
    starts_at: Mapped[datetime]
    ends_at: Mapped[datetime]
