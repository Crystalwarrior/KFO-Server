/**
 * gm-data-tab.js
 * GMDataTab ("Hub Data" in the nav): import/export for every GM-facing
 * yaml file the panel touches -- hub layouts (save_hub/load_hub), evidence
 * packs, character data, music lists and character lists.
 *
 * Talks only to the typed ApiClient methods added for this tab (§D2);
 * every dynamic string goes through esc() before landing in innerHTML.
 */

/** kind -> user-facing label, used only for toast/error copy. */
const GM_DATA_KIND_LABELS = {
    evidence: 'Evidence pack',
    character_data: 'Character data file',
    charlists: 'Character list file',
    musiclists: 'Music list',
};

/** kind -> tooltip for the row "Load" button (see GMDataTab._loadDataFile
 * for the per-kind command each one dispatches). */
const GM_DATA_KIND_LOAD_HINTS = {
    evidence: 'Load this evidence pack into your current area',
    character_data: 'Load this character data into the hub',
    charlists: 'Apply this character list to the hub',
    musiclists: 'Apply this music list to the hub',
};

/** localStorage key remembering the hub names this browser's GM has saved
 * or imported before. The server now lists ONLY the public read-only hubs
 * (see gm_panel.py's DATA_KIND_LIST_PUBLIC_ONLY -- editable hub names must
 * not leak to every GM with a session), so the Hub Saves list re-adds
 * these known names client-side: they are the one set of editable hubs a
 * GM can verifiably claim to know about (they typed/saved them here). */
const GM_DATA_KNOWN_HUBS_KEY = 'gmDataTab.knownHubs';

/** Matches the backend's single-segment name regex exactly (gm_panel.py's
 * HubDataRoutes) -- 1-64 letters/digits/spaces/underscore/hyphen. */
const GM_DATA_SEGMENT_RE = /^[A-Za-z0-9 _-]{1,64}$/;

/** Client-side mirror of the backend's multi-segment path validation: 1-4
 * "/"-separated segments, each matching GM_DATA_SEGMENT_RE, none of them
 * "read_only" (that name is reserved for the server's own top-level,
 * excluded-from-recursion convention -- see gm_panel.py's HubDataRoutes).
 * Never a substitute for the server's own check -- purely so a GM sees a
 * clear message instead of a raw 400. Returns { ok: true, name } or
 * { ok: false, error }. */
function validateDataName(raw) {
    const name = String(raw || '').trim();
    if (!name) return { ok: false, error: 'A name is required.' };
    const segments = name.split('/');
    if (segments.length > 4) {
        return { ok: false, error: 'Path may have at most 4 folder segments.' };
    }
    for (const seg of segments) {
        if (!GM_DATA_SEGMENT_RE.test(seg)) {
            return {
                ok: false,
                error: `Invalid path segment "${seg}": use 1-64 letters, numbers, spaces, "_" or "-", with no empty segments.`,
            };
        }
        if (seg === 'read_only') {
            // Case-sensitive, matching the backend's own check (and the
            // on-disk directory name it guards) exactly -- see
            // gm_panel.py's _split_data_name.
            return { ok: false, error: '"read_only" is a reserved folder name and cannot be used here.' };
        }
    }
    return { ok: true, name };
}

/** Join an optional folder-prefix field with a file's derived basename into
 * one candidate path name (folder prefix may itself be blank, or already
 * contain multiple "/"-separated segments). */
function joinDataFolderPrefix(prefix, basename) {
    const trimmedPrefix = String(prefix || '').trim().replace(/\/+$/, '');
    return trimmedPrefix ? `${trimmedPrefix}/${basename}` : basename;
}

