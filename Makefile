# ACTCM tasks. With uv installed use the defaults; with pip use:  make reproduce PY=python3
PY ?= uv run python
PYTEST ?= uv run pytest

.PHONY: install validate test build site stress reproduce checksums export publish-check links links-live
install:
	uv sync
validate:
	$(PY) scripts/validate.py
test:
	$(PYTEST) -q
build:
	$(PY) scripts/build.py && $(PY) scripts/navigator.py && $(PY) scripts/stress_test.py && $(PY) scripts/review_sheet.py
site:
	$(PY) scripts/build_site.py
stress:
	$(PY) scripts/stress_test.py
reproduce:
	$(PY) scripts/reproduce.py
checksums:
	$(PY) scripts/reproduce.py --write
# Build the public tree in .cache/public_export (never moves or deletes anything here) and scan it.
export:
	$(PY) scripts/export_public.py
# The publish gate: fails while a to-do marker for Tory is left or anything hidden would be public. It does not publish.
publish-check:
	$(PY) scripts/publish_check.py --full && PUBLISH_GATE=1 $(PYTEST) -q tests/test_publish_gate.py
# Link check you can run from your own machine (the build session could not reach most hosts).
links:
	$(PY) scripts/link_check.py
# After publishing: repository and the five Navigator layer files must answer.
links-live:
	$(PY) scripts/link_check.py --live
