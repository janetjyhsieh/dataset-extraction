import argparse
import json
from pathlib import Path

from dataset_extraction.state.queue import DatasetJob, Queue


def enqueue_from_directory(working_dir: str | Path, queue: Queue[DatasetJob]) -> None:
    """Create and enqueue a job for every PDF in ``working_dir/pdfs/``.

    Titles are resolved from ``working_dir/index.jsonl`` when available,
    falling back to the PDF filename stem.

    Args:
        working_dir: Conference paper directory containing ``pdfs/`` and
            optionally ``index.jsonl``.
        queue: The queue to add jobs to.
    """
    working_dir = Path(working_dir)

    title_by_id: dict[str, str] = {}
    index_path = working_dir / "index.jsonl"
    if index_path.exists():
        with open(index_path) as f:
            for line in f:
                if line.strip():
                    record = json.loads(line)
                    title_by_id[record["id"]] = record["title"]

    pdf_dir = working_dir / "pdfs"
    enqueued = 0
    for paper_id, title in title_by_id.items():
        pdf_path = pdf_dir / f"{paper_id}.pdf"
        if not pdf_path.exists():
            print(f"Skipping {paper_id}: PDF not found")
            continue
        queue.enqueue(DatasetJob(title=title, pdf_path=str(pdf_path)))
        print(f"Enqueued: {title}")
        enqueued += 1

    print(f"\nAdded {enqueued} job(s) to queue (total: {len(queue)})")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Populate the dataset processing queue from a paper directory."
    )
    parser.add_argument(
        "--working-dir",
        required=True,
        help="Conference paper directory containing pdfs/ and index.jsonl",
    )
    args = parser.parse_args()

    queue_path = Path(args.working_dir) / "state" / "dataset_queue.jsonl"
    queue: Queue[DatasetJob] = Queue(DatasetJob, queue_path)
    enqueue_from_directory(args.working_dir, queue)


if __name__ == "__main__":
    main()
