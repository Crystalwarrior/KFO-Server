/**
 * gm-areas-tab.js
 * AreasGraphTab: hub/area graph view. Owns a GraphRenderer for the SVG
 * itself and layers a click-to-open area inspector (roster, editable
 * fields, preference toggles, link editor, area create/remove/swap) and
 * the WS-driven movement animation on top of it.
 *
 * All HTTP still goes exclusively through the injected ApiClient (via its
 * generic get()/post() verbs for the newer area-management endpoints, and
 * its typed helpers for the pre-existing ones) -- nothing here touches
 * fetch()/WebSocket directly.
 */

class AreasGraphTab extends TabBase {
    /**
     * @param {GMPanelShell} shell
     * @param {ApiClient} api
     * @param {HTMLElement} root
     * @param {?GMLocalContent} localContent - optional; resolves background/
     *   client-marker imagery and colors. Safe to omit or attach later via
     *   setLocalContent() -- everything degrades to the plain fallback tiles.
     */
    constructor(shell, api, root, localContent) {
        super(shell, api, root);
        this.backgroundEvents = true;

        this._hubData = null;
        this._thumbBaseUrl = '';
        this._selectedAreaId = null;
        this._inspectorRefreshPending = false;
        // ITEM 2 (v6 brief): id -> full ClientSerializer record, refreshed
        // every reload() alongside the graph's folder map (see
        // _loadClientsData below) -- the inspector's occupant list needs
        // more than an id + area-scoped gm/cm membership to build its
        // descriptive label (role flags, char folder, pos, showname).
        this._clientsById = new Map();
        this._localContent = localContent || null;
        this._pollTimer = null;
        this._usingApiPolling = false;

        this._svg = root.querySelector('#areaGraph');
        this._popover = root.querySelector('#areaPopover');
        // The inspector's poll-driven reload()/_refreshInspector() replaces
        // the popover's innerHTML; if that fires while a GM is mid-typing in
        // a link pos / evidence / field editor, the rebuild yanks the
        // focused input out from under them and their in-progress edit
        // vanishes. Defer the rebuild while an editor inside the popover
        // has focus, and re-sync once focus leaves.
        this._popover.addEventListener('focusout', () => {
            if (!this._inspectorRefreshPending) return;
            // Tab'ing between two editors inside the popover keeps the
            // editing session alive -- only refresh once focus truly leaves.
            if (this._editingPopover()) return;
            this._inspectorRefreshPending = false;
            if (this._selectedAreaId !== null) this._refreshInspector();
        });
        this._hubLabel = root.querySelector('#areasHubLabel');

        this._injectStyles();

        this._renderer = new GraphRenderer(this._svg, {
            onNodeClick: (areaId) => this._openInspector(areaId),
            onToast: (message, kind) => this.shell.toast(message, kind),
        });
        this._localContentUnsubscribe = null;
        if (this._localContent) {
            this._renderer.setLocalContent(this._localContent);
            this._subscribeLocalContent();
        }

        this._buildManagementBar();

        root.querySelector('#areasRefreshBtn').addEventListener('click', () => this.reload());
        document.addEventListener('click', (e) => {
            if (this._selectedAreaId === null) return;
            if (this._popover.contains(e.target)) return;
            if (this._svg.contains(e.target)) return;
            if (this._mgmtBar && this._mgmtBar.contains(e.target)) return;
            this._closeInspector();
        });
    }

    /** Late-inject local content resolution (e.g. if the shell constructs
     * it after tabs are registered). */
    setLocalContent(localContent) {
        this._localContent = localContent || null;
        this._renderer.setLocalContent(this._localContent);
        this._subscribeLocalContent();
    }

    /** Keep the graph's icon/thumbnail caches in sync with GMLocalContent:
     * a GM setting/clearing a per-character icon override (Characters/
     * Clients tabs) or a background override updates instantly there, but
     * GraphRenderer keeps its own char-icon cache on top for render-loop
     * performance (see gm-graph.js), and neither cache would otherwise
     * notice the change until the next 4s poll happened to re-render.
     * Re-subscribes on every call so late-injecting a different
     * `localContent` (setLocalContent above) doesn't leave a listener
     * bound to the old one. */
    _subscribeLocalContent() {
        if (typeof this._localContentUnsubscribe === 'function') {
            this._localContentUnsubscribe();
            this._localContentUnsubscribe = null;
        }
        if (!this._localContent || typeof this._localContent.subscribe !== 'function') return;
        this._localContentUnsubscribe = this._localContent.subscribe((kind, name) => {
            if (kind === null || kind === 'char_icon') this._renderer.clearCharIconCache(name);
            if (kind === null || kind === 'background') this._renderer.refreshBackgroundThumbs(kind === null ? null : name);
        });
    }

    async activate() {
        super.activate();
        await this._loadThumbBaseUrl();
        await this.reload();
        this._startPolling();
    }

    deactivate() {
        super.deactivate();
        this._stopPolling();
        this._closeInspector();
    }

    // --- polling (WS is the fast path; this is the catch-all) -----------

    _startPolling() {
        if (typeof this.api.startPolling === 'function') {
            this.api.startPolling('areas-graph', () => this.reload(), 4000);
            this._usingApiPolling = true;
            return;
        }
        if (!this._pollTimer) {
            this._pollTimer = setInterval(() => this.reload(), 4000);
        }
    }

    _stopPolling() {
        if (this._usingApiPolling && typeof this.api.stopPolling === 'function') {
            this.api.stopPolling('areas-graph');
            this._usingApiPolling = false;
        }
        if (this._pollTimer) {
            clearInterval(this._pollTimer);
            this._pollTimer = null;
        }
    }

    async _loadThumbBaseUrl() {
        if (this._thumbBaseUrl) return;
        try {
            const data = await this.api.getBackgroundThumbBaseUrl();
            this._thumbBaseUrl = data.base_url || '';
            this._renderer.setThumbBaseUrl(this._thumbBaseUrl);
        } catch (e) {
            // Placeholder tiles are the safe default; nothing to do here.
        }
    }

