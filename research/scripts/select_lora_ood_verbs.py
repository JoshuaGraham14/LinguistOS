#!/usr/bin/env python3
"""Select LoRA OOD Spanish verbs: 12 per Zipf tier (36 total), exclude n150.

Frequency balance is the primary design axis. Irregularity is recorded but not
used to force a 2×3 grid (irregularity varies by tense). Quality gates reject
noun/adjective-confusable lemmas and verbs with incomplete or buggy paradigms.

Usage::

    python -m research.scripts.select_lora_ood_verbs
"""

from __future__ import annotations

import argparse
import csv
import random
import re
from collections import Counter
from pathlib import Path

from research.evaluation.lexicon.frequency import (
    _actual_es_form,
    _conjugate_es,
    _strip_pronoun,
    in_census,
    is_irregular,
    tier,
    verb_zipf,
    verbs_in_tier,
)

INDICATIVE_TENSES = ("present", "preterite", "imperfect", "future", "conditional")
PERSON_NUMBER_SLOTS = (
    ("1st", "singular", "yo"),
    ("2nd", "singular", "tú"),
    ("3rd", "singular", "él/ella"),
    ("1st", "plural", "nosotros"),
    ("2nd", "plural", "vosotros"),
    ("3rd", "plural", "ellos"),
)
ES_ENDINGS = ("ar", "er", "ir")
EXPERIMENT_ID = "lora_ood"


def _es_ending(verb: str) -> str | None:
    for ending in ES_ENDINGS:
        if verb.endswith(ending):
            return ending
    return None


def _es_participle(verb: str) -> str | None:
    data = _conjugate_es(verb)
    if data is None:
        return None
    entries = data["moods"].get("participo", {}).get("participo", [])
    for entry in entries:
        chunks = entry.get("c", [])
        if chunks:
            return _strip_pronoun(chunks[0])
    return None


def _es_preterite_1sg_ok(verb: str) -> bool:
    pret = _actual_es_form(verb, "preterite", "1st", "singular")
    if pret is None:
        return False
    if pret.endswith("ía"):
        return False
    return True


def _write_manifest(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "verb", "lang", "cell_id", "zipf", "tier", "irregular_probed", "in_census",
        "probed_tense", "probed_person", "probed_number",
        "gold_past_1sg", "gold_past_1sg_alts", "gold_participle", "gold_participle_alts",
        "ending", "seed", "experiment",
    ]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def manifest_row_for_verb(
    verb: str,
    lang: str,
    cell_id: str,
    *,
    seed: int = 43,
    experiment: str = EXPERIMENT_ID,
) -> dict[str, str]:
    z = verb_zipf(verb, lang)
    t = tier(verb, lang)
    pret = _actual_es_form(verb, "preterite", "1st", "singular")
    part = _es_participle(verb)
    ending = _es_ending(verb) or ""
    if pret is None or part is None:
        raise RuntimeError(f"verbecc missing forms for {verb!r}")
    irr = is_irregular(verb, "preterite", "es", "1st", "singular")
    return {
        "verb": verb,
        "lang": lang,
        "cell_id": cell_id,
        "zipf": f"{z:.3f}",
        "tier": t,
        "in_census": "yes" if in_census(verb, lang) else "no",
        "irregular_probed": "yes" if irr else "no",
        "probed_tense": "preterite",
        "probed_person": "1st",
        "probed_number": "singular",
        "gold_past_1sg": pret,
        "gold_past_1sg_alts": "",
        "gold_participle": part,
        "gold_participle_alts": "",
        "ending": ending,
        "seed": str(seed),
        "experiment": experiment,
    }

ROOT = Path(__file__).resolve().parents[2]
N150_MANIFEST = (
    ROOT
    / "research"
    / "evaluation"
    / "lexicon"
    / "experiment_verbs"
    / "manifest_diagnostic_2_paradigm_n150.csv"
)
DEFAULT_OUT = (
    ROOT
    / "research"
    / "evaluation"
    / "lexicon"
    / "experiment_verbs"
    / "manifest_lora_ood_n36.csv"
)

TIERS = ("high", "mid", "low")
PER_TIER = 12
SEED = 43

