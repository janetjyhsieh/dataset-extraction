import argparse
from pathlib import Path
from typing import Union

from dataset_extraction.state.queue import DatasetJob, Queue
from dataset_extraction.state.graph import Nodes
from dataset_extraction.state.nodes import DatasetNode
from dataset_extraction.dataset.datasets import DatasetSource
from dataset_extraction.clients.claude import ClaudeClient
from dataset_extraction.clients.openai import OpenAIClient
from dataset_extraction.dataset.extractor import extract_datasets

Client = Union[ClaudeClient, OpenAIClient]


def extract_datasets_and_save(job: DatasetJob, client: Client, nodes: Nodes) -> list[DatasetNode]:
    result = extract_datasets(job.pdf_path, client)
    new_dataset_nodes = []
    for dataset in result.new_datasets:
        dataset_node = DatasetNode(**dataset.model_dump(), source_processed=False)
        new_dataset_nodes.append(dataset_node)
        nodes.add(dataset_node)
    return new_dataset_nodes


def _already_seen(name: str, nodes: Nodes, queue: Queue[DatasetJob]) -> bool:
    if nodes.exists(name):
        return True
    return any(job.title == name for job in queue.all())


def process_source_datasets(dataset_node: DatasetNode, nodes: Nodes, queue: Queue[DatasetJob]) -> None:
    # Step 1: find and download the paper pdf associated with each of the source dataset
    # Step 2: add new papers to queue.
    # Additional note: When adding new papers to queue, must check the current papers in queue
    # and the papers (not datasets!) already in the graph (nodes.json)!
    raise NotImplementedError


def build(queue: Queue[DatasetJob], client: Client, nodes: Nodes) -> None:
    while len(queue) > 0:
        job = queue.peek()
        print(f"Processing: {job.title}")
        new_dataset_nodes = extract_datasets_and_save(job, client, nodes)
        queue.dequeue()
        for dataset_node in new_dataset_nodes:
            process_source_datasets(dataset_node, nodes, queue)
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
    build(queue, client, nodes)


if __name__ == "__main__":
    main()
