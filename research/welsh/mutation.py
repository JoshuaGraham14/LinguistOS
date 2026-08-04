"""Welsh initial consonant mutations (treigladau).

Deterministic lookup tables for soft / nasal / aspirate mutation. Used to
expand acceptable surface forms in evaluation when the cell's grammatical
context triggers a mutation (e.g. *gwneud* past + verbnoun → soft).

Eurfa / gold often stores the radical; mutated surfaces are derived here.
"""

from __future__ import annotations

from typing import Any, Iterable, Literal

MutationType = Literal["soft", "nasal", "aspirate", "none"]
MutationPolicy = Literal["none", "soft_optional", "soft_required"]

# Longest-first so digraphs win over single letters.
_SOFT_RULES: tuple[tuple[str, str], ...] = (
    ("ll", "l"),
    ("rh", "r"),
    ("ph", "ph"),  # no change; keep explicit
    ("th", "th"),
    ("ch", "ch"),
    ("ng", "ng"),
    ("p", "b"),
    ("t", "d"),
    ("c", "g"),
    ("b", "f"),
    ("d", "dd"),
    ("g", ""),
    ("m", "f"),
)

_NASAL_RULES: tuple[tuple[str, str], ...] = (
    ("p", "mh"),
    ("t", "nh"),
    ("c", "ngh"),
    ("b", "m"),
    ("d", "n"),
    ("g", "ng"),
)

_ASPIRATE_RULES: tuple[tuple[str, str], ...] = (
    ("p", "ph"),
    ("t", "th"),
    ("c", "ch"),
)


def _apply_rules(word: str, rules: tuple[tuple[str, str], ...]) -> str:
    if not word:
        return word
    was_title = word[0].isupper() and not word.isupper()
    probe = word.lower()
    for src, dst in rules:
        if probe.startswith(src):
            out = dst + probe[len(src) :]
            if was_title and out:
                out = out[0].upper() + out[1:]
            return out
    return word


def soft_mutate(word: str) -> str:
    """Apply soft mutation (treiglad meddal) to the initial of ``word``."""
    return _apply_rules(word, _SOFT_RULES)


def nasal_mutate(word: str) -> str:
    """Apply nasal mutation (treiglad trwynol) to the initial of ``word``."""
    return _apply_rules(word, _NASAL_RULES)


def aspirate_mutate(word: str) -> str:
    """Apply aspirate mutation (treiglad llaes) to the initial of ``word``."""
    return _apply_rules(word, _ASPIRATE_RULES)


def mutate(word: str, kind: MutationType) -> str:
    """Apply a named mutation; ``none`` returns ``word`` unchanged."""
    if kind == "soft":
        return soft_mutate(word)
    if kind == "nasal":
        return nasal_mutate(word)
    if kind == "aspirate":
        return aspirate_mutate(word)
    return word


def soft_mutate_alts(word: str, extra: list[str] | None = None) -> list[str]:
    """Primary soft-mutated form plus optional extras (deduped, primary first)."""
    primary = soft_mutate(word)
    out: list[str] = []
    for w in [primary, *(extra or [])]:
        if w and w not in out:
            out.append(w)
    return out


def _truthy(value: Any) -> bool:
    if value is True or value == 1:
        return True
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "y"}
    return False


def mutation_policy_for_constraints(constraints: dict[str, Any]) -> MutationPolicy:
    """Which mutation surfaces EF should accept for the lexical form.

    Policy is **context-conditioned** (construction / explicit flag), not
    "accept every mutated spelling of the gold form".

    - ``soft_optional``: accept radical *or* soft (fluent speech may omit).
    - ``soft_required``: accept soft (and radical only if already listed in
      gold/alts — handled by caller merging listed forms).
    - ``none``: do not invent mutated variants from the table.
    """
    if _truthy(constraints.get("requires_soft_mutation")):
        # Benchmark marks peri past VN soft-mutation cells. Accept both:
        # textbook expects soft; spoken Welsh sometimes keeps the radical.
        return "soft_optional"

    construction = str(constraints.get("construction") or "").strip().casefold()
    tense = str(constraints.get("tense") or "").strip().casefold()
    if construction == "periphrastic" and tense == "past":
        return "soft_optional"

    # Explicit override for future probes (possessives, prepositions, …).
    explicit = str(constraints.get("mutation") or "").strip().casefold()
    if explicit in {"soft", "soft_optional"}:
        return "soft_optional"
    if explicit in {"soft_required", "required_soft"}:
        return "soft_required"
    if explicit in {"nasal", "aspirate"}:
        # EF currently expands soft for verb cells; nasal/aspirate callers
        # should pass pre-expanded alts or use expand_mutation_candidates.
        return "none"

    return "none"


def expand_mutation_candidates(
    forms: Iterable[str],
    *,
    policy: MutationPolicy = "none",
    kinds: Iterable[MutationType] = (),
) -> list[str]:
    """Expand citation/gold forms with context-allowed mutated surfaces.

    Always keeps the input forms. Adds soft (and optionally other kinds)
    according to ``policy`` / ``kinds``. Does **not** treat every mutation
    as freely interchangeable.
    """
    out: list[str] = []
    seen: set[str] = set()

    def _add(w: str) -> None:
        w = (w or "").strip()
        if not w:
            return
        key = w.casefold()
        if key in seen:
            return
        seen.add(key)
        out.append(w)

    base = [f for f in forms if f and str(f).strip()]
    for f in base:
        _add(str(f).strip())

    apply_soft = policy in {"soft_optional", "soft_required"} or "soft" in kinds
    if apply_soft:
        for f in base:
            _add(soft_mutate(str(f).strip()))

    for kind in kinds:
        if kind in {"none", "soft"}:
            continue
        for f in base:
            _add(mutate(str(f).strip(), kind))

    return out
