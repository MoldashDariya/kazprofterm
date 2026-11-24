# KazProfTerm. Run `make help` to list the targets.
PY      ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
EXP     := skillbridge
export PYTHONPATH := $(EXP)/src
RUN     ?= main
REPEATS ?= 5

.PHONY: help venv validate stimuli sim analyze power test all freeze clean

help:
	@echo "venv      create .venv and install requirements"
	@echo "validate  check data/terms.csv"
	@echo "stimuli   build $(EXP)/build/stimuli.csv from the items and terms.csv"
	@echo "sim       run the pipeline with two simulated judges (no API keys needed)"
	@echo "analyze   all pre-specified analyses for RUN=$(RUN)"
	@echo "power     simulation-based power analysis"
	@echo "test      unit tests"
	@echo "all       validate + stimuli + test + sim + analyze RUN=pilot_sim"
	@echo "freeze    write SHA-256 hashes of the frozen study files"
	@echo "judge     e.g. make judge PROVIDER=anthropic MODEL=claude-haiku-4-5-20251001 RUN=main"

venv:
	python3 -m venv .venv && .venv/bin/pip install -q -r $(EXP)/requirements.txt

validate:
	$(PY) scripts/validate_terms.py

stimuli:
	$(PY) -m kpt_exp.stimuli

sim: stimuli
	$(PY) -m kpt_exp.run_judges --provider sim --model sim-null --run pilot_sim --repeats $(REPEATS)
	$(PY) -m kpt_exp.run_judges --provider sim --model sim-effect --run pilot_sim --repeats $(REPEATS)

judge: stimuli
	$(PY) -m kpt_exp.run_judges --provider $(PROVIDER) --model $(MODEL) --run $(RUN) --repeats $(REPEATS) $(if $(LIMIT),--limit $(LIMIT),)

analyze:
	$(PY) -m kpt_exp.analyze --run $(RUN)

power:
	$(PY) -m kpt_exp.power --sims 1000

test:
	$(PY) -m pytest -q $(EXP)/tests

all: validate stimuli test sim
	$(MAKE) analyze RUN=pilot_sim

freeze: stimuli
	shasum -a 256 data/terms.csv $(EXP)/items/*.json $(EXP)/prompt/*.md $(EXP)/build/stimuli.csv \
	  $(EXP)/src/kpt_exp/*.py $(EXP)/PREREGISTRATION_DRAFT.md > $(EXP)/HASHES.txt
	@cat $(EXP)/HASHES.txt

clean:
	rm -rf $(EXP)/build $(EXP)/runs/sim-* $(EXP)/results/pilot_sim
