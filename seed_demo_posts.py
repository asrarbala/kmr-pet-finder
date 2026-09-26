"""Add repeatable sample posts to the configured local database."""

from datetime import datetime, timedelta
from pathlib import Path
from random import Random

from sqlalchemy import select

from config import PROJECT_DIR
from database import Base, SessionLocal, engine
from models import PetPost
from schemas import INDIA_TIMEZONE, PetPostCreate


LOCATIONS = [
    ("Lal Chowk", "Srinagar"),
    ("Dal Lake", "Srinagar"),
    ("Sopore", "Baramulla"),
    ("Pahalgam", "Anantnag"),
    ("Pulwama town", "Pulwama"),
    ("Budgam town", "Budgam"),
    ("Kupwara town", "Kupwara"),
    ("Ganderbal town", "Ganderbal"),
]
ANIMALS = [
    ("dog", "Labrador"),
    ("dog", None),
    ("cat", "Persian"),
    ("cat", None),
    ("rabbit", None),
    ("parrot", None),
]
COLORS = ["brown", "black", "white", "grey", "golden", "black and white"]
DETAILS = ["with a blue collar", "with a red collar", "with a small white patch", "with no collar"]
NAMES = ["Buddy", "Milo", "Luna", "Snowy", "Simba", "Coco"]


def main():
    database_path = engine.url.database
    if (
        engine.url.get_backend_name() != "sqlite"
        or not database_path
        or Path(database_path).resolve() != PROJECT_DIR / "pets.db"
    ):
        raise RuntimeError("Demo posts may only be seeded into this project's local pets.db")

    Base.metadata.create_all(bind=engine)
    random = Random(20260927)
    today = datetime.now(INDIA_TIMEZONE).date()
    added = 0

    with SessionLocal() as db:
        for number in range(1, 22):
            marker = f"[KMR DEMO {number:02d}]"
            status = "LOST" if number % 2 else "FOUND"
            species, breed = random.choice(ANIMALS)
            area, district = random.choice(LOCATIONS)
            color = random.choice(COLORS)
            detail = random.choice(DETAILS)
            post = PetPostCreate(
                status=status,
                species=species,
                breed=breed,
                pet_name=random.choice(NAMES) if status == "LOST" else None,
                description=(
                    f"{marker} Sample report for testing. {color.capitalize()} {species} {detail}. "
                    "This is not a real pet report."
                ),
                area=area,
                district=district,
                event_date=today - timedelta(days=random.randint(0, 14)),
                contact_name="Demo contact",
                contact_phone="0000000000",
            )
            if db.scalar(select(PetPost.id).where(PetPost.description.startswith(marker))) is not None:
                continue
            # Demo rows have no private owner token and cannot be edited through the public API.
            db.add(PetPost(**post.model_dump(), edit_token_hash=None))
            added += 1
        db.commit()

    print(f"Added {added} demo posts. Existing posts were left unchanged.")


if __name__ == "__main__":
    main()
