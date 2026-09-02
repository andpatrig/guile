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
    height: 6px; flex-shrink: 0; background: var(--border); border-radius: 99px; overflow: hidden;
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

/* ── Tabs ───────────────────────────────────────────────────────────────── */
.guile-tabs { width: 100%; }
.guile-tab-strip {
    display: flex; border-bottom: 1px solid var(--border);
    overflow-x: auto; overflow-y: hidden;
}
.guile-tab-btn {
    flex-shrink: 0; padding: 9px 18px;
    font-size: 14px; font-weight: 500; font-family: inherit;
    background: none; border: none;
    border-bottom: 2px solid transparent; margin-bottom: -1px;
    color: var(--text-2); cursor: pointer; white-space: nowrap; outline: none;
    transition: color var(--t), border-color var(--t), background var(--t);
}
.guile-tab-btn:hover:not(.guile-tab-active) { color: var(--text); background: var(--surface-2); }
.guile-tab-active { color: var(--primary); border-bottom-color: var(--primary); font-weight: 600; }
.guile-tab-btn:focus-visible { box-shadow: inset 0 0 0 2px rgba(99,102,241,.3); }

/* ── Leaflet map container ──────────────────────────────────────────────── */
/* Imperative toast injected by gui.notify() — no render cycle */
.guile-notify {
    position: fixed;
    top: 16px;
    left: 50%;
    transform: translateX(-50%);
    border-radius: var(--r);
    padding: 10px 18px;
    font-size: 13px;
    font-weight: 500;
    z-index: 9999;
    display: flex;
    align-items: center;
    gap: 12px;
    box-shadow: 0 4px 16px rgba(0,0,0,.12);
    white-space: nowrap;
    max-width: 480px;
    animation: guile-fade-in .15s ease;
}
@keyframes guile-fade-in {
    from { opacity: 0; transform: translateX(-50%) translateY(-6px); }
    to   { opacity: 1; transform: translateX(-50%) translateY(0); }
}

.guile-map {
    border-radius: var(--r);
    overflow: hidden;
    width: 100%;
    background: var(--surface-2);
}
.guile-map-canvas { width: 100%; }
.guile-map-canvas .leaflet-container { width: 100%; height: 100%; }
/* Permanent on-shape labels (GeoJSON label=, drawn "label") */
.leaflet-tooltip.guile-map-label {
    background: rgba(20,20,22,.82); color: #fff; border: none;
    border-radius: 6px; padding: 2px 8px; font-size: 12px; font-weight: 600;
    box-shadow: 0 1px 4px rgba(0,0,0,.4); white-space: nowrap;
}
.leaflet-tooltip.guile-map-label::before { display: none; }


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
// guile-map elements: attributes are patched (so data-guile-map updates)
// but children are skipped (Leaflet owns that subtree).
function _guilePatch(oldNode, newNode) {
    if (oldNode.nodeType === 3) {
        if (oldNode.nodeValue !== newNode.nodeValue)
            oldNode.nodeValue = newNode.nodeValue;
        return;
    }

    var isPreserved = oldNode.classList &&
                      oldNode.classList.contains('guile-map');

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
    // Focused element: keep what the user is typing. Assigning .value
    // resets the caret even for an identical string, so only assign on a
    // real difference.
    if (savedValue !== undefined && oldNode.value !== savedValue)
        oldNode.value = savedValue;

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

    // Sync live form properties (dirty-value fix).
    // Once the user has interacted with a form control, the browser stops
    // reflecting the value/checked/selected ATTRIBUTES into the displayed
    // state, so attribute patching alone can't apply a Python-side change
    // (e.g. state.set("") to clear a field). Assign the properties
    // explicitly — but never on the focused element, which keeps whatever
    // the user is mid-typing. SELECT runs after the child sync above so
    // the new <option> set is already in place.
    if (!isFocused && oldNode.tagName) {
        var tag = oldNode.tagName;
        if (tag === 'INPUT') {
            if (oldNode.type === 'checkbox' || oldNode.type === 'radio') {
                var chk = newNode.hasAttribute('checked');
                if (oldNode.checked !== chk) oldNode.checked = chk;
            } else {
                var nv = newNode.getAttribute('value');
                if (nv !== null && oldNode.value !== nv) oldNode.value = nv;
            }
        } else if (tag === 'TEXTAREA') {
            if (oldNode.value !== newNode.value) oldNode.value = newNode.value;
        } else if (tag === 'SELECT') {
            var oo = oldNode.options;
            for (var i = 0; i < oo.length; i++) {
                var sel = oo[i].hasAttribute('selected');
                if (oo[i].selected !== sel) oo[i].selected = sel;
            }
        }
    }
}

