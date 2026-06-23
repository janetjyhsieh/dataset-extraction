"""Manually supply PDFs for papers where automatic download failed (link_found=False).

For each paper in paper_info_nodes.json with link_found=False, prompts the user
to paste a direct PDF URL. Downloads the PDF to working_dir/manual/<slug>.pdf,
updates paper_info_nodes.json, and enqueues a DatasetJob.

Usage:
    python -m dataset_extraction.fairground.manual_download --working-dir papers/
"""

from __future__ import annotations

import argparse
import re
import logging
from pathlib import Path

import requests

from dataset_extraction.log import setup_logging
from dataset_extraction.state.paper import PdfDownloadSource, PdfInfo
from dataset_extraction.state.queue import DatasetJob
from dataset_extraction.fairground.state_loader import load_state

logger = logging.getLogger("dataset_extraction.fairground.manual_download")


def _title_to_slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:80]


def _download_pdf(url: str, dest: Path) -> None:
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    if b"%PDF" not in resp.content[:8]:
        raise ValueError("Response does not appear to be a PDF")
    dest.write_bytes(resp.content)


def run(working_dir: Path) -> None:
    manual_dir = working_dir / "manual"
    manual_dir.mkdir(parents=True, exist_ok=True)

    state = load_state(working_dir)
    paper_info_db = state.paper_info_db
    queue = state.queue

    already_queued_titles = {job.title for job in queue.all()}

    candidates = [p for p in paper_info_db.all() if not p.pdf_info.pdf_file_path]
    if not candidates:
        print("No papers with link_found=False found.")
        return

    print(f"Found {len(candidates)} paper(s) without a PDF link.\n")

    for paper in candidates:
        if paper.canonical_title in already_queued_titles:
            logger.debug("Skipping %r — already in queue", paper.canonical_title)
            continue

        print(f"Paper: {paper.raw_title or paper.canonical_title}")
        if paper.pdf_info.errors:
            print(f"  Errors: {'; '.join(paper.pdf_info.errors)}")

        url = input("  PDF URL (leave blank to skip): ").strip()
        if not url:
            print("  Skipped.\n")
            continue

        dest = manual_dir / f"{_title_to_slug(paper.canonical_title)}.pdf"
        try:
            _download_pdf(url, dest)
        except Exception as e:
            print(f"  Download failed: {e}\n")
            logger.error("Download failed for %r: %s", paper.canonical_title, e)
            continue

        paper.pdf_info = PdfInfo(
            link_found=True,
            download_success=True,
            url=url,
            pdf_file_path=str(dest),
            pdf_download_source=PdfDownloadSource.direct,
        )
        paper_info_db.update(paper)

        queue.enqueue(DatasetJob(title=paper.canonical_title, pdf_path=str(dest)))
        print(f"  Saved to {dest} and enqueued.\n")
        logger.info("Manually downloaded %r → %s", paper.canonical_title, dest)

    print("Done.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--working-dir", required=True, help="Directory containing fg/ state")
    args = parser.parse_args()

    working_dir = Path(args.working_dir)
    setup_logging(working_dir / "fg" / "logs")
    run(working_dir)


if __name__ == "__main__":
    main()