    async reload() {
        try {
            const data = await this.api.getAreas();
            this._hubData = data;
            this._hubLabel.textContent = `Hub ${data.hub_id}: ${data.hub_name}`;
            // GMLocalContent.getClientColor() keys colors by character folder
            // name (persistent across client-id reuse -- see gm-clients-tab.js
            // and the spec), but the area snapshot only carries client ids.
            // Resolve id -> folder here so graph markers use the same color
            // a GM set from the Clients tab for that character. This same
            // fetch also refreshes `_clientsById` (ITEM 2, v6 brief) -- the
            // full records the inspector's occupant list needs.
            const clients = await this._loadClientsData();
            this._clientsById = new Map(clients.map((c) => [c.id, c]));
            this._renderer.setClientFolders(this._clientFoldersMap(clients));
            this._renderer.setData(data);
            this._populateCreatePositionSelect();
            if (this._selectedAreaId !== null) {
                const stillExists = (data.areas || []).some((a) => a.id === this._selectedAreaId);
                if (!stillExists) {
                    this._closeInspector();
                } else {
                    // ITEM 2 (v6 brief): the occupant list needs to reflect
                    // joins/leaves/moves live, not just at the moment the
                    // inspector was opened or an edit was saved -- reload()
                    // is the poll (4s) and every WS-driven refresh's entry
                    // point (see onEvent above), so this is what makes the
                    // roster's labels (which embed live state: who's here,
                    // their pos, ...) actually stay live.
                    await this._refreshInspector();
                }
            }
        } catch (e) {
            this.shell.toast('Failed to load areas: ' + e.message, 'error');
        }
    }

    async _loadClientsData() {
        try {
            const data = await this.api.getClients();
            return data.clients || [];
        } catch (e) {
            return [];
        }
    }

    _clientFoldersMap(clients) {
        const map = {};
        clients.forEach((c) => { map[c.id] = c.iniswap || c.char_name || ''; });
        return map;
    }

    onEvent(msg) {
        switch (msg.type) {
            case 'client_moved':
                this._onClientMoved(msg.data);
                break;
            case 'client_present':
                this.reload().then(() => this._renderer.flashNode(msg.data.area_id, 'gr-flash-join'));
                break;
            case 'background_changed':
                // The bg name on this event (fired by any GM's /bg-style
                // change, not just this panel's own inspector) is the
                // freshest live signal that a background image may need
                // re-resolving -- scoped to that one name so unrelated
                // cached thumbnails aren't thrown away on every area
                // mutation. Covers the "same name, updated asset" case;
                // an actual name change is already a fresh cache key and
                // needs no explicit invalidation.
                if (msg.data && msg.data.background) this._renderer.refreshBackgroundThumbs(msg.data.background);
                this.reload();
                break;
            case 'client_absent':
            case 'client_disconnected':
            case 'hub_gm_roster_changed':
            case 'area_cm_roster_changed':
            case 'areas_changed':
                this.reload();
                break;
            default:
                break;
        }
    }

    _onClientMoved(data) {
        if (!this._hubData) { this.reload(); return; }
        const inScopeFrom = data.from_hub_id === this._hubData.hub_id &&
            this._hubData.areas.some((a) => a.id === data.from_area_id);
        const inScopeTo = data.to_hub_id === this._hubData.hub_id &&
            this._hubData.areas.some((a) => a.id === data.to_area_id);
        if (!inScopeFrom && !inScopeTo) {
            this.reload();
            return;
        }
        this._renderer.animateMovement(
            data.client_id,
            inScopeFrom ? data.from_area_id : null,
            inScopeTo ? data.to_area_id : null,
            `#${data.client_id}`,
        );
        // Give the ~620ms token animation a moment to play before the
        // occupancy chips/counts snap to their new, authoritative state.
        setTimeout(() => this.reload(), 680);
    }

    // --- hub-level area management (create) ------------------------------

    _buildManagementBar() {
        const toolbar = this.root.querySelector('.gm-toolbar');
        if (!toolbar) return;
        const bar = document.createElement('div');
        bar.className = 'gm-toolbar gm-areas-mgmt-bar';
        bar.innerHTML = `
            <span class="hub-label">Create area:</span>
            <input type="text" id="areaCreateNameInput" placeholder="new area name">
            <select id="areaCreatePositionSelect"><option value="">At end of hub</option></select>
            <button class="btn-sm" id="areaCreateBtn">Create</button>
        `;
        toolbar.insertAdjacentElement('afterend', bar);
        this._mgmtBar = bar;
        this._createNameInput = bar.querySelector('#areaCreateNameInput');
        this._createPositionSelect = bar.querySelector('#areaCreatePositionSelect');
        bar.querySelector('#areaCreateBtn').addEventListener('click', () => this._createArea());
    }

    _populateCreatePositionSelect() {
        if (!this._createPositionSelect) return;
        const areas = (this._hubData && this._hubData.areas) || [];
        const options = ['<option value="">At end of hub</option>'];
        areas.forEach((a) => {
            options.push(`<option value="before:${a.id}">Before ${a.id}: ${esc(a.name)}</option>`);
            options.push(`<option value="after:${a.id}">After ${a.id}: ${esc(a.name)}</option>`);
        });
        const prevValue = this._createPositionSelect.value;
        this._createPositionSelect.innerHTML = options.join('');
        if (Array.from(this._createPositionSelect.options).some((o) => o.value === prevValue)) {
            this._createPositionSelect.value = prevValue;
        }
    }

    async _createArea() {
        const name = this._createNameInput.value.trim();
        if (!name) { this.shell.toast('Area name is required.', 'error'); return; }
        const posVal = this._createPositionSelect.value;
        let insertAt = null;
        if (posVal) {
            const sep = posVal.indexOf(':');
            const mode = posVal.slice(0, sep);
            const targetId = parseInt(posVal.slice(sep + 1), 10);
            const idx = (this._hubData.areas || []).findIndex((a) => a.id === targetId);
            if (idx !== -1) insertAt = mode === 'after' ? idx + 1 : idx;
        }
        try {
            const body = { name };
            if (insertAt !== null) body.insert_at = insertAt;
            const result = await this.api.post('/api/gm/hub/areas/create', body);
            this.shell.toast((result.output || []).join(' ') || 'Area created.', result.ok ? 'success' : 'error');
            this._createNameInput.value = '';
            await this.reload();
        } catch (e) {
            this.shell.toast('Failed to create area: ' + e.message, 'error');
        }
    }

