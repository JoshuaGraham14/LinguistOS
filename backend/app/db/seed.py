from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.api._auth import LOCAL_USER_EMAIL
from app.db.backfill_lexemes import find_or_create_lexeme, normalize_key_part
from app.db.database import SessionLocal
from app.db.models import Lexeme, User, Vocab, Workspace

VALID_POS_TAGS = {"noun", "verb", "adjective", "adverb", "preposition"}

DEFAULT_WORKSPACE_NAME = "Spanish core"
DEFAULT_WORKSPACE_LANGUAGE = "es"
DEFAULT_WORKSPACE_EMOJI = "🇪🇸"

DEFAULT_SPANISH_VOCAB: list[dict[str, str | list[str]]] = [
    {"word": "hola", "translation": "hello", "tags": ["other"]},
    {"word": "adiós", "translation": "goodbye", "tags": ["other"]},
    {"word": "gracias", "translation": "thank you", "tags": ["other"]},
    {"word": "por favor", "translation": "please", "tags": ["other"]},
    {"word": "sí", "translation": "yes", "tags": ["other"]},
    {"word": "no", "translation": "no", "tags": ["other"]},
    {"word": "casa", "translation": "house", "tags": ["noun"]},
    {"word": "agua", "translation": "water", "tags": ["noun"]},
    {"word": "pan", "translation": "bread", "tags": ["noun"]},
    {"word": "leche", "translation": "milk", "tags": ["noun"]},
    {"word": "café", "translation": "coffee", "tags": ["noun"]},
    {"word": "comida", "translation": "food", "tags": ["noun"]},
    {"word": "día", "translation": "day", "tags": ["noun"]},
    {"word": "noche", "translation": "night", "tags": ["noun"]},
    {"word": "año", "translation": "year", "tags": ["noun"]},
    {"word": "semana", "translation": "week", "tags": ["noun"]},
    {"word": "mes", "translation": "month", "tags": ["noun"]},
    {"word": "hora", "translation": "hour", "tags": ["noun"]},
    {"word": "minuto", "translation": "minute", "tags": ["noun"]},
    {"word": "tiempo", "translation": "time", "tags": ["noun"]},
    {"word": "trabajo", "translation": "work / job", "tags": ["noun"]},
    {"word": "escuela", "translation": "school", "tags": ["noun"]},
    {"word": "universidad", "translation": "university", "tags": ["noun"]},
    {"word": "familia", "translation": "family", "tags": ["noun"]},
    {"word": "amigo", "translation": "friend", "tags": ["noun"]},
    {"word": "mujer", "translation": "woman", "tags": ["noun"]},
    {"word": "hombre", "translation": "man", "tags": ["noun"]},
    {"word": "niño", "translation": "child", "tags": ["noun"]},
    {"word": "perro", "translation": "dog", "tags": ["noun"]},
    {"word": "gato", "translation": "cat", "tags": ["noun"]},
    {"word": "libro", "translation": "book", "tags": ["noun"]},
    {"word": "ciudad", "translation": "city", "tags": ["noun"]},
    {"word": "país", "translation": "country", "tags": ["noun"]},
    {"word": "calle", "translation": "street", "tags": ["noun"]},
    {"word": "coche", "translation": "car", "tags": ["noun"]},
    {"word": "dinero", "translation": "money", "tags": ["noun"]},
    {"word": "mercado", "translation": "market", "tags": ["noun"]},
    {"word": "problema", "translation": "problem", "tags": ["noun"]},
    {"word": "idea", "translation": "idea", "tags": ["noun"]},
    {"word": "mundo", "translation": "world", "tags": ["noun"]},
    {"word": "vida", "translation": "life", "tags": ["noun"]},
    {"word": "persona", "translation": "person", "tags": ["noun"]},
    {"word": "nombre", "translation": "name", "tags": ["noun"]},
    {"word": "foto", "translation": "photo", "tags": ["noun"]},
    {"word": "música", "translation": "music", "tags": ["noun"]},
    {"word": "película", "translation": "film", "tags": ["noun"]},
    {"word": "color", "translation": "color", "tags": ["noun"]},
    {"word": "número", "translation": "number", "tags": ["noun"]},
    {"word": "sol", "translation": "sun", "tags": ["noun"]},
    {"word": "luna", "translation": "moon", "tags": ["noun"]},
    {"word": "mar", "translation": "sea", "tags": ["noun"]},
    {"word": "montaña", "translation": "mountain", "tags": ["noun"]},
    {"word": "árbol", "translation": "tree", "tags": ["noun"]},
    {"word": "flor", "translation": "flower", "tags": ["noun"]},
    {"word": "animal", "translation": "animal", "tags": ["noun"]},
    {"word": "comer", "translation": "to eat", "tags": ["verb"]},
    {"word": "beber", "translation": "to drink", "tags": ["verb"]},
    {"word": "hablar", "translation": "to speak", "tags": ["verb"]},
    {"word": "escuchar", "translation": "to listen", "tags": ["verb"]},
    {"word": "leer", "translation": "to read", "tags": ["verb"]},
    {"word": "escribir", "translation": "to write", "tags": ["verb"]},
    {"word": "estudiar", "translation": "to study", "tags": ["verb"]},
    {"word": "trabajar", "translation": "to work", "tags": ["verb"]},
    {"word": "vivir", "translation": "to live", "tags": ["verb"]},
    {"word": "ir", "translation": "to go", "tags": ["verb"]},
    {"word": "venir", "translation": "to come", "tags": ["verb"]},
    {"word": "tener", "translation": "to have", "tags": ["verb"]},
    {"word": "ser", "translation": "to be", "tags": ["verb"]},
    {"word": "estar", "translation": "to be", "tags": ["verb"]},
    {"word": "hacer", "translation": "to do / to make", "tags": ["verb"]},
    {"word": "poder", "translation": "can / to be able", "tags": ["verb"]},
    {"word": "querer", "translation": "to want", "tags": ["verb"]},
    {"word": "necesitar", "translation": "to need", "tags": ["verb"]},
    {"word": "gustar", "translation": "to like", "tags": ["verb"]},
    {"word": "ayudar", "translation": "to help", "tags": ["verb"]},
    {"word": "comprar", "translation": "to buy", "tags": ["verb"]},
    {"word": "vender", "translation": "to sell", "tags": ["verb"]},
    {"word": "abrir", "translation": "to open", "tags": ["verb"]},
    {"word": "cerrar", "translation": "to close", "tags": ["verb"]},
    {"word": "pensar", "translation": "to think", "tags": ["verb"]},
    {"word": "correr", "translation": "to run", "tags": ["verb"]},
    {"word": "grande", "translation": "big", "tags": ["adjective"]},
    {"word": "pequeño", "translation": "small", "tags": ["adjective"]},
    {"word": "bueno", "translation": "good", "tags": ["adjective"]},
    {"word": "malo", "translation": "bad", "tags": ["adjective"]},
    {"word": "nuevo", "translation": "new", "tags": ["adjective"]},
    {"word": "viejo", "translation": "old", "tags": ["adjective"]},
    {"word": "joven", "translation": "young", "tags": ["adjective"]},
    {"word": "fácil", "translation": "easy", "tags": ["adjective"]},
    {"word": "difícil", "translation": "difficult", "tags": ["adjective"]},
    {"word": "importante", "translation": "important", "tags": ["adjective"]},
    {"word": "feliz", "translation": "happy", "tags": ["adjective"]},
    {"word": "triste", "translation": "sad", "tags": ["adjective"]},
    {"word": "rápido", "translation": "fast", "tags": ["adjective"]},
    {"word": "lento", "translation": "slow", "tags": ["adjective"]},
    {"word": "caliente", "translation": "hot", "tags": ["adjective"]},
    {"word": "frío", "translation": "cold", "tags": ["adjective"]},
    {"word": "dulce", "translation": "sweet", "tags": ["adjective"]},
    {"word": "aquí", "translation": "here", "tags": ["adverb"]},
    {"word": "mañana", "translation": "tomorrow / morning", "tags": ["adverb"]},
]


