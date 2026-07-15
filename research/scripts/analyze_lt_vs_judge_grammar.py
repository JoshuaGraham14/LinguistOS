#!/usr/bin/env python3
"""Correlate LanguageTool grammar vs LLM-judge grammaticality on n150 Fix-B arms."""

from __future__ import annotations

import json
import math
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

try:
    import numpy as np
    from scipy import stats

    HAS_SCIPY = True
except Exception:  # pragma: no cover
    HAS_SCIPY = False


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 3:
        return float("nan")
    mx, my = mean(xs), mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    denx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    deny = math.sqrt(sum((y - my) ** 2 for y in ys))
    if denx == 0 or deny == 0:
        return float("nan")
    return num / (denx * deny)


def ranks(v: list[float]) -> list[float]:
    order = sorted(range(len(v)), key=lambda i: v[i])
    out = [0.0] * len(v)
    i = 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            out[order[k]] = avg
        i = j + 1
    return out


def spearman(xs: list[float], ys: list[float]) -> float:
    return pearson(ranks(xs), ranks(ys))


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--exclude-hard",
        action="store_true",
        help="Exclude hard_plain arms from the correlation.",
    )
    args = parser.parse_args()

    runs = Path("research/runs")
    dbs = sorted(runs.glob("direction_1p2_n150_*.db"))
    if not dbs:
        raise SystemExit(f"No DBs found under {runs.resolve()}")

    rows: list[tuple] = []
    for db in dbs:
        arm = db.stem.replace("direction_1p2_n150_", "")
        if args.exclude_hard and "hard" in arm:
            continue
        con = sqlite3.connect(db)
        con.row_factory = sqlite3.Row
        q = """
        SELECT
          lt.score AS lt_score,
          lt.details AS lt_details,
          j.score AS judge_score,
          j.details AS j_details
        FROM generated_sentences gs
        JOIN sentence_evaluations lt
          ON lt.sentence_id = gs.id
         AND lt.evaluator_name = 'grammar_languagetool'
        JOIN sentence_evaluations j
          ON j.sentence_id = gs.id
         AND j.evaluator_name = 'naturalness_llm_judge'
        """
        for r in con.execute(q):
            ltd = r["lt_details"]
            jd = r["j_details"]
            if isinstance(ltd, str):
                ltd = json.loads(ltd)
            if isinstance(jd, str):
                jd = json.loads(jd)
            if jd.get("error") is not None:
                continue
            g_raw = jd.get("grammaticality")
            if g_raw is None:
                continue
            try:
                g = float(g_raw)
            except (TypeError, ValueError):
                continue
            lt_pass = 1.0 if float(r["lt_score"]) >= 0.5 else 0.0
            mc = int(ltd.get("match_count") or 0)
            rows.append(
                (
                    arm,
                    lt_pass,
                    mc,
                    g,
                    float(jd.get("naturalness") or 0),
                    float(jd.get("semantic_coherence") or 0),
                )
            )
        con.close()

    print(f"DBs: {[p.name for p in dbs]}")
    print(f"paired rows: {len(rows)}")
    if not rows:
        raise SystemExit("No paired rows")

    lt = [r[1] for r in rows]
    g = [r[3] for r in rows]
    mc = [r[2] for r in rows]

    print("\n=== POOLED (all n150 Fix-B arms) ===")
    print(f"N = {len(rows)}")
    print(f"LT pass rate = {mean(lt):.4f}")
    g_sd = math.sqrt(mean([(x - mean(g)) ** 2 for x in g]))
    print(f"Judge G mean = {mean(g):.4f}  (sd={g_sd:.4f})")
    print(f"Judge G distribution: {dict(sorted(Counter(int(x) for x in g).items()))}")

    print("\nContingency LT_pass x Judge_G:")
    print("G\\LT   fail    pass")
    for gk in range(1, 6):
        fail = sum(1 for L, G in zip(lt, g) if L == 0 and int(G) == gk)
        pas = sum(1 for L, G in zip(lt, g) if L == 1 and int(G) == gk)
        print(f"  {gk}   {fail:6d}  {pas:6d}")

    g_pass = [G for L, G in zip(lt, g) if L == 1]
    g_fail = [G for L, G in zip(lt, g) if L == 0]
    print(f"\nMean Judge G | LT pass = {mean(g_pass):.3f} (n={len(g_pass)})")
    print(f"Mean Judge G | LT fail = {mean(g_fail):.3f} (n={len(g_fail)})")
    print(f"Difference (pass - fail) = {mean(g_pass) - mean(g_fail):.3f}")

    print("\nAgreement treating Judge_G >= threshold as 'good':")
    print(
        "thr  LTpass  Jgood   acc    NPV(fail=>bad)  PPV   rec    F1     kappa  MCC"
    )
    for thr in (3, 4, 5):
        y_true = [1 if G >= thr else 0 for G in g]
        y_pred = [int(L) for L in lt]
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
        tn = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 0)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
        n = len(y_true)
        acc = (tp + tn) / n
        prec = tp / (tp + fp) if tp + fp else float("nan")
        rec = tp / (tp + fn) if tp + fn else float("nan")
        f1 = (
            2 * prec * rec / (prec + rec)
            if prec + rec and not math.isnan(prec + rec)
            else float("nan")
        )
        p_yes = (sum(y_true) / n) * (sum(y_pred) / n)
        p_no = (1 - sum(y_true) / n) * (1 - sum(y_pred) / n)
        pe = p_yes + p_no
        kappa = (acc - pe) / (1 - pe) if pe < 1 else float("nan")
        denom = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
        mcc = ((tp * tn - fp * fn) / denom) if denom else float("nan")
        npv = tn / (tn + fn) if tn + fn else float("nan")
        print(
            f">={thr} {mean(lt):6.3f} {mean(y_true):6.3f} {acc:6.3f} "
            f"{npv:14.3f} {prec:5.3f} {rec:5.3f} {f1:5.3f} {kappa:6.3f} {mcc:5.3f}"
        )

    r_pb = pearson(lt, g)
    r_mc = pearson([float(x) for x in mc], g)
    r_sp = spearman([-float(x) for x in mc], g)
    print(f"\nPoint-biserial r(LT_pass, Judge_G) = {r_pb:.4f}")
    print(f"Pearson r(match_count, Judge_G) = {r_mc:.4f}")
    print(f"Spearman rho(-match_count, Judge_G) = {r_sp:.4f}")

    if HAS_SCIPY:
        t, p = stats.ttest_ind(g_pass, g_fail, equal_var=False)
        print(f"Welch t-test G~pass vs fail: t={t:.3f}, p={p:.3e}")
        u, p_mw = stats.mannwhitneyu(g_pass, g_fail, alternative="two-sided")
        print(f"Mann-Whitney U: U={u:.1f}, p={p_mw:.3e}")
        r, p_r = stats.pointbiserialr(lt, g)
        print(f"scipy pointbiserialr = {r:.4f}, p={p_r:.3e}")
        rs, p_s = stats.spearmanr(mc, g)
        print(f"scipy spearman(match_count, G) = {rs:.4f}, p={p_s:.3e}")
        sp = math.sqrt(
            (
                (len(g_pass) - 1) * np.var(g_pass, ddof=1)
                + (len(g_fail) - 1) * np.var(g_fail, ddof=1)
            )
            / (len(g_pass) + len(g_fail) - 2)
        )
        d = (mean(g_pass) - mean(g_fail)) / sp if sp else float("nan")
        print(f"Cohen's d (pass vs fail) = {d:.3f}")
    else:
        print("scipy unavailable — skipping inferential tests")

    print("\n=== PER ARM ===")
    print(
        f"{'arm':40s} {'n':>5} {'LTpass':>7} {'Gmean':>6} "
        f"{'G|pass':>7} {'G|fail':>7} {'dlt':>6} {'r_pb':>7} {'n_fail':>7}"
    )
    by: dict[str, list] = defaultdict(list)
    for r in rows:
        by[r[0]].append(r)
    for arm in sorted(by):
        rr = by[arm]
        L = [x[1] for x in rr]
        G = [x[3] for x in rr]
        gp = [gv for lv, gv in zip(L, G) if lv == 1]
        gf = [gv for lv, gv in zip(L, G) if lv == 0]
        rpb = pearson(L, G)
        print(
            f"{arm:40s} {len(rr):5d} {mean(L):7.3f} {mean(G):6.2f} "
            f"{mean(gp):7.2f} {mean(gf):7.2f} {mean(gp) - mean(gf):6.2f} "
            f"{rpb:7.3f} {len(gf):7d}"
        )

    print("\n=== DISAGREEMENT SLICES (pooled) ===")
    lt_pass_g_low = sum(1 for L, G in zip(lt, g) if L == 1 and G <= 2)
    lt_pass_g_mid = sum(1 for L, G in zip(lt, g) if L == 1 and G == 3)
    lt_fail_g_high = sum(1 for L, G in zip(lt, g) if L == 0 and G >= 4)
    n = len(rows)
    print(
        f"LT pass & Judge G <= 2: {lt_pass_g_low} "
        f"({100 * lt_pass_g_low / n:.1f}%)  <- LT misses bad grammar"
    )
    print(
        f"LT pass & Judge G == 3: {lt_pass_g_mid} ({100 * lt_pass_g_mid / n:.1f}%)"
    )
    print(
        f"LT fail & Judge G >= 4: {lt_fail_g_high} "
        f"({100 * lt_fail_g_high / n:.1f}%)  <- LT false alarms vs judge"
    )

    print("\nAmong LT-pass sentences, Judge G shares:")
    npass = sum(lt)
    for gk in range(1, 6):
        c = sum(1 for L, G in zip(lt, g) if L == 1 and int(G) == gk)
        print(f"  G={gk}: {c:6d}  ({100 * c / npass:.1f}% of LT-pass)")

    print("\nAmong LT-fail sentences, Judge G shares:")
    nfail = len(lt) - npass
    for gk in range(1, 6):
        c = sum(1 for L, G in zip(lt, g) if L == 0 and int(G) == gk)
        print(f"  G={gk}: {c:6d}  ({100 * c / max(nfail, 1):.1f}% of LT-fail)")

    print("\n=== ARM-LEVEL means (LT% vs mean G) ===")
    arms = sorted(by)
    lt_means = [mean([x[1] for x in by[a]]) for a in arms]
    g_means = [mean([x[3] for x in by[a]]) for a in arms]
    print(f"Pearson r(arm LT%, arm mean G) = {pearson(lt_means, g_means):.4f}")
    print(f"Spearman rho = {spearman(lt_means, g_means):.4f}")
    for a, lm, gm in zip(arms, lt_means, g_means):
        print(f"  {a:40s} LT%={100 * lm:5.1f}  meanG={gm:.2f}")


if __name__ == "__main__":
    main()
