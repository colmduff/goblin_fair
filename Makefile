.PHONY: install test test-all lint format data eu-db results-doc walkthrough lab clean

install:
	poetry install --with test,dev

# Fast tests only (no FaIR runs, no downloads).
test:
	poetry run pytest -m "not slow and not network"

# Everything, including real FaIR runs and the upstream-data cross-check.
test-all:
	poetry run pytest

lint:
	poetry run ruff check src tests scripts

format:
	poetry run ruff format src tests scripts
	poetry run ruff check --fix src tests scripts

# Rebuild the bundled data from upstream sources (needs network).
data:
	poetry run python scripts/build_data.py

# Build EU-data/eu27_net_zero.sqlite from the ESABCC workbook (local, git-ignored).
eu-db:
	poetry run python scripts/build_eu_db.py

# Write EU-data/RESULTS_DB.md, the data dictionary of EU-data/results.db.
results-doc:
	poetry run python scripts/describe_results_db.py

# Execute the walkthrough notebooks in place (walkthrough/ is git-ignored).
walkthrough:
	poetry run jupyter nbconvert --to notebook --execute --inplace \
		--ExecutePreprocessor.timeout=1200 walkthrough/*.ipynb

lab:
	poetry run jupyter lab walkthrough/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .ipynb_checkpoints -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache .coverage dist