    // --- area inspector ---------------------------------------------------

    async _openInspector(areaId) {
        this._selectedAreaId = areaId;
        this._popover.classList.add('gm-area-inspector');
        this._popover.classList.remove('hidden');
        this._popover.innerHTML = '<div class="gm-empty">Loading area detail…</div>';
        if (this._createPositionSelect) {
            const val = `after:${areaId}`;
            if (Array.from(this._createPositionSelect.options).some((o) => o.value === val)) {
                this._createPositionSelect.value = val;
            }
        }
        await this._refreshInspector();
    }

    _closeInspector() {
        this._selectedAreaId = null;
        this._inspectorRefreshPending = false;
        this._popover.classList.add('hidden');
        this._popover.classList.remove('gm-area-inspector');
        this._popover.innerHTML = '';
    }

    /** Is the popover currently editing text? The 4s poll must not rebuild
     * the inspector's DOM (wiping the focused input's value) while a GM is
     * typing in it. Selects/checkboxes are committed on interaction and are
     * *not* "editing" -- a rebuild after their `change` is expected. */
    _editingPopover() {
        const active = document.activeElement;
        if (!active || !this._popover.contains(active)) return false;
        if (active.tagName === 'TEXTAREA') return true;
        if (active.tagName !== 'INPUT') return false;
        const t = (active.type || 'text').toLowerCase();
        return !['checkbox', 'radio', 'button', 'submit', 'range', 'color', 'hidden', 'file'].includes(t);
    }

    async _refreshInspector() {
        if (this._selectedAreaId === null) return;
        if (this._editingPopover()) {
            this._inspectorRefreshPending = true;
            return;
        }
        let detail;
        try {
            const resp = await this.api.get(`/api/gm/areas/${this._selectedAreaId}/detail`);
            detail = resp.area;
        } catch (e) {
            this.shell.toast('Failed to load area detail: ' + e.message, 'error');
            this._closeInspector();
            return;
        }
        if (this._selectedAreaId === null || !detail) return;
        // `/detail` nests the command-backed scalars under `detail.fields`
        // (that's the shape `AreaDetailSerializer.to_dict` actually emits)
        // and doesn't carry roster info at all -- the roster/name/background
        // summary the inspector template expects at the top level comes from
        // the already-loaded graph snapshot (`/api/gm/areas`) instead. Merge
        // both into one flat object for `_renderInspector`.
        const summary = ((this._hubData && this._hubData.areas) || [])
            .find((a) => a.id === this._selectedAreaId) || {};
        const merged = Object.assign({}, detail.fields || {}, {
            id: detail.id,
            editable_fields: detail.editable_fields || [],
            prefs: detail.prefs || [],
            links: detail.links || [],
            client_ids: summary.client_ids || [],
            gm_client_ids: summary.gm_client_ids || [],
            cm_client_ids: summary.cm_client_ids || [],
        });
        this._renderInspector(merged);
    }

    _linkBool(link, ...keys) {
        for (const k of keys) { if (link[k] !== undefined) return !!link[k]; }
        return false;
    }

    /** Does `fromId`'s area have an outgoing link to `toId`, per the
     * currently-loaded hub snapshot? Used to tell a mutual link pair apart
     * from a one-way link so the inspector can offer "Unlink both" only
     * where a second direction actually exists to remove. */
    _hasLinkBetween(fromId, toId) {
        const a = ((this._hubData && this._hubData.areas) || []).find((x) => x.id === fromId);
        if (!a) return false;
        return (a.links || []).some((l) => l.target_id === toId);
    }

