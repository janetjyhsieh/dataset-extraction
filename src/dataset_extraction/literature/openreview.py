from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import openreview

from dataset_extraction.literature.source import LiteratureSource, SourcePaper
from dataset_extraction.literature.utils import keywords_in_string

logger = logging.getLogger("dataset_extraction.literature.openreview")


class OpenReviewSource(LiteratureSource):
    def __init__(self, working_dir: Path, index_path: Path, client):
        super().__init__(working_dir, index_path)
        self.client = client

    def get_papers(self, venue: str, year: int | None = None, keywords: list[str] | None = None) -> list[SourcePaper]:
        notes = self.client.get_all_notes(content={"venueid": venue})
        new_papers = []
        for note in notes:
            title = note.content.get("title", {})
            if isinstance(title, dict):
                title = title.get("value", "")

            authors = note.content.get("authors", [])
            if isinstance(authors, dict):
                authors = authors.get("value", [])
            if not isinstance(authors, list):
                authors = []

            if keywords:
                raw = note.content.get("keywords", [])
                note_keywords = raw.get("value", []) if isinstance(raw, dict) else (raw if isinstance(raw, list) else [])
                if not keywords_in_string(" ".join(note_keywords) + " " + title, keywords):
                    continue

            if note.id in self.paper_ids:
                continue

            pdf_url = f"{self.client.baseurl}/pdf?id={note.id}"
            sp = SourcePaper(paper_id=note.id, title=title, authors=authors, venue=venue, year=year, pdf_url=pdf_url)
            self.papers.append(sp)
            self.paper_ids.add(note.id)
            new_papers.append(sp)
        return new_papers

    def download_and_save_papers(self, new_papers: list[SourcePaper]) -> None:
        for paper in new_papers:
            safe_id = re.sub(r"[^a-z0-9_-]", "_", paper.paper_id.lower())
            dest = self.working_dir / "pdfs" / f"{safe_id}.pdf"
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                paper.pdf_path = str(dest)
            else:
                tmp = dest.with_suffix(".tmp")
                try:
                    tmp.write_bytes(self.client.get_pdf(paper.paper_id))
                    tmp.rename(dest)
                except Exception:
                    tmp.unlink(missing_ok=True)
                    logger.warning("Failed to download %s", paper.paper_id, exc_info=True)
                    continue
                paper.pdf_path = str(dest)
            with open(self.index_path, "a") as f:
                f.write(json.dumps(paper.model_dump()) + "\n")