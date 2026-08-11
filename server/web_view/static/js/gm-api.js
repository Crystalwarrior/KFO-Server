/**
 * gm-api.js
 * ApiClient owns every network access the GM panel frontend makes: all
 * REST calls to /api/gm/* and the single /ws/gm/live WebSocket. Nothing
 * else in the frontend talks to fetch()/WebSocket directly -- tabs call
 * typed methods here and subscribe to push events via on()/off().
 */

class ApiError extends Error {
    constructor(message, status, payload) {
        super(message);
        this.name = 'ApiError';
        this.status = status;
        this.payload = payload || null;
    }
}

class ApiClient {
    constructor() {
        this._ws = null;
        this._pingTimer = null;
        this._wsHandlers = new Map(); // event type -> Set<handler>
        this._unauthorizedHandlers = new Set();
        this._pollers = new Map(); // poll name -> interval id
    }

    // --- pub/sub for WebSocket events -------------------------------

    /** Subscribe to a WS event type. Use '*' to receive every event as {type, data}. */
    on(type, handler) {
        if (!this._wsHandlers.has(type)) this._wsHandlers.set(type, new Set());
        this._wsHandlers.get(type).add(handler);
    }

    off(type, handler) {
        const set = this._wsHandlers.get(type);
        if (set) set.delete(handler);
    }

    /** Fired whenever any request comes back 401 (session gone/expired). */
    onUnauthorized(handler) {
        this._unauthorizedHandlers.add(handler);
    }

    _emit(type, data) {
        const direct = this._wsHandlers.get(type);
        if (direct) direct.forEach((fn) => this._safeCall(fn, data));
        const wildcard = this._wsHandlers.get('*');
        if (wildcard) wildcard.forEach((fn) => this._safeCall(fn, { type, data }));
    }

    _safeCall(fn, arg) {
        try { fn(arg); } catch (e) { console.error('[gm-api] handler error', e); }
    }

    // --- low-level REST -----------------------------------------------

    async _request(method, path, body) {
        const opts = { method, credentials: 'same-origin', headers: {} };
        if (body !== undefined) {
            opts.headers['Content-Type'] = 'application/json';
            opts.body = JSON.stringify(body);
        }
        let resp;
        try {
            resp = await fetch(path, opts);
        } catch (e) {
            throw new ApiError('Network error: ' + e.message, 0, null);
        }
        let data = null;
        try { data = await resp.json(); } catch (e) { data = null; }

        if (resp.status === 401) {
            this._unauthorizedHandlers.forEach((fn) => this._safeCall(fn, null));
            throw new ApiError((data && data.error) || 'session_invalid', 401, data);
        }
        if (!resp.ok) {
            throw new ApiError((data && data.error) || `HTTP ${resp.status}`, resp.status, data);
        }
        return data;
    }

    get(path) { return this._request('GET', path); }
    post(path, body) { return this._request('POST', path, body === undefined ? {} : body); }
    put(path, body) { return this._request('PUT', path, body === undefined ? {} : body); }
    del(path) { return this._request('DELETE', path); }

    // --- Auth (§3.1) ----------------------------------------------------

    exchangeToken(token) { return this.post('/api/gm/session/exchange', { token }); }
    getSession() { return this.get('/api/gm/session'); }
    logout() { return this.post('/api/gm/logout'); }

    // --- Areas tab (§3.2) ------------------------------------------------

    getAreas() { return this.get('/api/gm/areas'); }
    setAreaBackground(areaId, background, overlay) {
        return this.post(`/api/gm/areas/${areaId}/background`, { background, overlay });
    }
    getBackgroundThumbBaseUrl() { return this.get('/api/gm/areas/background_thumb_base_url'); }

    // --- Clients tab (§3.3) -----------------------------------------------

    getClients() { return this.get('/api/gm/clients'); }
    promoteClient(clientId) { return this.post(`/api/gm/clients/${clientId}/gm`); }
    demoteClient(clientId) { return this.post(`/api/gm/clients/${clientId}/ungm`); }

