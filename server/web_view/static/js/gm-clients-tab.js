/**
 * gm-clients-tab.js
 * ClientsTab: live roster of every client in the GM's current hub.
 * Identified only by "client id" (join-order index, reused after free)
 * and the ClientSerializer field whitelist the backend sends -- no ipid,
 * hdid or IP ever appear anywhere in this UI.
 */

class ClientsTab extends TabBase {
    /**
     * @param {GMPanelShell} shell
     * @param {ApiClient} api
     * @param {HTMLElement} root
     * @param {?GMLocalContent} localContent - optional; resolves each row's
     *   character icon and backs the per-character color swatch. Safe to
     *   omit -- icons just stay on the text fallback and swatches default
     *   to an unset color.
     */
    constructor(shell, api, root, localContent) {
        super(shell, api, root);
        this.backgroundEvents = true;
        this._localContent = localContent || null;

        this._clients = [];
        // ITEM 2 (v6 brief): area id -> that area's pos_lock length, so a
        // row's <pos> can be dropped per the same rule the inspector uses
        // (pos_lock has exactly 1 entry => everyone present is necessarily
        // there) -- see _loadPosLockCounts()/_rowHtml() below.
        this._posLockCountByArea = {};
        // The full areas payload (fetched alongside the pos_lock counts) so
        // the "Send to…" action can offer a live area picker.
        this._areas = [];
        this._hubLabel = root.querySelector('#clientsHubLabel');
        this._countEl = root.querySelector('#clientsCount');
        this._tbody = root.querySelector('#clientsTbody');

        root.querySelector('#clientsRefreshBtn').addEventListener('click', () => this.reload());
        this._tbody.addEventListener('click', (e) => this._onTableClick(e));
        this._tbody.addEventListener('change', (e) => this._onTableChange(e));

        this._searchQuery = '';
        this._buildClientSearch();
        this._buildMoveModal();
    }

    /** Late-inject local content resolution (mirrors AreasGraphTab). */
    setLocalContent(localContent) {
        this._localContent = localContent || null;
    }

    async activate() {
        super.activate();
        await this.reload();
        this._startPolling();
    }

    deactivate() {
        super.deactivate();
        this._stopPolling();
    }

    _startPolling() {
        if (typeof this.api.startPolling === 'function') {
            this.api.startPolling('clients', () => this.reload(), 4000);
        }
    }

    _stopPolling() {
        if (typeof this.api.stopPolling === 'function') this.api.stopPolling('clients');
    }

    async reload() {
        try {
            const data = await this.api.getClients();
            this._clients = data.clients || [];
            this._hubLabel.textContent = `Hub ${data.hub_id}`;
            await this._loadPosLockCounts();
            this._render();
        } catch (e) {
            this.shell.toast('Failed to load clients: ' + e.message, 'error');
        }
    }

    /** ITEM 2 (v6 brief): the areas payload (`/api/gm/areas`, the same
     * snapshot the graph tab uses) carries each area's `pos_lock` -- the
     * clients list itself has no such thing, so a small extra fetch here
     * is what lets a row's <pos> follow the exact same drop rule as the
     * area inspector's occupant list. Best-effort: a failure here just
     * means every row shows its pos (the more-informative default), not a
     * broken page. */
    async _loadPosLockCounts() {
        try {
            const areasData = await this.api.getAreas();
            this._areas = areasData.areas || [];
            const map = {};
            this._areas.forEach((a) => {
                map[a.id] = Array.isArray(a.pos_lock) ? a.pos_lock.length : 0;
            });
            this._posLockCountByArea = map;
        } catch (e) {
            this._areas = [];
            this._posLockCountByArea = {};
        }
    }

    onEvent(msg) {
        const relevant = [
            'client_present', 'client_absent', 'client_moved', 'client_disconnected',
            'hub_gm_roster_changed', 'area_cm_roster_changed',
        ];
        if (relevant.includes(msg.type)) this.reload();
    }

