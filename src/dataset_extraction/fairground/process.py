"""Extract dataset usages and metadata from all PDFs in working_dir/pdfs/.

Usage extraction is skipped if working_dir/state/usages.json already exists.
Metadata results are written to working_dir/fg/yyyy-mm-dd/hh-mm-ss/.

Usage:
    python -m dataset_extraction.fairground.process --working-dir papers/
    python -m dataset_extraction.fairground.process --working-dir papers/ --provider foundry
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path

from dataset_extraction.clients.claude import ClaudeClient
from dataset_extraction.clients.foundry import FoundryClient
from dataset_extraction.clients.openai import OpenAIClient
from dataset_extraction.fairground.metadata.extractor import extract_metadata
from dataset_extraction.graph_builder.process_usages import enqueue_used_datasets, extract_and_save_usages
from dataset_extraction.log import setup_logging
from dataset_extraction.state.graph import MetadataNodes, PaperInfoNodes, UsageNodes
from dataset_extraction.state.nodes import MetadataNode
from dataset_extraction.state.paper import canonicalize_title
from dataset_extraction.state.queue import DatasetJob, Queue

logger = logging.getLogger("dataset_extraction.fairground.process")


def extract_and_save_metadata(
    queue: Queue[DatasetJob],
    client,
    metadata_db: MetadataNodes,
) -> None:
    while len(queue) > 0:
        job = queue.peek()
        logger.info("Extracting metadata from %s", job.title)
        try:
            result = extract_metadata(job.pdf_path, client)
        except Exception:
            logger.exception("Metadata extraction failed for %s", job.title)
            queue.dequeue()
            continue
        data = result.model_dump()
        data["paper_title"] = canonicalize_title(result.paper_title)
        metadata_db.upsert(MetadataNode(**data))
        queue.dequeue()
        logger.info("Saved %d dataset(s) from %s", len(result.datasets), job.title)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--working-dir", required=True, help="Directory containing pdfs/ and state/")
    parser.add_argument("--provider", choices=["claude", "openai", "foundry"], default="foundry")
    parser.add_argument("--model", default=None, help="Model ID (default: provider's default)")
    parser.add_argument("--reasoning-effort", choices=["low", "medium", "high"], default=None, help="Reasoning effort (foundry only)")
    args = parser.parse_args()

    working_dir = Path(args.working_dir)
    (working_dir / "fg" / "state").mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    run_dir = working_dir / "fg" / now.strftime("%Y-%m-%d") / now.strftime("%H-%M-%S")
    run_dir.mkdir(parents=True, exist_ok=True)

    setup_logging(run_dir / "logs")

    kwargs = {} if args.model is None else {"model": args.model}
    if args.provider == "claude":
        client = ClaudeClient(**kwargs)
    elif args.provider == "openai":
        client = OpenAIClient(**kwargs)
    else:
        if args.reasoning_effort is not None:
            kwargs["reasoning_effort"] = args.reasoning_effort
        client = FoundryClient(**kwargs)

    usages_path = working_dir / "state" / "usages.json"
    usage_nodes = UsageNodes(usages_path)
    if not usages_path.exists():
        logger.info("No usages.json found — running usage extraction")
        extract_and_save_usages(working_dir, client, usage_nodes)
    else:
        logger.info("Skipping usage extraction (usages.json already exists)")

    paper_info_db = PaperInfoNodes(working_dir / "fg" / "state" / "paper_info_nodes.json")
    queue: Queue[DatasetJob] = Queue(DatasetJob, working_dir / "fg" / "state" / "dataset_queue.jsonl")
    enqueue_used_datasets(usage_nodes.all(), paper_info_db, queue, working_dir)

    metadata_db = MetadataNodes(run_dir / "metadata_nodes.json")
    extract_and_save_metadata(queue, client, metadata_db)

    logger.info("Done. Results in %s", run_dir)


if __name__ == "__main__":
    main()
