from __future__ import annotations

from pathlib import Path

from dataset_extraction.state.graph import Nodes
from dataset_extraction.visualize.data import (
    _canonical_title_map,
    add_usage_edges,
    build_paper_graph,
    load_usage_pairs,
)
from dataset_extraction.visualize.render import render


def visualize(
    nodes_store: Nodes,
    output_path: str | Path = "graph.html",
    usages_path: str | Path | None = None,
) -> Path:
    """Build and render the provenance graph from a Nodes store.

    If usages_path is provided, usage edges (dotted amber) are overlaid.
    """
    dataset_nodes = nodes_store.all()
    usage_triples = load_usage_pairs(usages_path) if usages_path else []

    extra_titles = [t for src, dst, _ in usage_triples for t in (src, dst)]
    canonical = _canonical_title_map(dataset_nodes, extra_titles=extra_titles)

    G = build_paper_graph(dataset_nodes, canonical=canonical)
    if usage_triples:
        add_usage_edges(G, usage_triples, canonical)

    return render(G, output_path)
