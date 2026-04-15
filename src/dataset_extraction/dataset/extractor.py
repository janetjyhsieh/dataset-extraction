from __future__ import annotations

from pathlib import Path
from typing import Union

from dataset_extraction.clients.claude import ClaudeClient
from dataset_extraction.clients.openai import OpenAIClient

from .prompts import DATASET_PROMPT

Client = Union[ClaudeClient, OpenAIClient]


def extract_datasets(
    pdf_path: str | Path,
    client: Client,
) -> str:
    """Extract dataset information from a paper PDF.

    Args:
        pdf_path: Path to the PDF file.
        client: An instantiated ``ClaudeClient`` or ``OpenAIClient``.

    Returns:
        The LLM's response text describing datasets found in the paper.
    """
    return client.send_pdf(pdf_path, DATASET_PROMPT)