    _render() {
        this._countEl.textContent = `${this._clients.length} online`;
        if (!this._clients.length) {
            this._tbody.innerHTML = '<tr><td colspan="9" class="gm-empty">No clients in this hub.</td></tr>';
            return;
        }
        this._tbody.innerHTML = this._clients.map((c) => this._rowHtml(c)).join('');
        this._loadIcons();
        this._applyClientSearch({ scroll: false });
    }

    /** Toolbar search: live-filter the roster, highlight the first match
     * and (on user-typed changes) scroll it into view. The query matches
     * showname, OOC name, character folder (incl. iniswap), client id, or
     * area ("A3"). Filters re-apply after every poll-driven re-render so
     * the search survives refreshes without the user doing anything. */
    _buildClientSearch() {
        const toolbar = this.root.querySelector('.gm-toolbar');
        if (!toolbar) return;
        const input = createGmSearchBox('Find client…', (v) => {
            this._searchQuery = v;
            this._applyClientSearch({ scroll: true });
        });
        toolbar.appendChild(input);
        this._clientSearchInput = input;
    }

    _applyClientSearch(opts) {
        opts = opts || {};
        const q = (this._searchQuery || '').trim().toLowerCase();
        const rows = Array.from(this._tbody.querySelectorAll('tr[data-id]'));
        let firstMatch = null;
        rows.forEach((row) => {
            const c = this._clients.find((x) => String(x.id) === String(row.dataset.id));
            let hay = '';
            if (c) {
                hay = [c.showname, c.name, this._folderKey(c), String(c.id), c.area_id !== undefined && c.area_id !== null ? 'A' + c.area_id : '']
                    .filter(Boolean).join(' ').toLowerCase();
            }
            const match = !q || hay.includes(q);
            row.classList.toggle('gm-search-row-hidden', !match);
            if (q && match && firstMatch === null) firstMatch = row;
        });
        rows.forEach((row) => {
            if (q) row.classList.toggle('gm-search-match', row === firstMatch);
            else row.classList.remove('gm-search-match');
        });
        if (opts.scroll && firstMatch) firstMatch.scrollIntoView({ block: 'nearest' });
    }

    /** The character folder to key icon/color lookups on -- accounts for
     * iniswap, matching what the server actually renders for the client. */
    _folderKey(c) {
        return c.iniswap || c.char_name || '';
    }

    _rowHtml(c) {
        const badges = [
            c.is_mod ? '<span class="badge mod">MOD</span>' : '',
            c.is_hub_gm ? '<span class="badge gm">GM</span>' : '',
            c.is_area_cm ? '<span class="badge cm">CM</span>' : '',
            c.is_afk ? '<span class="badge afk">AFK</span>' : '',
            c.hidden ? '<span class="badge hidden">HIDDEN</span>' : '',
        ].filter(Boolean).join(' ');

        const actionBtns = [];
        if (c.is_hub_gm) {
            actionBtns.push(`<button class="btn-sm danger" data-action="ungm" data-id="${c.id}" title="Remove from hub GM roster">Demote</button>`);
        } else {
            actionBtns.push(`<button class="btn-sm" data-action="gm" data-id="${c.id}" ${c.is_mod ? 'disabled title="Already staff"' : ''} title="Add to hub GM roster">Promote to GM</button>`);
        }
        actionBtns.push(`<button class="btn-sm" data-action="pm" data-id="${c.id}" title="Private message this player">PM</button>`);
        actionBtns.push(`<button class="btn-sm" data-action="teleport-here" data-id="${c.id}" title="Move this player to your current area">Bring here</button>`);
        actionBtns.push(`<button class="btn-sm" data-action="teleport-area" data-id="${c.id}" title="Move this player to a chosen area">Send to…</button>`);
        const actionBtn = `<span class="gm-client-actions">${actionBtns.join('')}</span>`;

        const folder = this._folderKey(c);
        const color = this._localContent ? this._localContent.getClientColor(folder) : null;

        // ITEM 2 (v6 brief): the Character cell reuses buildClientLabel()
        // (gm-utils.js) -- literally the same helper the area inspector's
        // occupant list uses -- for the folder ("base/iniswap" when
        // iniswapped, matching the inspector exactly, replacing this
        // column's old "(iniswap: X)" annotation) and the new <pos> part.
        // Icon/role-badge/id/showname are deliberately left out of this
        // cell: this row already has its own dedicated Icon, Status and
        // Showname/ID columns, so pulling those pieces in too would just
        // duplicate them right next to themselves.
        const dropPos = this._posLockCountByArea[c.area_id] === 1;
        const label = buildClientLabel(c, { dropPos });
        const charCell = [label.folderHtml || '<span class="dim">(none)</span>', label.posHtml]
            .filter(Boolean).join(' ');

        return `<tr data-id="${c.id}">
            <td class="mono">#${c.id}</td>
            <td>
                <span class="gm-icon-slot" data-cid="${c.id}"><span class="gm-icon-fallback">${esc((c.char_name || '?').slice(0, 1).toUpperCase())}</span></span>
                <button class="btn-sm gm-icon-set-btn" data-action="set-icon" data-id="${c.id}" title="Set a local icon override for this character folder">Set icon</button>
            </td>
            <td>${charCell}</td>
            <td>${esc(c.showname || '')}</td>
            <td>${esc(c.name || '')}</td>
            <td>A${c.area_id}</td>
            <td>${badges || '<span class="dim">—</span>'}</td>
            <td><input type="color" class="gm-color-input" data-id="${c.id}" data-folder="${esc(folder)}" value="${esc(color || '#4a4f66')}" title="Marker color for ${esc(folder || 'this character')}"></td>
            <td>${actionBtn}</td>
        </tr>`;
    }

