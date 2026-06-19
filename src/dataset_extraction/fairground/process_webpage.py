"""Extract dataset webpage info for all papers in the dataset_paper_nodes database.

For each paper, loads its datasets from metadata_nodes, groups them by dataset_page
URL, and calls the webpage extractor once per unique URL. Results are stored in
webpage_nodes.json and skipped on subsequent runs.

Usage:
    python -m dataset_extraction.fairground.process_webpage --working-dir papers/
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from dataset_extraction.fairground.webpage.extractor import extract_webpage
from dataset_extraction.log import setup_logging
from dataset_extraction.state.graph import DatasetPaperNodes, MetadataNodes, WebpageNodes

logger = logging.getLogger("dataset_extraction.fairground.process_webpage")


def process_all(
    dataset_paper_db: DatasetPaperNodes,
    metadata_db: MetadataNodes,
    webpage_db: WebpageNodes,
) -> None:
    papers = dataset_paper_db.all()
    logger.info("Processing %d dataset paper(s)", len(papers))

    for paper in papers:
        metadata_nodes = [
            node
            for dataset_id in paper.datasets
            if (node := metadata_db.get(dataset_id)) is not None
        ]

        if not metadata_nodes:
            logger.debug("No metadata nodes found for paper: %s", paper.title)
            continue

        # Group dataset names by their dataset_page URL; skip datasets with no URL.
        url_to_names: dict[str, list[str]] = {}
        for node in metadata_nodes:
            if node.dataset_page:
                url_to_names.setdefault(node.dataset_page, []).append(node.official_dataset_name)

        if not url_to_names:
            logger.debug("No dataset_page URLs for paper: %s", paper.title)
            continue

        for url, dataset_names in url_to_names.items():
            if webpage_db.exists(url):
                logger.debug("Skipping already-processed URL: %s", url)
                continue

            logger.info("Extracting webpage for '%s' — %s", paper.title, url)
            try:
                result = extract_webpage(
                    url=url,
                    paper_title=paper.title,
                    dataset_names=dataset_names,
                )
            except Exception:
                logger.exception("Webpage extraction failed for %s", url)
                continue

            webpage_db.upsert(result)
            logger.info("Saved webpage result for %s", url)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--working-dir", required=True, help="Directory containing fg/databases/")
    args = parser.parse_args()

    working_dir = Path(args.working_dir)
    databases_dir = working_dir / "fg" / "databases"
    databases_dir.mkdir(parents=True, exist_ok=True)

    setup_logging(working_dir / "fg" / "logs")

    dataset_paper_db = DatasetPaperNodes(databases_dir / "dataset_paper_nodes.json")
    metadata_db = MetadataNodes(databases_dir / "metadata_nodes.json")
    webpage_db = WebpageNodes(databases_dir / "webpage_nodes.json")

    process_all(dataset_paper_db, metadata_db, webpage_db)
    logger.info("Done.")


if __name__ == "__main__":
    main()
