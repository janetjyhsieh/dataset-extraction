from __future__ import annotations

from pathlib import Path
from typing import Union

from dataset_extraction.clients.claude import ClaudeClient
from dataset_extraction.clients.openai import OpenAIClient

from .prompts import USAGE_PROMPT

Client = Union[ClaudeClient, OpenAIClient]


def extract_usage(
    pdf_path: str | Path,
    client: Client,
) -> str:
    """Extract usage information from a paper PDF.

    Args:
        pdf_path: Path to the PDF file.
        client: An instantiated ``ClaudeClient`` or ``OpenAIClient``.

    Returns:
        The LLM's response text describing dataset usage found in the paper.
    """
    return client.send_pdf(pdf_path, USAGE_PROMPT)
