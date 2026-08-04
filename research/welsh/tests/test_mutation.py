"""Unit tests for Welsh soft mutation."""

from research.welsh.mutation import (
    aspirate_mutate,
    expand_mutation_candidates,
    mutation_policy_for_constraints,
    nasal_mutate,
    soft_mutate,
)


def test_soft_mutation_core_letters():
    assert soft_mutate("cath") == "gath"
    assert soft_mutate("tad") == "dad"
    assert soft_mutate("pen") == "ben"
    assert soft_mutate("brawd") == "frawd"
    assert soft_mutate("dos") == "ddos"
    assert soft_mutate("gardd") == "ardd"
    assert soft_mutate("mam") == "fam"
    assert soft_mutate("llaw") == "law"
    assert soft_mutate("rhaw") == "raw"


def test_soft_mutation_gw_and_unchanged():
    assert soft_mutate("gweld") == "weld"
    assert soft_mutate("siarad") == "siarad"
    assert soft_mutate("ffôn") == "ffôn"
    assert soft_mutate("chwerthin") == "chwerthin"


def test_soft_mutation_manifest_verbnouns():
    assert soft_mutate("meddwl") == "feddwl"
    assert soft_mutate("rhoi") == "roi"
    assert soft_mutate("troi") == "droi"
    assert soft_mutate("curo") == "guro"


def test_nasal_and_aspirate_mutation():
    assert nasal_mutate("cath") == "nghath"
    assert nasal_mutate("pen") == "mhen"
    assert nasal_mutate("tad") == "nhad"
    assert aspirate_mutate("cath") == "chath"
    assert aspirate_mutate("pen") == "phen"
    assert aspirate_mutate("siarad") == "siarad"


def test_mutation_policy_peri_past_soft_optional():
    assert (
        mutation_policy_for_constraints(
            {"construction": "periphrastic", "tense": "past"}
        )
        == "soft_optional"
    )
    assert (
        mutation_policy_for_constraints(
            {"construction": "periphrastic", "tense": "present"}
        )
        == "none"
    )
    assert (
        mutation_policy_for_constraints({"requires_soft_mutation": True})
        == "soft_optional"
    )


def test_expand_mutation_candidates_soft_optional():
    out = expand_mutation_candidates(["rhoi", "dyroi"], policy="soft_optional")
    assert "rhoi" in out
    assert "roi" in out
    assert "dyroi" in out