    _renderInspector(area) {
        // 'overlay' is edited via the dedicated background/overlay form
        // below, not the generic fields list; 'pos_lock' gets its own
        // dedicated list+editor section too (ITEM 2, v4 brief) -- it's a
        // LIST of position strings, not a scalar, so the generic
        // `typeof area[k] !== 'object'` filter below already excludes it
        // from `basicFields` on its own, but it's listed here explicitly
        // too so that exclusion reads as deliberate, not a silent drop (the
        // exact bug this item fixes: pos_lock used to fall through and
        // never render at all). The rest are bookkeeping keys merged in by
        // `_refreshInspector`, not real Area scalars.
        const skipKeys = new Set([
            'id', 'prefs', 'links', 'background', 'overlay', 'pos_lock',
            'editable_fields', 'client_ids', 'gm_client_ids', 'cm_client_ids',
        ]);
        const editableFields = new Set(area.editable_fields || []);
        const basicFields = Object.keys(area).filter((k) => !skipKeys.has(k) && typeof area[k] !== 'object');

        // ITEM 2 (v6 brief): "Client #0 [GM]" wasn't descriptive enough --
        // build the shared, richer label (icon, role badges, id, char
        // folder incl. iniswap, <pos>, showname) via buildClientLabel()
        // (gm-utils.js), the exact same helper gm-clients-tab.js's rows
        // use, so a client is described identically everywhere in this
        // panel. `<pos>` is dropped area-wide when pos_lock has exactly 1
        // entry (everyone present is necessarily there -- see
        // buildClientLabel's doc). A client missing from `_clientsById`
        // (a join the periodic client-list fetch hasn't caught up with
        // yet) still gets a sane fallback label from this area's own
        // gm/cm membership instead of no role info at all.
        const clientIds = area.client_ids || [];
        const dropPos = Array.isArray(area.pos_lock) && area.pos_lock.length === 1;
        const roster = clientIds.length
            ? clientIds.map((id) => {
                const client = this._clientsById.get(id) || {
                    id,
                    is_hub_gm: (area.gm_client_ids || []).includes(id),
                    is_area_cm: (area.cm_client_ids || []).includes(id),
                };
                return `<li>${buildClientLabel(client, { dropPos }).html}</li>`;
            }).join('')
            : '<li class="dim">Nobody here.</li>';

        // Only fields the backend actually has a real command behind
        // (`editable_fields`) get an editable input + Save button; the rest
        // of the allowlisted scalars (background_suffix, dark, locked,
        // evidence_mod, pos_lock, move_delay, ...) are shown read-only --
        // saving them would just 400 with "Unsupported field".
        const basicsHtml = basicFields.map((k) => {
            if (!editableFields.has(k)) {
                return `
            <div class="gm-field-row" data-field="${esc(k)}">
                <label title="${esc(k)} (read-only)">${esc(k)}</label>
                <span class="gm-field-readonly">${esc(fmtValue(area[k]))}</span>
            </div>`;
            }
            return `
            <div class="gm-field-row" data-field="${esc(k)}">
                <label title="${esc(k)}">${esc(k)}</label>
                <input type="text" class="gm-field-input" value="${esc(fmtValue(area[k]))}">
                <button class="btn-sm gm-field-save">Save</button>
            </div>`;
        }).join('');

        const prefsHtml = (area.prefs || []).map((p) => `
            <label class="gm-pref-toggle">
                <input type="checkbox" data-pref="${esc(p.name)}" ${p.value ? 'checked' : ''}>
                <span>${esc(p.name)}</span>
                ${p.gm_only ? '<span class="badge gm">GM</span>' : ''}
            </label>
        `).join('') || '<div class="dim">No preferences reported.</div>';

        const otherAreas = ((this._hubData && this._hubData.areas) || []).filter((a) => a.id !== area.id);
        const targetOptions = otherAreas.map((a) => `<option value="${a.id}">${esc(a.id)}: ${esc(a.name)}</option>`).join('');

        const linksHtml = (area.links || []).map((l) => {
            const target = ((this._hubData && this._hubData.areas) || []).find((a) => a.id === l.target_id);
            const label = target ? `${esc(target.id)}: ${esc(target.name)}` : `#${esc(l.target_id)}`;
            const peekable = this._linkBool(l, 'peekable', 'can_peek');
            // Backend link serialization exposes the pos as `target_pos`
            // (see AreaSerializer.links_to_list in gm_panel.py) -- reading
            // `l.pos` here would make the field always look empty, and the
            // inspector's post-commit refresh would "forget" the value.
            const posVal = (l.target_pos !== undefined && l.target_pos !== null) ? l.target_pos
                : ((l.pos !== undefined && l.pos !== null) ? l.pos : '');
            // Evidence-restriction is a *list* of evidence ids on the wire
            // (POST .../links/set { prop: 'evidence', value: [...] }), not a
            // boolean -- a plain checkbox can't represent "restricted to
            // these specific items", so this is a text field of comma/space
            // separated evidence ids (matching EvidenceSerializer's 0-indexed
            // `id`), empty = no restriction.
            const evidenceVal = Array.isArray(l.evidence) ? l.evidence.join(', ') : '';
            // Reciprocal is not known from this area's own link list alone
            // -- it needs the target area's own links too -- so "Unlink
            // both" can be disabled when there's only ever been a one-way
            // link to remove the other side of.
            const mutual = this._hasLinkBetween(l.target_id, area.id);
            return `
                <div class="gm-link-row" data-target="${l.target_id}">
                    <div class="gm-link-target">${label}${mutual ? ' <span class="badge cm" title="Linked back to this area too">↔</span>' : ' <span class="badge gm" title="One-way: target does not link back">→</span>'}</div>
                    <div class="gm-link-props">
                        <label><input type="checkbox" data-prop="lock" ${l.locked ? 'checked' : ''}> Locked</label>
                        <label><input type="checkbox" data-prop="hide" ${l.hidden ? 'checked' : ''}> Hidden</label>
                        <label><input type="checkbox" data-prop="peekable" ${peekable ? 'checked' : ''}> Peekable</label>
                    </div>
                    <div class="gm-link-pos-row">
                        <label>Pos <input type="text" class="gm-link-pos-input" value="${esc(posVal)}" placeholder="(none)" title="Enter to apply; blank clears the pos"></label>
                    </div>
                    <div class="gm-link-pos-row gm-link-unlink-row">
                        <button class="btn-sm danger gm-link-remove-one" title="Remove only this area's link to the target (leaves the target's link back, if any, untouched)">Unlink one-way</button>
                        <button class="btn-sm danger gm-link-remove-both" title="Remove the link in both directions (requires GM or ownership of both areas)" ${mutual ? '' : 'disabled'}>Unlink both</button>
                    </div>
                    <div class="gm-link-pos-row">
                        <label title="Evidence ids (comma-separated) required to see this link; empty = no restriction">Evidence ids <input type="text" class="gm-link-evidence-input" value="${esc(evidenceVal)}" placeholder="(none)"></label>
                    </div>
                </div>
            `;
        }).join('') || '<div class="dim">No outgoing links.</div>';

        // ITEM 5 (v4 brief): "Teleport here" moves the GM's own bound
        // client (the one that ran /gmpanel) into this area via the real
        // `/area <id>` command, run through the free-form command API --
        // see _teleportHere(). Disabled when the bound client is already
        // standing here; `shell.gmIdentity.area_id` is kept fresh by
        // GMPanelShell itself (the `hello` WS event on connect, and
        // `client_moved` whenever it's this client that moved -- see
        // gm-shell.js), so no extra plumbing is needed to know "here".
        const boundAreaId = this.shell.gmIdentity ? this.shell.gmIdentity.area_id : null;
        const alreadyHere = boundAreaId !== null && boundAreaId !== undefined && boundAreaId === area.id;

        // ITEM 2 (v4 brief): pos_lock is a LIST of position strings
        // (v3's scalar-only serializer allowlist silently dropped it --
        // see AreaDetailSerializer in gm_panel.py), so it gets its own
        // list display + comma-separated editor here instead of the
        // generic scalar field loop above (which explicitly skips it --
        // see skipKeys). Editing/clearing both route through the same
        // `/api/gm/areas/{id}/edit` endpoint (field: "pos_lock") the
        // generic fields use, which itself runs the real `/pos_lock` /
        // `/pos_lock_clear` commands -- see _editField().
        const posLock = Array.isArray(area.pos_lock) ? area.pos_lock : [];
        const posLockListHtml = posLock.length
            ? posLock.map((p) => `<span class="gm-poslock-chip">${esc(p)}</span>`).join('')
            : '<span class="dim">No position lock (all positions available).</span>';

        this._popover.innerHTML = `
            <div class="gm-inspector-head">
                <div class="area-popover-title">Area ${esc(area.id)}: ${esc(area.name || '')}</div>
                <button type="button" class="gm-inspector-close" id="inspectorCloseBtn"
                    title="Close inspector" aria-label="Close inspector">✕</button>
            </div>
            <div class="area-popover-sub">${area.locked ? 'LOCKED · ' : ''}${area.dark ? 'DARK · ' : ''}${esc(area.status || '')}</div>
            <ul class="area-popover-roster">${roster}</ul>

            <button class="btn-sm" id="inspectorTeleportBtn" style="width:100%;margin-bottom:0.4rem"
                title="${alreadyHere ? 'Your bound client is already here.' : 'Move your bound client to this area.'}"
                ${alreadyHere ? 'disabled' : ''}>Teleport here</button>

            <div class="gm-inspector-section">
                <label>Background (this area only)</label>
                <div class="gm-inline-form">
                    <input type="text" id="inspectorBgInput" value="${esc(area.background || '')}" placeholder="background name">
                    <input type="text" id="inspectorOverlayInput" value="${esc(area.overlay || '')}" placeholder="overlay">
                </div>
                <button class="btn-sm" id="inspectorBgSetBtn" style="margin-top:0.35rem;width:100%">Set Background</button>
            </div>

            <div class="gm-inspector-section">
                <label>Position Lock</label>
                <div class="gm-poslock-list">${posLockListHtml}</div>
                <div class="gm-inline-form">
                    <input type="text" id="inspectorPosLockInput" value="${esc(posLock.join(', '))}" placeholder="pos one, pos two">
                </div>
                <div class="gm-inline-form" style="margin-top:0.35rem">
                    <button class="btn-sm" id="inspectorPosLockSaveBtn" style="flex:1">Save</button>
                    <button class="btn-sm danger" id="inspectorPosLockClearBtn" style="flex:1" ${posLock.length ? '' : 'disabled'}>Clear</button>
                </div>
            </div>

            ${basicFields.length ? `<div class="gm-inspector-section"><h4>Fields</h4>${basicsHtml}</div>` : ''}

            <div class="gm-inspector-section">
                <h4>Preferences</h4>
                <div class="gm-pref-list">${prefsHtml}</div>
            </div>

            <div class="gm-inspector-section">
                <h4>Links</h4>
                <div class="gm-link-list">${linksHtml}</div>
                <div class="gm-inline-form">
                    <select id="inspectorLinkAddSelect">${targetOptions}</select>
                    <label class="gm-link-twoway-label" title="Unchecked: only this area gets a link to the target, the target does not link back">
                        <input type="checkbox" id="inspectorLinkTwoWay" checked> Two-way
                    </label>
                    <button class="btn-sm" id="inspectorLinkAddBtn">Add Link</button>
                </div>
            </div>

            <div class="gm-inspector-section">
                <h4>Area Management</h4>
                <div class="gm-inline-form">
                    <select id="inspectorSwapSelect">${targetOptions}</select>
                    <button class="btn-sm" id="inspectorSwapBtn">Swap</button>
                </div>
                <button class="btn-sm danger" id="inspectorRemoveBtn" style="width:100%;margin-top:0.35rem">Remove This Area</button>
            </div>
        `;

        this._wireInspector(area);
        this._loadRosterIcons(clientIds);
    }