def _pos_from_tags(tags: list[str]) -> str:
    for tag in tags:
        if tag in VALID_POS_TAGS:
            return tag
    return "other"


def _capitalize_first(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return stripped
    return stripped[0].upper() + stripped[1:]


def ensure_default_workspace_and_vocab() -> None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == LOCAL_USER_EMAIL))
        if user is None:
            user = User(email=LOCAL_USER_EMAIL)
            db.add(user)
            db.commit()
            db.refresh(user)

        workspace = db.scalar(
            select(Workspace).where(
                Workspace.owner_id == user.id,
                Workspace.name == DEFAULT_WORKSPACE_NAME,
            )
        )
        if workspace is None:
            workspace = Workspace(
                owner_id=user.id,
                name=DEFAULT_WORKSPACE_NAME,
                language=DEFAULT_WORKSPACE_LANGUAGE,
                emoji_or_flag=DEFAULT_WORKSPACE_EMOJI,
            )
            db.add(workspace)
            db.commit()
            db.refresh(workspace)

        vocab_count = db.scalar(
            select(func.count(Vocab.id)).where(Vocab.workspace_id == workspace.id)
        )
        if (vocab_count or 0) > 0:
            return

        for entry in DEFAULT_SPANISH_VOCAB:
            word = str(entry["word"])
            translation = str(entry["translation"])
            tags = list(entry["tags"])  # type: ignore[arg-type]
            pos = _pos_from_tags(tags)
            lexeme = find_or_create_lexeme(
                db,
                language=workspace.language,
                lemma=normalize_key_part(word) or word,
                pos=pos,
                gloss_primary=normalize_key_part(translation) or translation,
                tags=tags,
                glosses=[translation],
            )
            lexeme.enrichment_status = "enriched"
            lexeme.enriched_at = lexeme.enriched_at or datetime.utcnow()
            surface = _capitalize_first(word)
            gloss = translation
            db.add(
                Vocab(
                    workspace_id=workspace.id,
                    lexeme_id=lexeme.id,
                    word=surface,
                    translation=gloss,
                    surface_form=surface,
                    surface_forms=[surface],
                    learned=False,
                )
            )
        db.commit()


def backfill_canonical_word_fields() -> int:
    """Legacy no-op after Lexeme migration; kept for startup hook compatibility."""
    return 0
