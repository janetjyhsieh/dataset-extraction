import argparse
from pathlib import Path
from typing import Union

from dataset_extraction.clients.claude import ClaudeClient
from dataset_extraction.clients.openai import OpenAIClient
from dataset_extraction.dataset.extractor import extract_datasets
from dataset_extraction.downloader.paper_finder import find_and_download_pdf
from dataset_extraction.state.graph import DatasetPaperNodes, Nodes
from dataset_extraction.state.nodes import DatasetNode
from dataset_extraction.state.paper import DatasetPaperNode, PdfInfo, canonicalize_title
from dataset_extraction.state.queue import DatasetJob, Queue

Client = Union[ClaudeClient, OpenAIClient]


def extract_datasets_and_save(
    job: DatasetJob,
    client: Client,
    nodes: Nodes,
) -> list[DatasetNode]:
    result = extract_datasets(job.pdf_path, client)
    new_dataset_nodes = []
    for dataset in result.new_datasets:
        dataset_node = DatasetNode(
            **dataset.model_dump(),
            source_processed=False,
            paper_title=job.title,
        )
        new_dataset_nodes.append(dataset_node)
        nodes.add(dataset_node)
    return new_dataset_nodes


def _already_seen(canonical_title: str, paper_nodes: DatasetPaperNodes) -> bool:
    return paper_nodes.exists(canonical_title)


def process_source_datasets(
    dataset_node: DatasetNode,
    paper_node: DatasetPaperNode,
    nodes: Nodes,
    paper_nodes: DatasetPaperNodes,
    queue: Queue[DatasetJob],
    working_dir: Path,
) -> None:
    download_dir = working_dir / "discovered" / "pdfs"

    for source in dataset_node.sources:
        paper = source.source_paper
        canonical = canonicalize_title(paper.title)

        if canonical not in paper_node.source_papers:
            paper_node.source_papers.append(canonical)

        if _already_seen(canonical, paper_nodes):
            print(f"  Skipping '{paper.title}' (already seen)")
            continue

        print(f"  Looking up PDF for '{paper.title}'...")
        source_paper_node = DatasetPaperNode(
            raw_title=paper.title,
            canonical_title=canonical,
            pdf_info=PdfInfo(link_found=False, download_success=False),
        )
        pdf_path = find_and_download_pdf(source_paper_node, download_dir)
        paper_nodes.add(source_paper_node)#TODO should this happen before download?

        if pdf_path is None:
            print(f"  No PDF found for '{paper.title}': {source_paper_node.pdf_info.errors}")
            continue

        queue.enqueue(DatasetJob(title=canonical, pdf_path=str(pdf_path)))
        print(f"  Enqueued '{paper.title}'")

    paper_nodes.add(paper_node)


def process_unprocessed_nodes(
    nodes: Nodes,
    paper_nodes: DatasetPaperNodes,
    queue: Queue[DatasetJob],
    working_dir: Path,
) -> None:
    """Call process_source_datasets for every node with source_processed=False."""
    unprocessed = [node for node in nodes.all() if not node.source_processed]
    print(f"Found {len(unprocessed)} unprocessed node(s)")
    for node in unprocessed:
        print(f"Processing sources for: {node.name}")
        paper_node = paper_nodes.get(node.paper_title or "")
        assert paper_node is not None, f"No DatasetPaperNode found for '{node.paper_title}'"
        process_source_datasets(node, paper_node, nodes, paper_nodes, queue, working_dir)
        node.source_processed = True
        nodes.add(node)


def build(
    queue: Queue[DatasetJob],
    client: Client,
    nodes: Nodes,
    paper_nodes: DatasetPaperNodes,
    working_dir: Path,
) -> None:
    while len(queue) > 0:
        job = queue.peek()
        print(f"Processing: {job.title}")
        paper_node = paper_nodes.get(job.title)
        assert paper_node is not None, f"No DatasetPaperNode found for '{job.title}'"
        new_dataset_nodes = extract_datasets_and_save(job, client, nodes)
        queue.dequeue()
        for dataset_node in new_dataset_nodes:
            process_source_datasets(dataset_node, paper_node, nodes, paper_nodes, queue, working_dir)
            dataset_node.source_processed = True
            nodes.add(dataset_node)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Process dataset jobs from the queue."
    )
    parser.add_argument(
        "--working-dir",
        required=True,
        help="Conference paper directory containing state/dataset_queue.jsonl",
    )
    parser.add_argument(
        "--provider",
        choices=["claude", "openai"],
        default="claude",
        help="LLM provider (default: claude)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model ID (default: provider's default model)",
    )
    args = parser.parse_args()

    kwargs = {} if args.model is None else {"model": args.model}
    if args.provider == "claude":
        client = ClaudeClient(**kwargs)
    else:
        client = OpenAIClient(**kwargs)

    working_dir = Path(args.working_dir)
    queue: Queue[DatasetJob] = Queue(DatasetJob, working_dir / "state" / "dataset_queue.jsonl")
    nodes = Nodes(working_dir / "state" / "graph.json")
    paper_nodes = DatasetPaperNodes(working_dir / "state" / "paper_nodes.json")
    process_unprocessed_nodes(nodes, paper_nodes, queue, working_dir)
    build(queue, client, nodes, paper_nodes, working_dir)


if __name__ == "__main__":
    main()
