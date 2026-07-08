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
from dataset_extraction.fairground.state_loader import load_state

logger = logging.getLogger("dataset_extraction.fairground.dataset_table")

_METADATA_COLUMNS = [
    "dataset_id",
    "paper_title",
    "official_dataset_name",
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

_WEBSITE_COLUMNS = [
    "availability",
    "dataset_download_instruction",
    "website_data_license",
    "website_usage_agreement",
]

_PAPER_COLUMNS = [
    "project_page",
    "website_accessible",
    "website_error",
    "venue",
    "year",
]

_COMPUTED_COLUMNS = [
    "num_usages",
    "tasks",
    "aliases",
    "usage_papers",
]

_COLUMNS = _METADATA_COLUMNS + _WEBSITE_COLUMNS + _PAPER_COLUMNS + _COMPUTED_COLUMNS


def _website_row(dw) -> dict:
    if dw is None:
        return {col: None for col in _WEBSITE_COLUMNS}
    return {
        "availability": dw.dataset_download.availability,
        "dataset_download_instruction": dw.dataset_download.dataset_download_instruction,
        "website_data_license": dw.dataset_license.data_license,
        "website_usage_agreement": dw.usage_agreement.usage_agreement,
    }


def _paper_row(dp, pp, pi) -> dict:
    if dp is None:
        return {col: None for col in _PAPER_COLUMNS}
    status = pp.website_status if pp is not None else None
    return {
        "project_page": dp.project_page,
        "website_accessible": status.accessible if status else None,
        "website_error": status.error if status else None,
        "venue": pi.venue if pi else None,
        "year": pi.year if pi else None,
    }


def _build_computed_lookups(usage_map: dict, usage_nodes) -> dict[str, dict]:
    usage_counts: dict[str, int] = {}
    tasks_by_dataset: dict[str, set] = {}
    aliases_by_dataset: dict[str, set] = {}
    usage_papers_by_dataset: dict[str, set] = {}

    doc_info: dict[str, dict] = {
        str(doc.doc_id): doc
        for doc in usage_nodes._table.all()
    }

    for doc_id, entry in usage_map.items():
        if entry is not None and entry.get("dataset_id"):
            did = entry["dataset_id"]
            usage_counts[did] = usage_counts.get(did, 0) + 1
            doc = doc_info.get(doc_id, {})
            for task in doc.get("tasks", []):
                tasks_by_dataset.setdefault(did, set()).add(task)
            aliases_by_dataset.setdefault(did, set()).add(doc.get("dataset_name", ""))
            for alias in doc.get("aliases", []):
                aliases_by_dataset[did].add(alias)
            paper_title = doc.get("paper_title")
            if paper_title:
                usage_papers_by_dataset.setdefault(did, set()).add(paper_title)

    return {
        "usage_counts": usage_counts,
        "tasks_by_dataset": {did: sorted(tasks) for did, tasks in tasks_by_dataset.items()},
        "aliases_by_dataset": {did: sorted(a for a in aliases if a) for did, aliases in aliases_by_dataset.items()},
        "usage_papers_by_dataset": {did: sorted(titles) for did, titles in usage_papers_by_dataset.items()},
    }


def _computed_row(dataset_id: str, lookups: dict) -> dict:
    return {
        "num_usages": lookups["usage_counts"].get(dataset_id, 0),
        "tasks": lookups["tasks_by_dataset"].get(dataset_id, []),
        "aliases": lookups["aliases_by_dataset"].get(dataset_id, []),
        "usage_papers": lookups["usage_papers_by_dataset"].get(dataset_id, []),
    }


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

    state = load_state(working_dir)
    metadata_db = state.metadata_db
    dataset_website_db = state.dataset_website_db
    dataset_paper_db = state.dataset_paper_db
    project_page_db = state.project_page_db
    paper_info_db = state.paper_info_db

    computed_lookups = _build_computed_lookups(usage_map, state.usage_nodes)

    rows = []
    for dataset_id in sorted(dataset_ids):
        node = metadata_db.get(dataset_id)
        if node is None:
            logger.warning("MetadataNode %r not found — skipping", dataset_id)
            continue
        dw = dataset_website_db.get(dataset_id)
        dp = dataset_paper_db.get(node.paper_title) if node.paper_title else None
        pp = project_page_db.get(node.paper_title) if node.paper_title else None
        pi = paper_info_db.get(node.paper_title) if node.paper_title else None
        row = {col: getattr(node, col, None) for col in _METADATA_COLUMNS}
        row.update(_website_row(dw))
        row.update(_paper_row(dp, pp, pi))
        row.update(_computed_row(dataset_id, computed_lookups))
        rows.append(row)

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
