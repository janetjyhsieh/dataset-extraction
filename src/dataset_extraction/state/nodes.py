import uuid

from pydantic import model_validator

from dataset_extraction.dataset.datasets import Dataset
from dataset_extraction.metadata.metadata import DatasetMetadata
from dataset_extraction.usage.usages import DatasetUsage

_DATASET_NS = uuid.UUID("b4e9a3c1-5d7f-4e2b-8a6c-3f1d9e0b2a4c")
_METADATA_NS = uuid.UUID("a1c3e5b7-2d4f-4a6e-9b8c-7f0e1d3c5a2b")


# Inheriting from a Pydantic BaseModel subclass produces a valid Pydantic model,
# so all serialization (model_dump, model_dump_json, model_validate) works as normal.
class DatasetNode(Dataset):
    paper_title: str | None = None
    dataset_id: str = ""

    @model_validator(mode="after")
    def _assign_id(self) -> "DatasetNode":
        if not self.dataset_id:
            key = f"{self.paper_title or ''}::{self.name}"
            self.dataset_id = str(uuid.uuid5(_DATASET_NS, key))
        return self


class UsageNode(DatasetUsage):
    paper_title: str  # paper that used this dataset


class MetadataNode(DatasetMetadata):
    paper_title: str
    dataset_id: str = ""

    @model_validator(mode="after")
    def _assign_id(self) -> "MetadataNode":
        if not self.dataset_id:
            key = f"{self.paper_title}::{self.dataset_name}"
            self.dataset_id = str(uuid.uuid5(_METADATA_NS, key))
        return self
