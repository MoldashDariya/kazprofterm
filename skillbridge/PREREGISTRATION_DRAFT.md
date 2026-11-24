# Preregistration (DRAFT, not yet registered)

**Title:** Dictionary term or classroom term? How the language of the reference answer changes LLM judge scores for Kazakh vocational answers

**Author:** Dariya Moldash (Kazakh-British Technical University)

**Status:** draft v0.1, 2026-11-24. No judge model has scored any study item. Pipeline tests used only a simulated judge (`runs/sim-*`).
**To register:** finish the checklist in §9, freeze the files with SHA-256 hashes, and upload to Zenodo, as was done for 10.5281/zenodo.24023433.

---

## 1. Background

In the earlier preregistered study (Moldash, 2026; https://doi.org/10.5281/zenodo.24023433), native-speaker editing of Kazakh answers did not change the scores of three LLM judges. In that study the judges compared Kazakh answers with **English** reference points.

KazProfTerm v0.1 found that for 25 of 75 teacher-checked terms (33%), college teachers use a different Kazakh term than the officially approved one. A student who uses the classroom term could be marked down by a system whose reference answer uses the dictionary term. This study tests that risk directly. It also tests whether a simple remedy works: a glossary line built from KazProfTerm.

## 2. Research questions and hypotheses

- **RQ1.** When the reference points are written in Kazakh with the dictionary term, do LLM judges give a different score to the same answer if it uses the teacher's term instead of the dictionary term?
- **RQ2.** Is this effect different when the reference points are in English?
- **RQ3.** Does a glossary line listing all accepted Kazakh variants (from KazProfTerm) change the effect?

Let d = overall score (teacher form) − overall score (dictionary form), for the same item. d is averaged over repeats and over answer quality.

| | Hypothesis | Test |
|---|---|---|
| **H1 (primary)** | mean d ≠ 0 in `R_KK` | Wilcoxon signed-rank over items, two-sided; Holm across judges, α = .05 |
| **H2** | mean d(`R_KK`) − d(`R_EN`) ≠ 0 | same |
| **H3** | mean d(`R_KK_GLOSS`) − d(`R_KK`) ≠ 0 | same |
| **E1 (equivalence)** | \|mean d\| in `R_KK` < 0.25 rubric points | TOST, α = .05 per judge |

Expected direction: d < 0 in `R_KK` (penalty), smaller in `R_EN`, and reduced by the glossary. All tests are nevertheless two-sided.

## 3. Design

A fully within-item design: 25 items × 2 answer qualities × 2 term forms × 3 reference conditions × 5 repeats = **1,500 requests per judge**.

- **Items.** All 25 KazProfTerm v0.1 terms where the teacher's form differs from an attested alternative form, 6 IT, 8 electrical and 11 cook. The pairs are listed in `items/items_v0_1.json` (`official` field) and are linked to `terms.csv` by `term_id`.
- **Answers.** For each item there are two synthetic student answers in Kazakh: `full` (covers all essential points) and `partial` (names the concept and little else). Each answer contains a `{TERM}` slot, filled with the teacher form or the dictionary form. **The two versions of an answer differ only in the term.** Questions and answers are checked automatically so that neither form appears anywhere else (`stimuli.py`).
- **Reference conditions:**
  - `R_EN`: the question and the reference points are in English.
  - `R_KK`: the question and the reference points are in Kazakh, and the reference points use the dictionary form.
  - `R_KK_GLOSS`: the same as `R_KK`, plus a line `accepted_term_variants (all are correct)` listing the teacher form, the dictionary form and the other attested variants from `terms.csv`, sorted alphabetically.
- **Answer language.** Every answer is in Kazakh, so only the reference side changes.

## 4. Judges and settings

| Role | Model | Access |
|---|---|---|
| Primary | Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) | Anthropic API, temperature 0, `anthropic-version: 2023-06-01` |
| Primary | Gemini 3.8 Flash (`gemini-3.8-flash`) | Gemini API. Temperature is ignored by the provider; 0 is sent and this is recorded |
| Primary | Sherkala-8B Chat, the same pinned commit as in the earlier study | self-hosted OpenAI-compatible server, temperature 0, JSON schema enforced |

