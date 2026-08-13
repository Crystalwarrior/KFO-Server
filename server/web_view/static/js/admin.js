const PAGE_SIZE = 100;
let currentTab = 'area';
let currentPage = 0;
let totalCount = 0;
let liveMode = false;
let ws = null;
let hubsData = [];

(async function init() {
    try {
        const resp = await fetch('/api/hubs');
        if (resp.status === 401) { window.location.href = '/login'; return; }
        hubsData = await resp.json();
        populateHubs();
        loadEventTypes();
        applyFilters();
        startLive();
    } catch(e) {
        document.getElementById('content').innerHTML = '<div class="empty">Failed to connect to server</div>';
    }
})();

async function logout() {
    await fetch('/api/logout', {method: 'POST'});
    window.location.href = '/login';
}

function switchTab(tab) {
    currentTab = tab;
    currentPage = 0;
    document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));

    const isAdmin = tab === 'admin';
    const showLogTools = !isAdmin;

    // Show/hide log viewer vs admin panel
    document.getElementById('logToolbar').style.display = showLogTools ? '' : 'none';
    document.getElementById('content').style.display = showLogTools ? '' : 'none';
    document.getElementById('pagination').style.display = showLogTools && totalCount > 0 ? 'flex' : 'none';
    document.getElementById('adminPanel').style.display = isAdmin ? '' : 'none';

    if (isAdmin) {
        refreshPlayers();
        document.getElementById('adminCmdInput').focus();
        return;
    }

    // Log viewer tabs
    const showArea = tab === 'area';
    document.getElementById('filterHub').parentElement.style.display = showArea ? '' : 'none';
    document.getElementById('filterArea').parentElement.style.display = showArea ? '' : 'none';
    document.getElementById('filterHub').previousElementSibling.style.display = showArea ? '' : 'none';
    document.getElementById('filterArea').previousElementSibling.style.display = showArea ? '' : 'none';
    document.getElementById('eventTypeSep').style.display = showArea ? '' : 'none';
    document.getElementById('eventTypeLabel').style.display = showArea ? '' : 'none';
    document.getElementById('filterEventType').parentElement.style.display = showArea ? '' : 'none';
    loadEventTypes();
    applyFilters();
}

function populateHubs() {
    const sel = document.getElementById('filterHub');
    sel.innerHTML = '<option value="">All Hubs</option>';
    hubsData.forEach(h => {
        const opt = document.createElement('option');
        opt.value = h.hub_id;
        opt.textContent = `Hub ${h.hub_id}: ${h.hub_name}`;
        sel.appendChild(opt);
    });
}

function onHubChange() {
    const hubId = document.getElementById('filterHub').value;
    const areaSel = document.getElementById('filterArea');
    areaSel.innerHTML = '<option value="">All Areas</option>';
    if (hubId === '') {
        hubsData.forEach(h => {
            h.areas.forEach(a => {
                const opt = document.createElement('option');
                opt.value = a.area_id;
                opt.textContent = `[H${h.hub_id}] Area ${a.area_id}: ${a.area_name}`;
                areaSel.appendChild(opt);
            });
        });
    } else {
        const hub = hubsData.find(h => h.hub_id == hubId);
        if (hub) {
            hub.areas.forEach(a => {
                const opt = document.createElement('option');
                opt.value = a.area_id;
                opt.textContent = `Area ${a.area_id}: ${a.area_name}`;
                areaSel.appendChild(opt);
            });
        }
    }
}

async function loadEventTypes() {
    const sel = document.getElementById('filterEventType');
    sel.innerHTML = '<option value="">All Events</option>';
    const category = currentTab === 'area' ? 'area' : 'misc';
    try {
        const resp = await fetch(`/api/event_types?category=${category}`);
        const types = await resp.json();
        types.forEach(t => {
            const opt = document.createElement('option');
            opt.value = t;
            opt.textContent = t;
            sel.appendChild(opt);
        });
    } catch(e) {}
}

