"""Download OpenReview papers for a venue filtered by keywords.

Usage:
    python scripts/download_papers.py \\
        --venue 'NeurIPS.cc/2023/Conference' \\
        --keywords fairness bias \\
        [--username you@example.com --password yourpassword]
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import openreview

from dataset_extraction.downloader.papers import get_notes
from dataset_extraction.downloader.pdf import download_pdfs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--venue",
        default="NeurIPS.cc/2023/Conference",
        help="OpenReview venue ID, e.g. 'NeurIPS.cc/2023/Conference'",
    )
    parser.add_argument(
        "--keywords",
        nargs="+",
        default=[],
        help=(
            "Keywords to filter papers by "
            "(case-insensitive substring match, OR logic)"
        ),
    )
    parser.add_argument(
        "--username",
        default=os.environ.get("OPENREVIEW_USERNAME", ""),
        help="OpenReview username (falls back to $OPENREVIEW_USERNAME)",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("OPENREVIEW_PASSWORD", ""),
        help="OpenReview password (falls back to $OPENREVIEW_PASSWORD)",
    )
    parser.add_argument(
        "--baseurl",
        default="https://api2.openreview.net",
        help="OpenReview API base URL (default: v2 API)",
    )
    parser.add_argument(
        "--papers-dir",
        default="papers",
        help="Root directory for output (default: papers)",
    )
    args = parser.parse_args()

    client = openreview.api.OpenReviewClient(
        baseurl=args.baseurl,
        username=args.username or None,
        password=args.password or None,
    )

    papers_dir = Path(args.papers_dir)
    index_path = papers_dir / "index.jsonl"
    pdf_dir = papers_dir / "pdfs"

    print(args.keywords)

    notes = get_notes(client, venue=args.venue, keywords=args.keywords)

    print(f"Found {len(notes)} note(s).")
    papers = []
    for note in notes:
        title = note.content.get("title", {})
        if isinstance(title, dict):
            title = title.get("value", "")
        keywords = note.content.get("keywords", [])
        if isinstance(keywords, dict):
            keywords = keywords.get("value", [])
        papers.append({"id": note.id, "title": title, "keywords": keywords})

    with open(index_path, "w") as f:
        for p in papers:
            f.write(json.dumps(p)+"\n")

    download_pdfs(client, notes, pdf_dir)


if __name__ == "__main__":
    main()
