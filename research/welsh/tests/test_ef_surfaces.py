"""Unit tests for general Welsh EF surface expansions."""

from research.welsh.ef_surfaces import (
    expand_aux_surfaces,
    expand_oi_form_variants,
    fold_welsh_accents,
)


def test_fold_welsh_accents():
    assert fold_welsh_accents("Paratôdd") == "paratodd"
    assert fold_welsh_accents("troïwn") == "troiwn"
    assert fold_welsh_accents("gwnêst") == "gwnest"


def test_expand_aux_includes_rydyn_roedden_wnes():
    rydym = {fold_welsh_accents(x) for x in expand_aux_surfaces("rydym", ["ydym"])}
    assert "rydyn" in rydym
    roedd = {fold_welsh_accents(x) for x in expand_aux_surfaces("roeddem", ["oeddem"])}
    assert "roedden" in roedd
    gwnes = {fold_welsh_accents(x) for x in expand_aux_surfaces("gwnes")}
    assert "wnes" in gwnes


def test_expand_oi_variants_for_oi_lemma():
    trois = {fold_welsh_accents(x) for x in expand_oi_form_variants("trois", lemma="troi")}
    assert "troais" in trois
    trown = {fold_welsh_accents(x) for x in expand_oi_form_variants("trown", lemma="troi")}
    assert "troiwn" in trown
    paratof = {
        fold_welsh_accents(x) for x in expand_oi_form_variants("paratof", lemma="paratoi")
    }
    assert "paratoaf" in paratof


def test_expand_oi_skips_non_oi_lemma_and_bare_vn():
    assert expand_oi_form_variants("trois", lemma="rhoi") == ["trois"]
    assert expand_oi_form_variants("paratoi", lemma="paratoi") == ["paratoi"]
