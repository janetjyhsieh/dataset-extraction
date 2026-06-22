"""Extract dataset usages and metadata from all PDFs in working_dir/pdfs/.

Usage extraction is skipped if working_dir/state/usages.json already exists.
Metadata results are written to working_dir/fg/yyyy-mm-dd/hh-mm-ss/.

Usage:
    python -m dataset_extraction.fairground.process --working-dir papers/
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
from dataset_extraction.fairground.metadata.metadata import MetadataExtractionResult
from dataset_extraction.fairground.webpage.extractor import extract_webpage
from dataset_extraction.fairground.webpage.webpage import WebsiteExtractionResult

from dataset_extraction.usage.process import enqueue_used_datasets
from dataset_extraction.usage.extractor import extract_and_save_usages
from dataset_extraction.usage.nodes import UsageNodes
from dataset_extraction.log import setup_logging
from dataset_extraction.state.graph import MetadataNodes, PaperInfoNodes, DatasetPaperNodes
from dataset_extraction.state.graph import DatasetWebsiteNodes, ProjectPageNodes
from dataset_extraction.state.nodes import MetadataNode, DatasetWebsiteNode
from dataset_extraction.state.paper import canonicalize_title, DatasetPaperNode, ProjectPageNode
from dataset_extraction.state.queue import DatasetJob, Queue

logger = logging.getLogger("dataset_extraction.fairground.process")

def save_dataset_paper(
    result: MetadataExtractionResult,
    canonical_title: str,
    dataset_ids: List[str],
    dataset_paper_db: DatasetPaperNodes
) -> DatasetPaperNode:
    dp = DatasetPaperNode(
        title=canonical_title, 
        datasets=dataset_ids,
        project_page=result.project_page
    )
    dataset_paper_db.insert(dp)
    return dp

def save_metadata(
    result: MetadataExtractionResult, 
    canonical_title: str,
    metadata_db: MetadataNodes,
) -> List[str]:
    dataset_ids = []
    for dataset_metadata in result.datasets:
        data = dataset_metadata.model_dump()
        data["paper_title"] = canonical_title
        metadata = MetadataNode(**data)
        dataset_ids.append(metadata.dataset_id)
        metadata_db.upsert(metadata)
    return dataset_ids

def save_dataset_website(
    result: WebsiteExtractionResult,
    canonical_title: str,
    dataset_ids: list[str],
    dataset_website_db: DatasetWebsiteNodes
):
    for i, dataset_info in enumerate(result.datasets_info):
        data = dataset_info.model_dump()
        dw = DatasetWebsiteNode(
            paper_title=canonical_title,
            dataset_id=dataset_ids[i],
            **data
        )
        dataset_website_db.insert(dw)

def save_project_website(
    canonical_title: str,
    result: WebsiteExtractionResult,
    project_page_db: ProjectPageNodes
):
    pw = ProjectPageNode(
        paper_title = canonical_title,
        project_page = result.url,
        website_status = result.website_status
    )
    project_page_db.insert(pw)


def extract_and_save_metadata(
    queue: Queue[DatasetJob],
    client,
    metadata_db: MetadataNodes,
    dataset_paper_db: DatasetPaperNodes,
    dataset_website_db: DatasetWebsiteNodes,
    project_page_db: ProjectPageNodes
) -> None:
    while len(queue) > 0:
        job = queue.peek()
        logger.info("Extracting metadata from %s", job.title)
        try:
            result = extract_metadata(job.pdf_path, client)
        except Exception:
            logger.exception("Metadata extraction failed for %s", job.title)
            queue.dequeue() #TODO: re-enqueue?
            continue
        canonical_title = job.title
        dataset_ids = save_metadata(result, canonical_title, metadata_db)
        dataset_paper = save_dataset_paper(
            result, canonical_title, dataset_ids, dataset_paper_db
        )
        queue.dequeue()

        logger.info("Saved %d dataset(s) from %s", len(result.datasets), canonical_title)

        if dataset_paper.project_page:
            #TODO: this can be a function of the database. This is also used in mapper
            dataset_names = [dataset_metadata.official_dataset_name for dataset_metadata in result.datasets]
            try:
                result = extract_webpage(dataset_paper.project_page, canonical_title, 
                dataset_names, model=client.model)
            except Exception:
                logger.exception("Website extraction failed for %s", job.title)
                continue
            dataset_ids = save_dataset_website(
                result, canonical_title, dataset_ids, dataset_website_db
            )
            save_project_website(canonical_title, result, project_page_db)
            dataset_paper.link_processed=True
            dataset_paper_db.update(dataset_paper)
            


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--working-dir", required=True, help="Directory containing pdfs/ and state/")
    parser.add_argument("--model", default=None, help="Model ID (default: provider's default)")
    parser.add_argument("--reasoning-effort", choices=["low", "medium", "high"], default=None, help="Reasoning effort (foundry only)")
    parser.add_argument("--repopulate-queue", action="store_true", help="Re-enqueue all paper_info entries and run metadata extraction")
    args = parser.parse_args()

    working_dir = Path(args.working_dir)
    (working_dir / "fg" / "state").mkdir(parents=True, exist_ok=True)
    databases_dir = working_dir / "fg" / "databases"
    databases_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    run_dir = working_dir / "fg" / now.strftime("%Y-%m-%d") / now.strftime("%H-%M-%S")
    run_dir.mkdir(parents=True, exist_ok=True)

    setup_logging(working_dir / "fg" / "logs")

    kwargs = {} if args.model is None else {"model": args.model}
    if args.reasoning_effort is not None:
        kwargs["reasoning_effort"] = args.reasoning_effort
    client = FoundryClient(**kwargs)

    usages_path = working_dir / "state" / "usages.json"
    usage_nodes = UsageNodes(usages_path)
    if not usages_path.exists():
        logger.info("No usages.json found — running usage extraction") # TODO: should run this regardless, in case some havent been extracted
        extract_and_save_usages(working_dir, client, usage_nodes)
    else:
        logger.info("Skipping usage extraction (usages.json already exists)")

    paper_info_db = PaperInfoNodes(working_dir / "fg" / "state" / "paper_info_nodes.json")
    queue: Queue[DatasetJob] = Queue(DatasetJob, working_dir / "fg" / "state" / "dataset_queue.jsonl")

    if args.repopulate_queue: # TODO: think about this
        for paper in paper_info_db.all():
            if paper.pdf_info.download_success and paper.pdf_info.pdf_file_path:
                queue.enqueue(DatasetJob(title=paper.canonical_title, pdf_path=paper.pdf_info.pdf_file_path))
        logger.info("Repopulated queue with %d paper(s) from paper_info", len(queue))
    else:
        enqueue_used_datasets(usage_nodes.all(), paper_info_db, queue, working_dir)
    dataset_paper_db = DatasetPaperNodes(databases_dir / "dataset_paper_nodes.json")
    metadata_db = MetadataNodes(databases_dir / "metadata_nodes.json")
    dataset_website_db = DatasetWebsiteNodes(databases_dir / "dataset_website_nodes.json")
    project_page_db = ProjectPageNodes(databases_dir / "project_page_nodes.json")
    extract_and_save_metadata(queue, client, metadata_db, dataset_paper_db, dataset_website_db, project_page_db)

    logger.info("Done. Results in %s", working_dir)


if __name__ == "__main__":
    main()
