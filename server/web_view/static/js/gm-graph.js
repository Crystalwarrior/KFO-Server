/**
 * gm-graph.js
 * GraphRenderer is a pure rendering component (composed into
 * AreasGraphTab, not inherited) that draws the hub's area graph as
 * hand-rolled SVG: areas are nodes, area links are directed edges. No
 * external graph library.
 *
 * Layout: a deterministic left-to-right grid, areas ordered by area id,
 * wrapping into rows as the container width requires. New areas (which
 * always sort last by id) therefore always land to the right of / below
 * existing ones, never to the left. Per-node manual drag offsets are
 * layered on top of the computed grid position and persisted in
 * localStorage per hub.
 *
 * Viewing: wheel-zoom (centered on the cursor) and click-drag pan are
 * implemented via a single <g class="gr-viewport"> transform, with
 * +/-/fit/reset-view/reset-layout controls overlaid on the graph
 * container. A ResizeObserver keeps the viewBox in sync with the actual
 * pixel size of the container so layout never misaligns on resize.
 */

const GR_SVG_NS = 'http://www.w3.org/2000/svg';
const GR_XLINK_NS = 'http://www.w3.org/1999/xlink';

function grEl(tag, attrs) {
    const el = document.createElementNS(GR_SVG_NS, tag);
    if (attrs) {
        for (const key in attrs) {
            const value = attrs[key];
            if (value === undefined || value === null) continue;
            el.setAttribute(key, value);
        }
    }
    return el;
}

class GraphRenderer {
    constructor(svgElement, options) {
        this._svg = svgElement;
        this._onNodeClick = (options && options.onNodeClick) || (() => {});
        this._thumbBaseUrl = '';
        this._localContent = null;
        this._clientFolders = {}; // client_id -> character folder name

        // Per-character-folder icon resolution cache (B3): resolving an
        // icon goes through GMLocalContent (IndexedDB lookups / Image()
        // reachability probes for URL bases), which is not free -- with a
        // 4s poll cycle rebuilding every node's chips on every reload,
        // re-resolving on every render would hammer it needlessly. Settled
        // results (including "no icon") are cached for the lifetime of
        // this renderer / until setLocalContent() swaps the source; in-
        // flight lookups are deduped so concurrent renders share one call.
        this._charIconCache = new Map();   // folder -> url|null
        this._charIconPending = new Map(); // folder -> Promise<url|null>

        this._nodes = new Map();       // area_id -> {area, x, y}
        this._baseLayout = new Map();  // area_id -> {x, y} grid position (no manual offset)
        this._offsets = new Map();     // offsetKey -> {x, y} manual drag offsets
        this._edgePaths = new Map();   // "from->to" -> <path>/<line> element
        this._edgesByNode = new Map(); // area_id -> [{el, fromNode, toNode, kind, curve}]
        this._lastIdSet = '';
        this._lastAreas = [];
        this._hubId = null;

        this._nodeW = 150;
        this._nodeH = 96;
        this._width = 1000;
        this._height = 640;

        this._zoom = 1;
        this._panX = 0;
        this._panY = 0;
        this._minZoom = 0.25;
        this._maxZoom = 3;

        this._draggingNode = null;
        this._panning = null;
        this._resizeRaf = null;

        this._svg.innerHTML = '';
        this._svg.style.touchAction = 'none';
        this._svg.style.cursor = 'grab';
        this._buildDefs();

        this._viewport = grEl('g', { class: 'gr-viewport' });
        this._layerEdges = grEl('g', { class: 'gr-edges' });
        this._layerNodes = grEl('g', { class: 'gr-nodes' });
        this._layerTokens = grEl('g', { class: 'gr-tokens' });
        this._viewport.appendChild(this._layerEdges);
        this._viewport.appendChild(this._layerNodes);
        this._viewport.appendChild(this._layerTokens);
        this._svg.appendChild(this._viewport);

        this._buildControls();
        this._measure();

        if (typeof ResizeObserver !== 'undefined' && this._svg.parentElement) {
            this._resizeObserver = new ResizeObserver(() => this._onResize());
            this._resizeObserver.observe(this._svg.parentElement);
        } else {
            this._resizeObserver = null;
            window.addEventListener('resize', () => this._onResize());
        }

        this._bindPanZoom();
        this._applyViewportTransform();
    }

    setThumbBaseUrl(url) { this._thumbBaseUrl = url || ''; }

