.PHONY: test check
PYTHON ?= python3

test:
	$(PYTHON) -B scripts/run_tests.py

check:
	$(PYTHON) -B scripts/check.py
	git diff --check