class GMDataTab extends TabBase {
    /**
     * @param {GMPanelShell} shell
     * @param {ApiClient} api
     * @param {HTMLElement} root
     */
    constructor(shell, api, root) {
        super(shell, api, root);

        this._hubLabel = root.querySelector('#dataHubLabel');
        this._outputEl = root.querySelector('#dataOutput');

        // --- Subtab navigation (Hub Saves / Files) ---
        this._subtabButtons = Array.from(root.querySelectorAll('.gm-subtab[data-subtab]'));
        this._subtabBodies = Array.from(root.querySelectorAll('.gm-data-subtab[data-subtab]'));
        this._subtabButtons.forEach((btn) => {
            btn.addEventListener('click', () => this._setSubtab(btn.dataset.subtab));
        });

        // --- Hub layout (save_hub / load_hub) ---
        this._hubSaveNameInput = root.querySelector('#hubSaveNameInput');
        this._hubSaveBtn = root.querySelector('#hubSaveBtn');
        this._hubSaveDownloadBtn = root.querySelector('#hubSaveDownloadBtn');
        this._hubSavesTbody = root.querySelector('#hubSavesTbody');
        this._hubImportFile = root.querySelector('#hubImportFile');
        this._hubImportLoadCheck = root.querySelector('#hubImportLoadCheck');
        this._hubImportBtn = root.querySelector('#hubImportBtn');
        this._hubSaves = [];

        // --- Generic yaml-file kinds: evidence / character_data / charlists / musiclists ---
        this._kindBoxes = {};
        root.querySelectorAll('[data-kind]').forEach((box) => {
            const kind = box.dataset.kind;
            const entry = {
                el: box,
                tbody: box.querySelector('.gm-data-files-tbody'),
                fileInput: box.querySelector('.gm-data-upload-file'),
                uploadBtn: box.querySelector('.gm-data-upload-btn'),
                files: [],
            };
            entry.uploadBtn.addEventListener('click', () => this._uploadDataFile(kind));
            entry.tbody.addEventListener('click', (e) => this._onFileTableClick(e, kind));
            this._kindBoxes[kind] = entry;
        });

        // --- Music / character list file kinds live with the generic
        // `[data-kind]` boxes above; there is no separate live-editor UI.

        root.querySelector('#dataRefreshBtn').addEventListener('click', () => this.reloadAll());
        this._hubSaveBtn.addEventListener('click', () => this._hubSave());
        this._hubSaveDownloadBtn.addEventListener('click', () => this._hubSaveAndDownload());
        this._hubImportBtn.addEventListener('click', () => this._hubImport());
        this._hubSavesTbody.addEventListener('click', (e) => this._onHubTableClick(e));

        // File lists can now contain subpath entries ("events/mystery");
        // uploads default their name from the picked file's basename at the
        // kind's top level, same as before, but a GM needs a way to target
        // a subfolder too -- inject a small optional "folder" field next to
        // every file input (hub import + each generic kind box) since
        // gm.html/gm.css are not this package's to edit.
        this._injectFolderPrefixFields();
        this._injectStyles();
        this._buildDataSearchBoxes();
    }

    /** One live search filter per data section (Hub Saves + each of the
     * Files kinds -- evidence / character_data / charlists / musiclists),
     * injected after each box's <h3>. Rerenders just that section's
     * already-loaded table, no network round-trip. */
    _buildDataSearchBoxes() {
        this._search = { hub: '', evidence: '', character_data: '', charlists: '', musiclists: '' };
        const attachAfterHeading = (boxEl, key, placeholder) => {
            const heading = boxEl.querySelector('h3');
            if (!heading) return;
            const input = createGmSearchBox(placeholder, (v) => {
                this._search[key] = v;
                this._renderDataFiles(key);
            });
            const wrap = document.createElement('div');
            wrap.className = 'gm-search-row';
            wrap.appendChild(input);
            heading.after(wrap);
        };

        // Hub Saves search (its own panel, re-rendered below).
        const hubBox = this.root.querySelector('.gm-data-hub-box');
        const hubHeading = hubBox && hubBox.querySelector('h3');
        if (hubHeading) {
            const input = createGmSearchBox('Filter hubs…', (v) => {
                this._search.hub = v;
                this._renderHubSaves();
            });
            const wrap = document.createElement('div');
            wrap.className = 'gm-search-row';
            wrap.appendChild(input);
            hubHeading.after(wrap);
        }

        Object.keys(this._kindBoxes).forEach((kind) => {
            attachAfterHeading(this._kindBoxes[kind].el, kind, `Filter ${kind.replace(/_/g, ' ')}…`);
        });
    }