    setLocalContent(localContent) {
        this._localContent = localContent || null;
        // A different resolution source can legitimately answer 'no icon'
        // vs 'has icon' differently for the same folder name, so stale
        // cached results must not survive the swap.
        this._charIconCache.clear();
        this._charIconPending.clear();
        // Per-item invalidation (a GM setting/clearing a per-character icon
        // override, or a background override) is handled by the owning tab
        // subscribing to `localContent` and calling clearCharIconCache()/
        // refreshBackgroundThumbs() below -- see AreasGraphTab, which is
        // this renderer's only consumer.
    }

    /** Invalidate one (or, when `folderOrNull` is falsy, every) cached
     * char_icon resolution and immediately re-render the client chips.
     * GMLocalContent.setOverride/clearOverride (used by the Characters and
     * Clients tabs) invalidate GMLocalContent's own resolve cache, but this
     * renderer keeps a separate wrapper cache on top of it (see
     * _resolveCharIcon doc) for render-loop performance -- without this,
     * that wrapper cache would keep serving a character's old icon (or "no
     * icon") after a GM uploads/clears a per-character icon override, until
     * the next poll cycle (or a full page reload) happened to re-render it. */
    clearCharIconCache(folderOrNull) {
        if (folderOrNull) {
            this._charIconCache.delete(folderOrNull);
            this._charIconPending.delete(folderOrNull);
        } else {
            this._charIconCache.clear();
            this._charIconPending.clear();
        }
        if (this._lastAreas.length) this._render(this._lastAreas);
    }

    /** Re-render node thumbnails using the most recently pushed data.
     * Background thumbnails have no separate renderer-level cache (each
     * render re-resolves via `GMLocalContent.resolve('background', ...)`,
     * whose own resolve cache GMLocalContent already invalidates on
     * override/base-source changes) -- so nothing needs clearing here, only
     * a fresh render pass so the new result is picked up immediately
     * instead of waiting for the next poll cycle. */
    refreshBackgroundThumbs() {
        if (this._lastAreas.length) this._render(this._lastAreas);
    }

    /** Cached, deduped char_icon lookup keyed by character folder name
     * (see setClientFolders doc). Returns a Promise<?string>; settled
     * results are memoized so a 4s poll-driven re-render never re-asks
     * GMLocalContent for a folder it already resolved. */
    _resolveCharIcon(folder) {
        if (!folder) return Promise.resolve(null);
        if (this._charIconCache.has(folder)) return Promise.resolve(this._charIconCache.get(folder));
        if (this._charIconPending.has(folder)) return this._charIconPending.get(folder);
        const base = (this._localContent && typeof this._localContent.resolve === 'function')
            ? this._localContent.resolve('char_icon', folder).catch(() => null)
            : Promise.resolve(null);
        const pending = base.then((url) => {
            this._charIconCache.set(folder, url || null);
            this._charIconPending.delete(folder);
            return url || null;
        });
        this._charIconPending.set(folder, pending);
        return pending;
    }

    /** Join a (possibly slash-less) base URL with a path segment without
     * producing a doubled or missing '/'. */
    _urlJoin(base, path) {
        if (!base) return '';
        return base.endsWith('/') ? `${base}${path}` : `${base}/${path}`;
    }

    /** client_id -> character folder name map (see gm-areas-tab.js's
     * _loadClientFolders()). GMLocalContent.getClientColor() is keyed by
     * folder name (persistent across client-id reuse, matching how the
     * Clients tab sets colors), not by client id, so this lookup is what
     * lets a marker here show the same color a GM picked there. */
    setClientFolders(map) { this._clientFolders = map || {}; }

    // --- overlay controls ------------------------------------------------

