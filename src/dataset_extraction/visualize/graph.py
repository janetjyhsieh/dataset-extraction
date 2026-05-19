import json
from pathlib import Path

import networkx as nx
from pyvis.network import Network

from dataset_extraction.state.graph import Nodes
from dataset_extraction.state.nodes import DatasetNode

_KNOWN_COLOR = "#4e9af1"
_EXTERNAL_COLOR = "#888888"
_EDGE_COLOR = "#aaaaaa"
_EDGE_HIGHLIGHT = "#f0a500"
_USAGE_COLOR = "#e8a838"

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
    <span>Papers</span>
  </div>
  <div class="leg-row">
    <div class="leg-circle" style="width:14px;height:14px;background:#888888;"></div>
    <span>PDF not found</span>
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

  <div class="leg-section">
    <div class="leg-row">
      <div style="width:14px;height:14px;border-radius:50%;border:2px dashed #e8a838;flex-shrink:0;box-sizing:border-box;"></div>
      <span>Usage-only paper</span>
    </div>
    <div class="leg-row">
      <div style="width:26px;height:0;border-top:2px dashed #e8a838;flex-shrink:0;"></div>
      <span>Dataset used by (→)</span>
    </div>
  </div>

  <div class="leg-hint">Hover nodes or edges for details</div>
</div>
"""


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


def _build_extras(G: nx.DiGraph) -> str:
    """Generate injectable HTML/CSS/JS for component toggle and detail sidebar."""
    components = list(nx.weakly_connected_components(G))
    node_to_comp = {node: i for i, comp in enumerate(components) for node in comp}
    comp_sizes = [len(c) for c in components]
    num_comps = len(components)
    total_nodes = G.number_of_nodes()

    node_details = {
        paper: {
            "known": data.get("known", False),
            "usage_only": data.get("usage_only", False),
            "dataset_names": data.get("dataset_names", []),
        }
        for paper, data in G.nodes(data=True)
    }

    return f"""
<style>
.vis-tooltip {{
    white-space: pre-line !important;
    font-family: Arial, sans-serif !important;
    line-height: 1.5 !important;
}}
#component-controls {{
    position: fixed;
    top: 12px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 9999;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    background: rgba(28,28,28,0.93);
    padding: 8px 14px;
    border-radius: 8px;
    border: 1px solid #444;
    max-width: 90vw;
}}
#comp-buttons {{
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    justify-content: center;
}}
#comp-buttons.collapsed {{
    display: none;
}}
#controls-toggle {{
    background: none;
    border: none;
    color: #888;
    font-size: 11px;
    cursor: pointer;
    padding: 0;
    font-family: Arial, sans-serif;
    line-height: 1;
    letter-spacing: 0.03em;
}}
#controls-toggle:hover {{ color: #ddd; }}
.comp-btn {{
    padding: 4px 12px;
    border-radius: 4px;
    border: 1px solid #555;
    background: #333;
    color: #ddd;
    cursor: pointer;
    font-size: 12px;
    font-family: Arial, sans-serif;
    transition: background 0.15s;
}}
.comp-btn:hover {{ background: #444; }}
.comp-btn.active {{
    background: {_KNOWN_COLOR};
    border-color: {_KNOWN_COLOR};
    color: white;
}}
#detail-panel {{
    position: fixed;
    top: 60px;
    right: 24px;
    width: 280px;
    max-height: calc(100vh - 80px);
    overflow-y: auto;
    background: rgba(28,28,28,0.93);
    border: 1px solid #444;
    border-radius: 8px;
    padding: 14px 18px;
    color: #ddd;
    font-family: Arial, sans-serif;
    font-size: 13px;
    z-index: 9999;
    display: none;
    box-sizing: border-box;
}}
#detail-panel h4 {{
    margin: 0 0 10px 0;
    font-size: 14px;
    color: #fff;
    border-bottom: 1px solid #555;
    padding-bottom: 7px;
    word-break: break-word;
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 8px;
}}
.detail-close {{
    flex-shrink: 0;
    background: none;
    border: none;
    color: #888;
    font-size: 16px;
    cursor: pointer;
    padding: 0;
    line-height: 1;
}}
.detail-close:hover {{ color: #ddd; }}
#detail-panel ul {{
    margin: 6px 0 0 0;
    padding-left: 18px;
    line-height: 1.7;
}}
</style>

<div id="component-controls">
  <div id="comp-buttons"></div>
  <button id="controls-toggle" title="Collapse">▲ hide</button>
</div>

<div id="detail-panel">
  <div id="detail-content"></div>
</div>

