from __future__ import annotations

from pathlib import Path
from typing import Union

from dataset_extraction.clients.claude import ClaudeClient
from dataset_extraction.clients.foundry import FoundryClient
from dataset_extraction.clients.openai import OpenAIClient

from .datasets import ExtractionResult

DATASET_PROMPT = (__import__("pathlib").Path(__file__).parent / "prompts.xml").read_text()

Client = Union[ClaudeClient, FoundryClient, OpenAIClient]


def extract_datasets(
    pdf_path: str | Path,
    client: Client,
) -> ExtractionResult:
    _, result = client.send_pdf_structured(pdf_path, DATASET_PROMPT, ExtractionResult.model_json_schema())
    return ExtractionResult.model_validate(result)


