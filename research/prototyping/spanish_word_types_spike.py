#!/usr/bin/env python3
"""Non-verb word-type generalisation spike (one-off, Qwen 1.7B).

Quick diagnostic: does the constraint-driven sentence-generation framework
generalise from verbs to nouns, adjectives, adverbs, and past participles?

Approach:
  - Hand-crafted ~25 cells across 4 word types.
  - Single condition (baseline-style): give the model the lemma + morphological
    constraints, do NOT inject the gold form. We want to see whether the model
    produces the right inflection on its own and whether agreement holds
    across the sentence span.
  - No hard length constraint — structural requirements only (must appear with
    determiner / must modify a noun / must modify a verb).
  - n=5 sentences per cell, T=0.7.
  - Score: expected_form_match + grammar (LanguageTool) + adjacent-article
    sanity check for nouns. Manual review of all outputs.

NOT part of the formal pipeline; standalone JSON output for manual analysis.

Results: docs/spike-results/eval_spanish_word_types_qwen17b_results.json
"""

from __future__ import annotations

import json
import sys
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research.evaluation.sentence.expected_form import normalize_token, tokenize
from research.evaluation.sentence.languagetool import LanguageToolGrammarEvaluator
from research.generation.baseline_hf import (
    _is_qwen3,
    _load_model,
    _strip_thinking,
    parse_candidates_lenient,
)

MODEL_ID = "Qwen/Qwen3-1.7B"
N_PER_CELL = 5
TEMPERATURE = 0.7
MAX_NEW_TOKENS = 360

_OUTPUT = (
    Path(__file__).resolve().parents[2]
    / "docs/spike-results/eval_spanish_word_types_qwen17b_results.json"
)

SYSTEM_MESSAGE = (
    "You are a Spanish language tutor generating example sentences for "
    "beginners. Each sentence must be complete and grammatical, with correct "
    "gender and number agreement throughout. Sentences should read naturally "
    "(roughly 5–12 words, but write what is most natural — do not pad). "
    "Always respond with valid JSON."
)


@dataclass
class Cell:
    id: str
    pos: str  # "noun" | "adjective" | "adverb" | "participle"
    lemma: str
    expected_form: str
    translation: str
    gender: str | None = None
    number: str | None = None
    example_noun: str | None = None  # for adjectives/participles, optional hint
    invariant_gender: bool = False  # for adjectives like "grande", "feliz"
    notes: str = ""


