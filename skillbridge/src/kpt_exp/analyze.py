"""All pre-specified analyses, from raw run files to tables, one figure and report.md.

Primary quantity, per judge and item:
    d[item, ref] = mean overall score (teacher form) - mean overall score (alternative/official form)
averaged over repeats and answer quality. Negative d = the teacher's (classroom) term is penalised.

H1  d in R_KK != 0                       (Wilcoxon signed-rank, two-sided; Holm over judges)
H2  d in R_KK - d in R_EN != 0           (reference language moderates the term effect)
H3  d in R_KK_GLOSS - d in R_KK != 0     (a KazProfTerm glossary line reduces the effect)
Equivalence for H1: TOST with bounds +-0.25 rubric points.
Model: linear mixed model on cell means; ordinal (logit) model with item fixed effects
and item-clustered standard errors as robustness check.
Reliability: ICC(1) and exact agreement across repeats; QWK repeat 1 vs repeat 2.
Structure: PCA of the four criterion scores.

Usage: python -m kpt_exp.analyze --run main [--judges a b c]
"""
import argparse
import json
import warnings

import numpy as np
import pandas as pd
from scipy import stats

from . import REF_CONDITIONS, RESULTS, RUNS, SEED

EQ_BOUND = 0.25
CRITERIA = ["relevance_1to5", "correctness_1to5", "completeness_1to5", "terminology_1to5"]


