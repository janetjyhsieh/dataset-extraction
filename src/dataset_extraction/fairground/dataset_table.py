"""Build a dataframe of datasets that appear in usage_map.json.

Reads:
  working_dir/fg/databases/usage_map.json       – mapper results (keyed by usage doc_id)
  working_dir/fg/databases/metadata_nodes.json  – MetadataNodes

Writes:
  working_dir/fg/databases/dataset_table.csv

Usage:
    python -m dataset_extraction.fairground.dataset_table --working-dir papers/
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import pandas as pd

from dataset_extraction.log import setup_logging
from dataset_extraction.state.graph import MetadataNodes

logger = logging.getLogger("dataset_extraction.fairground.dataset_table")

_COLUMNS = [
    "dataset_id",
    "paper_title",
    "official_dataset_name",
    "dataset_page",
    "descriptions",
    "years_data",
    "data_license",
    "continents",
    "countries",
    "number_of_rows",
    "attributes",
    "protected_attributes",
    "other_annotations",
]


def run(working_dir: Path) -> pd.DataFrame:
    databases_dir = working_dir / "fg" / "databases"
    usage_map_path = databases_dir / "usage_map.json"

    if not usage_map_path.exists():
        raise FileNotFoundError(f"usage_map.json not found at {usage_map_path}")

    usage_map = json.loads(usage_map_path.read_text())
    dataset_ids = {
        entry["dataset_id"]
        for entry in usage_map.values()
        if entry is not None and entry.get("dataset_id")
    }
    logger.info("Found %d unique dataset_ids in usage_map", len(dataset_ids))

    metadata_db = MetadataNodes(databases_dir / "metadata_nodes.json")

    rows = []
    for dataset_id in sorted(dataset_ids):
        node = metadata_db.get(dataset_id)
        if node is None:
            logger.warning("MetadataNode %r not found — skipping", dataset_id)
            continue
        rows.append({col: getattr(node, col, None) for col in _COLUMNS})

    df = pd.DataFrame(rows, columns=_COLUMNS)

    out_path = databases_dir / "dataset_table.csv"
    df.to_csv(out_path, index=False)
    logger.info("Saved %d rows to %s", len(df), out_path)
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--working-dir", required=True, help="Directory containing fg/")
    args = parser.parse_args()

    working_dir = Path(args.working_dir)
    setup_logging(working_dir / "fg" / "logs")
    run(working_dir)


if __name__ == "__main__":
    main()
