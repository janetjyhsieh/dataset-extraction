import logging
import os
import time
from dataclasses import dataclass, field

import requests

from dataset_extraction.downloader.utils import titles_match

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
_FIELDS = "title,openAccessPdf,externalIds,year,authors,venue,paperId"
_RETRYABLE = {429, 503}


@dataclass
class S2Paper:
    title: str
    year: int | None
    venue: str | None
    authors: list[str]
    open_access_pdf: str | None
    external_ids: dict[str, str] = field(default_factory=dict)
    search_engine_id: str | None = None


class SemanticScholarClient:
    def __init__(self, max_retries: int = 4):
        self._max_retries = max_retries

    def _headers(self) -> dict:
        api_key = os.environ.get("S2_API_KEY")
        return {"x-api-key": api_key} if api_key else {}

    def _get(self, params: dict) -> requests.Response:
        delay = 5
        resp = None
        for attempt in range(self._max_retries):
            resp = requests.get(_SEARCH_URL, params=params, headers=self._headers(), timeout=15)
            if resp.status_code not in _RETRYABLE:
                return resp
            retry_after = int(resp.headers.get("Retry-After", delay))
            logger.warning(
                "%d from S2 — retrying in %ds (attempt %d/%d)",
                resp.status_code, retry_after, attempt + 1, self._max_retries,
            )
            time.sleep(retry_after)
            delay *= 2
        return resp

    def get_paper(self, title: str) -> S2Paper | None:
        """Search S2 by title and return the best matching paper, or None."""
        try:
            resp = self._get({"query": title, "fields": _FIELDS, "limit": 3})
            logger.debug("S2 status: %d", resp.status_code)
            resp.raise_for_status()
            for raw in resp.json().get("data", []):
                result_title = raw.get("title", "")
                match = titles_match(title, result_title)
                logger.debug("S2 result: %r", result_title)
                logger.debug("  externalIds: %s", raw.get("externalIds"))
                logger.debug("  openAccessPdf: %s", raw.get("openAccessPdf"))
                logger.debug(
                    "  year: %s  venue: %s  title match: %s",
                    raw.get("year"), raw.get("venue"), match,
                )
                if not match:
                    continue
                pdf_info = raw.get("openAccessPdf") or {}
                return S2Paper(
                    title=result_title,
                    year=raw.get("year"),
                    venue=raw.get("venue") or None,
                    authors=[a["name"] for a in (raw.get("authors") or []) if a.get("name")],
                    open_access_pdf=pdf_info.get("url"),
                    external_ids=raw.get("externalIds") or {},
                    search_engine_id=raw.get("paperId"),
                )
        except Exception:
            logger.debug("S2 error for %r", title, exc_info=True)
        return None

    def get_open_access_pdf(self, title: str) -> str | None:
        paper = self.get_paper(title)
        return paper.open_access_pdf if paper else None

    def get_external_ids(self, title: str) -> dict[str, str]:
        paper = self.get_paper(title)
        return paper.external_ids if paper else {}

    def get_venue_year(self, title: str) -> tuple[str | None, int | None]:
        paper = self.get_paper(title)
        return (paper.venue, paper.year) if paper else (None, None)
