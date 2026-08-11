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

    getCommandCatalog() { return this.get('/api/gm/commands'); }
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

    // --- Demos tab (§3.6) -------------------------------------------------

    getDemos(areaId) {
        const q = areaId !== undefined && areaId !== null ? `?area_id=${encodeURIComponent(areaId)}` : '';
        return this.get(`/api/gm/demos${q}`);
    }
    getDemo(areaId, demoId) { return this.get(`/api/gm/demos/${areaId}/${demoId}`); }
    putDemo(areaId, demoId, fields) { return this.put(`/api/gm/demos/${areaId}/${demoId}`, fields); }
    newDemo(areaId, fields) { return this.post(`/api/gm/demos/${areaId}/new`, fields); }
    deleteDemo(areaId, demoId) { return this.del(`/api/gm/demos/${areaId}/${demoId}`); }

    runDemo(areaId, demoId) { return this.post(`/api/gm/demos/${areaId}/${demoId}/run`); }
    stopDemo(areaId) { return this.post(`/api/gm/demos/${areaId}/stop`); }
    stopAllDemos(areaId) { return this.post(`/api/gm/demos/${areaId}/stop_all`); }
    getDemoStatus(areaId) { return this.get(`/api/gm/demos/${areaId}/status`); }
    evalExpression(areaId, expression) {
        return this.post('/api/gm/demos/eval', { area_id: areaId, expression });
    }

    getDemoPacks() { return this.get('/api/gm/demo_packs'); }
    loadDemoPack(name, areaId, overlay) {
        return this.post(`/api/gm/demo_packs/${encodeURIComponent(name)}/load`, {
            area_id: areaId, overlay: !!overlay,
        });
    }
    saveDemoPack(areaId, name) {
        return this.post('/api/gm/demo_packs/save', { area_id: areaId, name });
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
