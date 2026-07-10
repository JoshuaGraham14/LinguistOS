"""Tests for distribution-level (group) metrics."""

from __future__ import annotations

from research.db.models import GeneratedSentence, SentenceEvaluation
from research.evaluation.distribution import (
    DEFAULT_GROUP_METRICS,
    EXPERIMENT_GROUP_METRIC_NAMES,
    group_metrics_for_run,
)
from research.evaluation.distribution.distinct_ngram import DistinctNgramMetric
from research.evaluation.distribution.lt_error_breakdown import LtErrorBreakdownMetric
from research.evaluation.distribution.self_bleu import SelfBleuMetric
from research.evaluation.distribution.template_rate import TemplateRateMetric
from research.evaluation.distribution.tokens import tokenize
from research.evaluation.distribution.length_cv import LengthCvMetric
from research.evaluation.distribution.mean_clauses import MeanClausesMetric
from research.evaluation.distribution.mean_token_count import MeanTokenCountMetric
from research.evaluation.distribution.uniqueness import UniquenessRatioMetric
from research.evaluation.sentence.clause_count import EVALUATOR_NAME
from research.pipeline import _compute_and_store_group_metrics


def _sentences(texts: list[str]) -> list[GeneratedSentence]:
    return [
        GeneratedSentence(
            experiment_id=1,
            constraint_set_id=1,
            sentence=text,
            translation="Translation.",
            sample_index=i,
        )
        for i, text in enumerate(texts)
    ]


BATCH_REPETITIVE = [
    "Yo corro todos los días.",
    "Yo corro todos los días.",
    "Yo corro rápido.",
]

BATCH_VARIED = [
    "Corro en el parque.",
    "Yo corro con mi perro.",
    "Todas las mañanas corro.",
]

BATCH_NEAR_DUPLICATE = [
    "Ayer condujeron hasta el centro.",
    "Ayer condujeron hasta la costa.",
    "Condujeron hasta Madrid ayer.",
]


def test_tokenize_strips_edge_punctuation():
    assert tokenize("  Hola, mundo.  ") == ["hola", "mundo"]


def test_tokenize_strips_spanish_inverted_marks():
    assert tokenize("¿Tú hablas español?") == ["tú", "hablas", "español"]


def test_uniqueness_ratio_all_distinct():
    m = UniquenessRatioMetric("constraint_set")
    r = m.compute(_sentences(["Uno.", "Dos."]))
    assert r.value == 1.0
    assert r.details["unique"] == 2


def test_uniqueness_ratio_duplicates():
    m = UniquenessRatioMetric("constraint_set")
    r = m.compute(_sentences(["  Hola  ", "hola"]))
    assert r.value == 0.5


def test_group_metrics_for_run_filters_experiment_scope():
    all_metrics = group_metrics_for_run(include_experiment_scope=True)
    cell_only = group_metrics_for_run(include_experiment_scope=False)
    assert len(all_metrics) == len(DEFAULT_GROUP_METRICS)
    assert len(cell_only) == len(DEFAULT_GROUP_METRICS) - len(EXPERIMENT_GROUP_METRIC_NAMES)
    assert all(m.scope == "constraint_set" for m in cell_only)
    assert not any(m.scope == "experiment" for m in cell_only)


def test_self_bleu_skips_single_sentence_batch():
    m = SelfBleuMetric("constraint_set")
    r = m.compute(_sentences(["Solo."]))
    assert r.value == 0.0
    assert r.details["skipped"] is True


def test_self_bleu_identical_sentences_score_high():
    m = SelfBleuMetric("constraint_set")
    r = m.compute(_sentences(["Yo corro.", "Yo corro.", "Yo corro."]))
    assert r.value > 0.9


def test_self_bleu_varied_sentences_score_lower():
    m = SelfBleuMetric("constraint_set")
    repetitive = m.compute(_sentences(BATCH_REPETITIVE)).value
    varied = m.compute(_sentences(BATCH_VARIED)).value
    assert repetitive > varied


def test_self_bleu_experiment_subsamples_large_batches(monkeypatch):
    monkeypatch.setenv("SELF_BLEU_EXPERIMENT_CAP", "3")
    m = SelfBleuMetric("experiment")
    texts = [f"Oración número {i} con palabras distintas." for i in range(20)]
    r = m.compute(_sentences(texts))
    assert r.details["sampled"] is True
    assert r.details["sample_n"] == 3
    assert r.details["pool_n"] == 20


def test_template_rate_catches_shared_openings():
    m = TemplateRateMetric("constraint_set")
    repetitive = m.compute(_sentences(BATCH_REPETITIVE)).value
    varied = m.compute(_sentences(BATCH_VARIED)).value
    assert repetitive > varied
    assert repetitive >= 2 / 3


def test_template_rate_skips_single_sentence_batch():
    m = TemplateRateMetric("constraint_set")
    r = m.compute(_sentences(["Solo."]))
    assert r.value == 0.0
    assert r.details["skipped"] is True


def test_template_rate_uses_full_prefix_for_short_sentences():
    m = TemplateRateMetric("constraint_set", k=3)
    r = m.compute(_sentences(["Pan.", "Pan.", "Arroz."]))
    assert r.value == round(2 / 3, 4)


def test_distinct_ngram_unigram_and_bigram_names():
    assert DistinctNgramMetric(1, "constraint_set").name == "distinct_1"
    assert DistinctNgramMetric(2, "experiment").name == "distinct_2_experiment"