CELLS: list[Cell] = [
    # ───── Nouns ─────
    Cell(
        id="noun_casa_fs",
        pos="noun",
        lemma="casa",
        expected_form="casa",
        translation="house",
        gender="feminine",
        number="singular",
    ),
    Cell(
        id="noun_casas_fp",
        pos="noun",
        lemma="casa",
        expected_form="casas",
        translation="house",
        gender="feminine",
        number="plural",
    ),
    Cell(
        id="noun_libro_ms",
        pos="noun",
        lemma="libro",
        expected_form="libro",
        translation="book",
        gender="masculine",
        number="singular",
    ),
    Cell(
        id="noun_libros_mp",
        pos="noun",
        lemma="libro",
        expected_form="libros",
        translation="book",
        gender="masculine",
        number="plural",
    ),
    Cell(
        id="noun_problema_ms",
        pos="noun",
        lemma="problema",
        expected_form="problema",
        translation="problem",
        gender="masculine",
        number="singular",
        notes="deceptive: ends in -a but masculine",
    ),
    Cell(
        id="noun_mano_fs",
        pos="noun",
        lemma="mano",
        expected_form="mano",
        translation="hand",
        gender="feminine",
        number="singular",
        notes="deceptive: ends in -o but feminine",
    ),
    # ───── Adjectives ─────
    Cell(
        id="adj_rojo_ms",
        pos="adjective",
        lemma="rojo",
        expected_form="rojo",
        translation="red",
        gender="masculine",
        number="singular",
        example_noun="libro",
    ),
    Cell(
        id="adj_roja_fs",
        pos="adjective",
        lemma="rojo",
        expected_form="roja",
        translation="red",
        gender="feminine",
        number="singular",
        example_noun="casa",
    ),
    Cell(
        id="adj_rojos_mp",
        pos="adjective",
        lemma="rojo",
        expected_form="rojos",
        translation="red",
        gender="masculine",
        number="plural",
        example_noun="libros",
    ),
    Cell(
        id="adj_rojas_fp",
        pos="adjective",
        lemma="rojo",
        expected_form="rojas",
        translation="red",
        gender="feminine",
        number="plural",
        example_noun="manzanas",
    ),
    Cell(
        id="adj_pequeno_ms",
        pos="adjective",
        lemma="pequeño",
        expected_form="pequeño",
        translation="small",
        gender="masculine",
        number="singular",
        example_noun="perro",
    ),
    Cell(
        id="adj_pequena_fs",
        pos="adjective",
        lemma="pequeño",
        expected_form="pequeña",
        translation="small",
        gender="feminine",
        number="singular",
        example_noun="mesa",
    ),
    Cell(
        id="adj_pequenos_mp",
        pos="adjective",
        lemma="pequeño",
        expected_form="pequeños",
        translation="small",
        gender="masculine",
        number="plural",
        example_noun="niños",
    ),
    Cell(
        id="adj_pequenas_fp",
        pos="adjective",
        lemma="pequeño",
        expected_form="pequeñas",
        translation="small",
        gender="feminine",
        number="plural",
        example_noun="flores",
    ),
    Cell(
        id="adj_grande_s",
        pos="adjective",
        lemma="grande",
        expected_form="grande",
        translation="big",
        number="singular",
        invariant_gender=True,
    ),
    Cell(
        id="adj_grandes_p",
        pos="adjective",
        lemma="grande",
        expected_form="grandes",
        translation="big",
        number="plural",
        invariant_gender=True,
    ),
    Cell(
        id="adj_feliz_s",
        pos="adjective",
        lemma="feliz",
        expected_form="feliz",
        translation="happy",
        number="singular",
        invariant_gender=True,
    ),
    Cell(
        id="adj_felices_p",
        pos="adjective",
        lemma="feliz",
        expected_form="felices",
        translation="happy",
        number="plural",
        invariant_gender=True,
    ),
    # ───── Adverbs ─────
    Cell(
        id="adv_rapidamente",
        pos="adverb",
        lemma="rápidamente",
        expected_form="rápidamente",
        translation="quickly",
    ),
    Cell(
        id="adv_lentamente",
        pos="adverb",
        lemma="lentamente",
        expected_form="lentamente",
        translation="slowly",
    ),
    Cell(
        id="adv_ayer",
        pos="adverb",
        lemma="ayer",
        expected_form="ayer",
        translation="yesterday",
    ),
    Cell(
        id="adv_siempre",
        pos="adverb",
        lemma="siempre",
        expected_form="siempre",
        translation="always",
    ),
    # ───── Past participles used as adjectives ─────
    Cell(
        id="part_cerrada_fs",
        pos="participle",
        lemma="cerrar",
        expected_form="cerrada",
        translation="closed",
        gender="feminine",
        number="singular",
        example_noun="puerta",
    ),
    Cell(
        id="part_abiertas_fp",
        pos="participle",
        lemma="abrir",
        expected_form="abiertas",
        translation="open",
        gender="feminine",
        number="plural",
        example_noun="ventanas",
    ),
    Cell(
        id="part_roto_ms",
        pos="participle",
        lemma="romper",
        expected_form="roto",
        translation="broken",
        gender="masculine",
        number="singular",
        example_noun="vaso",
    ),
]


# ──────────────────────────── prompt building ────────────────────────────

_ARTICLE_BY_GENDER_NUMBER: dict[tuple[str, str], list[str]] = {
    ("masculine", "singular"): ["el", "un", "este", "ese", "aquel", "mi", "tu", "su"],
    ("feminine", "singular"): ["la", "una", "esta", "esa", "aquella", "mi", "tu", "su"],
    ("masculine", "plural"): ["los", "unos", "estos", "esos", "aquellos", "mis", "tus", "sus"],
    ("feminine", "plural"): ["las", "unas", "estas", "esas", "aquellas", "mis", "tus", "sus"],
}


def build_noun_prompt(cell: Cell, n: int) -> str:
    gender = cell.gender
    number = cell.number
    return (
        f"You generate Spanish example sentences for vocabulary practice.\n"
        f'Target word (lemma): "{cell.lemma}" (English: "{cell.translation}") — '
        f"Spanish noun, {gender}, {number}.\n\n"
        f"Constraints:\n"
        f"  - The noun must appear in the form \"{cell.expected_form}\" "
        f"({number}).\n"
        f"  - It must appear with its correct determiner "
        f"(el/la/los/las or un/una/unos/unas or a demonstrative/possessive) "
        f"matching its gender ({gender}) and number ({number}).\n"
        f"  - The noun must be embedded in a natural sentence with at least a "
        f"verb and a modifier or short clause — do not return a bare noun "
        f"phrase.\n\n"
        f"Produce {n} complete, natural Spanish sentences with English "
        f"translations. Reply ONLY as JSON in this shape:\n"
        '{"candidates":[{"sentence":"...","translation":"..."}, ...]}'
    )


