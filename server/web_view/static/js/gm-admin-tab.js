/**
 * gm-admin-tab.js
 * AdminTab: the GM panel's port of the legacy admin panel's log viewer
 * (admin.js). The admin console is the shared Commands tab console, and the
 * former players list + OOC/IC monitors now live in the Clients tab (admin
 * quick actions) and the Commands tab (monitor toggles). This tab is the
 * log viewer only -- the global Area/Connect/Misc event log with filters,
 * PAGE_SIZE=100 pagination and a "Go Live" stream.
 *
 * It talks only to the admin-gated moderator endpoints (`/api/gm/logs/*`,
 * `/api/gm/logs/live`). Live rows stream over the shared `/ws/gm/live`
 * WebSocket: enabling "Go Live" calls `/api/gm/logs/live`, which subscribes
 * this session to `database.subscribe()` server-side and fans the rows out
 * here as `{"type": "area"|"connect"|"misc", "data": {...}}` frames.
 *
 * Only admin-role sessions can reach it; every other session gets a 403 from
 * the server and never sees the tab (the shell hides it).
 */

class AdminTab extends TabBase {
    constructor(shell, api, root) {
        super(shell, api, root);

        this.currentTab = 'area';       // area | connect | misc
        this.currentPage = 0;
        this.totalCount = 0;
        this.liveMode = false;
        this.hubsData = [];

        this._build();
        this._injectStyles();
    }

    // --- DOM construction ---------------------------------------------

    _build() {
        this.root.innerHTML = `
            <div class="gm-admin-tab">
                <div class="gm-admin-subtabs">
                    <button class="gm-admin-subtab active" data-tab="area">Area Events</button>
                    <button class="gm-admin-subtab" data-tab="connect">Connections</button>
                    <button class="gm-admin-subtab" data-tab="misc">System/Misc</button>
                </div>

                <div class="gm-admin-toolbar" id="admLogTool">
                    <button class="btn-sm" id="admLiveBtn">Go Live</button>
                    <span class="live-dot" id="admLiveDot"></span>
                    <label>Hub</label>
                    <select id="admFilterHub"><option value="">All Hubs</option></select>
                    <label>Area</label>
                    <select id="admFilterArea"><option value="">All Areas</option></select>
                    <label>Event</label>
                    <select id="admFilterEventType"><option value="">All Events</option></select>
                    <label>IPID</label>
                    <input type="number" id="admFilterIpid" placeholder="IPID">
                    <label>From</label>
                    <input type="datetime-local" id="admFilterSince">
                    <label>To</label>
                    <input type="datetime-local" id="admFilterUntil">
                    <button class="btn-sm" id="admApplyBtn">Apply</button>
                    <button class="btn-sm" id="admClearBtn">Clear</button>
                </div>

                <div class="gm-admin-content gm-scroll-area" id="admContent"></div>

                <div class="gm-admin-pagination" id="admPagination" style="display:none">
                    <button class="btn-sm" id="admPrevBtn">Previous</button>
                    <span id="admPageInfo"></span>
                    <button class="btn-sm" id="admNextBtn">Next</button>
                </div>
            </div>`;

        this._contentEl = this.root.querySelector('#admContent');
        this._pagination = this.root.querySelector('#admPagination');

        this._filterHub = this.root.querySelector('#admFilterHub');
        this._filterArea = this.root.querySelector('#admFilterArea');
        this._filterEventType = this.root.querySelector('#admFilterEventType');
        this._filterIpid = this.root.querySelector('#admFilterIpid');
        this._filterSince = this.root.querySelector('#admFilterSince');
        this._filterUntil = this.root.querySelector('#admFilterUntil');

        this.root.querySelectorAll('.gm-admin-subtab').forEach((el) => {
            el.addEventListener('click', () => this._switchTab(el.dataset.tab));
        });
        this._filterHub.addEventListener('change', () => this._onHubChange());
        this.root.querySelector('#admApplyBtn').addEventListener('click', () => this._applyFilters());
        this.root.querySelector('#admClearBtn').addEventListener('click', () => this._clearFilters());
        this.root.querySelector('#admLiveBtn').addEventListener('click', () => this._toggleLive());
        this.root.querySelector('#admPrevBtn').addEventListener('click', () => this._prevPage());
        this.root.querySelector('#admNextBtn').addEventListener('click', () => this._nextPage());
    }

