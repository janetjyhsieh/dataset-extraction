from __future__ import annotations

from pathlib import Path
from typing import Generic, Type, TypeVar

from pydantic import BaseModel
from tinydb import Query, TinyDB

from dataset_extraction.state.nodes import DatasetNode, UsageNode
from dataset_extraction.state.paper import DatasetPaperNode, PaperInfo

_T = TypeVar("_T", bound=BaseModel)


class _NodeStore(Generic[_T]):
    """TinyDB-backed store for a single Pydantic model type, keyed by one string field."""

    def __init__(self, db_path: str | Path, model: Type[_T], key_field: str) -> None:
        self._db = TinyDB(db_path)
        self._model = model
        self._key_field = key_field

    def _q(self, value: str):
        return getattr(Query(), self._key_field) == value

    def _key(self, node: _T) -> str:
        return getattr(node, self._key_field)

    def upsert(self, node: _T) -> int:
        """Insert or update a node and return its TinyDB document ID."""
        doc_id = self._db.upsert(node.model_dump(mode="json"), self._q(self._key(node)))
        return doc_id[0]

    def insert(self, node: _T) -> int:
        """Insert a new node and return its TinyDB document ID.

        Raises:
            KeyError: If a node with the same key already exists.
        """
        key = self._key(node)
        if self._db.contains(self._q(key)):
            raise KeyError(f"{self._key_field}={key!r} already exists")
        return self._db.insert(node.model_dump(mode="json"))

    def update(self, node: _T) -> None:
        """Update an existing node in place.

        Raises:
            KeyError: If no node with the given key exists.
        """
        key = self._key(node)
        if not self._db.contains(self._q(key)):
            raise KeyError(f"{self._key_field}={key!r} not found")
        self._db.update(node.model_dump(mode="json"), self._q(key))

    def get(self, key: str) -> _T | None:
        """Return the node with the given key, or None if not found."""
        results = self._db.search(self._q(key))
        if not results:
            return None
        return self._model.model_validate(results[0])

    def all(self) -> list[_T]:
        """Return all stored nodes."""
        return [self._model.model_validate(doc) for doc in self._db.all()]

    def exists(self, key: str) -> bool:
        """Return True if a node with the given key is stored."""
        return self._db.contains(self._q(key))

    def remove(self, key: str) -> None:
        """Delete the node with the given key if it exists."""
        self._db.remove(self._q(key))

    def __len__(self) -> int:
        return len(self._db)


class DatasetNodes(_NodeStore[DatasetNode]):
    """Persistent store for dataset nodes, keyed by dataset_id."""

    def __init__(self, db_path: str | Path) -> None:
        super().__init__(db_path, DatasetNode, "dataset_id")

    def get_by_name(self, name: str) -> list[DatasetNode]:
        """Return all nodes with the given dataset name."""
        results = self._db.search(Query().name == name)
        return [DatasetNode.model_validate(doc) for doc in results]


class DatasetPaperNodes(_NodeStore[DatasetPaperNode]):
    """Persistent store for dataset-paper nodes, keyed by canonical title."""

    def __init__(self, db_path: str | Path) -> None:
        super().__init__(db_path, DatasetPaperNode, "title")

class PaperInfoNodes(_NodeStore[PaperInfo]):
    """Persistent store for paper-info nodes, keyed by canonical title."""

    def __init__(self, db_path: str | Path) -> None:
        super().__init__(db_path, PaperInfo, "canonical_title")

class UsageNodes:
    """Persistent store for dataset usage nodes backed by TinyDB.

    Uses two internal tables: ``usages`` (one record per paper×dataset pair)
    and ``processed_papers`` (tracks which papers have been fully extracted,
    including those with zero usages).

    Args:
        db_path: Path to the TinyDB JSON file. Created if it does not exist.
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db = TinyDB(db_path)
        self._table = self._db.table("usages")
        self._processed = self._db.table("processed_papers")

    def add(self, usage: UsageNode) -> None:
        """Upsert a usage node keyed by (paper_title, dataset_name)."""
        Q = Query()
        self._table.upsert(
            usage.model_dump(mode="json"),
            (Q.paper_title == usage.paper_title) & (Q.dataset_name == usage.dataset_name),
        )

    def mark_processed(self, paper_title: str) -> None:
        """Record that a paper has been fully usage-extracted (even if zero usages)."""
        Q = Query()
        if not self._processed.contains(Q.paper_title == paper_title):
            self._processed.insert({"paper_title": paper_title})

    def is_processed(self, paper_title: str) -> bool:
        """Return True if this paper has already been usage-extracted."""
        return self._processed.contains(Query().paper_title == paper_title)

    def all(self) -> list[UsageNode]:
        """Return all stored usage nodes."""
        return [UsageNode.model_validate(doc) for doc in self._table.all()]

    def __len__(self) -> int:
        return len(self._table)