def build_adjective_prompt(cell: Cell, n: int) -> str:
    parts: list[str] = []
    parts.append("You generate Spanish example sentences for vocabulary practice.")
    if cell.invariant_gender:
        parts.append(
            f'Target word (lemma): "{cell.lemma}" (English: "{cell.translation}") '
            f"— Spanish adjective, {cell.number} "
            f"(this adjective has the same form for masculine and feminine)."
        )
    else:
        parts.append(
            f'Target word (lemma): "{cell.lemma}" (English: "{cell.translation}") '
            f"— Spanish adjective, {cell.gender}, {cell.number}."
        )
    parts.append("")
    parts.append("Constraints:")
    parts.append(
        f'  - The adjective must appear in the form "{cell.expected_form}" '
        f"in the sentence."
    )
    if cell.invariant_gender:
        parts.append(
            f"  - It must modify a noun and agree with it in number "
            f"({cell.number}). The adjective form is the same for masculine "
            f"and feminine nouns."
        )
    else:
        parts.append(
            f"  - It must modify a noun and agree with it in gender "
            f"({cell.gender}) and number ({cell.number})."
        )
    parts.append(
        "  - The noun being modified must be explicitly written in the "
        "sentence (with its determiner). Do not drop the noun."
    )
    if cell.example_noun:
        parts.append(
            f'  - You may use a noun like "{cell.example_noun}" or any other '
            f"appropriate {cell.gender or 'matching'} {cell.number} noun."
        )
    parts.append("")
    parts.append(
        f"Produce {n} complete, natural Spanish sentences with English "
        f"translations. Reply ONLY as JSON in this shape:"
    )
    parts.append('{"candidates":[{"sentence":"...","translation":"..."}, ...]}')
    return "\n".join(parts)


def build_adverb_prompt(cell: Cell, n: int) -> str:
    return (
        f"You generate Spanish example sentences for vocabulary practice.\n"
        f'Target word: "{cell.expected_form}" (English: "{cell.translation}") — '
        f"Spanish adverb (invariant; same form everywhere).\n\n"
        f"Constraints:\n"
        f'  - The adverb "{cell.expected_form}" must appear in the sentence.\n'
        f"  - It must modify a verb (or the whole clause). It should not stand "
        f"alone or be used as an interjection.\n"
        f"  - The sentence must contain a subject and a finite verb.\n\n"
        f"Produce {n} complete, natural Spanish sentences with English "
        f"translations. Reply ONLY as JSON in this shape:\n"
        '{"candidates":[{"sentence":"...","translation":"..."}, ...]}'
    )


def build_participle_prompt(cell: Cell, n: int) -> str:
    return (
        f"You generate Spanish example sentences for vocabulary practice.\n"
        f'Target word: "{cell.expected_form}" (English: "{cell.translation}") — '
        f"Spanish past participle of \"{cell.lemma}\" used as an adjective, "
        f"{cell.gender}, {cell.number}.\n\n"
        f"Constraints:\n"
        f'  - The past participle must appear in the form "{cell.expected_form}".\n'
        f"  - It must agree in gender ({cell.gender}) and number ({cell.number}) "
        f"with the noun it modifies or is linked to (via 'ser' or 'estar').\n"
        f"  - The noun must be explicitly written in the sentence with its "
        f"determiner.\n"
        + (
            f'  - You may use a noun like "{cell.example_noun}" or another '
            f"appropriate {cell.gender} {cell.number} noun.\n"
            if cell.example_noun
            else ""
        )
        + f"\nProduce {n} complete, natural Spanish sentences with English "
        f"translations. Reply ONLY as JSON in this shape:\n"
        '{"candidates":[{"sentence":"...","translation":"..."}, ...]}'
    )


def build_prompt(cell: Cell, n: int) -> str:
    if cell.pos == "noun":
        return build_noun_prompt(cell, n)
    if cell.pos == "adjective":
        return build_adjective_prompt(cell, n)
    if cell.pos == "adverb":
        return build_adverb_prompt(cell, n)
    if cell.pos == "participle":
        return build_participle_prompt(cell, n)
    raise ValueError(f"Unknown pos: {cell.pos!r}")


# ──────────────────────────── inference ────────────────────────────


def call_model(prompt: str) -> str:
    import torch

    tokenizer, model = _load_model(MODEL_ID)
    messages = [
        {"role": "system", "content": SYSTEM_MESSAGE},
        {"role": "user", "content": prompt},
    ]
    template_kwargs: dict[str, Any] = {
        "add_generation_prompt": True,
        "tokenize": False,
    }
    if _is_qwen3(MODEL_ID):
        template_kwargs["enable_thinking"] = False
    text = tokenizer.apply_chat_template(messages, **template_kwargs)
    inputs = tokenizer(text, return_tensors="pt").to(model.device)
    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=True,
            temperature=TEMPERATURE,
            top_p=0.9,
            pad_token_id=tokenizer.eos_token_id,
        )
    prompt_len = inputs["input_ids"].shape[1]
    raw = tokenizer.decode(output[0][prompt_len:], skip_special_tokens=True)
    return _strip_thinking(raw)


