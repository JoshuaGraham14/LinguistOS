from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


def _build_engine():
    db_url = settings.database_url
    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    engine = create_engine(db_url, future=True, connect_args=connect_args)

    # If local Postgres isn't running, transparently fall back to SQLite for dev.
    if db_url.startswith("postgresql"):
        try:
            with engine.connect():
                pass
        except OperationalError:
            fallback_url = "sqlite+pysqlite:///./linguistos.db"
            print(
                "Database connection failed for DATABASE_URL. "
                f"Falling back to {fallback_url}."
            )
            engine = create_engine(
                fallback_url,
                future=True,
                connect_args={"check_same_thread": False},
            )

    return engine


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
