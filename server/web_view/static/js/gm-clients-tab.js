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
        this._hubLabel = root.querySelector('#clientsHubLabel');
        this._countEl = root.querySelector('#clientsCount');
        this._tbody = root.querySelector('#clientsTbody');

        root.querySelector('#clientsRefreshBtn').addEventListener('click', () => this.reload());
        this._tbody.addEventListener('click', (e) => this._onTableClick(e));
        this._tbody.addEventListener('change', (e) => this._onTableChange(e));
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
            this._render();
        } catch (e) {
            this.shell.toast('Failed to load clients: ' + e.message, 'error');
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

        const actionBtn = c.is_hub_gm
            ? `<button class="btn-sm danger" data-action="ungm" data-id="${c.id}">Demote</button>`
            : `<button class="btn-sm" data-action="gm" data-id="${c.id}" ${c.is_mod ? 'disabled title="Already staff"' : ''}>Promote to GM</button>`;

        const folder = this._folderKey(c);
        const color = this._localContent ? this._localContent.getClientColor(folder) : null;

        return `<tr data-id="${c.id}">
            <td class="mono">#${c.id}</td>
            <td>
                <span class="gm-icon-slot" data-cid="${c.id}"><span class="gm-icon-fallback">${esc((c.char_name || '?').slice(0, 1).toUpperCase())}</span></span>
                <button class="btn-sm gm-icon-set-btn" data-action="set-icon" data-id="${c.id}" title="Set a local icon override for this character folder">Set icon</button>
            </td>
            <td>${esc(c.char_name || '(none)')}${c.iniswap ? ` <span class="dim">(iniswap: ${esc(c.iniswap)})</span>` : ''}</td>
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

    async _runAction(action, id) {
        try {
            const result = action === 'gm' ? await this.api.promoteClient(id) : await this.api.demoteClient(id);
            const text = (result.output || []).join(' ') || (result.ok ? 'Done.' : 'Command failed.');
            this.shell.toast(text, result.ok ? 'success' : 'error');
            await this.reload();
        } catch (e) {
            this.shell.toast('Failed: ' + e.message, 'error');
        }
    }
}
