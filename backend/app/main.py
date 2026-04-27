from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import generate, practice, vocab
from app.config import settings

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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
