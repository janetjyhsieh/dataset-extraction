from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dataset_extraction.state.databases import (
    DatasetPaperNodes,
    DatasetWebsiteNodes,
    MetadataNodes,
    PaperInfoNodes,
    ProjectPageNodes,
)
from dataset_extraction.state.queue import DatasetJob, Queue
from dataset_extraction.usage.nodes import UsageNodes


@dataclass
class FairgroundState:
    metadata_db: MetadataNodes
    dataset_paper_db: DatasetPaperNodes
    dataset_website_db: DatasetWebsiteNodes
    project_page_db: ProjectPageNodes
    paper_info_db: PaperInfoNodes
    queue: Queue
    usage_nodes: UsageNodes


def load_state(working_dir: Path) -> FairgroundState:
    usage_state_dir = working_dir / "state"
    state_dir = working_dir / "fg" / "state"
    databases_dir = working_dir / "fg" / "databases"
    usage_state_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    databases_dir.mkdir(parents=True, exist_ok=True)
    return FairgroundState(
        metadata_db=MetadataNodes(databases_dir / "metadata_nodes.json"),
        dataset_paper_db=DatasetPaperNodes(databases_dir / "dataset_paper_nodes.json"),
        dataset_website_db=DatasetWebsiteNodes(databases_dir / "dataset_website_nodes.json"),
        project_page_db=ProjectPageNodes(databases_dir / "project_page_nodes.json"),
        paper_info_db=PaperInfoNodes(state_dir / "paper_info_nodes.json"),
        queue=Queue(DatasetJob, state_dir / "dataset_queue.jsonl"),
        usage_nodes=UsageNodes(usage_state_dir / "usages.json"),
    )
