KNOWN_COLOR = "#4e9af1"
EXTERNAL_COLOR = "#888888"
EDGE_COLOR = "#aaaaaa"
EDGE_HIGHLIGHT = "#f0a500"
USAGE_COLOR = "#e8a838"
FOCAL_COLOR = "#f5c518"

LEGEND_HTML = """
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
    display: flex;
    justify-content: space-between;
    align-items: center;
    cursor: pointer;
    user-select: none;
}
#legend-toggle {
    background: none;
    border: none;
    color: #888;
    font-size: 11px;
    cursor: pointer;
    padding: 0;
    font-family: Arial, sans-serif;
    line-height: 1;
    letter-spacing: 0.03em;
}
#legend-toggle:hover { color: #ddd; }
#legend-body.collapsed { display: none; }
.leg-section { margin-top: 9px; border-top: 1px solid #444; padding-top: 7px; }
.leg-row { display: flex; align-items: center; gap: 10px; margin: 5px 0; }
.leg-circle { border-radius: 50%; flex-shrink: 0; }
.leg-line { border-radius: 2px; flex-shrink: 0; }
.leg-hint { margin-top: 8px; color: #888; font-size: 11px; }
</style>
<div id="legend">
  <h4 onclick="(function(){var b=document.getElementById('legend-body');var t=document.getElementById('legend-toggle');var c=b.classList.toggle('collapsed');t.textContent=c?'▼ show':'▲ hide';})()">
    Legend
    <button id="legend-toggle" title="Collapse">&#9650; hide</button>
  </h4>
  <div id="legend-body">
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
</div>
"""
