from __future__ import annotations

from pydantic import BaseModel


class DatasetUsage(BaseModel):
    dataset_name: str
    dataset_version: str | None
    source_title: str | None
    source_first_author: str | None
    aliases: list[str]
    # Free-form string to accommodate "other: <describe>" values.
    purpose: str
    split: str | None
    modifications: bool
    modification_details: str | None
    modification_evidence: str | None
    original_size: str | None
    used_size: str | None
    source_section: str
    notes: str | None


class UsageExtractionResult(BaseModel):
    dataset_usages: list[DatasetUsage]
