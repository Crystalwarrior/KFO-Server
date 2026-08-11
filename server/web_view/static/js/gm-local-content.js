/**
 * gm-local-content.js
 * GMLocalContent resolves background/character-icon/evidence imagery from
 * a GM-configured local source (a picked directory via the File System
 * Access API, or a base URL), with per-item overrides and a server-side
 * fallback (GET /api/gm/assets/config), plus per-character marker colors.
 *
 * One instance is created by GMPanelShell and handed to tabs via
 * constructor injection -- there is no global/singleton access. Tabs code
 * against this file's public API only; they never touch IndexedDB or the
 * File System Access API themselves.
 *
 * LocalContentSettingsDialog is the small UI layer (pick/clear folder,
 * set URL, browse/clear overrides) that the shell wires to a header
 * button; it only calls GMLocalContent's public methods.
 */

const GM_LC_DB_NAME = 'gm-local-content';
const GM_LC_DB_VERSION = 1;
const GM_LC_HANDLE_STORE = 'handles';
const GM_LC_OVERRIDE_STORE = 'overrides';
const GM_LC_IMAGE_EXTS = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.apng', '.bmp'];

/** Thin promise wrapper around the one IndexedDB database this file uses.
 * Private to GMLocalContent -- nothing outside this file touches it. */
class GMLocalContentStore {
    constructor() {
        this._dbPromise = null;
    }

    _db() {
        if (this._dbPromise) return this._dbPromise;
        this._dbPromise = new Promise((resolve, reject) => {
            if (!('indexedDB' in window)) { reject(new Error('IndexedDB unavailable')); return; }
            const req = indexedDB.open(GM_LC_DB_NAME, GM_LC_DB_VERSION);
            req.onupgradeneeded = () => {
                const db = req.result;
                if (!db.objectStoreNames.contains(GM_LC_HANDLE_STORE)) {
                    db.createObjectStore(GM_LC_HANDLE_STORE);
                }
                if (!db.objectStoreNames.contains(GM_LC_OVERRIDE_STORE)) {
                    db.createObjectStore(GM_LC_OVERRIDE_STORE);
                }
            };
            req.onsuccess = () => resolve(req.result);
            req.onerror = () => reject(req.error || new Error('IndexedDB open failed'));
        });
        return this._dbPromise;
    }

    async get(store, key) {
        const db = await this._db();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(store, 'readonly');
            const req = tx.objectStore(store).get(key);
            req.onsuccess = () => resolve(req.result === undefined ? null : req.result);
            req.onerror = () => reject(req.error);
        });
    }

    async set(store, key, value) {
        const db = await this._db();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(store, 'readwrite');
            tx.objectStore(store).put(value, key);
            tx.oncomplete = () => resolve();
            tx.onerror = () => reject(tx.error);
        });
    }

    async delete(store, key) {
        const db = await this._db();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(store, 'readwrite');
            tx.objectStore(store).delete(key);
            tx.oncomplete = () => resolve();
            tx.onerror = () => reject(tx.error);
        });
    }

    async keys(store) {
        const db = await this._db();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(store, 'readonly');
            const req = tx.objectStore(store).getAllKeys();
            req.onsuccess = () => resolve(req.result || []);
            req.onerror = () => reject(req.error);
        });
    }
}

class GMLocalContent {
    /** @param {ApiClient} api - used only for the server-side asset-config fallback. */
    constructor(api) {
        this.api = api;
        this._store = new GMLocalContentStore();

        this._mode = 'none'; // 'none' | 'folder' | 'url'
        this._baseUrl = '';
        this._dirHandle = null;
        this._dirPermission = 'prompt'; // 'granted' | 'denied' | 'prompt'

        this._serverAssetUrl = '';
        this._serverConfigPromise = null;

        this._resolveCache = new Map(); // "kind:name" -> Promise<string|null>
        this._colors = this._loadColors();
        this._initPromise = null;
    }

    // --- lifecycle ------------------------------------------------------

    /** Idempotent; safe to call multiple times/from multiple places. */
    async init() {
        if (!this._initPromise) this._initPromise = this._doInit();
        return this._initPromise;
    }

    async _doInit() {
        const storedMode = localStorage.getItem('gmLocalContent.mode') || 'none';
        this._baseUrl = localStorage.getItem('gmLocalContent.baseUrl') || '';

        if (storedMode === 'folder' && this._hasFsAccess()) {
            try {
                const handle = await this._store.get(GM_LC_HANDLE_STORE, 'baseDir');
                if (handle) {
                    this._dirHandle = handle;
                    this._mode = 'folder';
                    this._dirPermission = await handle.queryPermission({ mode: 'read' });
                } else {
                    this._mode = 'none';
                }
            } catch (e) {
                this._mode = 'none';
            }
        } else if (storedMode === 'url' && this._baseUrl) {
            this._mode = 'url';
        } else {
            this._mode = 'none';
        }
    }

