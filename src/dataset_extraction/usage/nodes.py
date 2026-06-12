from __future__ import annotations

from pathlib import Path

from tinydb import Query, TinyDB

from .usages import DatasetUsage


class UsageNode(DatasetUsage):
    paper_title: str  # paper that used this dataset


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
        """Upsert a usage node keyed by (paper_title, dataset_name, dataset_version, dataset_variant)."""
        Q = Query()
        condition = (
            (Q.paper_title == usage.paper_title)
            & (Q.dataset_name == usage.dataset_name)
            & (Q.dataset_version == usage.dataset_version)
            & (Q.dataset_variant == usage.dataset_variant)
        )
        self._table.upsert(usage.model_dump(mode="json"), condition)

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
