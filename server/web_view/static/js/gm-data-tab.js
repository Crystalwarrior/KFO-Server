/**
 * gm-data-tab.js
 * GMDataTab ("Hub Data" in the nav): import/export for every GM-facing
 * yaml file the panel touches -- hub layouts (save_hub/load_hub), evidence
 * packs, character data, music lists and character lists -- plus two
 * "live" editors that push straight into the running hub: the current
 * music list and the current character list.
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

        // --- Music list editor (live hub musiclist) ---
        this._musicRefLabel = root.querySelector('#musicRefLabel');
        this._musicEditor = root.querySelector('#musicEditorTextarea');
        this._musicNameInput = root.querySelector('#musicNameInput');
        this._musicSaveAsBtn = root.querySelector('#musicSaveAsBtn');
        this._musicApplyBtn = root.querySelector('#musicApplyBtn');

        // --- Character list editor (live hub roster) ---
        this._charlistEditor = root.querySelector('#charlistEditorTextarea');
        this._charlistSaveAsInput = root.querySelector('#charlistSaveAsInput');
        this._charlistSubmitBtn = root.querySelector('#charlistSubmitBtn');
        this._charlistRevertBtn = root.querySelector('#charlistRevertBtn');
        this._charlistOriginal = [];

        root.querySelector('#dataRefreshBtn').addEventListener('click', () => this.reloadAll());
        this._hubSaveBtn.addEventListener('click', () => this._hubSave());
        this._hubSaveDownloadBtn.addEventListener('click', () => this._hubSaveAndDownload());
        this._hubImportBtn.addEventListener('click', () => this._hubImport());
        this._hubSavesTbody.addEventListener('click', (e) => this._onHubTableClick(e));
        this._musicSaveAsBtn.addEventListener('click', () => this._musicSaveAs());
        this._musicApplyBtn.addEventListener('click', () => this._musicApply());
        this._charlistSubmitBtn.addEventListener('click', () => this._charlistSubmit());
        this._charlistRevertBtn.addEventListener('click', () => this._charlistRevert());
    }

    async activate() {
        super.activate();
        this._renderHubHeading();
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

    async reloadAll() {
        await Promise.all([
            this._loadHubSaves(),
            this._loadDataFiles('evidence'),
            this._loadDataFiles('character_data'),
            this._loadDataFiles('charlists'),
            this._loadDataFiles('musiclists'),
            this._loadMusicEditor(),
            this._loadCharlistEditor(),
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

    async _loadHubSaves() {
        try {
            const data = await this.api.getHubSaves();
            this._hubSaves = data.files || [];
            this._renderHubSaves();
        } catch (e) {
            this._hubSavesTbody.innerHTML = `<tr><td colspan="3" class="gm-empty">Failed to load: ${esc(e.message)}</td></tr>`;
        }
    }

    _renderHubSaves() {
        if (!this._hubSaves.length) {
            this._hubSavesTbody.innerHTML = '<tr><td colspan="3" class="gm-empty">No saved hubs yet.</td></tr>';
            return;
        }
        this._hubSavesTbody.innerHTML = this._hubSaves.map((f) => `
            <tr>
                <td>${esc(f.name)}${f.read_only ? ' <span class="badge readonly">read-only</span>' : ''}</td>
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
        const name = this._hubSaveNameInput.value.trim();
        if (!name) { this.shell.toast('Enter a name to save the hub as.', 'error'); return; }
        try {
            const result = await this.api.saveHub(name);
            this._printOutput(result.output, result.ok);
            this.shell.toast(`Hub saved as "${name}".`, result.ok === false ? 'error' : 'success');
            this._hubSaveNameInput.value = '';
            await this._loadHubSaves();
        } catch (e) {
            this.shell.toast('Failed to save hub: ' + e.message, 'error');
        }
    }

    async _hubSaveAndDownload() {
        const name = this._hubSaveNameInput.value.trim();
        if (!name) { this.shell.toast('Enter a name to save the hub as.', 'error'); return; }
        try {
            const result = await this.api.saveHub(name);
            this._printOutput(result.output, result.ok);
            const file = await this.api.getDataFile('hubs', name);
            this.api.downloadText(`${name}.yaml`, file.content || '');
            this.shell.toast(`Hub saved as "${name}" and downloaded.`, 'success');
            this._hubSaveNameInput.value = '';
            await this._loadHubSaves();
        } catch (e) {
            this.shell.toast('Failed to save & download hub: ' + e.message, 'error');
        }
    }

    async _hubExport(name) {
        try {
            const file = await this.api.getDataFile('hubs', name);
            this.api.downloadText(`${name}.yaml`, file.content || '');
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
        const name = file.name.replace(/\.ya?ml$/i, '');
        const exists = this._hubSaves.some((f) => f.name === name);
        if (exists && !confirm(`Overwrite existing hub save "${name}"?`)) return;
        try {
            const content = await file.text();
            await this.api.putDataFile('hubs', name, content);
            this.shell.toast(`Hub file imported as "${name}".`, 'success');
            this._hubImportFile.value = '';
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
        if (!box.files.length) {
            box.tbody.innerHTML = '<tr><td colspan="2" class="gm-empty">No files.</td></tr>';
            return;
        }
        box.tbody.innerHTML = box.files.map((f) => `
            <tr>
                <td>${esc(f.name)}${f.read_only ? ' <span class="badge readonly">read-only</span>' : ''}</td>
                <td><button class="btn-sm" data-action="download" data-name="${esc(f.name)}">Download</button></td>
            </tr>`).join('');
    }

    _onFileTableClick(e, kind) {
        const btn = e.target.closest('button[data-action="download"]');
        if (!btn) return;
        this._downloadDataFile(kind, btn.dataset.name);
    }

    async _downloadDataFile(kind, name) {
        try {
            const file = await this.api.getDataFile(kind, name);
            this.api.downloadText(`${name}.yaml`, file.content || '');
        } catch (e) {
            this.shell.toast('Failed to download: ' + e.message, 'error');
        }
    }

    async _uploadDataFile(kind) {
        const box = this._kindBoxes[kind];
        const file = box.fileInput.files && box.fileInput.files[0];
        if (!file) { this.shell.toast('Choose a .yaml file first.', 'error'); return; }
        const name = file.name.replace(/\.ya?ml$/i, '');
        const exists = box.files.some((f) => f.name === name);
        if (exists && !confirm(`Overwrite existing file "${name}"?`)) return;
        const label = GM_DATA_KIND_LABELS[kind] || 'File';
        try {
            const content = await file.text();
            await this.api.putDataFile(kind, name, content);
            this.shell.toast(`${label} "${name}" saved.`, 'success');
            box.fileInput.value = '';
            await this._loadDataFiles(kind);
        } catch (e) {
            this.shell.toast(`Failed to upload ${label.toLowerCase()}: ` + e.message, 'error');
        }
    }

    // --- Music list editor (live hub musiclist) -------------------------

    async _loadMusicEditor() {
        try {
            const data = await this.api.getMusic();
            this._musicRefLabel.textContent = data.music_ref
                ? `Current hub musiclist file: ${data.music_ref}`
                : 'Current hub musiclist: (unsaved / live list)';
            this._musicEditor.value = data.content || '';
        } catch (e) {
            this._musicRefLabel.textContent = 'Failed to load current musiclist: ' + e.message;
        }
    }

    async _musicSaveAs() {
        const name = this._musicNameInput.value.trim();
        if (!name) { this.shell.toast('Enter a name to save the music list as.', 'error'); return; }
        const box = this._kindBoxes.musiclists;
        const exists = box && box.files.some((f) => f.name === name);
        if (exists && !confirm(`Overwrite existing music list "${name}"?`)) return;
        try {
            await this.api.putDataFile('musiclists', name, this._musicEditor.value);
            this.shell.toast(`Music list saved as "${name}".`, 'success');
            await this._loadDataFiles('musiclists');
        } catch (e) {
            this.shell.toast('Failed to save music list: ' + e.message, 'error');
        }
    }

    async _musicApply() {
        const name = this._musicNameInput.value.trim();
        if (!name) { this.shell.toast('Enter the saved music list name to apply.', 'error'); return; }
        if (!confirm(`Apply music list "${name}" to the current hub now?`)) return;
        try {
            const result = await this.api.applyMusic(name);
            this._printOutput(result.output, result.ok);
            this.shell.toast(`Music list "${name}" applied.`, result.ok === false ? 'error' : 'success');
            await this._loadMusicEditor();
        } catch (e) {
            this.shell.toast('Failed to apply music list: ' + e.message, 'error');
        }
    }

    // --- Character list editor (live hub roster) -------------------------

    async _loadCharlistEditor() {
        try {
            const data = await this.api.getCharlist();
            this._charlistOriginal = data.characters || [];
            this._charlistEditor.value = this._charlistOriginal.join('\n');
        } catch (e) {
            this.shell.toast('Failed to load character list: ' + e.message, 'error');
        }
    }

    _charlistRevert() {
        this._charlistEditor.value = this._charlistOriginal.join('\n');
        this._charlistSaveAsInput.value = '';
        this.shell.toast('Character list edits reverted.', 'info');
    }

    async _charlistSubmit() {
        const characters = this._charlistEditor.value
            .split('\n')
            .map((s) => s.trim())
            .filter((s) => s.length > 0);
        if (!characters.length) { this.shell.toast('Character list cannot be empty.', 'error'); return; }
        if (!confirm('Apply this character list to the hub now? This changes what everyone can select as a character.')) return;
        const saveAs = this._charlistSaveAsInput.value.trim();
        try {
            const result = await this.api.submitCharlist(characters, saveAs || undefined);
            this._printOutput(result.output, result.ok);
            this.shell.toast('Character list applied to the hub.', result.ok === false ? 'error' : 'success');
            this._charlistSaveAsInput.value = '';
            await this._loadCharlistEditor();
            if (saveAs) await this._loadDataFiles('charlists');
        } catch (e) {
            this.shell.toast('Failed to submit character list: ' + e.message, 'error');
        }
    }
}
