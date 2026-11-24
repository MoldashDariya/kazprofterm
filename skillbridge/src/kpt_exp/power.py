"""Simulation-based power analysis for H1 (term penalty with a Kazakh reference).

The same data-generating model as simulate.py is used: latent score = base(quality) + item effect
- penalty * [teacher form] + request noise, rounded and clipped to 1..5. For each scenario the
item-level differences d are computed exactly as in analyze.py and tested with the Wilcoxon
signed-rank test at alpha = .05 / 3 (Holm, worst case for the first of three judges).
Power for the TOST equivalence test (bounds +-0.25) is computed under a true penalty of 0.

Usage: python -m kpt_exp.power [--sims 1000]
"""
import argparse

import numpy as np
import pandas as pd
from scipy import stats

from . import RESULTS, SEED
from .analyze import EQ_BOUND, tost
from .simulate import DEFAULT

ALPHA = 0.05 / 3


def simulate_d(rng, n_items, reps, penalty, noise_sd, penalty_sd=0.0,
               item_sd=DEFAULT["item_sd"], base=DEFAULT["base"]):
    item = rng.normal(0, item_sd, size=n_items)
    pen = penalty + rng.normal(0, penalty_sd, size=n_items)  # the penalty differs between terms
    d = np.zeros(n_items)
    for q in ("full", "partial"):
        mu = base[q] + item
        off = np.clip(np.rint(mu[:, None] + rng.normal(0, noise_sd, (n_items, reps))), 1, 5).mean(1)
        tch = np.clip(np.rint(mu[:, None] - pen[:, None] + rng.normal(0, noise_sd, (n_items, reps))), 1, 5).mean(1)
        d += (tch - off) / 2
    return d


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--sims", type=int, default=1000)
    a = ap.parse_args(argv)
    rng = np.random.default_rng(SEED)
    rows = []
    grid = [(n, r, ns, psd, pen) for n in (25, 40) for r in (3, 5) for ns in (0.3, 0.45, 0.7)
            for psd in (0.0, 0.3) for pen in (0.0, 0.1, 0.2, 0.25, 0.3, 0.4, 0.5)]
    for n_items, reps, noise_sd, penalty_sd, penalty in grid:
        rej = eq = 0
        for _ in range(a.sims):
            d = simulate_d(rng, n_items, reps, penalty, noise_sd, penalty_sd)
            if not np.allclose(d, 0):
                rej += stats.wilcoxon(d, zero_method="wilcox").pvalue < ALPHA
            eq += tost(d, EQ_BOUND) < 0.05
        rows.append({"n_items": n_items, "repeats": reps, "noise_sd": noise_sd,
                     "true_penalty": penalty, "penalty_sd_between_terms": penalty_sd,
                     "power_wilcoxon_holm": rej / a.sims, "power_tost_equivalence": eq / a.sims})
    df = pd.DataFrame(rows)
    out = RESULTS / "power"
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "power.csv", index=False)

    main_tab = df[(df.n_items == 25) & (df.repeats == 5)].pivot_table(
        index="true_penalty", columns=["penalty_sd_between_terms", "noise_sd"], values="power_wilcoxon_holm")
    eq_tab = df[(df.true_penalty == 0) & (df.penalty_sd_between_terms == 0)].pivot_table(
        index=["n_items", "repeats"], columns="noise_sd", values="power_tost_equivalence")
    md = ["# Power analysis (simulation)", "",
          f"{a.sims} simulated studies per cell; Wilcoxon signed-rank at alpha = {ALPHA:.4f} (Holm, 3 judges).", "",
          "## Power to detect the term penalty (25 items, 5 repeats)", "",
          "Rows: mean true penalty in rubric points. Columns: (SD of the penalty between terms, judge noise SD between repeats).", "",
          main_tab.to_markdown(floatfmt=".2f"), "",
          f"## Power of the TOST equivalence test (bounds ±{EQ_BOUND}) when the true penalty is 0 for every term", "",
          eq_tab.to_markdown(floatfmt=".2f"), "",
          "Full grid (also 40 items and 3 repeats): `power.csv`."]
    (out / "report.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
