"""Scrape and download CVF open access conference papers.

Run as a module to download metadata and PDFs::

    python -m dataset_extraction.downloader.cvf --venue CVPR --year 2023
    python -m dataset_extraction.downloader.cvf --venue ICCV --year 2023 --metadata-only
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from dataset_extraction.log import setup_logging

logger = logging.getLogger("dataset_extraction.downloader.cvf")

CVF_BASE = "https://openaccess.thecvf.com"

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; dataset-extraction-bot/1.0)"}


@dataclass
class CvfPaper:
    paper_id: str
    title: str
    authors: list[str]
    abstract_url: str
    pdf_url: str


def get_papers(venue: str, year: int) -> list[CvfPaper]:
    """Fetch paper metadata for a CVF open access venue.

    Args:
        venue: Venue acronym, e.g. ``'CVPR'``, ``'ICCV'``, ``'WACV'``.
        year: Venue year, e.g. ``2023``.

    Returns:
        A list of :class:`CvfPaper` objects for all accepted papers.
    """
    url = f"{CVF_BASE}/{venue}{year}?day=all"
    response = requests.get(url, headers=_HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    papers = []

    for dt in soup.find_all("dt", class_="ptitle"):
        a_tag = dt.find("a")
        if not a_tag:
            continue

        title = a_tag.get_text(strip=True)
        abstract_href = a_tag.get("href", "")
        abstract_url = CVF_BASE + abstract_href if abstract_href.startswith("/") else abstract_href

        paper_id = Path(abstract_href).stem

        # PDF URL convention: /html/ -> /papers/, .html -> .pdf
        pdf_href = abstract_href.replace("/html/", "/papers/").replace(".html", ".pdf")
        pdf_url = CVF_BASE + pdf_href if pdf_href.startswith("/") else pdf_href

        dd = dt.find_next_sibling("dd")
        authors: list[str] = []
        if dd:
            authors_div = dd.find("div", class_="authors")
            if authors_div:
                authors = [
                    part.strip()
                    for part in authors_div.get_text().split(",")
                    if part.strip()
                ]

        papers.append(
            CvfPaper(
                paper_id=paper_id,
                title=title,
                authors=authors,
                abstract_url=abstract_url,
                pdf_url=pdf_url,
            )
        )

    return papers


def download_pdf(paper: CvfPaper, output_dir: str | Path) -> Path:
    """Download the PDF for a single CVF paper.

    Args:
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

    response = requests.get(paper.pdf_url, headers=_HEADERS, timeout=60)
    response.raise_for_status()

    dest.write_bytes(response.content)
    return dest


def download_pdfs(papers: list[CvfPaper], output_dir: str | Path) -> list[Path]:
    """Download PDFs for a list of CVF papers.

    Args:
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
            path = download_pdf(paper, output_dir)
            paths.append(path)
        except Exception:
            logger.warning("Failed to download %s", paper.paper_id, exc_info=True)
    return paths


def _title_matches(title: str, keywords: list[str]) -> bool:
    words = set(re.findall(r"[a-z]+", title.lower()))
    return any(kw.lower() in words for kw in keywords)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download CVF open access conference papers.",
    )
    parser.add_argument(
        "--venue",
        required=True,
        help="CVF venue acronym, e.g. CVPR, ICCV, WACV",
    )
    parser.add_argument(
        "--year",
        type=int,
        required=True,
        help="Venue year, e.g. 2023",
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
    parser.add_argument(
        "--keywords",
        nargs="+",
        default=None,
        help="Only include papers whose title contains any keyword (case-insensitive OR match)",
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

    logger.info("Fetching %s%d papers from CVF open access...", args.venue, args.year)
    papers = get_papers(args.venue, args.year)
    logger.info("Found %d paper(s).", len(papers))

    if args.keywords:
        papers = [p for p in papers if _title_matches(p.title, args.keywords)]
        logger.info("%d paper(s) match keywords %s.", len(papers), args.keywords)

    new_papers = [p for p in papers if p.paper_id not in existing_ids]
    logger.info("%d new paper(s) to add.", len(new_papers))

    working_dir.mkdir(parents=True, exist_ok=True)
    with open(index_path, "a") as f:
        for paper in new_papers:
            record = {
                "id": paper.paper_id,
                "title": paper.title,
                "authors": paper.authors,
                "year": args.year,
                "venue": args.venue,
                "abstract_url": paper.abstract_url,
                "pdf_url": paper.pdf_url,
            }
            f.write(json.dumps(record) + "\n")
    logger.info("Appended %d paper(s) to %s", len(new_papers), index_path)

    if not args.metadata_only:
        download_pdfs(new_papers, working_dir / "pdfs")


if __name__ == "__main__":
    main()
