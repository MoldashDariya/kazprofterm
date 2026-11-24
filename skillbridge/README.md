# KazProfTerm × SkillBridge: dictionary term or classroom term?

**Status: pipeline ready, preregistration in draft. No LLM judge has scored any study item yet.**

KazProfTerm v0.1 found that for 33% of the teacher-checked terms, college teachers use a different Kazakh term than the officially approved one. This experiment asks whether LLM judges penalise a student who uses the classroom term. It also asks whether the answer depends on the language of the reference answer, and whether a KazProfTerm glossary removes the penalty.

## Design

**Within-item design.** 25 term pairs × 2 answer qualities × 2 term forms × 3 reference conditions × 5 repeats = 1,500 requests per judge.

| Reference condition | Question and reference points | Glossary line |
|---|---|---|
| `R_EN` | English | no |
| `R_KK` | Kazakh, with the dictionary term | no |
| `R_KK_GLOSS` | Kazakh, with the dictionary term | all accepted variants from KazProfTerm |

The two versions of each answer differ **only** in the inserted term. The tests check this.

Hypotheses, analysis plan and power analysis: [`PREREGISTRATION_DRAFT.md`](PREREGISTRATION_DRAFT.md).

## Pipeline

```bash
make venv          # once
make all           # validate terms → build stimuli → unit tests → simulated judges → analysis
make power         # simulation-based power analysis
make judge PROVIDER=anthropic MODEL=claude-haiku-4-5-20251001 RUN=main   # needs ANTHROPIC_API_KEY
make analyze RUN=main
```

| File | Role |
|---|---|
| `items/items_v0_1.json` | 25 items: question, reference points (EN/KK), two answers with a `{TERM}` slot |
| `prompt/judge_prompt_v1_0.md` | judge prompt (system + user template) |
| `src/kpt_exp/stimuli.py` | builds the 100 answers and checks the items against `data/terms.csv` |
| `src/kpt_exp/run_judges.py` | runner: Anthropic, Gemini, OpenAI-compatible (Sherkala), simulator. Logs raw responses and hashes; resumable |
| `src/kpt_exp/analyze.py` | Wilcoxon + Holm, TOST, bootstrap CIs, mixed model, ordinal model, ICC/QWK, PCA → `results/<run>/report.md` |
| `src/kpt_exp/power.py` | power simulation → `results/power/report.md` |
| `src/kpt_exp/simulate.py` | simulated judge with known effects (parameter recovery, power) |

The CI workflow runs `make all` on every push. The Dockerfile gives the same environment.

## Pipeline check with simulated judges

`results/pilot_sim/` comes from two **simulated** judges, not real models:

- `sim-null` has no effect built in. It returns d ≈ 0, all p > .6, and TOST shows equivalence.
- `sim-effect` has a known built-in penalty: 0.5 with a Kazakh reference, 0.1 with English, 0.15 with the glossary. All three hypotheses are detected in the right direction.

This shows that the analysis recovers effects that are there and does not invent ones that are not. **These numbers say nothing about real LLM judges.**
