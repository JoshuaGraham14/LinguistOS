from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api._auth import ensure_workspace_owner
from app.db.database import get_db
from app.db.models import Vocab, Workspace
from app.db.schemas import VocabCreate, VocabListResponse, VocabOut, VocabUpdate
from app.services.enrichment_worker import maybe_enqueue_enrichment, process_enrichment_job
from app.services.lexeme_resolver import find_vocab_link, resolve_lexeme
from app.services.vocab_mapper import sync_legacy_mirrors, vocab_out

router = APIRouter()


def _capitalize_first_word(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return stripped
    return stripped[0].upper() + stripped[1:]


class _ResolvedCapture:
    """Resolved capture fields from create payload."""

    __slots__ = (
        "word",
        "translation",
        "lemma",
        "surface_form",
        "glosses",
        "gloss_primary",
        "pos",
        "tags",
        "cefr",
        "frequency_rank",
        "gender",
        "conjugation_class",
        "morph_features",
        "ipa",
        "audio_url",
        "image_url",
        "notes",
    )

    def __init__(self, payload: VocabCreate) -> None:
        surface = _capitalize_first_word(payload.surface_form or payload.word or "")
        if not surface:
            raise HTTPException(
                status_code=422,
                detail="Either surface_form or word must be provided",
            )
        gloss = (payload.gloss_primary or payload.translation or "").strip()
        self.surface_form = surface
        self.word = surface
        self.lemma = _capitalize_first_word(payload.lemma or surface)
        self.translation = gloss
        self.gloss_primary = gloss
        if payload.glosses:
            self.glosses = list(payload.glosses)
        elif gloss:
            self.glosses = [gloss]
        else:
            self.glosses = []
        self.pos = payload.pos
        self.tags = list(payload.tags or [])
        self.cefr = payload.cefr
        self.frequency_rank = payload.frequency_rank
        self.gender = payload.gender
        self.conjugation_class = payload.conjugation_class
        self.morph_features = payload.morph_features
        self.ipa = payload.ipa
        self.audio_url = payload.audio_url
        self.image_url = payload.image_url
        self.notes = payload.notes


def _load_vocab_with_mastery(db: Session, vocab_id: int) -> Vocab | None:
    return db.scalar(
        select(Vocab)
        .options(selectinload(Vocab.mastery), selectinload(Vocab.lexeme))
        .where(Vocab.id == vocab_id)
    )


def _workspace_language(db: Session, workspace_id: int) -> str:
    workspace = db.get(Workspace, workspace_id)
    return workspace.language if workspace else "es"


@router.get("/vocab", response_model=VocabListResponse)
def list_vocab(
    workspace_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
) -> VocabListResponse:
    ensure_workspace_owner(db, workspace_id)
    items = db.scalars(
        select(Vocab)
        .options(selectinload(Vocab.mastery), selectinload(Vocab.lexeme))
        .where(Vocab.workspace_id == workspace_id)
        .order_by(Vocab.created_at.desc())
    ).all()
    return VocabListResponse(
        items=[vocab_out(item) for item in items if item.lexeme is not None]
    )


@router.get("/vocab/{vocab_id}", response_model=VocabOut)
def get_vocab(vocab_id: int, db: Session = Depends(get_db)) -> VocabOut:
    item = _load_vocab_with_mastery(db, vocab_id)
    if not item or item.lexeme is None:
        raise HTTPException(status_code=404, detail="Word not found")
    ensure_workspace_owner(db, item.workspace_id)
    return vocab_out(item)


def _schedule_enrichment(background_tasks: BackgroundTasks | None, job_id: int | None) -> None:
    from app.config import settings

    if settings.linguistos_disable_enrichment:
        return
    if background_tasks is not None and job_id is not None:
        background_tasks.add_task(_run_enrichment_job, job_id)


def _run_enrichment_job(job_id: int) -> None:
    from app.db.database import SessionLocal

    with SessionLocal() as db:
        process_enrichment_job(db, job_id)
        db.commit()


@router.post("/vocab", response_model=VocabOut)
def add_vocab(
    payload: VocabCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> VocabOut:
    ensure_workspace_owner(db, payload.workspace_id)
    capture = _ResolvedCapture(payload)
    language = _workspace_language(db, payload.workspace_id)

    lexeme = resolve_lexeme(
        db,
        language,
        surface_form=capture.surface_form,
        lemma=capture.lemma,
        pos=capture.pos,
        gloss_primary=capture.gloss_primary,
        tags=capture.tags,
        glosses=capture.glosses,
        cefr=capture.cefr,
        frequency_rank=capture.frequency_rank,
        gender=capture.gender,
        conjugation_class=capture.conjugation_class,
        morph_features=capture.morph_features,
        ipa=capture.ipa,
        audio_url=capture.audio_url,
        image_url=capture.image_url,
        dictionary_notes=None,
    )

    existing = find_vocab_link(db, payload.workspace_id, lexeme.id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Word already in workspace vocabulary")

    item = Vocab(
        workspace_id=payload.workspace_id,
        lexeme_id=lexeme.id,
        word=capture.word,
        translation=capture.translation,
        surface_form=capture.surface_form,
        surface_forms=[capture.surface_form],
        notes=capture.notes,
    )
    sync_legacy_mirrors(item, lexeme)
    db.add(item)
    db.flush()
    job = maybe_enqueue_enrichment(db, lexeme_id=lexeme.id, vocab_id=item.id)
    db.commit()
    _schedule_enrichment(background_tasks, job.id if job else None)
    item = _load_vocab_with_mastery(db, item.id)
    assert item is not None
    return vocab_out(item)


_PERSONAL_FIELDS = frozenset({
    "learned",
    "notes",
    "surface_form",
    "word",
    "gloss_override",
})
_LEXEME_FIELDS = frozenset({
    "lemma",
    "pos",
    "tags",
    "cefr",
    "frequency_rank",
    "gender",
    "conjugation_class",
    "morph_features",
    "ipa",
    "audio_url",
    "image_url",
    "gloss_primary",
    "glosses",
    "translation",
})


@router.patch("/vocab/{vocab_id}", response_model=VocabOut)
def update_vocab(vocab_id: int, payload: VocabUpdate, db: Session = Depends(get_db)) -> VocabOut:
    item = _load_vocab_with_mastery(db, vocab_id)
    if not item or item.lexeme is None:
        raise HTTPException(status_code=404, detail="Word not found")
    ensure_workspace_owner(db, item.workspace_id)
    patch = payload.model_dump(exclude_unset=True)
    lexeme = item.lexeme

    for legacy, canonical in (("word", "surface_form"), ("translation", "gloss_primary")):
        if legacy in patch and canonical not in patch:
            patch[canonical] = patch[legacy]
        elif canonical in patch and legacy not in patch:
            patch[legacy] = patch[canonical]

    for field in ("word", "surface_form", "lemma"):
        value = patch.get(field)
        if isinstance(value, str):
            patch[field] = _capitalize_first_word(value)

    if "translation" in patch:
        gloss_val = patch.get("translation")
        if isinstance(gloss_val, str):
            item.gloss_override = gloss_val.strip() or None
        patch.pop("translation", None)

    patched_surface = patch.get("surface_form")
    if isinstance(patched_surface, str):
        normalized = patched_surface.strip()
        if normalized:
            forms = list(item.surface_forms or [])
            if normalized not in forms:
                forms.append(normalized)
                item.surface_forms = forms
        item.surface_form = normalized
        item.word = normalized
        patch.pop("surface_form", None)
        patch.pop("word", None)

    for field in _PERSONAL_FIELDS:
        if field in patch and field not in ("word", "gloss_override"):
            setattr(item, field, patch[field])

    for field in _LEXEME_FIELDS:
        if field not in patch:
            continue
        value = patch[field]
        if field == "tags" and value is not None:
            lexeme.tags = list(value)
        elif field == "glosses" and value is not None:
            lexeme.glosses = list(value)
        elif field == "gloss_primary" and isinstance(value, str):
            lexeme.gloss_primary = value.strip()
        elif hasattr(lexeme, field):
            setattr(lexeme, field, value)

    sync_legacy_mirrors(item, lexeme)
    db.add(item)
    db.add(lexeme)
    db.commit()
    db.refresh(item)
    item = _load_vocab_with_mastery(db, item.id)
    assert item is not None
    return vocab_out(item)


@router.delete("/vocab/{vocab_id}")
def delete_vocab(vocab_id: int, db: Session = Depends(get_db)) -> dict[str, bool]:
    item = db.get(Vocab, vocab_id)
    if not item:
        raise HTTPException(status_code=404, detail="Word not found")
    ensure_workspace_owner(db, item.workspace_id)
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.delete("/vocab")
def clear_vocab(
    workspace_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    ensure_workspace_owner(db, workspace_id)
    items = db.scalars(select(Vocab).where(Vocab.workspace_id == workspace_id)).all()
    for item in items:
        db.delete(item)
    db.commit()
    return {"ok": True}
