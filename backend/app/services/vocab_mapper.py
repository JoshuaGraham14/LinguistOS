"""Map Lexeme + Vocab link to flat API responses."""

from __future__ import annotations

from typing import Any

from app.db.backfill_lexemes import is_lexeme_complete
from app.db.models import Lexeme, Vocab
from app.db.schemas import MasteryOut, VocabOut, VocabTag


def _coerce_json_dict(value: Any) -> dict[str, Any] | None:
    if value is None or value == "null":
        return None
    return value if isinstance(value, dict) else None


def _capitalize_first(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return stripped
    return stripped[0].upper() + stripped[1:]


def _display_gloss(vocab: Vocab, lexeme: Lexeme) -> str:
    return (vocab.gloss_override or lexeme.gloss_primary or "").strip()


def sync_legacy_mirrors(vocab: Vocab, lexeme: Lexeme) -> None:
    vocab.word = vocab.surface_form or vocab.word
    vocab.translation = _display_gloss(vocab, lexeme)


def vocab_out(vocab: Vocab, lexeme: Lexeme | None = None) -> VocabOut:
    lx = lexeme or vocab.lexeme
    if lx is None:
        raise ValueError(f"Vocab {vocab.id} has no linked lexeme")

    gloss = _display_gloss(vocab, lx)
    tags: list[VocabTag] = [t for t in lx.tags if t in {
        "noun", "verb", "adjective", "adverb", "preposition", "other"
    }]  # type: ignore[misc]

    mastery = None
    if vocab.mastery is not None:
        mastery = MasteryOut.model_validate(vocab.mastery)

    enriching = not is_lexeme_complete(lx)

    return VocabOut(
        id=vocab.id,
        workspace_id=vocab.workspace_id,
        lexeme_id=lx.id,
        word=vocab.surface_form or vocab.word,
        translation=gloss,
        tags=tags if tags or not enriching else [],
        learned=vocab.learned,
        created_at=vocab.created_at,
        enriching=enriching,
        lemma=_capitalize_first(lx.lemma),
        surface_form=vocab.surface_form,
        surface_forms=list(vocab.surface_forms or []),
        pos=lx.pos,
        cefr=lx.cefr,
        frequency_rank=lx.frequency_rank,
        gender=lx.gender,
        conjugation_class=lx.conjugation_class,
        morph_features=_coerce_json_dict(lx.morph_features),
        ipa=lx.ipa,
        audio_url=lx.audio_url,
        image_url=lx.image_url,
        gloss_primary=lx.gloss_primary or None,
        glosses=list(lx.glosses or []),
        notes=vocab.notes,
        last_seen_at=vocab.last_seen_at,
        mastery=mastery,
    )
