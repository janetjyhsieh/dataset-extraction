// Controls for the dataset lineage graph.
// Globals injected by render.py before this script runs:
//   nodeComponents  — {nodeId: componentIndex}
//   nodeDetails     — {nodeId: {datasets, year, venue, source_processed}}
//   compSizes       — [size, ...]
//   numComps        — number of weakly-connected components
//   totalNodes      — total node count

(function () {
  var compButtons = document.getElementById('comp-buttons');
  var toggleBtn = document.getElementById('controls-toggle');

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

  // --- Subgraph highlight on click ---

  function buildAdjacency() {
    var children = {}, parents = {};
    nodes.forEach(function (n) { children[n.id] = []; parents[n.id] = []; });
    edges.forEach(function (e) {
      if (children[e.from]) children[e.from].push(e.to);
      if (parents[e.to]) parents[e.to].push(e.from);
    });
    return { children: children, parents: parents };
  }

  function bfs(startId, getNeighbors) {
    var visited = new Set(), queue = [startId];
    while (queue.length > 0) {
      var cur = queue.shift();
      (getNeighbors(cur) || []).forEach(function (nb) {
        if (!visited.has(nb)) { visited.add(nb); queue.push(nb); }
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
      if (highlighted.has(e.from) && highlighted.has(e.to)) highlightedEdges.add(e.id);
    });

    nodes.update(Array.from(highlighted).map(function (id) { return { id: id, opacity: 1 }; })
      .concat(
        nodes.get().filter(function (n) { return !highlighted.has(n.id); })
          .map(function (n) { return { id: n.id, opacity: 0.1 }; })
      ));

    edges.update(edges.get().map(function (e) {
      return { id: e.id, opacity: highlightedEdges.has(e.id) ? 1 : 0 };
    }));
  }

  function restoreAll() {
    nodes.update(nodes.get().map(function (n) { return { id: n.id, opacity: 1 }; }));
    edges.update(edges.get().map(function (e) { return { id: e.id, opacity: 1 }; }));
  }

  // --- Click handler: show detail panel ---

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
    var datasets = det.datasets || [];
    var year = det.year;
    var venue = det.venue || '';
    var sourcePending = det.source_processed === false && datasets.length > 0;

    var metaParts = [];
    if (venue) metaParts.push(venue);
    if (year) metaParts.push(year);

    var html = '<h4><span>' + nodeId + '</span>'
      + '<button class="detail-close" title="Close">&#x2715;</button></h4>';

    if (metaParts.length > 0) {
      html += '<div class="detail-meta">' + metaParts.join(' · ') + '</div>';
    }

    if (datasets.length > 0) {
      html += '<b>Datasets introduced (' + datasets.length + '):</b><ul>';
      datasets.forEach(function (d) { html += '<li>' + d + '</li>'; });
      html += '</ul>';
    } else {
      html += '<em style="color:#888">Referenced paper — datasets not extracted yet.</em>';
    }

    if (sourcePending) {
      html += '<p style="color:#e8a838;font-size:12px;margin-top:8px;">&#9888; Source papers not yet discovered.</p>';
    }

    content.innerHTML = html;
    panel.style.display = 'block';

    content.querySelector('.detail-close').addEventListener('click', function () {
      panel.style.display = 'none';
      restoreAll();
    });
  });
})();
