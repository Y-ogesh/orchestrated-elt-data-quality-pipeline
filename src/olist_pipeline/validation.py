"""Validate the Olist snapshot against the Milestone 1 source contract."""

import argparse
from pathlib import Path
from typing import Iterable, List, Optional

from .dataset import TABLES
from .profiling import profile_dataset


def validate_profile(profile: dict) -> List[str]:
    errors: List[str] = []
    for name, contract in TABLES.items():
        table = profile["tables"][name]
        if table["rows"] == 0:
            errors.append(f"{name}: table is empty")
        missing = sorted(set(contract.required_columns) - set(table["columns"]))
        if missing:
            errors.append(f"{name}: missing columns {missing}")
        if contract.natural_key and table["natural_key_duplicate_rows"]:
            errors.append(
                f"{name}: {table['natural_key_duplicate_rows']} duplicate natural-key rows"
            )
    for relationship in profile["relationships"]:
        if relationship["orphan_rows"]:
            errors.append(
                "{child}->{parent}: {orphan_rows} orphan rows".format(**relationship)
            )
    return errors


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/raw"))
    args = parser.parse_args(argv)
    errors = validate_profile(profile_dataset(args.data_dir))
    if errors:
        print("Source validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Source validation passed for {len(TABLES)} tables and all declared relationships")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
