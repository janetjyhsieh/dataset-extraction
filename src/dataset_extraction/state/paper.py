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
    semantic_scholar = "semantic_scholar"
    arxiv = "arxiv"
    acl = "acl"
    cvf = "cvf"
    ecva = "ecva"
    neurips = "neurips"
    pmlr = "pmlr"
    openreview = "openreview"
    aaai = "aaai"


class PdfInfo(BaseModel):
    link_found: bool
    download_success: bool
    url: str | None = None
    pdf_file_path: str | None = None
    pdf_download_source: PdfDownloadSource | None = None
    errors: list[str] = []


class PaperInfo(BaseModel):
    raw_title: str
    canonical_title: str
    authors: list[str] | None = None
    year: int | None = None
    venue: str | None = None
    pdf_info: PdfInfo


class DatasetPaperNode(PaperInfo):
    """A paper that introduces one or more new datasets.

    ``datasets`` is populated after LLM extraction completes. TODO(consider identifying with uuid)
    ``source_papers`` is populated from the source dataset citations found
    during extraction — these are the papers that proposed the upstream
    datasets used to construct the datasets introduced by this paper.
    """
    # datasets: list[str] = []
    source_papers: list[str] = []
