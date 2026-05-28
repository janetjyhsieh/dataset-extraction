import logging
import time
import xml.etree.ElementTree as ET

import requests

logger = logging.getLogger(__name__)

_API_URL = "http://export.arxiv.org/api/query"
_NS = {"atom": "http://www.w3.org/2005/Atom"}
_MIN_INTERVAL = 3.0  # seconds required between requests per arxiv API guidelines
_RETRYABLE = {429, 503}


class ArxivClient:
    def __init__(self, min_interval: float = _MIN_INTERVAL, max_retries: int = 4):
        self._min_interval = min_interval
        self._max_retries = max_retries
        self._last_call: float = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call = time.monotonic()

    def _get(self, params: dict) -> requests.Response:
        self._throttle()
        delay = 5
        resp = None
        for attempt in range(self._max_retries):
            resp = requests.get(_API_URL, params=params, timeout=30)
            if resp.status_code not in _RETRYABLE:
                return resp
            retry_after = int(resp.headers.get("Retry-After", delay))
            logger.warning(
                "%d from arXiv — retrying in %ds (attempt %d/%d)",
                resp.status_code, retry_after, attempt + 1, self._max_retries,
            )
            time.sleep(retry_after)
            self._throttle()
            delay *= 2
        return resp

    def search_by_title(self, title: str, max_results: int = 3) -> list[dict]:
        """Query the arXiv title index. Returns a list of dicts with 'title' and 'pdf_url'."""
        params = {
            "search_query": f'ti:"{title}"',
            "max_results": max_results,
            "sortBy": "relevance",
        }
        try:
            resp = self._get(params)
            resp.raise_for_status()
        except Exception:
            logger.debug("arXiv request failed for %r", title, exc_info=True)
            return []

        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError:
            logger.debug("arXiv response parse error for %r", title, exc_info=True)
            return []

        results = []
        for entry in root.findall("atom:entry", _NS):
            result_title = (entry.findtext("atom:title", "", _NS) or "").strip()
            entry_id = entry.findtext("atom:id", "", _NS) or ""
            pdf_url = None
            for link in entry.findall("atom:link", _NS):
                if link.get("title") == "pdf":
                    pdf_url = link.get("href")
                    break
            if pdf_url is None and "/abs/" in entry_id:
                arxiv_id = entry_id.split("/abs/")[-1]
                pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"
            if pdf_url:
                results.append({"title": result_title, "pdf_url": pdf_url, "id": entry_id})
        return results
