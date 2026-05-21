"""Extract dataset usages from all PDFs, discover their source datasets, and grow the graph.

Steps:
  1. For each PDF in working_dir/pdfs/, extract dataset usages and save as UsageNodes.
  2. For each usage with a source_title, enqueue the originating paper if not already in the graph or queue.
  3. Run build() to drain the queue (extract datasets from enqueued papers and find their parents).

Usage:
    python -m dataset_extraction.graph_builder.process_usages --working-dir papers/
    python -m dataset_extraction.graph_builder.process_usages --working-dir papers/ --provider openai
"""

import argparse
import json
from pathlib import Path
from typing import Union

from dataset_extraction.clients.claude import ClaudeClient
from dataset_extraction.clients.openai import OpenAIClient
from dataset_extraction.downloader.paper_finder import find_and_download_pdf
from dataset_extraction.graph_builder.build import _already_seen, build
from dataset_extraction.state.graph import DatasetNodes, DatasetPaperNodes, UsageNodes
from dataset_extraction.state.nodes import UsageNode
from dataset_extraction.state.paper import DatasetPaperNode, PdfInfo, canonicalize_title
from dataset_extraction.state.queue import DatasetJob, Queue
from dataset_extraction.usage.extractor import extract_usage

Client = Union[ClaudeClient, OpenAIClient]


def _load_title_map(working_dir: Path) -> dict[str, str]:
    index_path = working_dir / "index.jsonl"
    if not index_path.exists():
        return {}
    title_map: dict[str, str] = {}
    with open(index_path) as f:
        for line in f:
            if line.strip():
                record = json.loads(line)
                title_map[record["id"]] = record["title"]
    return title_map


def extract_and_save_usages(
    working_dir: Path,
    client: Client,
    usage_nodes: UsageNodes,
) -> list[UsageNode]:
    """Extract usages from all PDFs in working_dir/pdfs/ and save to the store.

    Skips papers that have already been processed. Returns all stored UsageNodes.
    """
    title_map = _load_title_map(working_dir)
    pdfs = sorted((working_dir / "pdfs").glob("*.pdf"))
    print(f"Found {len(pdfs)} PDF(s) under {working_dir}/pdfs")

    for pdf in pdfs:
        paper_id = pdf.stem
        paper_title = title_map.get(paper_id, paper_id)

        if usage_nodes.is_processed(paper_title):
            print(f"  Skipping {pdf.name} (already processed)")
            continue

        print(f"  Extracting usages from {pdf.name} ...", end=" ", flush=True)
        try:
            _, result = extract_usage(pdf, client)
        except Exception as exc:
            print(f"FAILED ({exc})")
            continue

        for usage in result.dataset_usages:
            usage_nodes.add(UsageNode(**usage.model_dump(), paper_title=paper_title))
        usage_nodes.mark_processed(paper_title)

        print(f"{len(result.dataset_usages)} usage(s)")

    return usage_nodes.all()


def enqueue_used_datasets(
    usages: list[UsageNode],
    paper_nodes: DatasetPaperNodes,
    queue: Queue[DatasetJob],
    working_dir: Path,
) -> None:
    """Ensure every used dataset's source paper is in the graph or queued for discovery."""
    download_dir = working_dir / "discovered" / "pdfs"

    for usage in usages:
        if not usage.source_title:
            print(f"  '{usage.dataset_name}' not in graph and has no source title, skipping")
            continue

        canonical = canonicalize_title(usage.source_title)

        if _already_seen(canonical, paper_nodes):
            print(f"  '{usage.source_title}' already in graph or queue")
            continue

        print(f"  '{usage.dataset_name}' not in graph — looking up '{usage.source_title}'...")
        node = DatasetPaperNode(
            raw_title=usage.source_title,
            canonical_title=canonical,
            pdf_info=PdfInfo(link_found=False, download_success=False),
        )
        pdf_path = find_and_download_pdf(node, download_dir) 
        paper_nodes.add(node)#TODO: should this happen before download?

        if pdf_path is None:
            print(f"    No PDF found for '{usage.source_title}': {node.pdf_info.errors}")
            continue

        queue.enqueue(DatasetJob(title=canonical, pdf_path=str(pdf_path)))
        print(f"    Enqueued '{usage.source_title}'")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--working-dir", required=True, help="Directory containing pdfs/ and state/")
    parser.add_argument("--provider", choices=["claude", "openai"], default="claude")
    parser.add_argument("--model", default=None, help="Model ID (default: provider's default)")
    args = parser.parse_args()

    kwargs = {} if args.model is None else {"model": args.model}
    client = ClaudeClient(**kwargs) if args.provider == "claude" else OpenAIClient(**kwargs)

    working_dir = Path(args.working_dir)
    queue: Queue[DatasetJob] = Queue(DatasetJob, working_dir / "state" / "dataset_queue.jsonl")
    nodes = DatasetNodes(working_dir / "state" / "graph.json")
    paper_nodes = DatasetPaperNodes(working_dir / "state" / "paper_nodes.json")
    usage_nodes = UsageNodes(working_dir / "state" / "usages.json")

    usages = extract_and_save_usages(working_dir, client, usage_nodes)
    enqueue_used_datasets(usages, paper_nodes, queue, working_dir)
    build(queue, client, nodes, paper_nodes, working_dir)


if __name__ == "__main__":
    main()