    /** Async icon fill-in for the occupant roster's label placeholders
     * (see buildClientLabel's `iconHtml` doc in gm-utils.js) -- mirrors
     * ClientsTab._loadIcons()'s pattern: resolve is cached/deduped by
     * GMLocalContent itself, so re-running this on every inspector refresh
     * (including the 4s poll-driven one, see reload() above) is cheap once
     * warm. Scoped to `this._popover` so it can never touch another
     * container's same-numbered slot. */
    _loadRosterIcons(clientIds) {
        if (!this._localContent) return;
        clientIds.forEach((id) => {
            const client = this._clientsById.get(id);
            const folder = client ? (client.iniswap || client.char_name || '') : '';
            if (!folder) return;
            this._localContent.resolve('char_icon', folder).then((url) => {
                if (!url) return;
                const slot = this._popover.querySelector(`.gm-label-icon-slot[data-cid="${id}"]`);
                if (!slot) return;
                const img = document.createElement('img');
                img.className = 'gm-char-icon-img';
                img.alt = folder;
                img.src = url;
                img.addEventListener('error', () => { img.remove(); });
                slot.innerHTML = '';
                slot.appendChild(img);
            }).catch(() => { /* keep the icon-less label */ });
        });
    }

    _wireInspector(area) {
        const p = this._popover;
        p.querySelector('#inspectorCloseBtn').addEventListener('click', () => this._closeInspector());
        p.querySelector('#inspectorBgSetBtn').addEventListener('click', () => this._setBackground(area.id));

        const teleportBtn = p.querySelector('#inspectorTeleportBtn');
        if (teleportBtn && !teleportBtn.disabled) {
            teleportBtn.addEventListener('click', () => this._teleportHere(area.id));
        }

        const posLockSaveBtn = p.querySelector('#inspectorPosLockSaveBtn');
        if (posLockSaveBtn) {
            posLockSaveBtn.addEventListener('click', () => {
                const value = p.querySelector('#inspectorPosLockInput').value;
                this._editField(area.id, 'pos_lock', value);
            });
        }
        const posLockClearBtn = p.querySelector('#inspectorPosLockClearBtn');
        if (posLockClearBtn && !posLockClearBtn.disabled) {
            posLockClearBtn.addEventListener('click', () => this._editField(area.id, 'pos_lock', ''));
        }

        p.querySelectorAll('.gm-field-row').forEach((row) => {
            const saveBtn = row.querySelector('.gm-field-save');
            if (!saveBtn) return; // read-only field row -- no command backs it
            saveBtn.addEventListener('click', () => {
                const field = row.dataset.field;
                const value = row.querySelector('.gm-field-input').value;
                this._editField(area.id, field, value);
            });
        });

        p.querySelectorAll('.gm-pref-toggle input[type=checkbox]').forEach((cb) => {
            cb.addEventListener('change', () => this._setPref(area.id, cb.dataset.pref, cb.checked));
        });

        p.querySelectorAll('.gm-link-row').forEach((row) => {
            const targetId = parseInt(row.dataset.target, 10);
            row.querySelectorAll('input[type=checkbox][data-prop]').forEach((cb) => {
                cb.addEventListener('change', () => this._setLinkProp(area.id, targetId, cb.dataset.prop, cb.checked));
            });
            const posInput = row.querySelector('.gm-link-pos-input');
            if (posInput) {
                // Commit only on Enter: the inspector is rebuilt by the 4s
                // poll and WS events, and a `change` listener fires on blur
                // (including when that rebuild yanks a focused input out of
                // the DOM), silently committing half-typed text. Enter is
                // the deliberate, visible commit point.
                posInput.addEventListener('keydown', (e) => {
                    if (e.key !== 'Enter') return;
                    e.preventDefault();
                    posInput.blur();
                    this._setLinkProp(area.id, targetId, 'pos', posInput.value);
                });
            }
            const evidenceInput = row.querySelector('.gm-link-evidence-input');
            if (evidenceInput) {
                evidenceInput.addEventListener('keydown', (e) => {
                    if (e.key !== 'Enter') return;
                    e.preventDefault();
                    evidenceInput.blur();
                    const ids = evidenceInput.value.split(/[,\s]+/)
                        .map((s) => s.trim())
                        .filter((s) => s !== '')
                        .map((s) => parseInt(s, 10))
                        .filter((n) => Number.isInteger(n));
                    this._setLinkProp(area.id, targetId, 'evidence', ids);
                });
            }
            const removeOneBtn = row.querySelector('.gm-link-remove-one');
            if (removeOneBtn) removeOneBtn.addEventListener('click', () => this._removeLink(area.id, targetId, false));
            const removeBothBtn = row.querySelector('.gm-link-remove-both');
            if (removeBothBtn && !removeBothBtn.disabled) {
                removeBothBtn.addEventListener('click', () => this._removeLink(area.id, targetId, true));
            }
        });

        const addBtn = p.querySelector('#inspectorLinkAddBtn');
        if (addBtn) addBtn.addEventListener('click', () => {
            const sel = p.querySelector('#inspectorLinkAddSelect');
            if (!sel || !sel.value) return;
            const twoWayCb = p.querySelector('#inspectorLinkTwoWay');
            this._addLink(area.id, parseInt(sel.value, 10), !twoWayCb || twoWayCb.checked);
        });

        const swapBtn = p.querySelector('#inspectorSwapBtn');
        if (swapBtn) swapBtn.addEventListener('click', () => {
            const sel = p.querySelector('#inspectorSwapSelect');
            if (!sel || !sel.value) return;
            this._swapAreas(area.id, parseInt(sel.value, 10));
        });

        const removeBtn = p.querySelector('#inspectorRemoveBtn');
        if (removeBtn) removeBtn.addEventListener('click', () => this._removeArea(area.id));
    }

