from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    """SQLite ships with FK enforcement off by default.

    We rely on ``ON DELETE CASCADE`` for sentence/sentence_word_links so we
    enable foreign keys at every connection checkout. Postgres is strict by
    default, so this is a no-op there.
    """
    if not engine.url.get_backend_name().startswith("sqlite"):
        return

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record):  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def _build_engine() -> Engine:
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

    _enable_sqlite_foreign_keys(engine)
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