# Homographs / denominals / adj-like lemmas that are weak sentence targets
# (easily read as nouns/adjectives, odd drill verbs, or meta-linguistic).
_ES_BLOCKED: frozenset[str] = frozenset(
    {
        # colour / adj / noun-leaning
        "claro",
        "fresco",
        "seco",
        "completo",
        "directo",
        "recto",
        "plano",
        "lleno",
        "vacio",
        "vacío",
        "solo",
        "sólido",
        "solido",
        "firme",
        "libre",
        "igual",
        "mejor",
        "peor",
        "mayor",
        "menor",
        "primer",
        "segundo",
        "tercero",
        # body / concrete nouns used as denominal verbs
        "mano",
        "cara",
        "casa",
        "agua",
        "oro",
        "plata",
        "papel",
        "radio",
        "motor",
        "piano",
        "teatro",
        "doctor",
        "guerra",
        "paz",
        # meta / orthography oddballs
        "verbelear",
        "españolizar",
        "castellanizar",
        "yacer",
        "raer",
        "roer",
        # quality rejects from first OOD draft (buggy forms / unsuitable)
        "erar",  # spurious high-Zipf lemma
        "incluir",  # verbecc participle → incluso
        "suprimir",  # verbecc participle → supreso
        "podrir",  # pret1sg podrí (should be pudrí)
        "eyacular",  # unsuitable for published benchmark
        "chinchar",  # colloquial / unsuitable
        "soler",  # participle confusion
        "juntar",  # participle → junto
        "salvar",  # participle → salvo
        "valer",  # participle → valido
        "veer",  # nonstandard
        "ademar",
        "aguar",
        "vivar",
        "mayar",
        "penar",
        "escolar",
        "historiar",
        "justiciar",
        "hermanar",
        "amigar",
        "listar",
        "manar",
        "sitiar",
        "fechar",
        "respectar",
        "pajear",
        "follar",
        "culear",
        "omitir",
        "afligir",
    }
)

# Manual curated swaps after auto-sample (tier-preserving). Documented for
# reproducibility: obscure/awkward lemmas → clearer same-tier verbs.
CURATED_SWAPS: dict[str, str] = {
    "malcriar": "balbucear",
    "chalar": "amonestar",
    "esquilar": "tararear",
    "ingeniar": "elogiar",
    "despuntar": "reanimar",
    "saber": "hablar",  # rebalance: drop deep multi-tense irregular from high OOD
}


def _load_exclude(path: Path) -> set[str]:
    with path.open(encoding="utf-8", newline="") as f:
        return {row["verb"] for row in csv.DictReader(f) if row.get("lang", "es") == "es"}


def _looks_noun_or_adj(verb: str) -> bool:
    if verb in _ES_BLOCKED:
        return True
    # Denominal -ajear verbs (homenajear, chantajear, …) are weak drill targets.
    return verb.endswith("ajear")


def _participle_surface_ok(part: str) -> bool:
    """Reject common verbecc confusions (incluso, junto, salvo, …)."""
    if not part:
        return False
    p = part.lower()
    # Canonical Spanish participle endings (incl. irregular -to/-so/-cho).
    if not re.search(r"(ado|ido|to|so|cho)$", p):
        return False
    # Observed verbecc noun/adv confusions
    if p in {"incluso", "junto", "salvo", "solido", "sólido", "valido", "válido", "omiso", "aflicto"}:
        return False
    return True


