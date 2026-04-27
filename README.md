# LinguistOS

Hybrid morpho-syntactic sentence generation + vocabulary learning system.

Two modes over one shared pipeline:
- **Learning Mode** — user-facing vocabulary practice (Next.js)
- **Research Mode** — evaluation, experimentation, analysis (Streamlit)

See [docs/hybrid_system_spec.md](docs/hybrid_system_spec.md) for the full specification.

## Layout

```
backend/    FastAPI service + core pipeline engine (the heart of the system)
frontend/   Next.js + TypeScript + Tailwind (Learning Mode UI)
research/   Streamlit app (Research Mode UI)
docs/       Specification and design notes
scripts/    Dev/db/setup utilities
```

## Quickstart

Each component has its own README with setup instructions:
- [backend/README.md](backend/README.md)
- [frontend/README.md](frontend/README.md)
- [research/README.md](research/README.md)

## Stack

| Layer        | Tech                                  |
|--------------|---------------------------------------|
| Frontend     | Next.js, TypeScript, Tailwind         |
| Research UI  | Streamlit                             |
| Backend API  | FastAPI (Python)                      |
| NLP          | spaCy, Stanza, LanguageTool           |
| Database     | PostgreSQL                            |
