from __future__ import annotations

from pathlib import Path

from tinydb import Query, TinyDB

from dataset_extraction.state.nodes import DatasetNode


# TODO(jy): check implementation
class Nodes:
    """Persistent store for dataset nodes backed by TinyDB.

    Each node represents a published dataset extracted from a paper.
    The dataset's ``name`` field is used as the natural key.

    Args:
        db_path: Path to the TinyDB JSON file. Created if it does not exist.
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db = TinyDB(db_path)

    def add(self, dataset: DatasetNode) -> int:
        """Insert a dataset node and return its TinyDB document ID.

        If a node with the same name already exists it is replaced.

        Args:
            dataset: The dataset to store.

        Returns:
            The TinyDB document ID of the inserted record.
        """
        Q = Query()
        doc_id = self._db.upsert(dataset.model_dump(mode="json"), Q.name == dataset.name)
        return doc_id[0]

    def get(self, name: str) -> DatasetNode | None:
        """Return the dataset node with the given name, or None if not found."""
        results = self._db.search(Query().name == name)
        if not results:
            return None
        return DatasetNode.model_validate(results[0])

    def all(self) -> list[DatasetNode]:
        """Return all stored dataset nodes."""
        return [DatasetNode.model_validate(doc) for doc in self._db.all()]

    def exists(self, name: str) -> bool:
        """Return True if a node with the given name is already stored."""
        return self._db.contains(Query().name == name)

    def remove(self, name: str) -> None:
        """Delete the node with the given name if it exists."""
        self._db.remove(Query().name == name)

    def __len__(self) -> int:
        return len(self._db)