    /** The injected folder-prefix fields (see _injectFolderPrefixFields)
     * are new markup this tab owns entirely; gm.html/gm.css are not this
     * package's to edit, so their styling is scoped here. Guarded by id so
     * re-construction never doubles the <style> tag up. */
    _injectStyles() {
        if (document.getElementById('gm-data-tab-styles')) return;
        const style = document.createElement('style');
        style.id = 'gm-data-tab-styles';
        style.textContent = `
            .gm-data-folder-prefix {
                width: 9rem; min-width: 6rem;
            }
            .badge.gm-data-known {
                background: rgba(79,209,197,0.12); color: var(--gm-accent2); border: 1px solid #2b5a52;
            }
        `;
        document.head.appendChild(style);
    }

    /** Optional folder-prefix text input, inserted right before each file
     * <input> in the DOM (hub import + every `[data-kind]` box's upload
     * row). Joined with the picked file's basename by _uploadDataFile()/
     * _hubImport() and validated the same way as every other typed name. */
    _injectFolderPrefixFields() {
        const attach = (fileInput) => {
            if (!fileInput || fileInput.dataset.gmFolderInjected) return null;
            const folderInput = document.createElement('input');
            folderInput.type = 'text';
            folderInput.className = 'gm-data-folder-prefix';
            folderInput.placeholder = 'folder (optional)';
            folderInput.title = 'Optional subfolder to save into, e.g. "events/mystery" -- 1-4 path segments, letters/numbers/spaces/_/- only.';
            fileInput.parentElement.insertBefore(folderInput, fileInput);
            fileInput.dataset.gmFolderInjected = '1';
            return folderInput;
        };

        this._hubImportFolderInput = attach(this._hubImportFile);
        Object.keys(this._kindBoxes).forEach((kind) => {
            const box = this._kindBoxes[kind];
            box.folderInput = attach(box.fileInput);
        });
    }

    async activate() {
        super.activate();
        this._renderHubHeading();
        // Restore the previously-active subtab (defaults to "hub"); the
        // per-subtab data is refreshed by reloadAll() right after, so skip
        // the extra reload here.
        this._setSubtab(this._storedSubtab(), { skipReload: true });
        await this.reloadAll();
    }

    deactivate() {
        super.deactivate();
    }

    onEvent(msg) {
        if (msg.type === 'hub_switched') {
            this._renderHubHeading();
        }
    }

    _renderHubHeading() {
        const gm = this.shell.gmIdentity;
        this._hubLabel.textContent = gm ? `Hub ${gm.hub_id}: ${gm.hub_name}` : 'Hub Data';
    }

    /** Last-selected subtab name, persisted so a GM's choice survives a
     * reload; anything unexpected falls back to the default "hub". */
    _storedSubtab() {
        try {
            return localStorage.getItem('gmDataTab.subtab') || 'hub';
        } catch (e) {
            return 'hub';
        }
    }

    /** Switches the active Hub Data subtab (see the nav bar in gm.html) and
     * refreshes just that subtab's data -- the Output console sits below
     * the subtab bodies and is shared across all of them. Each kind
     * (evidence / character_data / charlists / musiclists) has its own
     * subtab; "hub" covers the hub layout save/load panel. */
    _setSubtab(name, opts) {
        opts = opts || {};
        if (!this._subtabBodies.some((el) => el.dataset.subtab === name)) name = 'hub';
        this._subtabButtons.forEach((b) => b.classList.toggle('active', b.dataset.subtab === name));
        this._subtabBodies.forEach((el) => el.classList.toggle('hidden', el.dataset.subtab !== name));
        try { localStorage.setItem('gmDataTab.subtab', name); } catch (e) { /* best effort */ }
        if (opts.skipReload) return;
        if (name === 'hub') {
            this._loadHubSaves();
        } else {
            this._loadDataFiles(name);
        }
    }

    async reloadAll() {
        await Promise.all([
            this._loadHubSaves(),
            this._loadDataFiles('evidence'),
            this._loadDataFiles('character_data'),
            this._loadDataFiles('charlists'),
            this._loadDataFiles('musiclists'),
        ]);
    }

    // --- output console -------------------------------------------------

