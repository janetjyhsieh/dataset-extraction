from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
from pyvis.network import Network

from dataset_extraction.visualize.theme import EDGE_COLOR, EDGE_HIGHLIGHT, KNOWN_COLOR, PHANTOM_COLOR, LEGEND_HTML

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
    components = list(nx.weakly_connected_components(G))
    node_to_comp = {node: i for i, comp in enumerate(components) for node in comp}
    comp_sizes = [len(c) for c in components]

    node_details = {
        paper: {
            "datasets": data.get("datasets", []),
            "year": data.get("year"),
            "venue": data.get("venue"),
            "source_processed": data.get("source_processed", False),
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


def render(G: nx.DiGraph, output_path: str | Path) -> Path:
    """Render a lineage DiGraph as an interactive HTML file.

    Node attributes used: datasets (list[str]), year (int|None),
    venue (str|None), source_processed (bool).
    """
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
        datasets = data.get("datasets", [])
        year = data.get("year")
        venue = data.get("venue")

        is_known = len(datasets) > 0
        size = max(20, 20 + len(datasets) * 6)
        color = KNOWN_COLOR if is_known else PHANTOM_COLOR
        label = (paper[:35] + "…") if len(paper) > 35 else paper

        meta = " · ".join(filter(None, [venue, str(year) if year else None]))
        tooltip_lines = [paper]
        if meta:
            tooltip_lines.append(meta)
        tooltip_lines.append(f"{len(datasets)} dataset(s)")
        if datasets:
            tooltip_lines += ["", "Datasets:"] + [f"  • {d}" for d in datasets]
        if not is_known:
            tooltip_lines.append("(referenced — not yet explored)")

        net.add_node(paper, label=label, title="\n".join(tooltip_lines),
                     size=size, color=color, font={"size": 12})

    for src, dst in G.edges():
        net.add_edge(src, dst)

    net.save_graph(str(output_path))

    html = output_path.read_text(encoding="utf-8")
    html = html.replace("</body>", LEGEND_HTML + _build_extras(G) + "\n</body>")
    output_path.write_text(html, encoding="utf-8")

    return output_path