    async _loadIcons() {
        if (!this._localContent) return;
        this._clients.forEach((c) => {
            const folder = this._folderKey(c);
            if (!folder) return;
            this._localContent.resolve('char_icon', folder).then((url) => {
                if (!url) return;
                const slot = this._tbody.querySelector(`.gm-icon-slot[data-cid="${c.id}"]`);
                if (!slot) return;
                const img = document.createElement('img');
                img.className = 'gm-char-icon-img';
                img.alt = folder;
                img.src = url;
                img.addEventListener('error', () => { img.remove(); });
                slot.innerHTML = '';
                slot.appendChild(img);
            }).catch(() => { /* keep the text fallback */ });
        });
    }

    _onTableClick(e) {
        const iconBtn = e.target.closest('button[data-action="set-icon"]');
        if (iconBtn) { this._promptIconOverride(iconBtn.dataset.id); return; }
        const btn = e.target.closest('button[data-action]');
        if (!btn || btn.disabled) return;
        if (btn.dataset.action === 'teleport-area') {
            const client = this._clients.find((c) => String(c.id) === String(btn.dataset.id));
            if (client) this._openMoveModal(client);
            return;
        }
        this._runAction(btn.dataset.action, btn.dataset.id);
    }

    _onTableChange(e) {
        const input = e.target.closest('input.gm-color-input');
        if (!input || !this._localContent) return;
        const folder = input.dataset.folder;
        if (!folder) { this.shell.toast('This client has no character folder to attach a color to.', 'error'); return; }
        this._localContent.setClientColor(folder, input.value);
        this.shell.toast(`Color saved for ${folder}.`, 'success');
    }

    _promptIconOverride(clientId) {
        if (!this._localContent) return;
        const client = this._clients.find((c) => String(c.id) === String(clientId));
        if (!client) return;
        const folder = this._folderKey(client);
        if (!folder) { this.shell.toast('This client has no character folder to override.', 'error'); return; }
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'image/*';
        input.addEventListener('change', async () => {
            const file = input.files && input.files[0];
            if (!file) return;
            try {
                await this._localContent.setOverride('char_icon', folder, file);
                this.shell.toast(`Icon override saved for ${folder}.`, 'success');
                this._loadIcons();
            } catch (e) {
                this.shell.toast('Failed to save icon override: ' + e.message, 'error');
            }
        });
        input.click();
    }