    // --- Commands tab (§3.4) ----------------------------------------------
    // GET /api/gm/commands returns { ok, docs_url, groups: [{ module,
    // commands: [{name, summary, usage}] }] } -- an auto-generated reference
    // built from server/commands/'s own submodules (CommandLister), not a
    // hand-curated/allowlisted catalog. It never gates anything: the run
    // endpoint below accepts any command name regardless of what's listed.

    getCommandGroups() { return this.get('/api/gm/commands'); }
    runCommand(cmd, arg) { return this.post('/api/gm/commands/run', { cmd, arg }); }

    // --- Characters tab (§3.5) --------------------------------------------

    getCharacters() { return this.get('/api/gm/characters'); }
    getCharlists() { return this.get('/api/gm/charlists'); }
    applyCharlist(name) { return this.post('/api/gm/charlists/apply', { name }); }

    getCharacterData() { return this.get('/api/gm/character_data'); }
    getCharacterDataFolder(folder) {
        return this.get(`/api/gm/character_data/${encodeURIComponent(folder)}`);
    }
    setCharacterData(folder, key, value) {
        return this.post(`/api/gm/character_data/${encodeURIComponent(folder)}/set`, { key, value });
    }
    getCharacterDataKey(folder, key) {
        return this.get(`/api/gm/character_data/${encodeURIComponent(folder)}/${encodeURIComponent(key)}`);
    }

    getCharacterDataSnapshots() { return this.get('/api/gm/character_data_snapshots'); }
    saveCharacterDataSnapshot(name) { return this.post('/api/gm/character_data_snapshots/save', { name }); }
    loadCharacterDataSnapshot(name) { return this.post('/api/gm/character_data_snapshots/load', { name }); }

    // --- Evidence tab (was "Demos"; §3.6) ----------------------------------
    // Evidence items double as demo scripts (their `desc` holds the script),
    // so run/stop/status/eval still drive the real /demo command underneath
    // -- only the routes and the vocabulary changed.

    getEvidenceList(areaId) {
        const q = areaId !== undefined && areaId !== null ? `?area_id=${encodeURIComponent(areaId)}` : '';
        return this.get(`/api/gm/evidence${q}`);
    }
    getEvidenceItem(areaId, evidenceId) { return this.get(`/api/gm/evidence/${areaId}/${evidenceId}`); }
    putEvidenceItem(areaId, evidenceId, fields) { return this.put(`/api/gm/evidence/${areaId}/${evidenceId}`, fields); }
    newEvidenceItem(areaId, fields) { return this.post(`/api/gm/evidence/${areaId}/new`, fields); }
    deleteEvidenceItem(areaId, evidenceId) { return this.del(`/api/gm/evidence/${areaId}/${evidenceId}`); }

    runEvidence(areaId, evidenceId) { return this.post(`/api/gm/evidence/${areaId}/${evidenceId}/run`); }
    stopEvidence(areaId) { return this.post(`/api/gm/evidence/${areaId}/stop`); }
    stopAllEvidence(areaId) { return this.post(`/api/gm/evidence/${areaId}/stop_all`); }
    getEvidenceStatus(areaId) { return this.get(`/api/gm/evidence/${areaId}/status`); }
    evalExpression(areaId, expression) {
        return this.post('/api/gm/evidence/eval', { area_id: areaId, expression });
    }

    getEvidencePacks() { return this.get('/api/gm/evidence_packs'); }
    loadEvidencePack(name, areaId, overlay) {
        return this.post(`/api/gm/evidence_packs/${encodeURIComponent(name)}/load`, {
            area_id: areaId, overlay: !!overlay,
        });
    }
    saveEvidencePack(areaId, name) {
        return this.post('/api/gm/evidence_packs/save', { area_id: areaId, name });
    }

    // --- Hub Data tab: hub save/load + generic yaml file API ------------
    // Backs the "Hub Data" tab's import/export of every GM-facing yaml
    // kind: hub layouts, evidence packs, character data, music lists and
    // character lists. `kind` is one of the five literals the backend
    // accepts: 'hubs' | 'evidence' | 'character_data' | 'musiclists' | 'charlists'.

