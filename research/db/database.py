"""Research-mode SQLite database engine and session."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "research.db"


def get_db_path() -> Path:
    """Return the active SQLite path (``RESEARCH_DB`` env overrides the default)."""
    override = os.environ.get("RESEARCH_DB")
    if override:
        return Path(override)
    return _DEFAULT_DB_PATH


def create_engine_for_path(db_path: Path | None = None) -> Engine:
    """Build a SQLite engine for *db_path* (or ``get_db_path()`` when omitted)."""
    path = db_path if db_path is not None else get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    url = f"sqlite+pysqlite:///{path}"
    eng = create_engine(
        url,
        future=True,
        connect_args={"check_same_thread": False, "timeout": 60},
    )

    @event.listens_for(eng, "connect")
    def _configure_sqlite(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    return eng


engine = create_engine_for_path()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_session():
    """Yield a session that auto-closes."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def init_db(db_path: Path | None = None):
    """Create all tables if they do not exist."""
    from research.db import models  # noqa: F401

    eng = create_engine_for_path(db_path) if db_path is not None else engine
    Base.metadata.create_all(bind=eng)


def reset_db() -> None:
    """Delete research.db and recreate an empty schema.

    Use when the schema changes or you want a clean slate. Existing experiment
    data is discarded.
    """
    path = get_db_path()
    engine.dispose()
    if path.exists():
        path.unlink()
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(path) + suffix)
        if sidecar.exists():
            sidecar.unlink()
    init_db()