    async _setBackground(areaId) {
        const bg = this._popover.querySelector('#inspectorBgInput').value.trim();
        const overlay = this._popover.querySelector('#inspectorOverlayInput').value.trim();
        if (!bg) { this.shell.toast('Background name is required.', 'error'); return; }
        try {
            const result = await this.api.setAreaBackground(areaId, bg, overlay);
            this.shell.toast((result.output || []).join(' ') || 'Background updated.', result.ok ? 'success' : 'error');
            // Belt-and-suspenders alongside the WS `background_changed`
            // handler above: this GM's own panel doesn't need to depend on
            // its own WS round-trip to see its own change reflected live.
            if (result.ok !== false) this._renderer.refreshBackgroundThumbs(bg);
            await this.reload();
            if (this._selectedAreaId === areaId) await this._refreshInspector();
        } catch (e) {
            this.shell.toast('Failed to set background: ' + e.message, 'error');
        }
    }

    /**
     * ITEM 5 (v4 brief): move the GM's own bound client (the one that ran
     * /gmpanel) into `areaId`, the same way the panel already runs any
     * other OOC command -- through the free-form command-run API
     * (`api.runCommand`, backed by `POST /api/gm/commands/run`), which
     * always executes through the GM's real, live `Client` object (see
     * `GMSession.execute_command` in gm_panel.py), so this is exactly
     * `/area <id>` typed by the GM themselves: no separate permission path
     * to keep in sync. `/area` accepts a bare numeric id (see
     * `ooc_cmd_area` in server/commands/areas.py), matching this area's
     * `id`.
     *
     * The GM's own marker/position updates live via the normal
     * `client_moved` WS event (GraphRenderer.animateMovement + this tab's
     * own reload(), see onEvent/_onClientMoved above) and the header
     * identity line updates itself (GMPanelShell._handleWsMessage already
     * special-cases a `client_moved` whose `client_id` matches the bound
     * GM's own). That WS round-trip is not guaranteed though (a GM panel
     * browser tab with a flaky WS connection, for instance) -- reload()
     * here is belt-and-suspenders so this GM's own panel never depends on
     * its own WS delivery to see its own move reflected, same pattern as
     * `_setBackground` above.
     */
    async _teleportHere(areaId) {
        try {
            const result = await this.api.runCommand('area', String(areaId));
            this.shell.toast((result.output || []).join(' ') || 'Teleported.', result.ok ? 'success' : 'error');
            await this.reload();
            if (this._selectedAreaId === areaId) await this._refreshInspector();
        } catch (e) {
            this.shell.toast('Failed to teleport: ' + e.message, 'error');
        }
    }

    async _editField(areaId, field, value) {
        try {
            const result = await this.api.post(`/api/gm/areas/${areaId}/edit`, { field, value });
            this.shell.toast((result.output || []).join(' ') || `${field} updated.`, result.ok ? 'success' : 'error');
            await this.reload();
            if (this._selectedAreaId === areaId) await this._refreshInspector();
        } catch (e) {
            this.shell.toast(`Failed to update ${field}: ${e.message}`, 'error');
        }
    }

    async _setPref(areaId, pref, value) {
        try {
            const result = await this.api.post(`/api/gm/areas/${areaId}/pref`, { pref, value });
            this.shell.toast((result.output || []).join(' ') || `${pref} ${value ? 'enabled' : 'disabled'}.`, result.ok ? 'success' : 'error');
        } catch (e) {
            this.shell.toast(`Failed to set ${pref}: ${e.message}`, 'error');
        } finally {
            if (this._selectedAreaId === areaId) await this._refreshInspector();
        }
    }

