"""Build a networkx DiGraph of dataset paper lineage from state files.

Nodes: papers (canonical titles) that introduce datasets.
Edges: source_paper → derived_paper, meaning the derived paper's datasets
       were built using the source paper's datasets.

Usage:
    python -m dataset_extraction.graph_builder.generate_graph --working-dir papers/faces-small
"""

import argparse
import json
from pathlib import Path

import networkx as nx

from dataset_extraction.state.graph import DatasetPaperNodes, PaperInfoNodes


def build_lineage_graph(working_dir: Path) -> nx.DiGraph:
    """Build a directed lineage graph from DatasetPaperNodes in working_dir/state/.

    An edge (A → B) means paper B's datasets were derived from paper A's datasets.

    Node attributes:
        datasets (list[str]): dataset names introduced by this paper
        source_processed (bool): whether upstream source papers have been discovered
        year (int | None): publication year from PaperInfo
        venue (str | None): publication venue from PaperInfo

    Args:
        working_dir: Directory containing state/dataset_paper_nodes.json and
            state/paper_info_nodes.json

    Returns:
        A directed networkx graph.
    """
    state_dir = Path(working_dir) / "state"
    dataset_paper_db = DatasetPaperNodes(state_dir / "dataset_paper_nodes.json")
    paper_info_db = PaperInfoNodes(state_dir / "paper_info_nodes.json")

    info_by_title = {p.canonical_title: p for p in paper_info_db.all()}

    G = nx.DiGraph()

    papers = dataset_paper_db.all()
    for paper in papers:
        info = info_by_title.get(paper.title)
        G.add_node(
            paper.title,
            datasets=paper.datasets,
            source_processed=paper.source_processed,
            year=info.year if info else None,
            venue=info.venue if info else None,
        )

    for paper in papers:
        for source_title in paper.source_papers_titles:
            if not G.has_node(source_title):
                info = info_by_title.get(source_title)
                G.add_node(
                    source_title,
                    datasets=[],
                    source_processed=False,
                    year=info.year if info else None,
                    venue=info.venue if info else None,
                )
            G.add_edge(source_title, paper.title)

    return G


def _save_graph(G: nx.DiGraph, output: Path) -> None:
    """Save G to a file; format inferred from the file extension.

    Supports .graphml, .gexf, and .json (node-link format).
    GraphML does not support list attributes, so `datasets` is serialized as
    a pipe-separated string in that format.
    """
    if output.suffix == ".graphml":
        H = nx.DiGraph()
        for node, attrs in G.nodes(data=True):
            H.add_node(
                node,
                datasets="|".join(attrs.get("datasets", [])),
                source_processed=attrs.get("source_processed", False),
                year=attrs.get("year") or -1,
                venue=attrs.get("venue") or "",
            )
        H.add_edges_from(G.edges())
        nx.write_graphml(H, output)
    elif output.suffix == ".gexf":
        nx.write_gexf(G, output)
    elif output.suffix == ".json":
        data = nx.node_link_data(G)
        output.write_text(json.dumps(data, indent=2))
    else:
        raise ValueError(f"Unsupported output format: {output.suffix!r} (use .graphml, .gexf, or .json)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--working-dir", required=True, help="Papers directory containing state/")
    args = parser.parse_args()

    working_dir = Path(args.working_dir)
    G = build_lineage_graph(working_dir)

    print(f"Nodes : {G.number_of_nodes()}")
    print(f"Edges : {G.number_of_edges()}")

    roots = sorted(n for n in G.nodes if G.in_degree(n) == 0)
    print(f"Roots (no upstream sources): {len(roots)}")
    for r in roots:
        datasets = G.nodes[r].get("datasets", [])
        print(f"  {r!r}  →  {datasets}")

    out = working_dir / "graph.json"
    _save_graph(G, out)
    print(f"Saved to {out}")


if __name__ == "__main__":
    main()
