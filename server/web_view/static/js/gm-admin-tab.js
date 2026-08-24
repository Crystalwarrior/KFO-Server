/**
 * gm-admin-tab.js
 * AdminTab: the GM panel's port of the legacy admin panel's log viewer
 * (admin.js). The admin console is the shared Commands tab console, and the
 * former players list + OOC/IC monitors now live in the Clients tab (admin
 * quick actions) and the Commands tab (monitor toggles). This tab is the
 * log viewer only -- one unified chronological feed merging the former
 * Area Events / Connections / System-Misc views, with filters,
 * PAGE_SIZE=100 pagination and a "Go Live" stream.
 *
 * It talks only to the admin-gated moderator endpoints (`/api/gm/logs/*`,
 * `/api/gm/logs/live`). Rows come from the merged `/api/gm/logs/events`
 * query (area+connect+misc UNION ALL server-side) so pagination and
 * filtering stay consistent across categories. Live rows stream over the
 * shared `/ws/gm/live` WebSocket: enabling "Go Live" calls
 * `/api/gm/logs/live`, which subscribes this session to
 * `database.subscribe()` server-side and fans the rows out here as
 * `{"type": "area"|"connect"|"misc", "data": {...}}` frames.
 *
 * Only admin-role sessions can reach it; every other session gets a 403 from
 * the server and never sees the tab (the shell hides it).
 */

class AdminTab extends TabBase {
    constructor(shell, api, root) {
        super(shell, api, root);

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

    // --- filters --------------------------------------------------------

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
        try {
            const types = await this.api.getLogEventTypes('all');
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
        const hub = this._filterHub.value;
        const area = this._filterArea.value;
        const evt = this._filterEventType.value;
        if (hub) filters.hub_id = hub;
        if (area) filters.area_id = area;
        if (evt) filters.event_subtype = evt;
        const ipid = this._filterIpid.value;
        if (ipid) filters.ipid = ipid;
        const since = this._filterSince.value;
        if (since) filters.since = new Date(since).toISOString();
        const until = this._filterUntil.value;
        if (until) filters.until = new Date(until).toISOString();
        return filters;
    }

    _applyFilters() {
        // An inverted window (From after To) can never match anything --
        // say so instead of silently rendering an empty table.
        const since = this._filterSince.value;
        const until = this._filterUntil.value;
        if (since && until && new Date(since) > new Date(until)) {
            this.shell.toast('"From" is after "To" -- that range can\'t match any events.', 'error');
            return;
        }
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
            const data = await this.api.getAllEvents(filters);
            this.totalCount = data.total || 0;
            this._renderTable(data.events || []);
            this._updatePagination();
        } catch (e) {
            this._contentEl.innerHTML = `<div class="gm-empty">Failed to load data: ${esc(e.message)}</div>`;
        }
    }

    // One column set for every category, so the merged feed reads in
    // sequence: Time | Kind | Where | Player | OOC Name | IPID | HDID |
    // Target IPID | Event | Details.
    static COLUMNS = '<th>Time</th><th>Kind</th><th>Where</th><th>Player</th><th>OOC Name</th>'
        + '<th>IPID</th><th>HDID</th><th>Target IPID</th><th>Event</th><th>Details</th>';

    _categoryBadge(category) {
        const label = { area: 'AREA', connect: 'CONN', misc: 'MISC' }[category] || (category || '?').toUpperCase();
        return `<span class="event-tag tag-${esc(category || 'misc')}">${label}</span>`;
    }

    _rowHtml(ev) {
        const time = ev.event_time ? this._formatTime(ev.event_time) : '-';
        const kind = this._categoryBadge(ev.category);
        const where = ev.hub_id != null || ev.area_id != null
            ? `${ev.hub_id != null ? `H${ev.hub_id}` : '-'}${ev.area_id != null ? ` · A${ev.area_id}: ${esc(ev.area_name || '')}` : ''}`
            : '-';
        const player = esc(ev.char_name || ev.ipid || '-');
        const ooc = esc(ev.ooc_name || '-');
        let event;
        if (ev.category === 'connect') {
            event = ev.failed
                ? '<span class="event-tag tag-mod">BLOCKED</span>'
                : '<span class="event-tag tag-area">CONNECTED</span>';
        } else {
            event = this._eventTag(ev.event_subtype);
        }
        let details = '-';
        if (ev.category === 'area') details = esc(ev.message || '-');
        else if (ev.category === 'misc' && ev.event_data) {
            details = esc(typeof ev.event_data === 'string' ? ev.event_data : JSON.stringify(ev.event_data));
        }
        return `<td>${time}</td><td>${kind}</td><td>${where}</td><td>${player}</td><td>${ooc}</td>`
            + `<td>${ev.ipid != null ? ev.ipid : '-'}</td><td>${esc(ev.hdid != null ? ev.hdid : '-')}</td>`
            + `<td>${ev.target_ipid != null ? ev.target_ipid : '-'}</td><td>${event}</td><td>${details}</td>`;
    }

    _renderTable(events) {
        if (!events || events.length === 0) {
            this._contentEl.innerHTML = '<div class="gm-empty">No events found</div>';
            return;
        }
        const rows = events.map((ev) => `<tr>${this._rowHtml(ev)}</tr>`).join('');
        this._contentEl.innerHTML =
            `<table class="gm-table"><thead><tr>${AdminTab.COLUMNS}</tr></thead><tbody>${rows}</tbody></table>`;
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

    /** Format an event timestamp for display. DB rows store naive UTC
     * ('YYYY-MM-DD HH:MM:SS'), which `new Date` would misread as *local*
     * time -- tag those with 'Z' so they render as true local times,
     * consistent with what the From/To filters select (they also send
     * local picks converted to UTC). Live frames already carry ISO-Z.
     *
     * Rendered as `DD-MMM-YYYY HH:MM AM/PM` -- the same shape the
     * datetime-local From/To fields display, minus their zero seconds. */
    _formatTime(iso) {
        try {
            const normalized = /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}(:\d{2})?$/.test(iso)
                ? iso.replace(' ', 'T') + 'Z'
                : iso;
            const d = new Date(normalized);
            if (isNaN(d)) return iso;
            const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
            const h24 = d.getHours();
            const h12 = h24 % 12 || 12;
            const mm = String(d.getMinutes()).padStart(2, '0');
            return `${d.getDate()}-${months[d.getMonth()]}-${d.getFullYear()}`
                + ` ${h12}:${mm} ${h24 < 12 ? 'AM' : 'PM'}`;
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
            this._appendLiveRow(msg.data, msg.type);
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

    /** Live rows carry the same shapes the merged query returns, minus a
     * `category` field -- the WS frame's `type` is the category. */
    _appendLiveRow(data, category) {
        const tbody = this._contentEl.querySelector('tbody');
        if (!tbody) { this._loadPage(); return; }

        const tr = document.createElement('tr');
        tr.classList.add('new-row');
        tr.innerHTML = this._rowHtml({ ...data, category });

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