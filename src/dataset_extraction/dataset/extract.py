"""Extract dataset information from a paper PDF using an LLM.

Usage:
    python src/dataset_extraction/dataset/extract.py path/to/paper.pdf
    python src/dataset_extraction/dataset/extract.py path/to/paper.pdf --provider openai
    python src/dataset_extraction/dataset/extract.py path/to/paper.pdf --provider claude --model claude-sonnet-4-6
"""

from __future__ import annotations

import argparse

from dataset_extraction.clients.claude import ClaudeClient
from dataset_extraction.clients.openai import OpenAIClient

from .extractor import extract_datasets


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", help="Path to the PDF file")
    parser.add_argument(
        "--provider",
        choices=["claude", "openai"],
        default="claude",
        help="LLM provider (default: claude)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model ID (default: provider's default model)",
    )
    args = parser.parse_args()

    kwargs = {} if args.model is None else {"model": args.model}
    if args.provider == "claude":
        client = ClaudeClient(**kwargs)
    else:
        client = OpenAIClient(**kwargs)

    print(extract_datasets(args.pdf, client))


if __name__ == "__main__":
    main()
