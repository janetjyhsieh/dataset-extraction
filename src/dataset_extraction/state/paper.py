from __future__ import annotations

import re
from enum import Enum

from pydantic import BaseModel


def canonicalize_title(title: str) -> str:
    """Return a normalized paper title for use as a stable identifier.

    Lowercases, strips leading/trailing whitespace, and collapses internal
    whitespace to a single space.
    """
    return re.sub(r"\s+", " ", title.lower().strip())


class PdfDownloadSource(str, Enum):
    s2_open_access_pdf = "semantic_scholar.openAccessPdf"
    s2_arxiv = "semantic_scholar.external_ids.arxiv"
    s2_acl = "semantic_scholar.external_ids.acl"
    s2_pubmedcentral = "semantic_scholar.external_ids.pubmedcentral"
    venue_cvf = "venue.cvf"
    venue_ecva = "venue.ecva"
    venue_neurips = "venue.neurips"
    venue_pmlr = "venue.pmlr"
    venue_openreview = "venue.openreview"
    venue_aaai = "venue.aaai"
    venue_acl = "venue.acl"
    arxiv = "arxiv"
    direct = "direct"


class PdfInfo(BaseModel):
    link_found: bool #TODO: default False
    download_success: bool #TODO: default False
    url: str | None = None
    pdf_file_path: str | None = None
    pdf_download_source: PdfDownloadSource | None = None
    errors: list[str] = []


class PaperInfo(BaseModel):
    canonical_title: str
    raw_title: str | None = None
    authors: list[str] | None = None
    year: int | None = None
    venue: str | None = None
    pdf_info: PdfInfo


class DatasetPaperNode(BaseModel):
    """A paper that introduces one or more new datasets.

    ``datasets`` is populated after LLM extraction completes.
    ``source_papers_titles`` is populated from the source dataset citations found
    during extraction — these are the papers that proposed the upstream
    datasets used to construct the datasets introduced by this paper.
    """
    title: str
    datasets: list[str] = []
    source_papers_titles: list[str] = []
    source_processed: bool = False
