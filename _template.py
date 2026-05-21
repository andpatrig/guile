"""
guile._template — The base HTML page injected into the WebView.

Includes:
- A modern CSS design system (dark/light, design tokens)
- A tiny incremental DOM patcher (no external deps, handles focus preservation)
- The Python↔JS bridge wiring
"""

# ---------------------------------------------------------------------------
# Embedded CSS design system
# ---------------------------------------------------------------------------
_CSS = """
/* ── Reset ─────────────────────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html, body { height: 100%; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
                 Helvetica, Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
    font-size: 15px;
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}

/* ── Design tokens — Light theme ────────────────────────────────────────── */
:root {
    --bg:              #f2f2f7;
    --surface:         #ffffff;
    --surface-2:       #f5f5f7;
    --primary:         #6366f1;
    --primary-h:       #4f46e5;
    --primary-light:   #e0e7ff;
    --text:            #1c1c1e;
    --text-2:          #6e6e73;
    --border:          #d1d1d6;
    --border-focus:    #6366f1;
    --danger:          #ef4444;
    --danger-light:    #fee2e2;
    --success:         #22c55e;
    --success-light:   #dcfce7;
    --warning:         #f59e0b;
    --warning-light:   #fef3c7;
    --mono:            'SF Mono','Cascadia Code',Consolas,monospace;
    --r:               10px;
    --r-sm:            6px;
    --r-lg:            16px;
    --shadow:          0 1px 3px rgba(0,0,0,.06), 0 4px 14px rgba(0,0,0,.08);
    --shadow-sm:       0 1px 2px rgba(0,0,0,.06);
    --shadow-lg:       0 8px 32px rgba(0,0,0,.12);
    --t:               0.15s ease;
}

/* ── Dark theme ─────────────────────────────────────────────────────────── */
@media (prefers-color-scheme: dark) {
    :root {
        --bg:            #1c1c1e;
        --surface:       #2c2c2e;
        --surface-2:     #3a3a3c;
        --text:          #f5f5f7;
        --text-2:        #98989f;
        --border:        #48484a;
        --primary-light: rgba(99,102,241,0.2);
        --shadow:        0 1px 3px rgba(0,0,0,.3), 0 4px 14px rgba(0,0,0,.4);
    }
}

/* ── Layout ─────────────────────────────────────────────────────────────── */
#guile-app            { min-height: 100vh; }
.guile-col            { display: flex; flex-direction: column; }
.guile-row            { display: flex; flex-direction: row; flex-wrap: nowrap; }
.guile-fill           { flex: 1; }
.guile-scroll         { overflow: auto; }
.guile-wrap           { flex-wrap: wrap; }
.guile-center         { display: flex; align-items: center; justify-content: center; }

/* ── Card ───────────────────────────────────────────────────────────────── */
.guile-card {
    background: var(--surface);
    border-radius: var(--r);
    box-shadow: var(--shadow);
}

/* ── Typography ─────────────────────────────────────────────────────────── */
.guile-text      { color: var(--text); }
.guile-muted     { color: var(--text-2); }
.guile-bold      { font-weight: 600; }
.guile-italic    { font-style: italic; }
.guile-mono      { font-family: var(--mono); }
.guile-underline { text-decoration: underline; }

/* ── Divider ────────────────────────────────────────────────────────────── */
.guile-divider { border: none; border-top: 1px solid var(--border); width: 100%; }

/* ── Badge ──────────────────────────────────────────────────────────────── */
.guile-badge {
    display: inline-flex; align-items: center;
    padding: 2px 8px; border-radius: 99px;
    font-size: 12px; font-weight: 600; white-space: nowrap;
}

/* ── Button ─────────────────────────────────────────────────────────────── */
.guile-btn {
    display: inline-flex; align-items: center; justify-content: center; gap: 6px;
    padding: 8px 18px; border: none; border-radius: var(--r-sm);
    font-size: 14px; font-weight: 600; cursor: pointer;
    transition: background var(--t), box-shadow var(--t), transform var(--t);
    font-family: inherit; white-space: nowrap; user-select: none; outline: none;
}
.guile-btn:active:not(:disabled)          { transform: scale(0.96); }
.guile-btn:disabled                       { opacity: .45; cursor: not-allowed; }
.guile-btn:focus-visible                  { box-shadow: 0 0 0 3px rgba(99,102,241,.35); }
.guile-btn-primary                        { background: var(--primary); color: #fff; }
.guile-btn-primary:hover:not(:disabled)   { background: var(--primary-h); box-shadow: 0 2px 10px rgba(99,102,241,.4); }
.guile-btn-secondary                      { background: var(--border); color: var(--text); }
.guile-btn-secondary:hover:not(:disabled) { background: #c7c7cc; }
.guile-btn-ghost                          { background: transparent; color: var(--primary); }
.guile-btn-ghost:hover:not(:disabled)     { background: var(--primary-light); }
.guile-btn-danger                         { background: var(--danger); color: #fff; }
.guile-btn-danger:hover:not(:disabled)    { background: #dc2626; }
.guile-btn-sm  { padding: 5px 12px; font-size: 13px; }
.guile-btn-lg  { padding: 12px 28px; font-size: 16px; border-radius: var(--r); }
.guile-btn-icon { padding: 8px; aspect-ratio: 1; }

/* ── Input / TextArea ───────────────────────────────────────────────────── */
.guile-field { display: flex; flex-direction: column; gap: 5px; }
.guile-input, .guile-textarea, .guile-select {
    width: 100%; padding: 8px 12px;
    border: 1.5px solid var(--border);
    border-radius: var(--r-sm);
    font-size: 15px; font-family: inherit;
    background: var(--surface); color: var(--text); outline: none;
    transition: border-color var(--t), box-shadow var(--t);
}
.guile-input:focus, .guile-textarea:focus, .guile-select:focus {
    border-color: var(--border-focus);
    box-shadow: 0 0 0 3px rgba(99,102,241,.15);
}
.guile-input:disabled, .guile-textarea:disabled, .guile-select:disabled {
    opacity: .55; cursor: not-allowed; background: var(--surface-2);
}
.guile-textarea { resize: vertical; min-height: 80px; }

/* ── Select ─────────────────────────────────────────────────────────────── */
.guile-select {
    cursor: pointer; appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%236e6e73' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E");
    background-repeat: no-repeat; background-position: right 10px center; padding-right: 36px;
}

/* ── Checkbox ───────────────────────────────────────────────────────────── */
.guile-check-group { display: flex; align-items: center; gap: 9px; cursor: pointer; user-select: none; }
.guile-checkbox {
    width: 18px; height: 18px; border: 2px solid var(--border);
    border-radius: 5px; appearance: none; cursor: pointer;
    background: var(--surface); transition: all var(--t);
    flex-shrink: 0; position: relative;
}
.guile-checkbox:checked { background: var(--primary); border-color: var(--primary); }
.guile-checkbox:checked::after {
    content: ''; position: absolute;
    left: 4px; top: 1px; width: 6px; height: 10px;
    border: 2px solid #fff; border-top: none; border-left: none;
    transform: rotate(45deg);
}
.guile-checkbox:focus-visible { box-shadow: 0 0 0 3px rgba(99,102,241,.25); }

/* ── Progress bar ───────────────────────────────────────────────────────── */
.guile-progress-track {
    height: 6px; background: var(--border); border-radius: 99px; overflow: hidden;
}
.guile-progress-fill {
    height: 100%; background: var(--primary); border-radius: 99px;
    transition: width 0.35s ease;
}

/* ── Slider ─────────────────────────────────────────────────────────────── */
.guile-slider {
    width: 100%; height: 4px; appearance: none; border-radius: 99px;
    background: linear-gradient(to right, var(--primary) 0%, var(--border) 0%);
    outline: none; cursor: pointer; margin: 4px 0;
}
.guile-slider::-webkit-slider-thumb {
    -webkit-appearance: none; width: 18px; height: 18px;
    border-radius: 50%; background: var(--primary);
    box-shadow: 0 0 0 3px var(--surface), 0 0 0 5px var(--primary);
    cursor: pointer; transition: transform var(--t);
}
.guile-slider::-webkit-slider-thumb:active { transform: scale(1.15); }

/* ── Leaflet map container ──────────────────────────────────────────────── */
.guile-map {
    border-radius: var(--r);
    overflow: hidden;
    width: 100%;
    background: var(--surface-2);
}
.guile-map-canvas { width: 100%; }
.guile-map-canvas .leaflet-container { width: 100%; height: 100%; }


/* ── Table ──────────────────────────────────────────────────────────────── */
.guile-table-wrap {
    width: 100%; overflow-x: auto;
    border-radius: var(--r); border: 1px solid var(--border);
}
.guile-table {
    width: 100%; border-collapse: collapse;
    font-size: 14px;
}
.guile-th {
    background: var(--surface-2); color: var(--text-2);
    font-size: 12px; font-weight: 600; text-transform: uppercase;
    letter-spacing: .04em; padding: 10px 14px;
    text-align: left; white-space: nowrap;
    border-bottom: 1px solid var(--border);
    position: sticky; top: 0; z-index: 1;
}
.guile-tr { border-bottom: 1px solid var(--border); }
.guile-tr:last-child { border-bottom: none; }
.guile-tr:hover { background: var(--surface-2); }
.guile-td { padding: 10px 14px; color: var(--text); vertical-align: middle; }
.guile-table-empty {
    padding: 24px; text-align: center;
    color: var(--text-2); font-size: 14px;
}
/* ── Scrollbar (WebKit) ─────────────────────────────────────────────────── */
::-webkit-scrollbar       { width: 7px; height: 7px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #a0a0a8; }
"""

