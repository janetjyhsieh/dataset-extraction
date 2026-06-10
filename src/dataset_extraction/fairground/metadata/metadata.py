from __future__ import annotations

from pydantic import BaseModel


class Evidence(BaseModel):
    years_data: str | None
    license: str | None
    geographic_sourcing: str | None
    number_of_rows: str | None


class DatasetMetadata(BaseModel):
    official_dataset_name: str
    descriptions: str | None
    years_data: str | None
    license: str | None
    continents: list[str] | None
    countries: list[str] | str | None  # list of ISO3 codes, "not applicable", or null
    number_of_rows: str | None
    demographic_info: str | None
    annotations: str | None
    evidence: Evidence


class MetadataExtractionResult(BaseModel):
    paper_title: str
    first_author_name: str
    documents_dataset: bool
    datasets: list[DatasetMetadata]
