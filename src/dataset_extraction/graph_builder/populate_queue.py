import argparse
import json
from pathlib import Path

from dataset_extraction.state.graph import DatasetPaperNodes
from dataset_extraction.state.paper import DatasetPaperNode, canonicalize_title
from dataset_extraction.state.paper import PdfInfo, PdfDownloadSource
from dataset_extraction.state.queue import DatasetJob, Queue


def enqueue_from_directory(
    working_dir: str | Path,
    queue: Queue[DatasetJob],
    paper_nodes: DatasetPaperNodes,
) -> None:
    """Create a DatasetPaperNode and enqueue a job for every PDF in ``working_dir/pdfs/``.

    Titles are resolved from ``working_dir/index.jsonl`` when available,
    falling back to the PDF filename stem.

    Args:
        working_dir: Conference paper directory containing ``pdfs/`` and
            optionally ``index.jsonl``.
        queue: The queue to add jobs to.
        paper_nodes: Store where a DatasetPaperNode is saved for each paper
            before its job is enqueued.
    """
    working_dir = Path(working_dir)

    records_by_id: dict[str, dict] = {}
    index_path = working_dir / "index.jsonl"
    if index_path.exists():
        with open(index_path) as f:
            for line in f:
                if line.strip():
                    record = json.loads(line)
                    records_by_id[record["id"]] = record

    pdf_dir = working_dir / "pdfs"
    enqueued = 0
    for paper_id, record in records_by_id.items():
        pdf_path = pdf_dir / f"{paper_id}.pdf"
        if not pdf_path.exists():
            print(f"Skipping {paper_id}: PDF not found")
            continue

        title = record["title"]
        canonical = canonicalize_title(title)
        node = DatasetPaperNode(
            raw_title=title,
            canonical_title=canonical,
            year=record.get("year"),
            venue=record.get("venue"),
            pdf_info=PdfInfo(
                link_found=True,
                download_success=True,
                pdf_download_source=PdfDownloadSource.direct,
                pdf_file_path=str(pdf_path),
                #TODO: add url
            ),
        )
        paper_nodes.insert(node)
        queue.enqueue(DatasetJob(title=canonical, pdf_path=str(pdf_path)))
        print(f"Enqueued: {title} (year={record.get('year')}, venue={record.get('venue')})")
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

    working_dir = Path(args.working_dir)
    queue_path = working_dir / "state" / "dataset_queue.jsonl"
    paper_nodes_path = working_dir / "state" / "paper_nodes.json"
    queue: Queue[DatasetJob] = Queue(DatasetJob, queue_path)
    paper_nodes = DatasetPaperNodes(paper_nodes_path)
    enqueue_from_directory(working_dir, queue, paper_nodes)


if __name__ == "__main__":
    main()
