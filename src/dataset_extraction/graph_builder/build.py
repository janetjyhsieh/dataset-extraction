import argparse
from pathlib import Path
from typing import Union

from dataset_extraction.clients.claude import ClaudeClient
from dataset_extraction.clients.openai import OpenAIClient
from dataset_extraction.dataset.extractor import extract_datasets
from dataset_extraction.downloader.paper_finder import find_and_download_pdf
from dataset_extraction.state.graph import DatasetNodes, DatasetPaperNodes
from dataset_extraction.state.nodes import DatasetNode
from dataset_extraction.state.paper import DatasetPaperNode, PdfInfo, canonicalize_title
from dataset_extraction.state.queue import DatasetJob, Queue

Client = Union[ClaudeClient, OpenAIClient]


def extract_datasets_and_save(
    job: DatasetJob,
    client: Client,
    nodes: DatasetNodes,
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
        nodes.insert(dataset_node)
    return new_dataset_nodes


def _already_seen(canonical_title: str, papers_db: DatasetPaperNodes) -> bool:
    return papers_db.exists(canonical_title)


def process_source_datasets(
    dataset_node: DatasetNode,
    paper_node: DatasetPaperNode,
    papers_db: DatasetPaperNodes,
    queue: Queue[DatasetJob],
    working_dir: Path,
) -> None:
    download_dir = working_dir / "discovered" / "pdfs"

    for source in dataset_node.sources:
        source_paper_info = source.source_paper
        canonical_title = canonicalize_title(source_paper_info.title)

        if canonical_title not in paper_node.source_papers_titles:
            paper_node.source_papers_titles.append(canonical_title)

        if _already_seen(canonical_title, papers_db):
            print(f"  Skipping '{source_paper_info.title}' (already seen)")
            continue

        print(f"  Looking up PDF for '{source_paper_info.title}'...")
        source_paper_node = DatasetPaperNode(
            raw_title=source_paper_info.title,
            canonical_title=canonical_title,
            pdf_info=PdfInfo(link_found=False, download_success=False),
        )
        pdf_path = find_and_download_pdf(source_paper_node, download_dir)
        papers_db.insert(source_paper_node)

        if pdf_path is None:
            print(f"  No PDF found for '{source_paper_info.title}': {source_paper_node.pdf_info.errors}")
            continue

        queue.enqueue(DatasetJob(title=canonical_title, pdf_path=str(pdf_path)))
        print(f"  Enqueued '{source_paper_info.title}'")

    papers_db.update(paper_node)


def process_unprocessed_nodes(
    nodes_db: DatasetNodes,
    papers_db: DatasetPaperNodes,
    queue: Queue[DatasetJob],
    working_dir: Path,
) -> None:
    """Call process_source_datasets for every node with source_processed=False."""
    unprocessed = [node for node in nodes_db.all() if not node.source_processed]
    print(f"Found {len(unprocessed)} unprocessed node(s)")
    for node in unprocessed:
        print(f"Processing sources for: {node.name}")
        paper_node = papers_db.get(node.paper_title or "")
        assert paper_node is not None, f"No DatasetPaperNode found for '{node.paper_title}'"
        process_source_datasets(node, paper_node, papers_db, queue, working_dir)
        node.source_processed = True
        nodes_db.update(node)


def build(
    queue: Queue[DatasetJob],
    client: Client,
    nodes_db: DatasetNodes,
    papers_db: DatasetPaperNodes,
    working_dir: Path,
) -> None:
    while len(queue) > 0:
        job = queue.peek()
        print(f"Processing: {job.title}")
        paper_node = papers_db.get(job.title)
        assert paper_node is not None, f"No DatasetPaperNode found for '{job.title}'"
        new_dataset_nodes = extract_datasets_and_save(job, client, nodes_db)
        queue.dequeue()
        for dataset_node in new_dataset_nodes:
            process_source_datasets(dataset_node, paper_node, papers_db, queue, working_dir)
            dataset_node.source_processed = True
            nodes_db.update(dataset_node)


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
    nodes_db = DatasetNodes(working_dir / "state" / "dataset_nodes.json")
    papers_db = DatasetPaperNodes(working_dir / "state" / "paper_nodes.json")
    process_unprocessed_nodes(nodes_db, papers_db, queue, working_dir) #TODO: check 
    build(queue, client, nodes_db, papers_db, working_dir)


if __name__ == "__main__":
    main()
