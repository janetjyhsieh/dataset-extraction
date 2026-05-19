from enum import Enum

from pydantic import BaseModel

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
    venue: str | None = None
    year: int | None = None
    pdf_download_source: PdfDownloadSource | None = None

class PaperInfo(BaseModel):
    paper_title: str
    normalized_paper_title: str | None = None
    pdf_info: PdfInfo