    _hasFsAccess() {
        return typeof window.showDirectoryPicker === 'function';
    }

    // --- base source management ------------------------------------------

    /** Opens the browser's directory picker (requires a user gesture --
     * call this from a click handler). Persists the handle for reuse
     * across sessions (permission still needs re-granting per browser
     * rules; see reconnectBaseFolder()). */
    async pickBaseFolder() {
        if (!this._hasFsAccess()) {
            throw new Error('This browser does not support picking a local folder (no File System Access API). Use a base URL instead.');
        }
        const handle = await window.showDirectoryPicker({ id: 'gm-local-content', mode: 'read' });
        this._dirHandle = handle;
        this._mode = 'folder';
        this._dirPermission = await handle.requestPermission({ mode: 'read' });
        await this._store.set(GM_LC_HANDLE_STORE, 'baseDir', handle);
        localStorage.setItem('gmLocalContent.mode', 'folder');
        this._resolveCache.clear();
        return this.getBaseInfo();
    }

    /** Re-requests permission on the previously-picked folder (browsers
     * drop directory permission across restarts even though the handle
     * itself persists in IndexedDB). Requires a user gesture. */
    async reconnectBaseFolder() {
        if (!this._dirHandle) throw new Error('No folder has been picked yet.');
        this._dirPermission = await this._dirHandle.requestPermission({ mode: 'read' });
        this._resolveCache.clear();
        return this.getBaseInfo();
    }

    setBaseUrl(url) {
        const trimmed = String(url || '').trim().replace(/\/+$/, '');
        this._baseUrl = trimmed;
        this._mode = trimmed ? 'url' : 'none';
        localStorage.setItem('gmLocalContent.baseUrl', trimmed);
        localStorage.setItem('gmLocalContent.mode', this._mode);
        this._resolveCache.clear();
    }

    async clearBase() {
        this._mode = 'none';
        this._dirHandle = null;
        this._dirPermission = 'prompt';
        this._baseUrl = '';
        localStorage.removeItem('gmLocalContent.baseUrl');
        localStorage.setItem('gmLocalContent.mode', 'none');
        try { await this._store.delete(GM_LC_HANDLE_STORE, 'baseDir'); } catch (e) { /* best effort */ }
        this._resolveCache.clear();
    }

    /** Snapshot of the active base source, for the settings dialog and any
     * "resolved via..." UI hints. */
    getBaseInfo() {
        return {
            mode: this._mode,
            baseUrl: this._baseUrl,
            folderName: this._dirHandle ? this._dirHandle.name : '',
            hasFsAccess: this._hasFsAccess(),
            permission: this._mode === 'folder' ? this._dirPermission : null,
        };
    }

    // --- resolution -------------------------------------------------------

    /**
     * @param {'background'|'char_icon'|'evidence'} kind
     * @param {string} name
     * @returns {Promise<string|null>} an object URL / data URL / plain URL,
     *   or null if nothing resolved anywhere (override, base, server).
     */
    async resolve(kind, name) {
        if (!name) return null;
        const key = `${kind}:${name}`;
        if (this._resolveCache.has(key)) return this._resolveCache.get(key);
        const promise = this._resolveUncached(kind, name).catch(() => null);
        this._resolveCache.set(key, promise);
        return promise;
    }

    async _resolveUncached(kind, name) {
        const override = await this._resolveOverride(kind, name);
        if (override) return override;

        if (this._mode === 'folder') {
            const local = await this._resolveFromFolder(kind, name);
            if (local) return local;
        } else if (this._mode === 'url') {
            const local = this._resolveFromUrl(this._baseUrl, kind, name);
            if (local) return local;
        }
        return this._resolveFromServer(kind, name);
    }

    async _resolveOverride(kind, name) {
        try {
            const record = await this._store.get(GM_LC_OVERRIDE_STORE, `${kind}:${name}`);
            return record && record.dataUrl ? record.dataUrl : null;
        } catch (e) {
            return null;
        }
    }

