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
        // Optional (message, kind) toast sink -- GraphRenderer stays a pure
        // rendering component with no shell/toast dependency of its own
        // (see the module doc), so the Save/Load/Export/Import Layout
        // controls (ITEM 4 in the v4 brief) report through this callback
        // instead of reaching for `shell.toast` directly. Safe to omit.
        this._onToast = (options && options.onToast) || (() => {});
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

        // Per-background-name image resolution cache. Previously there was
        // no renderer-level cache here at all: _render() tears down and
        // rebuilds every node from scratch on *every* setData() call
        // (including the plain 4s occupancy poll -- see _startPolling in
        // gm-areas-tab.js), and the old code called straight into
        // GMLocalContent.resolve('background', ...) from every single one
        // of those rebuilds. GMLocalContent's own cache made that "only"
        // wasteful rather than broken, but it re-entered the whole
        // resolution pipeline (IndexedDB reads / File System Access calls /
        // Image() reachability probes) on every poll tick forever instead
        // of once per background name, and gave the render path no cheap,
        // synchronous "have we already got this one" check to render
        // text-first-then-patch against. See _resolveBgImage()/
        // refreshBackgroundThumbs() below.
        this._bgImageCache = new Map();   // bg name -> url|null
        this._bgImagePending = new Map(); // bg name -> Promise<url|null>

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

    /** Changing the flat-mirror thumb base (background_thumb_base_url)
     * changes what a cache miss falls back to, so a real change must
     * invalidate the bg image cache -- otherwise a name that previously
     * resolved to null (nothing found) would keep answering null forever
     * even though the new base could now serve it. */
    setThumbBaseUrl(url) {
        const next = url || '';
        if (next === this._thumbBaseUrl) return;
        this._thumbBaseUrl = next;
        this._bgImageCache.clear();
        this._bgImagePending.clear();
        if (this._lastAreas.length) this._render(this._lastAreas);
    }

    setLocalContent(localContent) {
        this._localContent = localContent || null;
        // A different resolution source can legitimately answer 'no icon'
        // vs 'has icon' differently for the same folder/background name, so
        // stale cached results must not survive the swap.
        this._charIconCache.clear();
        this._charIconPending.clear();
        this._bgImageCache.clear();
        this._bgImagePending.clear();
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

    /** Invalidate one (or, when `bgNameOrNull` is falsy, every) cached
     * background-image resolution and immediately re-render so a changed
     * background shows up live, with no page reload. Callers (see
     * AreasGraphTab):
     *   - GMLocalContent's own change notifications (a per-item background
     *     override set/cleared, passing that exact name; or a base-source
     *     change -- new folder/URL picked -- passing null for "everything").
     *   - the `background_changed` WS event, passing the area's (possibly
     *     unchanged) background name so a *reused* name whose underlying
     *     asset just changed doesn't keep serving a stale cached result.
     *     (The broader `areas_changed` event carries no background name and
     *     fires on every unrelated area mutation too -- it's left to fall
     *     through to the plain reload()/setData() path, where a genuine
     *     name change is simply a fresh cache key with nothing to
     *     invalidate.)
     *   - the inspector's own "Set Background" success (belt-and-suspenders
     *     alongside the WS event, which the GM's own panel also receives,
     *     but does not depend on WS being connected).
     * A background *name* change on its own needs no explicit invalidation
     * -- it is simply a different cache key that resolves fresh on its own
     * merits -- this exists for the "same name, updated content" case. */
    refreshBackgroundThumbs(bgNameOrNull) {
        if (bgNameOrNull) {
            // Cache keys are `<lowercased bgName>` or `<lowercased
            // bgName>::<lowercased position>` (see _bgImageCacheKey) -- a
            // given bg name may be cached under several different position
            // suffixes across areas that share the background but differ in
            // pos_lock, so every entry for this name (any/no position) has
            // to go, not just the no-position key.
            const prefix = String(bgNameOrNull).toLowerCase();
            [this._bgImageCache, this._bgImagePending].forEach((cache) => {
                Array.from(cache.keys()).forEach((k) => {
                    if (k === prefix || k.startsWith(`${prefix}::`)) cache.delete(k);
                });
            });
        } else {
            this._bgImageCache.clear();
            this._bgImagePending.clear();
        }
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

    /** Cache key for a (background name, preferred position) pair --
     * `position` is normally an area's `pos_lock[0]` (see _buildNode) or
     * null/absent when the area has no pos_lock. Lowercased throughout
     * (see ITEM 3's case-sensitivity rule in the v4 brief: lowercase is
     * the canonical form real asset hosts/filesystems actually serve) so
     * "Default"/"default" share one cache entry instead of two. Including
     * `position` in the key (rather than just the bg name) is what makes a
     * pos_lock change automatically invalidate: a different position is
     * simply a different, currently-uncached key, so it resolves fresh on
     * its own without needing separate invalidation plumbing tied to
     * pos_lock specifically. */
    _bgImageCacheKey(bgName, position) {
        const key = String(bgName).toLowerCase();
        return position ? `${key}::${String(position).toLowerCase()}` : key;
    }

    /** Cached, deduped background-image lookup keyed by (background name,
     * preferred position) -- mirrors _resolveCharIcon's cache/pending
     * pattern (see its doc) above. Tries GMLocalContent.resolve('background',
     * name, {position}) first (folder/URL/server-asset-url chain: the
     * position-mapped file, e.g. `defenseempty.png` for pos "def", falling
     * back to `witnessempty.png`, per ITEM 3 in the v4 brief), then falls
     * back to the documented flat `background_thumb_base_url` mirror
     * convention (`<base>/<name>.png`, no per-position imagery) -- a
     * different layout from GMLocalContent's folder-per-background one
     * above; a deployment configured per the documented flat-mirror
     * convention 404s every thumbnail if these two get conflated, so don't.
     * Settled results (including "no image found anywhere")
     * are memoized for this renderer's lifetime / until refreshBackgroundThumbs()
     * invalidates them, so a (name, position) pair is only ever resolved
     * once no matter how many render passes (4s poll ticks included) ask
     * for it. */
    _resolveBgImage(bgName, position) {
        if (!bgName) return Promise.resolve(null);
        const key = this._bgImageCacheKey(bgName, position);
        if (this._bgImageCache.has(key)) return Promise.resolve(this._bgImageCache.get(key));
        if (this._bgImagePending.has(key)) return this._bgImagePending.get(key);

        const attempt = (async () => {
            if (this._localContent && typeof this._localContent.resolve === 'function') {
                try {
                    const url = await this._localContent.resolve('background', bgName, position ? { position } : undefined);
                    if (url) return url;
                } catch (e) { /* fall through to the flat thumb-base convention */ }
            }
            if (this._thumbBaseUrl) {
                // The flat mirror is one file per background name (no
                // per-position imagery) and this layer has no reachability
                // probe of its own -- the <image> element's own error
                // handler (see showImage() below) silently drops a 404'd
                // thumb. Lowercase is the canonical form real asset hosts
                // serve (ITEM 3, v4 brief), so that's the only candidate
                // built here.
                return this._urlJoin(this._thumbBaseUrl, `${encodeURIComponent(String(bgName).toLowerCase())}.png`);
            }
            return null;
        })();

        const pending = attempt.then((url) => {
            this._bgImageCache.set(key, url || null);
            this._bgImagePending.delete(key);
            return url || null;
        });
        this._bgImagePending.set(key, pending);
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
        const mk = (label, title, fn, extraClass) => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = extraClass ? `gr-ctrl-btn ${extraClass}` : 'gr-ctrl-btn';
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

        // ITEM 4 (v4 brief) -- save/load/export/import named layout
        // snapshots (node offsets + zoom/pan), per hub, in localStorage.
        mk('Save', 'Save the current layout as a named snapshot', () => this._promptSaveLayout(), 'gr-ctrl-btn-wide');
        const loadBtn = mk('Load', 'Load or manage saved layouts for this hub', () => this._toggleLayoutMenu(), 'gr-ctrl-btn-wide');
        this._loadLayoutBtn = loadBtn;
        mk('Export', 'Download the current layout as a JSON file', () => this._exportLayoutFile(), 'gr-ctrl-btn-wide');
        mk('Import', 'Load a layout from a JSON file', () => { if (this._importInput) this._importInput.click(); }, 'gr-ctrl-btn-wide');

        const importInput = document.createElement('input');
        importInput.type = 'file';
        importInput.accept = 'application/json,.json';
        importInput.style.display = 'none';
        importInput.addEventListener('change', () => {
            const file = importInput.files && importInput.files[0];
            importInput.value = '';
            if (file) this._importLayoutFile(file);
        });
        controls.appendChild(importInput);
        this._importInput = importInput;

        wrap.appendChild(controls);
        this._controlsEl = controls;
        this._buildLayoutMenu(wrap);
    }

    /** Small popover listing this hub's saved layouts (toggled by the
     * "Load" control button), each row offering Apply/Delete. Built once;
     * content is (re)rendered on open via _renderLayoutMenu() so it always
     * reflects the current hub's saved set. */
    _buildLayoutMenu(wrap) {
        const menu = document.createElement('div');
        menu.className = 'gr-layout-menu hidden';
        wrap.appendChild(menu);
        this._layoutMenuEl = menu;
        document.addEventListener('click', (e) => {
            if (menu.classList.contains('hidden')) return;
            if (menu.contains(e.target)) return;
            if (this._loadLayoutBtn && this._loadLayoutBtn.contains(e.target)) return;
            menu.classList.add('hidden');
        });
    }

    _toggleLayoutMenu() {
        if (!this._layoutMenuEl) return;
        const willShow = this._layoutMenuEl.classList.contains('hidden');
        this._layoutMenuEl.classList.toggle('hidden', !willShow);
        if (willShow) this._renderLayoutMenu();
    }

    _renderLayoutMenu() {
        if (!this._layoutMenuEl) return;
        const names = this.listNamedLayouts();
        const rows = names.length
            ? names.map((n) => `
                <div class="gr-layout-row" data-name="${esc(n)}">
                    <span class="gr-layout-name">${esc(n)}</span>
                    <button type="button" class="btn-sm gr-layout-apply">Apply</button>
                    <button type="button" class="btn-sm danger gr-layout-delete" title="Delete this layout">✕</button>
                </div>`).join('')
            : '<div class="gr-layout-empty">No saved layouts for this hub yet.</div>';
        this._layoutMenuEl.innerHTML = `<div class="gr-layout-title">Saved layouts</div>${rows}`;
        this._layoutMenuEl.querySelectorAll('.gr-layout-row').forEach((row) => {
            const name = row.dataset.name;
            const applyBtn = row.querySelector('.gr-layout-apply');
            if (applyBtn) applyBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                if (this.loadNamedLayout(name)) {
                    this._onToast(`Layout "${name}" loaded.`, 'success');
                } else {
                    this._onToast(`Failed to load layout "${name}".`, 'error');
                }
                this._layoutMenuEl.classList.add('hidden');
            });
            const delBtn = row.querySelector('.gr-layout-delete');
            if (delBtn) delBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                if (!window.confirm(`Delete saved layout "${name}"?`)) return;
                this.deleteNamedLayout(name);
                this._onToast(`Layout "${name}" deleted.`, 'info');
                this._renderLayoutMenu();
            });
        });
    }

    _promptSaveLayout() {
        if (this._hubId === null || this._hubId === undefined) return;
        const name = window.prompt('Save layout as:', 'layout 1');
        if (name === null) return; // cancelled
        const trimmed = name.trim() || 'layout 1';
        this.saveNamedLayout(trimmed);
        this._onToast(`Layout "${trimmed}" saved.`, 'success');
    }

    _exportLayoutFile() {
        const json = this.exportLayoutJSON();
        const blob = new Blob([json], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        const hubPart = (this._hubId === null || this._hubId === undefined) ? '' : `-hub${this._hubId}`;
        a.href = url;
        a.download = `gm-graph-layout${hubPart}.json`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
    }

    async _importLayoutFile(file) {
        let text;
        try {
            text = await file.text();
        } catch (e) {
            this._onToast('Failed to read the selected file.', 'error');
            return;
        }
        const snapshot = this.parseLayoutImport(text);
        if (!snapshot) {
            this._onToast('That file is not a valid graph layout.', 'error');
            return;
        }
        this.applyLayoutSnapshot(snapshot);
        this._onToast('Layout imported.', 'success');
    }

    // --- named layout snapshots (save/load/export/import) ----------------

    _layoutsStorageKey(hubId) { return `gm-graph-layouts:${hubId}`; }

    _loadLayoutsMap() {
        if (this._hubId === null || this._hubId === undefined) return {};
        try {
            const raw = localStorage.getItem(this._layoutsStorageKey(this._hubId));
            const obj = raw ? JSON.parse(raw) : {};
            return (obj && typeof obj === 'object' && !Array.isArray(obj)) ? obj : {};
        } catch (e) {
            return {};
        }
    }

    _saveLayoutsMap(map) {
        if (this._hubId === null || this._hubId === undefined) return;
        try {
            localStorage.setItem(this._layoutsStorageKey(this._hubId), JSON.stringify(map));
        } catch (e) { /* storage full/unavailable: nothing more we can do */ }
    }

    /** The current node offsets + zoom/pan, in the exact shape persisted
     * under a saved layout name (and exported to JSON). */
    getLayoutSnapshot() {
        const offsets = {};
        this._offsets.forEach((v, k) => { offsets[k] = { x: v.x, y: v.y }; });
        return { offsets, view: { zoom: this._zoom, panX: this._panX, panY: this._panY } };
    }

    /** Validate an arbitrary parsed value as a layout snapshot shape before
     * trusting it -- imported JSON (and, defensively, anything read back
     * out of localStorage) is untrusted input; a malformed one must be
     * rejected cleanly rather than crash rendering. */
    _isValidLayoutSnapshot(snap) {
        if (!snap || typeof snap !== 'object') return false;
        if (!snap.offsets || typeof snap.offsets !== 'object' || Array.isArray(snap.offsets)) return false;
        for (const k of Object.keys(snap.offsets)) {
            const v = snap.offsets[k];
            if (!v || typeof v !== 'object') return false;
            if (!Number.isFinite(v.x) || !Number.isFinite(v.y)) return false;
        }
        if (!snap.view || typeof snap.view !== 'object') return false;
        if (!Number.isFinite(snap.view.zoom) || !Number.isFinite(snap.view.panX) || !Number.isFinite(snap.view.panY)) return false;
        return true;
    }

    /** Apply a validated layout snapshot: replaces the manual offsets and
     * zoom/pan, persists it as this hub's active offsets (so it's what a
     * future plain reload/re-render restores -- "making it the active
     * persisted layout" per the v4 brief), and re-renders immediately.
     * @returns {boolean} whether the snapshot was valid and applied. */
    applyLayoutSnapshot(snapshot) {
        if (!this._isValidLayoutSnapshot(snapshot)) return false;
        this._offsets = new Map();
        Object.keys(snapshot.offsets).forEach((k) => {
            const v = snapshot.offsets[k];
            this._offsets.set(k, { x: v.x, y: v.y });
        });
        this._zoom = Math.min(this._maxZoom, Math.max(this._minZoom, snapshot.view.zoom));
        this._panX = snapshot.view.panX;
        this._panY = snapshot.view.panY;
        this._saveOffsets();
        this._applyViewportTransform();
        if (this._lastAreas.length) {
            this._runLayout(this._lastAreas);
            this._render(this._lastAreas);
        }
        return true;
    }

    saveNamedLayout(name) {
        const trimmed = String(name || '').trim();
        if (!trimmed || this._hubId === null || this._hubId === undefined) return false;
        const map = this._loadLayoutsMap();
        map[trimmed] = this.getLayoutSnapshot();
        this._saveLayoutsMap(map);
        return true;
    }

    listNamedLayouts() {
        return Object.keys(this._loadLayoutsMap()).sort((a, b) => a.localeCompare(b));
    }

    loadNamedLayout(name) {
        const map = this._loadLayoutsMap();
        const snap = map[name];
        return snap ? this.applyLayoutSnapshot(snap) : false;
    }

    deleteNamedLayout(name) {
        const map = this._loadLayoutsMap();
        if (!(name in map)) return false;
        delete map[name];
        this._saveLayoutsMap(map);
        return true;
    }

    exportLayoutJSON() {
        return JSON.stringify({
            kind: 'kfo-gm-graph-layout',
            version: 1,
            hub_id: this._hubId,
            snapshot: this.getLayoutSnapshot(),
        }, null, 2);
    }

    /** @returns {?object} the validated inner snapshot from an exported
     * layout JSON file's text, or null if `text` isn't parseable JSON or
     * doesn't match the exported shape (a bare `{offsets, view}` snapshot,
     * with no wrapping envelope, is also accepted). Never throws. */
    parseLayoutImport(text) {
        let parsed;
        try {
            parsed = JSON.parse(text);
        } catch (e) {
            return null;
        }
        const snapshot = (parsed && typeof parsed === 'object' && parsed.snapshot) ? parsed.snapshot : parsed;
        return this._isValidLayoutSnapshot(snapshot) ? snapshot : null;
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
    //
    // ITEM 1 (v4 brief) -- ONE shared screen<->world conversion, used by
    // every pointer handler below (pan, wheel-zoom, node drag) plus
    // anything doing hit-testing in the future. Two coordinate spaces are
    // in play:
    //   - "svg-local": relative to the <svg>'s own box, i.e.
    //     `clientX/Y - boundingRect.left/top`. Because the viewBox is kept
    //     in sync with the element's actual rendered CSS-pixel size (see
    //     _measure()/_onResize()), one svg-local unit == one CSS pixel --
    //     this is also the space `panX`/`panY` live in, since the viewport
    //     transform is `translate(panX,panY) scale(zoom)` and `translate`
    //     is applied in the *parent* (pre-scale) coordinate system.
    //   - "world": content coordinates *inside* the scaled viewport --
    //     where `_nodes`/`_baseLayout`/`_offsets` all live. Getting from
    //     svg-local to world requires undoing BOTH the pan and the zoom:
    //     worldX = (svgLocalX - panX) / zoom.
    //
    // The historical form of this bug is applying a screen-pixel delta
    // straight to a WORLD-space coordinate with no `/ zoom` at all -- the
    // resulting error is `(1 - 1/zoom) * dragDistance`: invisible at
    // zoom=1, and growing (in either direction) the further zoomed in/out
    // you are, exactly matching the "the further you drag, the more it
    // drifts" bug report. Every handler below is written against
    // `_screenToWorld`/`_screenDeltaToWorld` so there is exactly one place
    // that conversion can go wrong instead of N independently-hand-rolled
    // ones.

    /** clientX/clientY (page space, e.g. straight off a PointerEvent) ->
     * svg-local space. Re-measures the bounding rect on every call (cheap)
     * so a scroll/resize mid-gesture can't leave a stale offset baked in. */
    _clientToSvg(clientX, clientY) {
        const rect = this._svg.getBoundingClientRect();
        return { x: clientX - rect.left, y: clientY - rect.top };
    }

    /** svg-local -> world (see the doc block above). */
    _svgToWorld(svgX, svgY) {
        return { x: (svgX - this._panX) / this._zoom, y: (svgY - this._panY) / this._zoom };
    }

    /** clientX/clientY -> world in one call; the primary entry point for
     * "where in content-space is the cursor right now" (node drag start/
     * current point, pan's cursor anchor). */
    _screenToWorld(clientX, clientY) {
        const p = this._clientToSvg(clientX, clientY);
        return this._svgToWorld(p.x, p.y);
    }

    /** Convert a pure screen-pixel DELTA (e.g. `e.clientX - startClientX`)
     * into the equivalent WORLD-space delta. Only valid for deltas, not
     * absolute points (panX/panY cancel out of a delta, so this is just
     * the zoom division -- but funneled through one named helper so every
     * caller states its intent instead of re-deriving `/ this._zoom`
     * inline, which is exactly how this class of bug creeps back in). */
    _screenDeltaToWorld(dxClient, dyClient) {
        return { x: dxClient / this._zoom, y: dyClient / this._zoom };
    }

    _bindPanZoom() {
        this._svg.addEventListener('wheel', (e) => {
            e.preventDefault();
            const p = this._clientToSvg(e.clientX, e.clientY);
            const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12;
            this._zoomAt(p.x, p.y, factor);
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
                // The WORLD point currently under the cursor -- panning is
                // "keep this world point locked under the cursor as the
                // mouse moves", the exact same invariant _zoomAt uses for
                // zoom-at-cursor, just solving for pan instead of zoom.
                // This is 1:1 with cursor movement at ANY zoom level by
                // construction (no separate "/zoom" anywhere in this
                // handler): the world point's screen position is
                // `panX + worldX*zoom`, so re-solving panX for a fixed
                // worldX as svgX changes moves the screen position by
                // exactly the svg-local (== CSS-pixel) delta every time.
                anchorWorld: this._screenToWorld(e.clientX, e.clientY),
            };
            try { this._svg.setPointerCapture(e.pointerId); } catch (err) { /* ignore */ }
            this._svg.classList.add('gr-panning');
            this._svg.style.cursor = 'grabbing';
        });
        this._svg.addEventListener('pointermove', (e) => {
            if (!this._panning || this._panning.pointerId !== e.pointerId) return;
            const p = this._clientToSvg(e.clientX, e.clientY);
            const a = this._panning.anchorWorld;
            this._panX = p.x - a.x * this._zoom;
            this._panY = p.y - a.y * this._zoom;
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

    /** `svgX`/`svgY` are svg-local coordinates (see the doc block above --
     * `zoomBy()` passes the viewBox center directly since that's already
     * in this space; the wheel handler converts clientX/Y via
     * `_clientToSvg` first). Keeps the WORLD point currently under
     * (svgX,svgY) fixed on screen across the zoom change. */
    _zoomAt(svgX, svgY, factor) {
        const newZoom = Math.min(this._maxZoom, Math.max(this._minZoom, this._zoom * factor));
        if (newZoom === this._zoom) return;
        const anchor = this._svgToWorld(svgX, svgY);
        this._panX = svgX - anchor.x * newZoom;
        this._panY = svgY - anchor.y * newZoom;
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

        // Header band: fallback tile -> (once resolved) the background
        // image -> a dark scrim -> the name label, in that paint order, so
        // the label always stays on top and readable while the image sits
        // visibly behind it (see _resolveBgImage()/showImage() below).
        // Rendered text-first: the label/fallback show immediately and the
        // image is patched in asynchronously whenever resolution settles,
        // never blocking the rest of the node from drawing.
        const thumbGroup = grEl('g', { 'clip-path': `url(#${clipId})` });
        const fallback = grEl('rect', { width: this._nodeW, height: 44, class: 'gr-thumb-fallback' });
        thumbGroup.appendChild(fallback);
        const scrim = grEl('rect', { width: this._nodeW, height: 44, class: 'gr-thumb-scrim' });
        scrim.style.display = 'none';
        thumbGroup.appendChild(scrim);
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
                scrim.style.display = '';
                bgLabel.classList.add('gr-thumb-label-scrimmed');
            });
            img.addEventListener('error', () => {
                if (img.parentNode) img.parentNode.removeChild(img);
                scrim.style.display = 'none';
                bgLabel.classList.remove('gr-thumb-label-scrimmed');
            });
            // Insert right before the scrim (which is itself right before
            // the label) so DOM/paint order stays fallback -> image ->
            // scrim -> label no matter when this settles.
            thumbGroup.insertBefore(img, scrim);
        };

        if (area.background) {
            const bgName = area.background;
            // ITEM 3 (v4 brief): prefer the position image for this area's
            // pos_lock[0] (the snapshot now carries `pos_lock` -- see
            // AreaSerializer.to_dict in gm_panel.py) over the generic
            // witness-stand fallback _resolveBgImage() falls back to on its
            // own. No pos_lock (or an empty one) means "all positions
            // available", so there's no preferred position to pass.
            const position = (area.pos_lock && area.pos_lock.length) ? area.pos_lock[0] : null;
            const cacheKey = this._bgImageCacheKey(bgName, position);
            if (this._bgImageCache.has(cacheKey)) {
                // Already resolved (by an earlier render of this or any
                // other node sharing the name+position) -- no async hop
                // needed.
                const cachedUrl = this._bgImageCache.get(cacheKey);
                if (cachedUrl) showImage(cachedUrl);
            } else {
                this._resolveBgImage(bgName, position).then((url) => { if (url) showImage(url); });
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
     * (falling back to id) and reapplied over the computed grid layout,
     * always in WORLD coordinates (see _screenDeltaToWorld) so a saved
     * offset means the same physical position on the canvas regardless of
     * what zoom level it was dragged at or is later viewed from -- the
     * persisted localStorage offsets therefore survive zoom changes
     * unchanged. A drag that actually moved the node suppresses the
     * trailing click so dragging never also opens the inspector. */
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
            // Screen-space delta drives the "did this actually turn into a
            // drag" threshold (a constant N screen pixels, independent of
            // zoom, so the click-vs-drag feel doesn't get twitchier the
            // further zoomed out you are); the WORLD-space delta (divided
            // by zoom via the shared helper) is what actually moves the
            // node, which is what keeps the exact point of the node grabbed
            // under the cursor at every zoom level.
            const dxScreen = e.clientX - d.startClientX;
            const dyScreen = e.clientY - d.startClientY;
            if (Math.abs(dxScreen) > 2 || Math.abs(dyScreen) > 2) dragMoved = true;
            const worldDelta = this._screenDeltaToWorld(dxScreen, dyScreen);
            const offX = d.startOffsetX + worldDelta.x;
            const offY = d.startOffsetY + worldDelta.y;
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
