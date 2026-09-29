# Troubleshooting

## Download cannot resolve or reach Kaggle

Confirm network/DNS access and open the [official dataset page](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce). Retry `make download`. In restricted environments, download the archive manually from the official page and extract exactly nine CSVs into `data/raw/`. Do not commit them.

## Kaggle requires authentication

Kaggle's public endpoint worked without credentials during Milestone 1. If policy changes, configure Kaggle credentials in its standard user-level location, never in this repository. Alternatively use an authenticated browser download from the official Olist listing.

## `Missing dataset files`

Run `make download` and verify filenames have not been renamed. The validator expects the exact nine names declared in `src/olist_pipeline/dataset.py`.

## Translation file reports a missing first column

The official translation CSV begins with a UTF-8 BOM. Repository readers already use `utf-8-sig`. Custom readers must do the same or strip the BOM before comparing the header.

## Profile hash differs

Stop and treat the files as a different source artifact. Check that the files came from the official Olist listing, record the new metadata, compare schema/count changes, and create new profile evidence. Do not edit hashes manually.

## Validation reports natural-key duplicates or orphans

Do not delete or rewrite RAW rows. Confirm the source version, inspect aggregate counts without publishing customer/order IDs, and classify the condition as either an upstream source change or a pipeline defect. Update the contract only after a reviewed modeling decision.

## Python import errors

Run Make targets from the repository root; they set `PYTHONPATH=src`. For direct commands use `PYTHONPATH=src python3 -m olist_pipeline.validation --data-dir data/raw`, or install the project in an activated virtual environment with `python -m pip install -e .`.

## Why payment and item totals differ

The source contains different child grains and 303 shared orders differ by more than R$0.01. Always aggregate each child to `order_id` separately. The difference is a quality/reconciliation output, not permission to fan out or force values equal.