    async _resolveFromFolder(kind, name) {
        if (!this._dirHandle) return null;
        if (this._dirPermission !== 'granted') {
            try {
                this._dirPermission = await this._dirHandle.queryPermission({ mode: 'read' });
            } catch (e) {
                return null;
            }
            if (this._dirPermission !== 'granted') return null;
        }
        try {
            if (kind === 'background') {
                const dir = await this._walkDir(this._dirHandle, ['background', name]);
                return dir ? await this._firstImageInDir(dir) : null;
            }
            if (kind === 'char_icon') {
                const dir = await this._walkDir(this._dirHandle, ['characters', name]);
                return dir ? await this._fileUrl(dir, 'char_icon.png') : null;
            }
            if (kind === 'evidence') {
                const dir = await this._walkDir(this._dirHandle, ['evidence']);
                if (!dir) return null;
                const direct = await this._fileUrl(dir, name);
                if (direct) return direct;
                if (!/\.[a-z0-9]{2,5}$/i.test(name)) {
                    for (const ext of GM_LC_IMAGE_EXTS) {
                        const withExt = await this._fileUrl(dir, name + ext);
                        if (withExt) return withExt;
                    }
                }
                return null;
            }
        } catch (e) {
            return null;
        }
        return null;
    }

    async _walkDir(root, parts) {
        let dir = root;
        for (const part of parts) {
            try {
                dir = await dir.getDirectoryHandle(part);
            } catch (e) {
                return null;
            }
        }
        return dir;
    }

    async _fileUrl(dir, filename) {
        try {
            const fh = await dir.getFileHandle(filename);
            const file = await fh.getFile();
            return URL.createObjectURL(file);
        } catch (e) {
            return null;
        }
    }

    async _firstImageInDir(dir) {
        if (typeof dir.values !== 'function') return null;
        const names = [];
        try {
            for await (const entry of dir.values()) {
                if (entry.kind === 'file' && GM_LC_IMAGE_EXTS.some((ext) => entry.name.toLowerCase().endsWith(ext))) {
                    names.push(entry.name);
                }
            }
        } catch (e) {
            return null;
        }
        if (!names.length) return null;
        names.sort();
        const preferred = names.find((n) => /^background\./i.test(n));
        return this._fileUrl(dir, preferred || names[0]);
    }

    _resolveFromUrl(base, kind, name) {
        if (!base) return null;
        if (kind === 'background') return `${base}/background/${encodeURIComponent(name)}.png`;
        if (kind === 'char_icon') return `${base}/characters/${encodeURIComponent(name)}/char_icon.png`;
        if (kind === 'evidence') {
            const hasExt = /\.[a-z0-9]{2,5}$/i.test(name);
            return `${base}/evidence/${encodeURIComponent(name)}${hasExt ? '' : '.png'}`;
        }
        return null;
    }

    async _loadServerAssetUrl() {
        if (this._serverConfigPromise) return this._serverConfigPromise;
        this._serverConfigPromise = (async () => {
            try {
                const data = await this.api.getAssetsConfig();
                this._serverAssetUrl = (data && data.asset_url) || '';
            } catch (e) {
                this._serverAssetUrl = '';
            }
            return this._serverAssetUrl;
        })();
        return this._serverConfigPromise;
    }

    async _resolveFromServer(kind, name) {
        const base = await this._loadServerAssetUrl();
        if (!base) return null;
        return this._resolveFromUrl(base, kind, name);
    }

    // --- per-item overrides -------------------------------------------------

    /** @param {File} file */
    async setOverride(kind, name, file) {
        const dataUrl = await this._readFileAsDataUrl(file);
        await this._store.set(GM_LC_OVERRIDE_STORE, `${kind}:${name}`, {
            dataUrl, name: file.name || '', storedAt: Date.now(),
        });
        this._resolveCache.delete(`${kind}:${name}`);
        return dataUrl;
    }

    async clearOverride(kind, name) {
        await this._store.delete(GM_LC_OVERRIDE_STORE, `${kind}:${name}`);
        this._resolveCache.delete(`${kind}:${name}`);
    }

    async hasOverride(kind, name) {
        try {
            const record = await this._store.get(GM_LC_OVERRIDE_STORE, `${kind}:${name}`);
            return !!(record && record.dataUrl);
        } catch (e) {
            return false;
        }
    }

    /** @returns {Promise<Array<{kind:string, name:string}>>} */
    async listOverrides() {
        let keys;
        try {
            keys = await this._store.keys(GM_LC_OVERRIDE_STORE);
        } catch (e) {
            return [];
        }
        return keys.map((k) => {
            const raw = String(k);
            const idx = raw.indexOf(':');
            return idx === -1
                ? { kind: '', name: raw }
                : { kind: raw.slice(0, idx), name: raw.slice(idx + 1) };
        });
    }

    _readFileAsDataUrl(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = () => reject(reader.error || new Error('Failed to read file.'));
            reader.readAsDataURL(file);
        });
    }

    // --- per-character marker colors ---------------------------------------
    // Keyed by character folder name (not client id) so a color survives
    // client-id reuse across reconnects/moves.

    _loadColors() {
        try {
            return JSON.parse(localStorage.getItem('gmLocalContent.colors') || '{}');
        } catch (e) {
            return {};
        }
    }

    _saveColors() {
        localStorage.setItem('gmLocalContent.colors', JSON.stringify(this._colors));
    }

    /** @returns {?string} a CSS color, or null if none is set for `key`. */
    getClientColor(key) {
        if (!key) return null;
        return this._colors[key] || null;
    }

    setClientColor(key, cssColor) {
        if (!key) return;
        if (!cssColor) delete this._colors[key];
        else this._colors[key] = cssColor;
        this._saveColors();
    }
}

