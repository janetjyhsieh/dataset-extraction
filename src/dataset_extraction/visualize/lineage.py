from __future__ import annotations

import argparse
from pathlib import Path

import networkx as nx
from pyvis.network import Network

from dataset_extraction.state.graph import Nodes
from dataset_extraction.visualize.data import (
    _canonical_title_map,
    add_usage_edges,
    build_paper_graph,
    load_usage_pairs,
)
from dataset_extraction.visualize.render import _build_extras
from dataset_extraction.visualize.theme import (
    EDGE_COLOR,
    EDGE_HIGHLIGHT,
    FOCAL_COLOR,
    KNOWN_COLOR,
    LEGEND_HTML,
    USAGE_COLOR,
)


def visualize_lineage(
    nodes_store: Nodes,
    paper_title: str,
    output_path: str | Path = "lineage.html",
    usages_path: str | Path | None = None,
) -> Path:
    """Render the ancestor+descendant subtree for one focal paper.

    paper_title is matched case-insensitively and may be a substring; the
    function raises ValueError listing candidates if the match is ambiguous.
    """
    dataset_nodes = nodes_store.all()
    usage_triples = load_usage_pairs(usages_path) if usages_path else []

    extra_titles = [t for src, dst, _ in usage_triples for t in (src, dst)]
    canonical = _canonical_title_map(dataset_nodes, extra_titles=extra_titles)

    G = build_paper_graph(dataset_nodes, canonical=canonical)
    if usage_triples:
        add_usage_edges(G, usage_triples, canonical)

    query = paper_title.strip().lower()
    matches = [n for n in G.nodes if query in n.lower()]
    if not matches:
        raise ValueError(
            f"No paper found matching {paper_title!r}.\n"
            f"Available papers ({G.number_of_nodes()} total) — try a substring of the title."
        )
    if len(matches) > 1:
        exact = [m for m in matches if m.lower() == query]
        if len(exact) == 1:
            matches = exact
        else:
            bullet_list = "\n".join(f"  • {m}" for m in sorted(matches))
            raise ValueError(
                f"{len(matches)} papers match {paper_title!r}. Be more specific:\n{bullet_list}"
            )

    focal = matches[0]
    return _render_lineage(G, focal, output_path)


