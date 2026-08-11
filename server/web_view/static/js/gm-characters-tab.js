/**
 * gm-characters-tab.js
 * CharactersTab: browse/apply the hub's character list, and a visual
 * interface for the persistent Character Data system
 * (/save_character_data, /load_character_data, /get_char_data,
 * /set_char_data) -- browse stored data per character, edit keys, and
 * save/load named snapshots.
 */

class CharactersTab extends TabBase {
    constructor(shell, api, root) {
        super(shell, api, root);

        this._characterData = {};
        this._folders = [];
        this._selectedFolder = null;

        this._charListRefEl = root.querySelector('#charListRef');
        this._charlistSelect = root.querySelector('#charlistSelect');
        this._slotsTbody = root.querySelector('#charSlotsTbody');
        this._folderSelect = root.querySelector('#charDataFolderSelect');
        this._dataTbody = root.querySelector('#charDataTbody');
        this._snapshotSelect = root.querySelector('#snapshotSelect');
        this._output = root.querySelector('#charactersOutput');

        root.querySelector('#charlistApplyBtn').addEventListener('click', () => this._applyCharlist());
        root.querySelector('#charDataRefreshBtn').addEventListener('click', () => this._loadCharacterData());
        this._folderSelect.addEventListener('change', () => this._onFolderChange());
        root.querySelector('#charDataSetBtn').addEventListener('click', () => this._setKeyFromForm());
        root.querySelector('#snapshotLoadBtn').addEventListener('click', () => this._loadSnapshot());
        root.querySelector('#snapshotSaveBtn').addEventListener('click', () => this._saveSnapshot());
        this._dataTbody.addEventListener('click', (e) => this._onDataTableClick(e));
    }

    async activate() {
        super.activate();
        await Promise.all([
            this._loadSlots(),
            this._loadCharlists(),
            this._loadCharacterData(),
            this._loadSnapshots(),
        ]);
    }