# ──────────────────────────── scoring ────────────────────────────


def _nfc_casefold(text: str) -> str:
    return unicodedata.normalize("NFC", text).casefold()


def expected_form_hit(sentence: str, expected_form: str) -> bool:
    target = _nfc_casefold(expected_form)
    return any(_nfc_casefold(t) == target for t in tokenize(sentence))


def article_agreement_hit(sentence: str, cell: Cell) -> bool | None:
    """For noun/participle cells with gender+number, check the noun is
    preceded by an article (within 1-2 tokens) that matches gender+number."""
    if cell.pos not in {"noun", "participle"}:
        return None
    if not cell.gender or not cell.number:
        return None
    target_noun = _nfc_casefold(
        cell.expected_form if cell.pos == "noun" else (cell.example_noun or "")
    )
    if not target_noun:
        return None
    tokens = [_nfc_casefold(t) for t in tokenize(sentence)]
    correct_articles = {
        _nfc_casefold(a)
        for a in _ARTICLE_BY_GENDER_NUMBER.get((cell.gender, cell.number), [])
    }
    if not correct_articles:
        return None
    for i, tok in enumerate(tokens):
        if tok == target_noun:
            # check up to 2 tokens before for a matching article
            for j in range(max(0, i - 2), i):
                if tokens[j] in correct_articles:
                    return True
    return False


# ──────────────────────────── main ────────────────────────────


def run() -> dict[str, Any]:
    lt = LanguageToolGrammarEvaluator()
    results: list[dict[str, Any]] = []
    t_start = time.perf_counter()

    for idx, cell in enumerate(CELLS, 1):
        print(
            f"[{idx}/{len(CELLS)}] {cell.id} ({cell.pos}) "
            f"expected={cell.expected_form}...",
            flush=True,
        )
        prompt = build_prompt(cell, N_PER_CELL)
        t0 = time.perf_counter()
        raw = call_model(prompt)
        latency = round(time.perf_counter() - t0, 2)
        cands, parse_mode = parse_candidates_lenient(raw)
        scored: list[dict[str, Any]] = []
        for c in cands:
            sentence = c["sentence"]
            ef_pass = expected_form_hit(sentence, cell.expected_form)
            article_pass = article_agreement_hit(sentence, cell)
            grammar_result = lt.evaluate(
                sentence=sentence,
                translation=c["translation"],
                constraints={"target_language": "es"},
            )
            scored.append(
                {
                    "sentence": sentence,
                    "translation": c["translation"],
                    "ef_pass": ef_pass,
                    "article_agreement_pass": article_pass,
                    "grammar_pass": bool(grammar_result.score >= 1.0),
                    "grammar_matches": (grammar_result.details or {}).get(
                        "matches", []
                    ),
                }
            )
        n = len(scored)
        results.append(
            {
                "cell": {
                    "id": cell.id,
                    "pos": cell.pos,
                    "lemma": cell.lemma,
                    "expected_form": cell.expected_form,
                    "translation": cell.translation,
                    "gender": cell.gender,
                    "number": cell.number,
                    "example_noun": cell.example_noun,
                    "invariant_gender": cell.invariant_gender,
                    "notes": cell.notes,
                },
                "prompt": prompt,
                "raw": raw,
                "parse_mode": parse_mode,
                "latency_s": latency,
                "n_candidates": n,
                "candidates": scored,
                "ef_rate": (
                    round(sum(1 for s in scored if s["ef_pass"]) / n, 3) if n else None
                ),
                "grammar_rate": (
                    round(sum(1 for s in scored if s["grammar_pass"]) / n, 3)
                    if n
                    else None
                ),
                "article_agreement_rate": (
                    round(
                        sum(1 for s in scored if s["article_agreement_pass"]) / n,
                        3,
                    )
                    if n and any(s["article_agreement_pass"] is not None for s in scored)
                    else None
                ),
            }
        )

    elapsed = round(time.perf_counter() - t_start, 1)
    print(f"\nDone in {elapsed}s")

    return {
        "model_id": MODEL_ID,
        "temperature": TEMPERATURE,
        "n_per_cell": N_PER_CELL,
        "system": SYSTEM_MESSAGE,
        "elapsed_s": elapsed,
        "results": results,
    }


def main() -> None:
    data = run()
    _OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    _OUTPUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {_OUTPUT}")


if __name__ == "__main__":
    main()
