.PHONY: download test profile validate ingest-local warehouse-validate quality-reconcile quality-synthetic incremental-replay dbt-parse dbt-compile dbt-freshness dbt-docs-local dbt-expectations docs clean

download:
	PYTHONPATH=src python3 scripts/download_dataset.py --output-dir data/raw

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

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

dbt-parse:
	dbt parse --project-dir dbt

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

clean:
	find src tests -type d -name __pycache__ -prune -exec rm -r {} +
