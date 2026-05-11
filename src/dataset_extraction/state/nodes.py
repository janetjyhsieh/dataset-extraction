from dataset_extraction.dataset.datasets import Dataset


# Inheriting from a Pydantic BaseModel subclass produces a valid Pydantic model,
# so all serialization (model_dump, model_dump_json, model_validate) works as normal.
class DatasetNode(Dataset):
    source_processed: bool = False
    paper_title: str | None = None
