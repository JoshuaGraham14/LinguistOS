from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import generate, practice, vocab, workspaces
from app.config import settings
from app.db.database import Base, engine
from app.db import models  # noqa: F401
from app.db.seed import ensure_default_workspace_and_vocab

app = FastAPI(title="LinguistOS API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(generate.router, prefix="/api", tags=["generate"])
app.include_router(practice.router, prefix="/api", tags=["practice"])
app.include_router(vocab.router, prefix="/api", tags=["vocab"])
app.include_router(workspaces.router, prefix="/api", tags=["workspaces"])


@app.on_event("startup")
def _init_db() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_default_workspace_and_vocab()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
