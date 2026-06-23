from __future__ import annotations

import logging
from pathlib import Path
from typing import Union

import json

from dataset_extraction.clients.claude import ClaudeClient
from dataset_extraction.clients.foundry import FoundryClient
from dataset_extraction.clients.openai import OpenAIClient
from dataset_extraction.usage.nodes import UsageNode, UsageNodes

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
    """Extract usages from PDFs listed in working_dir/index.jsonl and save to the store.

    Skips papers that have already been processed. Returns all stored UsageNodes.
    """
    index_path = working_dir / "index.jsonl"
    if not index_path.exists():
        logger.warning("No index.jsonl found at %s — nothing to extract", index_path)
        return usage_nodes.all()

    with open(index_path) as f:
        entries = [json.loads(line) for line in f if line.strip()]
    logger.info("Found %d entries in index.jsonl", len(entries))

    for entry in entries:
        paper_id = entry["id"]
        paper_title = entry["title"]
        pdf = working_dir / "pdfs" / f"{paper_id}.pdf"

        if not pdf.exists():
            logger.debug("PDF not found for %s (%s) — skipping", paper_id, paper_title)
            continue

        if usage_nodes.is_processed(paper_title):
            logger.debug("Skipping %s (already processed)", paper_title)
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

