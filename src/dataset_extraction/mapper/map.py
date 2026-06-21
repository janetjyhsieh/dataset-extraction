from __future__ import annotations

from pydantic import BaseModel, Field

from dataset_extraction.clients.foundry import DEFAULT_MODEL, FoundryClient


PROMPT = """
You are matching a dataset reference to its source.

A downstream paper used a dataset it calls: "USAGE_DATASET"
Context from the downstream paper (may be empty):
"USAGE_SUMMARY"

This dataset was cited to a paper that introduces the following datasets:
PAPER_DATASETS_LIST

Decide which ONE introduced dataset the downstream reference points to.
Match on semantic content (task, domain, modality, construction), not just
name similarity. The downstream name is often an alias, acronym, or rename.

Return JSON only:
{
  "choice": "<dataset_name, or 'NONE', or 'AMBIGUOUS'>",
  "confidence": <0-1>,
  "reasoning": "<one or two sentences>"
}

Use "NONE" if no candidate fits (e.g. likely citation error, or the
reference is to a dataset not in this list).
Use "AMBIGUOUS" if two or more candidates fit roughly equally and the
information given cannot separate them.
"""


class WebsiteExtractionResult(BaseModel):
    choice: str = Field(description="The exact name of the matched dataset, or 'NONE' if no candidate fits, or 'AMBIGUOUS' if two or more candidates fit equally.")
    confidence: float = Field(description="Confidence score between 0 and 1.")
    reasoning: str = Field(description="One or two sentences explaining the match decision.")


def map_datasets(
    usage_dataset: dict,
    official_datasets: list[dict],
    model: str = DEFAULT_MODEL,
) -> WebsiteExtractionResult:
    dataset_list = "\n".join(
        f"[{d['name']}]: {d.get('description', '')}"
        for d in official_datasets
    )
    prompt = (
        PROMPT
        .replace("USAGE_DATASET", usage_dataset["name"])
        .replace("USAGE_SUMMARY", usage_dataset.get("description", ""))
        .replace("PAPER_DATASETS_LIST", dataset_list)
    )
    client = FoundryClient(model=model)
    result = client.send_text_structured(prompt, WebsiteExtractionResult.model_json_schema())
    return WebsiteExtractionResult.model_validate(result)
