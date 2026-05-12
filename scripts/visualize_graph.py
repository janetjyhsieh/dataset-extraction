"""Render the dataset provenance graph as an interactive HTML file.

Usage:
    python scripts/visualize_graph.py --working-dir papers/
    python scripts/visualize_graph.py --working-dir papers/ --output out/graph.html
"""

import argparse
from pathlib import Path

from dataset_extraction.state.graph import Nodes
from dataset_extraction.visualize.graph import visualize


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--working-dir", required=True, help="Directory containing state/graph.json")
    parser.add_argument("--output", default=None, help="Output HTML path (default: <working-dir>/graph.html)")
    args = parser.parse_args()

    working_dir = Path(args.working_dir)
    output_path = Path(args.output) if args.output else working_dir / "graph.html"

    nodes = Nodes(working_dir / "state" / "graph.json")
    output = visualize(nodes, output_path)
    print(f"Graph written to {output}  ({len(nodes)} node(s))")


if __name__ == "__main__":
    main()
