"""Download CVF open access conference papers.

Usage:
    python scripts/download_cvf_papers.py \\
        --conference CVPR \\
        --year 2023 \\
        [--papers-dir papers]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dataset_extraction.downloader.cvf import CvfPaper, download_pdfs, get_papers


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--conference",
        required=True,
        help="CVF conference acronym, e.g. CVPR, ICCV, WACV",
    )
    parser.add_argument(
        "--year",
        type=int,
        required=True,
        help="Conference year, e.g. 2023",
    )
    parser.add_argument(
        "--papers-dir",
        default="papers",
        help="Root directory for output (default: papers)",
    )
    args = parser.parse_args()

    papers_dir = Path(args.papers_dir)
    index_path = papers_dir / "index.jsonl"
    pdf_dir = papers_dir / "pdfs"

    print(f"Fetching {args.conference}{args.year} papers from CVF open access...")
    papers = get_papers(args.conference, args.year)
    print(f"Found {len(papers)} paper(s).")

    papers_dir.mkdir(parents=True, exist_ok=True)
    with open(index_path, "w") as f:
        for paper in papers:
            record = {
                "id": paper.paper_id,
                "title": paper.title,
                "authors": paper.authors,
                "abstract_url": paper.abstract_url,
                "pdf_url": paper.pdf_url,
            }
            f.write(json.dumps(record) + "\n")

    download_pdfs(papers, pdf_dir)


if __name__ == "__main__":
    main()