    // --- lifecycle ------------------------------------------------------

    async activate() {
        super.activate();
        try {
            this.hubsData = await this.api.getLogHubs();
            this._populateHubs();
        } catch (e) {
            this.shell.toast('Failed to load hubs: ' + e.message, 'error');
        }
        this._loadEventTypes();
        this._loadPage();
        this._startLive();
    }

    deactivate() {
        super.deactivate();
        this._stopLive();
    }

    // --- sub-tabs -------------------------------------------------------

    _switchTab(tab) {
        this.currentTab = tab;
        this.currentPage = 0;
        this.root.querySelectorAll('.gm-admin-subtab').forEach((el) =>
            el.classList.toggle('active', el.dataset.tab === tab));

        const isArea = tab === 'area';
        this._filterHub.style.display = isArea ? '' : 'none';
        this._filterArea.style.display = isArea ? '' : 'none';
        this._filterEventType.style.display = tab === 'connect' ? 'none' : '';
        this._loadEventTypes();
        this._loadPage();
    }

    _populateHubs() {
        this._filterHub.innerHTML = '<option value="">All Hubs</option>';
        this.hubsData.forEach((h) => {
            const opt = document.createElement('option');
            opt.value = h.hub_id;
            opt.textContent = `Hub ${h.hub_id}: ${h.hub_name}`;
            this._filterHub.appendChild(opt);
        });
    }

    _onHubChange() {
        const hubId = this._filterHub.value;
        this._filterArea.innerHTML = '<option value="">All Areas</option>';
        if (hubId === '') {
            this.hubsData.forEach((h) => {
                (h.areas || []).forEach((a) => {
                    const opt = document.createElement('option');
                    opt.value = a.area_id;
                    opt.textContent = `[H${h.hub_id}] Area ${a.area_id}: ${a.area_name}`;
                    this._filterArea.appendChild(opt);
                });
            });
        } else {
            const hub = this.hubsData.find((h) => h.hub_id == hubId);
            if (hub) {
                (hub.areas || []).forEach((a) => {
                    const opt = document.createElement('option');
                    opt.value = a.area_id;
                    opt.textContent = `Area ${a.area_id}: ${a.area_name}`;
                    this._filterArea.appendChild(opt);
                });
            }
        }
    }

    async _loadEventTypes() {
        const sel = this._filterEventType;
        sel.innerHTML = '<option value="">All Events</option>';
        const category = this.currentTab === 'area' ? 'area' : 'misc';
        try {
            const types = await this.api.getLogEventTypes(category);
            (types || []).forEach((t) => {
                const opt = document.createElement('option');
                opt.value = t;
                opt.textContent = t;
                sel.appendChild(opt);
            });
        } catch (e) { /* leave as "All Events" */ }
    }

    _getFilters() {
        const filters = {};
        if (this.currentTab === 'area') {
            const hub = this._filterHub.value;
            const area = this._filterArea.value;
            const evt = this._filterEventType.value;
            if (hub) filters.hub_id = hub;
            if (area) filters.area_id = area;
            if (evt) filters.event_subtype = evt;
        } else if (this.currentTab === 'misc') {
            const evt = this._filterEventType.value;
            if (evt) filters.event_subtype = evt;
        }
        const ipid = this._filterIpid.value;
        if (ipid) filters.ipid = ipid;
        const since = this._filterSince.value;
        if (since) filters.since = new Date(since).toISOString();
        const until = this._filterUntil.value;
        if (until) filters.until = new Date(until).toISOString();
        return filters;
    }

    _applyFilters() {
        this.currentPage = 0;
        this._loadPage();
    }

