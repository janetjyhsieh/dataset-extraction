"""
TODO: make sure the paper finding (ExternalIDs, venue-based) rules are in the desired order.
"""
import logging
import os
import re
import time
from pathlib import Path

import arxiv
import requests
from bs4 import BeautifulSoup

from dataset_extraction.state.paper import DatasetPaperNode, PdfDownloadSource

logger = logging.getLogger(__name__)

_S2_SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search"
_CVF_BASE = "https://openaccess.thecvf.com"
_CVF_VENUES = {"cvpr": "CVPR", "iccv": "ICCV", "wacv": "WACV"}
_ACL_VENUES = {"acl", "emnlp", "naacl", "eacl", "coling"}


def _s2_headers() -> dict:
    api_key = os.environ.get("S2_API_KEY")
    return {"x-api-key": api_key} if api_key else {}


def _normalize(text: str) -> set[str]:
    return set(re.sub(r"[^a-z0-9 ]", "", text.lower()).split())


def _titles_match(query: str, result: str, threshold: float = 0.7) -> bool:
    q_words = _normalize(query)
    r_words = _normalize(result)
    if not q_words:
        return False
    return len(q_words & r_words) / len(q_words) >= threshold


def _get_with_backoff(url: str, params: dict, timeout: int, headers: dict | None = None) -> requests.Response:
    delay = 5
    for attempt in range(4):
        resp = requests.get(url, params=params, headers=headers, timeout=timeout)
        if resp.status_code != 429:
            return resp
        retry_after = int(resp.headers.get("Retry-After", delay))
        logger.warning("429 rate limited — retrying in %ds (attempt %d/4)", retry_after, attempt + 1)
        time.sleep(retry_after)
        delay *= 2
    return resp


def _get_s2_paper(title: str) -> dict | None:
    """Search S2 for a paper by title, return the best matching paper dict."""
    try:
        resp = _get_with_backoff(
            _S2_SEARCH,
            params={
                "query": title,
                "fields": "title,openAccessPdf,externalIds,year,authors,venue",
                "limit": 3,
            },
            timeout=15,
            headers=_s2_headers(),
        )
        logger.debug("S2 status: %d", resp.status_code)
        resp.raise_for_status()
        for paper in resp.json().get("data", []):
            result_title = paper.get("title", "")
            match = _titles_match(title, result_title)
            logger.debug("S2 result: %r", result_title)
            logger.debug("  externalIds: %s", paper.get("externalIds"))
            logger.debug("  openAccessPdf: %s", paper.get("openAccessPdf"))
            logger.debug("  year: %s  venue: %s  title match: %s", paper.get("year"), paper.get("venue"), match)
            if match:
                return paper
    except Exception:
        logger.debug("S2 error for %r", title, exc_info=True)
    return None


def _pdf_from_external_ids(external_ids: dict) -> str | None:
    """Return a direct PDF URL from known external IDs (ArXiv, ACL)."""
    arxiv_id = external_ids.get("ArXiv")
    if arxiv_id:
        url = f"https://arxiv.org/pdf/{arxiv_id}"
        logger.debug("Found ArXiv ID: %s → %s", arxiv_id, url)
        return url

    acl_id = external_ids.get("ACL")
    if acl_id:
        url = f"https://aclanthology.org/{acl_id}.pdf"
        logger.debug("Found ACL ID: %s → %s", acl_id, url)
        return url

    return None


def _search_cvf(dblp_key: str, year: int, title: str) -> str | None:
    venue_key = dblp_key.split("/")[1]
    venue = _CVF_VENUES.get(venue_key)
    if not venue:
        return None
    try:
        url = f"{_CVF_BASE}/{venue}{year}?day=all"
        logger.debug("CVF fetching: %s", url)
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for dt in soup.find_all("dt", class_="ptitle"):
            a_tag = dt.find("a")
            if not a_tag:
                continue
            result_title = a_tag.get_text(strip=True)
            match = _titles_match(title, result_title)
            if not match:
                continue
            logger.debug("CVF result: %r, match: %s", result_title, match)
            href = a_tag.get("href", "")
            logger.debug("CVF href: %s", href)
            pdf_href = href.replace("/html/", "/papers/").replace(".html", ".pdf")
            return _CVF_BASE + pdf_href if pdf_href.startswith("/") else _CVF_BASE + "/" + pdf_href
    except Exception:
        logger.debug("CVF error for %r", title, exc_info=True)
    return None