    _printOutput(output, ok) {
        if (!this._outputEl) return;
        const text = Array.isArray(output) ? output.join('\n') : (output || '');
        if (!text) return;
        const div = document.createElement('div');
        div.className = 'gm-output-line' + (ok === false ? ' error' : '');
        div.textContent = text;
        this._outputEl.appendChild(div);
        this._outputEl.scrollTop = this._outputEl.scrollHeight;
    }

    // --- Hub layout: save_hub / load_hub --------------------------------

    /** Hub names this browser's GM has saved/imported before (see
     * GM_DATA_KNOWN_HUBS_KEY). Untrusted, possibly-corrupt storage is
     * tolerated defensively -- a bad payload just yields no known hubs. */
    _knownHubNames() {
        try {
            const raw = JSON.parse(localStorage.getItem(GM_DATA_KNOWN_HUBS_KEY) || '[]');
            if (!Array.isArray(raw)) return [];
            return raw.filter((n) => typeof n === 'string' && n.length > 0);
        } catch (e) {
            return [];
        }
    }

    /** Records `name` so the Hub Saves list keeps showing this editable hub
     * even though the server only lists read-only hubs (see
     * GM_DATA_KNOWN_HUBS_KEY). Call sites remember ONLY on success -- a
     * failed save/import proves nothing about who owns that name. */
    _rememberHub(name) {
        try {
            const known = new Set(this._knownHubNames());
            known.add(name);
            localStorage.setItem(GM_DATA_KNOWN_HUBS_KEY, JSON.stringify([...known]));
        } catch (e) { /* storage full/unavailable: known-hubs list stays in-memory only */ }
    }

    async _loadHubSaves() {
        try {
            const data = await this.api.getHubSaves();
            // Non-mod hub GMs get only the public read_only hubs; mods get
            // every hub on the server. Merge in this GM's own editable saves
            // (localStorage known-hubs) so its layouts still appear even when
            // the server only listed read_only ones -- and use that same known
            // set to tell "yours" apart from editable hubs other GMs saved.
            const knownNames = new Set(this._knownHubNames());
            const byName = new Map();
            (data.files || []).forEach((f) => {
                const readOnly = !!f.read_only;
                byName.set(f.name, { name: f.name, read_only: readOnly, known: !readOnly && knownNames.has(f.name) });
            });
            knownNames.forEach((name) => {
                if (!byName.has(name)) byName.set(name, { name, read_only: false, known: true });
            });
            const sortByName = (a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase());
            this._hubSaves = [
                ...[...byName.values()].filter((f) => f.read_only).sort(sortByName),
                ...[...byName.values()].filter((f) => !f.read_only).sort(sortByName),
            ];
            this._renderHubSaves();
        } catch (e) {
            this._hubSavesTbody.innerHTML = `<tr><td colspan="3" class="gm-empty">Failed to load: ${esc(e.message)}</td></tr>`;
        }
    }

    _renderHubSaves() {
        const q = (this._search && this._search.hub || '').trim().toLowerCase();
        const list = q ? this._hubSaves.filter((f) => f.name.toLowerCase().includes(q)) : this._hubSaves;
        if (!list.length) {
            this._hubSavesTbody.innerHTML = `<tr><td colspan="3" class="gm-empty">${
                q ? 'No saved hubs match.' : 'No hubs to show. Shared read-only hubs and hubs you\'ve saved before appear here.'}</td></tr>`;
            return;
        }
        this._hubSavesTbody.innerHTML = list.map((f) => `
            <tr>
                <td>${esc(f.name)}${f.read_only ? ' <span class="badge readonly">read-only</span>' : (f.known ? ' <span class="badge gm-data-known">yours</span>' : ' <span class="badge">editable</span>')}</td>
                <td><button class="btn-sm" data-action="load" data-name="${esc(f.name)}">Load</button></td>
                <td><button class="btn-sm" data-action="export" data-name="${esc(f.name)}">Export</button></td>
            </tr>`).join('');
    }

    _onHubTableClick(e) {
        const btn = e.target.closest('button[data-action]');
        if (!btn) return;
        const name = btn.dataset.name;
        if (btn.dataset.action === 'load') this._hubLoad(name);
        else if (btn.dataset.action === 'export') this._hubExport(name);
    }

