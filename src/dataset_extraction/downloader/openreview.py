"""Download OpenReview papers for a venue.

Run as a module to download metadata and PDFs::

    python -m dataset_extraction.downloader.openreview --venue NeurIPS.cc/2023/Conference
    python -m dataset_extraction.downloader.openreview --venue NeurIPS.cc/2023/Conference --metadata-only --keywords fairness bias
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import openreview

from dataset_extraction.log import setup_logging

logger = logging.getLogger("dataset_extraction.downloader.openreview")


@dataclass
class OpenReviewPaper:
    paper_id: str
    title: str
    keywords: list[str]
    venue: str


def _get_keywords(note: openreview.Note) -> list[str]:
    raw = note.content.get("keywords", [])
    if isinstance(raw, dict):
        # v2 API wraps content fields: {"value": [...]}
        return raw.get("value", [])
    if isinstance(raw, list):
        return raw
    return []


def _note_matches(note: openreview.Note, keywords: list[str]) -> bool:
    note_keywords = _get_keywords(note) + [note.content.get("title", "")]
    query_lower = [q.lower() for q in keywords]
    return any(
        any(q in kw.lower() for q in query_lower)
        for kw in note_keywords
        if isinstance(kw, str)
    )


def get_papers(
    client: Any,
    venue: str,
    keywords: list[str] | None = None,
) -> list[OpenReviewPaper]:
    """Fetch paper metadata for an OpenReview venue.

    Args:
        client: An OpenReview API client (v1 ``openreview.Client`` or v2
            ``openreview.api.OpenReviewClient``).
        venue: The venue ID, e.g. ``'NeurIPS.cc/2023/Conference'``.
        keywords: Keywords to filter by (case-insensitive substring match,
            OR logic). If None or empty, all papers are returned.

    Returns:
        A list of :class:`OpenReviewPaper` objects matching the criteria.
    """
    notes = client.get_all_notes(content={"venueid": venue})

    if keywords:
        notes = [note for note in notes if _note_matches(note, keywords)]
        logger.debug("Filtered to %d note(s) matching %s", len(notes), keywords)

    papers = []
    for note in notes:
        title = note.content.get("title", {})
        if isinstance(title, dict):
            title = title.get("value", "")
        papers.append(
            OpenReviewPaper(
                paper_id=note.id,
                title=title,
                keywords=_get_keywords(note),
                venue=venue,
            )
        )
    return papers


def download_pdf(
    client: Any,
    paper: OpenReviewPaper,
    output_dir: str | Path,
) -> Path:
    """Download the PDF for a single OpenReview paper.

    Args:
        client: An OpenReview API client (v1 or v2).
        paper: The paper whose PDF to download.
        output_dir: Directory to save the PDF in.

    Returns:
        The :class:`Path` of the saved PDF file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    dest = output_dir / f"{paper.paper_id}.pdf"
    if dest.exists():
        return dest

    pdf_bytes = client.get_pdf(paper.paper_id)
    dest.write_bytes(pdf_bytes)
    return dest


def download_pdfs(
    client: Any,
    papers: list[OpenReviewPaper],
    output_dir: str | Path,
) -> list[Path]:
    """Download PDFs for a list of OpenReview papers.

    Args:
        client: An OpenReview API client (v1 or v2).
        papers: Papers whose PDFs to download.
        output_dir: Directory to save PDFs in.

    Returns:
        Paths of successfully saved PDF files.
    """
    n = len(papers)
    paths = []
    for i, paper in enumerate(papers, start=1):
        logger.info("Downloading %d/%d: %s", i, n, paper.paper_id)
        try:
            path = download_pdf(client, paper, output_dir)
            paths.append(path)
        except Exception:
            logger.warning("Failed to download %s", paper.paper_id, exc_info=True)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download OpenReview papers for a venue.",
    )
    parser.add_argument(
        "--venue",
        default="NeurIPS.cc/2023/Conference",
        help="OpenReview venue ID, e.g. 'NeurIPS.cc/2023/Conference'",
    )
    parser.add_argument(
        "--keywords",
        nargs="+",
        default=None,
        help="Only include papers matching any keyword (case-insensitive OR match)",
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
        "--working-dir",
        default="papers",
        help="Root directory for output (default: papers)",
    )
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="Write index.jsonl but skip PDF downloads",
    )
    args = parser.parse_args()

    working_dir = Path(args.working_dir)
    setup_logging(working_dir / "logs")
    index_path = working_dir / "index.jsonl"

    existing_ids: set[str] = set()
    if index_path.exists():
        with open(index_path) as f:
            for line in f:
                if line.strip():
                    existing_ids.add(json.loads(line)["id"])
        logger.info("Loaded %d existing paper(s) from %s", len(existing_ids), index_path)

    client = openreview.api.OpenReviewClient(
        baseurl=args.baseurl,
        username=args.username or None,
        password=args.password or None,
    )

    logger.info("Fetching papers from %s...", args.venue)
    papers = get_papers(client, venue=args.venue, keywords=args.keywords)
    logger.info("Found %d paper(s).", len(papers))

    new_papers = [p for p in papers if p.paper_id not in existing_ids]
    logger.info("%d new paper(s) to add.", len(new_papers))

    working_dir.mkdir(parents=True, exist_ok=True)
    with open(index_path, "a") as f:
        for paper in new_papers:
            record = {
                "id": paper.paper_id,
                "title": paper.title,
                "keywords": paper.keywords,
                "venue": paper.venue,
            }
            f.write(json.dumps(record) + "\n")
    logger.info("Appended %d paper(s) to %s", len(new_papers), index_path)

    if not args.metadata_only:
        download_pdfs(client, new_papers, working_dir / "pdfs")


if __name__ == "__main__":
    main()
