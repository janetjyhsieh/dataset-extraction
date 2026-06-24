"""Download corpus papers listed in the annotations spreadsheet.

Run as a module::

    python -m dataset_extraction.corpus.import_xlsx path/to/annotations.xlsx --venue FAccT --year 2022 --working-dir papers/facct-2022
    python -m dataset_extraction.corpus.import_xlsx path/to/annotations.xlsx --venue ICML --year 2023 --metadata-only
    python -m dataset_extraction.corpus.import_xlsx path/to/annotations.xlsx --venue FAccT --year 2022 --paper-sources FAccT-2022 Fabris_2021
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import requests

from dataset_extraction.log import setup_logging

logger = logging.getLogger("dataset_extraction.corpus.import_xlsx")

_ANNOTATIONS_PATH = Path(__file__).parents[4] / "gdrive" / "annotations.xlsx"
_SHEET_NAME = "2. Papers"
_HEADERS_ROW = 2

_HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; dataset-extraction-bot/1.0)"}


@dataclass
class AnnotationPaper:
    paper_id: str
    title: str
    doi: str | None
    url: str | None
    code_url: str | None
    paper_source: str
    uses_data: str | None
    status: str | None


def _is_formula_error(value: str | None) -> bool:
    return not value or value.startswith("#") or value == "NA"


def load_papers(
    annotations_path: Path,
    paper_sources: list[str],
) -> list[AnnotationPaper]:
    """Return unique papers from the annotations sheet matching ``paper_sources``.

    Deduplicates by ``paper_id``; keeps the first occurrence.
    """
    import openpyxl

    wb = openpyxl.load_workbook(str(annotations_path), data_only=True)
    ws = wb[_SHEET_NAME]

    headers = [cell.value for cell in ws[_HEADERS_ROW]]
    col = {h: i for i, h in enumerate(headers) if h}

    seen: set[str] = set()
    papers: list[AnnotationPaper] = []

    for row in ws.iter_rows(min_row=_HEADERS_ROW + 1, values_only=True):
        source = row[col["paper_source"]]
        if not source or source not in paper_sources:
            continue

        paper_id = row[col["paper_id"]]
        if not paper_id or paper_id in seen:
            continue

        title = row[col["title"]]
        if not title:
            continue

        seen.add(str(paper_id))

        doi_raw = row[col["doi"]]
        doi = None if _is_formula_error(doi_raw) else doi_raw

        url_raw = row[col["url"]]
        url = None if _is_formula_error(url_raw) else url_raw

        code_url_raw = row[col["code_url"]]
        code_url = None if _is_formula_error(code_url_raw) else code_url_raw

        papers.append(
            AnnotationPaper(
                paper_id=str(paper_id),
                title=str(title),
                doi=doi,
                url=url,
                code_url=code_url,
                paper_source=str(source),
                uses_data=row[col["uses_data"]],
                status=row[col["STATUS"]],
            )
        )

    return papers


def download_pdf(paper: AnnotationPaper, output_dir: Path) -> Path | None:
    """Download the PDF for *paper* using its annotated URL."""
    if not paper.url:
        logger.warning("No URL for %s (%s)", paper.paper_id, paper.title)
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    safe_id = re.sub(r"[^a-z0-9_-]", "_", paper.paper_id.lower())
    dest = output_dir / f"{safe_id}.pdf"
    if dest.exists():
        return dest

    try:
        resp = requests.get(paper.url, headers=_HTTP_HEADERS, timeout=60, allow_redirects=True)
        resp.raise_for_status()
        if not resp.content[:4] == b"%PDF":
            logger.warning(
                "Response for %s may not be a PDF (content-type: %s)",
                paper.paper_id,
                resp.headers.get("Content-Type"),
            )
        dest.write_bytes(resp.content)
        return dest
    except Exception:
        logger.warning("Failed to download %s from %s", paper.paper_id, paper.url, exc_info=True)
        return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download corpus papers from the annotations spreadsheet.",
    )
    parser.add_argument("--venue", required=True, help="Venue acronym, e.g. FAccT, ICML, NeurIPS")
    parser.add_argument("--year", type=int, required=True, help="Venue year, e.g. 2022")
    parser.add_argument(
        "--paper-sources",
        nargs="+",
        metavar="SOURCE",
        dest="paper_sources",
        default=None,
        help=(
            "Explicit paper_source values to filter by, e.g. FAccT-2022 Fabris_2021. "
            "Defaults to '<venue>-<year>'."
        ),
    )
    parser.add_argument(
        "--annotations",
        default=str(_ANNOTATIONS_PATH),
        help=f"Path to annotations.xlsx (default: {_ANNOTATIONS_PATH})",
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

    paper_sources = args.paper_sources or [f"{args.venue}-{args.year}"]

    working_dir = Path(args.working_dir)
    setup_logging(working_dir / "logs")
    index_path = working_dir / "index.jsonl"

    records: dict[str, dict] = {}
    if index_path.exists():
        with open(index_path) as f:
            for line in f:
                if line.strip():
                    rec = json.loads(line)
                    records[rec["id"]] = rec
        logger.info("Loaded %d existing paper(s) from %s", len(records), index_path)

    logger.info(
        "Loading papers from %s for source(s): %s", args.annotations, paper_sources
    )
    papers = load_papers(Path(args.annotations), paper_sources)
    logger.info("Found %d unique paper(s).", len(papers))

    new_papers = [p for p in papers if p.paper_id not in records]
    logger.info("%d new paper(s) to add.", len(new_papers))

    for paper in new_papers:
        records[paper.paper_id] = {
            "id": paper.paper_id,
            "title": paper.title,
            "doi": paper.doi,
            "url": paper.url,
            "code_url": paper.code_url,
            "paper_source": paper.paper_source,
            "uses_data": paper.uses_data,
            "status": paper.status,
        }

    working_dir.mkdir(parents=True, exist_ok=True)
    with open(index_path, "w") as f:
        for rec in records.values():
            f.write(json.dumps(rec) + "\n")
    logger.info("Wrote %d paper(s) to %s", len(records), index_path)

    if not args.metadata_only:
        pdf_dir = working_dir / "pdfs"
        n = len(new_papers)
        for i, paper in enumerate(new_papers, start=1):
            logger.info("Downloading %d/%d: %s", i, n, paper.paper_id)
            download_pdf(paper, pdf_dir)


if __name__ == "__main__":
    main()