    /** @param {boolean} [twoWay=true] - false creates only this area's
     * outgoing link (the one-way primitive); true (default) routes through
     * /link, which links both directions. */
    async _addLink(areaId, targetId, twoWay) {
        try {
            const body = { target_id: targetId, two_way: twoWay !== false };
            const result = await this.api.post(`/api/gm/areas/${areaId}/links/add`, body);
            this.shell.toast((result.output || []).join(' ') || 'Link added.', result.ok ? 'success' : 'error');
            await this.reload();
            if (this._selectedAreaId === areaId) await this._refreshInspector();
        } catch (e) {
            this.shell.toast('Failed to add link: ' + e.message, 'error');
        }
    }

    /** @param {boolean} [twoWay=true] - false removes only this area's
     * outgoing link to targetId (the one-way primitive), leaving any link
     * back untouched; true (default) routes through /unlink, which removes
     * both directions. */
    async _removeLink(areaId, targetId, twoWay) {
        try {
            const body = { target_id: targetId, two_way: twoWay !== false };
            const result = await this.api.post(`/api/gm/areas/${areaId}/links/remove`, body);
            this.shell.toast((result.output || []).join(' ') || 'Link removed.', result.ok ? 'success' : 'error');
            await this.reload();
            if (this._selectedAreaId === areaId) await this._refreshInspector();
        } catch (e) {
            this.shell.toast('Failed to remove link: ' + e.message, 'error');
        }
    }

    async _setLinkProp(areaId, targetId, prop, value) {
        try {
            const result = await this.api.post(`/api/gm/areas/${areaId}/links/set`, { target_id: targetId, prop, value });
            this.shell.toast((result.output || []).join(' ') || 'Link updated.', result.ok ? 'success' : 'error');
            await this.reload();
        } catch (e) {
            this.shell.toast('Failed to update link: ' + e.message, 'error');
        } finally {
            if (this._selectedAreaId === areaId) await this._refreshInspector();
        }
    }

    async _swapAreas(a, b) {
        try {
            const result = await this.api.post('/api/gm/hub/areas/swap', { a, b });
            this.shell.toast((result.output || []).join(' ') || 'Areas swapped.', result.ok ? 'success' : 'error');
            await this.reload();
        } catch (e) {
            this.shell.toast('Failed to swap areas: ' + e.message, 'error');
        }
    }

    async _removeArea(areaId) {
        const area = ((this._hubData && this._hubData.areas) || []).find((a) => a.id === areaId);
        const label = area ? `${area.id}: ${area.name}` : `#${areaId}`;
        if (!window.confirm(`Remove area ${label}? This cannot be undone.`)) return;
        try {
            const result = await this.api.post(`/api/gm/hub/areas/${areaId}/remove`);
            this.shell.toast((result.output || []).join(' ') || 'Area removed.', result.ok ? 'success' : 'error');
            this._closeInspector();
            await this.reload();
        } catch (e) {
            this.shell.toast('Failed to remove area: ' + e.message, 'error');
        }
    }

    // --- styles (dynamic DOM only; gm.html/gm.css are not ours to edit) --

