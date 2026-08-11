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
 *
 * Case sensitivity (ITEM 3 in the v4 brief, user-confirmed rule): lowercase
 * is how KFO-Server actually resolves assets -- stored names (an area's
 * `background`, a client's character folder, an evidence `image`) can
 * carry arbitrary casing (e.g. `/bg "Default"`), but real asset hosts
 * (plain static web servers) and unix filesystems are case-sensitive and
 * only serve the lowercase paths the server itself writes/expects. So for
 * every kind (background/char_icon/evidence) the CANONICAL lookup form
 * used to build URL candidates is the lowercased name; original casing is
 * only ever tried as a last-resort extra candidate once every lowercase
 * candidate has failed (see _buildUrlCandidates/_resolveFromUrl below).
 * FS-Access folder mode matches directory entries case-insensitively
 * instead (see _dirEntryCI/_fileEntryCI) since there's no way to know a
 * real folder's on-disk casing up front. Resolve-cache keys (see
 * _cacheKey) are always the lowercased name (+ position, for backgrounds).
 */

const GM_LC_DB_NAME = 'gm-local-content';
const GM_LC_DB_VERSION = 1;
const GM_LC_HANDLE_STORE = 'handles';
const GM_LC_OVERRIDE_STORE = 'overrides';
const GM_LC_IMAGE_EXTS = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.apng', '.bmp'];

/** Standard AO courtroom-position -> background-preview-file mapping (ITEM
 * 3, v4 brief): the file inside a background's folder (or, in URL/server
 * mode, the equivalent path segment) that shows what that position looks
 * like. Keys are lowercase position abbreviations as stored in
 * `area.pos_lock`. */
const GM_LC_POSITION_BG_FILES = {
    def: 'defenseempty',
    pro: 'prosecutorempty',
    wit: 'witnessempty',
    jud: 'judgestand',
    hld: 'helperstand',
    hlp: 'prohelperstand',
    jur: 'jurystand',
    sea: 'seancestand',
};

/** Ordered list of background-preview basenames (no extension) to try for
 * an optional preferred `position` (an area's `pos_lock[0]`), most
 * specific first, always ending in the universal `witnessempty` fallback
 * so every background still resolves *something* when the preferred
 * position has no dedicated asset:
 *   - a known position (per GM_LC_POSITION_BG_FILES) -> its mapped file.
 *   - an unrecognized/custom position -> try `<pos>` then `<pos>empty`
 *     (the same `empty`-suffix convention every standard position file
 *     follows) as literal guesses.
 *   - no position at all -> just `witnessempty`, matching the pre-ITEM-3
 *     behavior exactly. */