    async _hubSave() {
        const check = validateDataName(this._hubSaveNameInput.value);
        if (!check.ok) { this.shell.toast(check.error, 'error'); return; }
        const name = check.name;
        try {
            const result = await this.api.saveHub(name);
            this._printOutput(result.output, result.ok);
            this.shell.toast(`Hub saved as "${name}".`, result.ok === false ? 'error' : 'success');
            if (result.ok !== false) this._rememberHub(name);
            this._hubSaveNameInput.value = '';
            await this._loadHubSaves();
        } catch (e) {
            this.shell.toast('Failed to save hub: ' + e.message, 'error');
        }
    }

    async _hubSaveAndDownload() {
        const check = validateDataName(this._hubSaveNameInput.value);
        if (!check.ok) { this.shell.toast(check.error, 'error'); return; }
        const name = check.name;
        try {
            const result = await this.api.saveHub(name);
            this._printOutput(result.output, result.ok);
            const file = await this.api.getDataFile('hubs', name);
            this.api.downloadText(`${name.replace(/\//g, '_')}.yaml`, file.content || '');
            this.shell.toast(`Hub saved as "${name}" and downloaded.`, 'success');
            if (result.ok !== false) this._rememberHub(name);
            this._hubSaveNameInput.value = '';
            await this._loadHubSaves();
        } catch (e) {
            this.shell.toast('Failed to save & download hub: ' + e.message, 'error');
        }
    }

    async _hubExport(name) {
        try {
            const file = await this.api.getDataFile('hubs', name);
            // A subpath name ("events/mystery") isn't a valid single
            // filename for a browser download -- flatten it to "_" so the
            // save-as dialog gets one sane file, not a path.
            this.api.downloadText(`${name.replace(/\//g, '_')}.yaml`, file.content || '');
        } catch (e) {
            this.shell.toast('Failed to export hub: ' + e.message, 'error');
        }
    }

    async _hubLoad(name, opts) {
        const skipConfirm = !!(opts && opts.skipConfirm);
        if (!skipConfirm && !confirm(`Load hub "${name}"? This replaces the current hub's areas and links.`)) return;
        try {
            const result = await this.api.loadHub(name);
            this._printOutput(result.output, result.ok);
            this.shell.toast(`Hub "${name}" loaded.`, result.ok === false ? 'error' : 'success');
        } catch (e) {
            this.shell.toast('Failed to load hub: ' + e.message, 'error');
        }
    }

    async _hubImport() {
        const file = this._hubImportFile.files && this._hubImportFile.files[0];
        if (!file) { this.shell.toast('Choose a .yaml file first.', 'error'); return; }
        const basename = file.name.replace(/\.ya?ml$/i, '');
        const folderPrefix = this._hubImportFolderInput ? this._hubImportFolderInput.value : '';
        const check = validateDataName(joinDataFolderPrefix(folderPrefix, basename));
        if (!check.ok) { this.shell.toast(check.error, 'error'); return; }
        const name = check.name;
        const exists = this._hubSaves.some((f) => f.name === name);
        if (exists && !confirm(`Overwrite existing hub save "${name}"?`)) return;
        try {
            const content = await file.text();
            await this.api.putDataFile('hubs', name, content);
            this._rememberHub(name);
            this.shell.toast(`Hub file imported as "${name}".`, 'success');
            this._hubImportFile.value = '';
            if (this._hubImportFolderInput) this._hubImportFolderInput.value = '';
            await this._loadHubSaves();
            if (this._hubImportLoadCheck.checked && confirm(`Load "${name}" into the current hub now?`)) {
                await this._hubLoad(name, { skipConfirm: true });
            }
        } catch (e) {
            this.shell.toast('Failed to import hub file: ' + e.message, 'error');
        }
    }

    // --- Generic yaml kinds: evidence / character_data / charlists / musiclists ---

    async _loadDataFiles(kind) {
        const box = this._kindBoxes[kind];
        if (!box) return;
        try {
            const data = await this.api.getDataFiles(kind);
            box.files = data.files || [];
            this._renderDataFiles(kind);
        } catch (e) {
            box.tbody.innerHTML = `<tr><td colspan="2" class="gm-empty">Failed to load: ${esc(e.message)}</td></tr>`;
        }
    }

