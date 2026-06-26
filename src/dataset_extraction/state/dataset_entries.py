import uuid

from pydantic import model_validator

from dataset_extraction.fairground.metadata.metadata import DatasetMetadata
from dataset_extraction.fairground.webpage.webpage import DatasetWebsiteInfo


_DATASET_NS = uuid.UUID("b4e9a3c1-5d7f-4e2b-8a6c-3f1d9e0b2a4c")


# Inheriting from a Pydantic BaseModel subclass produces a valid Pydantic model,
# so all serialization (model_dump, model_dump_json, model_validate) works as normal.
class MetadataNode(DatasetMetadata):
    paper_title: str | None = None
    dataset_id: str = ""

    @model_validator(mode="after")
    def _assign_id(self) -> "DatasetNode":
        if not self.dataset_id:
            key = f"{self.paper_title or ''}::{self.official_dataset_name}"
            self.dataset_id = str(uuid.uuid5(_DATASET_NS, key))
        return self

class DatasetWebsiteNode(DatasetWebsiteInfo):
    paper_title: str | None = None
    dataset_id: str = ""