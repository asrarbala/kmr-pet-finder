from datetime import date

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import PetPost, PostStatus
from schemas import PetPostCreate, PetPostResponse, PetPostUpdate


Base.metadata.create_all(bind=engine)
if "breed" not in {column["name"] for column in inspect(engine).get_columns("pet_posts")}:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE pet_posts ADD COLUMN breed VARCHAR"))

app = FastAPI()


@app.get("/")
def root():
    return {"message": "KMR Pet Finder API is running"}


@app.post("/pets", response_model=PetPostResponse, status_code=201)
def create_pet_post(post: PetPostCreate, db: Session = Depends(get_db)):
    pet_post = PetPost(**post.model_dump())
    db.add(pet_post)
    db.commit()
    db.refresh(pet_post)
    return pet_post


@app.put("/pets/{id}", response_model=PetPostResponse)
def update_pet_post(id: int, post: PetPostUpdate, db: Session = Depends(get_db)):
    pet_post = db.get(PetPost, id)
    if pet_post is None:
        raise HTTPException(status_code=404, detail="Pet post not found")
    for field, value in post.model_dump().items():
        setattr(pet_post, field, value)
    db.commit()
    db.refresh(pet_post)
    return pet_post


@app.get("/pets", response_model=list[PetPostResponse])
def list_pet_posts(
    status: PostStatus | None = None,
    species: str | None = None,
    district: str | None = None,
    area: str | None = None,
    event_date_from: date | None = None,
    event_date_to: date | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(PetPost)
    if status is not None:
        query = query.filter(PetPost.status == status)
    if species is not None:
        query = query.filter(PetPost.species == species)
    if district is not None:
        query = query.filter(PetPost.district == district)
    if area is not None:
        query = query.filter(PetPost.area == area)
    if event_date_from is not None:
        query = query.filter(PetPost.event_date >= event_date_from)
    if event_date_to is not None:
        query = query.filter(PetPost.event_date <= event_date_to)
    return query.order_by(PetPost.created_at.desc()).all()


@app.get("/pets/{id}", response_model=PetPostResponse)
def get_pet_post(id: int, db: Session = Depends(get_db)):
    pet_post = db.get(PetPost, id)
    if pet_post is None:
        raise HTTPException(status_code=404, detail="Pet post not found")
    return pet_post
