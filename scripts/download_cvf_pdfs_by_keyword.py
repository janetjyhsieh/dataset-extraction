"""Download CVF PDFs for papers whose titles match given keywords.

Reads index.jsonl written by `python -m dataset_extraction.downloader.cvf`
and downloads PDFs for papers whose title contains any of the provided
keywords (case-insensitive substring match, OR logic).

Usage:
    python scripts/download_cvf_pdfs_by_keyword.py \\
        --papers-dir papers/cvpr2023 \\
        --keywords diffusion generative
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dataset_extraction.downloader.cvf import CvfPaper, download_pdfs


def _title_matches(title: str, keywords: list[str]) -> bool:
    return any(kw in title for kw in keywords)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--papers-dir",
        required=True,
        help="Path to the conference paper directory containing index.jsonl",
    )
    parser.add_argument(
        "--keywords",
        nargs="+",
        required=True,
        help="Keywords to filter by (case-insensitive substring match, OR logic)",
    )
    args = parser.parse_args()

    papers_dir = Path(args.papers_dir)
    index_path = papers_dir / "index.jsonl"

    if not index_path.exists():
        raise FileNotFoundError(f"No index.jsonl found at {index_path}")

    with open(index_path) as f:
        records = [json.loads(line) for line in f if line.strip()]

    matching = [r for r in records if _title_matches(r["title"], args.keywords)]
    print(f"Found {len(matching)}/{len(records)} paper(s) matching {args.keywords}.")

    papers = [
        CvfPaper(
            paper_id=r["id"],
            title=r["title"],
            authors=r["authors"],
            abstract_url=r["abstract_url"],
            pdf_url=r["pdf_url"],
        )
        for r in matching
    ]

    download_pdfs(papers, papers_dir / "pdfs")


if __name__ == "__main__":
    main()
