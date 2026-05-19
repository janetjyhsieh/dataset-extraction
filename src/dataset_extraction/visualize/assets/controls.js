// Controls for the dataset provenance graph.
// Expects these globals set by the inline data script before this file runs:
//   nodeComponents, nodeDetails, compSizes, numComps, totalNodes
// Expects vis-network globals: nodes, edges, network

(function () {
  var compButtons = document.getElementById('comp-buttons');
  var toggleBtn = document.getElementById('controls-toggle');

  // Tracks which edge IDs are hidden by the component filter so that
  // highlight/restore can correctly compose with the filter state.
  var hiddenByFilter = new Set();

  // --- Component toggle buttons ---

  var allBtn = document.createElement('button');
  allBtn.className = 'comp-btn active';
  allBtn.textContent = 'All (' + totalNodes + ')';
  allBtn.dataset.comp = 'all';
  compButtons.appendChild(allBtn);

  if (numComps > 1) {
    for (var i = 0; i < numComps; i++) {
      var btn = document.createElement('button');
      btn.className = 'comp-btn';
      btn.textContent = 'Component ' + (i + 1) + ' (' + compSizes[i] + ')';
      btn.dataset.comp = String(i);
      compButtons.appendChild(btn);
    }
  }

  toggleBtn.addEventListener('click', function () {
    var collapsed = compButtons.classList.toggle('collapsed');
    toggleBtn.textContent = collapsed ? '▼ show' : '▲ hide';
  });

  function filterByComponent(compIdx) {
    hiddenByFilter.clear();

    var nodeUpdate = [];
    nodes.forEach(function (node) {
      nodeUpdate.push({
        id: node.id,
        hidden: compIdx !== 'all' && nodeComponents[node.id] !== parseInt(compIdx),
      });
    });
    nodes.update(nodeUpdate);

    var edgeUpdate = [];
    edges.forEach(function (edge) {
      var hide =
        compIdx !== 'all' &&
        (nodeComponents[edge.from] !== parseInt(compIdx) ||
          nodeComponents[edge.to] !== parseInt(compIdx));
      if (hide) hiddenByFilter.add(edge.id);
      edgeUpdate.push({ id: edge.id, hidden: hide });
    });
    edges.update(edgeUpdate);

    if (compIdx === 'all') {
      network.fit({ animation: { duration: 500 } });
    } else {
      var visible = nodeUpdate
        .filter(function (n) { return !n.hidden; })
        .map(function (n) { return n.id; });
      network.fit({ nodes: visible, animation: { duration: 500 } });
    }
  }

  compButtons.addEventListener('click', function (e) {
    var btn = e.target.closest('.comp-btn');
    if (!btn) return;
    compButtons.querySelectorAll('.comp-btn').forEach(function (b) {
      b.classList.remove('active');
    });
    btn.classList.add('active');
    filterByComponent(btn.dataset.comp);
  });

  // --- Subgraph highlight ---

  function buildAdjacency() {
    var children = {};
    var parents = {};
    nodes.forEach(function (n) {
      children[n.id] = [];
      parents[n.id] = [];
    });
    edges.forEach(function (e) {
      if (children[e.from]) children[e.from].push(e.to);
      if (parents[e.to]) parents[e.to].push(e.from);
    });
    return { children: children, parents: parents };
  }

  function bfs(startId, getNeighbors) {
    var visited = new Set();
    var queue = [startId];
    while (queue.length > 0) {
      var cur = queue.shift();
      (getNeighbors(cur) || []).forEach(function (nb) {
        if (!visited.has(nb)) {
          visited.add(nb);
          queue.push(nb);
        }
      });
    }
    return visited;
  }

  function highlightSubgraph(nodeId) {
    var adj = buildAdjacency();
    var ancestors = bfs(nodeId, function (n) { return adj.parents[n]; });
    var descendants = bfs(nodeId, function (n) { return adj.children[n]; });
    var highlighted = new Set([nodeId]);
    ancestors.forEach(function (n) { highlighted.add(n); });
    descendants.forEach(function (n) { highlighted.add(n); });

    var highlightedEdges = new Set();
    edges.forEach(function (e) {
      if (highlighted.has(e.from) && highlighted.has(e.to)) {
        highlightedEdges.add(e.id);
      }
    });

    var nodeUpdate = [];
    nodes.forEach(function (n) {
      nodeUpdate.push({ id: n.id, opacity: highlighted.has(n.id) ? 1 : 0.1 });
    });
    nodes.update(nodeUpdate);

    var edgeUpdate = [];
    edges.forEach(function (e) {
      edgeUpdate.push({ id: e.id, opacity: highlightedEdges.has(e.id) ? 1 : 0 });
    });
    edges.update(edgeUpdate);
  }

  function restoreAll() {
    var nodeUpdate = [];
    nodes.forEach(function (n) { nodeUpdate.push({ id: n.id, opacity: 1 }); });
    nodes.update(nodeUpdate);

    var edgeUpdate = [];
    edges.forEach(function (e) { edgeUpdate.push({ id: e.id, opacity: 1 }); });
    edges.update(edgeUpdate);
  }

  // --- Click handler ---

  network.on('click', function (params) {
    var panel = document.getElementById('detail-panel');
    var content = document.getElementById('detail-content');

    if (params.nodes.length === 0) {
      restoreAll();
      panel.style.display = 'none';
      return;
    }

    var nodeId = params.nodes[0];
    highlightSubgraph(nodeId);

    var det = nodeDetails[nodeId] || {};
    var names = det.dataset_names || [];
    var html =
      '<h4><span>' +
      nodeId +
      '</span><button class="detail-close" title="Close">&#x2715;</button></h4>';
    if (det.known) {
      html += '<b>Datasets proposed (' + names.length + '):</b><ul>';
      names.forEach(function (n) { html += '<li>' + n + '</li>'; });
      html += '</ul>';
    } else if (det.usage_only) {
      html +=
        '<em style="color:#888">Usage-only paper — appears in usage data but not in the provenance graph.</em>';
    } else {
      html +=
        '<em style="color:#888">External reference — datasets not extracted from this paper.</em>';
    }
    content.innerHTML = html;
    panel.style.display = 'block';
    content.querySelector('.detail-close').addEventListener('click', function () {
      panel.style.display = 'none';
      restoreAll();
    });
  });
})();