// ── Leaflet map registry ──────────────────────────────────────────────────

var _guileMaps = {};

// ── Lazy Leaflet loader ───────────────────────────────────────────────────
// The Leaflet <script>/<link> tags are normally injected at startup, when
// the silent probe run of ui() reaches a gui.leaflet() call. But a map that
// only renders conditionally (a non-default tab, behind an if) is invisible
// to that probe — the flag is never set and the map would stay blank
// forever. This loader is the fallback: when a data-guile-map element
// appears and Leaflet (or the draw plugin) is missing, fetch it from the
// CDN, then re-sync.
var _guileLeafletLoading = false;

function _guileLoadCss(href) {
    var l = document.createElement('link');
    l.rel = 'stylesheet'; l.href = href;
    document.head.appendChild(l);
}

function _guileLoadJs(src, onload) {
    var s = document.createElement('script');
    s.src = src;
    s.onload  = onload;
    s.onerror = function() {
        _guileLeafletLoading = false;
        console.error('[guile] failed to load ' + src);
    };
    document.body.appendChild(s);
}

function _guileLoadLeaflet(needDraw) {
    if (_guileLeafletLoading) return;
    _guileLeafletLoading = true;
    var finish = function() {
        _guileLeafletLoading = false;
        // Re-attach events on existing maps: a map created before the draw
        // plugin arrived is skipped by the cfgJson comparison in
        // _guileSyncMaps, so give it its draw control explicitly.
        Object.keys(_guileMaps).forEach(function(id) {
            var entry = _guileMaps[id];
            _guileAttachMapEvents(entry, JSON.parse(entry.cfgJson));
        });
        _guileSyncMaps();
    };
    var loadDraw = function(next) {
        _guileLoadCss('__LEAFLET_DRAW_CSS__');
        _guileLoadJs('__LEAFLET_DRAW_JS__', next);
    };
    if (typeof L === 'undefined') {
        _guileLoadCss('__LEAFLET_CSS__');
        _guileLoadJs('__LEAFLET_JS__', function() {
            if (needDraw) loadDraw(finish); else finish();
        });
    } else if (needDraw) {
        loadDraw(finish);
    } else {
        _guileLeafletLoading = false;
    }
}

