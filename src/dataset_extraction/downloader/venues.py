import logging
import re

import requests
from bs4 import BeautifulSoup

from dataset_extraction.downloader.utils import titles_match
from dataset_extraction.state.paper import PdfDownloadSource

logger = logging.getLogger(__name__)

_CVF_BASE = "https://openaccess.thecvf.com"
_CVF_VENUES = {"cvpr": "CVPR", "iccv": "ICCV", "wacv": "WACV"}
_ACL_VENUES = {"acl", "emnlp", "naacl", "eacl", "coling"}


def _cvf_search_page(url: str, title: str) -> str | None:
    """Fetch one CVF listing page and return the PDF URL if the paper is found."""
    logger.debug("CVF fetching: %s", url)
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for dt in soup.find_all("dt", class_="ptitle"):
        a_tag = dt.find("a")
        if not a_tag:
            continue
        result_title = a_tag.get_text(strip=True)
        if not titles_match(title, result_title):
            continue
        logger.debug("CVF result: %r", result_title)
        href = a_tag.get("href", "")
        logger.debug("CVF href: %s", href)
        pdf_href = href.replace("/html/", "/papers/").replace(".html", ".pdf")
        return _CVF_BASE + pdf_href if pdf_href.startswith("/") else _CVF_BASE + "/" + pdf_href
    return None


def search_cvf(dblp_key: str, year: int, title: str) -> str | None:
    venue_key = dblp_key.split("/")[1]
    venue = _CVF_VENUES.get(venue_key)
    if not venue:
        return None
    try:
        if year > 2020:
            return _cvf_search_page(f"{_CVF_BASE}/{venue}{year}?day=all", title)

        # For ≤ 2020, day=all is empty; find per-day links from the landing page.
        resp = requests.get(f"{_CVF_BASE}/{venue}{year}", timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "day=" not in href or "day=all" in href:
                continue
            url = href if href.startswith("http") else f"{_CVF_BASE}/{href}"
            result = _cvf_search_page(url, title)
            if result is not None:
                return result
    except Exception:
        logger.debug("CVF error for %r", title, exc_info=True)
    return None


def search_ecva(year: int, title: str) -> str | None:
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
            match = titles_match(title, result_title)
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


def search_neurips(year: int, title: str) -> str | None:
    try:
        url = f"https://papers.nips.cc/paper_files/paper/{year}"
        logger.debug("NeurIPS fetching: %s", url)
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for a_tag in soup.find_all("a", href=lambda h: h and "/hash/" in h):
            result_title = a_tag.get_text(strip=True)
            match = titles_match(title, result_title)
            if not match:
                continue
            href = a_tag.get("href")
            pdf_href = re.sub(r"/hash/(.+?)-Abstract(.*?)\.html$", r"/file/\1-Paper\2.pdf", href)
            return "https://papers.nips.cc" + pdf_href
    except Exception:
        logger.debug("NeurIPS error for %r", title, exc_info=True)
    return None


def search_pmlr(title: str) -> str | None:
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
            match = titles_match(title, result_title)
            logger.debug("PMLR result: %r, match: %s", result_title, match)
            if not match:
                continue
            pdf_link = div.find("a", string=re.compile(r"download pdf", re.I))
            if pdf_link:
                return pdf_link.get("href")
    except Exception:
        logger.debug("PMLR error for %r", title, exc_info=True)
    return None


def search_acl_anthology(title: str) -> str | None:
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
            match = titles_match(title, result_title)
            logger.debug("ACL result: %r, match: %s", result_title, match)
            if not match:
                continue
            acl_id = a_tag.get("href", "").strip("/")
            return f"https://aclanthology.org/{acl_id}.pdf"
    except Exception:
        logger.debug("ACL Anthology error for %r", title, exc_info=True)
    return None


def search_aaai(year: int, title: str) -> str | None:
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
            match = titles_match(title, result_title)
            logger.debug("AAAI result: %r, match: %s", result_title, match)
            if not match:
                continue
            return a_tag.get("href", "").rstrip("/") + "/pdf"
    except Exception:
        logger.debug("AAAI error for %r", title, exc_info=True)
    return None


def search_openreview(title: str) -> str | None:
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
            match = titles_match(title, result_title)
            logger.debug("OpenReview result: %r, match: %s", result_title, match)
            if match:
                return f"https://openreview.net/pdf?id={note['id']}"
    except Exception:
        logger.debug("OpenReview error for %r", title, exc_info=True)
    return None


def pdf_from_venue(external_ids: dict, year: int, title: str) -> str | None:
    """Route to a venue-specific open-access source based on the DBLP key."""
    dblp_key = external_ids.get("DBLP")
    if not dblp_key:
        return None

    venue = dblp_key.split("/")[1] if "/" in dblp_key else None
    if not venue:
        return None

    if venue in _CVF_VENUES:
        logger.debug("Routing to CVF (%s%d)", venue.upper(), year)
        return search_cvf(dblp_key, year, title)

    if venue == "eccv":
        logger.debug("Routing to ECVA (ECCV%d)", year)
        return search_ecva(year, title)

    if venue == "nips":
        logger.debug("Routing to NeurIPS proceedings (%d)", year)
        return search_neurips(year, title)

    if venue == "icml":
        logger.debug("Routing to PMLR (ICML%d)", year)
        return search_pmlr(title)

    if venue == "iclr":
        logger.debug("Routing to OpenReview (ICLR)")
        return search_openreview(title)

    if venue in _ACL_VENUES:
        logger.debug("Routing to ACL Anthology (%s)", venue.upper())
        return search_acl_anthology(title)

    if venue == "aaai":
        logger.debug("Routing to AAAI OJS (%d)", year)
        return search_aaai(year, title)

    logger.debug("No open-access handler for venue '%s'", venue)
    return None


def venue_source(external_ids: dict) -> PdfDownloadSource | None:
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
