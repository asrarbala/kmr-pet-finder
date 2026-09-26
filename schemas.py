import re
from datetime import date, datetime, timedelta, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator

from models import PostStatus

INDIA_TIMEZONE = timezone(timedelta(hours=5, minutes=30))


class PetPostCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {
        "status": "LOST",
        "species": "dog",
        "breed": "Kashmiri Sheepdog",
        "pet_name": "Buddy",
        "description": "Brown dog with a red collar",
        "area": "Lal Chowk",
        "district": "Srinagar",
        "event_date": "2026-09-26",
        "contact_name": "Amina",
        "contact_phone": "9876543210",
        "contact_email": None,
        "photo_url": None,
    }})

    status: PostStatus
    species: str = Field(min_length=1, max_length=50, description="Animal type, such as dog or cat")
    breed: str | None = Field(default=None, max_length=80, description="Optional breed within the species; null or empty is allowed")
    pet_name: str | None = Field(default=None, max_length=80)
    description: str = Field(min_length=1, max_length=2000)
    area: str = Field(min_length=1, max_length=100)
    district: str = Field(min_length=1, max_length=100)
    event_date: date
    contact_name: str = Field(min_length=1, max_length=100)
    contact_phone: str = Field(min_length=7, max_length=30)
    contact_email: str | None = Field(default=None, max_length=254)
    photo_url: str | None = None

    @field_validator(
        "species", "breed", "pet_name", "description", "area", "district",
        "contact_name", "contact_phone", "contact_email", "photo_url", mode="before"
    )
    @classmethod
    def trim_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("contact_phone")
    @classmethod
    def validate_phone(cls, value):
        digits = sum(character.isdigit() for character in value)
        if not re.fullmatch(r"\+?[0-9 ()-]+", value) or not 7 <= digits <= 15:
            raise ValueError("Phone must contain 7 to 15 digits and only simple phone punctuation")
        return value

    @field_validator("contact_email")
    @classmethod
    def validate_email(cls, value):
        if value == "":
            return None
        if value is not None and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Invalid email address")
        return value

    @field_validator("event_date")
    @classmethod
    def validate_event_date(cls, value):
        if value > datetime.now(INDIA_TIMEZONE).date():
            raise ValueError("Lost or found date cannot be in the future")
        return value


class PetPostUpdate(PetPostCreate):
    pass


class PetPostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: PostStatus
    species: str
    breed: str | None
    pet_name: str | None
    description: str
    area: str
    district: str
    event_date: date
    contact_name: str
    contact_phone: str
    contact_email: str | None
    photo_url: str | None
    created_at: datetime


class PetPostCreated(PetPostResponse):
    edit_token: str = Field(description="Save this private token; it is only returned when the post is created")
