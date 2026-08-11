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
        this._localContent = localContent || null;
        this._pollTimer = null;
        this._usingApiPolling = false;

        this._svg = root.querySelector('#areaGraph');
        this._popover = root.querySelector('#areaPopover');
        this._hubLabel = root.querySelector('#areasHubLabel');

        this._injectStyles();

        this._renderer = new GraphRenderer(this._svg, {
            onNodeClick: (areaId) => this._openInspector(areaId),
        });
        if (this._localContent) this._renderer.setLocalContent(this._localContent);

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
            // a GM set from the Clients tab for that character.
            this._renderer.setClientFolders(await this._loadClientFolders());
            this._renderer.setData(data);
            this._populateCreatePositionSelect();
            if (this._selectedAreaId !== null) {
                const stillExists = (data.areas || []).some((a) => a.id === this._selectedAreaId);
                if (!stillExists) this._closeInspector();
            }
        } catch (e) {
            this.shell.toast('Failed to load areas: ' + e.message, 'error');
        }
    }

    async _loadClientFolders() {
        try {
            const data = await this.api.getClients();
            const map = {};
            (data.clients || []).forEach((c) => { map[c.id] = c.iniswap || c.char_name || ''; });
            return map;
        } catch (e) {
            return {};
        }
    }

    onEvent(msg) {
        switch (msg.type) {
            case 'client_moved':
                this._onClientMoved(msg.data);
                break;
            case 'client_present':
                this.reload().then(() => this._renderer.flashNode(msg.data.area_id, 'gr-flash-join'));
                break;
            case 'client_absent':
            case 'client_disconnected':
            case 'hub_gm_roster_changed':
            case 'area_cm_roster_changed':
            case 'background_changed':
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
        this._popover.classList.add('hidden');
        this._popover.classList.remove('gm-area-inspector');
        this._popover.innerHTML = '';
    }

    async _refreshInspector() {
        if (this._selectedAreaId === null) return;
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

    _renderInspector(area) {
        // 'overlay' is edited via the dedicated background/overlay form
        // below, not the generic fields list; the rest are bookkeeping keys
        // merged in by `_refreshInspector`, not real Area scalars.
        const skipKeys = new Set([
            'id', 'prefs', 'links', 'background', 'overlay',
            'editable_fields', 'client_ids', 'gm_client_ids', 'cm_client_ids',
        ]);
        const editableFields = new Set(area.editable_fields || []);
        const basicFields = Object.keys(area).filter((k) => !skipKeys.has(k) && typeof area[k] !== 'object');

        const clientIds = area.client_ids || [];
        const roster = clientIds.length
            ? clientIds.map((id) => {
                const isGm = (area.gm_client_ids || []).includes(id);
                const isCm = (area.cm_client_ids || []).includes(id);
                const badges = `${isGm ? ' <span class="badge gm">GM</span>' : ''}${isCm ? ' <span class="badge cm">CM</span>' : ''}`;
                return `<li>Client #${id}${badges}</li>`;
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
            const posVal = (l.pos !== undefined && l.pos !== null) ? l.pos : '';
            // Evidence-restriction is a *list* of evidence ids on the wire
            // (POST .../links/set { prop: 'evidence', value: [...] }), not a
            // boolean -- a plain checkbox can't represent "restricted to
            // these specific items", so this is a text field of comma/space
            // separated evidence ids (matching EvidenceSerializer's 0-indexed
            // `id`), empty = no restriction.
            const evidenceVal = Array.isArray(l.evidence) ? l.evidence.join(', ') : '';
            return `
                <div class="gm-link-row" data-target="${l.target_id}">
                    <div class="gm-link-target">${label}</div>
                    <div class="gm-link-props">
                        <label><input type="checkbox" data-prop="lock" ${l.locked ? 'checked' : ''}> Locked</label>
                        <label><input type="checkbox" data-prop="hide" ${l.hidden ? 'checked' : ''}> Hidden</label>
                        <label><input type="checkbox" data-prop="peekable" ${peekable ? 'checked' : ''}> Peekable</label>
                    </div>
                    <div class="gm-link-pos-row">
                        <label>Pos <input type="text" class="gm-link-pos-input" value="${esc(posVal)}" placeholder="(none)"></label>
                        <button class="btn-sm danger gm-link-remove">Unlink</button>
                    </div>
                    <div class="gm-link-pos-row">
                        <label title="Evidence ids (comma-separated) required to see this link; empty = no restriction">Evidence ids <input type="text" class="gm-link-evidence-input" value="${esc(evidenceVal)}" placeholder="(none)"></label>
                    </div>
                </div>
            `;
        }).join('') || '<div class="dim">No outgoing links.</div>';

        this._popover.innerHTML = `
            <div class="area-popover-title">Area ${esc(area.id)}: ${esc(area.name || '')}</div>
            <div class="area-popover-sub">${area.locked ? 'LOCKED · ' : ''}${area.dark ? 'DARK · ' : ''}${esc(area.status || '')}</div>
            <ul class="area-popover-roster">${roster}</ul>

            <div class="gm-inspector-section">
                <label>Background (this area only)</label>
                <div class="gm-inline-form">
                    <input type="text" id="inspectorBgInput" value="${esc(area.background || '')}" placeholder="background name">
                    <input type="text" id="inspectorOverlayInput" value="${esc(area.overlay || '')}" placeholder="overlay">
                </div>
                <button class="btn-sm" id="inspectorBgSetBtn" style="margin-top:0.35rem;width:100%">Set Background</button>
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

            <button class="btn-sm area-popover-close" id="inspectorCloseBtn">Close</button>
        `;

        this._wireInspector(area);
    }

    _wireInspector(area) {
        const p = this._popover;
        p.querySelector('#inspectorCloseBtn').addEventListener('click', () => this._closeInspector());
        p.querySelector('#inspectorBgSetBtn').addEventListener('click', () => this._setBackground(area.id));

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
                posInput.addEventListener('change', () => this._setLinkProp(area.id, targetId, 'pos', posInput.value));
            }
            const evidenceInput = row.querySelector('.gm-link-evidence-input');
            if (evidenceInput) {
                evidenceInput.addEventListener('change', () => {
                    const ids = evidenceInput.value.split(/[,\s]+/)
                        .map((s) => s.trim())
                        .filter((s) => s !== '')
                        .map((s) => parseInt(s, 10))
                        .filter((n) => Number.isInteger(n));
                    this._setLinkProp(area.id, targetId, 'evidence', ids);
                });
            }
            const removeBtn = row.querySelector('.gm-link-remove');
            if (removeBtn) removeBtn.addEventListener('click', () => this._removeLink(area.id, targetId));
        });

        const addBtn = p.querySelector('#inspectorLinkAddBtn');
        if (addBtn) addBtn.addEventListener('click', () => {
            const sel = p.querySelector('#inspectorLinkAddSelect');
            if (!sel || !sel.value) return;
            this._addLink(area.id, parseInt(sel.value, 10));
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
            await this.reload();
            if (this._selectedAreaId === areaId) await this._refreshInspector();
        } catch (e) {
            this.shell.toast('Failed to set background: ' + e.message, 'error');
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

    async _addLink(areaId, targetId) {
        try {
            const result = await this.api.post(`/api/gm/areas/${areaId}/links/add`, { target_id: targetId });
            this.shell.toast((result.output || []).join(' ') || 'Link added.', result.ok ? 'success' : 'error');
            await this.reload();
            if (this._selectedAreaId === areaId) await this._refreshInspector();
        } catch (e) {
            this.shell.toast('Failed to add link: ' + e.message, 'error');
        }
    }

    async _removeLink(areaId, targetId) {
        try {
            const result = await this.api.post(`/api/gm/areas/${areaId}/links/remove`, { target_id: targetId });
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
        `;
        document.head.appendChild(style);
    }
}
