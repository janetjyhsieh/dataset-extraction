from __future__ import annotations

import json
from pathlib import Path
from typing import Union

from dataset_extraction.clients.claude import ClaudeClient
from dataset_extraction.clients.openai import OpenAIClient
from dataset_extraction.state.graph import DatasetNodes
from dataset_extraction.state.nodes import DatasetNode

from .datasets import ExtractionResult
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
    print(f"Found {len(pdfs)} PDF(s) under {papers_path}/pdfs")

    out_path = Path(papers_path) / "out" / "extraction_results.jsonl"

    with out_path.open("a") as out_file:
        for pdf in pdfs:
            print(f"Processing {pdf.name} ...", end=" ", flush=True)
            try:
                result = extract_datasets(pdf, client)
            except Exception as exc:
                print(f"FAILED ({exc})")
                continue

            out_file.write(result.model_dump_json() + "\n")

            if not result.publishes_new_dataset:
                print("no new dataset")
                continue

            for dataset in result.new_datasets:
                nodes.add(DatasetNode(**dataset.model_dump()))

            print(f"saved {len(result.new_datasets)} dataset(s)")