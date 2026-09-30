#!/usr/bin/env python3
"""Check required documentation and repository-relative Markdown links."""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "README.md",
    "docs/project_plan.md",
    "docs/architecture.md",
    "docs/data_dictionary.md",
    "docs/dataset_profiling.md",
    "docs/ingestion.md",
    "docs/snowflake_warehouse.md",
    "docs/dbt_transformations.md",
    "docs/dimensional_model.md",
    "docs/decisions.md",
    "docs/engineering_journal.md",
    "docs/validation_report.md",
    "docs/setup_guide.md",
    "docs/troubleshooting.md",
)
LINK = re.compile(r"\[[^]]+\]\(([^)]+)\)")


def main() -> int:
    errors = []
    for relative in REQUIRED:
        document = ROOT / relative
        if not document.is_file():
            errors.append(f"missing required document: {relative}")
            continue
        text = document.read_text(encoding="utf-8")
        for target in LINK.findall(text):
            if target.startswith(("http://", "https://", "#", "mailto:")) or "<" in target:
                continue
            path = (document.parent / target.split("#", 1)[0]).resolve()
            if not path.exists():
                errors.append(f"broken link in {relative}: {target}")
    if errors:
        print("Documentation validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Documentation validation passed for {len(REQUIRED)} required files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
