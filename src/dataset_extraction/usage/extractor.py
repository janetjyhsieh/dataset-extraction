from __future__ import annotations

import logging
from pathlib import Path
from typing import Union

from dataset_extraction.clients.claude import ClaudeClient
from dataset_extraction.clients.foundry import FoundryClient
from dataset_extraction.clients.openai import OpenAIClient
from dataset_extraction.state.graph import UsageNodes
from dataset_extraction.state.nodes import UsageNode
from dataset_extraction.utils import load_title_map

from .usages import UsageExtractionResult

USAGE_PROMPT = (__import__("pathlib").Path(__file__).parent / "prompts.xml").read_text()

Client = Union[ClaudeClient, FoundryClient, OpenAIClient]

logger = logging.getLogger("dataset_extraction.usage.extractor")


def extract_usage(
    pdf_path: str | Path,
    client: Client,
) -> tuple[str | None, UsageExtractionResult]:
    thinking, result = client.send_pdf_structured(pdf_path, USAGE_PROMPT, UsageExtractionResult.model_json_schema(), thinking=True)
    return thinking, UsageExtractionResult.model_validate(result)


def extract_and_save_usages(
    working_dir: Path,
    client: Client,
    usage_nodes: UsageNodes,
) -> list[UsageNode]:
    """Extract usages from all PDFs in working_dir/pdfs/ and save to the store.

    Skips papers that have already been processed. Returns all stored UsageNodes.
    """
    title_map = load_title_map(working_dir)
    pdfs = sorted((working_dir / "pdfs").glob("*.pdf"))
    logger.info("Found %d PDF(s) under %s/pdfs", len(pdfs), working_dir)

    for pdf in pdfs:
        paper_id = pdf.stem
        paper_title = title_map.get(paper_id, paper_id)

        if usage_nodes.is_processed(paper_title):
            logger.debug("Skipping %s (already processed)", pdf.name)
            continue

        logger.info("Extracting usages from %s", pdf.name)
        try:
            _, result = extract_usage(pdf, client)
        except Exception:
            logger.exception("Extraction failed for %s", pdf.name)
            continue

        for usage in result.dataset_usages:
            usage_nodes.add(UsageNode(**usage.model_dump(), paper_title=paper_title))
        usage_nodes.mark_processed(paper_title)

        logger.info("Saved %d usage(s) from %s", len(result.dataset_usages), pdf.name)

    return usage_nodes.all()