    _clearFilters() {
        this._filterHub.value = '';
        this._filterArea.value = '';
        this._filterEventType.value = '';
        this._filterIpid.value = '';
        this._filterSince.value = '';
        this._filterUntil.value = '';
        this._applyFilters();
    }

    async _loadPage() {
        const filters = this._getFilters();
        filters.limit = 100;
        filters.offset = this.currentPage * 100;
        try {
            let data;
            if (this.currentTab === 'area') data = await this.api.getAreaEvents(filters);
            else if (this.currentTab === 'connect') data = await this.api.getConnectEvents(filters);
            else data = await this.api.getMiscEvents(filters);
            this.totalCount = data.total || 0;
            this._renderTable(data.events || []);
            this._updatePagination();
        } catch (e) {
            this._contentEl.innerHTML = `<div class="gm-empty">Failed to load data: ${esc(e.message)}</div>`;
        }
    }

    _renderTable(events) {
        if (!events || events.length === 0) {
            this._contentEl.innerHTML = '<div class="gm-empty">No events found</div>';
            return;
        }
        let html = '<table class="gm-table"><thead><tr>';
        if (this.currentTab === 'area') {
            html += '<th>Time</th><th>Hub</th><th>Area</th><th>Player</th><th>OOC Name</th><th>Event</th><th>Message</th>';
        } else if (this.currentTab === 'connect') {
            html += '<th>Time</th><th>IPID</th><th>HDID</th><th>Status</th>';
        } else {
            html += '<th>Time</th><th>IPID</th><th>Target IPID</th><th>Event</th><th>Data</th>';
        }
        html += '</tr></thead><tbody>';
        events.forEach((ev) => {
            html += '<tr>';
            if (this.currentTab === 'area') {
                const time = ev.event_time ? this._formatTime(ev.event_time) : '-';
                const hub = ev.hub_id != null ? `H${ev.hub_id}` : '-';
                const area = ev.area_id != null ? `A${ev.area_id}: ${esc(ev.area_name || '')}` : '-';
                const player = esc(ev.char_name || ev.ipid || '-');
                const ooc = esc(ev.ooc_name || '-');
                const tag = this._eventTag(ev.event_subtype);
                const msg = esc(ev.message || '');
                html += `<td>${time}</td><td>${hub}</td><td>${area}</td><td>${player}</td><td>${ooc}</td><td>${tag}</td><td>${msg}</td>`;
            } else if (this.currentTab === 'connect') {
                const time = ev.event_time ? this._formatTime(ev.event_time) : '-';
                const status = ev.failed ? '<span class="event-tag tag-mod">BLOCKED</span>' : '<span class="event-tag tag-area">CONNECTED</span>';
                html += `<td>${time}</td><td>${ev.ipid || '-'}</td><td>${esc(ev.hdid || '-')}</td><td>${status}</td>`;
            } else {
                const time = ev.event_time ? this._formatTime(ev.event_time) : '-';
                const tag = this._eventTag(ev.event_subtype);
                const d = ev.event_data ? esc(typeof ev.event_data === 'string' ? ev.event_data : JSON.stringify(ev.event_data)) : '-';
                html += `<td>${time}</td><td>${ev.ipid || '-'}</td><td>${ev.target_ipid || '-'}</td><td>${tag}</td><td>${d}</td>`;
            }
            html += '</tr>';
        });
        html += '</tbody></table>';
        this._contentEl.innerHTML = html;
    }

    _eventTag(name) {
        if (!name) return '<span class="event-tag tag-misc">unknown</span>';
        let cls = 'tag-misc';
        if (name.startsWith('chat.')) cls = 'tag-chat';
        else if (name.startsWith('area.')) cls = 'tag-area';
        else if (name.startsWith('music') || name.startsWith('jukebox') || name.startsWith('blockdj')) cls = 'tag-music';
        else if (name.startsWith('evidence')) cls = 'tag-evidence';
        else if (name.startsWith('mod') || name.startsWith('ooc_') || name.startsWith('login') || name.startsWith('kick') || name.startsWith('ban')) cls = 'tag-mod';
        else if (name.startsWith('roll') || name.startsWith('notecard') || name.startsWith('vote') || name.startsWith('coinflip')) cls = 'tag-rp';
        else if (name.startsWith('wtce') || name.startsWith('hp') || name.startsWith('case') || name.startsWith('cm.') || name.startsWith('gm.')) cls = 'tag-connect';
        return `<span class="event-tag ${cls}">${esc(name)}</span>`;
    }

