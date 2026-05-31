from __future__ import annotations

from pydantic import BaseModel


class SourcePaper(BaseModel):
    bibliographic_string: str | None
    title: str | None
    first_author: str | None
    relevance_reason: str


class DatasetUsage(BaseModel):
    dataset_name: str
    dataset_version: str | None
    dataset_variant: str | None
    task: str
    subtask: str | None
    source_paper: SourcePaper
    aliases: list[str]
    dataset_task_summary: str
    modifications: bool
    modification_details: str | None
    modification_evidence: str | None
    source_section: str
    notes: str | None


class UsageExtractionResult(BaseModel):
    dataset_usages: list[DatasetUsage]
