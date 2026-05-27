"""Render the dataset lineage graph as an interactive HTML file.

Usage:
    python -m dataset_extraction.visualize.graph --working-dir papers/faces-small
    python -m dataset_extraction.visualize.graph --working-dir papers/faces-small --output out/graph.html
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from dataset_extraction.graph_builder.generate_graph import build_lineage_graph
from dataset_extraction.log import setup_logging
from dataset_extraction.visualize.render import render

logger = logging.getLogger("dataset_extraction.visualize.graph")


def visualize(working_dir: str | Path, output_path: str | Path | None = None) -> Path:
    """Build and render the dataset lineage graph for a paper collection.

    Args:
        working_dir: Directory containing state/dataset_paper_nodes.json and
            state/paper_info_nodes.json.
        output_path: Destination HTML file. Defaults to working_dir/graph.html.

    Returns:
        Path to the written HTML file.
    """
    working_dir = Path(working_dir)
    if output_path is None:
        output_path = working_dir / "graph.html"
    G = build_lineage_graph(working_dir)
    return render(G, output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--working-dir", required=True, help="Papers directory containing state/")
    parser.add_argument("--output", default=None, help="Output HTML path (default: working_dir/graph.html)")
    args = parser.parse_args()

    setup_logging(Path(args.working_dir) / "logs")
    output = visualize(args.working_dir, args.output)
    logger.info("Graph written to %s", output)


if __name__ == "__main__":
    main()
