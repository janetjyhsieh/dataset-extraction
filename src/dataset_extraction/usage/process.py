from __future__ import annotations

import json
import logging
from pathlib import Path

from dataset_extraction.downloader.paper_finder import find_and_download_pdf
from dataset_extraction.state.databases import PaperInfoNodes
from dataset_extraction.state.paper_entries import PaperInfo, PdfInfo, canonicalize_title
from dataset_extraction.state.paper_entries import PdfDownloadSource
from dataset_extraction.state.queue import DatasetJob, Queue
from dataset_extraction.usage.nodes import UsageNode

logger = logging.getLogger("dataset_extraction.usage.process")

def _find_index_entry(paper_title: str, working_dir: Path) -> dict | None:
    index_path = working_dir / "index.jsonl"
    if not index_path.exists():
        return None
    with open(index_path) as f:
        for line in f:
            if line.strip():
                entry = json.loads(line)
                if entry.get("title") == paper_title:
                    return entry
    return None


def _is_original_source(usage: UsageNode):
    if usage.source_paper.bibliographic_string == "(self)":
        return True
    if usage.source_paper.title is not None:
        canonical_source_title = canonicalize_title(usage.source_paper.title)
        canonical_title = canonicalize_title(usage.paper_title)
        if canonical_source_title == canonical_title:
            return True
    return False


def enqueue_used_datasets(
    usages: list[UsageNode],
    paper_info_db: PaperInfoNodes,
    queue: Queue[DatasetJob],
    working_dir: Path,
) -> None:
    """Ensure every used dataset's source paper is in the graph or queued for discovery."""
    download_dir = working_dir / "discovered" / "pdfs"

    pdf_path = None
    for usage in usages:
        if _is_original_source(usage):
            logger.info("'%s' has no source title, original dataset", usage.dataset_name)
            index_entry = _find_index_entry(usage.paper_title, working_dir)
            canonical = canonicalize_title(usage.paper_title)
            
            if paper_info_db.exists(canonical):
                logger.debug("'%s' already in graph or queue", source_title)
                continue
            
            pdf_path = index_entry["pdf_path"]
            usage_paper_info = PaperInfo(
                raw_title=usage.paper_title,
                canonical_title=canonical,
                pdf_info=PdfInfo(
                    link_found=True, 
                    download_success=True,
                    url = index_entry["pdf_url"],
                    pdf_file_path = pdf_path,
                    pdf_download_source = PdfDownloadSource.direct
                ),
            )

        else:
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