function getFilters() {
    const filters = {};
    if (currentTab === 'area') {
        const hub = document.getElementById('filterHub').value;
        const area = document.getElementById('filterArea').value;
        const evt = document.getElementById('filterEventType').value;
        if (hub) filters.hub_id = hub;
        if (area) filters.area_id = area;
        if (evt) filters.event_subtype = evt;
    } else if (currentTab === 'misc') {
        const evt = document.getElementById('filterEventType').value;
        if (evt) filters.event_subtype = evt;
    }
    const ipid = document.getElementById('filterIpid').value;
    if (ipid) filters.ipid = ipid;
    const since = document.getElementById('filterSince').value;
    if (since) filters.since = new Date(since).toISOString();
    const until = document.getElementById('filterUntil').value;
    if (until) filters.until = new Date(until).toISOString();
    return filters;
}

function applyFilters() {
    currentPage = 0;
    loadPage();
}

function clearFilters() {
    document.getElementById('filterHub').value = '';
    document.getElementById('filterArea').value = '';
    document.getElementById('filterEventType').value = '';
    document.getElementById('filterIpid').value = '';
    document.getElementById('filterSince').value = '';
    document.getElementById('filterUntil').value = '';
    applyFilters();
}

async function loadPage() {
    const filters = getFilters();
    filters.limit = PAGE_SIZE;
    filters.offset = currentPage * PAGE_SIZE;

    const params = new URLSearchParams(filters);
    const endpoint = currentTab === 'area' ? 'area_events'
                   : currentTab === 'connect' ? 'connect_events'
                   : 'misc_events';

    try {
        const resp = await fetch(`/api/${endpoint}?${params}`);
        const data = await resp.json();
        totalCount = data.total;
        renderTable(data.events);
        updatePagination();
    } catch(e) {
        document.getElementById('content').innerHTML = '<div class="empty">Failed to load data</div>';
    }
}

function renderTable(events) {
    const content = document.getElementById('content');
    if (!events || events.length === 0) {
        content.innerHTML = '<div class="empty">No events found</div>';
        return;
    }

    let html = '<table><thead><tr>';
    if (currentTab === 'area') {
        html += '<th>Time</th><th>Hub</th><th>Area</th><th>Player</th><th>OOC Name</th><th>Event</th><th>Message</th>';
    } else if (currentTab === 'connect') {
        html += '<th>Time</th><th>IPID</th><th>HDID</th><th>Status</th>';
    } else {
        html += '<th>Time</th><th>IPID</th><th>Target IPID</th><th>Event</th><th>Data</th>';
    }
    html += '</tr></thead><tbody>';

    events.forEach(ev => {
        html += '<tr>';
        if (currentTab === 'area') {
            const time = ev.event_time ? formatTime(ev.event_time) : '-';
            const hub = ev.hub_id != null ? `H${ev.hub_id}` : '-';
            const area = ev.area_id != null ? `A${ev.area_id}: ${esc(ev.area_name||'')}` : '-';
            const player = esc(ev.char_name || ev.ipid || '-');
            const ooc = esc(ev.ooc_name || '-');
            const tag = eventTag(ev.event_subtype);
            const msg = esc(ev.message || '');
            html += `<td>${time}</td><td>${hub}</td><td>${area}</td><td>${player}</td><td>${ooc}</td><td>${tag}</td><td>${msg}</td>`;
        } else if (currentTab === 'connect') {
            const time = ev.event_time ? formatTime(ev.event_time) : '-';
            const status = ev.failed ? '<span class="event-tag tag-mod">BLOCKED</span>' : '<span class="event-tag tag-area">CONNECTED</span>';
            html += `<td>${time}</td><td>${ev.ipid||'-'}</td><td>${esc(ev.hdid||'-')}</td><td>${status}</td>`;
        } else {
            const time = ev.event_time ? formatTime(ev.event_time) : '-';
            const tag = eventTag(ev.event_subtype);
            const data = ev.event_data ? esc(typeof ev.event_data === 'string' ? ev.event_data : JSON.stringify(ev.event_data)) : '-';
            html += `<td>${time}</td><td>${ev.ipid||'-'}</td><td>${ev.target_ipid||'-'}</td><td>${tag}</td><td>${data}</td>`;
        }
        html += '</tr>';
    });

    html += '</tbody></table>';
    content.innerHTML = html;
}