    async _loadSlots() {
        try {
            const data = await this.api.getCharacters();
            this._charListRefEl.textContent = `Hub ${data.hub_id} — list: ${data.char_list_ref || '(server default)'}`;
            const slots = data.slots || [];
            this._slotsTbody.innerHTML = slots.length
                ? slots.map((s) => `
                    <tr>
                        <td class="mono">${s.char_id}</td>
                        <td>${esc(s.folder)}</td>
                        <td>${s.taken ? `#${s.occupied_by_client_id}` : '<span class="dim">free</span>'}</td>
                    </tr>`).join('')
                : '<tr><td colspan="3" class="gm-empty">No characters.</td></tr>';
        } catch (e) {
            this.shell.toast('Failed to load character slots: ' + e.message, 'error');
        }
    }

    async _loadCharlists() {
        try {
            const data = await this.api.getCharlists();
            const lists = data.charlists || [];
            this._charlistSelect.innerHTML = '<option value="">(server default)</option>' +
                lists.map((n) => `<option value="${esc(n)}">${esc(n)}</option>`).join('');
        } catch (e) {
            // non-fatal: charlist picker just stays empty
        }
    }

    async _applyCharlist() {
        const name = this._charlistSelect.value;
        try {
            const result = await this.api.applyCharlist(name);
            this._log(result);
            await this._loadSlots();
        } catch (e) {
            this.shell.toast('Failed to apply character list: ' + e.message, 'error');
        }
    }

    async _loadCharacterData() {
        try {
            const data = await this.api.getCharacterData();
            this._characterData = data.character_data || {};
            this._folders = Object.keys(this._characterData);
            const prevSelected = this._selectedFolder;
            this._folderSelect.innerHTML = this._folders.map((f) => `<option value="${esc(f)}">${esc(f)}</option>`).join('');

            if (this._folders.length) {
                this._selectedFolder = this._folders.includes(prevSelected) ? prevSelected : this._folders[0];
                this._folderSelect.value = this._selectedFolder;
                this._renderFolderData();
            } else {
                this._selectedFolder = null;
                this._dataTbody.innerHTML = '<tr><td colspan="3" class="gm-empty">No character data stored yet.</td></tr>';
            }
        } catch (e) {
            this.shell.toast('Failed to load character data: ' + e.message, 'error');
        }
    }

    _onFolderChange() {
        this._selectedFolder = this._folderSelect.value;
        this._renderFolderData();
    }

    _renderFolderData() {
        const data = (this._characterData && this._characterData[this._selectedFolder]) || {};
        const keys = Object.keys(data);
        if (!keys.length) {
            this._dataTbody.innerHTML = '<tr><td colspan="3" class="gm-empty">No keys for this character.</td></tr>';
            return;
        }
        this._dataTbody.innerHTML = keys.map((k) => `
            <tr>
                <td class="mono">${esc(k)}</td>
                <td>${esc(fmtValue(data[k]))}</td>
                <td><button class="btn-sm danger" data-action="delete" data-key="${esc(k)}">Delete</button></td>
            </tr>`).join('');
    }

    _onDataTableClick(e) {
        const btn = e.target.closest('button[data-action="delete"]');
        if (!btn || !this._selectedFolder) return;
        if (!confirm(`Delete key "${btn.dataset.key}" from ${this._selectedFolder}'s data?`)) return;
        this._setKeyValue(this._selectedFolder, btn.dataset.key, '');
    }

    async _setKeyFromForm() {
        if (!this._selectedFolder) { this.shell.toast('Select a character first.', 'error'); return; }
        const keyInput = this.root.querySelector('#charDataKeyInput');
        const valueInput = this.root.querySelector('#charDataValueInput');
        const key = keyInput.value.trim();
        if (!key) { this.shell.toast('Key is required.', 'error'); return; }
        await this._setKeyValue(this._selectedFolder, key, valueInput.value);
        keyInput.value = '';
        valueInput.value = '';
    }

    async _setKeyValue(folder, key, value) {
        try {
            const result = await this.api.setCharacterData(folder, key, value);
            this._log(result);
            await this._loadCharacterData();
        } catch (e) {
            this.shell.toast('Failed to set character data: ' + e.message, 'error');
        }
    }

    async _loadSnapshots() {
        try {
            const data = await this.api.getCharacterDataSnapshots();
            const snaps = data.snapshots || [];
            this._snapshotSelect.innerHTML = snaps.length
                ? snaps.map((s) => `<option value="${esc(s)}">${esc(s)}</option>`).join('')
                : '<option value="">(none saved)</option>';
        } catch (e) {
            // non-fatal: snapshot picker just stays empty
        }
    }

    async _loadSnapshot() {
        const name = this._snapshotSelect.value;
        if (!name) return;
        if (!confirm(`Load snapshot "${name}"? This overwrites the hub's current character data with the snapshot's contents.`)) return;
        try {
            const result = await this.api.loadCharacterDataSnapshot(name);
            this._log(result);
            await this._loadCharacterData();
        } catch (e) {
            this.shell.toast('Failed to load snapshot: ' + e.message, 'error');
        }
    }

    async _saveSnapshot() {
        const input = this.root.querySelector('#snapshotNameInput');
        const name = input.value.trim();
        if (!name) { this.shell.toast('Snapshot name is required.', 'error'); return; }
        try {
            const result = await this.api.saveCharacterDataSnapshot(name);
            this._log(result);
            input.value = '';
            await this._loadSnapshots();
        } catch (e) {
            this.shell.toast('Failed to save snapshot: ' + e.message, 'error');
        }
    }

    _log(result) {
        const line = document.createElement('div');
        const isError = result && result.ok === false;
        line.className = 'gm-output-line' + (isError ? ' error' : '');
        line.textContent = (result && result.output && result.output.length)
            ? result.output.join('\n')
            : (result && result.ok ? 'Done.' : 'No output.');
        this._output.appendChild(line);
        this._output.scrollTop = this._output.scrollHeight;
    }
}
