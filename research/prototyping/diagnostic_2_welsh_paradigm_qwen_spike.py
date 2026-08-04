#!/usr/bin/env python3
"""Diagnostic 2A — Welsh paradigm isolation on welsh_transfer_n10.

Full six-person paradigm tables (Spanish 2A style), separate by construction:

- Synthetic: 10 verbs × 3 tenses → 30 tables (180 finite forms)
- Periphrastic: 10 verbs × 4 tenses → 40 tables (240 aux[+particle]+VN packages)

Gold from ``research/benchmarks/welsh_transfer_n10.yaml``.

Run:
  python3 -m research.prototyping.diagnostic_2_welsh_paradigm_qwen_spike --dry-run
  python3 -m research.prototyping.diagnostic_2_welsh_paradigm_qwen_spike \\
      --models qwen17b --limit 2
  python3 -m research.prototyping.diagnostic_2_welsh_paradigm_qwen_spike \\
      --models gpt55   # OpenAI frontier ceiling (same prompts)
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research.evaluation.paradigm_slot_scoring import (
    first_token,
    normalize_form,
)
from research.generation.baseline_hf import (
    ChatGenerationSpec,
    DEFAULT_HF_BATCH_SIZE,
    _strip_thinking,
    generate_chat_batch,
    unload_model,
)

_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_BENCHMARK = _ROOT / "benchmarks" / "welsh_transfer_n10.yaml"
_DEFAULT_OUT = (
    _ROOT / "welsh" / "manifests" / "eval_diagnostic_2a_welsh_n10_qwen17b_results.json"
)

QWEN_MODELS: dict[str, str] = {
    "qwen06b": "Qwen/Qwen3-0.6B",
    "qwen17b": "Qwen/Qwen3-1.7B",
    "qwen4b": "Qwen/Qwen3-4B",
}

# Frontier OpenAI ceiling (same prompts/scoring as HF arms).
OPENAI_MODELS: dict[str, str] = {
    "gpt55": "gpt-5.5",
}

ALL_MODELS: dict[str, str] = {**QWEN_MODELS, **OPENAI_MODELS}

PERSON_ORDER: tuple[tuple[str, str], ...] = (
    ("1st", "singular"),
    ("2nd", "singular"),
    ("3rd", "singular"),
    ("1st", "plural"),
    ("2nd", "plural"),
    ("3rd", "plural"),
)

PERSON_LABELS: tuple[str, ...] = ("fi", "ti", "e/hi", "ni", "chi", "nhw")

SUBJECT_HINTS: dict[tuple[str, str], str] = {
    ("1st", "singular"): "I",
    ("2nd", "singular"): "you singular",
    ("3rd", "singular"): "he/she",
    ("1st", "plural"): "we",
    ("2nd", "plural"): "you plural",
    ("3rd", "plural"): "they",
}

# Longer labels first so ``e/hi`` wins over ``e``.
_WELSH_LINE_LABELS: tuple[tuple[str, int], ...] = (
    ("e/hi", 2),
    ("nhw", 5),
    ("chi", 4),
    ("ni", 3),
    ("fi", 0),
    ("ti", 1),
    ("e", 2),
    ("hi", 2),
    ("ef", 2),
    ("o", 2),
)

TENSE_PHRASE: dict[str, str] = {
    "present": "present tense (presennol)",
    "past": "past / preterite tense (gorffennol)",
    "imperfect": "imperfect tense (amherffaith)",
    "future": "future tense (dyfodol)",
}

SYSTEM_MESSAGE = (
    "You are a Welsh conjugation assistant. "
    "Follow the instruction exactly and output only the requested verb forms."
)

SCORING_VERSION = "welsh_paradigm_v3"
PROMPT_VERSION = "welsh_2a_v1"

_EDGE_PUNCT = ".,;:!?\"'«»""''¡¿()[]{}"
_TOKEN_RE = re.compile(r"[\w'\-]+", flags=re.UNICODE)

# Optional subject pronouns the model may insert into peri packages.
_OPTIONAL_SUBJECTS = frozenset({
    "fi", "i", "ti", "di", "e", "hi", "ef", "o", "fe", "fo",
    "ni", "chi", "nhw", "nhwy",
})

# Extra colloquial aux surfaces not always listed in benchmark alts.
_COLLOQUIAL_AUX: dict[str, tuple[str, ...]] = {
    "rwyf": ("dw", "ydw", "rwy", "wi", "ydwyf", "wyf"),
    "rwyt": ("wyt",),
    # Formal rydym / everyday rydyn ni ("we are")
    "rydym": ("dyn", "dan", "ydyn", "ydym", "ŷm", "rydyn"),
    "rydych": ("dych", "dach", "ydych", "ych"),
    "mae": ("ydy", "yw"),
    "maen": ("ydyn",),
    # Formal roeddem / everyday roedden ni ("we were")
    "roeddem": ("oeddem", "oeddan", "roedden", "oedden"),
    "gwnes": ("wnes", "nes", "gwneuthum", "gwnaes"),
    "gwnêst": ("wnest", "nest", "gwnest", "gwnaethost"),
    "nath": ("wnaeth", "naeth", "gwnaeth"),
    "gwnaethom": ("wnaethom", "wnaethon", "naethom", "gwnaethon"),
    "gwnaethoch": ("wnaethoch", "naethoch"),
    "gwnaethon": ("wnaethon", "naethon", "gwnaethant"),
}

# rhoi ↔ rhoddi stem doublet: same meaning "give", alternate citation stem.
# Ordered fi, ti, e/hi, ni, chi, nhw (same as PERSON_ORDER).
_RHODDI_PARADIGM: dict[str, tuple[str, ...]] = {
    "present": (
        "rhoddaf",
        "rhoddi",
        "rhodda",
        "rhoddwn",
        "rhoddwch",
        "rhoddant",
    ),
    "past": (
        "rhoddais",
        "rhoddaist",
        "rhoddodd",
        "rhoddasom",
        "rhoddasoch",
        "rhoddasant",
    ),
    "imperfect": (
        "rhoddwn",
        "rhoddit",
        "rhoddai",
        "rhoddem",
        "rhoddech",
        "rhoddent",
    ),
}


def _soft_mutate_initial(form: str) -> str | None:
    """Common soft-mutation of an initial consonant (Welsh)."""
    if not form:
        return None
    low = form.casefold()
    rules = (
        ("rh", "r"),
        ("ll", "l"),
        ("ph", "f"),
        ("th", "dd"),
        ("ch", "j"),  # unused sentinel; skip
        ("p", "b"),
        ("t", "d"),
        ("c", "g"),
        ("b", "f"),
        ("d", "dd"),
        ("g", ""),
        ("m", "f"),
    )
    for src, dst in rules:
        if src == "ch":
            continue
        if low.startswith(src):
            return dst + low[len(src) :]
    return None


def _expand_aux_surfaces(slot: SlotGold) -> set[str]:
    out = set(_acceptable_auxes(slot))
    bases = set(out)
    if slot.expected_aux:
        bases.add(normalize_form(slot.expected_aux))
    extra: set[str] = set()
    for a in bases:
        sm = _soft_mutate_initial(a)
        if sm:
            extra.add(normalize_form(sm))
        for colloq in _COLLOQUIAL_AUX.get(a, ()):
            extra.add(normalize_form(colloq))
        # casefold key lookup for accented forms
        for colloq in _COLLOQUIAL_AUX.get(a.casefold(), ()):
            extra.add(normalize_form(colloq))
    out |= {x for x in extra if x}
    return out


def _normalize_peri_tokens(parsed: str) -> list[str]:
    """Tokenize a peri package; expand ``i'n`` → ``i yn``, drop subject pronouns."""
    raw_toks = tokenize_welsh(parsed)
    expanded: list[str] = []
    for tok in raw_toks:
        n = normalize_form(tok)
        # clitic linker: i'n / ti'n / 'n → keep host (if any) + yn
        if n.endswith("'n") or n.endswith("’n"):
            host = n[:-2]
            if host and host not in _OPTIONAL_SUBJECTS:
                expanded.append(host)
            expanded.append("yn")
            continue
        if n in {"'n", "’n"}:
            expanded.append("yn")
            continue
        expanded.append(n)
    # drop optional subjects so "bydda i yn rhoi" ≈ "bydda yn rhoi"
    return [t for t in expanded if t not in _OPTIONAL_SUBJECTS]


