from pathlib import Path
from typing import Generic, TypeVar
from uuid import uuid4

from pydantic import BaseModel, Field

T = TypeVar("T", bound=BaseModel)


class DatasetJob(BaseModel):
    title: str
    pdf_path: str
    uuid: str = Field(default_factory=lambda: str(uuid4()))


class Queue(Generic[T]):
    """Persistent JSONL-backed job queue for a single Pydantic model type.

    Jobs are appended as newline-delimited JSON. The file is created on first
    use if it does not exist.

    Args:
        model: The Pydantic model class this queue holds.
        path: Path to the JSONL queue file.
    """

    def __init__(self, model: type[T], path: str | Path) -> None:
        self._model = model
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.touch()

    def enqueue(self, job: T) -> None:
        """Validate and append a job to the queue."""
        validated = self._model.model_validate(job.model_dump())
        with open(self._path, "a") as f:
            f.write(validated.model_dump_json() + "\n")

    def peek(self) -> T:
        """Return the first job without removing it.

        Raises:
            IndexError: If the queue is empty.
        """
        jobs = self.all()
        if not jobs:
            raise IndexError("peek at an empty queue")
        return jobs[0]

    def dequeue(self) -> T:
        """Remove and return the first job in the queue.

        Raises:
            IndexError: If the queue is empty.
        """
        jobs = self.all()
        if not jobs:
            raise IndexError("dequeue from an empty queue")
        self._path.write_text(
            "".join(job.model_dump_json() + "\n" for job in jobs[1:])
        )
        return jobs[0]

    def all(self) -> list[T]:
        """Return all jobs currently in the queue."""
        with open(self._path) as f:
            return [self._model.model_validate_json(line) for line in f if line.strip()]

    def clear(self) -> None:
        """Remove all jobs from the queue."""
        self._path.write_text("")

    def __len__(self) -> int:
        with open(self._path) as f:
            return sum(1 for line in f if line.strip())
