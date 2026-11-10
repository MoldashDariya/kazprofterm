#!/usr/bin/env python3
"""Validate data/terms.csv and data/sources.csv. Standard library only.

Usage:  python3 scripts/validate_terms.py [--target 100]
Exit code 1 if there are errors (warnings do not fail).
"""
import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TERMS = ROOT / "data" / "terms.csv"
SOURCES = ROOT / "data" / "sources.csv"

COLUMNS = ["id", "specialty", "category", "en", "ru", "kk", "kk_variants", "kk_latn",
           "pos", "term_type", "source_kk", "status", "in_skillbridge",
           "definition_en", "definition_kk", "wikidata", "notes"]
REQUIRED_V01 = ["id", "specialty", "category", "en", "ru", "kk", "pos",
                "term_type", "status", "in_skillbridge"]
ENUMS = {
    "specialty": {"electrician", "cook", "it_technician"},
    "category": {"tool", "material", "process", "safety", "equipment", "concept"},
    "pos": {"noun", "noun phrase", "verb", "verb phrase", "adjective"},
    "term_type": {"calque", "borrowing", "native", "hybrid"},
    "status": {"verified", "expert_checked", "draft"},
    "in_skillbridge": {"yes", "no"},
}
LATIN = re.compile(r"[A-Za-z]")
CYRILLIC = re.compile(r"[А-Яа-яЁёӘәҒғҚқҢңӨөҰұҮүҺһІі]")


def read(path):
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames or [], list(reader)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=100, help="target number of terms")
    args = ap.parse_args()

    errors, warnings = [], []
    cols, rows = read(TERMS)
    if cols != COLUMNS:
        errors.append(f"terms.csv columns differ from expected.\n  got:      {cols}\n  expected: {COLUMNS}")

    s_cols, s_rows = read(SOURCES)
    source_ids = {r["id"].strip() for r in s_rows if r.get("id")}
    for r in s_rows:
        if not r.get("title", "").strip():
            warnings.append(f"sources.csv {r.get('id')}: empty title")

    ids = Counter()
    pairs = Counter()
    for n, r in enumerate(rows, start=2):  # line 1 = header
        r = {k: (v or "").strip() for k, v in r.items() if k}
        tag = f"line {n} ({r.get('id') or '?'})"
        ids[r.get("id", "")] += 1
        pairs[(r.get("specialty"), r.get("en", "").lower())] += 1

        for c in REQUIRED_V01:
            if not r.get(c):
                errors.append(f"{tag}: empty required column '{c}'")
        for c, allowed in ENUMS.items():
            v = r.get(c)
            if v and v not in allowed:
                errors.append(f"{tag}: {c}='{v}' not in {sorted(allowed)}")
        if r.get("id") and not re.fullmatch(r"T\d{4}", r["id"]):
            errors.append(f"{tag}: id must look like T0001")

        # sources
        srcs = [s.strip() for s in r.get("source_kk", "").split(";") if s.strip()]
        if r.get("status") in {"verified", "expert_checked"} and not srcs:
            errors.append(f"{tag}: status={r['status']} requires source_kk")
        for s in srcs:
            if s not in source_ids:
                errors.append(f"{tag}: source '{s}' not found in sources.csv")
        if r.get("status") == "draft" and not r.get("notes"):
            warnings.append(f"{tag}: draft without justification in notes")

        # scripts
        if r.get("kk") and LATIN.search(r["kk"]):
            warnings.append(f"{tag}: kk contains Latin letters: '{r['kk']}'")
        if r.get("ru") and LATIN.search(r["ru"]):
            warnings.append(f"{tag}: ru contains Latin letters: '{r['ru']}'")
        if r.get("en") and CYRILLIC.search(r["en"]):
            errors.append(f"{tag}: en contains Cyrillic: '{r['en']}'")
        variants = [v.strip() for v in r.get("kk_variants", "").split(";") if v.strip()]
        if r.get("kk") in variants:
            warnings.append(f"{tag}: kk repeated in kk_variants")
        if r.get("wikidata") and not re.fullmatch(r"Q\d+", r["wikidata"]):
            errors.append(f"{tag}: wikidata must look like Q12345")

    for i, c in ids.items():
        if i and c > 1:
            errors.append(f"duplicate id {i} ({c}x)")
    for (spec, en), c in pairs.items():
        if en and c > 1:
            warnings.append(f"duplicate en '{en}' in {spec} ({c}x)")

    # summary
    clean = [{k: (v or "").strip() for k, v in r.items() if k} for r in rows]
    print(f"Terms: {len(clean)} / target {args.target}   Sources: {len(source_ids)}")
    for col in ["specialty", "status", "term_type", "category", "in_skillbridge"]:
        cnt = Counter(r.get(col, "") for r in clean)
        print(f"  {col:15s} " + ", ".join(f"{k or '∅'}={v}" for k, v in sorted(cnt.items())))
    evaluable = sum(r.get("status") in {"verified", "expert_checked"} for r in clean)
    print(f"  evaluable (verified + expert_checked): {evaluable}")

    for w in warnings:
        print("WARN ", w)
    for e in errors:
        print("ERROR", e)
    print(f"\n{len(errors)} error(s), {len(warnings)} warning(s)")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
