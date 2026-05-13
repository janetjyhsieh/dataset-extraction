import argparse
from pathlib import Path
from typing import Union

from dataset_extraction.state.queue import DatasetJob, Queue
from dataset_extraction.state.graph import Nodes
from dataset_extraction.state.nodes import DatasetNode
from dataset_extraction.clients.claude import ClaudeClient
from dataset_extraction.clients.openai import OpenAIClient
from dataset_extraction.dataset.extractor import extract_datasets
from dataset_extraction.downloader.paper_finder import download_pdf, find_open_access_pdf

Client = Union[ClaudeClient, OpenAIClient]


def extract_datasets_and_save(job: DatasetJob, client: Client, nodes: Nodes) -> list[DatasetNode]:
    result = extract_datasets(job.pdf_path, client)
    new_dataset_nodes = []
    for dataset in result.new_datasets:
        dataset_node = DatasetNode(**dataset.model_dump(), source_processed=False, paper_title=job.title)
        new_dataset_nodes.append(dataset_node)
        nodes.add(dataset_node)
    return new_dataset_nodes


def _already_seen(paper_title: str, nodes: Nodes, queue: Queue[DatasetJob]) -> bool:
    #TODO: should be cap-insensitive
    if any(node.paper_title == paper_title for node in nodes.all()):
        return True
    # TODO: debug this: job still get enqueued when titles are the exact same.
    return any(job.title == paper_title for job in queue.all())


def process_source_datasets(
    dataset_node: DatasetNode,
    nodes: Nodes,
    queue: Queue[DatasetJob],
    working_dir: Path,
) -> None:
    download_dir = working_dir / "discovered" / "pdfs"

    for source in dataset_node.sources:
        paper = source.source_paper
        if _already_seen(paper.title, nodes, queue):
            print(f"  Skipping '{paper.title}' (already seen)")
            continue

        print(f"  Looking up PDF for '{paper.title}'...")
        pdf_url = find_open_access_pdf(paper.title, paper.first_author)
        if pdf_url is None:
            # TODO: still create new node for these, just no analysis
            print(f"  No open-access PDF found for '{paper.title}'")
            continue

        pdf_path = download_pdf(pdf_url, paper.title, download_dir)
        if pdf_path is None:
            # probably need some proper error handlnig
            print(f"  Failed to download PDF for '{paper.title}'")
            continue

        queue.enqueue(DatasetJob(title=paper.title, pdf_path=str(pdf_path)))
        print(f"  Enqueued '{paper.title}'")


def process_unprocessed_nodes(nodes: Nodes, queue: Queue[DatasetJob], working_dir: Path) -> None:
    """Call process_source_datasets for every node with source_processed=False."""
    unprocessed = [node for node in nodes.all() if not node.source_processed]
    print(f"Found {len(unprocessed)} unprocessed node(s)")
    for node in unprocessed:
        print(f"Processing sources for: {node.name}")
        process_source_datasets(node, nodes, queue, working_dir)
        node.source_processed = True
        nodes.add(node)


def build(queue: Queue[DatasetJob], client: Client, nodes: Nodes, working_dir: Path) -> None:
    while len(queue) > 0:
        job = queue.peek()
        print(f"Processing: {job.title}")
        new_dataset_nodes = extract_datasets_and_save(job, client, nodes)
        queue.dequeue()
        for dataset_node in new_dataset_nodes:
            process_source_datasets(dataset_node, nodes, queue, working_dir)
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
    process_unprocessed_nodes(nodes, queue, working_dir)
    build(queue, client, nodes, working_dir)


if __name__ == "__main__":
    main()