    _formatTime(iso) {
        try {
            const d = new Date(iso);
            if (isNaN(d)) return iso;
            return d.toLocaleString();
        } catch (e) { return iso; }
    }

    _updatePagination() {
        if (this.totalCount === 0) { this._pagination.style.display = 'none'; return; }
        this._pagination.style.display = 'flex';
        const totalPages = Math.ceil(this.totalCount / 100);
        this.root.querySelector('#admPageInfo').textContent =
            `Page ${this.currentPage + 1} of ${totalPages} (${this.totalCount} total)`;
        this.root.querySelector('#admPrevBtn').disabled = this.currentPage === 0;
        this.root.querySelector('#admNextBtn').disabled = this.currentPage >= totalPages - 1;
    }

    _prevPage() { if (this.currentPage > 0) { this.currentPage--; this._loadPage(); } }
    _nextPage() { this.currentPage++; this._loadPage(); }

    // --- live mode (streams over the shared /ws/gm/live) ----------------

    onEvent(msg) {
        if (!this.liveMode) return;
        if (msg.type === 'area' || msg.type === 'connect' || msg.type === 'misc') {
            this._handleLiveEvent(msg);
        }
    }

    _toggleLive() {
        if (this.liveMode) this._stopLive(); else this._startLive();
    }

    async _startLive() {
        if (this.liveMode) return;
        try {
            await this.api.setLogLive(true);
            this.liveMode = true;
            this.root.querySelector('#admLiveBtn').textContent = 'Stop Live';
            this.root.querySelector('#admLiveBtn').classList.add('active');
            this.root.querySelector('#admLiveDot').classList.add('connected');
        } catch (e) {
            this.shell.toast('Failed to start live log: ' + e.message, 'error');
        }
    }

    async _stopLive() {
        if (!this.liveMode) return;
        this.liveMode = false;
        if (this.api && typeof this.api.setLogLive === 'function') {
            try { await this.api.setLogLive(false); } catch (e) { /* best-effort */ }
        }
        const btn = this.root.querySelector('#admLiveBtn');
        if (btn) { btn.textContent = 'Go Live'; btn.classList.remove('active'); }
        const dot = this.root.querySelector('#admLiveDot');
        if (dot) dot.classList.remove('connected');
    }

    _handleLiveEvent(entry) {
        const data = entry.data;
        if (this.currentTab === 'area' && entry.type === 'area') this._appendLiveRow(data, 'area');
        else if (this.currentTab === 'connect' && entry.type === 'connect') this._appendLiveRow(data, 'connect');
        else if (this.currentTab === 'misc' && entry.type === 'misc') this._appendLiveRow(data, 'misc');
    }