/**
 * LocalContentSettingsDialog: the small modal UI for GMLocalContent,
 * reachable from the shell header. Talks only to GMLocalContent's public
 * API and the shell's toast(); never touches the network or storage
 * directly.
 */
class LocalContentSettingsDialog {
    /**
     * @param {GMPanelShell} shell
     * @param {GMLocalContent} localContent
     * @param {HTMLElement} root - the modal backdrop element in gm.html
     */
    constructor(shell, localContent, root) {
        this.shell = shell;
        this.localContent = localContent;
        this.root = root;

        this._infoEl = root.querySelector('#lcBaseInfo');
        this._urlInput = root.querySelector('#lcBaseUrlInput');
        this._overridesEl = root.querySelector('#lcOverridesList');
        this._reconnectBtn = root.querySelector('#lcReconnectFolderBtn');

        root.querySelector('#lcPickFolderBtn').addEventListener('click', () => this._pickFolder());
        this._reconnectBtn.addEventListener('click', () => this._reconnectFolder());
        root.querySelector('#lcClearBaseBtn').addEventListener('click', () => this._clearBase());
        root.querySelector('#lcSetUrlBtn').addEventListener('click', () => this._setUrl());
        root.querySelector('#lcCloseBtn').addEventListener('click', () => this.close());
        root.addEventListener('click', (e) => { if (e.target === root) this.close(); });
        this._overridesEl.addEventListener('click', (e) => this._onOverridesClick(e));
    }

    open() {
        this.root.classList.remove('hidden');
        this._render();
    }

    close() {
        this.root.classList.add('hidden');
    }

    async _pickFolder() {
        try {
            await this.localContent.pickBaseFolder();
            this.shell.toast('Local content folder set.', 'success');
            this._render();
        } catch (e) {
            this.shell.toast('Failed to pick folder: ' + e.message, 'error');
        }
    }

    async _reconnectFolder() {
        try {
            await this.localContent.reconnectBaseFolder();
            this.shell.toast('Folder permission refreshed.', 'success');
            this._render();
        } catch (e) {
            this.shell.toast('Failed to reconnect folder: ' + e.message, 'error');
        }
    }

    async _clearBase() {
        await this.localContent.clearBase();
        this._urlInput.value = '';
        this.shell.toast('Local content source cleared.', 'info');
        this._render();
    }

    _setUrl() {
        const url = this._urlInput.value.trim();
        this.localContent.setBaseUrl(url);
        this.shell.toast(url ? 'Base URL set.' : 'Base URL cleared.', 'success');
        this._render();
    }

    async _onOverridesClick(e) {
        const btn = e.target.closest('button[data-kind][data-name]');
        if (!btn) return;
        await this.localContent.clearOverride(btn.dataset.kind, btn.dataset.name);
        this.shell.toast('Override cleared.', 'info');
        this._render();
    }

    async _render() {
        const info = this.localContent.getBaseInfo();
        let statusLine;
        if (info.mode === 'folder') {
            const perm = info.permission === 'granted' ? 'granted' : 'needs reconnect';
            statusLine = `Local folder: <strong>${esc(info.folderName || '(picked folder)')}</strong> (permission ${esc(perm)})`;
        } else if (info.mode === 'url') {
            statusLine = `Base URL: <strong>${esc(info.baseUrl)}</strong>`;
        } else {
            statusLine = 'No local source configured -- falling back to the server asset URL, then plain placeholders.';
        }
        if (!info.hasFsAccess) {
            statusLine += '<br><span class="dim">This browser does not support picking a local folder; use a base URL instead.</span>';
        }
        this._infoEl.innerHTML = statusLine;
        this._reconnectBtn.classList.toggle('hidden', !(info.mode === 'folder' && info.permission !== 'granted'));
        this._urlInput.value = info.baseUrl || '';

        const overrides = await this.localContent.listOverrides();
        this._overridesEl.innerHTML = overrides.length
            ? overrides.map((o) => `<div class="gm-lc-override-row">
                <span class="mono">${esc(o.kind)}</span><span>${esc(o.name)}</span>
                <button class="btn-sm danger" data-kind="${esc(o.kind)}" data-name="${esc(o.name)}">Clear</button>
              </div>`).join('')
            : '<div class="dim">No per-item overrides saved.</div>';
    }
}
