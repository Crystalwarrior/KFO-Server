/**
 * gm-admin-tab.js
 * AdminTab: the GM panel's port of the legacy admin panel's log viewer +
 * admin console (admin.js). This is the ONLY tab that talks to the
 * moderator endpoints (`/api/gm/logs/*`, `/api/gm/admin/*`, `/ws/gm/admin_live`)
 * and it is only reachable by admin-role sessions; every other session gets a
 * 403 from the server and never sees the tab (the shell hides it).
 *
 * Logic is ported from admin.js (log sub-tabs, filters, PAGE_SIZE=100
 * pagination, live mode, event-tag coloring, console + history, per-player
 * quick actions + modals, OOC/IC monitors) but re-expressed as a TabBase
 * subclass with gm.css variables + a scoped <style> block, exactly like
 * gm-commands-tab.js does.
 */

class AdminTab extends TabBase {
    constructor(shell, api, root) {
        super(shell, api, root);
        this.backgroundEvents = false; // owns its own WS + polling, not the shared stream

        this.currentTab = 'area';       // area | connect | misc | admin
        this.currentPage = 0;
        this.totalCount = 0;
        this.liveMode = false;
        this.ws = null;
        this.hubsData = [];
        this.adminCmdHistory = [];
        this.adminCmdHistoryIdx = -1;
        this.oocMonitorActive = false;
        this.icMonitorActive = false;
        this._players = [];
        this._playerRefreshTimer = null;

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
                    <button class="gm-admin-subtab" data-tab="admin">Admin</button>
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

                <div class="gm-admin-panel" id="admPanel" style="display:none">
                    <div class="gm-admin-output" id="admOutput"></div>
                    <div class="gm-admin-input-bar">
                        <input type="text" id="admCmdInput" placeholder="Type a command, e.g. /kick 1" autocomplete="off" spellcheck="false">
                        <button class="btn-sm" id="admRunBtn">Run</button>
                    </div>
                    <div class="gm-admin-players">
                        <div class="gm-admin-players-header">
                            <span>Online Players</span>
                            <label title="Forward all OOC from your current area to the console">
                                <input type="checkbox" id="admOocToggle"> Monitor OOC
                            </label>
                            <label title="Forward all IC from your current area to the console">
                                <input type="checkbox" id="admIcToggle"> Monitor IC
                            </label>
                            <button class="btn-sm" id="admRefreshPlayers">Refresh</button>
                        </div>
                        <div class="gm-admin-players-list gm-scroll-area" id="admPlayersList"></div>
                    </div>
                </div>

                <div class="gm-admin-pagination" id="admPagination" style="display:none">
                    <button class="btn-sm" id="admPrevBtn">Previous</button>
                    <span id="admPageInfo"></span>
                    <button class="btn-sm" id="admNextBtn">Next</button>
                </div>
            </div>`;

        this._logTool = this.root.querySelector('#admLogTool');
        this._contentEl = this.root.querySelector('#admContent');
        this._panel = this.root.querySelector('#admPanel');
        this._pagination = this.root.querySelector('#admPagination');
        this._outputEl = this.root.querySelector('#admOutput');
        this._cmdInput = this.root.querySelector('#admCmdInput');
        this._playersList = this.root.querySelector('#admPlayersList');

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
        this.root.querySelector('#admRunBtn').addEventListener('click', () => this._executeAdminCmd());
        this.root.querySelector('#admRefreshPlayers').addEventListener('click', () => this._refreshPlayers());

        this._cmdInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') { e.preventDefault(); this._executeAdminCmd(); }
            else if (e.key === 'ArrowUp') {
                e.preventDefault();
                if (this.adminCmdHistoryIdx > 0) {
                    this.adminCmdHistoryIdx--;
                    this._cmdInput.value = this.adminCmdHistory[this.adminCmdHistoryIdx];
                }
            } else if (e.key === 'ArrowDown') {
                e.preventDefault();
                if (this.adminCmdHistoryIdx < this.adminCmdHistory.length - 1) {
                    this.adminCmdHistoryIdx++;
                    this._cmdInput.value = this.adminCmdHistory[this.adminCmdHistoryIdx];
                } else {
                    this.adminCmdHistoryIdx = this.adminCmdHistory.length;
                    this._cmdInput.value = '';
                }
            }
        });

        this.root.querySelector('#admOocToggle').addEventListener('change', (e) => this._toggleOocMonitor(e.target.checked));
        this.root.querySelector('#admIcToggle').addEventListener('change', (e) => this._toggleIcMonitor(e.target.checked));

        this._playersList.addEventListener('click', (e) => {
            const btn = e.target.closest('button[data-action]');
            if (!btn) return;
            const idx = Number(btn.dataset.idx);
            this._adminDangerous(btn.dataset.action, idx);
        });
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

        const isAdmin = tab === 'admin';
        this._logTool.style.display = isAdmin ? 'none' : '';
        this._contentEl.style.display = isAdmin ? 'none' : '';
        this._pagination.style.display = isAdmin ? 'none' : (this.totalCount > 0 ? 'flex' : 'none');
        this._panel.style.display = isAdmin ? '' : 'none';

        if (isAdmin) {
            this._refreshPlayers();
            this._cmdInput.focus();
            return;
        }

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
    // --- live mode (own WebSocket to /ws/gm/admin_live) -----------------

    _toggleLive() {
        if (this.liveMode) this._stopLive(); else this._startLive();
    }

    _startLive() {
        if (this.ws) return;
        const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
        this.ws = new WebSocket(`${proto}//${location.host}/ws/gm/admin_live`);

        this.ws.onopen = () => {
            this.liveMode = true;
            this.root.querySelector('#admLiveBtn').textContent = 'Stop Live';
            this.root.querySelector('#admLiveBtn').classList.add('active');
            this.root.querySelector('#admLiveDot').classList.add('connected');
        };

        this.ws.onmessage = (evt) => {
            try {
                const entry = JSON.parse(evt.data);
                if (entry.type === 'connected' || entry.type === 'pong') return;
                if (entry.type === 'ooc') {
                    if (this.oocMonitorActive) this._appendAdminOutput(`${entry.name}: ${entry.msg}`, 'ooc');
                    return;
                }
                if (entry.type === 'ic') {
                    if (this.icMonitorActive) {
                        const name = entry.showname || entry.char_name || `CID:${entry.client_id}`;
                        const charPart = (entry.showname && entry.char_name && entry.showname !== entry.char_name) ? ` (${entry.char_name})` : '';
                        const text = entry.text || '';
                        this._appendAdminOutput(`[${entry.area_name || 'A' + entry.area_id}] ${name}${charPart}: ${text}`, 'ic');
                    }
                    return;
                }
                if (entry.type && entry.data) this._handleLiveEvent(entry);
            } catch (e) { /* ignore malformed frames */ }
        };

        this.ws.onclose = () => this._stopLive();
        this.ws.onerror = () => this._stopLive();

        this.ws._pingInterval = setInterval(() => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ type: 'ping' }));
            }
        }, 25000);
    }

    _stopLive() {
        this.liveMode = false;
        if (this.oocMonitorActive) {
            this.oocMonitorActive = false;
            const toggle = this.root.querySelector('#admOocToggle');
            if (toggle) toggle.checked = false;
            this.api.setOocMonitor(false).catch(() => {});
        }
        if (this.icMonitorActive) {
            this.icMonitorActive = false;
            const toggle = this.root.querySelector('#admIcToggle');
            if (toggle) toggle.checked = false;
            this.api.setIcMonitor(false).catch(() => {});
        }
        if (this.ws) {
            clearInterval(this.ws._pingInterval);
            try { this.ws.close(); } catch (e) { /* already closing */ }
            this.ws = null;
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

        if (this.currentTab === 'admin') {
            clearTimeout(this._playerRefreshTimer);
            this._playerRefreshTimer = setTimeout(() => this._refreshPlayers(), 500);
        }
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

    // --- admin console ---------------------------------------------------

    async _executeAdminCmd() {
        const raw = this._cmdInput.value.trim();
        if (!raw) return;
        this.adminCmdHistory.push(raw);
        this.adminCmdHistoryIdx = this.adminCmdHistory.length;
        this._cmdInput.value = '';

        const line = document.createElement('div');
        line.className = 'cmd-line';
        line.textContent = raw;
        this._outputEl.appendChild(line);

        let cmd = raw, arg = '';
        if (raw.startsWith('/')) {
            const parts = raw.slice(1).split(/\s+/);
            cmd = parts[0];
            arg = parts.slice(1).join(' ');
        } else {
            this._appendAdminOutput('Commands must start with /. Use /ooc <message> to send OOC chat.', 'sys');
            this._cmdInput.focus();
            return;
        }

        const outDiv = document.createElement('div');
        outDiv.className = 'cmd-output';
        outDiv.textContent = 'Running...';
        this._outputEl.appendChild(outDiv);

        try {
            const data = await this.api.runAdminCommand(cmd, arg);
            if (data.error) {
                outDiv.className = 'cmd-output cmd-error';
                outDiv.textContent = data.error;
            } else if (data.output && data.output.length > 0) {
                outDiv.textContent = data.output.join('\n');
            } else {
                outDiv.textContent = 'Command executed (no output).';
            }
        } catch (e) {
            outDiv.className = 'cmd-output cmd-error';
            outDiv.textContent = 'Request failed: ' + e.message;
        }
        this._outputEl.scrollTop = this._outputEl.scrollHeight;
    }

    _adminQuickCmd(cmd) {
        this._cmdInput.value = cmd;
        this._executeAdminCmd();
    }

    _appendAdminOutput(msg, type) {
        const line = document.createElement('div');
        line.className = 'cmd-line' + (type === 'ooc' ? ' ooc-line' : type === 'ic' ? ' ic-line' : type === 'sys' ? ' sys-line' : '');
        line.textContent = msg;
        this._outputEl.appendChild(line);
        this._outputEl.scrollTop = this._outputEl.scrollHeight;
    }

    // --- players ---------------------------------------------------------

    async _refreshPlayers() {
        const list = this._playersList;
        try {
            const players = await this.api.getPlayers();
            this._players = players || [];
            if (!this._players.length) {
                list.innerHTML = '<div class="gm-empty">No players connected</div>';
                return;
            }
            list.innerHTML = '';
            this._players.forEach((p, i) => {
                const row = document.createElement('div');
                row.className = 'player-row';
                const displayName = esc(p.showname || p.char_name || p.name || `ID:${p.id}`);
                const oocName = esc(p.name || '(none)');
                const charName = esc(p.char_name || '');
                const area = `A${p.area_id}`;
                const ipid = `IPID:${p.ipid}`;
                const clientId = `#${p.id}`;
                const badges = [
                    p.is_mod ? '<span class="badge mod">MOD</span>' : '',
                    p.is_muted ? '<span class="badge muted">MIC</span>' : '',
                    p.is_ooc_muted ? '<span class="badge ooc-muted">OOC</span>' : '',
                ].filter(Boolean).join('');
                row.innerHTML = `
                    <span class="p-id">${clientId}</span>
                    <span class="p-name">${displayName}${charName && charName !== displayName ? ` <span class="p-char">(${charName})</span>` : ''}</span>
                    <span class="p-ooc">${oocName}</span>
                    <span class="p-area">${area}</span>
                    <span class="p-ipid">${ipid}</span>
                    ${badges ? `<span class="p-badges">${badges}</span>` : ''}
                    <span class="p-actions">
                        <button data-action="whois" data-idx="${i}">Whois</button>
                        <button class="danger" data-action="kick" data-idx="${i}">Kick</button>
                        <button class="danger" data-action="ban" data-idx="${i}">Ban</button>
                        <button class="danger" data-action="mute" data-idx="${i}">Mute</button>
                        <button data-action="unmute" data-idx="${i}">Unmute</button>
                        <button class="danger" data-action="ooc_mute" data-idx="${i}">OOC Mute</button>
                        <button data-action="ooc_unmute" data-idx="${i}">OOC Unmute</button>
                        <button data-action="pm" data-idx="${i}">PM</button>
                    </span>`;
                list.appendChild(row);
            });
        } catch (e) {
            list.innerHTML = '<div class="gm-empty">Failed to load players</div>';
        }
    }

    _adminDangerous(action, idx) {
        const p = this._players[idx];
        if (!p) return;
        const ipid = p.ipid;
        const pname = p.showname || p.char_name || p.name || `ID:${p.id}`;

        if (action === 'whois') { this._adminQuickCmd(`/whois ${ipid}`); return; }

        const modals = {
            kick: {
                title: `Kick ${pname}?`,
                fields: [{ id: 'reason', label: 'Reason (optional):', placeholder: 'Optional kick reason', required: false }],
                build: (vals) => `/kick ${ipid}${vals.reason ? ' ' + vals.reason : ''}`,
            },
            ban: {
                title: `Ban ${pname}?`,
                fields: [
                    { id: 'reason', label: 'Reason:', placeholder: 'Ban reason', required: true },
                    { id: 'duration', label: 'Duration (e.g. 6 hours, 1 week, perma):', placeholder: 'Default: 6 hours', required: false },
                ],
                build: (vals) => `/ban ${ipid} "${vals.reason}"${vals.duration ? ' "' + vals.duration + '"' : ''}`,
            },
            mute: { title: `Mute ${pname}?`, fields: [], build: () => `/mute ${ipid}` },
            unmute: { title: `Unmute ${pname}?`, fields: [], build: () => `/unmute ${ipid}` },
            ooc_mute: { title: `OOC Mute ${pname}?`, fields: [], build: () => `/ooc_mute ${p.name || pname}` },
            ooc_unmute: { title: `OOC Unmute ${pname}?`, fields: [], build: () => `/ooc_unmute ${p.name || pname}` },
            pm: {
                title: `PM ${pname}?`,
                fields: [{ id: 'message', label: 'Message:', placeholder: 'Type your message...', required: true }],
                build: (vals) => `/pm ${p.id} ${vals.message}`,
            },
        };

        const m = modals[action];
        if (!m) return;
        if (m.fields.length === 0) {
            if (!window.confirm(m.title)) return;
            this._adminQuickCmd(m.build({}));
            return;
        }
        this._showModal(m.title, m.fields, (vals) => {
            if (m.fields.some((f) => f.required && !vals[f.id].trim())) {
                window.alert('Please fill in all required fields.');
                return true;
            }
            this._adminQuickCmd(m.build(vals));
        });
    }

    // --- OOC / IC monitors ------------------------------------------------

    async _toggleOocMonitor(enable) {
        try {
            const data = await this.api.setOocMonitor(enable);
            if (data.ok) {
                this.oocMonitorActive = !!data.monitoring;
                if (data.monitoring) this._appendAdminOutput(`[SYSTEM] OOC monitoring enabled for ${data.area_name} (A${data.area_id})`, 'sys');
                else this._appendAdminOutput('[SYSTEM] OOC monitoring disabled', 'sys');
            } else {
                this._appendAdminOutput(`[ERROR] ${data.error || 'Failed to toggle OOC monitor'}`, 'sys');
                this.root.querySelector('#admOocToggle').checked = false;
                this.oocMonitorActive = false;
            }
        } catch (e) {
            this._appendAdminOutput('[ERROR] Failed to toggle OOC monitor', 'sys');
            this.root.querySelector('#admOocToggle').checked = false;
            this.oocMonitorActive = false;
        }
    }

    async _toggleIcMonitor(enable) {
        try {
            const data = await this.api.setIcMonitor(enable);
            if (data.ok) {
                this.icMonitorActive = !!data.monitoring;
                if (data.monitoring) this._appendAdminOutput(`[SYSTEM] IC monitoring enabled for ${data.area_name} (A${data.area_id})`, 'sys');
                else this._appendAdminOutput('[SYSTEM] IC monitoring disabled', 'sys');
            } else {
                this._appendAdminOutput(`[ERROR] ${data.error || 'Failed to toggle IC monitor'}`, 'sys');
                this.root.querySelector('#admIcToggle').checked = false;
                this.icMonitorActive = false;
            }
        } catch (e) {
            this._appendAdminOutput('[ERROR] Failed to toggle IC monitor', 'sys');
            this.root.querySelector('#admIcToggle').checked = false;
            this.icMonitorActive = false;
        }
    }

    // --- modal ------------------------------------------------------------

    _showModal(title, fields, onSubmit) {
        let existing = document.getElementById('gmAdminModal');
        if (existing) existing.remove();

        const overlay = document.createElement('div');
        overlay.id = 'gmAdminModal';
        overlay.className = 'gm-modal-backdrop';
        overlay.innerHTML = `
            <div class="gm-modal">
                <div class="gm-modal-header"><h3>${esc(title)}</h3></div>
                <div class="gm-modal-body">
                    ${fields.map((f) => `
                        <label class="dim">${esc(f.label)}</label>
                        <input type="text" class="gm-modal-input" id="gmModal_${f.id}" placeholder="${esc(f.placeholder)}" data-field="${f.id}">
                    `).join('')}
                </div>
                <div class="gm-toolbar">
                    <button class="btn-sm" id="gmModalCancel">Cancel</button>
                    <button class="btn-sm danger" id="gmModalConfirm">Confirm</button>
                </div>
            </div>`;
        document.body.appendChild(overlay);

        const firstInput = overlay.querySelector('.gm-modal-input');
        if (firstInput) firstInput.focus();
        const close = () => overlay.remove();

        overlay.querySelector('#gmModalCancel').onclick = close;
        overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
        overlay.querySelector('#gmModalConfirm').onclick = () => {
            const vals = {};
            overlay.querySelectorAll('.gm-modal-input').forEach((inp) => { vals[inp.dataset.field] = inp.value; });
            if (!onSubmit(vals)) close();
        };
        overlay.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') close();
            if (e.key === 'Enter') overlay.querySelector('#gmModalConfirm').click();
        });
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
            .gm-admin-panel { display: flex; flex-direction: column; gap: 0.5rem; flex: 1 1 auto; min-height: 0; }
            .gm-admin-output {
                background: #0d0d0f; border: 1px solid var(--gm-border); border-radius: 6px;
                padding: 0.5rem; overflow-y: auto; min-height: 8rem; flex: 1 1 auto; min-height: 0;
                font-family: var(--gm-mono, monospace); font-size: 0.8rem; white-space: pre-wrap; word-break: break-word;
            }
            .gm-admin-output .cmd-line { color: var(--gm-text-dim); }
            .gm-admin-output .cmd-line.ooc-line { color: #8fc7ff; }
            .gm-admin-output .cmd-line.ic-line { color: #ffd98f; }
            .gm-admin-output .cmd-line.sys-line { color: var(--gm-accent2); }
            .gm-admin-output .cmd-output { color: var(--gm-text); }
            .gm-admin-output .cmd-error { color: var(--gm-danger); }
            .gm-admin-input-bar { display: flex; gap: 0.5rem; }
            .gm-admin-input-bar input { flex: 1; background: var(--gm-panel-alt); color: var(--gm-text); border: 1px solid var(--gm-border); border-radius: 5px; padding: 0.5rem; }
            .gm-admin-players { border: 1px solid var(--gm-border); border-radius: 6px; overflow: hidden; }
            .gm-admin-players-header { display: flex; align-items: center; gap: 0.8rem; padding: 0.4rem 0.6rem; background: var(--gm-panel-alt); font-size: 0.8rem; }
            .gm-admin-players-header label { display: inline-flex; align-items: center; gap: 0.3rem; cursor: pointer; color: var(--gm-text-dim); }
            .gm-admin-players-list { max-height: 14rem; overflow-y: auto; }
            .player-row {
                display: flex; align-items: center; gap: 0.6rem; padding: 0.35rem 0.6rem;
                border-bottom: 1px solid var(--gm-border); font-size: 0.8rem; flex-wrap: wrap;
            }
            .player-row .p-id { color: var(--gm-text-dim); font-family: var(--gm-mono, monospace); }
            .player-row .p-name { color: var(--gm-text); }
            .player-row .p-char { color: var(--gm-text-dim); }
            .player-row .p-ooc { color: var(--gm-accent2); }
            .player-row .p-area { color: var(--gm-text-dim); }
            .player-row .p-ipid { color: var(--gm-text-dim); font-family: var(--gm-mono, monospace); }
            .badge { padding: 0 0.35rem; border-radius: 3px; font-size: 0.7rem; }
            .badge.mod { background: #6a2a2a; color: #ffd4d4; }
            .badge.muted { background: #6a5a2a; color: #fdf0c9; }
            .badge.ooc-muted { background: #4a4a6a; color: #d4d4ff; }
            .player-row .p-actions { margin-left: auto; display: flex; gap: 0.25rem; flex-wrap: wrap; }
            .player-row .p-actions button {
                background: var(--gm-panel-alt); color: var(--gm-text); border: 1px solid var(--gm-border);
                border-radius: 3px; padding: 0.15rem 0.4rem; font-size: 0.72rem; cursor: pointer;
            }
            .player-row .p-actions button.danger { border-color: var(--gm-danger); color: var(--gm-danger); }
            .gm-admin-pagination { display: flex; align-items: center; gap: 0.6rem; }
            .gm-admin-pagination span { color: var(--gm-text-dim); font-size: 0.8rem; }
            .gm-modal-input { width: 100%; background: var(--gm-panel-alt); color: var(--gm-text); border: 1px solid var(--gm-border); border-radius: 4px; padding: 0.4rem; margin-bottom: 0.5rem; }
        `;
        document.head.appendChild(style);
    }
}