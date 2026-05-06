from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import requests
from bs4 import BeautifulSoup

CVF_BASE = "https://openaccess.thecvf.com"

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; dataset-extraction-bot/1.0)"}


@dataclass
class CvfPaper:
    paper_id: str
    title: str
    authors: list[str]
    abstract_url: str
    pdf_url: str


def get_papers(conference: str, year: int) -> list[CvfPaper]:
    """Fetch paper metadata for a CVF open access conference.

    Args:
        conference: Conference acronym, e.g. ``'CVPR'``, ``'ICCV'``, ``'WACV'``.
        year: Conference year, e.g. ``2023``.

    Returns:
        A list of :class:`CvfPaper` objects for all accepted papers.
    """
    url = f"{CVF_BASE}/{conference}{year}?day=all"
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

    response = requests.get(paper.pdf_url, headers=_HEADERS, timeout=60)
    response.raise_for_status()

    dest = output_dir / f"{paper.paper_id}.pdf"
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
        print(f"Downloading {i}/{n}: {paper.paper_id}")
        try:
            path = download_pdf(paper, output_dir)
            paths.append(path)
        except Exception as e:
            print(f"Warning: failed to download {paper.paper_id}: {e}")
    return paths
