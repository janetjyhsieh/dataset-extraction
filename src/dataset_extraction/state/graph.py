from __future__ import annotations

from pathlib import Path

from tinydb import Query, TinyDB

from dataset_extraction.state.nodes import DatasetNode, UsageNode
from dataset_extraction.state.paper import Paper


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


class Papers:
    """Persistent store for paper metadata backed by TinyDB.

    Each entry is a :class:`PaperInfo` model keyed by ``paper_title``.

    Args:
        db_path: Path to the TinyDB JSON file. Created if it does not exist.
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db = TinyDB(db_path)

    def add(self, paper: PaperInfo) -> int:
        """Upsert a paper and return its TinyDB document ID."""
        Q = Query()
        doc_id = self._db.upsert(paper.model_dump(mode="json"), Q.paper_title == paper.paper_title)
        return doc_id[0]

    def get(self, paper_title: str) -> PaperInfo | None:
        """Return the paper with the given title, or None if not found."""
        results = self._db.search(Query().paper_title == paper_title)
        if not results:
            return None
        return PaperInfo.model_validate(results[0])

    def all(self) -> list[PaperInfo]:
        """Return all stored papers."""
        return [PaperInfo.model_validate(doc) for doc in self._db.all()]

    def exists(self, paper_title: str) -> bool:
        """Return True if a paper with the given title is already stored."""
        return self._db.contains(Query().paper_title == paper_title)

    def remove(self, paper_title: str) -> None:
        """Delete the paper with the given title if it exists."""
        self._db.remove(Query().paper_title == paper_title)

    def __len__(self) -> int:
        return len(self._db)