def _search_ecva(year: int, title: str) -> str | None:
    try:
        url = "https://www.ecva.net/papers.php"
        logger.debug("ECVA fetching: %s", url)
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        year_str = str(year)
        for dt in soup.find_all("dt", class_="ptitle"):
            a_tag = dt.find("a")
            if not a_tag:
                continue
            href = a_tag.get("href", "")
            if year_str not in href:
                continue
            result_title = a_tag.get_text(strip=True)
            match = _titles_match(title, result_title)
            logger.debug("ECVA result: %r, match: %s", result_title, match)
            if not match:
                continue
            dd = dt.find_next_sibling("dd")
            if dd:
                pdf_link = dd.find("a", href=lambda h: h and h.endswith(".pdf"))
                if pdf_link:
                    pdf_href = pdf_link.get("href")
                    return pdf_href if pdf_href.startswith("http") else "https://www.ecva.net" + pdf_href
            pdf_href = href.replace("/html/", "/papers/").replace(".html", ".pdf")
            return "https://www.ecva.net" + pdf_href
    except Exception:
        logger.debug("ECVA error for %r", title, exc_info=True)
    return None


def _search_neurips(year: int, title: str) -> str | None:
    try:
        url = f"https://papers.nips.cc/paper_files/paper/{year}"
        logger.debug("NeurIPS fetching: %s", url)
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for a_tag in soup.find_all("a", href=lambda h: h and "/hash/" in h):
            result_title = a_tag.get_text(strip=True)
            match = _titles_match(title, result_title)
            if not match:
                continue
            href = a_tag.get("href")
            # /paper_files/paper/2023/hash/xxx-Abstract-Conference.html
            # → /paper_files/paper/2023/file/xxx-Paper-Conference.pdf
            pdf_href = re.sub(r"/hash/(.+?)-Abstract(.*?)\.html$", r"/file/\1-Paper\2.pdf", href)
            return "https://papers.nips.cc" + pdf_href
    except Exception:
        logger.debug("NeurIPS error for %r", title, exc_info=True)
    return None


def _search_pmlr(title: str) -> str | None:
    try:
        resp = requests.get(
            "https://proceedings.mlr.press/search",
            params={"query": title},
            timeout=15,
        )
        logger.debug("PMLR status: %d", resp.status_code)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for div in soup.select("div.paper"):
            title_tag = div.find("p", class_="title")
            if not title_tag:
                continue
            result_title = title_tag.get_text(strip=True)
            match = _titles_match(title, result_title)
            logger.debug("PMLR result: %r, match: %s", result_title, match)
            if not match:
                continue
            pdf_link = div.find("a", string=re.compile(r"download pdf", re.I))
            if pdf_link:
                return pdf_link.get("href")
    except Exception:
        logger.debug("PMLR error for %r", title, exc_info=True)
    return None


def _search_acl_anthology(title: str) -> str | None:
    try:
        resp = requests.get(
            "https://aclanthology.org/search/",
            params={"q": title},
            timeout=15,
        )
        logger.debug("ACL Anthology status: %d", resp.status_code)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for item in soup.select("li.list-group-item"):
            a_tag = item.find("a", class_="align-middle")
            if not a_tag:
                continue
            result_title = a_tag.get_text(strip=True)
            match = _titles_match(title, result_title)
            logger.debug("ACL result: %r, match: %s", result_title, match)
            if not match:
                continue
            acl_id = a_tag.get("href", "").strip("/")
            return f"https://aclanthology.org/{acl_id}.pdf"
    except Exception:
        logger.debug("ACL Anthology error for %r", title, exc_info=True)
    return None


