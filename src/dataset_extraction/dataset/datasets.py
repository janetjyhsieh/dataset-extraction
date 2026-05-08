from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class DatasetType(str, Enum):
    original = "original"
    derived = "derived"
    mixed = "mixed"


class SourcePaper(BaseModel):
    bibliographic_string: str | None
    title: str
    first_author: str
    relevance_reason: str


class DatasetSource(BaseModel):
    source_dataset_name: str
    source_paper: SourcePaper
    source_quote: str
    filtering_and_transformation: str


class Dataset(BaseModel):
    name: str
    download_url: str | None
    domain: str | None
    size: str | None
    type: DatasetType
    new_raw_data_collected: bool
    raw_data_collection_method: str | None
    creation_detail: str
    sources: list[DatasetSource]


class ExtractionResult(BaseModel):
    paper_title: str
    first_author_name: str
    publishes_new_dataset: bool
    new_datasets: list[Dataset]
