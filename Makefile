.PHONY: download test profile validate docs clean

download:
	PYTHONPATH=src python3 scripts/download_dataset.py --output-dir data/raw

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

profile:
	PYTHONPATH=src python3 -m olist_pipeline.profiling --data-dir data/raw --output reports/data_profile.json

validate:
	PYTHONPATH=src python3 -m olist_pipeline.validation --data-dir data/raw

docs:
	python3 scripts/check_docs.py

clean:
	find src tests -type d -name __pycache__ -prune -exec rm -r {} +
