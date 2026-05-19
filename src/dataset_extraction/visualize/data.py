from __future__ import annotations

import json
from pathlib import Path

import networkx as nx

from dataset_extraction.state.nodes import DatasetNode


def _canonical_title_map(
    nodes: list[DatasetNode],
    extra_titles: list[str] | None = None,
) -> dict[str, str]:
    """Return a mapping from normalized title → display title.

    Known papers (node.paper_title) take priority; external source titles fill
    in the rest; extra_titles (e.g. from usage data) are added last.
    """
    canonical: dict[str, str] = {}
    for node in nodes:
        if node.paper_title:
            key = node.paper_title.strip().lower()
            if key not in canonical:
                canonical[key] = node.paper_title.strip()
    for node in nodes:
        if not node.paper_title:
            continue
        for source in node.sources:
            t = source.source_paper.title
            if t:
                key = t.strip().lower()
                if key not in canonical:
                    canonical[key] = t.strip()
    for t in (extra_titles or []):
        if t:
            key = t.strip().lower()
            if key not in canonical:
                canonical[key] = t.strip()
    return canonical


def build_paper_graph(
    nodes: list[DatasetNode],
    canonical: dict[str, str] | None = None,
) -> nx.DiGraph:
    """Build a paper-level provenance DiGraph from dataset nodes.

    Each graph node is a paper (keyed by title). An edge A → B means a dataset
    in paper B was derived from a dataset introduced in paper A.
    """
    G = nx.DiGraph()
    if canonical is None:
        canonical = _canonical_title_map(nodes)

    def canon(title: str) -> str:
        return canonical.get(title.strip().lower(), title.strip())

    dataset_counts: dict[str, int] = {}
    dataset_names: dict[str, list[str]] = {}
    for node in nodes:
        if node.paper_title:
            c = canon(node.paper_title)
            dataset_counts[c] = dataset_counts.get(c, 0) + 1
            dataset_names.setdefault(c, []).append(node.name)

    for paper, count in dataset_counts.items():
        G.add_node(paper, dataset_count=count, known=True, dataset_names=dataset_names.get(paper, []))

    for node in nodes:
        if not node.paper_title:
            continue
        dst = canon(node.paper_title)
        for source in node.sources:
            src_title = source.source_paper.title
            if not src_title:
                continue
            src = canon(src_title)
            if src == dst:
                continue
            if src not in G:
                G.add_node(src, dataset_count=0, known=False, dataset_names=[])
            if G.has_edge(src, dst):
                G[src][dst]["datasets"].append(source.source_dataset_name)
            else:
                G.add_edge(src, dst, datasets=[source.source_dataset_name])

    return G


def load_usage_pairs(usages_path: str | Path) -> list[tuple[str, str, str]]:
    """Load (source_title, paper_title, dataset_name) triples from a TinyDB usages file."""
    path = Path(usages_path)
    if not path.exists():
        return []
    with open(path) as f:
        data = json.load(f)
    triples = []
    for rec in data.get("usages", {}).values():
        if rec.get("source_title") is None:
            continue
        source = rec["source_title"].strip()
        paper = (rec.get("paper_title") or "").strip()
        dataset = (rec.get("dataset_name") or "").strip()
        if source and paper:
            triples.append((source, paper, dataset))
    return triples


def add_usage_edges(
    G: nx.DiGraph,
    usage_triples: list[tuple[str, str, str]],
    canonical: dict[str, str],
) -> None:
    """Add usage edges to G in-place.

    Each triple (source_title, paper_title, dataset_name) means paper_title
    used a dataset from source_title. Aggregates dataset names per pair.
    Skips pairs where a provenance edge already exists in that direction.
    """
    def canon(title: str) -> str:
        return canonical.get(title.strip().lower(), title.strip())

    usage_datasets: dict[tuple[str, str], list[str]] = {}
    for source_title, paper_title, dataset_name in usage_triples:
        src = canon(source_title)
        dst = canon(paper_title)
        if src != dst:
            usage_datasets.setdefault((src, dst), []).append(dataset_name)

    for (src, dst), datasets in usage_datasets.items():
        if src not in G:
            G.add_node(src, dataset_count=0, known=False, dataset_names=[], usage_only=True)
        if dst not in G:
            G.add_node(dst, dataset_count=0, known=False, dataset_names=[], usage_only=True)
        if not G.has_edge(src, dst):
            G.add_edge(src, dst, is_usage=True, datasets=datasets)
