"""Gold past-tense and past-participle forms for English isolation probes."""

from __future__ import annotations

import lemminflect

from research.evaluation.lexicon.en_irregular_lemmas import _normalize_lem_form
from research.evaluation.lexicon.frequency import _en_regular_forms

# Extra accepted alternates beyond lemminflect (primary form first).
_SUPPLEMENTAL: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "beseech": (("besought", "beseeched"), ("besought", "beseeched")),
    "bet": (("bet", "betted"), ("bet", "betted")),
    "betide": (("betid", "betided"), ("betid", "betided")),
    "barbeque": (("barbecued", "barbequed"), ("barbecued", "barbequed")),
    "cleave": (("clove", "cleft", "cleaved"), ("cloven", "cleft", "cleaved")),
    "cling": (("clung",), ("clung",)),
    "fling": (("flung",), ("flung",)),
    "flub": (("flubbed",), ("flubbed",)),
    "forego": (("forewent",), ("foregone",)),
    "forgo": (("forwent",), ("forgone",)),
    "forswear": (("forswore",), ("forsworn",)),
    "gainsay": (("gainsaid",), ("gainsaid",)),
    "gird": (("girt", "girded"), ("girt", "girded")),
    "heave": (("heaved", "hove"), ("heaved", "hoven")),
    "kneel": (("knelt", "kneeled"), ("knelt", "kneeled")),
    "knit": (("knit", "knitted"), ("knit", "knitted")),
    "misunderstand": (("misunderstood",), ("misunderstood",)),
    "mow": (("mowed",), ("mown", "mowed")),
    "outdo": (("outdid",), ("outdone",)),
    "overtake": (("overtook",), ("overtaken",)),
    "overthrow": (("overthrew",), ("overthrown",)),
    "shear": (("sheared", "shorn"), ("sheared", "shorn")),
    "slay": (("slew", "slayed"), ("slain", "slayed")),
    "shrive": (("shrove", "shrived"), ("shriven", "shrived")),
    "sling": (("slung",), ("slung",)),
    "slink": (("slunk", "slinked"), ("slunk", "slinked")),
    "slit": (("slit",), ("slit",)),
    "stink": (("stank", "stunk"), ("stunk",)),
    "strew": (("strewed",), ("strewn", "strewed")),
    "stride": (("strode",), ("stridden", "strid")),
    "tread": (("trod",), ("trodden", "treaded")),
    "unbind": (("unbound",), ("unbound",)),
    "wed": (("wed", "wedded"), ("wed", "wedded")),
    "weep": (("wept",), ("wept",)),
    "withhold": (("withheld",), ("withheld",)),
    "withstand": (("withstood",), ("withstood",)),
    "wreak": (("wreaked", "wrought"), ("wreaked", "wrought")),
}


def _from_lemminflect(stem: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    past_raw = lemminflect.getInflection(stem, "VBD") or []
    part_raw = lemminflect.getInflection(stem, "VBN") or []
    past = tuple(dict.fromkeys(_normalize_lem_form(f) for f in past_raw))
    part = tuple(dict.fromkeys(_normalize_lem_form(f) for f in part_raw))
    if not past:
        past = (_en_regular_forms(stem)[2],)
    if not part:
        part = past
    return past, part


def en_past_and_participle(lemma: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return (accepted_past_forms, accepted_participle_forms) for *lemma*."""
    stem = lemma.lower()
    past, part = _from_lemminflect(stem)
    if stem in _SUPPLEMENTAL:
        sup_past, sup_part = _SUPPLEMENTAL[stem]
        past = tuple(dict.fromkeys(sup_past + past))
        part = tuple(dict.fromkeys(sup_part + part))
    return past, part