    async _runAction(action, id, opts) {
        opts = opts || {};
        const client = this._clients.find((c) => String(c.id) === String(id));
        const label = client ? (client.showname || client.name || `#${client.id}`) : `#${id}`;
        try {
            let result;
            if (action === 'pm') {
                const message = window.prompt(`Private message to ${label} (sent as you via /pm):`, '');
                if (message === null || !message.trim()) return;
                result = await this.api.pmClient(id, message.trim());
            } else if (action === 'teleport-here') {
                if (!window.confirm(`Move ${label} to your current area?`)) return;
                result = await this.api.teleportClientHere(id);
            } else if (action === 'teleport-area') {
                result = await this.api.teleportClientToArea(id, opts.area_id, opts.pos || '');
            } else if (action === 'ungm') {
                if (!window.confirm(`Demote ${label} from GM?`)) return;
                result = await this.api.demoteClient(id);
            } else { // 'gm'
                result = await this.api.promoteClient(id);
            }
            const text = (result.output || []).join(' ') || (result.ok ? 'Done.' : 'Command failed.');
            this.shell.toast(text, result.ok ? 'success' : 'error');
            await this.reload();
        } catch (e) {
            this.shell.toast('Failed: ' + e.message, 'error');
        }
    }

    // --- "Send to…" (teleport to area) modal -------------------------------

    _buildMoveModal() {
        const backdrop = document.createElement('div');
        backdrop.className = 'gm-modal-backdrop hidden';
        backdrop.id = 'clientsMoveModal';
        backdrop.innerHTML = `
            <div class="gm-modal">
                <div class="gm-modal-header">
                    <h3>Teleport Player</h3>
                    <button type="button" class="btn-sm" data-action="close">Close</button>
                </div>
                <div class="gm-modal-body">
                    <p class="dim" id="clientsMoveTargetLabel"></p>
                    <div class="gm-inline-form">
                        <span class="dim">To area:</span>
                        <select id="clientsMoveAreaSelect"></select>
                    </div>
                    <div class="gm-inline-form">
                        <span class="dim">Position (optional):</span>
                        <input type="text" id="clientsMovePosInput" placeholder="e.g. wit / def / pro">
                    </div>
                    <div class="gm-toolbar">
                        <button class="btn-sm" id="clientsMoveConfirmBtn">Teleport</button>
                        <button class="btn-sm" data-action="close">Cancel</button>
                    </div>
                </div>
            </div>`;
        this.root.appendChild(backdrop);

        this._moveModal = backdrop;
        this._moveTarget = null;
        this._moveTargetLabel = backdrop.querySelector('#clientsMoveTargetLabel');
        this._moveAreaSelect = backdrop.querySelector('#clientsMoveAreaSelect');
        this._movePosInput = backdrop.querySelector('#clientsMovePosInput');

        backdrop.querySelectorAll('[data-action="close"]').forEach((b) =>
            b.addEventListener('click', () => this._closeMoveModal()));
        backdrop.querySelector('#clientsMoveConfirmBtn').addEventListener('click', () => this._confirmMove());
        backdrop.addEventListener('click', (e) => { if (e.target === backdrop) this._closeMoveModal(); });
    }

    _openMoveModal(client) {
        if (!this._areas.length) {
            this.shell.toast('Area list is not loaded yet; try again in a moment.', 'error');
            return;
        }
        this._moveTarget = client;
        this._moveTargetLabel.textContent =
            `Move ${client.showname || client.name || ('#' + client.id)} (#${client.id}) to another area.`;
        this._moveAreaSelect.innerHTML = this._areas
            .map((a) => `<option value="${a.id}">A${a.id}: ${esc(a.name)}</option>`)
            .join('');
        this._movePosInput.value = '';
        this._moveModal.classList.remove('hidden');
    }

    _closeMoveModal() {
        this._moveModal.classList.add('hidden');
        this._moveTarget = null;
    }

    async _confirmMove() {
        const client = this._moveTarget;
        if (!client) return;
        const areaId = this._moveAreaSelect.value;
        const pos = this._movePosInput.value.trim();
        this._closeMoveModal();
        if (areaId === '') return;
        await this._runAction('teleport-area', client.id, { area_id: areaId, pos });
    }
}
