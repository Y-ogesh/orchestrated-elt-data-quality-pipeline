#!/usr/bin/env python3
"""Download and safely extract the official public Olist Kaggle snapshot."""

import argparse
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from olist_pipeline.dataset import TABLES


DATASET_URL = "https://www.kaggle.com/api/v1/datasets/download/olistbr/brazilian-ecommerce"


def download(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="olist-download-") as directory:
        archive = Path(directory) / "olist.zip"
        print(f"Downloading {DATASET_URL}")
        with urllib.request.urlopen(DATASET_URL, timeout=60) as response, archive.open("wb") as target:
            shutil.copyfileobj(response, target)

        with zipfile.ZipFile(archive) as source:
            members = [member for member in source.infolist() if not member.is_dir()]
            unsafe = [member.filename for member in members if Path(member.filename).name != member.filename]
            if unsafe:
                raise ValueError(f"Archive contains unsafe paths: {unsafe}")
            actual = {member.filename for member in members}
            expected = {contract.filename for contract in TABLES.values()}
            if actual != expected:
                raise ValueError(
                    f"Archive file set differs from contract; missing={sorted(expected - actual)}, "
                    f"unexpected={sorted(actual - expected)}"
                )
            source.extractall(output_dir)
    print(f"Extracted {len(members)} files to {output_dir}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw"))
    args = parser.parse_args()
    download(args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