    getHubSaves() { return this.get('/api/gm/hub/saves'); }
    saveHub(name) { return this.post('/api/gm/hub/save', { name }); }
    loadHub(name) { return this.post('/api/gm/hub/load', { name }); }

    getDataFiles(kind) { return this.get(`/api/gm/data/${encodeURIComponent(kind)}/files`); }
    getDataFile(kind, name) {
        return this.get(`/api/gm/data/${encodeURIComponent(kind)}/file?name=${encodeURIComponent(name)}`);
    }
    putDataFile(kind, name, content) {
        return this.put(`/api/gm/data/${encodeURIComponent(kind)}/file`, { name, content });
    }

    // Live hub character list (distinct from the saved-file browser above,
    // which is /api/gm/charlists -- this is the editable current roster).
    getCharlist() { return this.get('/api/gm/charlist'); }
    submitCharlist(characters, saveAs) {
        const body = { characters };
        if (saveAs) body.save_as = saveAs;
        return this.post('/api/gm/charlist/submit', body);
    }

    // Live hub musiclist (yaml text of the current music_ref, editable).
    getMusic() { return this.get('/api/gm/music'); }
    applyMusic(name) { return this.post('/api/gm/music/apply', { name }); }

    /** Trigger a browser download of `text` as `filename` -- no server
     * round-trip beyond the GET that already fetched the content. */
    downloadText(filename, text) {
        const blob = new Blob([text], { type: 'text/yaml' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
    }

    // --- Local content fallback (§A6) ---------------------------------------

    /** Server-side asset resolution config, used by GMLocalContent as a
     * fallback when a GM hasn't configured (or is missing an item from)
     * their own local base folder/URL. */
    getAssetsConfig() { return this.get('/api/gm/assets/config'); }

    // --- Polling (§C2) -------------------------------------------------------
    // WS events are the fast path; tabs additionally poll their primary list
    // on a short interval while active so a missed/late WS event (or state
    // that changed before this panel connected) never needs a manual reload.

    /** Start (or restart) a named poll: calls `fn` every `intervalMs` ms.
     * `fn` may return a Promise; poll failures are swallowed so one bad
     * request doesn't kill future ticks. */
    startPolling(name, fn, intervalMs) {
        this.stopPolling(name);
        const id = setInterval(() => {
            try {
                Promise.resolve(fn()).catch(() => { /* transient poll failure */ });
            } catch (e) { /* transient poll failure */ }
        }, intervalMs);
        this._pollers.set(name, id);
    }

    stopPolling(name) {
        const id = this._pollers.get(name);
        if (id !== undefined) {
            clearInterval(id);
            this._pollers.delete(name);
        }
    }

    /** Stop every active poll (used on logout/teardown). */
    stopAllPolling() {
        this._pollers.forEach((id) => clearInterval(id));
        this._pollers.clear();
    }

    // --- WebSocket (§3.7) -------------------------------------------------

    get wsConnected() {
        return !!this._ws && this._ws.readyState === WebSocket.OPEN;
    }

    connectWebSocket() {
        if (this._ws) return;
        const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const ws = new WebSocket(`${proto}//${location.host}/ws/gm/live`);
        this._ws = ws;

        ws.onopen = () => {
            this._emit('_open', {});
            this._pingTimer = setInterval(() => {
                if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'ping' }));
            }, 25000);
        };
        ws.onmessage = (evt) => {
            let msg;
            try { msg = JSON.parse(evt.data); } catch (e) { return; }
            if (!msg || !msg.type) return;
            this._emit(msg.type, msg.data || {});
        };
        ws.onclose = () => { this._teardownWs(); this._emit('_close', {}); };
        ws.onerror = () => { this._teardownWs(); this._emit('_error', {}); };
    }

    disconnectWebSocket() {
        if (this._ws) {
            try { this._ws.close(); } catch (e) { /* already closing */ }
        }
        this._teardownWs();
    }

    _teardownWs() {
        if (this._pingTimer) { clearInterval(this._pingTimer); this._pingTimer = null; }
        this._ws = null;
    }
}