function gmLcBackgroundCandidateFiles(position) {
    const names = [];
    const pos = position ? String(position).trim().toLowerCase() : '';
    if (pos) {
        const mapped = GM_LC_POSITION_BG_FILES[pos];
        if (mapped) names.push(mapped);
        else names.push(pos, `${pos}empty`);
    }
    if (names.indexOf('witnessempty') === -1) names.push('witnessempty');
    return names;
}

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
        this._urlCheckCache = new Map(); // url -> Promise<boolean>, reachability of URL-sourced candidates
        this._colors = this._loadColors();
        this._initPromise = null;

        // Other components (the area graph's per-character-folder icon
        // cache, in particular -- see gm-graph.js) may keep their own
        // resolved-URL cache on top of ours for render-loop performance.
        // Without a change notification those caches would keep serving
        // stale results after a per-item override is set/cleared here, so
        // notify any subscriber whenever a resolution for `kind:name` (or,
        // for base-source changes, everything) may have changed.
        this._changeListeners = new Set();
    }

    /**
     * Subscribe to resolution-invalidating changes (per-item override
     * set/cleared, or a base-source change that invalidates everything).
     * @param {(kind: ?string, name: ?string) => void} fn - called with
     *   (kind, name) for a targeted invalidation, or (null, null) when
     *   every cached resolution may have changed.
     * @returns {() => void} unsubscribe function.
     */
    subscribe(fn) {
        if (typeof fn !== 'function') return () => {};
        this._changeListeners.add(fn);
        return () => this._changeListeners.delete(fn);
    }

    _notifyChange(kind, name) {
        for (const fn of this._changeListeners) {
            try { fn(kind || null, name || null); } catch (e) { /* listener errors must not break resolution */ }
        }
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
        this._notifyChange(null, null);
        return this.getBaseInfo();
    }

    /** Re-requests permission on the previously-picked folder (browsers
     * drop directory permission across restarts even though the handle
     * itself persists in IndexedDB). Requires a user gesture. */
    async reconnectBaseFolder() {
        if (!this._dirHandle) throw new Error('No folder has been picked yet.');
        this._dirPermission = await this._dirHandle.requestPermission({ mode: 'read' });
        this._resolveCache.clear();
        this._notifyChange(null, null);
        return this.getBaseInfo();
    }

    setBaseUrl(url) {
        const trimmed = String(url || '').trim().replace(/\/+$/, '');
        this._baseUrl = trimmed;
        this._mode = trimmed ? 'url' : 'none';
        localStorage.setItem('gmLocalContent.baseUrl', trimmed);
        localStorage.setItem('gmLocalContent.mode', this._mode);
        this._resolveCache.clear();
        this._urlCheckCache.clear();
        this._notifyChange(null, null);
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
        this._urlCheckCache.clear();
        this._notifyChange(null, null);
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
     * @param {{position?: string}} [opts] - `background` only: a preferred
     *   courtroom position (an area's `pos_lock[0]`) to try before the
     *   generic `witnessempty` preview -- see gmLcBackgroundCandidateFiles.
     * @returns {Promise<string|null>} an object URL / data URL / plain URL,
     *   or null if nothing resolved anywhere (override, base, server).
     */
    async resolve(kind, name, opts) {
        if (!name) return null;
        const position = (kind === 'background' && opts && opts.position) ? opts.position : null;
        const key = this._cacheKey(kind, name, position);
        if (this._resolveCache.has(key)) return this._resolveCache.get(key);
        const promise = this._resolveUncached(kind, name, position).catch(() => null);
        this._resolveCache.set(key, promise);
        return promise;
    }

    /** Canonical resolve-cache key: always the lowercased name (see the
     * case-sensitivity doc at the top of this file), plus a lowercased
     * position suffix for backgrounds so two areas sharing a background
     * name but differing in pos_lock don't collide on one cached URL. */
    _cacheKey(kind, name, position) {
        const key = `${kind}:${String(name).toLowerCase()}`;
        return position ? `${key}:${String(position).toLowerCase()}` : key;
    }

    /** Delete every resolve-cache entry for `kind`+`name` regardless of
     * position suffix (see _cacheKey) -- used by setOverride/clearOverride
     * so a per-item override change can't leave a stale per-position
     * background resolution cached under a key it doesn't know the exact
     * form of. */
    _invalidateResolveCache(kind, name) {
        const prefix = `${kind}:${String(name).toLowerCase()}`;
        Array.from(this._resolveCache.keys()).forEach((k) => {
            if (k === prefix || k.startsWith(`${prefix}:`)) this._resolveCache.delete(k);
        });
    }

    async _resolveUncached(kind, name, position) {
        const override = await this._resolveOverride(kind, name);
        if (override) return override;

        if (this._mode === 'folder') {
            const local = await this._resolveFromFolder(kind, name, position);
            if (local) return local;
        } else if (this._mode === 'url') {
            const local = await this._resolveFromUrl(this._baseUrl, kind, name, position);
            if (local) return local;
        }
        return this._resolveFromServer(kind, name, position);
    }

    async _resolveOverride(kind, name) {
        try {
            const record = await this._store.get(GM_LC_OVERRIDE_STORE, `${kind}:${name}`);
            return record && record.dataUrl ? record.dataUrl : null;
        } catch (e) {
            return null;
        }
    }

    async _resolveFromFolder(kind, name, position) {
        if (!this._dirHandle) return null;
        if (this._dirPermission !== 'granted') {
            try {
                this._dirPermission = await this._dirHandle.queryPermission({ mode: 'read' });
            } catch (e) {
                return null;
            }
            if (this._dirPermission !== 'granted') return null;
        }
        // Lowercase is the canonical lookup form (see the case-sensitivity
        // doc at the top of this file); _walkDir/_fileUrl below additionally
        // match directory entries case-insensitively (a folder handle
        // carries no way to know its own real on-disk casing up front), so
        // this is primarily about which candidate string gets tried/logged
        // first, not a correctness requirement on its own.
        const lname = String(name).toLowerCase();
        try {
            if (kind === 'background') {
                // AO asset layout: a folder per background, one image per
                // courtroom position. Try the preferred-position file(s)
                // first (see gmLcBackgroundCandidateFiles -- always ends in
                // the universal witnessempty.* fallback), then whatever
                // image sorts first if none of those exist either.
                const dir = await this._walkDir(this._dirHandle, ['background', lname]);
                if (!dir) return null;
                for (const base of gmLcBackgroundCandidateFiles(position)) {
                    for (const ext of ['png', 'webp', 'jpg']) {
                        const direct = await this._fileUrl(dir, `${base}.${ext}`);
                        if (direct) return direct;
                    }
                }
                return this._firstImageInDir(dir);
            }
            if (kind === 'char_icon') {
                const dir = await this._walkDir(this._dirHandle, ['characters', lname]);
                return dir ? await this._fileUrl(dir, 'char_icon.png') : null;
            }
            if (kind === 'evidence') {
                const dir = await this._walkDir(this._dirHandle, ['evidence']);
                if (!dir) return null;
                const direct = await this._fileUrl(dir, lname);
                if (direct) return direct;
                if (!/\.[a-z0-9]{2,5}$/i.test(lname)) {
                    for (const ext of GM_LC_IMAGE_EXTS) {
                        const withExt = await this._fileUrl(dir, lname + ext);
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
            const next = await this._dirEntryCI(dir, part);
            if (!next) return null;
            dir = next;
        }
        return dir;
    }

    /** Case-insensitive `getDirectoryHandle` (see the case-sensitivity doc
     * at the top of this file): tries the exact name first (the fast path
     * -- also the only path needed on a case-insensitive host filesystem,
     * e.g. Windows/macOS), then falls back to scanning entries and
     * matching lowercased names so a real folder on a case-sensitive
     * filesystem (Linux) whose on-disk casing doesn't match `name` still
     * resolves. */
    async _dirEntryCI(dir, name) {
        try {
            return await dir.getDirectoryHandle(name);
        } catch (e) { /* fall through to a case-insensitive scan */ }
        if (typeof dir.entries !== 'function') return null;
        const lower = String(name).toLowerCase();
        try {
            for await (const [entryName, handle] of dir.entries()) {
                if (handle.kind === 'directory' && entryName.toLowerCase() === lower) return handle;
            }
        } catch (e) { /* entries() unsupported/denied -- nothing more to try */ }
        return null;
    }

    /** Case-insensitive `getFileHandle` counterpart to _dirEntryCI. */
    async _fileEntryCI(dir, name) {
        try {
            return await dir.getFileHandle(name);
        } catch (e) { /* fall through to a case-insensitive scan */ }
        if (typeof dir.entries !== 'function') return null;
        const lower = String(name).toLowerCase();
        try {
            for await (const [entryName, handle] of dir.entries()) {
                if (handle.kind === 'file' && entryName.toLowerCase() === lower) return handle;
            }
        } catch (e) { /* entries() unsupported/denied -- nothing more to try */ }
        return null;
    }

    async _fileUrl(dir, filename) {
        try {
            const fh = await this._fileEntryCI(dir, filename);
            if (!fh) return null;
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

    /**
     * Builds the ordered list of candidate URLs for a (base, kind, name)
     * triple, most-preferred first. AO asset layout for backgrounds is a
     * folder per background holding one image per courtroom position (see
     * gmLcBackgroundCandidateFiles for the position->file mapping and its
     * witnessempty fallback; background/<name>.png with no position
     * subfolder does not exist on a real AO base).
     *
     * Case sensitivity (see the doc at the top of this file): the
     * lowercased `name` is the canonical/primary candidate set; the
     * original casing is appended as a last-resort extra candidate only
     * when it actually differs, so it's only ever tried after every
     * lowercase candidate (all position files, for backgrounds) has
     * already failed.
     */
    _buildUrlCandidates(base, kind, name, position) {
        if (!base) return [];
        const lower = String(name).toLowerCase();
        const variants = lower === name ? [lower] : [lower, name];
        const out = [];
        variants.forEach((n) => {
            if (kind === 'background') {
                gmLcBackgroundCandidateFiles(position).forEach((file) => {
                    out.push(`${base}/background/${encodeURIComponent(n)}/${file}.png`);
                });
            } else if (kind === 'char_icon') {
                out.push(`${base}/characters/${encodeURIComponent(n)}/char_icon.png`);
            } else if (kind === 'evidence') {
                const hasExt = /\.[a-z0-9]{2,5}$/i.test(n);
                out.push(`${base}/evidence/${encodeURIComponent(n)}${hasExt ? '' : '.png'}`);
            }
        });
        return out;
    }

    /** URL-sourced candidates (a base URL, or the server's asset_url) are
     * only usable once confirmed reachable -- otherwise the graph/roster
     * just shows a broken image. Verified via an Image() load; both
     * successes and failures are cached in-memory for the session so we
     * never re-probe the same URL. */
    _verifyImageUrl(url) {
        if (this._urlCheckCache.has(url)) return this._urlCheckCache.get(url);
        const promise = new Promise((resolve) => {
            const img = new Image();
            img.onload = () => resolve(true);
            img.onerror = () => resolve(false);
            img.src = url;
        });
        this._urlCheckCache.set(url, promise);
        return promise;
    }

    async _resolveFromUrl(base, kind, name, position) {
        for (const url of this._buildUrlCandidates(base, kind, name, position)) {
            const reachable = await this._verifyImageUrl(url);
            if (reachable) return url;
        }
        return null;
    }

    /** Memoizes a SUCCESSFUL /api/gm/assets/config fetch for the rest of
     * the session (it's effectively static config, and this is the
     * fallback every background/char_icon/evidence resolution funnels
     * through -- see _resolveFromServer -- so it would otherwise be
     * refetched constantly). A failed fetch (one transient network
     * hiccup, a momentary 5xx) must NOT be memoized the same way: doing so
     * would permanently poison every asset resolution for the rest of the
     * session with no way to recover short of a full page reload, which is
     * exactly the kind of one-failure-poisons-everything caching this class
     * must avoid (a session-scoped negative cache on an individual
     * resolved name is fine -- see `_resolveCache` -- but this is the
     * single shared gate every one of those goes through, so caching ITS
     * failure is a different, much bigger blast radius). So on failure the
     * memoized promise is cleared, letting the next resolve() call retry
     * the fetch instead of forever answering "no server asset url" here. */
    async _loadServerAssetUrl() {
        if (this._serverConfigPromise) return this._serverConfigPromise;
        this._serverConfigPromise = (async () => {
            try {
                const data = await this.api.getAssetsConfig();
                this._serverAssetUrl = (data && data.asset_url) || '';
                return this._serverAssetUrl;
            } catch (e) {
                this._serverConfigPromise = null;
                this._serverAssetUrl = '';
                return '';
            }
        })();
        return this._serverConfigPromise;
    }

    async _resolveFromServer(kind, name, position) {
        const base = await this._loadServerAssetUrl();
        if (!base) return null;
        return this._resolveFromUrl(base, kind, name, position);
    }

    // --- per-item overrides -------------------------------------------------

    /** @param {File} file */
    async setOverride(kind, name, file) {
        const dataUrl = await this._readFileAsDataUrl(file);
        await this._store.set(GM_LC_OVERRIDE_STORE, `${kind}:${name}`, {
            dataUrl, name: file.name || '', storedAt: Date.now(),
        });
        // Background resolve-cache keys carry a per-position suffix (see
        // _cacheKey) that this call site has no way to know in advance --
        // _invalidateResolveCache clears every entry for this kind+name
        // regardless of that suffix, not just the no-position one.
        this._invalidateResolveCache(kind, name);
        this._notifyChange(kind, name);
        return dataUrl;
    }

    async clearOverride(kind, name) {
        await this._store.delete(GM_LC_OVERRIDE_STORE, `${kind}:${name}`);
        this._invalidateResolveCache(kind, name);
        this._notifyChange(kind, name);
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

    /**
     * @returns {?string} a CSS hex color, or null only when `key` itself is
     *   falsy (nothing to key a color on). Once a key has any color -- user
     *   set or derived -- this always returns the same value: a stable
     *   pseudo-random color is derived from the key on first lookup and
     *   persisted immediately, so every character has a color and it
     *   survives reloads. A user-set color always wins over the derived one.
     */
    getClientColor(key) {
        if (!key) return null;
        if (this._colors[key]) return this._colors[key];
        const derived = this._deriveColor(key);
        this._colors[key] = derived;
        this._saveColors();
        return derived;
    }

    setClientColor(key, cssColor) {
        if (!key) return;
        if (!cssColor) delete this._colors[key];
        else this._colors[key] = cssColor;
        this._saveColors();
    }

    /** Stable hash of `key` -> a pleasant hex color (fixed saturation/
     * lightness, hue spread across the full wheel by the hash). Same key
     * always derives the same color, independent of storage order. */
    _deriveColor(key) {
        let hash = 0;
        for (let i = 0; i < key.length; i++) {
            hash = (hash * 31 + key.charCodeAt(i)) >>> 0;
        }
        const hue = hash % 360;
        return this._hslToHex(hue, 65, 55);
    }

    _hslToHex(h, s, l) {
        s /= 100; l /= 100;
        const k = (n) => (n + h / 30) % 12;
        const a = s * Math.min(l, 1 - l);
        const f = (n) => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
        const toHex = (n) => Math.round(f(n) * 255).toString(16).padStart(2, '0');
        return `#${toHex(0)}${toHex(8)}${toHex(4)}`;
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
