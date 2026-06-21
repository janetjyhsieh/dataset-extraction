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

_SENTINEL = {"NONE", "AMBIGUOUS"}


class _LLMChoice(BaseModel):
    choice: str = Field(description="The exact name of the matched dataset, or 'NONE' if no candidate fits, or 'AMBIGUOUS' if two or more candidates fit equally.")
    confidence: float = Field(description="Confidence score between 0 and 1.")
    reasoning: str = Field(description="One or two sentences explaining the match decision.")


class MapperExtractionResult(BaseModel):
    choice: str = Field(description="The exact name of the matched dataset, or 'NONE', or 'AMBIGUOUS'.")
    confidence: float = Field(description="Confidence score between 0 and 1.")
    reasoning: str = Field(description="One or two sentences explaining the match decision.")
    dataset_id: str | None = Field(description="dataset_id of the matched MetadataNode, or None if choice is NONE/AMBIGUOUS or unresolvable.")


def map_datasets(
    usage_dataset: dict,
    official_datasets: list[dict],
    model: str = DEFAULT_MODEL,
) -> MapperExtractionResult | None:
    """Match a usage dataset to one of the official datasets.

    Each entry in official_datasets must have "name", "description", and "id" (dataset_id).
    """
    name_to_id = {d["name"]: d["id"] for d in official_datasets}
    valid_names = set(name_to_id)

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

    llm_schema = _LLMChoice.model_json_schema()
    client = FoundryClient(model=model)

    result_dict, response_id = client.send_text_structured(prompt, llm_schema)
    choice = result_dict["choice"]

    if choice not in valid_names and choice not in _SENTINEL:
        valid_list = ", ".join(f'"{n}"' for n in sorted(valid_names))
        followup = (
            f'"{choice}" is not one of the valid dataset names. '
            f"Please choose from: {valid_list}, or use \"NONE\" or \"AMBIGUOUS\"."
        )
        result_dict, _ = client.send_text_structured(followup, llm_schema, previous_response_id=response_id)
        choice = result_dict["choice"]
        if choice not in valid_names and choice not in _SENTINEL:
            return None

    return MapperExtractionResult(
        choice=choice,
        confidence=result_dict["confidence"],
        reasoning=result_dict["reasoning"],
        dataset_id=name_to_id.get(choice),
    )
