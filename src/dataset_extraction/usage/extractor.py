from __future__ import annotations

import json
from pathlib import Path
from typing import Union

from dataset_extraction.clients.claude import ClaudeClient
from dataset_extraction.clients.openai import OpenAIClient

from .usages import UsageExtractionResult
from .prompts import USAGE_PROMPT

Client = Union[ClaudeClient, OpenAIClient]


def extract_usage(
    pdf_path: str | Path,
    client: Client,
) -> tuple[str | None, UsageExtractionResult]:
    """Extract dataset usage information from a paper PDF.

    For Claude, the model's reasoning is returned as a separate thinking string
    via extended thinking blocks. For OpenAI, reasoning is internal and the
    first element of the tuple is None.

    Args:
        pdf_path: Path to the PDF file.
        client: An instantiated ``ClaudeClient`` or ``OpenAIClient``.

    Returns:
        A ``(thinking, result)`` tuple where *thinking* is the model's reasoning
        text (or None) and *result* is a validated ``UsageExtractionResult``.
    """
    thinking, raw = client.send_pdf_structured(
        pdf_path,
        USAGE_PROMPT,
        UsageExtractionResult.model_json_schema(),
        thinking=True,
    )
    return thinking, UsageExtractionResult.model_validate(raw)


def extract_all_usages(
    papers_path: str | Path,
    client: Client,
) -> None:
    """Extract dataset usages from all PDFs under *papers_path*/pdfs.

    Appends one JSON line per paper to ``out/usages.jsonl``. Each line
    includes the paper_id alongside the structured extraction result.
    Thinking text (Claude only) is saved per-paper to
    ``out/usages_extraction/{paper_id}_thinking.txt``.

    Args:
        papers_path: Root papers directory containing a ``pdfs/`` subdirectory.
        client: An instantiated ``ClaudeClient`` or ``OpenAIClient``.
    """
    pdfs = sorted(Path(papers_path).glob("pdfs/*.pdf"))
    print(f"Found {len(pdfs)} PDF(s) under {papers_path}/pdfs")

    out_dir = Path("out/usages_extraction")
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = Path("out/usages_extraction/usages.jsonl")

    with jsonl_path.open("a") as jsonl_file:
        for pdf in pdfs:
            paper_id = pdf.stem
            print(f"Processing {pdf.name} ...", end=" ", flush=True)
            try:
                thinking, result = extract_usage(pdf, client)
            except Exception as exc:
                print(f"FAILED ({exc})")
                continue

            record = {"paper_id": paper_id} | result.model_dump(mode="json")
            jsonl_file.write(json.dumps(record) + "\n")

            if thinking:
                (out_dir / f"{paper_id}_thinking.txt").write_text(thinking, encoding="utf-8")

            thinking_note = " + thinking" if thinking else ""
            print(f"saved {len(result.dataset_usages)} usage(s){thinking_note}")