function eventTag(name) {
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

function formatTime(iso) {
    try {
        const d = new Date(iso);
        if (isNaN(d)) return iso;
        return d.toLocaleString();
    } catch(e) { return iso; }
}

function esc(s) {
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
}

function updatePagination() {
    const pag = document.getElementById('pagination');
    if (totalCount === 0) { pag.style.display = 'none'; return; }
    pag.style.display = 'flex';
    const totalPages = Math.ceil(totalCount / PAGE_SIZE);
    document.getElementById('pageInfo').textContent =
        `Page ${currentPage + 1} of ${totalPages} (${totalCount} total)`;
    document.getElementById('prevBtn').disabled = currentPage === 0;
    document.getElementById('nextBtn').disabled = currentPage >= totalPages - 1;
}

function prevPage() { if (currentPage > 0) { currentPage--; loadPage(); } }
function nextPage() { currentPage++; loadPage(); }

function toggleLive() {
    if (liveMode) { stopLive(); } else { startLive(); }
}

function startLive() {
    if (ws) return;
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${proto}//${location.host}/ws/live`);

    ws.onopen = () => {
        liveMode = true;
        document.getElementById('liveBtn').textContent = 'Stop Live';
        document.getElementById('liveBtn').classList.add('active');
        document.getElementById('liveDot').classList.add('connected');
        document.getElementById('statusLeft').textContent = 'Live streaming active';
    };

    ws.onmessage = (evt) => {
        try {
            const entry = JSON.parse(evt.data);
            if (entry.type === 'connected' || entry.type === 'pong') return;
            if (entry.type === 'ooc') {
                if (oocMonitorActive) {
                    appendAdminOutput(`${entry.name}: ${entry.msg}`, 'ooc');
                }
                return;
            }
            if (entry.type === 'ic') {
                if (icMonitorActive) {
                    const name = entry.showname || entry.char_name || `CID:${entry.client_id}`;
                    const charPart = (entry.showname && entry.char_name && entry.showname !== entry.char_name) ? ` (${entry.char_name})` : '';
                    const text = entry.text || '';
                    appendAdminOutput(`[${entry.area_name || 'A' + entry.area_id}] ${name}${charPart}: ${text}`, 'ic');
                }
                return;
            }
            if (entry.type && entry.data) { handleLiveEvent(entry); }
        } catch(e) {}
    };

    ws.onclose = () => { stopLive(); };
    ws.onerror = () => { stopLive(); };

    ws._pingInterval = setInterval(() => {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({type: 'ping'}));
        }
    }, 25000);
}

function stopLive() {
    liveMode = false;
    if (oocMonitorActive) {
        oocMonitorActive = false;
        const toggle = document.getElementById('oocMonitorToggle');
        if (toggle) toggle.checked = false;
    }
    if (icMonitorActive) {
        icMonitorActive = false;
        const toggle = document.getElementById('icMonitorToggle');
        if (toggle) toggle.checked = false;
    }
    if (ws) {
        clearInterval(ws._pingInterval);
        ws.close();
        ws = null;
    }
    document.getElementById('liveBtn').textContent = 'Go Live';
    document.getElementById('liveBtn').classList.remove('active');
    document.getElementById('liveDot').classList.remove('connected');
    document.getElementById('statusLeft').textContent = 'Disconnected';
}

let _playerRefreshTimer = null;

function handleLiveEvent(entry) {
    const data = entry.data;
    if (currentTab === 'area' && entry.type === 'area') {
        appendLiveRow(data, 'area');
    } else if (currentTab === 'connect' && entry.type === 'connect') {
        appendLiveRow(data, 'connect');
    } else if (currentTab === 'misc' && entry.type === 'misc') {
        appendLiveRow(data, 'misc');
    }
    document.getElementById('statusRight').textContent =
        `Last event: ${new Date().toLocaleTimeString()}`;

    if (currentTab === 'admin') {
        clearTimeout(_playerRefreshTimer);
        _playerRefreshTimer = setTimeout(refreshPlayers, 500);
    }
}

