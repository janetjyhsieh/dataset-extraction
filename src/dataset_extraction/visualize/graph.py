from pathlib import Path

import networkx as nx
from pyvis.network import Network

from dataset_extraction.state.graph import Nodes
from dataset_extraction.state.nodes import DatasetNode

_KNOWN_COLOR = "#4e9af1"
_EXTERNAL_COLOR = "#888888"
_EDGE_COLOR = "#aaaaaa"
_EDGE_HIGHLIGHT = "#f0a500"

_LEGEND_HTML = """
<style>
#legend {
    position: fixed;
    bottom: 24px;
    left: 24px;
    background: rgba(28, 28, 28, 0.93);
    border: 1px solid #444;
    border-radius: 8px;
    padding: 14px 18px;
    color: #ddd;
    font-family: Arial, sans-serif;
    font-size: 13px;
    z-index: 9999;
    pointer-events: none;
    line-height: 1.5;
    min-width: 210px;
}
#legend h4 {
    margin: 0 0 10px 0;
    font-size: 14px;
    color: #fff;
    border-bottom: 1px solid #555;
    padding-bottom: 7px;
    letter-spacing: 0.02em;
}
.leg-section { margin-top: 9px; border-top: 1px solid #444; padding-top: 7px; }
.leg-row { display: flex; align-items: center; gap: 10px; margin: 5px 0; }
.leg-circle { border-radius: 50%; flex-shrink: 0; }
.leg-line { border-radius: 2px; flex-shrink: 0; }
.leg-hint { margin-top: 8px; color: #888; font-size: 11px; }
</style>
<div id="legend">
  <h4>Legend</h4>

  <div class="leg-row">
    <div class="leg-circle" style="width:14px;height:14px;background:#4e9af1;"></div>
    <span>Paper in graph</span>
  </div>
  <div class="leg-row">
    <div class="leg-circle" style="width:14px;height:14px;background:#888888;"></div>
    <span>External source paper</span>
  </div>
  <div class="leg-row">
    <div style="display:flex;align-items:center;gap:3px;flex-shrink:0;">
      <div class="leg-circle" style="width:10px;height:10px;background:#4e9af1;opacity:0.6;"></div>
      <div class="leg-circle" style="width:16px;height:16px;background:#4e9af1;opacity:0.8;"></div>
      <div class="leg-circle" style="width:22px;height:22px;background:#4e9af1;"></div>
    </div>
    <span>Node size = # datasets</span>
  </div>

  <div class="leg-section">
    <div class="leg-row">
      <div class="leg-line" style="width:26px;height:2px;background:#aaaaaa;"></div>
      <span>Derived from (→)</span>
    </div>
    <div class="leg-row">
      <div style="display:flex;align-items:center;gap:3px;flex-shrink:0;">
        <div class="leg-line" style="width:26px;height:2px;background:#aaaaaa;"></div>
        <div class="leg-line" style="width:26px;height:5px;background:#aaaaaa;"></div>
      </div>
      <span>Width = # datasets</span>
    </div>
    <div class="leg-row">
      <div class="leg-line" style="width:26px;height:3px;background:#f0a500;"></div>
      <span>Selected edge</span>
    </div>
  </div>

  <div class="leg-hint">Hover nodes or edges for details</div>
</div>
"""


def build_paper_graph(nodes: list[DatasetNode]) -> nx.DiGraph:
    """Build a paper-level provenance DiGraph from dataset nodes.

    Each graph node is a paper (keyed by title). An edge A → B means a dataset
    in paper B was derived from a dataset introduced in paper A.
    """
    G = nx.DiGraph()

    dataset_counts: dict[str, int] = {}
    for node in nodes:
        if node.paper_title:
            dataset_counts[node.paper_title] = dataset_counts.get(node.paper_title, 0) + 1

    for paper, count in dataset_counts.items():
        G.add_node(paper, dataset_count=count, known=True)

    for node in nodes:
        if not node.paper_title:
            continue
        for source in node.sources:
            src_paper = source.source_paper.title
            if not src_paper or src_paper == node.paper_title:
                continue
            if src_paper not in G:
                G.add_node(src_paper, dataset_count=0, known=False)
            if G.has_edge(src_paper, node.paper_title):
                G[src_paper][node.paper_title]["datasets"].append(source.source_dataset_name)
            else:
                G.add_edge(src_paper, node.paper_title, datasets=[source.source_dataset_name])

    return G


def render(G: nx.DiGraph, output_path: str | Path = "graph.html") -> Path:
    """Render the paper provenance graph as an interactive HTML file."""
    output_path = Path(output_path)

    net = Network(directed=True, height="100vh", width="100%")
    net.set_options(f"""
    {{
      "layout": {{
        "hierarchical": {{
          "enabled": true,
          "direction": "LR",
          "sortMethod": "directed",
          "nodeSpacing": 150,
          "levelSeparation": 350,
          "treeSpacing": 200
        }}
      }},
      "physics": {{ "enabled": false }},
      "edges": {{
        "arrows": {{ "to": {{ "enabled": true }} }},
        "smooth": {{ "type": "cubicBezier", "forceDirection": "horizontal" }},
        "color": {{
          "color": "{_EDGE_COLOR}",
          "highlight": "{_EDGE_HIGHLIGHT}",
          "hover": "{_EDGE_HIGHLIGHT}",
          "inherit": false
        }}
      }},
      "interaction": {{ "hover": true, "tooltipDelay": 100 }}
    }}
    """)

    for paper, data in G.nodes(data=True):
        count = data.get("dataset_count", 0)
        known = data.get("known", False)
        size = 20 + count * 6
        color = _KNOWN_COLOR if known else _EXTERNAL_COLOR
        label = (paper[:35] + "…") if len(paper) > 35 else paper
        tooltip = f"<b>{paper}</b><br>{count} dataset(s)"
        if not known:
            tooltip += "<br><i>(external reference)</i>"
        net.add_node(paper, label=label, title=tooltip, size=size, color=color, font={"size": 12})

    for src, dst, data in G.edges(data=True):
        datasets = data.get("datasets", [])
        tooltip = "<br>".join(f"• {d}" for d in datasets)
        net.add_edge(src, dst, title=tooltip, width=1 + len(datasets))

    net.save_graph(str(output_path))

    html = output_path.read_text(encoding="utf-8")
    html = html.replace("</body>", _LEGEND_HTML + "\n</body>")
    output_path.write_text(html, encoding="utf-8")

    return output_path


def visualize(nodes_store: Nodes, output_path: str | Path = "graph.html") -> Path:
    """Build and render the provenance graph from a Nodes store."""
    G = build_paper_graph(nodes_store.all())
    return render(G, output_path)
