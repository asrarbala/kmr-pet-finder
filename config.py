import os
from pathlib import Path

from sqlalchemy.engine import URL, make_url


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_FRONTEND_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


def database_url() -> str:
    configured_url = os.getenv("KMR_DATABASE_URL", "").strip()
    if configured_url:
        url = make_url(configured_url)
        if not url.drivername.startswith("sqlite"):
            raise ValueError("KMR_DATABASE_URL must be a SQLite URL")
        if url.database and url.database != ":memory:":
            path = Path(url.database)
            if not path.is_absolute():
                url = url.set(database=str(PROJECT_DIR / path))
        return str(url)

    path = Path(os.getenv("KMR_DATABASE_PATH") or "pets.db")
    if not path.is_absolute():
        path = PROJECT_DIR / path
    return str(URL.create("sqlite", database=str(path)))


def allowed_frontend_origins() -> list[str]:
    configured_origins = os.getenv("KMR_FRONTEND_ORIGINS")
    if configured_origins is None:
        return DEFAULT_FRONTEND_ORIGINS.copy()
    origins = [origin.strip().rstrip("/") for origin in configured_origins.split(",") if origin.strip()]
    if "*" in origins:
        raise ValueError("KMR_FRONTEND_ORIGINS must list explicit origins")
    return origins