<script>
(function() {{
  var nodeComponents = {json.dumps(node_to_comp)};
  var nodeDetails = {json.dumps(node_details)};
  var compSizes = {json.dumps(comp_sizes)};
  var numComps = {num_comps};
  var totalNodes = {total_nodes};

  // drawGraph() already ran synchronously above, so nodes/edges/network are defined.
  var compButtons = document.getElementById('comp-buttons');
  var toggleBtn = document.getElementById('controls-toggle');

  var allBtn = document.createElement('button');
  allBtn.className = 'comp-btn active';
  allBtn.textContent = 'All (' + totalNodes + ')';
  allBtn.dataset.comp = 'all';
  compButtons.appendChild(allBtn);

  if (numComps > 1) {{
    for (var i = 0; i < numComps; i++) {{
      var btn = document.createElement('button');
      btn.className = 'comp-btn';
      btn.textContent = 'Component ' + (i + 1) + ' (' + compSizes[i] + ')';
      btn.dataset.comp = String(i);
      compButtons.appendChild(btn);
    }}
  }}

  toggleBtn.addEventListener('click', function() {{
    var collapsed = compButtons.classList.toggle('collapsed');
    toggleBtn.textContent = collapsed ? '▼ show' : '▲ hide';
  }});

  function filterByComponent(compIdx) {{
    var nodeUpdate = [];
    nodes.forEach(function(node) {{
      nodeUpdate.push({{
        id: node.id,
        hidden: compIdx !== 'all' && nodeComponents[node.id] !== parseInt(compIdx)
      }});
    }});
    nodes.update(nodeUpdate);

    var edgeUpdate = [];
    edges.forEach(function(edge) {{
      edgeUpdate.push({{
        id: edge.id,
        hidden: compIdx !== 'all' && (
          nodeComponents[edge.from] !== parseInt(compIdx) ||
          nodeComponents[edge.to] !== parseInt(compIdx)
        )
      }});
    }});
    edges.update(edgeUpdate);

    if (compIdx === 'all') {{
      network.fit({{ animation: {{ duration: 500 }} }});
    }} else {{
      var visible = nodeUpdate
        .filter(function(n) {{ return !n.hidden; }})
        .map(function(n) {{ return n.id; }});
      network.fit({{ nodes: visible, animation: {{ duration: 500 }} }});
    }}
  }}

  compButtons.addEventListener('click', function(e) {{
    var btn = e.target.closest('.comp-btn');
    if (!btn) return;
    compButtons.querySelectorAll('.comp-btn').forEach(function(b) {{ b.classList.remove('active'); }});
    btn.classList.add('active');
    filterByComponent(btn.dataset.comp);
  }});

  network.on('click', function(params) {{
    var panel = document.getElementById('detail-panel');
    var content = document.getElementById('detail-content');
    if (params.nodes.length === 0) {{
      panel.style.display = 'none';
      return;
    }}
    var nodeId = params.nodes[0];
    var det = nodeDetails[nodeId] || {{}};
    var names = det.dataset_names || [];
    var html = '<h4><span>' + nodeId + '</span>' +
      '<button class="detail-close" title="Close">&#x2715;</button></h4>';
    if (det.known) {{
      html += '<b>Datasets proposed (' + names.length + '):</b><ul>';
      names.forEach(function(n) {{ html += '<li>' + n + '</li>'; }});
      html += '</ul>';
    }} else if (det.usage_only) {{
      html += '<em style="color:#888">Usage-only paper — appears in usage data but not in the provenance graph.</em>';
    }} else {{
      html += '<em style="color:#888">External reference — datasets not extracted from this paper.</em>';
    }}
    content.innerHTML = html;
    panel.style.display = 'block';
    content.querySelector('.detail-close').addEventListener('click', function() {{
      panel.style.display = 'none';
    }});
  }});
}})();
</script>
"""


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
                size=size, color=_USAGE_COLOR, font={"size": 12},
                borderWidth=2, shapeProperties={"borderDashes": [5, 5]},
            )
        else:
            color = _KNOWN_COLOR if known else _EXTERNAL_COLOR
            net.add_node(paper, label=label, title="\n".join(tooltip_lines), size=size, color=color, font={"size": 12})

    for src, dst, data in G.edges(data=True):
        datasets = data.get("datasets", [])
        is_usage = data.get("is_usage", False)
        tooltip = "\n".join(f"• {d}" for d in datasets)
        if is_usage:
            net.add_edge(
                src, dst, title=tooltip, width=1 + len(datasets),
                dashes=[5, 5], color=_USAGE_COLOR,
            )
        else:
            net.add_edge(src, dst, title=tooltip, width=1 + len(datasets))

    net.save_graph(str(output_path))

    html = output_path.read_text(encoding="utf-8")
    html = html.replace("</body>", _LEGEND_HTML + _build_extras(G) + "\n</body>")
    output_path.write_text(html, encoding="utf-8")

    return output_path


def visualize(
    nodes_store: Nodes,
    output_path: str | Path = "graph.html",
    usages_path: str | Path | None = None,
) -> Path:
    """Build and render the provenance graph from a Nodes store.

    If usages_path is provided, usage edges (dotted) are overlaid on the graph.
    """
    dataset_nodes = nodes_store.all()
    usage_triples = load_usage_pairs(usages_path) if usages_path else []

    extra_titles = [t for src, dst, _ in usage_triples for t in (src, dst)]
    canonical = _canonical_title_map(dataset_nodes, extra_titles=extra_titles)

    G = build_paper_graph(dataset_nodes, canonical=canonical)
    if usage_triples:
        add_usage_edges(G, usage_triples, canonical)

    return render(G, output_path)
