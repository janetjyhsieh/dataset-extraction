from __future__ import annotations

from pydantic import BaseModel


class DatasetMetadata(BaseModel):
    dataset_name: str
    demographic_info_available: bool


class MetadataExtractionResult(BaseModel):
    paper_title: str
    datasets: list[DatasetMetadata]