    _renderDataFiles(kind) {
        const box = this._kindBoxes[kind];
        if (!box) return;
        const q = (this._search && this._search[kind] || '').trim().toLowerCase();
        const list = q ? box.files.filter((f) => f.name.toLowerCase().includes(q)) : box.files;
        if (!list.length) {
            box.tbody.innerHTML = `<tr><td colspan="2" class="gm-empty">${
                q ? 'No files match.' : 'No files.'}</td></tr>`;
            return;
        }
        box.tbody.innerHTML = list.map((f) => `
            <tr>
                <td>${esc(f.name)}${f.read_only ? ' <span class="badge readonly">read-only</span>' : ''}</td>
                <td class="gm-data-file-actions">
                    <button class="btn-sm" data-action="load" data-name="${esc(f.name)}" title="${esc(GM_DATA_KIND_LOAD_HINTS[kind] || 'Apply this file to the hub')}">Load</button>
                    <button class="btn-sm" data-action="download" data-name="${esc(f.name)}">Download</button>
                </td>
            </tr>`).join('');
    }

    _onFileTableClick(e, kind) {
        const btn = e.target.closest('button[data-action]');
        if (!btn) return;
        const name = btn.dataset.name;
        if (btn.dataset.action === 'load') this._loadDataFile(kind, name);
        else if (btn.dataset.action === 'download') this._downloadDataFile(kind, name);
    }

    async _downloadDataFile(kind, name) {
        try {
            const file = await this.api.getDataFile(kind, name);
            this.api.downloadText(`${name.replace(/\//g, '_')}.yaml`, file.content || '');
        } catch (e) {
            this.shell.toast('Failed to download: ' + e.message, 'error');
        }
    }

    /** "Load" in the Files subtab: apply a saved yaml file to the live hub.
     * Backed by POST /api/gm/data/{kind}/load, which routes through the
     * real command layer (`/charlist`, `/hub_musiclist`,
     * `/load_character_data`, `/evidence_load`) with its own gates -- see
     * the backend handler's docstring. Charlists are applied under their
     * lowercased name to match `load_characters`'s own case rule. */
    async _loadDataFile(kind, name) {
        const label = GM_DATA_KIND_LABELS[kind] || 'File';
        const hints = {
            evidence: 'into your current area',
            character_data: 'into the hub',
            charlists: 'to the hub',
            musiclists: 'to the hub',
        };
        const where = hints[kind] || '';
        if (!confirm(`Load ${label.toLowerCase()} "${name}" ${where} now?`)) return;
        try {
            const result = await this.api.loadDataFile(kind, name);
            this._printOutput(result.output, result.ok);
            this.shell.toast(result.ok === false ? 'Load failed.' : `"${name}" loaded.`, result.ok === false ? 'error' : 'success');
        } catch (e) {
            this.shell.toast(`Failed to load ${label.toLowerCase()}: ` + e.message, 'error');
        }
    }

    async _uploadDataFile(kind) {
        const box = this._kindBoxes[kind];
        const file = box.fileInput.files && box.fileInput.files[0];
        if (!file) { this.shell.toast('Choose a .yaml file first.', 'error'); return; }
        const basename = file.name.replace(/\.ya?ml$/i, '');
        const folderPrefix = box.folderInput ? box.folderInput.value : '';
        const check = validateDataName(joinDataFolderPrefix(folderPrefix, basename));
        if (!check.ok) { this.shell.toast(check.error, 'error'); return; }
        const name = check.name;
        const exists = box.files.some((f) => f.name === name);
        if (exists && !confirm(`Overwrite existing file "${name}"?`)) return;
        const label = GM_DATA_KIND_LABELS[kind] || 'File';
        try {
            const content = await file.text();
            await this.api.putDataFile(kind, name, content);
            this.shell.toast(`${label} "${name}" saved.`, 'success');
            box.fileInput.value = '';
            if (box.folderInput) box.folderInput.value = '';
            await this._loadDataFiles(kind);
        } catch (e) {
            this.shell.toast(`Failed to upload ${label.toLowerCase()}: ` + e.message, 'error');
        }
    }
}
