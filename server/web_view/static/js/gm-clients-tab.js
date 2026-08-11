/**
 * gm-clients-tab.js
 * ClientsTab: live roster of every client in the GM's current hub.
 * Identified only by "client id" (join-order index, reused after free)
 * and the ClientSerializer field whitelist the backend sends -- no ipid,
 * hdid or IP ever appear anywhere in this UI.
 */

class ClientsTab extends TabBase {
    constructor(shell, api, root) {
        super(shell, api, root);
        this.backgroundEvents = true;

        this._clients = [];
        this._hubLabel = root.querySelector('#clientsHubLabel');
        this._countEl = root.querySelector('#clientsCount');
        this._tbody = root.querySelector('#clientsTbody');

        root.querySelector('#clientsRefreshBtn').addEventListener('click', () => this.reload());
        this._tbody.addEventListener('click', (e) => this._onTableClick(e));
    }

    async activate() {
        super.activate();
        await this.reload();
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
            this._tbody.innerHTML = '<tr><td colspan="7" class="gm-empty">No clients in this hub.</td></tr>';
            return;
        }
        this._tbody.innerHTML = this._clients.map((c) => this._rowHtml(c)).join('');
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

        return `<tr>
            <td class="mono">#${c.id}</td>
            <td>${esc(c.char_name || '(none)')}${c.iniswap ? ` <span class="dim">(iniswap: ${esc(c.iniswap)})</span>` : ''}</td>
            <td>${esc(c.showname || '')}</td>
            <td>${esc(c.name || '')}</td>
            <td>A${c.area_id}</td>
            <td>${badges || '<span class="dim">—</span>'}</td>
            <td>${actionBtn}</td>
        </tr>`;
    }

    _onTableClick(e) {
        const btn = e.target.closest('button[data-action]');
        if (!btn || btn.disabled) return;
        this._runAction(btn.dataset.action, btn.dataset.id);
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
