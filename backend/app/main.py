from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    enrichment,
    generate,
    mastery,
    practice,
    sentences,
    tokens,
    vocab,
    vocab_suggest,
    voice,
    workspaces,
)
from app.services.enrichment_worker import run_startup_enrichment, start_enrichment_scheduler
from app.config import settings
from app.db.database import Base, engine
from app.db import models  # noqa: F401
from app.db.backfill_lexemes import backfill_lexemes
from app.db.migrate import (
    drop_deprecated_vocab_columns,
    ensure_enrichment_job_lexeme_column,
    ensure_lexeme_vocab_columns,
    ensure_vocab_canonical_columns,
)
from app.db.seed import (
    backfill_canonical_word_fields,
    ensure_default_workspace_and_vocab,
)

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
app.include_router(enrichment.router, prefix="/api", tags=["enrichment"])
app.include_router(vocab_suggest.router, prefix="/api", tags=["vocab-suggest"])
app.include_router(workspaces.router, prefix="/api", tags=["workspaces"])
app.include_router(mastery.router, prefix="/api", tags=["mastery"])
app.include_router(sentences.router, prefix="/api", tags=["sentences"])
app.include_router(tokens.router, prefix="/api", tags=["tokens"])
# Voice routes mix REST (`/api/tts`) and WebSocket (`/ws/realtime`); both
# paths are declared inside the router itself, so we mount with no prefix.
app.include_router(voice.router, tags=["voice"])


@app.on_event("startup")
def _init_db() -> None:
    ensure_vocab_canonical_columns(engine)
    ensure_lexeme_vocab_columns(engine)
    ensure_enrichment_job_lexeme_column(engine)
    Base.metadata.create_all(bind=engine)
    ensure_default_workspace_and_vocab()
    backfill_canonical_word_fields()
    backfill_lexemes()
    drop_deprecated_vocab_columns(engine)
    run_startup_enrichment()
    start_enrichment_scheduler()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
