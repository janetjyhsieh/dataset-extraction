"""Extract dataset usages from all PDFs, discover their source datasets, and grow the graph.

Steps:
  1. For each PDF in working_dir/pdfs/, extract dataset usages and save as UsageNodes.
  2. For each usage with a source_paper.title, enqueue the originating paper if not already in the graph or queue.
  3. Run build() to drain the queue (extract datasets from enqueued papers and find their parents).

Usage:
    python -m dataset_extraction.graph_builder.process_usages --working-dir papers/
    python -m dataset_extraction.graph_builder.process_usages --working-dir papers/ --provider openai
"""

import argparse
import logging
from pathlib import Path
from typing import Union

from dataset_extraction.clients.claude import ClaudeClient
from dataset_extraction.clients.foundry import FoundryClient
from dataset_extraction.clients.openai import OpenAIClient
from dataset_extraction.graph_builder.build import build
from dataset_extraction.log import setup_logging
from dataset_extraction.state.graph import DatasetNodes, DatasetPaperNodes, PaperInfoNodes
from dataset_extraction.usage.nodes import UsageNodes
from dataset_extraction.state.queue import DatasetJob, Queue
from dataset_extraction.usage.extractor import extract_and_save_usages
from dataset_extraction.usage.process import enqueue_used_datasets

logger = logging.getLogger("dataset_extraction.graph_builder.process_usages")

Client = Union[ClaudeClient, FoundryClient, OpenAIClient]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--working-dir", required=True, help="Directory containing pdfs/ and state/")
    parser.add_argument("--provider", choices=["claude", "openai", "foundry"], default="claude")
    parser.add_argument("--model", default=None, help="Model ID (default: provider's default)")
    parser.add_argument("--reasoning-effort", choices=["low", "medium", "high"], default=None, help="Reasoning effort (foundry only)")
    args = parser.parse_args()

    kwargs = {} if args.model is None else {"model": args.model}
    if args.provider == "claude":
        client = ClaudeClient(**kwargs)
    elif args.provider == "openai":
        client = OpenAIClient(**kwargs)
    else:
        if args.reasoning_effort is not None:
            kwargs["reasoning_effort"] = args.reasoning_effort
        client = FoundryClient(**kwargs)

    working_dir = Path(args.working_dir)
    setup_logging(working_dir / "logs")
    queue: Queue[DatasetJob] = Queue(DatasetJob, working_dir / "state" / "dataset_queue.jsonl")
    dataset_db = DatasetNodes(working_dir / "state" / "dataset_nodes.json")
    paper_info_db = PaperInfoNodes(working_dir / "state" / "paper_info_nodes.json")
    dataset_paper_db = DatasetPaperNodes(working_dir / "state" / "dataset_paper_nodes.json")
    usage_nodes = UsageNodes(working_dir / "state" / "usages.json")

    usages = extract_and_save_usages(working_dir, client, usage_nodes)
    enqueue_used_datasets(usages, paper_info_db, queue, working_dir)
    build(queue, client, dataset_paper_db, dataset_db, paper_info_db, working_dir)


if __name__ == "__main__":
    main()
