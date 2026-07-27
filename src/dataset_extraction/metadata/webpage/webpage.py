from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class DatasetAvailabilityType(str, Enum):
    open_access = "open access"
    restricted = "restricted"
    unavailable = "unavailable"


class Evidence(BaseModel):
    url: str | None = Field(description="URL of the page where the evidence was found, or null if not from a specific URL.")
    quote: str | None = Field(description="Verbatim quote from the page supporting the field's value. Unrelated details may be omitted with [...]. null if no supporting text was found.")


class WebsiteStatus(BaseModel):
    accessible: bool = Field(description="True if the landing page loaded successfully; false if it returned an error, was blocked, or was unreachable.")
    error: str | None = Field(description="The error message or HTTP status if the page was not accessible, or null if it loaded successfully.")


class DatasetLicense(BaseModel):
    data_license: str | None = Field(description="The license governing the DATASET (not the code), named exactly as stated (e.g. 'CC-BY-4.0', 'MIT'). null if no license is explicitly stated for the data.")
    evidence: Evidence


class DataseUsageAgreement(BaseModel):
    usage_agreement: str | None = Field(description="Any usage agreement, terms of service, or access conditions the user must accept to use the dataset (e.g. 'research use only', 'requires registration'). null if none is stated.")
    evidence: Evidence


class DatasetDownload(BaseModel):
    availability: DatasetAvailabilityType = Field(description="'open access' if the dataset can be downloaded freely without registration; 'restricted' if access requires approval, registration, or a signed agreement; 'unavailable' if the dataset is not publicly released or the link is broken.")
    dataset_download_instruction: str | None = Field(description="How to obtain the dataset — e.g. a direct download URL, a command, or instructions to request access. null if not determinable.")
    evidence: Evidence


class DatasetWebsiteInfo(BaseModel):
    dataset_name: str = Field(description="Name of the dataset as referenced in the paper.")
    dataset_license: DatasetLicense
    usage_agreement: DataseUsageAgreement
    dataset_download: DatasetDownload


class WebsiteExtractionResult(BaseModel):
    url: str = Field(description="The primary landing page URL that was inspected.")
    website_status: WebsiteStatus
    datasets_info: list[DatasetWebsiteInfo] = Field(description="One entry per dataset introduced in the paper, with license, usage agreement, and download availability as found through the landing page.")