# ---------------------------------------------------------------- loading
def load(run, judges=None):
    rows = []
    for path in sorted(RUNS.glob(f"*/{run}.jsonl")):
        with open(path, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                if judges and r["judge_model"] not in judges:
                    continue
                res = r.get("result") or {}
                row = {k: r[k] for k in ("judge_model", "status", "stim_id", "item_id", "term_id",
                                         "specialty", "quality", "term_form", "ref", "rep")}
                row.update({k: res.get(k) for k in CRITERIA + ["overall_1to5"]})
                rows.append(row)
    if not rows:
        raise SystemExit(f"no run files named {run}.jsonl under {RUNS}")
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- helpers
def holm(pvals):
    p = np.asarray(pvals, float)
    order = np.argsort(p)
    adj = np.empty_like(p)
    running = 0.0
    m = len(p)
    for rank, i in enumerate(order):
        running = max(running, (m - rank) * p[i])
        adj[i] = min(1.0, running)
    return adj


def boot_ci(x, n=5000, seed=SEED):
    x = np.asarray(x, float)
    rng = np.random.default_rng(seed)
    means = rng.choice(x, size=(n, len(x)), replace=True).mean(axis=1)
    return np.percentile(means, [2.5, 97.5])


def wilcoxon_p(x):
    x = np.asarray(x, float)
    if np.allclose(x, 0):
        return 1.0
    return float(stats.wilcoxon(x, zero_method="wilcox", alternative="two-sided").pvalue)


def tost(x, bound=EQ_BOUND):
    """Two one-sided t-tests; returns the larger p (equivalence if < .05)."""
    x = np.asarray(x, float)
    n, m, se = len(x), x.mean(), x.std(ddof=1) / np.sqrt(len(x))
    if se == 0:
        return 0.0 if abs(m) < bound else 1.0
    p_low = 1 - stats.t.cdf((m + bound) / se, n - 1)
    p_up = stats.t.cdf((m - bound) / se, n - 1)
    return float(max(p_low, p_up))


def qwk(a, b):
    from sklearn.metrics import cohen_kappa_score
    a, b = np.asarray(a, int), np.asarray(b, int)
    if len(set(a) | set(b)) < 2:
        return float("nan")
    return float(cohen_kappa_score(a, b, weights="quadratic", labels=[1, 2, 3, 4, 5]))


def icc1(df, value, group):
    """One-way random-effects ICC(1) for repeated scores of the same request."""
    g = df.groupby(group)[value]
    k = g.size().mean()
    grand = df[value].mean()
    n = g.ngroups
    msb = (g.size() * (g.mean() - grand) ** 2).sum() / (n - 1)
    msw = ((df[value] - g.transform("mean")) ** 2).sum() / (len(df) - n)
    return float((msb - msw) / (msb + (k - 1) * msw)) if msb + (k - 1) * msw > 0 else float("nan")


# ---------------------------------------------------------------- analyses
def item_differences(ok):
    m = ok.groupby(["judge_model", "item_id", "ref", "term_form"])["overall_1to5"].mean().unstack("term_form")
    d = (m["teacher"] - m["official"]).unstack("ref")
    return d  # index: judge, item; columns: refs


def hypothesis_tests(d):
    rows = []
    contrasts = {
        "H1: d(R_KK)": lambda x: x["R_KK"],
        "H2: d(R_KK) - d(R_EN)": lambda x: x["R_KK"] - x["R_EN"],
        "H3: d(R_KK_GLOSS) - d(R_KK)": lambda x: x["R_KK_GLOSS"] - x["R_KK"],
        "descr: d(R_EN)": lambda x: x["R_EN"],
        "descr: d(R_KK_GLOSS)": lambda x: x["R_KK_GLOSS"],
    }
    for judge, dj in d.groupby(level=0):
        for name, f in contrasts.items():
            x = f(dj).dropna().to_numpy()
            lo, hi = boot_ci(x)
            rows.append({"judge": judge, "contrast": name, "n_items": len(x), "mean": x.mean(),
                         "ci95_low": lo, "ci95_high": hi, "p_wilcoxon": wilcoxon_p(x),
                         "p_tost_0.25": tost(x) if name.startswith("H1") else np.nan})
    out = pd.DataFrame(rows)
    out["p_holm"] = np.nan
    for name in [c for c in contrasts if c.startswith("H")]:
        idx = out["contrast"] == name
        out.loc[idx, "p_holm"] = holm(out.loc[idx, "p_wilcoxon"])
    return out


def mixed_models(ok):
    import statsmodels.formula.api as smf
    rows = []
    cells = (ok.groupby(["judge_model", "item_id", "quality", "term_form", "ref"])["overall_1to5"]
               .mean().reset_index())
    formula = ("overall_1to5 ~ C(ref, Treatment('R_EN')) * C(term_form, Treatment('official'))"
               " + C(quality, Treatment('full'))")
    for judge, cj in cells.groupby("judge_model"):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fit = smf.mixedlm(formula, cj, groups=cj["item_id"]).fit(reml=True)
        for name in fit.fe_params.index:
            rows.append({"judge": judge, "model": "LMM (cell means, random item intercept)", "term": name,
                         "estimate": fit.fe_params[name], "se": fit.bse_fe[name], "p": fit.pvalues[name]})
    return pd.DataFrame(rows)


def ordinal_models(ok):
    from statsmodels.miscmodels.ordinal_model import OrderedModel
    rows = []
    for judge, dj in ok.groupby("judge_model"):
        X = pd.DataFrame({
            "R_KK": (dj["ref"] == "R_KK").astype(float),
            "R_KK_GLOSS": (dj["ref"] == "R_KK_GLOSS").astype(float),
            "teacher": (dj["term_form"] == "teacher").astype(float),
            "partial": (dj["quality"] == "partial").astype(float),
        })
        X["R_KK:teacher"] = X["R_KK"] * X["teacher"]
        X["R_KK_GLOSS:teacher"] = X["R_KK_GLOSS"] * X["teacher"]
        items = pd.get_dummies(dj["item_id"], prefix="item", drop_first=True, dtype=float)
        X = pd.concat([X.reset_index(drop=True), items.reset_index(drop=True)], axis=1)
        y = dj["overall_1to5"].astype(int).reset_index(drop=True)
        y = pd.Series(pd.Categorical(y, categories=sorted(y.unique()), ordered=True))
        if y.cat.categories.size < 3:
            continue
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                fit = OrderedModel(y, X, distr="logit").fit(
                    method="bfgs", disp=False, maxiter=2000,
                    cov_type="cluster", cov_kwds={"groups": pd.factorize(dj["item_id"])[0]})
        except Exception as e:  # report, do not hide
            rows.append({"judge": judge, "model": "ordinal logit", "term": "FIT FAILED", "estimate": np.nan,
                         "se": np.nan, "p": np.nan, "note": repr(e)[:200]})
            continue
        for name in ["teacher", "R_KK:teacher", "R_KK_GLOSS:teacher", "partial"]:
            rows.append({"judge": judge, "model": "ordinal logit (item FE, item-clustered SE)", "term": name,
                         "estimate": fit.params[name], "se": fit.bse[name], "p": fit.pvalues[name]})
    return pd.DataFrame(rows)


def reliability(ok):
    rows = []
    for (judge, ref), dj in ok.groupby(["judge_model", "ref"]):
        per = dj.groupby("stim_id")["overall_1to5"]
        exact = (per.nunique() == 1).mean()
        wide = dj.pivot_table(index="stim_id", columns="rep", values="overall_1to5")
        k = qwk(wide[1], wide[2]) if {1, 2} <= set(wide.columns) else np.nan
        rows.append({"judge": judge, "ref": ref, "requests": len(dj), "repeats": dj["rep"].nunique(),
                     "ICC1_overall": icc1(dj, "overall_1to5", "stim_id"),
                     "all_repeats_identical": exact, "QWK_rep1_vs_rep2": k,
                     "mean_within_sd": per.std(ddof=1).mean()})
    return pd.DataFrame(rows)


def pca_criteria(ok):
    rows = []
    for judge, dj in ok.groupby("judge_model"):
        Z = dj[CRITERIA].astype(float)
        Z = (Z - Z.mean()) / Z.std(ddof=0).replace(0, np.nan)
        Z = Z.dropna(axis=1)
        if Z.shape[1] < 2:
            continue
        evals, evecs = np.linalg.eigh(np.cov(Z.T))
        order = np.argsort(evals)[::-1]
        evals, evecs = evals[order], evecs[:, order]
        ratio = evals / evals.sum()
        pc1 = evecs[:, 0] * np.sign(evecs[:, 0].sum())
        row = {"judge": judge, "n": len(Z)}
        row.update({f"PC{i + 1}_var_share": r for i, r in enumerate(ratio)})
        row.update({f"PC1_loading_{c.replace('_1to5', '')}": v for c, v in zip(Z.columns, pc1)})
        row["corr_terminology_vs_overall"] = dj["terminology_1to5"].astype(float).corr(dj["overall_1to5"].astype(float))
        rows.append(row)
    return pd.DataFrame(rows)


def status_table(df):
    t = df.groupby(["judge_model", "ref", "term_form", "status"]).size().unstack("status", fill_value=0)
    t["total"] = t.sum(axis=1)
    for s in ("parse_failed", "api_error"):
        if s in t:
            t[f"{s}_rate"] = t[s] / t["total"]
    return t.reset_index()


def figure(d, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    judges = list(d.index.get_level_values(0).unique())
    fig, ax = plt.subplots(figsize=(1.8 + 2.2 * len(judges), 3.6))
    width = 0.8 / len(REF_CONDITIONS)
    colors = {"R_EN": "#4C78A8", "R_KK": "#E45756", "R_KK_GLOSS": "#54A24B"}
    for j, judge in enumerate(judges):
        dj = d.loc[judge]
        for k, ref in enumerate(REF_CONDITIONS):
            x = dj[ref].dropna().to_numpy()
            lo, hi = boot_ci(x)
            pos = j + (k - 1) * width
            ax.bar(pos, x.mean(), width * 0.9, color=colors[ref], label=ref if j == 0 else None)
            ax.errorbar(pos, x.mean(), yerr=[[x.mean() - lo], [hi - x.mean()]], color="black", capsize=3, lw=1)
    ax.axhline(0, color="grey", lw=0.8)
    for b in (-EQ_BOUND, EQ_BOUND):
        ax.axhline(b, color="grey", lw=0.6, ls="--")
    ax.set_xticks(range(len(judges)))
    ax.set_xticklabels(judges)
    ax.set_ylabel("teacher form − official form\n(mean overall score, 95% CI)")
    ax.set_title("Score difference caused by the Kazakh term variant")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def fmt(df, cols=None):
    df = df if cols is None else df[cols]
    return df.to_markdown(index=False, floatfmt=".3f") if hasattr(df, "to_markdown") else df.to_string(index=False)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--judges", nargs="*")
    a = ap.parse_args(argv)

    df = load(a.run, a.judges)
    ok = df[df["status"] == "ok"].copy()
    out = RESULTS / a.run
    out.mkdir(parents=True, exist_ok=True)

    status = status_table(df)
    d = item_differences(ok)
    tests = hypothesis_tests(d)
    lmm = mixed_models(ok)
    olm = ordinal_models(ok)
    rel = reliability(ok)
    pca = pca_criteria(ok)
    means = (ok.groupby(["judge_model", "ref", "quality", "term_form"])["overall_1to5"].mean()
               .unstack("term_form").reset_index())

    for name, t in [("status", status), ("item_differences", d.reset_index()), ("tests", tests),
                    ("lmm", lmm), ("ordinal", olm), ("reliability", rel), ("pca", pca), ("cell_means", means)]:
        t.to_csv(out / f"{name}.csv", index=False)
    figure(d, out / "term_effect.png")

    lmm_show = lmm[lmm["term"].str.contains("term_form")]
    report = [
        f"# Results: run `{a.run}`", "",
        f"Judges: {', '.join(sorted(df['judge_model'].unique()))}. Requests: {len(df)}, ok: {len(ok)}.", "",
        "## Primary and secondary hypotheses (item level, n = items)", "",
        "`mean` is the mean of d = score(teacher form) − score(official form); negative = teacher's term penalised.", "",
        fmt(tests), "",
        "![term effect](term_effect.png)", "",
        "## Mixed model: term-form terms", "", fmt(lmm_show), "",
        "## Ordinal model (robustness)", "", fmt(olm) if len(olm) else "_not estimated_", "",
        "## Cell means", "", fmt(means), "",
        "## Repeat reliability", "", fmt(rel), "",
        "## PCA of the four criterion scores", "", fmt(pca) if len(pca) else "_not estimated_", "",
        "## Request status", "", fmt(status), "",
    ]
    (out / "report.md").write_text("\n".join(report), encoding="utf-8")
    print(f"wrote {out}/report.md")
    print(tests[tests["contrast"].str.startswith("H")].to_string(index=False, float_format=lambda v: f"{v:.3f}"))


if __name__ == "__main__":
    main()
