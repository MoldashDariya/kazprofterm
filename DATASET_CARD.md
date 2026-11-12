---
license: cc-by-4.0
language:
- kk
- ru
- en
multilinguality: multilingual
size_categories:
- n<1K
task_categories:
- translation
pretty_name: KazProfTerm
tags:
- terminology
- lexicography
- kazakh
- low-resource
- vocational-education
configs:
- config_name: default
  data_files:
  - split: train
    path: data/terms.csv
---

# KazProfTerm (v0.1)

A trilingual **Kazakh / Russian / English** terminology resource for three vocational specialties:
**IT technician, electrician, cook**. Each term has a source for its Kazakh form, a status
(`verified` / `expert_checked` / `draft`) and a term-formation type
(`calque` / `borrowing` / `native` / `hybrid`).

## Dataset summary

| | v0.1 |
|---|---|
| Terms | 100 (IT technician 34, electrician 33, cook 33) |
| `verified` / `expert_checked` / `draft` | 25 / 71 / 4 |
| Terms used in SkillBridge interview questions | 82 |
| Definitions | not yet (planned for v0.5–v1.0) |

## Motivation

LLM judges in our earlier study compared Kazakh interview answers against **English** reference
points. KazProfTerm provides the Kazakh terms needed to write reference points in Kazakh and to
evaluate how well models translate vocational terms into Kazakh.

## Data fields

See the column table in the [README](README.md#columns-of-termscsv). Key fields:
`en`, `ru`, `kk` (main Kazakh term, Cyrillic), `kk_variants` (`;`-separated attested variants),
`term_type`, `source_kk` (ids in `sources.csv`), `status`, `in_skillbridge`.

## Construction

1. **Term selection** — terms from SkillBridge interview questions and reference points
   (`in_skillbridge = yes`), college curricula and textbooks, and occupational standards.
2. **Kazakh equivalents** — State Terminology Commission database (termincom.kz), parallel
   Russian/Kazakh legal acts (adilet.zan.kz: ICT requirements, electrical safety and operation
   rules, catering sanitary rules), Kazakh-language textbooks. Kazakh Wikipedia was used only as a
   hint. A term is `verified` only if the whole term is attested; per-term URLs and clause numbers
   are in `evidence.csv`.
3. **Annotation** of `term_type` according to written guidelines (README), fixed before annotation.
4. **Quality control** (v0.5): independent second annotator on 60 terms (translation agreement,
   Cohen's κ for `term_type`); review by subject teachers (acceptance rate).

Dictionaries were not copied wholesale; only individual terms with references. Definitions are
written by the authors.

## Intended use

- Evaluating term translation EN→KK and cross-lingual retrieval (use only `verified` and
  `expert_checked` terms; accept `kk` or any `kk_variants`).
- Kazakh glossaries for LLM-based interview scoring.
- Lexicographic analysis of Kazakh vocational terminology.

## Limitations

- Only three specialties; small size (100 terms in v0.1).
- Some terms are `draft` (no source found) — **exclude them from evaluation**.
- One main annotator in v0.1; inter-annotator agreement is added in v0.5.
- Subject-teacher review: one teacher per specialty (IT, electrical, cook). The cook teacher reviewed
  all 33 culinary terms (accepted as is: 22/33 = 67%; acceptable incl. variants: 28/33 = 85%). Where a teacher's form differed from the Termincom form,
  the teacher's form is the main entry and the Termincom form is kept in `kk_variants`.
- Kazakh usage varies; students often use Russian words in speech. `kk_variants` records only
  attested variants.

## License

CC BY 4.0.

## Citation

_TBA._