def test_distinct_ngram_varied_batch_scores_higher_than_repetitive():
    uni = DistinctNgramMetric(1, "constraint_set")
    bi = DistinctNgramMetric(2, "constraint_set")

    repetitive_uni = uni.compute(_sentences(BATCH_REPETITIVE)).value
    varied_uni = uni.compute(_sentences(BATCH_VARIED)).value
    assert varied_uni > repetitive_uni

    repetitive_bi = bi.compute(_sentences(BATCH_REPETITIVE)).value
    varied_bi = bi.compute(_sentences(BATCH_VARIED)).value
    assert varied_bi > repetitive_bi


def test_distinct_ngram_near_duplicate_batch_unique_strings_but_low_bigram_diversity():
    uni = UniquenessRatioMetric("constraint_set")
    bi = DistinctNgramMetric(2, "constraint_set")
    self_bleu = SelfBleuMetric("constraint_set")

    sentences = _sentences(BATCH_NEAR_DUPLICATE)
    assert uni.compute(sentences).value == 1.0
    assert self_bleu.compute(sentences).value > 0.1
    assert bi.compute(sentences).value < 1.0


def test_distinct_ngram_empty_batch():
    m = DistinctNgramMetric(2, "constraint_set")
    r = m.compute([])
    assert r.value == 0.0
    assert r.details["total"] == 0


def test_compute_and_store_group_metrics_no_sentence_evaluations(
    session, sample_constraint_set, sample_experiment
):
    session.add(GeneratedSentence(
        experiment_id=sample_experiment.id,
        constraint_set_id=sample_constraint_set.id,
        sentence="X.",
        translation="X.",
        sample_index=0,
    ))
    session.commit()
    assert session.query(SentenceEvaluation).count() == 0

    n = _compute_and_store_group_metrics(
        session, sample_experiment, DEFAULT_GROUP_METRICS
    )
    assert n == 18  # 9 metric types × (1 constraint_set + 1 experiment)
    assert session.query(SentenceEvaluation).count() == 0


def test_lt_error_breakdown_aggregates_categories():
    m = LtErrorBreakdownMetric("constraint_set")
    s1 = GeneratedSentence(
        experiment_id=1,
        constraint_set_id=1,
        sentence="Yo comimos pizza.",
        translation="We ate pizza.",
        sample_index=0,
    )
    s2 = GeneratedSentence(
        experiment_id=1,
        constraint_set_id=1,
        sentence="Las chico come.",
        translation="The boy eats.",
        sample_index=1,
    )
    s1.evaluations = [
        SentenceEvaluation(
            sentence_id=1,
            evaluator_name="grammar_languagetool",
            score=0.0,
            details={
                "matches": [
                    {"category": "AGREEMENT_VERBS", "rule": "A"},
                    {"category": "AGREEMENT_VERBS", "rule": "B"},
                ]
            },
        )
    ]
    s2.evaluations = [
        SentenceEvaluation(
            sentence_id=2,
            evaluator_name="grammar_languagetool",
            score=0.0,
            details={
                "matches": [{"category": "AGREEMENT_NOUNS", "rule": "C"}],
            },
        )
    ]
    r = m.compute([s1, s2])
    assert r.value == 3.0
    assert r.details == {"AGREEMENT_VERBS": 2, "AGREEMENT_NOUNS": 1}


def test_mean_token_count_averages_lengths():
    m = MeanTokenCountMetric("constraint_set")
    r = m.compute(_sentences(["Yo corro.", "Corro rápido en el parque."]))
    assert r.value == 3.5
    assert r.details["counts"] == [2, 5]


def test_length_cv_zero_for_identical_lengths():
    m = LengthCvMetric("constraint_set")
    r = m.compute(_sentences(["Yo corro.", "Tú hablas.", "Él come."]))
    assert r.value == 0.0


def test_length_cv_positive_for_mixed_lengths():
    m = LengthCvMetric("constraint_set")
    short = m.compute(_sentences(["Yo corro.", "Tú hablas."])).value
    mixed = m.compute(_sentences(["Yo corro.", "Corro rápido en el parque todos los días."])).value
    assert mixed > short


def test_mean_clauses_reads_clause_count_evaluations():
    m = MeanClausesMetric("constraint_set")
    s1 = GeneratedSentence(
        experiment_id=1,
        constraint_set_id=1,
        sentence="Yo corro.",
        translation="I run.",
        sample_index=0,
    )
    s2 = GeneratedSentence(
        experiment_id=1,
        constraint_set_id=1,
        sentence="Creo que viene.",
        translation="I think he is coming.",
        sample_index=1,
    )
    s1.evaluations = [
        SentenceEvaluation(
            sentence_id=1,
            evaluator_name=EVALUATOR_NAME,
            score=0.25,
            details={"clause_count": 1},
        )
    ]
    s2.evaluations = [
        SentenceEvaluation(
            sentence_id=2,
            evaluator_name=EVALUATOR_NAME,
            score=0.5,
            details={"clause_count": 2},
        )
    ]
    r = m.compute([s1, s2])
    assert r.value == 1.5
    assert r.details["counts"] == [1, 2]


def test_lt_error_breakdown_empty_without_evaluations():
    m = LtErrorBreakdownMetric("experiment")
    sent = GeneratedSentence(
        experiment_id=1,
        constraint_set_id=1,
        sentence="Hola.",
        translation="Hi.",
        sample_index=0,
    )
    r = m.compute([sent])
    assert r.value == 0.0
    assert r.details == {}
