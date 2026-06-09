from __future__ import annotations

from pathlib import Path
from typing import Union

from dataset_extraction.clients.claude import ClaudeClient
from dataset_extraction.clients.foundry import FoundryClient
from dataset_extraction.clients.openai import OpenAIClient

from .usages import UsageExtractionResult

USAGE_PROMPT = (__import__("pathlib").Path(__file__).parent / "prompts.xml").read_text()

Client = Union[ClaudeClient, FoundryClient, OpenAIClient]


def extract_usage(
    pdf_path: str | Path,
    client: Client,
) -> tuple[str | None, UsageExtractionResult]:
    thinking, result = client.send_pdf_structured(pdf_path, USAGE_PROMPT, UsageExtractionResult.model_json_schema(), thinking=True)
    return thinking, UsageExtractionResult.model_validate(result)

