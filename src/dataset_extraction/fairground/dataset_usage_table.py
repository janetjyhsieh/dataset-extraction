"""Build a dataframe of datasets usages.

Reads:
  working_dir/databases/usages.json             – UsageNodes (via load_state)
  working_dir/fg/databases/usage_map.json       – mapper results (keyed by usage doc_id)
  working_dir/fg/databases/metadata_nodes.json  – MetadataNodes

Writes:
  working_dir/fg/databases/dataset_table.csv

Usage:
    python -m dataset_extraction.fairground.dataset_table --working-dir papers/
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from dataset_extraction.log import setup_logging
from dataset_extraction.fairground.state_loader import load_state

logger = logging.getLogger("dataset_extraction.fairground.usages_table")

def _to_snake(s: str) -> str:
    return s.strip().lower().replace(" ", "_").replace("-", "_")

def _dataset_full_name(row) -> str:
    parts = [row["dataset_name"], row["dataset_version"], row["dataset_variant"]]
    return "-".join(_to_snake(str(p)) for p in parts if p is not np.nan)

def _combine_lists(series):
    combined = []
    for val in series:
        if isinstance(val, list):
            combined.extend(val)
        elif val is not None and val is not np.nan:
            combined.append(val)
    return list(dict.fromkeys(combined))  # deduplicate, preserve order

def run(working_dir: Path):
    state = load_state(working_dir)
    usages = [u.model_dump(mode="json") for u in state.usage_nodes.all()]
    usages_df = pd.json_normalize(usages)

    usages_df["dataset_full_identifier"] = usages_df.apply(_dataset_full_name, axis=1)
    dataset_table_df = usages_df.rename(columns={
        "source_paper.title": "citation_title",
        "paper_title": "usage_papers"
    })

    dataset_table_df = (
        dataset_table_df
        .groupby(["dataset_full_identifier", "citation_title"], as_index=False, dropna=False)
        .agg(
            aliases=("aliases", _combine_lists),
            paper_titles=("usage_papers", list),
            usage_indices=("usage_papers", lambda s: list(s.index+1)),
        )
    )
    dataset_table_df = dataset_table_df.sort_values(key=lambda col: col.str.lower(), \
                                                    by="dataset_full_identifier")
    dataset_table_df = dataset_table_df.reset_index(drop=True)

    csv_path = working_dir / "fg/output"
    dataset_table_df.to_csv(csv_path / "dataset_usages_table.csv", index=False)

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--working-dir", required=True, help="Directory containing fg/")
    args = parser.parse_args()

    working_dir = Path(args.working_dir)
    setup_logging(working_dir / "logs")
    run(working_dir)


if __name__ == "__main__":
    main()