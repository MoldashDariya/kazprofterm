"""Build the stimulus table: 25 items x 2 answer qualities x 2 term forms = 100 answers.

Each pair of answers (teacher form vs alternative form) differs ONLY in the inserted term,
so any score difference inside a pair is caused by the term.

Usage: python -m kpt_exp.stimuli
"""
import csv
import hashlib
import json
import re
import sys

from . import BUILD, ITEMS, QUALITIES, TERM_FORMS, TERMS

PLACEHOLDER = re.compile(r"\{(TERM|OFF)\}")


def load_terms():
    with open(TERMS, encoding="utf-8") as f:
        return {r["id"]: r for r in csv.DictReader(f)}


def load_items():
    with open(ITEMS, encoding="utf-8") as f:
        return json.load(f)["items"]


def variants(term_row):
    return [v.strip() for v in (term_row.get("kk_variants") or "").split(";") if v.strip()]


def check_items(items, terms):
    """Return a list of problems; an empty list means the items are consistent with terms.csv."""
    errors = []
    seen = set()
    for it in items:
        iid, tid = it["item_id"], it["term_id"]
        if iid in seen:
            errors.append(f"{iid}: duplicate item_id")
        seen.add(iid)
        if tid not in terms:
            errors.append(f"{iid}: term {tid} not in terms.csv")
            continue
        t = terms[tid]
        if it["official"] not in variants(t):
            errors.append(f"{iid}: official form '{it['official']}' is not among kk_variants of {tid}")
        if it["official"] == t["kk"]:
            errors.append(f"{iid}: official form equals the teacher form")
        for q in QUALITIES:
            txt = it[f"answer_{q}_kk"]
            if "{TERM}" not in txt:
                errors.append(f"{iid}: answer_{q}_kk has no {{TERM}}")
            if "{OFF}" in txt:
                errors.append(f"{iid}: answer_{q}_kk must not contain {{OFF}}")
            # the answer must not already contain either form outside the placeholder
            bare = txt.replace("{TERM}", "")
            for form in (t["kk"], it["official"]):
                if form.lower() in bare.lower():
                    errors.append(f"{iid}: answer_{q}_kk contains the form '{form}' outside {{TERM}}")
        if len(it["ref_en"]) != len(it["ref_kk"]):
            errors.append(f"{iid}: ref_en and ref_kk have different lengths")
        if not any("{OFF}" in p for p in it["ref_kk"]):
            errors.append(f"{iid}: ref_kk does not mention {{OFF}}")
        if any("{TERM}" in p for p in it["ref_kk"] + it["ref_en"]):
            errors.append(f"{iid}: reference points must not contain {{TERM}}")
        n = len(it["ref_en"])
        if not it["essential"] or any(not 1 <= e <= n for e in it["essential"]):
            errors.append(f"{iid}: essential indices out of range")
        for field in ("question_kk", "question_en"):
            for form in (t["kk"], it["official"]):
                if form.lower() in it[field].lower():
                    errors.append(f"{iid}: {field} leaks the form '{form}'")
    return errors


def build(items, terms):
    rows = []
    for it in items:
        t = terms[it["term_id"]]
        forms = {"teacher": t["kk"], "official": it["official"]}
        for q in QUALITIES:
            for tf in TERM_FORMS:
                text = it[f"answer_{q}_kk"].replace("{TERM}", forms[tf])
                rows.append({
                    "stim_id": f"{it['item_id']}_{q}_{tf}",
                    "item_id": it["item_id"],
                    "term_id": it["term_id"],
                    "specialty": t["specialty"],
                    "quality": q,
                    "term_form": tf,
                    "term_text": forms[tf],
                    "answer_text": text,
                    "answer_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                })
    return rows


def main():
    terms, items = load_terms(), load_items()
    errors = check_items(items, terms)
    if errors:
        print("Item problems:\n  " + "\n  ".join(errors))
        sys.exit(1)
    rows = build(items, terms)
    BUILD.mkdir(parents=True, exist_ok=True)
    out = BUILD / "stimuli.csv"
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(items)} items -> {len(rows)} answers -> {out.relative_to(BUILD.parent.parent)}")


if __name__ == "__main__":
    main()
