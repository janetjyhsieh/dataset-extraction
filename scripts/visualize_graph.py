"""Render the dataset provenance graph as an interactive HTML file.

Usage:
    python scripts/visualize_graph.py --working-dir papers/cvpr
    python scripts/visualize_graph.py --working-dir papers/cvpr --output out/graph.html
    python scripts/visualize_graph.py --working-dir papers/cvpr --usages papers/cvpr/state/usages.json
"""

import argparse
from pathlib import Path

from dataset_extraction.state.graph import Nodes
from dataset_extraction.visualize.graph import visualize


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--working-dir", required=True, help="Directory containing state/graph.json")
    parser.add_argument("--output", default=None, help="Output HTML path (default: <working-dir>/graph.html)")
    parser.add_argument("--usages", default=None, help="Path to usages TinyDB JSON to overlay usage edges")
    args = parser.parse_args()

    working_dir = Path(args.working_dir)
    output_path = Path(args.output) if args.output else working_dir / "graph.html"

    nodes = Nodes(working_dir / "state" / "graph.json")
    output = visualize(nodes, output_path, usages_path=args.usages)
    print(f"Graph written to {output}  ({len(nodes)} node(s))")


if __name__ == "__main__":
    main()
