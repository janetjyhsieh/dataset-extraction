import re
import requests
from pathlib import Path
import tempfile

_HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; dataset-extraction-bot/1.0)"}

def keywords_in_string(string: str, keywords: list[str]) -> bool:
    words = set(re.findall(r"[a-z]+", string.lower()))
    return any(kw.lower() in words for kw in keywords)

def download_pdf(url: str, dest: str | Path) -> Path:
    """Download the PDF for a single CVF paper.

    Args:
        paper: The paper whose PDF to download.
        download_path: Path to save the PDF in.

    Returns:
        The :class:`Path` of the saved PDF file.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return dest

    response = requests.get(url, headers=_HTTP_HEADERS, timeout=60)
    response.raise_for_status()

    tmp = dest.with_suffix(".tmp")
    try:
        tmp.write_bytes(response.content)
        tmp.rename(dest)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise

    return dest