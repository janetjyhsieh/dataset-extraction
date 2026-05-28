"""
TODO: make sure the paper finding (ExternalIDs, venue-based) rules are in the desired order.
"""
import logging
import re
from pathlib import Path

import requests

from dataset_extraction.downloader.arxiv import ArxivClient
from dataset_extraction.downloader.semantic_scholar import SemanticScholarClient
from dataset_extraction.downloader.utils import titles_match
from dataset_extraction.downloader.venues import pdf_from_venue, venue_source
from dataset_extraction.state.paper import PaperInfo, PdfDownloadSource

logger = logging.getLogger(__name__)

_s2_client = SemanticScholarClient()
_arxiv_client = ArxivClient()


def _pdf_from_external_ids(external_ids: dict) -> str | None:
    """Return a direct PDF URL from known external IDs (ArXiv, ACL, PubMedCentral)."""
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

    pmc_id = external_ids.get("PubMedCentral")
    if pmc_id:
        url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/pdf"
        logger.debug("Found PubMedCentral ID: %s → %s", pmc_id, url)
        return url

    return None


def _search_arxiv(title: str) -> str | None:
    for result in _arxiv_client.search_by_title(title):
        match = titles_match(title, result["title"])
        logger.debug("arXiv result: %r  id: %s  match: %s", result["title"], result["id"], match)
        if match:
            return result["pdf_url"]
    return None


def _title_to_id(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:80]


def _venue_year_from_dblp(dblp_key: str) -> int | None:
    """Extract the conference year from a DBLP key.

    DBLP keys encode the year as a 2-digit suffix on the paper ID, e.g.
    'conf/cvpr/HeZRS16' → 2016. More reliable than S2's year field, which
    reflects the arXiv submission date rather than the conference year.
    """
    last = dblp_key.rstrip("/").rsplit("/", 1)[-1]
    m = re.search(r"(\d{2})$", last)
    if not m:
        return None
    yy = int(m.group(1))
    return 2000 + yy if yy <= 25 else 1900 + yy


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
    s2_paper = _s2_client.get_paper(title)
    if s2_paper:
        node.year = s2_paper.year
        node.venue = s2_paper.venue
        node.authors = s2_paper.authors

        if s2_paper.open_access_pdf:
            pdf_url = s2_paper.open_access_pdf
            pdf_source = PdfDownloadSource.semantic_scholar
            logger.debug("Found via S2 openAccessPdf")

        if pdf_url is None:
            result = _pdf_from_external_ids(s2_paper.external_ids)
            if result:
                pdf_url = result
                ids = s2_paper.external_ids
                if ids.get("ArXiv"):
                    pdf_source = PdfDownloadSource.arxiv
                elif ids.get("ACL"):
                    pdf_source = PdfDownloadSource.acl
                elif ids.get("PubMedCentral"):
                    pdf_source = PdfDownloadSource.pubmedcentral

            venue_year = _venue_year_from_dblp(s2_paper.external_ids.get("DBLP", "")) or s2_paper.year
            if pdf_url is None and venue_year:
                result = pdf_from_venue(s2_paper.external_ids, venue_year, title)
                if result:
                    pdf_url = result
                    pdf_source = venue_source(s2_paper.external_ids)

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
