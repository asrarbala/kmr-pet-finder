from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from config import database_url


DATABASE_URL = database_url()

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
