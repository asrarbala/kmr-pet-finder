from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, Date, DateTime, Enum as SqlEnum, Integer, String, Text

from database import Base


class PostStatus(str, Enum):
    LOST = "LOST"
    FOUND = "FOUND"


class PetPost(Base):
    __tablename__ = "pet_posts"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(SqlEnum(PostStatus), nullable=False)
    species = Column(String, nullable=False)
    breed = Column(String, nullable=True)
    pet_name = Column(String, nullable=True)
    description = Column(Text, nullable=False)
    area = Column(String, nullable=False)
    district = Column(String, nullable=False)
    event_date = Column(Date, nullable=False)
    contact_name = Column(String, nullable=False)
    contact_phone = Column(String, nullable=False)
    contact_email = Column(String, nullable=True)
    photo_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    edit_token_hash = Column(String(64), nullable=True)