def _search_aaai(year: int, title: str) -> str | None:
    try:
        resp = requests.get(
            "https://ojs.aaai.org/index.php/AAAI/search/search",
            params={"searchInitiated": "1", "query": title, "searchField": "title"},
            timeout=15,
        )
        logger.debug("AAAI status: %d", resp.status_code)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for article in soup.select("li.obj_article_summary"):
            title_tag = article.find("h3", class_="title")
            a_tag = title_tag.find("a") if title_tag else article.find("a")
            if not a_tag:
                continue
            result_title = a_tag.get_text(strip=True)
            match = _titles_match(title, result_title)
            logger.debug("AAAI result: %r, match: %s", result_title, match)
            if not match:
                continue
            return a_tag.get("href", "").rstrip("/") + "/pdf"
    except Exception:
        logger.debug("AAAI error for %r", title, exc_info=True)
    return None


def _search_openreview(title: str) -> str | None:
    try:
        resp = requests.get(
            "https://api2.openreview.net/notes",
            params={"content.title": title, "limit": 3},
            timeout=15,
        )
        logger.debug("OpenReview status: %d", resp.status_code)
        resp.raise_for_status()
        for note in resp.json().get("notes", []):
            content = note.get("content", {})
            result_title = content.get("title", "")
            if isinstance(result_title, dict):
                result_title = result_title.get("value", "")
            match = _titles_match(title, result_title)
            logger.debug("OpenReview result: %r, match: %s", result_title, match)
            if match:
                return f"https://openreview.net/pdf?id={note['id']}"
    except Exception:
        logger.debug("OpenReview error for %r", title, exc_info=True)
    return None


def _pdf_from_venue(external_ids: dict, year: int, title: str) -> str | None:
    """Route to a venue-specific open-access source based on the DBLP key."""
    dblp_key = external_ids.get("DBLP")
    if not dblp_key:
        return None

    venue = dblp_key.split("/")[1] if "/" in dblp_key else None
    if not venue:
        return None

    if venue in _CVF_VENUES:
        logger.debug("Routing to CVF (%s%d)", venue.upper(), year)
        return _search_cvf(dblp_key, year, title)

    if venue == "eccv":
        logger.debug("Routing to ECVA (ECCV%d)", year)
        return _search_ecva(year, title)

    if venue == "nips":
        logger.debug("Routing to NeurIPS proceedings (%d)", year)
        return _search_neurips(year, title)

    if venue == "icml":
        logger.debug("Routing to PMLR (ICML%d)", year)
        return _search_pmlr(title)

    if venue == "iclr":
        logger.debug("Routing to OpenReview (ICLR)")
        return _search_openreview(title)

    if venue in _ACL_VENUES:
        logger.debug("Routing to ACL Anthology (%s)", venue.upper())
        return _search_acl_anthology(title)

    if venue == "aaai":
        logger.debug("Routing to AAAI OJS (%d)", year)
        return _search_aaai(year, title)

    logger.debug("No open-access handler for venue '%s'", venue)
    return None


def _search_arxiv(title: str) -> str | None:
    try:
        client = arxiv.Client()
        results = client.results(arxiv.Search(
            query=f'ti:"{title}"',
            max_results=3,
            sort_by=arxiv.SortCriterion.Relevance,
        ))
        for paper in results:
            match = _titles_match(title, paper.title)
            logger.debug("arXiv result: %r  id: %s  match: %s", paper.title, paper.entry_id, match)
            if match:
                return paper.pdf_url
    except Exception:
        logger.debug("arXiv error for %r", title, exc_info=True)
    return None


def _venue_source(external_ids: dict) -> PdfDownloadSource | None:
    """Map a DBLP venue key to its PdfDownloadSource enum value."""
    dblp_key = external_ids.get("DBLP", "")
    venue = dblp_key.split("/")[1] if "/" in dblp_key else ""
    mapping: dict[str, PdfDownloadSource] = {
        "cvpr": PdfDownloadSource.cvf,
        "iccv": PdfDownloadSource.cvf,
        "wacv": PdfDownloadSource.cvf,
        "eccv": PdfDownloadSource.ecva,
        "nips": PdfDownloadSource.neurips,
        "icml": PdfDownloadSource.pmlr,
        "iclr": PdfDownloadSource.openreview,
        "aaai": PdfDownloadSource.aaai,
        **{v: PdfDownloadSource.acl for v in _ACL_VENUES},
    }
    return mapping.get(venue)


