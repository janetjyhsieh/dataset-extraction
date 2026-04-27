"""Extract datasets from all PDFs under papers/pdfs and save to the node database.

Usage:
    python scripts/extract_all_datasets.py
    python scripts/extract_all_datasets.py --provider openai
    python scripts/extract_all_datasets.py --papers-dir papers --db out/nodes.json --model claude-sonnet-4-6
"""

from __future__ import annotations

import argparse

from dataset_extraction.clients.claude import ClaudeClient
from dataset_extraction.clients.openai import OpenAIClient
from dataset_extraction.dataset.extractor import extract_all_datasets
from dataset_extraction.state.graph import Nodes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--provider",
        choices=["claude", "openai"],
        default="openai",
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
    parser.add_argument(
        "--db",
        default="out/nodes.json",
        help="Path to the TinyDB nodes database (default: out/nodes.json)",
    )
    args = parser.parse_args()

    kwargs = {} if args.model is None else {"model": args.model}
    client = ClaudeClient(**kwargs) if args.provider == "claude" else OpenAIClient(**kwargs)
    nodes = Nodes(args.db)

    extract_all_datasets(args.papers_dir, client, nodes)

    print(f"\nDone. {len(nodes)} node(s) total in {args.db}")


if __name__ == "__main__":
    main()
