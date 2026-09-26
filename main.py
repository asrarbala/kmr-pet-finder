import hashlib
import hmac
import logging
import re
import secrets
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, inspect, text
from sqlalchemy.orm import Session

from config import allowed_frontend_origins
from database import Base, engine, get_db
from models import PetPost, PostStatus
from schemas import PetPostCreate, PetPostCreated, PetPostResponse, PetPostUpdate


UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
MAX_PHOTO_BYTES = 5 * 1024 * 1024
IMAGE_TYPES = {"image/jpeg": (b"\xff\xd8\xff", ".jpg"), "image/png": (b"\x89PNG\r\n\x1a\n", ".png")}


Base.metadata.create_all(bind=engine)
columns = {column["name"] for column in inspect(engine).get_columns("pet_posts")}
if "breed" not in columns:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE pet_posts ADD COLUMN breed VARCHAR"))
if "edit_token_hash" not in columns:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE pet_posts ADD COLUMN edit_token_hash VARCHAR(64)"))

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_frontend_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-Edit-Token"],
)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


@app.get("/")
def root():
    return {"message": "KMR Pet Finder API is running"}


def require_edit_token(pet_post: PetPost, edit_token: str | None):
    candidate_hash = hashlib.sha256((edit_token or "").encode()).hexdigest()
    stored_hash = pet_post.edit_token_hash or "0" * 64
    if not edit_token or not pet_post.edit_token_hash or not hmac.compare_digest(candidate_hash, stored_hash):
        raise HTTPException(status_code=403, detail="Invalid or missing edit token")


def local_photo_path(post_id: int, photo_url: str | None) -> Path | None:
    prefix = "/uploads/"
    if photo_url and photo_url.startswith(prefix):
        filename = photo_url[len(prefix):]
        if re.fullmatch(rf"{post_id}-[0-9a-f]{{32}}\.(?:jpg|png|webp)", filename):
            return UPLOAD_DIR / filename
    return None


def remove_local_photo(path: Path | None):
    if path is not None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logging.warning("Could not remove local photo: %s", path)


@app.post("/pets", response_model=PetPostCreated, status_code=201)
def create_pet_post(post: PetPostCreate, db: Session = Depends(get_db)):
    edit_token = secrets.token_urlsafe(32)
    pet_post = PetPost(**post.model_dump(), edit_token_hash=hashlib.sha256(edit_token.encode()).hexdigest())
    db.add(pet_post)
    db.commit()
    db.refresh(pet_post)
    return {**PetPostResponse.model_validate(pet_post).model_dump(), "edit_token": edit_token}


@app.put("/pets/{id}", response_model=PetPostResponse)
def update_pet_post(
    id: int,
    post: PetPostUpdate,
    edit_token: str | None = Header(default=None, alias="X-Edit-Token"),
    db: Session = Depends(get_db),
):
    pet_post = db.get(PetPost, id)
    if pet_post is None:
        raise HTTPException(status_code=404, detail="Pet post not found")
    require_edit_token(pet_post, edit_token)
    for field, value in post.model_dump().items():
        setattr(pet_post, field, value)
    db.commit()
    db.refresh(pet_post)
    return pet_post


@app.post("/pets/{id}/photo", response_model=PetPostResponse)
def upload_pet_photo(
    id: int,
    photo: UploadFile = File(...),
    edit_token: str | None = Header(default=None, alias="X-Edit-Token"),
    db: Session = Depends(get_db),
):
    pet_post = db.get(PetPost, id)
    if pet_post is None:
        raise HTTPException(status_code=404, detail="Pet post not found")
    require_edit_token(pet_post, edit_token)

    try:
        image = photo.file.read(MAX_PHOTO_BYTES + 1)
    finally:
        photo.file.close()
    if len(image) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=413, detail="Photo must be 5 MB or smaller")

    image_type = IMAGE_TYPES.get(photo.content_type)
    if image_type is not None and image.startswith(image_type[0]):
        extension = image_type[1]
    elif photo.content_type == "image/webp" and image.startswith(b"RIFF") and image[8:12] == b"WEBP":
        extension = ".webp"
    else:
        raise HTTPException(status_code=415, detail="Only JPEG, PNG, and WEBP images are supported")

    filename = f"{id}-{secrets.token_hex(16)}{extension}"
    new_path = UPLOAD_DIR / filename
    old_path = local_photo_path(id, pet_post.photo_url)
    try:
        with new_path.open("xb") as stored_photo:
            stored_photo.write(image)
        pet_post.photo_url = f"/uploads/{filename}"
        db.commit()
    except Exception:
        db.rollback()
        new_path.unlink(missing_ok=True)
        raise

    remove_local_photo(old_path)
    return pet_post


@app.delete("/pets/{id}", status_code=204)
def delete_pet_post(
    id: int,
    edit_token: str | None = Header(default=None, alias="X-Edit-Token"),
    db: Session = Depends(get_db),
):
    pet_post = db.get(PetPost, id)
    if pet_post is None:
        raise HTTPException(status_code=404, detail="Pet post not found")
    require_edit_token(pet_post, edit_token)
    photo_path = local_photo_path(id, pet_post.photo_url)
    db.delete(pet_post)
    db.commit()
    remove_local_photo(photo_path)


@app.get("/pets", response_model=list[PetPostResponse])
def list_pet_posts(
    status: PostStatus | None = None,
    species: str | None = None,
    district: str | None = None,
    area: str | None = None,
    event_date_from: date | None = None,
    event_date_to: date | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(PetPost)
    if status is not None:
        query = query.filter(PetPost.status == status)
    if species is not None:
        query = query.filter(func.lower(PetPost.species) == species.strip().lower())
    if district is not None:
        query = query.filter(func.lower(PetPost.district) == district.strip().lower())
    if area is not None:
        query = query.filter(func.lower(PetPost.area) == area.strip().lower())
    if event_date_from is not None:
        query = query.filter(PetPost.event_date >= event_date_from)
    if event_date_to is not None:
        query = query.filter(PetPost.event_date <= event_date_to)
    return query.order_by(PetPost.created_at.desc(), PetPost.id.desc()).offset(offset).limit(limit).all()


@app.get("/pets/{id}", response_model=PetPostResponse)
def get_pet_post(id: int, db: Session = Depends(get_db)):
    pet_post = db.get(PetPost, id)
    if pet_post is None:
        raise HTTPException(status_code=404, detail="Pet post not found")
    return pet_post