    _appendLiveRow(data, tab) {
        const tbody = this._contentEl.querySelector('tbody');
        if (!tbody) { this._loadPage(); return; }

        const tr = document.createElement('tr');
        tr.classList.add('new-row');
        if (tab === 'area') {
            const time = data.event_time ? this._formatTime(data.event_time) : '-';
            const hub = data.hub_id != null ? `H${data.hub_id}` : '-';
            const area = data.area_id != null ? `A${data.area_id}: ${esc(data.area_name || '')}` : '-';
            const player = esc(data.char_name || data.ipid || '-');
            const ooc = esc(data.ooc_name || '-');
            const tag = this._eventTag(data.event_subtype);
            const msg = esc(data.message || '');
            tr.innerHTML = `<td>${time}</td><td>${hub}</td><td>${area}</td><td>${player}</td><td>${ooc}</td><td>${tag}</td><td>${msg}</td>`;
        } else if (tab === 'connect') {
            const time = data.event_time ? this._formatTime(data.event_time) : '-';
            const status = data.failed ? '<span class="event-tag tag-mod">BLOCKED</span>' : '<span class="event-tag tag-area">CONNECTED</span>';
            tr.innerHTML = `<td>${time}</td><td>${data.ipid || '-'}</td><td>${esc(data.hdid || '-')}</td><td>${status}</td>`;
        } else {
            const time = data.event_time ? this._formatTime(data.event_time) : '-';
            const tag = this._eventTag(data.event_subtype);
            const d = data.event_data ? esc(typeof data.event_data === 'string' ? data.event_data : JSON.stringify(data.event_data)) : '-';
            tr.innerHTML = `<td>${time}</td><td>${data.ipid || '-'}</td><td>${data.target_ipid || '-'}</td><td>${tag}</td><td>${d}</td>`;
        }

        if (tbody.firstChild) tbody.insertBefore(tr, tbody.firstChild);
        else tbody.appendChild(tr);
        while (tbody.children.length > 100) tbody.removeChild(tbody.lastChild);
        this.totalCount++;
        this._updatePagination();
    }

    // --- scoped styles ----------------------------------------------------

    _injectStyles() {
        if (document.getElementById('gm-admin-tab-styles')) return;
        const style = document.createElement('style');
        style.id = 'gm-admin-tab-styles';
        style.textContent = `
            .gm-admin-tab { display: flex; flex-direction: column; gap: 0.5rem; height: 100%; }
            .gm-admin-subtabs { display: flex; gap: 0.35rem; flex-wrap: wrap; }
            .gm-admin-subtab {
                background: var(--gm-panel-alt); border: 1px solid var(--gm-border); border-radius: 5px;
                color: var(--gm-text-dim); padding: 0.35rem 0.7rem; cursor: pointer; font-size: 0.82rem;
            }
            .gm-admin-subtab.active { color: var(--gm-accent); border-color: var(--gm-accent); }
            .gm-admin-toolbar { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
            .gm-admin-toolbar label { font-size: 0.75rem; color: var(--gm-text-dim); }
            .gm-admin-toolbar select, .gm-admin-toolbar input {
                background: var(--gm-panel-alt); color: var(--gm-text); border: 1px solid var(--gm-border);
                border-radius: 4px; padding: 0.25rem 0.4rem; font-size: 0.8rem;
            }
            .gm-admin-content { flex: 1 1 auto; min-height: 0; }
            .gm-admin-content table { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
            .gm-admin-content th { position: sticky; top: 0; background: var(--gm-panel-alt); text-align: left; }
            .gm-admin-content th, .gm-admin-content td { padding: 0.3rem 0.5rem; border-bottom: 1px solid var(--gm-border); }
            .gm-admin-content tr.new-row { animation: gmAdminFlash 1.2s ease-out; }
            @keyframes gmAdminFlash { from { background: var(--gm-accent); } to { background: transparent; } }
            .event-tag { display: inline-block; padding: 0.1rem 0.4rem; border-radius: 4px; font-size: 0.72rem; font-family: var(--gm-mono, monospace); }
            .tag-chat { background: #2a4a6a; color: #cfe4ff; }
            .tag-area { background: #2a4a3a; color: #c9f2d9; }
            .tag-music { background: #5a3a6a; color: #ecd4ff; }
            .tag-evidence { background: #6a5a2a; color: #fdf0c9; }
            .tag-mod { background: #6a2a2a; color: #ffd4d4; }
            .tag-rp { background: #2a5a5a; color: #c9f0f0; }
            .tag-connect { background: #4a4a4a; color: #e4e4e4; }
            .tag-misc { background: #4a4a4a; color: #e4e4e4; }
            .gm-admin-pagination { display: flex; align-items: center; gap: 0.6rem; }
            .gm-admin-pagination span { color: var(--gm-text-dim); font-size: 0.8rem; }
        `;
        document.head.appendChild(style);
    }
}