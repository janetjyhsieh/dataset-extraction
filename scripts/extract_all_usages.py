"""Extract dataset usages from all PDFs under papers/pdfs and save to usages.jsonl.

Usage:
    python scripts/extract_all_usages.py
    python scripts/extract_all_usages.py --provider openai
    python scripts/extract_all_usages.py --papers-dir papers --model claude-sonnet-4-6
"""

from __future__ import annotations

import argparse

from dataset_extraction.clients.claude import ClaudeClient
from dataset_extraction.clients.openai import OpenAIClient
from dataset_extraction.usage.extractor import extract_all_usages


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
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
    parser.add_argument(
        "--papers-dir",
        default="papers",
        help="Root papers directory containing a pdfs/ subdirectory (default: papers)",
    )
    args = parser.parse_args()

    kwargs = {} if args.model is None else {"model": args.model}
    client = ClaudeClient(**kwargs) if args.provider == "claude" else OpenAIClient(**kwargs)

    extract_all_usages(args.papers_dir, client)

    print("\nDone.")


if __name__ == "__main__":
    main()