// ── Attach / update map-level event listeners ─────────────────────────────
// Called on first creation AND whenever cfgJson changes.
// Compares stored cids to new ones; re-wires only when they differ
// so duplicate listeners never accumulate.
function _guileAttachMapEvents(entry, cfg) {
    var map = entry.map;

    // ── Map background click ──────────────────────────────────────────────
    var newClickCid = cfg.on_click_cid || null;
    if (entry.onClickCid !== newClickCid) {
        map.off('click');
        entry.onClickCid = newClickCid;
        if (newClickCid) {
            (function(cid) {
                map.on('click', function(e) {
                    _guile.trigger(cid, {lat: e.latlng.lat, lng: e.latlng.lng});
                });
            })(newClickCid);
        }
    }

    // ── Pan / zoom end (debounced 150 ms) ────────────────────────────────
    var newMoveCid = cfg.on_move_cid || null;
    if (entry.onMoveCid !== newMoveCid) {
        map.off('moveend');
        entry.onMoveCid = newMoveCid;
        if (newMoveCid) {
            (function(cid) {
                var _moveTimer = null;
                map.on('moveend', function() {
                    clearTimeout(_moveTimer);
                    _moveTimer = setTimeout(function() {
                        var c = map.getCenter();
                        _guile.trigger(cid, {
                            center: [c.lat, c.lng],
                            zoom:   map.getZoom()
                        });
                    }, 150);
                });
            })(newMoveCid);
        }
    }

    // ── Shape callbacks ──────────────────────────────────────────────────
    // Cids live on the entry and are read at fire time, so a re-render that
    // adds or drops a callback never needs the listeners re-wired.
    entry.shapeCid       = cfg.on_shape_cid        || null;
    entry.shapeEditCid   = cfg.on_shape_edit_cid   || null;
    entry.shapeDeleteCid = cfg.on_shape_delete_cid || null;
    entry.shapeClickCid  = cfg.on_shape_click_cid  || null;
    entry.shapeHoverCid  = cfg.on_shape_hover_cid  || null;

    // ── Draw toolbar (Leaflet.draw) — set up once per map instance ───────
    var drawTools = cfg.draw || [];
    if (drawTools.length > 0 && !entry.drawControl
            && typeof L.Control.Draw !== 'undefined') {
        var drawnItems = _guileDrawnItems(entry);

        // Build per-tool options: tool enabled = {}, disabled = false
        var toolOpts = {};
        ['rectangle', 'polygon', 'polyline', 'circle', 'marker'].forEach(function(t) {
            toolOpts[t] = drawTools.indexOf(t) >= 0 ? {} : false;
        });
        toolOpts.circlemarker = false; // always off (rarely useful)

        var drawControl = new L.Control.Draw({
            draw:   toolOpts,
            edit:   { featureGroup: drawnItems }
        });
        map.addControl(drawControl);
        entry.drawControl = drawControl;

        map.on('draw:created', function(e) {
            var layer = e.layer;
            layer._guileType = e.layerType;
            // Keep it visible now; with drawn= Python re-renders it with an
            // id on the next pass, without drawn= this copy is the record.
            drawnItems.addLayer(layer);
            if (entry.shapeCid) {
                _guile.trigger(entry.shapeCid, {
                    type: e.layerType,
                    coords: _guileShapeCoords(e.layerType, layer)
                });
            }
        });
        // Edit / delete toolbars fire once per affected layer on Save.
        map.on('draw:edited', function(e) {
            if (!entry.shapeEditCid) return;
            e.layers.eachLayer(function(l) {
                _guile.trigger(entry.shapeEditCid, {
                    id: l._guileId || null, type: l._guileType,
                    coords: _guileShapeCoords(l._guileType, l)
                });
            });
        });
        map.on('draw:deleted', function(e) {
            if (!entry.shapeDeleteCid) return;
            e.layers.eachLayer(function(l) {
                _guile.trigger(entry.shapeDeleteCid, {id: l._guileId || null});
            });
        });
    }
}

// ── Drawn shapes ──────────────────────────────────────────────────────────
// One FeatureGroup holds everything drawn; Leaflet.draw's edit toolbar
// operates on it. Created lazily so drawn= also works with draw=False
// (read-only display) and before the draw plugin has loaded.
function _guileDrawnItems(entry) {
    if (!entry.drawnItems) {
        entry.drawnItems = new L.FeatureGroup().addTo(entry.map);
    }
    return entry.drawnItems;
}

// Layer → plain coords: the format on_shape hands to Python and drawn=
// accepts back. [[lat,lng],...] for polygon/rectangle/polyline,
// {lat,lng,radius} for circle, {lat,lng} for marker.
function _guileShapeCoords(type, layer) {
    if (type === 'rectangle' || type === 'polygon' || type === 'polyline') {
        var lls = layer.getLatLngs();
        // polygon/rectangle: [[pt,...]], polyline: [pt,...]
        var pts = (lls.length === 1 && Array.isArray(lls[0])) ? lls[0] : lls;
        return pts.map(function(ll) { return [ll.lat, ll.lng]; });
    }
    var c = layer.getLatLng();
    if (type === 'circle') {
        return {lat: c.lat, lng: c.lng, radius: layer.getRadius()};
    }
    return {lat: c.lat, lng: c.lng};
}

// Inverse: a drawn= entry → Leaflet layer (types Leaflet.draw can edit).
function _guileShapeLayer(shape, style) {
    var t = shape.type, c = shape.coords;
    if (t === 'polygon')   return L.polygon(c, style);
    if (t === 'polyline')  return L.polyline(c, style);
    if (t === 'rectangle') return L.rectangle(L.latLngBounds(c), style);
    if (t === 'circle')    return L.circle([c.lat, c.lng],
                                    Object.assign({radius: c.radius}, style));
    if (t === 'marker')    return L.marker([c.lat, c.lng]);
    return null;
}

function _guileLabel(layer, text) {
    layer.bindTooltip(String(text), {
        permanent: true, className: 'guile-map-label',
        direction: (layer instanceof L.Marker) ? 'top' : 'center'
    });
}

