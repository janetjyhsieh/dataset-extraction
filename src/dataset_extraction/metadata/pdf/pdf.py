from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class Evidence(BaseModel):
    years_data: str | None = Field(description="Verbatim supporting quote for years_data, or null.")
    license: str | None = Field(description="Verbatim supporting quote for license, or null.")
    geographic_sourcing: str | None = Field(description="Verbatim supporting quote for continents/countries, or null.")
    number_of_rows: str | None = Field(description="Verbatim supporting quote for number_of_rows, or null.")
    protected_attributes: str | None = Field(description="Verbatim supporting quote for protected_attributes, or null.")


class DatasetMetadata(BaseModel):
    official_dataset_name: str = Field(description="Official dataset name as introduced, including version if a specific version is identified.")
    descriptions: str | None = Field(description="3–6 sentence free-text field covering, where determinable: (1) aim/purpose of the dataset; (2) high-level description of available features; (3) labeling procedure for annotated attributes, with attention to sensitive ones; (4) the envisioned ML task. Note any aspect that is unspecified rather than fabricating it.")
    years_data: str | None = Field(description="Temporal coverage of the data content ('social realities'): a single year (e.g. '1994'), a continuous span (e.g. '1994-1996'), or semicolon-separated non-contiguous years (e.g. '1994; 1997'). null if not applicable (e.g. synthetic data with no temporal referent).")
    data_license: str | None = Field(description="The license under which the dataset is made available, named exactly as stated (e.g. 'CC-BY-4.0'). null if no formal license is found anywhere in the paper.")
    continents: list[str] | None = Field(description="Two-letter continent codes (AF, AN, AS, EU, NA, OC, SA) where the data is sourced. null if not applicable (e.g. synthetic) or not reported.")
    countries: list[str] | str | None = Field(description="ISO 3166-1 alpha-3 codes (e.g. ['USA', 'GBR']) where the data is sourced; the string 'not applicable' if the concept does not apply (e.g. synthetic data); or null if the concept applies but no country is reported.")
    number_of_rows: str | None = Field(description="Number of entries/observations in the dataset, with the unit reported by the authors, summed across splits (e.g. '50,000 images', '~1.2M tokens').")
    attributes: list[str] | str | None = Field(description="Labeled attributes describing each subject or entity (e.g. per-item attributes of a facial dataset). If the set is very large, a faithful summary string with total count is acceptable. null if none.")
    protected_attributes: list[str] | None = Field(description="Attributes the AUTHORS themselves explicitly designate as protected, sensitive, or used for fairness/bias analysis. Do not infer from external frameworks. null if the authors report none.")
    other_annotations: list[str] | None = Field(description="Annotation types OTHER than the per-subject attribute set — e.g. facial landmarks, bounding boxes, identity labels, segmentation masks, captions, or task/target labels — and their format. null if there are none beyond `attributes`.")
    evidence: Evidence


class PdfExtractionResult(BaseModel):
    paper_title: str = Field(description="Full paper title.")
    first_author_name: str = Field(description="Last, First — use the first name appearing in the author list.")
    project_page: str | None = Field(description="URL to the project web page as reported in the paper; prefer the official project/landing page if several links are given. null if no public release URL is reported.")
    documents_dataset: bool = Field(description="True if the paper introduces, constructs, curates, or makes available a dataset as a central artifact. False if no qualifying dataset is documented.")
    datasets: list[DatasetMetadata] = Field(description="One entry per distinct qualifying dataset. Empty array if documents_dataset is false.")

    @field_validator("project_page", mode="before")
    @classmethod
    def strip_trailing_periods(cls, v):
        if isinstance(v, str):
            return v.rstrip(".")
        return v
