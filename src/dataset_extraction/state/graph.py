from __future__ import annotations

from pathlib import Path
from typing import Generic, Type, TypeVar

from pydantic import BaseModel
from tinydb import Query, TinyDB

from dataset_extraction.fairground.webpage.webpage import WebsiteExtractionResult
from dataset_extraction.state.nodes import DatasetNode, MetadataNode
from dataset_extraction.state.paper import DatasetPaperNode, PaperInfo, PdfInfo

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
        null_paper = PaperInfo(
            canonical_title="null",
            pdf_info = PdfInfo(link_found=False, download_success=False)
        )
        if not self.exists(null_paper.canonical_title):
            self.insert(null_paper)

class MetadataNodes(_NodeStore[MetadataNode]):
    """Persistent store for metadata nodes, keyed by dataset_id."""

    def __init__(self, db_path: str | Path) -> None:
        super().__init__(db_path, MetadataNode, "dataset_id")


class WebpageNodes(_NodeStore[WebsiteExtractionResult]):
    """Persistent store for webpage extraction results, keyed by URL."""

    def __init__(self, db_path: str | Path) -> None:
        super().__init__(db_path, WebsiteExtractionResult, "url")