// Rebuild the drawn layer from Python's list (drawn=). Called only when
// the list or draw_style actually changed.
function _guileApplyDrawn(entry, cfg) {
    var items = _guileDrawnItems(entry);
    items.clearLayers();
    (cfg.drawn || []).forEach(function(shape) {
        var style = Object.assign({}, cfg.draw_style || {}, shape.style || {});
        var layer = _guileShapeLayer(shape, style);
        if (!layer) return;
        layer._guileId   = shape.id;
        layer._guileType = shape.type;
        if (shape.label) _guileLabel(layer, shape.label);
        layer.on('click', function(e) {
            if (!entry.shapeClickCid) return;      // let map on_click fire
            L.DomEvent.stopPropagation(e);
            _guile.trigger(entry.shapeClickCid, {id: shape.id});
        });
        layer.on('mouseover', function() {
            if (entry.shapeHoverCid) _guile.trigger(entry.shapeHoverCid, {id: shape.id});
        });
        layer.on('mouseout', function() {
            if (entry.shapeHoverCid) _guile.trigger(entry.shapeHoverCid, null);
        });
        items.addLayer(layer);
    });
}

function _guileSyncMaps() {
    var els = document.querySelectorAll('[data-guile-map]');
    if (!els.length) return;

    // Do any of the maps on the page need the draw plugin?
    var needDraw = false;
    els.forEach(function(el) {
        var cfg = JSON.parse(el.getAttribute('data-guile-map'));
        if (cfg.draw && cfg.draw.length) needDraw = true;
    });

    // Assets missing (conditionally-rendered map the startup probe never
    // saw) → fetch them; the loader re-runs this function when done.
    if (typeof L === 'undefined' ||
            (needDraw && typeof L.Control.Draw === 'undefined')) {
        _guileLoadLeaflet(needDraw);
        if (typeof L === 'undefined') return;
        // Leaflet itself is present — create maps now; draw controls
        // attach on the re-sync after the plugin finishes loading.
    }

    els.forEach(function(el) {
        var id      = el.id;
        var cfg     = JSON.parse(el.getAttribute('data-guile-map'));
        var cfgJson = JSON.stringify(cfg);

        // Orphan guard. The patcher replaces a whole subtree when an
        // ancestor's id changes (e.g. an unkeyed sidebar element appears or
        // disappears, shifting auto-numbered ids). The map element keeps its
        // keyed id, but its canvas is now a fresh clone while the registry
        // still points at a Leaflet instance on the detached node — blank
        // map, and updates go to the orphan. Detect it, dispose, and rebuild
        // below, carrying the user's current view across.
        var keepView = null;
        if (_guileMaps[id] &&
                !document.body.contains(_guileMaps[id].map.getContainer())) {
            var oldMap = _guileMaps[id].map;
            keepView = {center: oldMap.getCenter(), zoom: oldMap.getZoom()};
            oldMap.remove();
            delete _guileMaps[id];
        }

        if (!_guileMaps[id]) {
            var canvas = el.querySelector('.guile-map-canvas');
            if (!canvas) return;
            var map = L.map(canvas, {zoomControl: true});
            if (keepView) map.setView(keepView.center, keepView.zoom);
            else          map.setView(cfg.center, cfg.zoom);
            // Image overlays get their own pane between the tile pane (200)
            // and the overlay pane (400) so they always sit under GeoJSON
            // vectors and markers, whatever order the layers were created.
            map.createPane('guile-image');
            map.getPane('guile-image').style.zIndex = 350;
            var lg = L.layerGroup().addTo(map);
            var entry = {
                map: map, layerGroup: lg, cfgJson: cfgJson,
                onClickCid: null, onMoveCid: null,
                drawControl: null, drawnItems: null,
                tileLayers: [], tilesJson: null,
                overlayLayers: [], overlaysJson: null,
                drawnJson: null
            };
            _guileMaps[id] = entry;
            _guileApplyTiles(entry, cfg.tiles);
            entry.tilesJson = JSON.stringify(cfg.tiles || []);
            _guileApplyOverlays(entry, cfg.layers);
            entry.overlaysJson = JSON.stringify(cfg.layers || []);
            _guileAttachMapEvents(entry, cfg);
            if (cfg.drawn) _guileApplyDrawn(entry, cfg);
            entry.drawnJson = JSON.stringify([cfg.drawn || null, cfg.draw_style || null]);
            _guileApplyMarkers(lg, cfg.markers || []);
        } else if (_guileMaps[id].cfgJson !== cfgJson) {
            var entry = _guileMaps[id];
            entry.map.setView(cfg.center, cfg.zoom);
            // Rebuild tiles / overlays only when they actually changed, so
            // panning or adding markers doesn't flash the base map or
            // re-decode an embedded image.
            var newTilesJson = JSON.stringify(cfg.tiles || []);
            if (entry.tilesJson !== newTilesJson) {
                _guileApplyTiles(entry, cfg.tiles);
                entry.tilesJson = newTilesJson;
            }
            var newOverlaysJson = JSON.stringify(cfg.layers || []);
            if (entry.overlaysJson !== newOverlaysJson) {
                _guileApplyOverlays(entry, cfg.layers);
                entry.overlaysJson = newOverlaysJson;
            }
            entry.layerGroup.clearLayers();
            _guileAttachMapEvents(entry, cfg);
            // drawn=None (null) means the JS layer owns shapes: leave it be.
            var newDrawnJson = JSON.stringify([cfg.drawn || null, cfg.draw_style || null]);
            if (entry.drawnJson !== newDrawnJson) {
                if (cfg.drawn) _guileApplyDrawn(entry, cfg);
                entry.drawnJson = newDrawnJson;
            }
            _guileApplyMarkers(entry.layerGroup, cfg.markers || []);
            entry.cfgJson = cfgJson;
        }
    });
}

