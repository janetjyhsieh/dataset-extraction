"""Extract dataset usages and datasets (single-level) from all PDFs in working_dir/pdfs/.

Results are written to working_dir/fg/yyyy-mm-dd/hh-mm-ss/.

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
from dataset_extraction.graph_builder.build import create_and_save_dataset_paper, extract_datasets_and_save
from dataset_extraction.graph_builder.process_usages import _load_title_map, extract_and_save_usages
from dataset_extraction.log import setup_logging
from dataset_extraction.state.graph import DatasetNodes, DatasetPaperNodes, UsageNodes
from dataset_extraction.state.queue import DatasetJob

logger = logging.getLogger("dataset_extraction.fairground.process")


def extract_datasets_single_level(
    working_dir: Path,
    client,
    dataset_db: DatasetNodes,
    dataset_paper_db: DatasetPaperNodes,
) -> None:
    title_map = _load_title_map(working_dir)
    for pdf in sorted((working_dir / "pdfs").glob("*.pdf")):
        title = title_map.get(pdf.stem, pdf.stem)
        job = DatasetJob(title=title, pdf_path=str(pdf))
        logger.info("Extracting datasets from %s", pdf.name)
        new_dataset_nodes = extract_datasets_and_save(job, client, dataset_db)
        if new_dataset_nodes:
            create_and_save_dataset_paper(title, new_dataset_nodes, dataset_paper_db)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--working-dir", required=True, help="Directory containing pdfs/ and state/")
    parser.add_argument("--provider", choices=["claude", "openai", "foundry"], default="foundry")
    parser.add_argument("--model", default=None, help="Model ID (default: provider's default)")
    parser.add_argument("--reasoning-effort", choices=["low", "medium", "high"], default=None, help="Reasoning effort (foundry only)")
    args = parser.parse_args()

    working_dir = Path(args.working_dir)
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

    usage_nodes = UsageNodes(run_dir / "usages.json")
    dataset_db = DatasetNodes(run_dir / "dataset_nodes.json")
    dataset_paper_db = DatasetPaperNodes(run_dir / "dataset_paper_nodes.json")

    extract_and_save_usages(working_dir, client, usage_nodes)
    extract_datasets_single_level(working_dir, client, dataset_db, dataset_paper_db)

    logger.info("Done. Results in %s", run_dir)


if __name__ == "__main__":
    main()