@dataclass
class SlotGold:
    person: str
    number: str
    person_label: str
    expected_form: str
    expected_form_alts: list[str]
    expected_aux: str | None
    expected_aux_alts: list[str]
    particle: str | None
    cell_id: str
    tier: str | None
    zipf: float | None


@dataclass
class ParadigmCase:
    id: str
    lemma: str
    translation: str
    construction: str
    tense: str
    slots: list[SlotGold]
    prompt: str

    @property
    def person_labels(self) -> list[str]:
        return [s.person_label for s in self.slots]


def _split_alts(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [p.strip() for p in str(raw).split("|") if p.strip()]


def _canonical_package(slot: SlotGold) -> str:
    parts: list[str] = []
    if slot.expected_aux:
        parts.append(slot.expected_aux)
    if slot.particle:
        parts.append(slot.particle)
    parts.append(slot.expected_form)
    return " ".join(parts)


def _acceptable_packages(slot: SlotGold) -> set[str]:
    """All gold surface packages (aux/form alts × particle)."""
    forms = [slot.expected_form, *slot.expected_form_alts]
    if not slot.expected_aux:
        return {normalize_form(f) for f in forms}
    auxes = [slot.expected_aux, *slot.expected_aux_alts]
    out: set[str] = set()
    for aux in auxes:
        for form in forms:
            if slot.particle:
                out.add(normalize_form(f"{aux} {slot.particle} {form}"))
            else:
                out.add(normalize_form(f"{aux} {form}"))
    return out


def _person_index(slot: SlotGold) -> int | None:
    key = (slot.person, slot.number)
    try:
        return PERSON_ORDER.index(key)
    except ValueError:
        return None


def _acceptable_forms(
    slot: SlotGold,
    *,
    lemma: str = "",
    tense: str = "",
) -> set[str]:
    out = {
        normalize_form(f)
        for f in [slot.expected_form, *slot.expected_form_alts]
        if f
    }
    # Fairness: rhoi/rhoddi citation-stem doublet (synthetic finite cells).
    if lemma.casefold() == "rhoi" and tense in _RHODDI_PARADIGM:
        idx = _person_index(slot)
        if idx is not None:
            out.add(normalize_form(_RHODDI_PARADIGM[tense][idx]))
    return out


def _acceptable_auxes(slot: SlotGold) -> set[str]:
    if not slot.expected_aux:
        return set()
    return {normalize_form(a) for a in [slot.expected_aux, *slot.expected_aux_alts]}


def build_synthetic_prompt(lemma: str, tense: str) -> str:
    tense_label = TENSE_PHRASE.get(tense, tense)
    lines = "\n".join(
        f"- {label} ({SUBJECT_HINTS[pn]})"
        for label, pn in zip(PERSON_LABELS, PERSON_ORDER, strict=True)
    )
    return (
        f'Conjugate the Welsh verb "{lemma}" in the {tense_label}, '
        "using the synthetic (inflected lexical verb) construction.\n"
        "List all six finite forms for:\n"
        f"{lines}\n"
        "Reply with only the six conjugated verb forms, one per line "
        "(optionally prefixed with the person label)."
    )


def build_periphrastic_prompt(lemma: str, tense: str) -> str:
    tense_label = TENSE_PHRASE.get(tense, tense)
    lines = "\n".join(
        f"- {label} ({SUBJECT_HINTS[pn]})"
        for label, pn in zip(PERSON_LABELS, PERSON_ORDER, strict=True)
    )
    past_note = ""
    if tense == "past":
        past_note = (
            " Use the past periphrastic with a gwneud-type auxiliary + verbnoun "
            "(no yn particle).\n"
        )
    else:
        past_note = (
            " Use the periphrastic pattern: conjugated auxiliary + yn + verbnoun "
            f'of "{lemma}".\n'
        )
    return (
        f'Give the Welsh periphrastic {tense_label} paradigm for the verb "{lemma}".\n'
        f"{past_note}"
        "List all six packages for:\n"
        f"{lines}\n"
        "Reply with only the six packages, one per line "
        "(optionally prefixed with the person label)."
    )


def load_paradigm_cases(
    benchmark_path: Path,
    *,
    limit: int | None = None,
) -> list[ParadigmCase]:
    data = yaml.safe_load(benchmark_path.read_text(encoding="utf-8"))
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    translations: dict[str, str] = {}
    for cs in data["constraint_sets"]:
        lemma = cs["keyword"]
        translations[lemma] = cs.get("translation", "")
        key = (lemma, cs["construction"], cs["tense"])
        grouped[key].append(cs)

    cases: list[ParadigmCase] = []
    for (lemma, construction, tense), rows in sorted(grouped.items()):
        by_pn = {(r["person"], r["number"]): r for r in rows}
        slots: list[SlotGold] = []
        for (person, number), label in zip(PERSON_ORDER, PERSON_LABELS, strict=True):
            row = by_pn.get((person, number))
            if row is None:
                raise ValueError(
                    f"Missing cell {lemma}/{construction}/{tense}/{person}/{number}"
                )
            slots.append(
                SlotGold(
                    person=person,
                    number=number,
                    person_label=label,
                    expected_form=row["expected_form"],
                    expected_form_alts=_split_alts(row.get("expected_form_alts")),
                    expected_aux=row.get("expected_aux"),
                    expected_aux_alts=_split_alts(row.get("expected_aux_alts")),
                    particle=row.get("particle"),
                    cell_id=row.get("cell_id", ""),
                    tier=row.get("tier"),
                    zipf=float(row["zipf"]) if row.get("zipf") is not None else None,
                )
            )
        if construction == "synthetic":
            prompt = build_synthetic_prompt(lemma, tense)
        elif construction == "periphrastic":
            prompt = build_periphrastic_prompt(lemma, tense)
        else:
            raise ValueError(f"Unknown construction: {construction}")
        cases.append(
            ParadigmCase(
                id=f"{lemma}__{construction}__{tense}",
                lemma=lemma,
                translation=translations.get(lemma, ""),
                construction=construction,
                tense=tense,
                slots=slots,
                prompt=prompt,
            )
        )

    if limit is not None:
        cases = cases[:limit]
    return cases


def _line_starts_with_label(line: str, label: str) -> bool:
    low = line.casefold()
    lab = label.casefold()
    if not low.startswith(lab):
        return False
    if len(low) == len(lab):
        return True
    return low[len(lab)] in ":.,/ )-"


def _strip_person_label(line: str) -> str:
    cleaned = re.sub(r"^[-*•\d.)\s]+", "", line.strip())
    for label, _ in _WELSH_LINE_LABELS:
        if _line_starts_with_label(cleaned, label):
            return cleaned[len(label) :].lstrip(":.,/ )- ")
    return cleaned


def tokenize_welsh(text: str) -> list[str]:
    text = _strip_thinking(text)
    return _TOKEN_RE.findall(text)


def parse_welsh_slots(raw: str, *, multi_token: bool) -> list[str | None]:
    """Map model output to six ordered slots (fi … nhw)."""
    slots: list[str | None] = [None] * 6
    lines = [ln.strip() for ln in _strip_thinking(raw).splitlines() if ln.strip()]
    unlabeled: list[str] = []

    for line in lines:
        cleaned = re.sub(r"^[-*•\d.)\s]+", "", line).strip()
        matched = False
        for label, idx in _WELSH_LINE_LABELS:
            if _line_starts_with_label(cleaned, label):
                rest = cleaned[len(label) :].lstrip(":.,/ )- ")
                if multi_token:
                    toks = tokenize_welsh(rest)
                    slots[idx] = " ".join(toks) if toks else None
                else:
                    slots[idx] = first_token(rest) if rest else None
                matched = True
                break
        if not matched:
            unlabeled.append(cleaned)

    if all(s is None for s in slots) and lines:
        for i, line in enumerate(lines[:6]):
            rest = _strip_person_label(line)
            if multi_token:
                toks = tokenize_welsh(rest)
                slots[i] = " ".join(toks) if toks else None
            else:
                slots[i] = first_token(rest) if rest else None
        return slots

    empty = [i for i, s in enumerate(slots) if s is None]
    for idx, line in zip(empty, unlabeled, strict=False):
        rest = _strip_person_label(line)
        if multi_token:
            toks = tokenize_welsh(rest)
            slots[idx] = " ".join(toks) if toks else None
        else:
            slots[idx] = first_token(rest) if rest else None
    return slots


def _package_components_ok(
    parsed: str | None,
    slot: SlotGold,
    *,
    lemma: str = "",
    tense: str = "",
) -> dict[str, bool]:
    if not parsed:
        return {"aux_ok": False, "particle_ok": False, "form_ok": False, "package_ok": False}
    toks = _normalize_peri_tokens(parsed)
    norm = normalize_form(" ".join(toks))
    aux_surfaces = _expand_aux_surfaces(slot)
    form_surfaces = _acceptable_forms(slot, lemma=lemma, tense=tense)

    aux_ok = True
    if slot.expected_aux:
        aux_ok = any(a in toks or a == norm for a in aux_surfaces)
    particle_ok = True
    if slot.particle:
        particle_ok = normalize_form(slot.particle) in toks
    form_ok = any(f in toks or f == norm for f in form_surfaces)

    # Exact package (with alts) after pronoun/'n normalization
    package_ok = False
    for pkg in _acceptable_packages(slot):
        pkg_toks = _normalize_peri_tokens(pkg)
        if toks == pkg_toks:
            package_ok = True
            break
    # Soft package: required pieces present after normalization
    if not package_ok and aux_ok and form_ok and particle_ok:
        package_ok = True
    return {
        "aux_ok": aux_ok,
        "particle_ok": particle_ok,
        "form_ok": form_ok,
        "package_ok": package_ok,
    }


def score_paradigm(case: ParadigmCase, raw: str) -> dict[str, Any]:
    multi = case.construction == "periphrastic"
    parsed_slots = parse_welsh_slots(raw, multi_token=multi)
    per_person: list[dict[str, Any]] = []
    strict_hits = 0
    aux_hits = 0
    form_hits = 0
    particle_hits = 0
    particle_total = 0

    for label, slot, parsed in zip(
        case.person_labels, case.slots, parsed_slots, strict=True
    ):
        if multi:
            comps = _package_components_ok(
                parsed, slot, lemma=case.lemma, tense=case.tense
            )
            strict = comps["package_ok"]
            gold = _canonical_package(slot)
            if slot.particle:
                particle_total += 1
                if comps["particle_ok"]:
                    particle_hits += 1
            if comps["aux_ok"]:
                aux_hits += 1
            if comps["form_ok"]:
                form_hits += 1
            detail = {
                "person_label": label,
                "gold": gold,
                "parsed": parsed,
                "strict_match": strict,
                **comps,
            }
        else:
            parsed_norm = normalize_form(parsed) if parsed else None
            strict = (
                parsed_norm
                in _acceptable_forms(slot, lemma=case.lemma, tense=case.tense)
                if parsed_norm
                else False
            )
            gold = slot.expected_form
            form_hits += int(strict)
            detail = {
                "person_label": label,
                "gold": gold,
                "parsed": parsed,
                "strict_match": strict,
                "form_ok": strict,
                "aux_ok": None,
                "particle_ok": None,
                "package_ok": None,
            }
        if strict:
            strict_hits += 1
        per_person.append(detail)

    n = len(case.slots)
    return {
        "raw": raw.strip(),
        "parsed_slots": parsed_slots,
        "per_person": per_person,
        "strict_slots_correct": strict_hits,
        "strict_slots_total": n,
        "strict_slot_recall": round(strict_hits / n, 4) if n else None,
        "perfect_paradigm": strict_hits == n,
        "aux_slots_correct": aux_hits if multi else None,
        "form_slots_correct": form_hits,
        "particle_slots_correct": particle_hits if multi else None,
        "particle_slots_total": particle_total if multi else None,
    }


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if n <= 0:
        return None, None
    p_hat = k / n
    z2 = z * z
    denom = 1 + z2 / n
    centre = (p_hat + z2 / (2 * n)) / denom
    margin = (z / denom) * math.sqrt(p_hat * (1 - p_hat) / n + z2 / (4 * n * n))
    return max(0.0, centre - margin), min(1.0, centre + margin)


def _rate(rows: list[dict[str, Any]], *, correct_key: str, total_key: str, **filters: Any) -> dict[str, Any]:
    filtered = [
        r for r in rows if all(r["case"].get(k) == v for k, v in filters.items())
    ]
    n_total = sum(r[total_key] for r in filtered)
    k = sum(r[correct_key] for r in filtered)
    lo, hi = wilson_ci(k, n_total)
    return {
        "cases": len(filtered),
        "slots_correct": k,
        "slots_total": n_total,
        "slot_recall": round(k / n_total, 4) if n_total else None,
        "wilson_95_ci": [round(lo, 4), round(hi, 4)] if lo is not None else None,
    }


def _rate_perfect(rows: list[dict[str, Any]], **filters: Any) -> dict[str, Any]:
    filtered = [
        r for r in rows if all(r["case"].get(k) == v for k, v in filters.items())
    ]
    n = len(filtered)
    k = sum(1 for r in filtered if r.get("perfect_paradigm"))
    lo, hi = wilson_ci(k, n)
    return {
        "cases": n,
        "perfect_paradigms": k,
        "perfect_paradigm_rate": round(k / n, 4) if n else None,
        "wilson_95_ci": [round(lo, 4), round(hi, 4)] if lo is not None else None,
    }


def summarize(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"per_model": {}}
    for key, block in payload["by_model"].items():
        rows = block["results"]
        per: dict[str, Any] = {
            "overall_strict": _rate(
                rows, correct_key="strict_slots_correct", total_key="strict_slots_total"
            ),
            "overall_perfect_paradigm": _rate_perfect(rows),
            "synthetic_strict": _rate(
                rows,
                correct_key="strict_slots_correct",
                total_key="strict_slots_total",
                construction="synthetic",
            ),
            "synthetic_perfect": _rate_perfect(rows, construction="synthetic"),
            "periphrastic_strict": _rate(
                rows,
                correct_key="strict_slots_correct",
                total_key="strict_slots_total",
                construction="periphrastic",
            ),
            "periphrastic_perfect": _rate_perfect(rows, construction="periphrastic"),
            "strict_slots_histogram": dict(
                sorted(Counter(r["strict_slots_correct"] for r in rows).items())
            ),
        }
        for tense in ("present", "past", "imperfect", "future"):
            per[f"tense_{tense}_strict"] = _rate(
                rows,
                correct_key="strict_slots_correct",
                total_key="strict_slots_total",
                tense=tense,
            )
        peri_rows = [r for r in rows if r["case"]["construction"] == "periphrastic"]
        if peri_rows:
            aux_k = sum(r.get("aux_slots_correct") or 0 for r in peri_rows)
            form_k = sum(r.get("form_slots_correct") or 0 for r in peri_rows)
            part_k = sum(r.get("particle_slots_correct") or 0 for r in peri_rows)
            part_n = sum(r.get("particle_slots_total") or 0 for r in peri_rows)
            peri_slots = sum(r["strict_slots_total"] for r in peri_rows)
            per["periphrastic_aux_recall"] = round(aux_k / peri_slots, 4) if peri_slots else None
            per["periphrastic_vn_recall"] = round(form_k / peri_slots, 4) if peri_slots else None
            per["periphrastic_particle_recall"] = (
                round(part_k / part_n, 4) if part_n else None
            )
        out["per_model"][key] = per
    return out


def _case_meta(case: ParadigmCase) -> dict[str, Any]:
    return {
        "id": case.id,
        "lemma": case.lemma,
        "translation": case.translation,
        "construction": case.construction,
        "tense": case.tense,
        "person_labels": case.person_labels,
        "expected": [
            _canonical_package(s)
            if case.construction == "periphrastic"
            else s.expected_form
            for s in case.slots
        ],
        "tier": case.slots[0].tier,
        "zipf": case.slots[0].zipf,
    }


def _complete_openai(
    *,
    model: str,
    system: str,
    user: str,
    temperature: float,
    reasoning_effort: str | None,
) -> str:
    """Same chat path as frontier Fix-B ceiling (``baseline_gpt_plain._chat_once``)."""
    import os

    from openai import OpenAI

    from research.generation.baseline_gpt_plain import _chat_once

    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set")
    client = OpenAI(api_key=key)
    return _chat_once(
        client,
        model=model,
        temperature=temperature,
        reasoning_effort=reasoning_effort,
        system=system,
        user=user,
    )


def _save(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_spike(
    cases: list[ParadigmCase],
    model_keys: list[str],
    *,
    benchmark_path: Path,
    output_path: Path,
    temperature: float = 0.0,
    resume: bool = False,
    batch_size: int = DEFAULT_HF_BATCH_SIZE,
    reasoning_effort: str | None = "low",
) -> dict[str, Any]:
    payload: dict[str, Any] | None = None
    if resume and output_path.is_file():
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        print(f"Resuming from {output_path}", flush=True)

    if payload is None:
        payload = {
            "diagnostic_id": "diagnostic_2a_welsh",
            "diagnostic_number": "2A",
            "diagnostic_title": "Welsh paradigm production (full table)",
            "diagnostic_label": "Diagnostic 2A — Welsh full-paradigm production",
            "probe_mode": "diagnostic_2a",
            "prompt_version": PROMPT_VERSION,
            "scoring_version": SCORING_VERSION,
            "benchmark_path": str(benchmark_path),
            "n_verbs": len({c.lemma for c in cases}),
            "n_paradigms": len(cases),
            "n_slots": sum(len(c.slots) for c in cases),
            "person_order": [f"{p}_{n}" for p, n in PERSON_ORDER],
            "temperature": temperature,
            "reasoning_effort": reasoning_effort,
            "by_model": {},
        }

    for key in model_keys:
        if key not in ALL_MODELS:
            raise ValueError(f"Unknown model key {key!r}; known={sorted(ALL_MODELS)}")
        model_id = ALL_MODELS[key]
        is_openai = key in OPENAI_MODELS

        existing = list(payload.get("by_model", {}).get(key, {}).get("results") or [])
        done_ids = {r["case"]["id"] for r in existing}
        pending = [c for c in cases if c.id not in done_ids]
        if not pending:
            print(f"=== {key}: all {len(cases)} paradigms already done ===", flush=True)
            continue

        print(
            f"\n=== {key} ({model_id}) — {len(pending)}/{len(cases)} paradigms "
            f"({'openai' if is_openai else 'hf'}) ===",
            flush=True,
        )
        t0 = time.time()
        results = existing

        if is_openai:
            for i, case in enumerate(pending, start=1):
                raw = _complete_openai(
                    model=model_id,
                    system=SYSTEM_MESSAGE,
                    user=case.prompt,
                    temperature=temperature,
                    reasoning_effort=reasoning_effort,
                )
                scored = score_paradigm(case, raw)
                results.append({"case": _case_meta(case), **scored})
                if i % 5 == 0 or i == len(pending):
                    payload["by_model"][key] = {
                        "model_id": model_id,
                        "backend": "openai",
                        "reasoning_effort": reasoning_effort,
                        "elapsed_s": round(time.time() - t0, 2),
                        "results": results,
                    }
                    payload["summary"] = summarize(payload)
                    _save(payload, output_path)
                    print(
                        f"  [{len(results)}/{len(cases)}] "
                        f"{case.id} recall={scored['strict_slot_recall']}",
                        flush=True,
                    )
        else:
            for batch_start in range(0, len(pending), batch_size):
                chunk = pending[batch_start : batch_start + batch_size]
                specs = [
                    ChatGenerationSpec(
                        system=SYSTEM_MESSAGE,
                        user=case.prompt,
                        max_new_tokens=256,
                    )
                    for case in chunk
                ]
                raws = generate_chat_batch(
                    model_id,
                    specs,
                    temperature=temperature,
                    batch_size=batch_size,
                )
                for case, raw in zip(chunk, raws, strict=True):
                    scored = score_paradigm(case, raw)
                    results.append({"case": _case_meta(case), **scored})
                print(
                    f"  [{len(results)}/{len(cases)}] "
                    f"last recall={results[-1]['strict_slot_recall']}",
                    flush=True,
                )
            unload_model(model_id)

        elapsed = time.time() - t0
        payload["by_model"][key] = {
            "model_id": model_id,
            "backend": "openai" if is_openai else "hf",
            "reasoning_effort": reasoning_effort if is_openai else None,
            "elapsed_s": round(elapsed, 2),
            "results": results,
        }
        payload["summary"] = summarize(payload)
        _save(payload, output_path)
        s = payload["summary"]["per_model"][key]
        print(
            f"  done in {elapsed:.1f}s | "
            f"strict={s['overall_strict']['slot_recall']} "
            f"perfect={s['overall_perfect_paradigm']['perfect_paradigm_rate']} "
            f"syn={s['synthetic_strict']['slot_recall']} "
            f"peri={s['periphrastic_strict']['slot_recall']}",
            flush=True,
        )

    payload["summary"] = summarize(payload)
    _save(payload, output_path)
    return payload


def rescore_results_file(
    path: Path,
    cases: list[ParadigmCase],
    *,
    out_path: Path | None = None,
) -> dict[str, Any]:
    """Re-score saved raw outputs with the current scorer (no model calls)."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    by_id = {c.id: c for c in cases}
    payload["scoring_version"] = SCORING_VERSION
    for key, block in payload.get("by_model", {}).items():
        new_rows: list[dict[str, Any]] = []
        for row in block.get("results") or []:
            case = by_id.get(row["case"]["id"])
            if case is None:
                new_rows.append(row)
                continue
            scored = score_paradigm(case, row.get("raw") or "")
            new_rows.append({"case": _case_meta(case), **scored})
        block["results"] = new_rows
    payload["summary"] = summarize(payload)
    dest = out_path or path
    _save(payload, dest)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--benchmark",
        type=Path,
        default=_DEFAULT_BENCHMARK,
        help="Welsh transfer benchmark YAML",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=["qwen17b"],
        choices=sorted(ALL_MODELS),
        help="HF keys (qwen*) and/or OpenAI frontier key gpt55",
    )
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUT)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_HF_BATCH_SIZE)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument(
        "--reasoning-effort",
        default="low",
        help="OpenAI reasoning_effort for gpt55 (default: low, matches frontier ceiling)",
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--rescore",
        type=Path,
        default=None,
        help="Re-score an existing results JSON (uses --output if set as dest)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build cases and print prompts/golds; no model load",
    )
    args = parser.parse_args()

    cases = load_paradigm_cases(args.benchmark, limit=args.limit)
    syn = sum(1 for c in cases if c.construction == "synthetic")
    peri = sum(1 for c in cases if c.construction == "periphrastic")
    print(
        f"Loaded {len(cases)} paradigms "
        f"(synthetic={syn}, periphrastic={peri}, slots={sum(len(c.slots) for c in cases)})"
    )

    if args.dry_run:
        for case in cases[:4]:
            print("\n" + "=" * 60)
            print(case.id)
            print(case.prompt)
            print("GOLD:")
            for s in case.slots:
                print(
                    f"  {s.person_label}: {_canonical_package(s) if case.construction == 'periphrastic' else s.expected_form}"
                )
        print(f"\nDry-run OK ({len(cases)} cases).")
        return

    if args.rescore is not None:
        dest = args.output if args.output != _DEFAULT_OUT else args.rescore
        # If user passes --output explicitly different, use it; else overwrite rescore path.
        if "--output" in sys.argv:
            dest = args.output
        else:
            dest = args.rescore
        payload = rescore_results_file(args.rescore, cases, out_path=dest)
        print(f"Re-scored → {dest} (scoring_version={SCORING_VERSION})")
        for key, s in payload.get("summary", {}).get("per_model", {}).items():
            print(
                f"  {key}: strict={s['overall_strict']['slot_recall']} "
                f"perfect={s['overall_perfect_paradigm']['perfect_paradigm_rate']} "
                f"syn={s['synthetic_strict']['slot_recall']} "
                f"peri={s['periphrastic_strict']['slot_recall']} "
                f"aux={s.get('periphrastic_aux_recall')} "
                f"vn={s.get('periphrastic_vn_recall')} "
                f"particle={s.get('periphrastic_particle_recall')}"
            )
        return

    effort = args.reasoning_effort
    if effort in ("", "none", "null"):
        effort = None

    run_spike(
        cases,
        args.models,
        benchmark_path=args.benchmark,
        output_path=args.output,
        temperature=args.temperature,
        resume=args.resume,
        batch_size=args.batch_size,
        reasoning_effort=effort,
    )
    print(f"\nWrote {args.output}")


if __name__ == "__main__":
    main()
