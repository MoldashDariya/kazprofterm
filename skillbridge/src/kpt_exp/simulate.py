"""A simulated judge with known effects. Used for two things:

1. parameter recovery: run the whole pipeline on the simulator and check that the analysis finds
   exactly the effects that were put in;
2. power analysis (power.py).

The latent score of one request is
    base[quality] + item_effect + term_penalty(ref) * [term_form == teacher] + noise,
rounded and clipped to 1..5. The penalty depends on the reference condition.
"""
import hashlib

import numpy as np

DEFAULT = {
    "base": {"full": 4.4, "partial": 2.1},
    "item_sd": 0.35,
    "noise_sd": 0.45,          # request-to-request noise of the judge (repeats)
    "penalty": {"R_EN": 0.0, "R_KK": 0.0, "R_KK_GLOSS": 0.0},
    "criterion_noise_sd": 0.4,
}


def _rng(*keys):
    h = hashlib.sha256("|".join(map(str, keys)).encode()).digest()
    return np.random.default_rng(int.from_bytes(h[:8], "little"))


def item_effect(item_id, params, seed):
    return _rng("item", item_id, seed).normal(0, params["item_sd"])


def latent(item_id, quality, term_form, ref, rep, params, seed):
    mu = params["base"][quality] + item_effect(item_id, params, seed)
    if term_form == "teacher":
        mu -= params["penalty"][ref]
    noise = _rng("noise", item_id, quality, term_form, ref, rep, seed).normal(0, params["noise_sd"])
    return mu + noise


def clip_round(x):
    return int(min(5, max(1, round(float(x)))))


def judge_response(item_id, quality, term_form, ref, rep, n_points, essential, params=None, seed=0):
    """Return a dict in the judge's JSON format."""
    p = params or DEFAULT
    x = latent(item_id, quality, term_form, ref, rep, p, seed)
    r = _rng("crit", item_id, quality, term_form, ref, rep, seed)
    crit = {k: clip_round(x + r.normal(0, p["criterion_noise_sd"]))
            for k in ("relevance_1to5", "correctness_1to5", "completeness_1to5", "terminology_1to5")}
    overall = clip_round(x)
    k = max(1, round(len(essential) * (overall - 1) / 4)) if overall > 1 else 0
    return {**crit, "overall_1to5": overall,
            "addressed_essential_points": list(essential[:k]),
            "missed_essential_points": list(essential[k:]),
            "evidence": "simulated"}
