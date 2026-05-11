"""Debug script for paper_finder — tests PDF lookup for a given paper title.

Usage:
    python scripts/debug_paper_finder.py "AUNet: Learning Relations Between Action Units for Face Forgery Detection"
    python scripts/debug_paper_finder.py "Some Paper Title" --author "Smith"
"""

import argparse

from dataset_extraction.downloader.paper_finder import (
    _get_s2_paper,
    _pdf_from_external_ids,
    _pdf_from_venue,
    _search_arxiv,
    find_open_access_pdf,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("title", help="Paper title to look up")
    parser.add_argument("--author", default="", help="First author name (optional)")
    args = parser.parse_args()

    print(f"Title:  {args.title}")
    print(f"Author: {args.author or '(not provided)'}")
    print()

    print("--- Semantic Scholar ---")
    paper = _get_s2_paper(args.title, verbose=True)
    print()

    if paper:
        external_ids = paper.get("externalIds") or {}
        year = paper.get("year")

        print("--- External IDs (ArXiv/ACL) ---")
        result = _pdf_from_external_ids(external_ids, verbose=True)
        print(f"  Result: {result}")
        print()

        if year:
            print(f"--- Venue routing (year={year}) ---")
            result = _pdf_from_venue(external_ids, year, args.title, verbose=True)
            print(f"  Result: {result}")
            print()

    print("--- arXiv fallback ---")
    _search_arxiv(args.title, verbose=True)
    print()

    print("--- find_open_access_pdf ---")
    final = find_open_access_pdf(args.title, args.author, verbose=True)
    print(f"Result: {final}")


if __name__ == "__main__":
    main()
