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
from dataset_extraction.state.paper_entries import PaperInfo, PdfDownloadSource

logger = logging.getLogger(__name__)

_s2_client = SemanticScholarClient()
_arxiv_client = ArxivClient()


def _urls_from_external_ids(external_ids: dict) -> str | None:
    """Return a direct PDF URL from known external IDs (ArXiv, ACL, PubMedCentral)."""
    external_urls = []
    arxiv_id = external_ids.get("ArXiv")
    if arxiv_id:
        url = f"https://arxiv.org/pdf/{arxiv_id}"
        logger.debug("Found ArXiv ID: %s → %s", arxiv_id, url)
        external_urls.append(
            {"source": PdfDownloadSource.s2_arxiv, "url": url}
        )

    acl_id = external_ids.get("ACL")
    if acl_id:
        url = f"https://aclanthology.org/{acl_id}.pdf"
        logger.debug("Found ACL ID: %s → %s", acl_id, url)
        external_urls.append(
            {"source": PdfDownloadSource.s2_acl, "url": url}
        )

    pmc_id = external_ids.get("PubMedCentral")
    if pmc_id:
        url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/pdf"
        logger.debug("Found PubMedCentral ID: %s → %s", pmc_id, url)
        external_urls.append(
            {"source": PdfDownloadSource.s2_pubmedcentral, "url": url}
        )

    return external_urls


def _search_arxiv(title: str) -> tuple[str, str] | None:
    """Return (pdf_url, arxiv_id) for the first matching result, or None."""
    for result in _arxiv_client.search_by_title(title):
        match = titles_match(title, result["title"])
        logger.debug("arXiv result: %r  id: %s  match: %s", result["title"], result["id"], match)
        if match:
            arxiv_id = result["id"].split("/abs/")[-1].split("v")[0]
            return result["pdf_url"], arxiv_id
    return None


def _title_to_id(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:80]


def _download_pdf(url: str, dest: Path, node: PaperInfo, source: PdfDownloadSource) -> bool:
    node.pdf_info.link_found = True
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
    except Exception as e:
        logger.debug("Download failed from %s: %s", url, e)
        node.pdf_info.errors.append(f"Download failed: {url}")
        return False
    node.pdf_info.url = url
    node.pdf_info.pdf_download_source = source
    node.pdf_info.pdf_file_path = str(dest)
    node.pdf_info.download_success = True
    return True


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

    Each URL is downloaded immediately after being found. If the download fails,
    the next source is tried. Populates node.authors, node.year, node.venue,
    and node.pdf_info in-place. Errors are appended to node.pdf_info.errors.
    Skips the download if the destination file already exists.

    Args:
        node: The PaperInfo to populate. Must have canonical_title set.
        download_dir: Directory to save the downloaded PDF.

    Returns:
        Local Path of the downloaded PDF, or None on failure.
    """
    download_dir = Path(download_dir)
    download_dir.mkdir(parents=True, exist_ok=True)
    title = node.canonical_title
    dest = download_dir / f"{_title_to_id(title)}.pdf"

    # Stage 1 & 2: Semantic Scholar
    s2_paper = _s2_client.get_paper(title)
    if s2_paper:
        node.year = s2_paper.year
        node.venue = s2_paper.venue
        node.authors = s2_paper.authors
        node.ss_id = s2_paper.paper_id

        if s2_paper.open_access_pdf:
            if _download_pdf(s2_paper.open_access_pdf, dest, node, PdfDownloadSource.s2_open_access_pdf):
                return dest

        ext_urls = _urls_from_external_ids(s2_paper.external_ids) # this should live inside utils
        for ext_url in ext_urls:
            if _download_pdf(ext_url["url"], dest, node, ext_url["source"]):
                return dest

        venue_url = pdf_from_venue(s2_paper.external_ids, title)
        if venue_url and _download_pdf(venue_url, dest, node, venue_source(s2_paper.external_ids)):
            return dest

    # Stage 3: arXiv fallback
    logger.debug("Falling back to arXiv search for %r", title)
    arxiv_result = _search_arxiv(title)
    if arxiv_result:
        arxiv_url, arxiv_id = arxiv_result
        if _download_pdf(arxiv_url, dest, node, PdfDownloadSource.arxiv):
            return dest

    if not node.pdf_info.link_found:
        node.pdf_info.errors.append("No open-access PDF found")
    node.pdf_info.download_success = False
    return None
