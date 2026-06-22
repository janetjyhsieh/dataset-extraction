from __future__ import annotations

import logging
import urllib.error
import urllib.parse
import urllib.request

from dataset_extraction.clients.foundry import DEFAULT_MODEL, FoundryClient

logger = logging.getLogger(__name__)

from .webpage import WebsiteExtractionResult

PROMPT = """\
You are a research data assistant. Your job is to determine how a dataset published alongside \
a research paper can be accessed.

You have been given a landing page URL for the paper or its datasets. Explore it thoroughly: \
follow links to GitHub repositories, README files, LICENSE files, dataset hosting pages \
(e.g. HuggingFace, Zenodo, Figshare, Google Drive), and any linked download instructions. \
Stop exploring a branch once you have confirmed or ruled out the relevant information.

You will be given user inputs in this format:
The paper is: PAPER_NAME
Landing page: LANDING_PAGE_URL
The datasets introduced in the paper are:
DATASET_NAMES

For each dataset, determine:

1. WEBSITE STATUS
   - Did the landing page load successfully?
   - If not, record the error.

2. LICENSE
   - What license governs the DATA (not the accompanying code)?
   - A code license (e.g. MIT or Apache-2.0 on a GitHub repo) does NOT count unless the \
paper or README explicitly states it also covers the dataset.
   - Informal phrases such as "for research use only" or "available upon request" are NOT \
licenses — record them in `usage_agreement` instead.
   - If no formal license is found, use null.

3. USAGE AGREEMENT
   - Are there any terms, access conditions, or usage restrictions the user must accept? \
(e.g. "non-commercial use only", "requires signing a data use agreement", \
"registration required").
   - null if none are stated.

4. AVAILABILITY
   - "open access": dataset can be downloaded freely without registration or approval.
   - "restricted": access requires registration, approval, or a signed agreement.
   - "unavailable": the dataset is not publicly released, the download link is broken, \
or no download path exists.

IMPORTANT:
- Do not fabricate answers. If you cannot verify a field from the pages you fetched, use null.
- For every non-null field, record the URL where you found the evidence and a verbatim quote. \
Unrelated details within a quote may be omitted with [...].
- You MUST output exactly one entry in `datasets_info` per dataset listed above, in the same \
order. The `dataset_name` field must be copied exactly as written above.
- When you have gathered all available information, you MUST call the `extract_result` tool \
to submit your final answer. Do not return JSON as plain text.
"""

_FETCH_TOOL = {
    "type": "function",
    "name": "fetch_webpage",
    "description": (
        "Fetch the text content of a webpage. Use this to read landing pages, "
        "GitHub READMEs, LICENSE files, and dataset hosting pages. "
        "Do not use for PDFs, ZIPs, or other binary file types."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The URL to fetch."},
        },
        "required": ["url"],
        "additionalProperties": False,
    },
    "strict": True,
}


def _normalize_url(url: str) -> str:
    """Percent-encode non-ASCII characters in URL path/query so urllib can send it."""
    p = urllib.parse.urlparse(url)
    return urllib.parse.urlunparse(p._replace(
        path=urllib.parse.quote(p.path, safe="/:@!$&'()*+,;=~"),
        query=urllib.parse.quote(p.query, safe="=&+%"),
    ))


def _fetch_url(args: dict) -> str:
    url = _normalize_url(args["url"])
    if url.lower().endswith((".pdf", ".zip", ".tar", ".gz", ".tar.gz")):
        return "Error: cannot fetch binary file types with this tool."
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; dataset-extraction/1.0)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read(1 * 1024 * 1024 + 1)
            if len(content) > 1 * 1024 * 1024:
                return "Error: response exceeds 1 MB limit."
            return content.decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        return f"Fetch failed: {e}"


def _normalize(s: str) -> str:
    return s.lower().strip()


def _validate_and_fix(
    result: WebsiteExtractionResult, dataset_names: list[str]
) -> tuple[list, list[int]]:
    """Return (matched_infos, matched_indices) for entries whose dataset_name matches a canonical name."""
    canonical = {_normalize(n): (i, n) for i, n in enumerate(dataset_names)}
    matched_infos = []
    matched_indices = []
    for info in result.datasets_info:
        match = canonical.get(_normalize(info.dataset_name))
        if match is not None:
            idx, exact = match
            info.dataset_name = exact
            matched_infos.append(info)
            matched_indices.append(idx)
    return matched_infos, matched_indices


def extract_webpage(
    url: str,
    paper_title: str,
    dataset_names: list[str],
    model: str = DEFAULT_MODEL,
) -> tuple[WebsiteExtractionResult, list[int]]:
    client = FoundryClient(model=model)

    prompt = (
        PROMPT
        .replace("PAPER_NAME", paper_title)
        .replace("LANDING_PAGE_URL", url)
        .replace("DATASET_NAMES", "\n".join(f"- {d}" for d in dataset_names))
    )

    result = client.run_agent(
        prompt=prompt,
        tools=[_FETCH_TOOL],
        tool_handlers={"fetch_webpage": _fetch_url},
        output_schema=WebsiteExtractionResult.model_json_schema(),
        max_tool_calls=6,
    )
    website_result = WebsiteExtractionResult.model_validate(result)
    matched_infos, matched_indices = _validate_and_fix(website_result, dataset_names)
    if not matched_infos:
        msg = f"No dataset names matched for {url!r}. Expected: {dataset_names}."
        logger.warning(msg)
    if len(matched_infos) < len(dataset_names):
        unmatched = [n for i, n in enumerate(dataset_names) if i not in matched_indices]
        logger.warning("Partial match (%d/%d) for %r — no info for: %s", len(matched_info), len(dataset_names), url, unmatched)
    website_result.datasets_info = matched_infos
    return website_result, matched_indices