// Replace an entry's base tile layers. Tiles live in Leaflet's tilePane
// (below markers/shapes regardless of add order), so switching them never
// covers your data.
function _guileApplyTiles(entry, tiles) {
    (entry.tileLayers || []).forEach(function(l) {
        entry.map.removeLayer(l);
    });
    entry.tileLayers = [];
    (tiles || []).forEach(function(t) {
        var layer = L.tileLayer(t.url, t.options || {});
        layer.addTo(entry.map);
        entry.tileLayers.push(layer);
    });
}

// Replace an entry's overlay layers (gui.ImageOverlay / TileOverlay /
// GeoJSON). Drawn in list order. Stacking is fixed by pane:
//   base tiles (tilePane, zIndex 1) < tile overlays (tilePane, zIndex 10)
//   < images (guile-image pane) < GeoJSON (overlayPane) < markers.
function _guileApplyOverlays(entry, layers) {
    // Cross-fade: add the new layers first and remove the previous ones only
    // once the new raster layers (tiles, images) have loaded — or after a
    // short fallback — so switching a TileOverlay URL or an ImageOverlay
    // never flashes the base map through the gap. Vector-only changes have
    // nothing to wait for and swap immediately. Removing a layer that is
    // already gone is a no-op in Leaflet, so overlapping calls are safe.
    var oldLayers = entry.overlayLayers || [];
    entry.overlayLayers = [];
    var pending = 0, removed = false;
    function removeOld() {
        if (removed) return;
        removed = true;
        oldLayers.forEach(function(l) { entry.map.removeLayer(l); });
    }
    (layers || []).forEach(function(cfg) {
        var layer = null;
        if (cfg.type === 'image') {
            layer = L.imageOverlay(cfg.src, cfg.bounds,
                                   {opacity: cfg.opacity, pane: 'guile-image'});
        } else if (cfg.type === 'tiles') {
            // zIndex 10 keeps the overlay above base tiles even after a
            // base-map switch re-adds them.
            layer = L.tileLayer(cfg.url,
                                Object.assign({zIndex: 10}, cfg.options || {}));
        } else if (cfg.type === 'geojson') {
            layer = L.geoJSON(cfg.data, {
                style: function() { return cfg.style || {}; },
                onEachFeature: function(feature, lyr) {
                    var props = feature.properties || {};
                    if (cfg.popup && props[cfg.popup] !== undefined
                            && props[cfg.popup] !== null) {
                        lyr.bindPopup(String(props[cfg.popup]));
                    }
                    if (cfg.label && props[cfg.label] !== undefined
                            && props[cfg.label] !== null) {
                        _guileLabel(lyr, props[cfg.label]);
                    }
                    if (cfg.cid) {
                        lyr.on('click', function(e) {
                            L.DomEvent.stopPropagation(e); // not also map click
                            _guile.trigger(cfg.cid, props);
                        });
                    }
                    if (cfg.hover_cid) {
                        lyr.on('mouseover', function() { _guile.trigger(cfg.hover_cid, props); });
                        lyr.on('mouseout',  function() { _guile.trigger(cfg.hover_cid, null); });
                    }
                }
            });
        }
        if (layer) {
            if (cfg.type === 'tiles' || cfg.type === 'image') {
                pending++;
                layer.once('load', function() {
                    if (--pending <= 0) removeOld();
                });
            }
            layer.addTo(entry.map);
            entry.overlayLayers.push(layer);
        }
    });
    if (!oldLayers.length) return;
    if (pending === 0) removeOld();
    else setTimeout(removeOld, 2000);   // fallback if 'load' never fires
}

