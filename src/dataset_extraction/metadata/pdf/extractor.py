from __future__ import annotations

from pathlib import Path
from typing import Union

from dataset_extraction.clients.claude import ClaudeClient
from dataset_extraction.clients.foundry import FoundryClient
from dataset_extraction.clients.openai import OpenAIClient

from .pdf import PdfExtractionResult

METADATA_PROMPT = (Path(__file__).parent / "prompts.xml").read_text()

Client = Union[ClaudeClient, FoundryClient, OpenAIClient]


def extract_metadata(
    pdf_path: str | Path,
    client: Client,
) -> PdfExtractionResult:
    _, result = client.send_pdf_structured(
        pdf_path,
        METADATA_PROMPT,
        PdfExtractionResult.model_json_schema(),
    )
    return PdfExtractionResult.model_validate(result)
