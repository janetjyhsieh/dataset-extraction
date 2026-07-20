"""Scrape and download CVF open access conference papers."""

from __future__ import annotations

import logging
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from dataset_extraction.corpus.corpus import CorpusSource, SourcePaper
from dataset_extraction.corpus.utils import keywords_in_string

logger = logging.getLogger("dataset_extraction.corpus.cvf")

CVF_BASE = "https://openaccess.thecvf.com"

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; dataset-extraction-bot/1.0)"}


class CvfSource(CorpusSource):
    def __init__(self, working_dir: Path, index_path: Path):
        super().__init__(working_dir, index_path)

    def get_papers(self, venue: str, year: int, keywords: list[str] | None = None) -> list[SourcePaper]:
        url = f"{CVF_BASE}/{venue}{year}?day=all"
        response = requests.get(url, headers=_HEADERS, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        new_papers = []

        for dt in soup.find_all("dt", class_="ptitle"):
            a_tag = dt.find("a")
            if not a_tag:
                continue

            title = a_tag.get_text(strip=True)
            abstract_href = a_tag.get("href", "")
            paper_id = Path(abstract_href).stem

            if paper_id in self.paper_ids:
                continue

            if keywords and not keywords_in_string(title, keywords):
                continue

            pdf_href = abstract_href.replace("/html/", "/papers/").replace(".html", ".pdf")
            pdf_url = CVF_BASE + pdf_href if pdf_href.startswith("/") else pdf_href

            dd = dt.find_next_sibling("dd")
            authors: list[str] = []
            if dd:
                authors_div = dd.find("div", class_="authors")
                if authors_div:
                    authors = [p.strip() for p in authors_div.get_text().split(",") if p.strip()]

            sp = SourcePaper(
                paper_id=paper_id,
                title=title,
                authors=authors,
                pdf_url=pdf_url,
                venue=venue,
                year=year,
            )
            self.papers.append(sp)
            self.paper_ids.add(paper_id)
            new_papers.append(sp)

        return new_papers
