"""Unit tests for Welsh soft mutation."""

from research.welsh.mutation import soft_mutate


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
