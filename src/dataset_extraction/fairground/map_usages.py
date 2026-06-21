"""Map each usage in state/usages.json to an official dataset introduced by its source paper.

Reads:
  working_dir/state/usages.json                      – UsageNodes (TinyDB)
  working_dir/fg/databases/metadata_nodes.json        – MetadataNodes
  working_dir/fg/databases/dataset_paper_nodes.json   – DatasetPaperNodes

Writes:
  working_dir/fg/databases/usage_map.json  – dict keyed by usage TinyDB doc_id

Usage:
    python -m dataset_extraction.fairground.map_usages --working-dir papers/
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from dataset_extraction.clients.foundry import DEFAULT_MODEL
from dataset_extraction.log import setup_logging
from dataset_extraction.mapper.map import map_datasets
from dataset_extraction.state.graph import MetadataNodes, DatasetPaperNodes
from dataset_extraction.state.paper import canonicalize_title
from dataset_extraction.usage.nodes import UsageNode, UsageNodes

logger = logging.getLogger("dataset_extraction.fairground.map_usages")


def _load_output(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return {}


def _save_output(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2))


def run(working_dir: Path, model: str = DEFAULT_MODEL) -> None:
    databases_dir = working_dir / "fg" / "databases"
    databases_dir.mkdir(parents=True, exist_ok=True)

    usage_nodes = UsageNodes(working_dir / "state" / "usages.json")
    dataset_metadata_db = MetadataNodes(databases_dir / "metadata_nodes.json")
    dataset_paper_db = DatasetPaperNodes(databases_dir / "dataset_paper_nodes.json")

    output_path = databases_dir / "usage_map.json"
    output = _load_output(output_path)

    raw_docs = usage_nodes._table.all()
    logger.info("Processing %d usages", len(raw_docs))

    for doc in raw_docs:
        doc_id = str(doc.doc_id)
        if doc_id in output:
            logger.debug("Skipping usage %s (already mapped)", doc_id)
            continue

        usage = UsageNode.model_validate(dict(doc))

        source_title = usage.source_paper.title
        if not source_title:
            logger.warning("Usage %s has no source_paper.title — skipping", doc_id)
            output[doc_id] = None
            _save_output(output_path, output)
            continue

        canonical = canonicalize_title(source_title)
        paper_node = dataset_paper_db.get(canonical)
        if paper_node is None:
            logger.warning("DatasetPaperNode not found for %r — skipping usage %s", canonical, doc_id)
            output[doc_id] = None
            _save_output(output_path, output)
            continue

        official_datasets = []
        for dataset_id in paper_node.datasets:
            node = dataset_metadata_db.get(dataset_id)
            if node is None:
                logger.warning("DatasetNode %r not found", dataset_id)
                continue
            official_datasets.append({
                "id": dataset_id,
                "name": node.official_dataset_name,
                "description": node.descriptions,
            })

        if not official_datasets:
            logger.warning("No official datasets found for paper %r — skipping usage %s", canonical, doc_id)
            output[doc_id] = None
            _save_output(output_path, output)
            continue

        usage_dataset = {
            "name": usage.dataset_name,
            "description": usage.dataset_task_summary,
        }

        try:
            result = map_datasets(usage_dataset, official_datasets, model=model)
        except Exception:
            logger.exception("map_datasets failed for usage %s", doc_id)
            output[doc_id] = None
            _save_output(output_path, output)
            continue

        if result is None:
            logger.warning("Usage %s — mapper returned invalid choice after retry, skipping", doc_id)
            output[doc_id] = None
        else:
            output[doc_id] = result.model_dump()
            logger.info("Usage %s → %r dataset_id=%s (confidence=%.2f)", doc_id, result.choice, result.dataset_id, result.confidence)

        _save_output(output_path, output)

    logger.info("Done. %d/%d usages mapped. Results at %s", sum(v is not None for v in output.values()), len(raw_docs), output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--working-dir", required=True, help="Directory containing state/ and fg/")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model ID for the mapper")
    args = parser.parse_args()

    working_dir = Path(args.working_dir)
    setup_logging(working_dir / "fg" / "logs")
    run(working_dir, model=args.model)


if __name__ == "__main__":
    main()
