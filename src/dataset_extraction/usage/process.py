from __future__ import annotations

import logging
from pathlib import Path

from dataset_extraction.downloader.paper_finder import find_and_download_pdf
from dataset_extraction.state.graph import PaperInfoNodes
from dataset_extraction.state.paper import PaperInfo, PdfInfo, canonicalize_title
from dataset_extraction.state.queue import DatasetJob, Queue
from dataset_extraction.usage.nodes import UsageNode

logger = logging.getLogger("dataset_extraction.usage.process")


def enqueue_used_datasets(
    usages: list[UsageNode],
    paper_info_db: PaperInfoNodes,
    queue: Queue[DatasetJob],
    working_dir: Path,
) -> None:
    """Ensure every used dataset's source paper is in the graph or queued for discovery."""
    download_dir = working_dir / "discovered" / "pdfs"

    for usage in usages:
        source_title = usage.source_paper.title
        if not source_title:
            logger.debug("'%s' has no source title, skipping", usage.dataset_name)
            continue

        canonical = canonicalize_title(source_title)

        if paper_info_db.exists(canonical):
            logger.debug("'%s' already in graph or queue", source_title)
            continue

        logger.info("'%s' not in graph — looking up '%s'", usage.dataset_name, source_title)
        usage_paper_info = PaperInfo(
            raw_title=source_title,
            canonical_title=canonical,
            pdf_info=PdfInfo(link_found=False, download_success=False),
        )
        pdf_path = find_and_download_pdf(usage_paper_info, download_dir)
        paper_info_db.insert(usage_paper_info)

        if pdf_path is None:
            logger.warning("No PDF found for '%s': %s", source_title, usage_paper_info.pdf_info.errors)
            continue

        queue.enqueue(DatasetJob(title=canonical, pdf_path=str(pdf_path)))
        logger.info("Enqueued '%s'", source_title)