# ---------------------------------------------------------------------------
# Embedded JS — incremental DOM patcher + bridge + Leaflet map registry
# ---------------------------------------------------------------------------
_JS = """
// ── Incremental DOM patcher ───────────────────────────────────────────────
// Walks old/new DOM trees and surgically patches only what changed.
// data-guile-preserve — skip children (Leaflet owns that subtree)
function _guilePatch(oldNode, newNode) {
    if (oldNode.nodeType === 3) {
        if (oldNode.nodeValue !== newNode.nodeValue)
            oldNode.nodeValue = newNode.nodeValue;
        return;
    }

    var isPreserved = oldNode.getAttribute &&
                      oldNode.getAttribute('data-guile-preserve');

    var isFocused = (oldNode === document.activeElement);
    var savedValue = isFocused ? oldNode.value : undefined;

    // Sync attributes
    var na = newNode.attributes || [], oa = oldNode.attributes || [];
    for (var i = 0; i < na.length; i++) {
        var a = na[i];
        if (oldNode.getAttribute(a.name) !== a.value)
            oldNode.setAttribute(a.name, a.value);
    }
    for (var i = oa.length - 1; i >= 0; i--) {
        if (!newNode.hasAttribute(oa[i].name))
            oldNode.removeAttribute(oa[i].name);
    }
    if (savedValue !== undefined) oldNode.value = savedValue;

    if (isPreserved) return;

    // Sync children
    var oc = Array.from(oldNode.childNodes);
    var nc = Array.from(newNode.childNodes);
    var max = Math.max(oc.length, nc.length);
    for (var i = 0; i < max; i++) {
        if (i >= nc.length) {
            oldNode.removeChild(oc[i]);
        } else if (i >= oc.length) {
            oldNode.appendChild(nc[i].cloneNode(true));
        } else if (oc[i].nodeType !== nc[i].nodeType ||
                   oc[i].tagName !== nc[i].tagName ||
                   (oc[i].getAttribute &&
                    oc[i].getAttribute('id') !==
                    (nc[i].getAttribute && nc[i].getAttribute('id')))) {
            oldNode.replaceChild(nc[i].cloneNode(true), oc[i]);
        } else {
            _guilePatch(oc[i], nc[i]);
        }
    }
}

// ── Leaflet map registry ──────────────────────────────────────────────────
var _guileMaps = {};

function _guileSyncMaps() {
    if (typeof L === 'undefined') return;
    document.querySelectorAll('[data-guile-map]').forEach(function(el) {
        var id      = el.id;
        var cfg     = JSON.parse(el.getAttribute('data-guile-map'));
        var cfgJson = JSON.stringify(cfg);

        if (!_guileMaps[id]) {
            var canvas = el.querySelector('.guile-map-canvas');
            if (!canvas) return;
            var map = L.map(canvas, {zoomControl: true}).setView(cfg.center, cfg.zoom);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap contributors', maxZoom: 19
            }).addTo(map);
            var lg = L.layerGroup().addTo(map);
            _guileMaps[id] = { map: map, layerGroup: lg, cfgJson: cfgJson };
            _guileApplyMarkers(lg, cfg.markers || []);
        } else if (_guileMaps[id].cfgJson !== cfgJson) {
            var entry = _guileMaps[id];
            entry.map.setView(cfg.center, cfg.zoom);
            entry.layerGroup.clearLayers();
            _guileApplyMarkers(entry.layerGroup, cfg.markers || []);
            entry.cfgJson = cfgJson;
        }
    });
}

function _guileApplyMarkers(lg, markers) {
    markers.forEach(function(m) {
        var marker = L.marker(m.latlng);
        if (m.popup)   marker.bindPopup(m.popup);
        if (m.tooltip) marker.bindTooltip(m.tooltip);
        marker.addTo(lg);
    });
}

// ── Guile bridge ─────────────────────────────────────────────────────────
window._guile = {
    update: function(html) {
        var tmp = document.createElement('div');
        tmp.innerHTML = html;
        var newEl = tmp.firstElementChild;
        var oldEl = document.getElementById('guile-app');
        if (!oldEl || !newEl) return;

        // guile-app is the static wrapper div; g1,g2... is the rendered content.
        // On first render oldEl has no children — insert directly.
        // On subsequent renders oldEl has one child (the previous g1) —
        // patch that child against the new g1 so the patcher works at the
        // correct level and IDs align properly.
        if (oldEl.children.length === 0) {
            oldEl.appendChild(newEl.cloneNode(true));
        } else {
            _guilePatch(oldEl.children[0], newEl);
        }
        _guileSyncMaps();
    },
    trigger: function(cid, value) {
        var hasApi = !!(window.pywebview && window.pywebview.api);
        var hasHandle = !!(window.pywebview && window.pywebview.api && window.pywebview.api.handle);
        console.log('[guile] trigger cid=' + cid + ' hasApi=' + hasApi + ' hasHandle=' + hasHandle);
        if (hasHandle) {
            window.pywebview.api.handle(cid,
                value === undefined ? null : value);
        } else {
            console.error('[guile] handle not available — api=' + hasApi);
        }
    }
};

// Belt-and-suspenders: if pywebviewready fires and the api is available,
// call ready() to trigger an extra render. Not required — _on_loaded
// handles the initial render — but helps on some pywebview configurations.
window.addEventListener('pywebviewready', function() {
    try {
        if (window.pywebview && window.pywebview.api && window.pywebview.api.ready)
            window.pywebview.api.ready();
    } catch(e) {}
});
"""

_LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
_LEAFLET_JS  = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"


def get_html(title: str, use_leaflet: bool = False) -> str:
    """Return the full base HTML page for the WebView window."""
    safe_title = title.replace("<", "&lt;").replace(">", "&gt;")

    leaflet_head = (
        f'<link rel="stylesheet" href="{_LEAFLET_CSS}">'
        if use_leaflet else ""
    )
    leaflet_js = (
        f'<script src="{_LEAFLET_JS}"></script>'
        if use_leaflet else ""
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{safe_title}</title>
<style>{_CSS}</style>
{leaflet_head}
</head>
<body>
<div id="guile-app"></div>
{leaflet_js}
<script>{_JS}</script>
</body>
</html>"""