def _paradigm_ok(verb: str) -> tuple[bool, str]:
    """Return (ok, reason). Requires full 30 indicative + participle forms."""
    if _looks_noun_or_adj(verb):
        return False, "noun_adj_like"
    if verb in _ES_BLOCKED:
        return False, "blocked"
    if not _es_preterite_1sg_ok(verb):
        return False, "bad_preterite_1sg"
    data = _conjugate_es(verb)
    if data is None:
        return False, "no_conjugate"
    part = _es_participle(verb)
    if not part or not re.fullmatch(r"[A-Za-zÁÉÍÓÚÜáéíóúüñÑ]+", part):
        return False, "bad_participle"
    if not _participle_surface_ok(part):
        return False, f"bad_participle_surface:{part}"
    for tense in INDICATIVE_TENSES:
        for person, number, _label in PERSON_NUMBER_SLOTS:
            form = _actual_es_form(verb, tense, person, number)
            if not form:
                return False, f"missing:{tense}/{person}/{number}"
            if not re.fullmatch(r"[A-Za-zÁÉÍÓÚÜáéíóúüñÑ]+", form):
                return False, f"junk_form:{tense}/{person}/{number}:{form}"
            if "ach" in form and verb.endswith("cer") and "ach" not in verb:
                return False, f"verbecc_garbage:{form}"
    yo = _actual_es_form(verb, "present", "1st", "singular")
    if yo == verb:
        return False, "present_1sg_eq_infinitive"
    # podrir bug: pret 1sg should be pudrí, not podrí
    pret = _actual_es_form(verb, "preterite", "1st", "singular")
    if verb == "podrir" or (pret and pret.endswith("odrí") and yo and yo.startswith("pud")):
        return False, "bad_stem_change_preterite"
    return True, "ok"


def _score_quality(verb: str) -> float:
    """Higher is better among accepted candidates (prefer clear verbal lemmas)."""
    z = verb_zipf(verb, "es")
    ending = _es_ending(verb) or ""
    # Mild preference: -ar (most productive drill verbs), longer stems (less stubby).
    bonus = 0.0
    if ending == "ar":
        bonus += 0.05
    elif ending == "er":
        bonus += 0.02
    bonus += min(0.1, 0.01 * max(0, len(verb) - 5))
    return z + bonus


def _candidates_for_tier(tier_name: str, exclude: set[str]) -> list[str]:
    pool = []
    for v in verbs_in_tier(tier_name, "es"):
        if v in exclude or v in _ES_BLOCKED:
            continue
        ok, _reason = _paradigm_ok(v)
        if ok:
            pool.append(v)
    pool.sort(key=_score_quality, reverse=True)
    return pool


def _balanced_pick(
    pool: list[str],
    n: int,
    rng: random.Random,
) -> list[str]:
    """Pick n verbs, spreading -ar/-er/-ir when possible; shuffle within ending."""
    by_ending: dict[str, list[str]] = {"ar": [], "er": [], "ir": [], "other": []}
    for v in pool:
        by_ending[_es_ending(v) or "other"].append(v)
    for e in by_ending:
        rng.shuffle(by_ending[e])

    picked: list[str] = []
    # Round-robin across ar/er/ir
    endings = ["ar", "er", "ir"]
    while len(picked) < n:
        progressed = False
        for e in endings:
            if len(picked) >= n:
                break
            if by_ending[e]:
                picked.append(by_ending[e].pop())
                progressed = True
        if not progressed:
            # drain leftovers
            rest = by_ending["other"] + by_ending["ar"] + by_ending["er"] + by_ending["ir"]
            rng.shuffle(rest)
            for v in rest:
                if len(picked) >= n:
                    break
                if v not in picked:
                    picked.append(v)
            break
    return picked[:n]