These are the same judges and the same settings policy as in the earlier study, §4. The prompt is `prompt/judge_prompt_v1_0.md`: the earlier prompt plus four criterion scores, without score caps. Every request is logged with the prompt and answer SHA-256, settings, SDK version, the returned model version and the full raw response (`run_judges.py`).

**Parse failures:** up to 3 attempts with the identical request. A request that still fails is recorded as `parse_failed`, never replaced by another score, and is reported per condition.

## 5. Analysis plan

All analyses run with one command (`make analyze RUN=main`) and are listed here before any data are collected.

1. **H1–H3:**
   - Wilcoxon signed-rank test on item-level differences, with `zero_method = "wilcox"`.
   - Holm correction across the three primary judges, separately for each hypothesis.
   - Item-bootstrap 95% CI for the mean (5,000 resamples, seed 20261124).
2. **E1:** TOST on item-level d in `R_KK`, with bounds ±0.25.
3. **Model-based estimates (secondary):**
   - A linear mixed model on cell means: `overall ~ ref × term_form + quality + (1 | item)`.
   - An ordinal logit model on the request-level scores, with item fixed effects and item-clustered standard errors.
4. **Reliability (secondary):**
   - ICC(1) of overall scores across the 5 repeats, for each judge and condition.
   - The share of requests whose 5 repeats are all identical.
   - QWK between repeats 1 and 2.
5. **Criterion structure (exploratory):** PCA of the four standardised criterion scores, per judge. The question is whether the criteria are distinguished or collapse into one general-impression component. Also the correlation of `terminology` with `overall`.
6. **Exploratory:** d by specialty (IT, electrical, cook) and by answer quality. d by type of difference between the forms (borrowing vs Kazakh coinage, spelling-only differences such as *тоқ/ток*).

## 6. Sample size and power

The number of items is fixed by the resource: 25 is every divergent pair in KazProfTerm v0.1. The simulation is in `power.py` and its results in `results/power/report.md`. It uses the same rounding to 1..5 and the same Holm-adjusted test.

- The **penalty is the same for every term** and request noise SD is 0.45. Then 25 items × 5 repeats give power ≥ .89 for a penalty of 0.2 and ≥ .99 for 0.25.
- The **penalty varies between terms** (SD 0.3). Then power is .72 for 0.25 and .90 for 0.30. With 40 items it would be .94 for 0.25.
- **Equivalence:** if there is no penalty, TOST shows equivalence within ±0.25 with power ≥ .98 for any noise level up to 0.7.

**Decision:** the smallest effect of interest is 0.30 rubric points, and power at that size is ≥ .90 under the heterogeneous model. If KazProfTerm v0.5 adds new divergent pairs before registration, the item set may grow to 40. This decision is made before any data are collected.

## 7. Exclusions

- No items are excluded after data collection.
- An item is excluded **before** registration only if the native-speaker check (§9) finds that a term slot makes one version ungrammatical. Excluded items are listed with the reason.

## 8. Limitations

- **Synthetic answers.** Real students' answers will be studied with the SkillBridge data covered by the colleges' agreement (November 2026).
- **One teacher per specialty decides the teacher form.** The second-annotator agreement planned for v0.5 will qualify this.
- **The "official" form is the attested alternative listed in `kk_variants`.** For some pairs this is a Termincom-approved term. For others it is an earlier dictionary or textbook form. The source of each pair is checked in §9.
- **Haiku 4.5 is past its earliest possible retirement date,** and Gemini sampling cannot be fixed.

## 9. Checklist before registration (to be done by the author)

- [ ] Native-speaker check of every Kazakh question, reference point and answer in `items/items_v0_1.json`. In particular, check that both term forms fit grammatically into each `{TERM}` slot. The drafts were written with an AI assistant.
- [ ] For each of the 25 pairs, confirm the source of the `official` form (Termincom / act / textbook) and record it in the item file.
- [ ] Calibrate the noise assumption: score 5 non-study practice answers × 5 repeats with each judge, and update §6 if the noise SD is outside 0.3–0.7. These calls are excluded from the study.
- [ ] Freeze the files (`make freeze`), add the hashes and register on Zenodo.