def _title_to_id(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:80]


# BUG: the year from semantic shcolar may not be the same as the conference year.
# For example: Deep Residual Learning for Image Recognition, year 2015
# However, the paper was published in CVPR 2016. If use year 2015, then the 
# Find by venue will not succeed.
def find_and_download_pdf(
    node: PaperInfo,
    download_dir: Path,
) -> Path | None:
    """Populate *node* with paper metadata and download its PDF.

    Searches for the paper using node.canonical_title via a three-stage lookup:
      1. Semantic Scholar openAccessPdf field.
      2. Venue routing from S2 metadata (ArXiv/ACL IDs, then venue-specific
         sources: CVF, ECVA, NeurIPS, PMLR, ACL Anthology, AAAI, OpenReview).
      3. arXiv title search as final fallback.

    Populates node.authors, node.year, node.venue, and node.pdf_info in-place.
    Errors are appended to node.pdf_info.errors. Skips the download if the
    destination file already exists.

    Args:
        node: The DatasetPaperNode to populate. Must have canonical_title set.
        download_dir: Directory to save the downloaded PDF.

    Returns:
        Local Path of the downloaded PDF, or None on failure.
    """
    download_dir = Path(download_dir)
    download_dir.mkdir(parents=True, exist_ok=True)
    title = node.canonical_title

    pdf_url: str | None = None
    pdf_source: PdfDownloadSource | None = None

    # Stage 1 & 2: Semantic Scholar
    s2_paper = _get_s2_paper(title)
    if s2_paper:
        node.year = s2_paper.get("year")
        node.venue = s2_paper.get("venue") or None
        node.authors = [a["name"] for a in (s2_paper.get("authors") or []) if a.get("name")]

        s2_pdf = s2_paper.get("openAccessPdf")
        if s2_pdf and s2_pdf.get("url"):
            pdf_url = s2_pdf["url"]
            pdf_source = PdfDownloadSource.semantic_scholar
            logger.debug("Found via S2 openAccessPdf")

        if pdf_url is None:
            external_ids = s2_paper.get("externalIds") or {}
            year = s2_paper.get("year")

            result = _pdf_from_external_ids(external_ids)
            if result:
                pdf_url = result
                pdf_source = (
                    PdfDownloadSource.arxiv if external_ids.get("ArXiv")
                    else PdfDownloadSource.acl
                )

            if pdf_url is None and year:
                result = _pdf_from_venue(external_ids, year, title)
                if result:
                    pdf_url = result
                    pdf_source = _venue_source(external_ids)

    # Stage 3: arXiv fallback
    if pdf_url is None:
        logger.debug("Falling back to arXiv search for %r", title)
        result = _search_arxiv(title)
        if result:
            pdf_url = result
            pdf_source = PdfDownloadSource.arxiv

    node.pdf_info.link_found = pdf_url is not None
    node.pdf_info.url = pdf_url
    node.pdf_info.pdf_download_source = pdf_source

    if pdf_url is None:
        node.pdf_info.errors.append("No open-access PDF found")
        node.pdf_info.download_success = False
        return None

    # Download
    dest = download_dir / f"{_title_to_id(title)}.pdf"
    if dest.exists():
        node.pdf_info.pdf_file_path = str(dest)
        node.pdf_info.download_success = True
        return dest

    try:
        resp = requests.get(pdf_url, timeout=60)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        node.pdf_info.pdf_file_path = str(dest)
        node.pdf_info.download_success = True
        return dest
    except Exception as e:
        node.pdf_info.errors.append(f"Failed to download PDF from {pdf_url}: {e}")
        node.pdf_info.download_success = False
        return None
