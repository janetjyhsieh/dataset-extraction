 Here's a walkthrough of the visualize submodule from the Python side down to
  the browser:

  ---
  What it does
  
  The module takes your DatasetNode store and renders an interactive HTML file —
   a directed graph you open in a browser where each node is a paper and each
  arrow means "this paper derived a dataset from that paper."

  ---
  The pipeline (4 files)
  
  1. graph.py — the entry point

  visualize(nodes_store, output_path, usages_path) is the single public
  function. It:
  1. Loads all DatasetNode records from TinyDB
  2. Optionally loads usage data
  3. Calls build_paper_graph() → render() and returns the path to the HTML file
  
  2. data.py — graph construction (pure Python/NetworkX)

  build_paper_graph() builds a NetworkX directed graph (nx.DiGraph). Each node =
   a paper title, each edge A→B = "a dataset in paper B was derived from
  something in paper A." Node attributes track dataset_count and known (whether
  the paper itself is in your store vs. just referenced).

  add_usage_edges() overlays a second layer of edges from a separate usages file
   — these represent "paper B used a dataset from paper A" (distinct from
  provenance/derivation).
  
  3. render.py — turns the graph into HTML

    Uses pyvis, a Python wrapper around the vis-network JavaScript library. The
    flow:
    1. Creates a Network object and configures layout (left-to-right
    hierarchical), physics (disabled — nodes don't float around), and edge styling
    2. Loops over nodes/edges and calls net.add_node() / net.add_edge() — this is
    where colors, sizes, tooltips are set
    3. net.save_graph() writes a self-contained HTML file with the vis-network JS
    embedded
    4. Then it modifies that HTML — reads it back, injects the legend and the
    controls panel before </body>

  4. theme.py — just color constants

  Named hex strings (KNOWN_COLOR, USAGE_COLOR, etc.) and the legend HTML/CSS
  block. Kept separate so you can change the look without touching rendering
  logic.
  
  ---
  The browser-side JS (assets/controls.js)
  
  This file runs in the browser after the HTML is opened. It does two things:

  Component filter buttons — if the graph has disconnected subgraphs
  ("components"), buttons appear to isolate each one. Clicking hides all other
  nodes/edges and zooms in.
  
  Click-to-highlight — clicking a node dims everything except that node's
  ancestors and descendants (BFS up and down the DAG). Clicking blank space
  restores full opacity.
  
  The JS reads from variables injected inline by _build_extras() in render.py
  (nodeComponents, nodeDetails, etc.) — that's how Python data gets passed to
  JavaScript.
  
  ---
  Mental model

  TinyDB → Python objects → NetworkX graph → pyvis → HTML + vis-network JS
                                                    ↑
                                injected: data JSON + controls.js

  The output is a single .html file with everything embedded — no server needed,
   just open it in a browser.