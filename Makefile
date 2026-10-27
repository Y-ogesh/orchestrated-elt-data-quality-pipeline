.PHONY: download test lint profile validate ingest-local warehouse-validate quality-reconcile quality-synthetic incremental-replay power-bi-project power-bi-validate dbt-parse dbt-compile dbt-freshness dbt-docs-local dbt-expectations docs final-check clean

download:
	PYTHONPATH=src python3 scripts/download_dataset.py --output-dir data/raw

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

lint:
	python3 -m ruff check .

profile:
	PYTHONPATH=src python3 -m olist_pipeline.profiling --data-dir data/raw --output reports/data_profile.json

validate:
	PYTHONPATH=src python3 -m olist_pipeline.validation --data-dir data/raw

ingest-local:
	PYTHONPATH=src python3 -m olist_pipeline.ingestion --backend local

warehouse-validate:
	PYTHONPATH=src python3 -m olist_pipeline.warehouse validate-local

quality-reconcile:
	PYTHONPATH=src python3 -m olist_pipeline.data_quality reconcile

quality-synthetic:
	PYTHONPATH=src python3 -m olist_pipeline.data_quality synthetic

incremental-replay:
	PYTHONPATH=src python3 -m olist_pipeline.incremental --phase replay

power-bi-project:
	python3 scripts/build_power_bi_project.py

power-bi-validate:
	PYTHONPATH=src python3 -m olist_pipeline.power_bi

dbt-parse:
	dbt parse --project-dir dbt --profiles-dir dbt --no-partial-parse

dbt-compile:
	dbt compile --project-dir dbt --no-introspect

dbt-freshness:
	dbt source freshness --project-dir dbt

dbt-docs-local:
	dbt docs generate --project-dir dbt --empty-catalog --no-compile

dbt-expectations:
	PYTHONPATH=src python3 -m olist_pipeline.dimensional_expectations

docs:
	python3 scripts/check_docs.py

final-check: lint test docs dbt-parse

clean:
	find src tests -type d -name __pycache__ -prune -exec rm -r {} +