    _buildControls() {
        const wrap = this._svg.parentElement;
        if (!wrap) return;
        const controls = document.createElement('div');
        controls.className = 'gr-controls';
        const mk = (label, title, fn) => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'gr-ctrl-btn';
            btn.textContent = label;
            btn.title = title;
            btn.addEventListener('click', (e) => { e.stopPropagation(); fn(); });
            controls.appendChild(btn);
            return btn;
        };
        mk('+', 'Zoom in', () => this.zoomBy(1.25));
        mk('−', 'Zoom out', () => this.zoomBy(0.8));
        mk('⤡', 'Fit graph to view', () => this.fit());
        mk('⟳', 'Reset zoom & pan', () => this.resetView());
        mk('✕', 'Reset manual layout for this hub', () => this.resetOffsets());
        wrap.appendChild(controls);
        this._controlsEl = controls;
    }

    // --- measurement / resize ---------------------------------------------

    _measure() {
        const rect = this._svg.getBoundingClientRect();
        if (rect.width > 100) this._width = rect.width;
        if (rect.height > 100) this._height = rect.height;
    }

    _onResize() {
        if (this._resizeRaf) return;
        this._resizeRaf = requestAnimationFrame(() => {
            this._resizeRaf = null;
            this._measure();
            if (this._lastAreas && this._lastAreas.length) {
                this._runLayout(this._lastAreas);
                this._render(this._lastAreas);
            } else {
                this._svg.setAttribute('viewBox', `0 0 ${Math.max(this._width, 300)} ${Math.max(this._height, 300)}`);
            }
        });
    }

    _buildDefs() {
        const defs = grEl('defs');
        const marker = grEl('marker', {
            id: 'gr-arrow', viewBox: '0 0 10 10', refX: 9, refY: 5,
            markerWidth: 7, markerHeight: 7, orient: 'auto-start-reverse',
        });
        marker.appendChild(grEl('path', { d: 'M0,0 L10,5 L0,10 z', class: 'gr-arrowhead' }));
        defs.appendChild(marker);
        this._svg.appendChild(defs);
    }

    // --- pan / zoom ---------------------------------------------------------

    _bindPanZoom() {
        this._svg.addEventListener('wheel', (e) => {
            e.preventDefault();
            const rect = this._svg.getBoundingClientRect();
            const mx = e.clientX - rect.left;
            const my = e.clientY - rect.top;
            const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12;
            this._zoomAt(mx, my, factor);
        }, { passive: false });

        this._svg.addEventListener('pointerdown', (e) => {
            if (e.button !== 0) return;
            if (e.target.closest && e.target.closest('.gr-node')) return;
            // Without this, a drag that starts on/crosses a <text> label
            // (node names, thumb captions, chip counts) is interpreted by
            // the browser as a text-selection drag instead of a pan --
            // preventDefault suppresses that native selection gesture.
            e.preventDefault();
            this._panning = {
                pointerId: e.pointerId,
                startClientX: e.clientX, startClientY: e.clientY,
                startPanX: this._panX, startPanY: this._panY,
            };
            try { this._svg.setPointerCapture(e.pointerId); } catch (err) { /* ignore */ }
            this._svg.classList.add('gr-panning');
            this._svg.style.cursor = 'grabbing';
        });
        this._svg.addEventListener('pointermove', (e) => {
            if (!this._panning || this._panning.pointerId !== e.pointerId) return;
            const dx = e.clientX - this._panning.startClientX;
            const dy = e.clientY - this._panning.startClientY;
            this._panX = this._panning.startPanX + dx;
            this._panY = this._panning.startPanY + dy;
            this._applyViewportTransform();
        });
        const endPan = (e) => {
            if (!this._panning || (e && this._panning.pointerId !== e.pointerId)) return;
            this._panning = null;
            this._svg.classList.remove('gr-panning');
            this._svg.style.cursor = 'grab';
        };
        this._svg.addEventListener('pointerup', endPan);
        this._svg.addEventListener('pointercancel', endPan);
        this._svg.addEventListener('pointerleave', (e) => { if (this._panning) endPan(e); });
    }

    _zoomAt(screenX, screenY, factor) {
        const newZoom = Math.min(this._maxZoom, Math.max(this._minZoom, this._zoom * factor));
        if (newZoom === this._zoom) return;
        const contentX = (screenX - this._panX) / this._zoom;
        const contentY = (screenY - this._panY) / this._zoom;
        this._panX = screenX - contentX * newZoom;
        this._panY = screenY - contentY * newZoom;
        this._zoom = newZoom;
        this._applyViewportTransform();
    }

    zoomBy(factor) { this._zoomAt(this._width / 2, this._height / 2, factor); }

    fit() {
        if (this._nodes.size === 0) { this.resetView(); return; }
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        this._nodes.forEach((node) => {
            minX = Math.min(minX, node.x - this._nodeW / 2);
            minY = Math.min(minY, node.y - this._nodeH / 2);
            maxX = Math.max(maxX, node.x + this._nodeW / 2);
            maxY = Math.max(maxY, node.y + this._nodeH / 2);
        });
        const pad = 40;
        const bw = Math.max(1, maxX - minX + pad * 2);
        const bh = Math.max(1, maxY - minY + pad * 2);
        const zoom = Math.min(this._maxZoom, Math.max(this._minZoom, Math.min(this._width / bw, this._height / bh)));
        this._zoom = zoom;
        this._panX = this._width / 2 - ((minX + maxX) / 2) * zoom;
        this._panY = this._height / 2 - ((minY + maxY) / 2) * zoom;
        this._applyViewportTransform();
    }

    resetView() {
        this._zoom = 1;
        this._panX = 0;
        this._panY = 0;
        this._applyViewportTransform();
    }

    _applyViewportTransform() {
        this._viewport.setAttribute('transform', `translate(${this._panX}, ${this._panY}) scale(${this._zoom})`);
    }

    // --- data -----------------------------------------------------------

    /**
     * Push a fresh hub snapshot ({hub_id, hub_name, areas}) from
     * GET /api/gm/areas. Node positions are kept stable across
     * occupancy-only updates; the grid layout is only recomputed when the
     * set of area ids actually changed. Zoom/pan/manual offsets and any
     * in-flight token animation are always preserved across calls.
     */
    setData(hubData) {
        const areas = hubData.areas || [];
        this._lastAreas = areas;

        if (this._hubId !== hubData.hub_id) {
            this._loadOffsets(hubData.hub_id);
        }

        const idSet = areas.map((a) => a.id).sort((a, b) => a - b).join(',');
        const structuralChange = idSet !== this._lastIdSet;
        this._lastIdSet = idSet;

        const prevPositions = new Map();
        this._nodes.forEach((node, id) => prevPositions.set(id, { x: node.x, y: node.y }));

        this._nodes = new Map();
        areas.forEach((area) => {
            const prev = prevPositions.get(area.id);
            this._nodes.set(area.id, {
                area,
                x: prev ? prev.x : this._width / 2,
                y: prev ? prev.y : this._height / 2,
            });
        });

        if (structuralChange || prevPositions.size === 0) {
            this._runLayout(areas);
        }
        this._render(areas);
    }

    // --- offset persistence (per-area manual drag positions) -------------

    _offsetKey(area) {
        if (area && area.name && String(area.name).trim()) return `n:${area.name}`;
        return `i:${area ? area.id : ''}`;
    }

    _offsetsStorageKey(hubId) { return `gm-graph-offsets:${hubId}`; }

    _loadOffsets(hubId) {
        this._hubId = hubId;
        this._offsets = new Map();
        try {
            const raw = localStorage.getItem(this._offsetsStorageKey(hubId));
            if (raw) {
                const obj = JSON.parse(raw);
                Object.keys(obj).forEach((k) => this._offsets.set(k, obj[k]));
            }
        } catch (e) { /* corrupt/unavailable storage: start fresh */ }
    }

    _saveOffsets() {
        if (this._hubId === null || this._hubId === undefined) return;
        const obj = {};
        this._offsets.forEach((v, k) => { obj[k] = v; });
        try {
            localStorage.setItem(this._offsetsStorageKey(this._hubId), JSON.stringify(obj));
        } catch (e) { /* storage full/unavailable: offsets stay in-memory only */ }
    }

    /** Clear all manually-dragged node positions for the current hub. */
    resetOffsets() {
        this._offsets = new Map();
        try { localStorage.removeItem(this._offsetsStorageKey(this._hubId)); } catch (e) { /* ignore */ }
        if (this._lastAreas.length) {
            this._runLayout(this._lastAreas);
            this._render(this._lastAreas);
        }
    }

    // --- layout: deterministic left-to-right grid ------------------------

    /**
     * Areas are ordered by id ascending and laid into a grid flowing left
     * to right, wrapping into new rows as needed. Because new areas always
     * sort to the end of this list, they always land to the right of (or
     * on the row below) every pre-existing area -- never to the left.
     * Manual per-node drag offsets (see _offsets) are then layered on top.
     */
    _runLayout(areas) {
        const w = Math.max(this._width, 300);
        const h = Math.max(this._height, 300);
        const margin = 90;
        const colSpacing = this._nodeW + 70;
        const rowSpacing = this._nodeH + 60;
        const cols = Math.max(1, Math.floor((w - margin * 2) / colSpacing) + 1);

        const sorted = areas.slice().sort((a, b) => a.id - b.id);
        this._baseLayout = new Map();
        sorted.forEach((area, i) => {
            const col = i % cols;
            const row = Math.floor(i / cols);
            this._baseLayout.set(area.id, {
                x: margin + col * colSpacing + this._nodeW / 2,
                y: margin + row * rowSpacing + this._nodeH / 2,
            });
        });
        // Grow the canvas height to fit every row so nothing is clipped.
        const rows = Math.ceil(sorted.length / cols);
        this._height = Math.max(h, margin * 2 + rows * rowSpacing);

        this._nodes.forEach((node, id) => {
            const base = this._baseLayout.get(id);
            if (!base) return;
            const off = this._offsets.get(this._offsetKey(node.area)) || { x: 0, y: 0 };
            node.x = base.x + off.x;
            node.y = base.y + off.y;
        });
    }

    // --- rendering --------------------------------------------------------

    _render(areas) {
        this._layerNodes.innerHTML = '';
        this._layerEdges.innerHTML = '';
        this._edgePaths = new Map();
        this._edgesByNode = new Map();

        const w = Math.max(this._width, 300);
        const h = Math.max(this._height, 300);
        this._svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
        this._svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');

        const addEdgeRef = (fromId, toId, el, kind, curve) => {
            const entry = { el, fromNode: fromId, toNode: toId, kind, curve };
            if (!this._edgesByNode.has(fromId)) this._edgesByNode.set(fromId, []);
            this._edgesByNode.get(fromId).push(entry);
            if (toId !== fromId) {
                if (!this._edgesByNode.has(toId)) this._edgesByNode.set(toId, []);
                this._edgesByNode.get(toId).push(entry);
            }
        };

        // Faint implicit edges for "open hub" (fully_connected) areas first,
        // drawn once per unordered pair so they don't double up.
        areas.forEach((a) => {
            if (!a.fully_connected) return;
            const from = this._nodes.get(a.id);
            if (!from) return;
            areas.forEach((b) => {
                if (b.id === a.id) return;
                if (a.id > b.id && b.fully_connected) return; // already drawn from the other side
                const to = this._nodes.get(b.id);
                if (!to) return;
                const line = grEl('line', {
                    x1: from.x, y1: from.y, x2: to.x, y2: to.y, class: 'gr-edge gr-edge-implicit',
                });
                this._layerEdges.appendChild(line);
                addEdgeRef(a.id, b.id, line, 'line');
            });
        });

        // Explicit directed links. A mutual pair (A->B and B->A) is drawn as
        // two independent curved arrows so /onelink asymmetry stays visible,
        // each carrying its own arrowhead marker showing its direction.
        areas.forEach((a) => {
            const from = this._nodes.get(a.id);
            if (!from) return;
            (a.links || []).forEach((link) => {
                const to = this._nodes.get(link.target_id);
                if (!to) return;
                const reciprocal = this._hasLink(areas, link.target_id, a.id);
                const d = this._edgePathD(from, to, reciprocal);
                const classes = ['gr-edge'];
                if (link.locked) classes.push('gr-edge-locked');
                if (link.hidden) classes.push('gr-edge-hidden');
                const pathEl = grEl('path', {
                    d, class: classes.join(' '), fill: 'none', 'marker-end': 'url(#gr-arrow)',
                });
                this._layerEdges.appendChild(pathEl);
                this._edgePaths.set(`${a.id}->${link.target_id}`, pathEl);
                addEdgeRef(a.id, link.target_id, pathEl, 'path', reciprocal);
            });
        });

        areas.forEach((a) => {
            const pos = this._nodes.get(a.id);
            if (!pos) return;
            this._layerNodes.appendChild(this._buildNode(a, pos));
        });
    }

    /** Cheap in-place reposition used while dragging: no DOM rebuild, so
     * pointer capture on the dragged node survives the update. */
    _updateNodePosition(areaId) {
        const node = this._nodes.get(areaId);
        const g = this._layerNodes.querySelector(`[data-area-id="${areaId}"]`);
        if (node && g) {
            g.setAttribute('transform', `translate(${node.x - this._nodeW / 2}, ${node.y - this._nodeH / 2})`);
        }
        const edges = this._edgesByNode.get(areaId) || [];
        edges.forEach((e) => {
            const from = this._nodes.get(e.fromNode);
            const to = this._nodes.get(e.toNode);
            if (!from || !to) return;
            if (e.kind === 'path') {
                e.el.setAttribute('d', this._edgePathD(from, to, e.curve));
            } else {
                e.el.setAttribute('x1', from.x); e.el.setAttribute('y1', from.y);
                e.el.setAttribute('x2', to.x); e.el.setAttribute('y2', to.y);
            }
        });
    }

    _hasLink(areas, fromId, toId) {
        const a = areas.find((x) => x.id === fromId);
        if (!a) return false;
        return (a.links || []).some((l) => l.target_id === toId);
    }

    /**
     * The point where a ray from a rectangle's center in direction (dx,dy)
     * crosses that rectangle's boundary. The rectangle is centered at
     * (cx,cy) with half-extents this._nodeW/2 x this._nodeH/2 (every node
     * is drawn at that fixed size). Standard centered-box ray/AABB
     * parametrization: scale (dx,dy) by the smallest t that pushes either
     * axis out to its half-extent.
     *
     * Guards against NaN on the two degenerate inputs edge lists can
     * legitimately produce: a zero-length vector (dx=dy=0, e.g. a link
     * targeting its own area, or two nodes dragged to the exact same
     * point) falls back to a fixed direction instead of computing 0/0;
     * an axis-aligned vector (dx=0 or dy=0, i.e. a perfectly horizontal or
     * vertical link -- previously the exact case that got swallowed by
     * wide rectangular nodes) skips the division on the zero axis instead
     * of dividing by it, relying on Infinity losing the Math.min below.
     */
    _rectEdgePoint(cx, cy, dx, dy) {
        const halfW = this._nodeW / 2;
        const halfH = this._nodeH / 2;
        if (dx === 0 && dy === 0) return { x: cx, y: cy + halfH };
        const tx = dx !== 0 ? halfW / Math.abs(dx) : Infinity;
        const ty = dy !== 0 ? halfH / Math.abs(dy) : Infinity;
        const t = Math.min(tx, ty);
        return { x: cx + dx * t, y: cy + dy * t };
    }

    _edgePathD(from, to, curve) {
        const dx = to.x - from.x, dy = to.y - from.y;
        // Anchor each endpoint on its OWN node's rectangle boundary along
        // the center-to-center direction (and its reverse for the target),
        // rather than a fixed circular radius -- a wide node's horizontal
        // half-extent (75px) is well past a circle-derived radius, so the
        // old approach left both the visible line segment and the
        // arrowhead stranded underneath the opaque node card for
        // horizontal/near-horizontal links.
        const start = this._rectEdgePoint(from.x, from.y, dx, dy);
        const end = this._rectEdgePoint(to.x, to.y, -dx, -dy);
        if (!curve) return `M ${start.x} ${start.y} L ${end.x} ${end.y}`;
        const mx = (start.x + end.x) / 2, my = (start.y + end.y) / 2;
        const dist = Math.sqrt(dx * dx + dy * dy);
        const ux = dist > 1e-6 ? dx / dist : 1;
        const uy = dist > 1e-6 ? dy / dist : 0;
        const nx = -uy, ny = ux;
        const bend = 22;
        const cx = mx + nx * bend, cy = my + ny * bend;
        return `M ${start.x} ${start.y} Q ${cx} ${cy} ${end.x} ${end.y}`;
    }

    _buildNode(area, pos) {
        const classes = ['gr-node'];
        if (area.locked) classes.push('gr-node-locked');
        if (area.dark) classes.push('gr-node-dark');
        const g = grEl('g', {
            class: classes.join(' '),
            transform: `translate(${pos.x - this._nodeW / 2}, ${pos.y - this._nodeH / 2})`,
            'data-area-id': area.id,
        });

        g.appendChild(grEl('rect', { width: this._nodeW, height: this._nodeH, rx: 10, ry: 10, class: 'gr-node-card' }));

        const clipId = `gr-clip-${area.id}`;
        const clip = grEl('clipPath', { id: clipId });
        clip.appendChild(grEl('rect', { width: this._nodeW, height: 44, rx: 10, ry: 10 }));
        g.appendChild(clip);

        const thumbGroup = grEl('g', { 'clip-path': `url(#${clipId})` });
        const fallback = grEl('rect', { width: this._nodeW, height: 44, class: 'gr-thumb-fallback' });
        thumbGroup.appendChild(fallback);
        const bgLabel = grEl('text', { x: this._nodeW / 2, y: 26, 'text-anchor': 'middle', class: 'gr-thumb-label' });
        bgLabel.textContent = area.background || '(no background)';
        thumbGroup.appendChild(bgLabel);

        const showImage = (href) => {
            if (!href) return;
            const img = grEl('image', {
                x: 0, y: 0, width: this._nodeW, height: 44, preserveAspectRatio: 'xMidYMid slice',
            });
            img.setAttributeNS(GR_XLINK_NS, 'href', href);
            img.setAttribute('href', href);
            img.addEventListener('load', () => {
                fallback.style.display = 'none';
                bgLabel.style.display = 'none';
            });
            img.addEventListener('error', () => {
                if (img.parentNode) img.parentNode.removeChild(img);
            });
            thumbGroup.appendChild(img);
        };

        if (area.background) {
            const bgName = area.background;
            // NOTE: `background_thumb_base_url` (this._thumbBaseUrl) is a
            // config knob documented (config_sample/config.yaml) as
            // pointing directly at a flat static-host mirror of the
            // server's own `backgrounds/` folder (e.g.
            // "https://assets.example.com/backgrounds/") -- i.e. its root
            // already *is* the backgrounds directory, one image per
            // background name (`<name>.png`). That is a different
            // convention from the AO asset root (`asset_url` /
            // GMLocalContent's base, resolved above via
            // `this._localContent.resolve('background', bgName)`), which
            // uses the folder-per-background `background/<name>/
            // witnessempty.png` layout. Do not conflate the two here --
            // doing so 404s every thumbnail for a deployment configured
            // per the documented convention.
            const tryThumbBase = () => {
                if (this._thumbBaseUrl) {
                    showImage(this._urlJoin(this._thumbBaseUrl, `${encodeURIComponent(bgName)}.png`));
                }
            };
            if (this._localContent && typeof this._localContent.resolve === 'function') {
                this._localContent.resolve('background', bgName)
                    .then((url) => { if (url) { showImage(url); } else { tryThumbBase(); } })
                    .catch(() => tryThumbBase());
            } else {
                tryThumbBase();
            }
        }
        g.appendChild(thumbGroup);

        const nameText = grEl('text', { x: 8, y: 60, class: 'gr-node-name' });
        nameText.textContent = `${area.id}: ${truncateText(area.name, 20)}`;
        g.appendChild(nameText);

        const statusBits = [];
        if (area.locked) statusBits.push('LOCKED');
        if (area.dark) statusBits.push('DARK');
        if (area.status) statusBits.push(area.status);
        const statusText = grEl('text', { x: 8, y: 73, class: 'gr-node-status' });
        statusText.textContent = statusBits.join(' · ');
        g.appendChild(statusText);

        const countText = grEl('text', { x: this._nodeW - 6, y: 73, 'text-anchor': 'end', class: 'gr-node-count' });
        const ids = area.client_ids || [];
        countText.textContent = `${ids.length} here`;
        g.appendChild(countText);

        const chipsGroup = grEl('g', { transform: 'translate(8, 80)' });
        const maxChips = 8;
        ids.slice(0, maxChips).forEach((cid, i) => {
            const isGm = (area.gm_client_ids || []).includes(cid);
            const isCm = (area.cm_client_ids || []).includes(cid);
            // Keyed by character folder (falling back to the client id when
            // no folder is known yet), matching the Clients/Characters tabs
            // and GMLocalContent's own color-store key convention -- this is
            // what makes a color a GM sets on one tab show up here too.
            const folder = this._clientFolders[cid] || '';
            const colorKey = folder || String(cid);
            const cx = i * 15 + 6, cy = 6, r = 6;
            const chipClasses = ['gr-chip'];
            if (isGm) chipClasses.push('gr-chip-gm');
            else if (isCm) chipClasses.push('gr-chip-cm');
            const chipG = grEl('g', { class: chipClasses.join(' ') });

            const color = (this._localContent && typeof this._localContent.getClientColor === 'function')
                ? (this._localContent.getClientColor(colorKey) || '#5a6280')
                : '#5a6280';
            // Fallback colored dot -- always drawn first so it shows
            // immediately and stays visible (via the icon's clip) as the
            // ring around/behind whatever sliver of a non-square icon peeks
            // out. Inline styles (not classList/setAttribute('fill', ...))
            // deliberately win over the .gr-chip-gm/.gr-chip-cm stylesheet
            // fill rules, which otherwise out-specificity a plain fill
            // attribute and silently discard the resolved color.
            const dot = grEl('circle', { r, cx, cy, class: 'gr-chip-dot' });
            dot.style.fill = color;
            chipG.appendChild(dot);

            if (isGm || isCm) {
                const ring = grEl('circle', { r: r + 1.5, cx, cy, class: 'gr-chip-ring', fill: 'none' });
                ring.style.stroke = isGm ? 'var(--gm-accent)' : 'var(--gm-accent2)';
                ring.style.strokeWidth = '1.2';
                chipG.appendChild(ring);
            }

            if (folder) {
                const clipId = `gr-chip-clip-${area.id}-${i}`;
                const clip = grEl('clipPath', { id: clipId });
                clip.appendChild(grEl('circle', { r, cx, cy }));
                chipG.appendChild(clip);
                this._resolveCharIcon(folder).then((url) => {
                    if (!url || !chipG.isConnected) return;
                    const img = grEl('image', {
                        x: cx - r, y: cy - r, width: r * 2, height: r * 2,
                        'clip-path': `url(#${clipId})`, preserveAspectRatio: 'xMidYMid slice',
                    });
                    img.setAttributeNS(GR_XLINK_NS, 'href', url);
                    img.setAttribute('href', url);
                    img.addEventListener('error', () => { if (img.parentNode) img.parentNode.removeChild(img); });
                    chipG.appendChild(img);
                });
            }

            const title = grEl('title');
            title.textContent = `Client #${cid}`;
            chipG.appendChild(title);
            chipsGroup.appendChild(chipG);
        });
        if (ids.length > maxChips) {
            const more = grEl('text', { x: maxChips * 15 + 8, y: 10, class: 'gr-chip-more' });
            more.textContent = `+${ids.length - maxChips}`;
            chipsGroup.appendChild(more);
        }
        g.appendChild(chipsGroup);

        this._bindNodeDrag(g, area);
        return g;
    }

    /** Draggable nodes: manual offset is stored keyed by hub id + area name
     * (falling back to id) and reapplied over the computed grid layout. A
     * drag that actually moved the node suppresses the trailing click so
     * dragging never also opens the inspector. */
    _bindNodeDrag(g, area) {
        let dragMoved = false;

        g.addEventListener('pointerdown', (e) => {
            if (e.button !== 0) return;
            e.stopPropagation();
            // Same rationale as the pan handler above: a node drag that
            // starts on a label must not turn into a text selection.
            e.preventDefault();
            const key = this._offsetKey(area);
            const existing = this._offsets.get(key) || { x: 0, y: 0 };
            dragMoved = false;
            this._draggingNode = {
                areaId: area.id, key, pointerId: e.pointerId,
                startClientX: e.clientX, startClientY: e.clientY,
                startOffsetX: existing.x, startOffsetY: existing.y,
            };
            try { g.setPointerCapture(e.pointerId); } catch (err) { /* ignore */ }
        });

        g.addEventListener('pointermove', (e) => {
            const d = this._draggingNode;
            if (!d || d.pointerId !== e.pointerId || d.areaId !== area.id) return;
            const dx = (e.clientX - d.startClientX) / this._zoom;
            const dy = (e.clientY - d.startClientY) / this._zoom;
            if (Math.abs(dx) > 2 || Math.abs(dy) > 2) dragMoved = true;
            const offX = d.startOffsetX + dx;
            const offY = d.startOffsetY + dy;
            this._offsets.set(d.key, { x: offX, y: offY });
            const base = this._baseLayout.get(d.areaId);
            const node = this._nodes.get(d.areaId);
            if (base && node) {
                node.x = base.x + offX;
                node.y = base.y + offY;
                this._updateNodePosition(d.areaId);
            }
        });

        const endDrag = (e) => {
            const d = this._draggingNode;
            if (!d || d.pointerId !== e.pointerId || d.areaId !== area.id) return;
            this._draggingNode = null;
            if (dragMoved) this._saveOffsets();
        };
        g.addEventListener('pointerup', endDrag);
        g.addEventListener('pointercancel', endDrag);

        g.addEventListener('click', () => {
            if (dragMoved) { dragMoved = false; return; }
            this._onNodeClick(area.id);
        });
    }

    getNodeCenter(areaId) {
        const node = this._nodes.get(areaId);
        return node ? { x: node.x, y: node.y } : null;
    }

    /** Briefly highlight a node's border, e.g. on join/leave. */
    flashNode(areaId, cssClass) {
        const g = this._layerNodes.querySelector(`[data-area-id="${areaId}"]`);
        if (!g) return;
        g.classList.add(cssClass);
        setTimeout(() => g.classList.remove(cssClass), 700);
    }

    /**
     * Animate a token traveling from one area node to another along the
     * matching edge path, falling back to a straight line between node
     * centers when no direct edge/path exists. Lives in its own layer
     * inside the pan/zoom viewport, so it survives node/edge re-renders
     * (which only touch the edges/nodes layers) and pans/zooms along with
     * everything else.
     */
    animateMovement(clientId, fromAreaId, toAreaId, labelText) {
        const from = fromAreaId !== null && fromAreaId !== undefined ? this.getNodeCenter(fromAreaId) : null;
        const to = toAreaId !== null && toAreaId !== undefined ? this.getNodeCenter(toAreaId) : null;
        if (!from && !to) return;
        const start = from || to;
        const end = to || from;

        const token = grEl('g', { class: 'gr-token' });
        token.appendChild(grEl('circle', { r: 9, class: 'gr-token-dot' }));
        const label = grEl('text', { y: -13, 'text-anchor': 'middle', class: 'gr-token-label' });
        label.textContent = labelText !== undefined && labelText !== null ? String(labelText) : `#${clientId}`;
        token.appendChild(label);
        this._layerTokens.appendChild(token);

        const pathEl = (from && to) ? this._edgePaths.get(`${fromAreaId}->${toAreaId}`) : null;
        const duration = 620;
        const startTime = performance.now();

        const step = (now) => {
            const t = Math.min(1, (now - startTime) / duration);
            let x, y;
            if (pathEl) {
                const len = pathEl.getTotalLength();
                const pt = pathEl.getPointAtLength(len * t);
                x = pt.x; y = pt.y;
            } else {
                x = start.x + (end.x - start.x) * t;
                y = start.y + (end.y - start.y) * t;
            }
            token.setAttribute('transform', `translate(${x}, ${y})`);
            if (t < 1) {
                requestAnimationFrame(step);
            } else {
                token.classList.add('gr-token-arrived');
                setTimeout(() => { if (token.parentNode) token.parentNode.removeChild(token); }, 260);
            }
        };
        requestAnimationFrame(step);
    }
}