function _guileApplyMarkers(lg, markers) {
    markers.forEach(function(m) {
        var marker = L.marker(m.latlng);
        if (m.popup)   marker.bindPopup(m.popup);
        if (m.tooltip) marker.bindTooltip(m.tooltip);
        // Wire marker click if a Python callback was registered.
        if (m.cid) {
            (function(cid) {
                marker.on('click', function(e) {
                    L.DomEvent.stopPropagation(e); // don't also fire map click
                    _guile.trigger(cid, null);
                });
            })(m.cid);
        }
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
        // Invalidate any map that is now visible — fixes blank maps in tabs.
        // Leaflet measures the container at init time; if the tab was hidden
        // it gets 0x0 and never recovers until invalidateSize() is called.
        Object.values(_guileMaps).forEach(function(entry) {
            entry.map.invalidateSize();
        });
    },
    trigger: function(cid, value) {
        if (window.pywebview && window.pywebview.api && window.pywebview.api.handle) {
            window.pywebview.api.handle(cid,
                value === undefined ? null : value);
        } else {
            console.error('[guile] pywebview api not available');
        }
    },
    // silent: update Python state without triggering a re-render.
    // Used by multiselect onchange so variables.value stays current
    // while the user is mid-selection, without replacing the DOM element.
    silent: function(cid, value) {
        if (window.pywebview && window.pywebview.api && window.pywebview.api.silent_update) {
            window.pywebview.api.silent_update(cid,
                value === undefined ? null : value);
        }
    }
};

// Sync maps after the initial render completes.
// _guile.update() handles subsequent renders; this covers the first load.
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(_guileSyncMaps, 100);
});
"""

_LEAFLET_CSS      = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
_LEAFLET_JS       = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
_LEAFLET_DRAW_CSS = "https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.css"
_LEAFLET_DRAW_JS  = "https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.js"


def get_html(title: str, use_leaflet: bool = False,
             use_leaflet_draw: bool = False) -> str:
    """Return the full base HTML page for the WebView window."""
    safe_title = title.replace("<", "&lt;").replace(">", "&gt;")

    # Fast path: when the startup probe saw a gui.leaflet() call, include
    # the assets directly so the map appears without a lazy-load round trip.
    # Maps the probe missed (conditional tabs) are covered by the lazy
    # loader in _JS, which fetches these same URLs on demand.
    leaflet_head = ""
    leaflet_js   = ""
    if use_leaflet:
        leaflet_head = f'<link rel="stylesheet" href="{_LEAFLET_CSS}">'
        leaflet_js   = f'<script src="{_LEAFLET_JS}"></script>'
        if use_leaflet_draw:
            leaflet_head += f'\n<link rel="stylesheet" href="{_LEAFLET_DRAW_CSS}">'
            leaflet_js   += f'\n<script src="{_LEAFLET_DRAW_JS}"></script>'

    js = (_JS
          .replace("__LEAFLET_CSS__",      _LEAFLET_CSS)
          .replace("__LEAFLET_JS__",       _LEAFLET_JS)
          .replace("__LEAFLET_DRAW_CSS__", _LEAFLET_DRAW_CSS)
          .replace("__LEAFLET_DRAW_JS__",  _LEAFLET_DRAW_JS))

    return f"""<!DOCTYPE html>
<html lang="en-GB">
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
<script>{js}</script>
</body>
</html>"""
