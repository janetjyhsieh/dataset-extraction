import argparse
import os
from pathlib import Path

import openreview

from dataset_extraction.log import setup_logging
from dataset_extraction.literature.source import LiteratureSource
from dataset_extraction.literature.xlsx import XslxSource
from dataset_extraction.literature.openreview import OpenReviewSource
from dataset_extraction.literature.cvf import CvfSource

_ANNOTATIONS_PATH = Path(__file__).parents[4] / "gdrive" / "annotations.xlsx"

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download conference papers.",
    )
    parser.add_argument(
        "--source",
        required=True,
        choices=['xslx', 'openreview', 'cvf']
    )
    parser.add_argument(
        "--venue",
        required=True,
        help="CVF venue acronym, e.g. CVPR, ICCV, WACV",
    )
    parser.add_argument(
        "--year",
        type=int,
        required=True,
        help="Venue year, e.g. 2023",
    )
    parser.add_argument(
        "--paper-sources",
        nargs="+",
        metavar="SOURCE",
        dest="paper_sources",
        default=None,
        help=(
            "Explicit paper_source values to filter by, e.g. FAccT-2022 Fabris_2021. "
            "Defaults to '<venue>-<year>'."
        ),
    )
    parser.add_argument(
        "--working-dir",
        default="papers",
        help="Root directory for output (default: papers)",
    )
    parser.add_argument(
        "--keywords",
        nargs="+",
        default=None,
        help="Only include papers whose title contains any keyword (case-insensitive OR match)",
    )
    parser.add_argument(
        "--annotations",
        default=str(_ANNOTATIONS_PATH),
        help=f"Path to annotations.xlsx (default: {_ANNOTATIONS_PATH})",
    )
    parser.add_argument(
        "--baseurl",
        default="https://api2.openreview.net",
        help="OpenReview API base URL (default: v2 API)",
    )
    args = parser.parse_args()

    working_dir = Path(args.working_dir)
    setup_logging(working_dir / "logs")
    index_path = working_dir / "index.jsonl"

    lit_source: LiteratureSource = None
    new_papers = []
    if args.source == "xslx":
        paper_sources = args.paper_sources
        if not paper_sources:
            paper_sources = [f"{args.venue}-{args.year}"]
        lit_source = XslxSource(working_dir, index_path, args.annotations)
        new_papers = lit_source.get_papers(paper_sources, args.keywords)
    elif args.source == "openreview":
        client = openreview.api.OpenReviewClient(
            baseurl=args.baseurl,
            username=os.environ.get("OPENREVIEW_USERNAME") or None,
            password=os.environ.get("OPENREVIEW_PASSWORD") or None,
        )
        lit_source = OpenReviewSource(working_dir, index_path, client)
        new_papers = lit_source.get_papers(venue=args.venue, year=args.year, keywords=args.keywords)
    elif args.source == "cvf":
        lit_source = CvfSource(working_dir, index_path)
        new_papers = lit_source.get_papers(venue=args.venue, year=args.year, keywords=args.keywords)
    else:
        raise NotImplementedError(f"Corpus source {args.source!r} not implemented")
    
    lit_source.download_and_save_papers(new_papers)


if __name__ == "__main__":
    main()
