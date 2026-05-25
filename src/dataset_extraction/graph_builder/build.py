import argparse
from pathlib import Path
from typing import Union

from dataset_extraction.clients.claude import ClaudeClient
from dataset_extraction.clients.foundry import FoundryClient
from dataset_extraction.clients.openai import OpenAIClient
from dataset_extraction.dataset.extractor import extract_datasets
from dataset_extraction.downloader.paper_finder import find_and_download_pdf
from dataset_extraction.state.graph import DatasetNodes, DatasetPaperNodes, PaperInfoNodes
from dataset_extraction.state.nodes import DatasetNode
from dataset_extraction.state.paper import DatasetPaperNode, PdfInfo, PaperInfo 
from dataset_extraction.state.paper import canonicalize_title
from dataset_extraction.state.queue import DatasetJob, Queue

Client = Union[ClaudeClient, FoundryClient, OpenAIClient]


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
            paper_title=job.title,
            # Need an identifier for the dataset
        )
        new_dataset_nodes.append(dataset_node)
        nodes.insert(dataset_node)
    return new_dataset_nodes

def create_and_save_dataset_paper(title: str, dataset_nodes: list[DatasetNode], dataset_paper_db: DatasetPaperNodes):
    source_titles = {
        canonicalize_title(source.source_paper.title)
        for node in dataset_nodes
        for source in node.sources
    }
    dataset_paper = DatasetPaperNode(
            title = title,
            datasets = [dn.name for dn in dataset_nodes],
            source_papers_titles = list(source_titles)
        )
    dataset_paper_db.insert(dataset_paper)
    return dataset_paper

def _already_seen(canonical_title: str, paper_info_db: PaperInfoNodes) -> bool:
    return paper_info_db.exists(canonical_title)


def process_source_datasets(
    dataset_paper, paper_info_db,
    queue: Queue[DatasetJob],
    working_dir: Path,
) -> None:
    download_dir = working_dir / "discovered" / "pdfs"

    for source_title in dataset_paper.source_papers_titles:
        if _already_seen(source_title, paper_info_db):
            print(f"  Skipping '{source_title}' (already seen)")
            continue

        print(f"  Looking up PDF for '{source_title}'...")
        source_paper_info = PaperInfo(
            canonical_title=source_title,
            pdf_info=PdfInfo(link_found=False, download_success=False),
        )
        pdf_path = find_and_download_pdf(source_paper_info, download_dir)
        paper_info_db.insert(source_paper_info)

        if pdf_path is None:
            print(f"  No PDF found for '{source_paper_info.canonical_title}': {source_paper_info.pdf_info.errors}")
            continue

        queue.enqueue(DatasetJob(title=source_title, pdf_path=str(pdf_path)))
        print(f"  Enqueued '{source_paper_info.canonical_title}'")

def process_unprocessed_nodes(
    dataset_paper_db: DatasetPaperNodes,
    paper_info_db: PaperInfoNodes,
    queue: Queue[DatasetJob],
    working_dir: Path,
) -> None:
    """Call process_source_datasets for every node with source_processed=False."""
    unprocessed = [dp for dp in dataset_paper_db.all() if not dp.source_processed]
    print(f"Found {len(unprocessed)} unprocessed node(s)")
    for dataset_paper in unprocessed:
        print(f"Processing sources for: {dataset_paper.title}")
        process_source_datasets(dataset_paper, paper_info_db, queue, working_dir)
        dataset_paper.source_processed = True
        dataset_paper_db.update(dataset_paper)


def build(
    queue: Queue[DatasetJob],
    client: Client,
    dataset_paper_db: DatasetPaperNodes, 
    dataset_db: DatasetNodes, 
    paper_info_db: PaperInfoNodes,
    working_dir: Path,
) -> None:
    while len(queue) > 0:
        job = queue.peek()
        print(f"Processing: {job.title}")
        new_dataset_nodes = extract_datasets_and_save(job, client, dataset_db)
        if len(new_dataset_nodes) > 0:
            dataset_paper = create_and_save_dataset_paper(job.title, new_dataset_nodes, dataset_paper_db)
            queue.dequeue()
            for source_title in dataset_paper.source_papers_titles:
                process_source_datasets(dataset_paper, paper_info_db, queue, working_dir)
            dataset_paper.source_processed = True
            dataset_paper_db.update(dataset_paper)
        else:
            queue.dequeue()


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
        choices=["claude", "openai", "foundry"],
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
    elif args.provider == "openai":
        client = OpenAIClient(**kwargs)
    else:
        client = FoundryClient(**kwargs)

    working_dir = Path(args.working_dir)
    queue: Queue[DatasetJob] = Queue(DatasetJob, working_dir / "state" / "dataset_queue.jsonl")
    dataset_db = DatasetNodes(working_dir / "state" / "dataset_nodes.json")
    paper_info_db = PaperInfoNodes(working_dir / "state" / "paper_info_nodes.json")
    dataset_paper_db = DatasetPaperNodes(working_dir / "state" / "dataset_paper_nodes.json")
    process_unprocessed_nodes(dataset_paper_db, paper_info_db, queue, working_dir) #TODO: check 
    build(queue, client, dataset_paper_db, dataset_db, paper_info_db, working_dir)


if __name__ == "__main__":
    main()