def select_ood_verbs(
    *,
    per_tier: int = PER_TIER,
    seed: int = SEED,
    exclude_manifest: Path = N150_MANIFEST,
) -> tuple[list[dict[str, str]], list[tuple[str, str, str]]]:
    """Return (rows, rejected_log) where rejected_log is (verb, tier, reason)."""
    exclude = _load_exclude(exclude_manifest)
    rng = random.Random(seed)
    rejected: list[tuple[str, str, str]] = []
    rows: list[dict[str, str]] = []

    for tier_name in TIERS:
        # First pass: collect rejections from a sample of blocked/failed for report
        raw_pool = [v for v in verbs_in_tier(tier_name, "es") if v not in exclude]
        for v in raw_pool:
            ok, reason = _paradigm_ok(v)
            if not ok and v in _ES_BLOCKED or reason == "noun_adj_like":
                # Only log quality rejects we care about (not sheer volume)
                if reason in {"noun_adj_like", "bad_preterite_1sg", "verbecc_garbage", "no_conjugate", "bad_participle"} or reason.startswith("junk") or reason.startswith("missing") or reason.startswith("verbecc"):
                    rejected.append((v, tier_name, reason))

        pool = _candidates_for_tier(tier_name, exclude)
        if len(pool) < per_tier:
            raise RuntimeError(
                f"tier={tier_name}: only {len(pool)} quality candidates, need {per_tier}"
            )
        # Prefer top of quality-sorted pool, then balanced ending pick among top 80
        head = pool[: max(per_tier * 6, 80)]
        chosen = _balanced_pick(head, per_tier, rng)
        exclude.update(chosen)
        for verb in chosen:
            # cell_id keeps irregularity as annotation only
            irr = is_irregular(verb, "preterite", "es", "1st", "singular")
            cell = f"{tier_name}_{'irregular' if irr else 'regular'}"
            rows.append(
                manifest_row_for_verb(
                    verb, "es", cell, seed=seed, experiment=EXPERIMENT_ID
                )
            )

    # Apply curated quality swaps (must stay in-tier; validated below)
    by_verb = {r["verb"]: r for r in rows}
    for old, new in CURATED_SWAPS.items():
        if old not in by_verb:
            continue
        old_row = by_verb[old]
        if new in by_verb:
            raise RuntimeError(f"Swap target {new!r} already in set")
        ok, reason = _paradigm_ok(new)
        if not ok:
            raise RuntimeError(f"Swap target {new!r} fails paradigm: {reason}")
        if tier(new, "es") != old_row["tier"]:
            raise RuntimeError(
                f"Swap {old}→{new} crosses tier {old_row['tier']}→{tier(new, 'es')}"
            )
        irr = is_irregular(new, "preterite", "es", "1st", "singular")
        cell = f"{tier(new, 'es')}_{'irregular' if irr else 'regular'}"
        new_row = manifest_row_for_verb(new, "es", cell, seed=seed, experiment=EXPERIMENT_ID)
        rows = [new_row if r["verb"] == old else r for r in rows]
        rejected.append((old, old_row["tier"], f"curated_swap→{new}"))

    rows.sort(key=lambda r: (r["tier"], r["verb"]))
    # Dedup rejection log
    seen: set[tuple[str, str, str]] = set()
    uniq_rej = []
    for item in rejected:
        if item not in seen:
            seen.add(item)
            uniq_rej.append(item)
    return rows, uniq_rej


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-tier", type=int, default=PER_TIER)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--exclude-manifest", type=Path, default=N150_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    rows, rejected = select_ood_verbs(
        per_tier=args.per_tier,
        seed=args.seed,
        exclude_manifest=args.exclude_manifest,
    )
    _write_manifest(rows, args.output)

    # Final validation: every form for every verb
    print("Final paradigm re-check...")
    for r in rows:
        ok, reason = _paradigm_ok(r["verb"])
        if not ok:
            raise SystemExit(f"Selected verb failed validation: {r['verb']} ({reason})")

    n150 = _load_exclude(args.exclude_manifest)
    overlap = sorted({r["verb"] for r in rows} & n150)
    if overlap:
        raise SystemExit(f"Overlap with n150: {overlap}")

    print(f"\nWrote {len(rows)} OOD verbs → {args.output}")
    print("By tier:", dict(Counter(r["tier"] for r in rows)))
    print("By ending:", dict(Counter(r.get("ending", "") for r in rows)))
    print("By irregular_probed:", dict(Counter(r["irregular_probed"] for r in rows)))
    zips = [float(r["zipf"]) for r in rows]
    print(f"Zipf range: {min(zips):.2f} – {max(zips):.2f}")
    print("\nVerbs:")
    for r in rows:
        print(
            f"  {r['tier']:<4} z={r['zipf']}  {r['verb']:<16} "
            f"{r['ending']} irr={r['irregular_probed']} "
            f"pret1sg={r['gold_past_1sg']} part={r['gold_participle']}"
        )

    # Surface a short sample of quality rejects (not all)
    interesting = [
        x for x in rejected if x[2] in {"noun_adj_like", "bad_preterite_1sg"} or x[2].startswith("verbecc") or x[2].startswith("junk") or x[2].startswith("missing")
    ][:40]
    if interesting:
        print(f"\nSample quality rejects ({len(interesting)} shown):")
        for v, t, reason in interesting:
            print(f"  skip {v!r} ({t}): {reason}")


if __name__ == "__main__":
    main()