function appendLiveRow(data, tab) {
    const tbody = document.querySelector('#content tbody');
    if (!tbody) { loadPage(); return; }

    const tr = document.createElement('tr');
    tr.classList.add('new-row');

    if (tab === 'area') {
        const time = data.event_time ? formatTime(data.event_time) : '-';
        const hub = data.hub_id != null ? `H${data.hub_id}` : '-';
        const area = data.area_id != null ? `A${data.area_id}: ${esc(data.area_name||'')}` : '-';
        const player = esc(data.char_name || data.ipid || '-');
        const ooc = esc(data.ooc_name || '-');
        const tag = eventTag(data.event_subtype);
        const msg = esc(data.message || '');
        tr.innerHTML = `<td>${time}</td><td>${hub}</td><td>${area}</td><td>${player}</td><td>${ooc}</td><td>${tag}</td><td>${msg}</td>`;
    } else if (tab === 'connect') {
        const time = data.event_time ? formatTime(data.event_time) : '-';
        const status = data.failed ? '<span class="event-tag tag-mod">BLOCKED</span>' : '<span class="event-tag tag-area">CONNECTED</span>';
        tr.innerHTML = `<td>${time}</td><td>${data.ipid||'-'}</td><td>${esc(data.hdid||'-')}</td><td>${status}</td>`;
    } else {
        const time = data.event_time ? formatTime(data.event_time) : '-';
        const tag = eventTag(data.event_subtype);
        const d = data.event_data ? esc(typeof data.event_data === 'string' ? data.event_data : JSON.stringify(data.event_data)) : '-';
        tr.innerHTML = `<td>${time}</td><td>${data.ipid||'-'}</td><td>${data.target_ipid||'-'}</td><td>${tag}</td><td>${d}</td>`;
    }

    if (tbody.firstChild) {
        tbody.insertBefore(tr, tbody.firstChild);
    } else {
        tbody.appendChild(tr);
    }

    while (tbody.children.length > PAGE_SIZE) {
        tbody.removeChild(tbody.lastChild);
    }

    totalCount++;
    updatePagination();
}

// --- Admin Tab ---

let adminCmdHistory = [];
let adminCmdHistoryIdx = -1;

