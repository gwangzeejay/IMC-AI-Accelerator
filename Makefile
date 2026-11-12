# Current laptop-only RECAP-CIM workflow. Historical targets: docs/legacy/Makefile_pre_G8
PYTHON ?= python
RUN_ID ?= local-rerun
.PHONY: all help test audit experiment rtl setup
all: test audit
help:
	@echo "make test / audit / experiment RUN_ID=unique-name / rtl RUN_ID=unique-name"
test:
	$(PYTHON) 10_Experiments/run_tests.py
audit:
	$(PYTHON) 10_Experiments/check_project.py
setup:
	$(PYTHON) 10_Experiments/setup_g8_data.py
experiment:
	$(PYTHON) 10_Experiments/run_g8.py --run-id $(RUN_ID)
rtl:
	$(PYTHON) 10_Experiments/verify_g8_rtl.py --run-id rtl-$(RUN_ID)
