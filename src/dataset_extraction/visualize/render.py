from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
from pyvis.network import Network

from dataset_extraction.visualize.theme import (
    EDGE_COLOR,
    EDGE_HIGHLIGHT,
    KNOWN_COLOR,
    USAGE_COLOR,
    LEGEND_HTML,
)

_ASSETS_DIR = Path(__file__).parent / "assets"

_CONTROLS_HTML = """
<div id="component-controls">
  <div id="comp-buttons"></div>
  <button id="controls-toggle" title="Collapse">&#9650; hide</button>
</div>

<div id="detail-panel">
  <div id="detail-content"></div>
</div>
"""


def _build_extras(G: nx.DiGraph) -> str:
    """Inline CSS, data JSON, and JS controls into the rendered HTML."""
    components = list(nx.weakly_connected_components(G))
    node_to_comp = {node: i for i, comp in enumerate(components) for node in comp}
    comp_sizes = [len(c) for c in components]

    node_details = {
        paper: {
            "known": data.get("known", False),
            "usage_only": data.get("usage_only", False),
            "dataset_names": data.get("dataset_names", []),
        }
        for paper, data in G.nodes(data=True)
    }

    css = (_ASSETS_DIR / "controls.css").read_text()
    js = (_ASSETS_DIR / "controls.js").read_text()

    data_block = (
        f"var nodeComponents = {json.dumps(node_to_comp)};\n"
        f"var nodeDetails = {json.dumps(node_details)};\n"
        f"var compSizes = {json.dumps(comp_sizes)};\n"
        f"var numComps = {len(components)};\n"
        f"var totalNodes = {G.number_of_nodes()};\n"
    )

    return (
        f"<style>\n{css}\n</style>\n"
        f"{_CONTROLS_HTML}\n"
        f"<script>\n{data_block}</script>\n"
        f"<script>\n{js}\n</script>\n"
    )


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
          "color": "{EDGE_COLOR}",
          "highlight": "{EDGE_HIGHLIGHT}",
          "hover": "{EDGE_HIGHLIGHT}",
          "inherit": false
        }}
      }},
      "interaction": {{ "hover": true, "tooltipDelay": 100 }}
    }}
    """)

    for paper, data in G.nodes(data=True):
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

        if usage_only:
            net.add_node(
                paper, label=label, title="\n".join(tooltip_lines),
                size=size, color=USAGE_COLOR, font={"size": 12},
                borderWidth=2, shapeProperties={"borderDashes": [5, 5]},
            )
        else:
            color = KNOWN_COLOR if known else "#888888"
            net.add_node(paper, label=label, title="\n".join(tooltip_lines), size=size, color=color, font={"size": 12})

    for src, dst, data in G.edges(data=True):
        datasets = data.get("datasets", [])
        is_usage = data.get("is_usage", False)
        tooltip = "\n".join(f"• {d}" for d in datasets)
        if is_usage:
            net.add_edge(src, dst, title=tooltip, width=1 + len(datasets), dashes=[5, 5], color=USAGE_COLOR)
        else:
            net.add_edge(src, dst, title=tooltip, width=1 + len(datasets))

    net.save_graph(str(output_path))

    html = output_path.read_text(encoding="utf-8")
    html = html.replace("</body>", LEGEND_HTML + _build_extras(G) + "\n</body>")
    output_path.write_text(html, encoding="utf-8")

    return output_path
