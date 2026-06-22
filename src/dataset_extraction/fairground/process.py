"""Extract dataset usages and metadata from all PDFs in working_dir/pdfs/.

Usage extraction is skipped if working_dir/state/usages.json already exists.
Metadata results are written to working_dir/fg/yyyy-mm-dd/hh-mm-ss/.

Usage:
    python -m dataset_extraction.fairground.process --working-dir papers/
"""

from __future__ import annotations

import argparse
import logging
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

def extract_and_save_pdf_metadata(
    job: DatasetJob,
    metadata_db: MetadataNodes,
    dataset_paper_db: DatasetPaperNodes,
    client
) -> DatasetPaperNode:
    logger.info("Extracting metadata from %s", job.title)
    try:
        result = extract_metadata(job.pdf_path, client)
    except Exception:
        logger.exception("PDF metadata extraction failed for %s", job.title)
        raise
    canonical_title = job.title
    dataset_ids = save_metadata(result, canonical_title, metadata_db)
    dataset_paper = save_dataset_paper(
        result, canonical_title, dataset_ids, dataset_paper_db
    )
    logger.info("Saved %d dataset(s) from %s", len(result.datasets), job.title)
    return dataset_paper

def extract_and_save_website_metadata(
    dataset_paper: DatasetPaperNode,
    metadata_db: MetadataNodes,
    dataset_website_db: DatasetWebsiteNodes,
    project_page_db: ProjectPageNodes,
    client
) -> None:
    if dataset_paper.project_page:
        #TODO: this can be a function of the database. This is also used in mapper
        # datasets = [
        #     (did, metadata_db.get(did).official_dataset_name)
        #     for did in dataset_paper.datasets
        # ]
        dataset_names = [
            metadata_db.get(did).official_dataset_name
            for did in dataset_paper.datasets
        ]
        title = dataset_paper.title
        try:
            result, matched_indices = extract_webpage(dataset_paper.project_page, title,
            dataset_names, model=client.model)
        except Exception:
            logger.exception("Website extraction failed for %s", title)
            raise
        matched_dataset_ids = [dataset_paper.datasets[i] for i in matched_indices]
        dataset_ids = save_dataset_website(
            result, title, matched_dataset_ids, dataset_website_db
        )
        save_project_website(title, result, project_page_db)
        logger.info("Saved website metadata for %s", title)


def extract_and_save(
    queue: Queue[DatasetJob],
    client,
    metadata_db: MetadataNodes,
    dataset_paper_db: DatasetPaperNodes,
    dataset_website_db: DatasetWebsiteNodes,
    project_page_db: ProjectPageNodes
) -> None:
    while len(queue) > 0:
        job = queue.peek()
        try:
            dataset_paper = extract_and_save_pdf_metadata(
                job, metadata_db, dataset_paper_db, client
            )
        except Exception:
            queue.dequeue()
            queue.enqueue(job)
            continue
        else:
            queue.dequeue()

        # Step 2: extract website metadata
        try:
            extract_and_save_website_metadata(
                dataset_paper, metadata_db, dataset_website_db, project_page_db,
                client
            )
        except Exception:
            continue
        dataset_paper.link_processed=True
        dataset_paper_db.update(dataset_paper)


def verify_databases(
    metadata_db: MetadataNodes,
    dataset_paper_db: DatasetPaperNodes,
    dataset_website_db: DatasetWebsiteNodes,
    project_page_db: ProjectPageNodes,
) -> None:
    errors = []

    # 1. All DatasetPaperNode dataset_ids exist as MetadataNodes
    for dp in dataset_paper_db.all():
        for did in dp.datasets:
            if not metadata_db.exists(did):
                errors.append(
                    f"[DatasetPaper→Metadata] {dp.title!r}: dataset_id {did!r} missing from metadata_db"
                )

    # 2. All DatasetPaperNodes with a project_page have link_processed = True
    for dp in dataset_paper_db.all():
        if dp.project_page and not dp.link_processed:
            errors.append(f"[DatasetPaper.link_processed] {dp.title!r}: has project_page but link_processed is False")

    # Build paper_title → set of dataset_ids from DatasetWebsiteNodes
    website_ids_by_paper: dict[str, set[str]] = {}
    for dw in dataset_website_db.all():
        website_ids_by_paper.setdefault(dw.paper_title, set()).add(dw.dataset_id)

    for pp in project_page_db.all():
        dp = dataset_paper_db.get(pp.paper_title)
        if dp is None:
            errors.append(f"[ProjectPage→DatasetPaper] {pp.paper_title!r}: no DatasetPaperNode found")
            continue
        dp_ids = set(dp.datasets)
        web_ids = website_ids_by_paper.get(pp.paper_title, set())

        # 3. ProjectPage's DatasetWebsiteNodes are a subset of DatasetPaperNode's datasets
        extra = web_ids - dp_ids
        if extra:
            errors.append(
                f"[DatasetWebsite⊄DatasetPaper] {pp.paper_title!r}: DatasetWebsiteNodes contain dataset_ids not in DatasetPaperNode: {extra}"
            )

    if errors:
        for e in errors:
            logger.warning("DB verify: %s", e)
        logger.warning("Database verification found %d issue(s).", len(errors))
        raise ValueError("Database verification failed with %d issue(s).", len(errors))
    else:
        logger.info("Database verification passed.")


def process_unprocessed_links(
    client,
    metadata_db: MetadataNodes,
    dataset_paper_db: DatasetPaperNodes,
    dataset_website_db: DatasetWebsiteNodes,
    project_page_db: ProjectPageNodes,
) -> None:
    for dataset_paper in dataset_paper_db.all():
        if not dataset_paper.link_processed:
            logger.info("Processing unprocessed link for %s", dataset_paper.title)
            try:
                extract_and_save_website_metadata(
                    dataset_paper, metadata_db, dataset_website_db, project_page_db, client
                )
            except Exception:
                logger.exception("Website extraction failed for %s", dataset_paper.title)
                continue
            dataset_paper.link_processed = True
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
    
    extract_and_save(queue, client, metadata_db, dataset_paper_db, dataset_website_db, project_page_db)
    process_unprocessed_links(client, metadata_db, dataset_paper_db, dataset_website_db, project_page_db)
    verify_databases(metadata_db, dataset_paper_db, dataset_website_db, project_page_db)

    logger.info("Done. Results in %s", working_dir)


if __name__ == "__main__":
    main()
