from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Union

from dataset_extraction.clients.claude import ClaudeClient
from dataset_extraction.clients.openai import OpenAIClient
from dataset_extraction.state.graph import DatasetNodes
from dataset_extraction.state.nodes import DatasetNode

from .datasets import ExtractionResult
from .prompts import DATASET_PROMPT

logger = logging.getLogger(__name__)

Client = Union[ClaudeClient, OpenAIClient]


def extract_datasets(
    pdf_path: str | Path,
    client: Client,
) -> ExtractionResult:
    """Extract dataset information from a paper PDF.

    Args:
        pdf_path: Path to the PDF file.
        client: An instantiated ``ClaudeClient`` or ``OpenAIClient``.

    Returns:
        An ``ExtractionResult`` containing structured dataset information.
    """
    _, result = client.send_pdf_structured(
        pdf_path,
        DATASET_PROMPT,
        ExtractionResult.model_json_schema(),
    )
    return ExtractionResult.model_validate(result)


def extract_all_datasets(
    papers_path: str | Path,
    client: Client,
    nodes: DatasetNodes,
) -> None:
    """Extract datasets from all PDFs under *papers_path*/pdfs and save to *nodes*.

    Skips PDFs that fail extraction and prints a warning, so one bad paper
    does not abort the whole run.

    Args:
        papers_path: Root papers directory containing a ``pdfs/`` subdirectory.
        client: An instantiated ``ClaudeClient`` or ``OpenAIClient``.
        nodes: The ``DatasetNodes`` store where extracted datasets will be saved.
    """
    pdfs = sorted(Path(papers_path).glob("pdfs/*.pdf"))
    logger.info("Found %d PDF(s) under %s/pdfs", len(pdfs), papers_path)

    out_path = Path(papers_path) / "out" / "extraction_results.jsonl"

    with out_path.open("a") as out_file:
        for pdf in pdfs:
            logger.info("Processing %s", pdf.name)
            try:
                result = extract_datasets(pdf, client)
            except Exception:
                logger.exception("Extraction failed for %s", pdf.name)
                continue

            out_file.write(result.model_dump_json() + "\n")

            if not result.publishes_new_dataset:
                logger.debug("%s: no new dataset", pdf.name)
                continue

            for dataset in result.new_datasets:
                nodes.upsert(DatasetNode(**dataset.model_dump()))

            logger.info("Saved %d dataset(s) from %s", len(result.new_datasets), pdf.name)