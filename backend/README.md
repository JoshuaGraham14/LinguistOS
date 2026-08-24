# Backend

FastAPI service for the user-facing learning prototype (vocab + sentence practice). Not used by the [`research/`](../research/) experimental framework.

## Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

## Run

```bash
uvicorn app.main:app --reload --port 8000
```

API docs at http://localhost:8000/docs.

## Layout

```
app/
  main.py        FastAPI entrypoint
  config.py      Settings (env vars)
  api/           HTTP route handlers
  core/          Pipeline engine — generation, analysis, validation, scoring
  nlp/           Wrappers around spaCy, Stanza, LanguageTool
  db/            SQLAlchemy models, session, schemas
tests/
```