    _injectStyles() {
        if (document.getElementById('gm-areas-inspector-style')) return;
        const style = document.createElement('style');
        style.id = 'gm-areas-inspector-style';
        style.textContent = `
            /* Dragging/panning the graph must never turn into a native
             * text-selection drag over node labels (name/status/count/
             * background caption/chip-more text). user-select:none on the
             * whole graph surface is the belt; pointer-events:none on the
             * label text itself (so hits fall through to the node's <rect>,
             * which owns the drag listener) is the suspenders -- together
             * they cover both the "drag started on a label" and "drag
             * crossed over a label mid-gesture" cases across browsers.
             */
            .area-graph {
                -webkit-user-select: none; -moz-user-select: none; user-select: none;
            }
            .gr-node text {
                -webkit-user-select: none; -moz-user-select: none; user-select: none;
                pointer-events: none;
            }

            /* Node header background thumbnail (see GraphRenderer._buildNode
             * / _resolveBgImage in gm-graph.js): a resolved background image
             * paints behind the name label with a dark scrim between them so
             * the label stays legible over any image, light or dark. Hidden
             * by default -- only shown once an <image> actually loads. */
            .gr-thumb-scrim { fill: #05070d; opacity: 0.45; pointer-events: none; }
            .gr-thumb-label.gr-thumb-label-scrimmed { fill: #f0f1fa; font-weight: 600; }

            .gr-controls {
                position: absolute; top: 0.6rem; left: 0.6rem; z-index: 6;
                display: flex; flex-direction: column; gap: 0.3rem;
            }
            .gr-ctrl-btn {
                background: var(--gm-panel); color: var(--gm-text); border: 1px solid var(--gm-border);
                width: 30px; height: 28px; border-radius: 4px; cursor: pointer; font-size: 0.85rem;
                display: flex; align-items: center; justify-content: center; padding: 0;
            }
            .gr-ctrl-btn:hover { background: #26304a; border-color: var(--gm-accent); }
            .area-graph.gr-panning { cursor: grabbing; }

            /* ITEM 1 (v6 brief): player marker/chip size slider, grouped
             * with the +/-/Fit/Reset glyph buttons above it. */
            .gr-ctrl-iconscale {
                display: flex; align-items: center; gap: 0.3rem; background: var(--gm-panel);
                border: 1px solid var(--gm-border); border-radius: 4px; padding: 0.15rem 0.4rem;
            }
            .gr-ctrl-iconscale-label { font-size: 0.68rem; color: var(--gm-text-dim); white-space: nowrap; }
            .gr-ctrl-iconscale-slider { width: 64px; accent-color: var(--gm-accent); cursor: pointer; }

            /* ITEM 2 (v6 brief): the shared occupant/client label's mini
             * char-icon placeholder (see buildClientLabel in gm-utils.js) --
             * sized small and inline so it sits before the [badges][id]
             * text without disturbing line height. The actual <img>
             * (appended async once resolved) reuses .gm-char-icon-img's
             * existing 100%/100%-of-parent sizing (gm.css). */
            .gm-label-icon-slot {
                display: inline-block; width: 14px; height: 14px; border-radius: 3px;
                overflow: hidden; vertical-align: -2px; margin-right: 0.2rem;
                background: var(--gm-panel-alt);
            }

            /* ITEM 4 (v4 brief): Save/Load/Export/Import Layout controls --
             * text-labeled, so they need more room than the square +/-/Fit/
             * Reset glyph buttons above. */
            .gr-ctrl-btn-wide { width: auto; align-self: flex-start; padding: 0 0.5rem; white-space: nowrap; }

            /* "Load Layout" popover: this hub's saved named layouts, each
             * with an Apply/Delete pair. */
            .gr-layout-menu {
                position: absolute; top: 0.6rem; left: 3.4rem; z-index: 7;
                background: var(--gm-panel); border: 1px solid var(--gm-border); border-radius: 6px;
                padding: 0.4rem; width: 220px; max-height: 260px; overflow-y: auto;
                box-shadow: 0 4px 14px rgba(0,0,0,0.35);
            }
            .gr-layout-menu.hidden { display: none; }
            .gr-layout-title {
                font-size: 0.72rem; color: var(--gm-text-dim); text-transform: uppercase;
                letter-spacing: 0.03em; margin-bottom: 0.35rem;
            }
            .gr-layout-empty { font-size: 0.78rem; color: var(--gm-text-dim); }
            .gr-layout-row {
                display: flex; align-items: center; gap: 0.3rem; padding: 0.2rem 0;
            }
            .gr-layout-name {
                flex: 1; min-width: 0; font-size: 0.8rem; color: var(--gm-text);
                overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
            }
            .gr-layout-row .btn-sm { padding: 0.2rem 0.4rem; font-size: 0.72rem; }

            /* ITEM 2 (v4 brief): pos_lock's read-only chip list, above its
             * comma-separated editor. */
            .gm-poslock-list { display: flex; flex-wrap: wrap; gap: 0.3rem; margin-bottom: 0.35rem; }
            .gm-poslock-chip {
                background: var(--gm-panel-alt); border: 1px solid var(--gm-border); border-radius: 10px;
                padding: 0.1rem 0.5rem; font-size: 0.74rem; color: var(--gm-text);
            }

            .gm-areas-mgmt-bar { margin-top: 0.4rem; }
            .gm-areas-mgmt-bar select {
                background: var(--gm-panel-alt); color: var(--gm-text); border: 1px solid var(--gm-border);
                border-radius: 4px; padding: 0.32rem 0.5rem; font-size: 0.82rem;
            }

            .area-popover.gm-area-inspector { width: 340px; max-width: calc(100% - 1.4rem); }
            .gm-inspector-section { border-top: 1px solid var(--gm-border); margin-top: 0.55rem; padding-top: 0.5rem; }
            .gm-inspector-section h4 {
                font-size: 0.78rem; color: var(--gm-accent2); margin-bottom: 0.35rem;
                text-transform: uppercase; letter-spacing: 0.03em;
            }
            .gm-field-row { display: flex; align-items: center; gap: 0.35rem; margin-bottom: 0.3rem; }
            .gm-field-row label {
                flex: 0 0 auto; font-size: 0.72rem; color: var(--gm-text-dim); width: 78px;
                overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
            }
            .gm-field-row .gm-field-input {
                flex: 1; min-width: 0; background: var(--gm-panel-alt); color: var(--gm-text);
                border: 1px solid var(--gm-border); border-radius: 4px; padding: 0.25rem 0.4rem; font-size: 0.78rem;
            }
            .gm-field-row .gm-field-readonly {
                flex: 1; min-width: 0; color: var(--gm-text-dim); font-size: 0.78rem;
                overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
            }

            .gm-pref-list { display: flex; flex-direction: column; gap: 0.25rem; max-height: 220px; overflow-y: auto; }
            .gm-pref-toggle { display: flex; align-items: center; gap: 0.4rem; font-size: 0.78rem; cursor: pointer; }
            .gm-pref-toggle span { flex: 1; }
            .gm-pref-toggle input[type=checkbox] { accent-color: var(--gm-accent); width: 14px; height: 14px; }

            .gm-link-list { display: flex; flex-direction: column; gap: 0.4rem; margin-bottom: 0.4rem; }
            .gm-link-row {
                border: 1px solid var(--gm-border); border-radius: 5px; padding: 0.4rem 0.5rem;
                background: var(--gm-panel-alt);
            }
            .gm-link-target { font-size: 0.8rem; font-weight: 600; color: var(--gm-text); margin-bottom: 0.25rem; }
            .gm-link-props { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 0.3rem; }
            .gm-link-props label { display: flex; align-items: center; gap: 0.25rem; font-size: 0.72rem; color: var(--gm-text-dim); }
            .gm-link-props input[type=checkbox] { accent-color: var(--gm-accent2); }
            .gm-link-pos-row { display: flex; align-items: center; justify-content: space-between; gap: 0.4rem; }
            .gm-link-pos-row label { font-size: 0.72rem; color: var(--gm-text-dim); display: flex; align-items: center; gap: 0.25rem; }
            .gm-link-pos-input {
                width: 60px; background: var(--gm-bg); color: var(--gm-text); border: 1px solid var(--gm-border);
                border-radius: 4px; padding: 0.2rem 0.3rem; font-size: 0.75rem;
            }
            .gm-link-evidence-input {
                width: 100px; background: var(--gm-bg); color: var(--gm-text); border: 1px solid var(--gm-border);
                border-radius: 4px; padding: 0.2rem 0.3rem; font-size: 0.75rem;
            }
            .gm-link-unlink-row { display: flex; gap: 0.35rem; }
            .gm-link-unlink-row .btn-sm { flex: 1; padding: 0.25rem 0.3rem; font-size: 0.7rem; }
            .gm-link-unlink-row .btn-sm:disabled { opacity: 0.4; cursor: not-allowed; }
            .gm-link-twoway-label {
                display: flex; align-items: center; gap: 0.3rem; font-size: 0.75rem;
                color: var(--gm-text-dim); white-space: nowrap;
            }
            .gm-link-twoway-label input[type=checkbox] { accent-color: var(--gm-accent); }
        `;
        document.head.appendChild(style);
    }
}
