from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from models import PostStatus


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
    species: str = Field(description="Animal type, such as dog or cat")
    breed: str | None = Field(default=None, description="Optional breed within the species; null or empty is allowed")
    pet_name: str | None = None
    description: str
    area: str
    district: str
    event_date: date
    contact_name: str
    contact_phone: str
    contact_email: str | None = None
    photo_url: str | None = None


class PetPostUpdate(PetPostCreate):
    pass


class PetPostResponse(PetPostCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class PetPostCreated(PetPostResponse):
    edit_token: str = Field(description="Save this private token; it is only returned when the post is created")