async function executeAdminCmd() {
    const input = document.getElementById('adminCmdInput');
    const raw = input.value.trim();
    if (!raw) return;

    // Add to history
    adminCmdHistory.push(raw);
    adminCmdHistoryIdx = adminCmdHistory.length;
    input.value = '';

    const output = document.getElementById('adminOutput');
    const line = document.createElement('div');
    line.className = 'cmd-line';
    line.textContent = raw;
    output.appendChild(line);

    // Parse command and arg (e.g. "/kick 1" -> cmd="kick", arg="1")
    let cmd = raw, arg = '';
    if (raw.startsWith('/')) {
        const parts = raw.slice(1).split(/\s+/);
        cmd = parts[0];
        arg = parts.slice(1).join(' ');
    } else {
        const outDiv = document.createElement('div');
        outDiv.className = 'cmd-output cmd-error';
        outDiv.textContent = 'Commands must start with /. Use /ooc <message> to send OOC chat.';
        output.appendChild(outDiv);
        output.scrollTop = output.scrollHeight;
        input.focus();
        return;
    }

    const body = { cmd, arg };

    const outDiv = document.createElement('div');
    outDiv.className = 'cmd-output';
    outDiv.textContent = 'Running...';
    output.appendChild(outDiv);

    try {
        const resp = await fetch('/api/admin/command', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        const data = await resp.json();

        if (data.error) {
            outDiv.className = 'cmd-output cmd-error';
            outDiv.textContent = data.error;
        } else if (data.output && data.output.length > 0) {
            outDiv.textContent = data.output.join('\n');
        } else {
            outDiv.textContent = 'Command executed (no output).';
        }
    } catch(e) {
        outDiv.className = 'cmd-output cmd-error';
        outDiv.textContent = 'Request failed: ' + e.message;
    }

    output.scrollTop = output.scrollHeight;
}

let oocMonitorActive = false;
let icMonitorActive = false;

function appendAdminOutput(msg, type) {
    const output = document.getElementById('adminOutput');
    if (!output) return;
    const line = document.createElement('div');
    line.className = 'cmd-line' + (type === 'ooc' ? ' ooc-line' : type === 'ic' ? ' ic-line' : type === 'sys' ? ' sys-line' : '');
    line.textContent = msg;
    output.appendChild(line);
    output.scrollTop = output.scrollHeight;
}

async function toggleOocMonitor(enable) {
    try {
        const resp = await fetch('/api/admin/ooc_monitor', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enable }),
        });
        const data = await resp.json();
        if (data.ok) {
            oocMonitorActive = data.monitoring;
            if (data.monitoring) {
                appendAdminOutput(`[SYSTEM] OOC monitoring enabled for ${data.area_name} (A${data.area_id})`, 'sys');
            } else {
                appendAdminOutput('[SYSTEM] OOC monitoring disabled', 'sys');
            }
        } else {
            appendAdminOutput(`[ERROR] ${data.error || 'Failed to toggle OOC monitor'}`, 'sys');
            document.getElementById('oocMonitorToggle').checked = false;
            oocMonitorActive = false;
        }
    } catch (e) {
        appendAdminOutput('[ERROR] Failed to toggle OOC monitor', 'sys');
        document.getElementById('oocMonitorToggle').checked = false;
        oocMonitorActive = false;
    }
}

async function toggleIcMonitor(enable) {
    try {
        const resp = await fetch('/api/admin/ic_monitor', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enable }),
        });
        const data = await resp.json();
        if (data.ok) {
            icMonitorActive = data.monitoring;
            if (data.monitoring) {
                appendAdminOutput(`[SYSTEM] IC monitoring enabled for ${data.area_name} (A${data.area_id})`, 'sys');
            } else {
                appendAdminOutput('[SYSTEM] IC monitoring disabled', 'sys');
            }
        } else {
            appendAdminOutput(`[ERROR] ${data.error || 'Failed to toggle IC monitor'}`, 'sys');
            document.getElementById('icMonitorToggle').checked = false;
            icMonitorActive = false;
        }
    } catch (e) {
        appendAdminOutput('[ERROR] Failed to toggle IC monitor', 'sys');
        document.getElementById('icMonitorToggle').checked = false;
        icMonitorActive = false;
    }
}

