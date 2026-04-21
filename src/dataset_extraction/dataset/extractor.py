from __future__ import annotations

from pathlib import Path
from typing import Union

from dataset_extraction.clients.claude import ClaudeClient
from dataset_extraction.clients.openai import OpenAIClient
from dataset_extraction.state.datasets import ExtractionResult

from .prompts import DATASET_PROMPT

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
    result = client.send_pdf_structured(
        pdf_path,
        DATASET_PROMPT,
        ExtractionResult.model_json_schema(),
    )
    return ExtractionResult.model_validate(result)


# TODO write extract_all_datasets that takes in all papers and write results into the database.