def _render_lineage(
    G: nx.DiGraph,
    focal_paper: str,
    output_path: str | Path = "lineage.html",
) -> Path:
    """Render the ancestor+descendant subtree for one focal paper as HTML.

    The focal paper is highlighted in gold. Ancestors (papers it derived from)
    appear above; descendants (papers that derived from it) appear below.
    """
    if focal_paper not in G:
        raise ValueError(f"Paper not found in graph: {focal_paper!r}")

    output_path = Path(output_path)

    ancestors = nx.ancestors(G, focal_paper)
    descendants = nx.descendants(G, focal_paper)
    subgraph_nodes = ancestors | descendants | {focal_paper}
    H = G.subgraph(subgraph_nodes).copy()

    net = Network(directed=True, height="100vh", width="100%")
    net.set_options(f"""
    {{
      "layout": {{
        "hierarchical": {{
          "enabled": true,
          "direction": "UD",
          "sortMethod": "directed",
          "nodeSpacing": 150,
          "levelSeparation": 350,
          "treeSpacing": 200
        }}
      }},
      "physics": {{ "enabled": false }},
      "edges": {{
        "arrows": {{ "to": {{ "enabled": true }} }},
        "smooth": {{ "type": "cubicBezier", "forceDirection": "vertical" }},
        "color": {{
          "color": "{EDGE_COLOR}",
          "highlight": "{EDGE_HIGHLIGHT}",
          "hover": "{EDGE_HIGHLIGHT}",
          "inherit": false
        }}
      }},
      "interaction": {{ "hover": true, "tooltipDelay": 100 }}
    }}
    """)

    for paper, data in H.nodes(data=True):
        is_focal = paper == focal_paper
        count = data.get("dataset_count", 0)
        known = data.get("known", False)
        usage_only = data.get("usage_only", False)
        size = 20 + count * 6
        label = (paper[:35] + "…") if len(paper) > 35 else paper
        names = data.get("dataset_names", [])
        tooltip_lines = [paper, f"{count} dataset(s)"]
        if names:
            tooltip_lines += ["", "Datasets:"] + [f"  • {n}" for n in names]
        if usage_only:
            tooltip_lines.append("(usage only — not in provenance graph)")
        elif not known:
            tooltip_lines.append("(external reference)")

        if is_focal:
            net.add_node(
                paper, label=label, title="\n".join(tooltip_lines),
                size=max(size, 30) + 10, color=FOCAL_COLOR,
                font={"size": 14, "bold": True},
                borderWidth=4, borderWidthSelected=5,
            )
        elif usage_only:
            net.add_node(
                paper, label=label, title="\n".join(tooltip_lines),
                size=size, color=USAGE_COLOR, font={"size": 12},
                borderWidth=2, shapeProperties={"borderDashes": [5, 5]},
            )
        else:
            color = KNOWN_COLOR if known else "#888888"
            net.add_node(paper, label=label, title="\n".join(tooltip_lines), size=size, color=color, font={"size": 12})

    for src, dst, data in H.edges(data=True):
        datasets = data.get("datasets", [])
        is_usage = data.get("is_usage", False)
        tooltip = "\n".join(f"• {d}" for d in datasets)
        if is_usage:
            net.add_edge(src, dst, title=tooltip, width=1 + len(datasets), dashes=[5, 5], color=USAGE_COLOR)
        else:
            net.add_edge(src, dst, title=tooltip, width=1 + len(datasets))

    net.save_graph(str(output_path))

    title_banner = f"""
<style>
#lineage-title {{
  position: fixed;
  top: 12px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 9999;
  background: rgba(28,28,28,0.93);
  border: 1px solid {FOCAL_COLOR};
  border-radius: 8px;
  padding: 8px 18px;
  color: {FOCAL_COLOR};
  font-family: Arial, sans-serif;
  font-size: 13px;
  font-weight: bold;
  white-space: nowrap;
  max-width: 80vw;
  overflow: hidden;
  text-overflow: ellipsis;
}}
</style>
<div id="lineage-title">Lineage: {focal_paper}</div>
"""

    html = output_path.read_text(encoding="utf-8")
    html = html.replace("</body>", LEGEND_HTML + title_banner + _build_extras(H) + "\n</body>")
    output_path.write_text(html, encoding="utf-8")

    return output_path


def main() -> None:
    """Render the lineage subtree for a single paper as an interactive HTML file.

    Usage:
        python -m dataset_extraction.visualize.lineage --working-dir papers/cvpr --paper "ImageNet"
        python -m dataset_extraction.visualize.lineage --working-dir papers/cvpr --paper "ImageNet" --output out/imagenet_lineage.html
        python -m dataset_extraction.visualize.lineage --working-dir papers/cvpr --paper "ImageNet" --usages papers/cvpr/state/usages.json
    """
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("--working-dir", required=True, help="Directory containing state/graph.json")
    parser.add_argument("--paper", required=True, help="Paper title (or substring) to use as the focal node")
    parser.add_argument("--output", default=None, help="Output HTML path (default: <working-dir>/lineage.html)")
    parser.add_argument("--usages", default=None, help="Path to usages TinyDB JSON to overlay usage edges")
    args = parser.parse_args()

    working_dir = Path(args.working_dir)
    output_path = Path(args.output) if args.output else working_dir / "lineage.html"

    nodes = Nodes(working_dir / "state" / "graph.json")
    output = visualize_lineage(nodes, args.paper, output_path, usages_path=args.usages)
    print(f"Lineage graph written to {output}")


if __name__ == "__main__":
    main()