async function refreshPlayers() {
    const list = document.getElementById('adminPlayersList');

    try {
        const resp = await fetch('/api/admin/players');
        const players = await resp.json();

        if (players.length === 0) {
            list.innerHTML = '<div class="empty" style="padding:0.5rem">No players connected</div>';
            return;
        }

        window._playerList = players;
        list.innerHTML = '';
        players.forEach((p, i) => {
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
                    <button onclick="adminQuickCmd('/whois ${p.ipid}')" title="Whois">Whois</button>
                    <button class="danger" onclick="adminDangerous('kick', ${i})" title="Kick">Kick</button>
                    <button class="danger" onclick="adminDangerous('ban', ${i})" title="Ban">Ban</button>
                    <button class="danger" onclick="adminDangerous('mute', ${i})" title="Mute">Mute</button>
                    <button onclick="adminDangerous('unmute', ${i})" title="Unmute">Unmute</button>
                    <button class="danger" onclick="adminDangerous('ooc_mute', ${i})" title="OOC Mute">OOC Mute</button>
                    <button onclick="adminDangerous('ooc_unmute', ${i})" title="OOC Unmute">OOC Unmute</button>
                    <button onclick="adminDangerous('pm', ${i})" title="PM">PM</button>
                </span>`;
            list.appendChild(row);
        });
    } catch(e) {
        list.innerHTML = '<div class="empty" style="padding:0.5rem">Failed to load players</div>';
    }
}

function adminQuickCmd(cmd) {
    document.getElementById('adminCmdInput').value = cmd;
    executeAdminCmd();
}

// Dangerous command confirmation system
function adminDangerous(action, idx) {
    const p = window._playerList ? window._playerList[idx] : null;
    if (!p) return;
    const ipid = p.ipid;
    const pname = p.showname || p.char_name || p.name || `ID:${p.id}`;

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
        mute: {
            title: `Mute ${pname}?`,
            fields: [],
            build: () => `/mute ${ipid}`,
        },
        unmute: {
            title: `Unmute ${pname}?`,
            fields: [],
            build: () => `/unmute ${ipid}`,
        },
        ooc_mute: {
            title: `OOC Mute ${pname}?`,
            fields: [],
            build: () => `/ooc_mute ${p.id || pname}`,
        },
        ooc_unmute: {
            title: `OOC Unmute ${pname}?`,
            fields: [],
            build: () => `/ooc_unmute ${p.id || pname}`,
        },
        pm: {
            title: `PM ${pname}?`,
            fields: [{ id: 'message', label: 'Message:', placeholder: 'Type your message...', required: true }],
            build: (vals) => `/pm ${p.id} ${vals.message}`,
        },
    };

    const m = modals[action];
    if (!m) return;

    if (m.fields.length === 0) {
        if (!confirm(m.title)) return;
        adminQuickCmd(m.build({}));
        return;
    }

    showModal(m.title, m.fields, (vals) => {
        if (m.fields.some(f => f.required && !vals[f.id].trim())) {
            alert('Please fill in all required fields.');
            return true; // keep modal open
        }
        adminQuickCmd(m.build(vals));
    });
}

function showModal(title, fields, onSubmit) {
    let existing = document.getElementById('adminModal');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'adminModal';
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
        <div class="modal-box">
            <div class="modal-title">${esc(title)}</div>
            ${fields.map(f => `
                <label class="modal-label">${esc(f.label)}</label>
                <input class="modal-input" type="text" id="modal_${f.id}"
                       placeholder="${esc(f.placeholder)}" data-field="${f.id}">
            `).join('')}
            <div class="modal-actions">
                <button class="modal-cancel" id="modalCancel">Cancel</button>
                <button class="modal-confirm" id="modalConfirm">Confirm</button>
            </div>
        </div>`;

    document.body.appendChild(overlay);

    const firstInput = overlay.querySelector('.modal-input');
    if (firstInput) firstInput.focus();

    function close() { overlay.remove(); }

    overlay.querySelector('#modalCancel').onclick = close;
    overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });

    overlay.querySelector('#modalConfirm').onclick = () => {
        const vals = {};
        overlay.querySelectorAll('.modal-input').forEach(inp => {
            vals[inp.dataset.field] = inp.value;
        });
        const keepOpen = onSubmit(vals);
        if (!keepOpen) close();
    };

    overlay.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') close();
        if (e.key === 'Enter') overlay.querySelector('#modalConfirm').click();
    });
}

// Keyboard shortcuts for admin input
document.addEventListener('keydown', function(e) {
    if (currentTab !== 'admin') return;
    const input = document.getElementById('adminCmdInput');
    if (document.activeElement !== input) return;

    if (e.key === 'Enter') {
        e.preventDefault();
        executeAdminCmd();
    } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        if (adminCmdHistoryIdx > 0) {
            adminCmdHistoryIdx--;
            input.value = adminCmdHistory[adminCmdHistoryIdx];
        }
    } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (adminCmdHistoryIdx < adminCmdHistory.length - 1) {
            adminCmdHistoryIdx++;
            input.value = adminCmdHistory[adminCmdHistoryIdx];
        } else {
            adminCmdHistoryIdx = adminCmdHistory.length;
            input.value = '';
        }
    }
});
