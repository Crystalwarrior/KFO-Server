/**
 * gm-characters-tab.js
 * CharactersTab: browse/apply the hub's character list, and a visual
 * interface for the persistent Character Data system
 * (/save_character_data, /load_character_data, /get_char_data,
 * /set_char_data) -- browse stored data per character, edit keys, and
 * save/load named snapshots.
 */

class CharactersTab extends TabBase {
    /**
     * @param {GMPanelShell} shell
     * @param {ApiClient} api
     * @param {HTMLElement} root
     * @param {?GMLocalContent} localContent - optional; resolves each
     *   character-list row's icon and backs the per-character color swatch,
     *   using the exact same resolution/keying convention as the Clients
     *   tab and the area graph (key = character FOLDER name). Safe to
     *   omit -- icons just stay on the text fallback.
     */
    constructor(shell, api, root, localContent) {
        super(shell, api, root);
        this._localContent = localContent || null;

        this._characterData = {};
        this._folders = [];
        this._selectedFolder = null;
        this._slots = [];

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
        this._slotsTbody.addEventListener('click', (e) => this._onSlotsTableClick(e));
        this._slotsTbody.addEventListener('change', (e) => this._onSlotsTableChange(e));

        this._ensureSlotsColumns();
    }

    /** Late-inject local content resolution (mirrors ClientsTab /
     * AreasGraphTab), so the shell can wire this up even if it's not
     * available yet at construction time. */
    setLocalContent(localContent) {
        this._localContent = localContent || null;
    }

    /** The character list table (gm.html) ships with 3 columns (#, Folder,
     * Occupied By). Icon and Color previously only appeared on the Clients
     * tab, even though this tab is the one keyed by character folder name
     * -- insert the two extra header cells here at runtime so both tabs
     * present icons/colors the same way, without touching the static
     * template. Idempotent so re-construction (shouldn't happen, but stay
     * defensive) never doubles the columns. */
    _ensureSlotsColumns() {
        const headRow = this.root.querySelector('#charSlotsTable thead tr');
        if (!headRow || headRow.dataset.gmExtended === '1') return;
        const folderTh = headRow.children[1];
        const occupiedTh = headRow.children[2];
        if (!folderTh || !occupiedTh) return;
        const iconTh = document.createElement('th');
        iconTh.textContent = 'Icon';
        headRow.insertBefore(iconTh, folderTh);
        const colorTh = document.createElement('th');
        colorTh.textContent = 'Color';
        headRow.insertBefore(colorTh, occupiedTh);
        headRow.dataset.gmExtended = '1';
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
            this._slots = data.slots || [];
            this._renderSlots();
        } catch (e) {
            this.shell.toast('Failed to load character slots: ' + e.message, 'error');
        }
    }

    _renderSlots() {
        const slots = this._slots;
        this._slotsTbody.innerHTML = slots.length
            ? slots.map((s) => this._slotRowHtml(s)).join('')
            : '<tr><td colspan="5" class="gm-empty">No characters.</td></tr>';
        if (slots.length) this._loadSlotIcons(slots);
    }

    _slotRowHtml(s) {
        const folder = s.folder || '';
        const color = this._localContent ? this._localContent.getClientColor(folder) : null;
        return `<tr>
            <td class="mono">${s.char_id}</td>
            <td>
                <span class="gm-icon-slot" data-role="icon"><span class="gm-icon-fallback">${esc((folder || '?').slice(0, 1).toUpperCase())}</span></span>
                <button class="btn-sm gm-icon-set-btn" data-action="set-icon" data-folder="${esc(folder)}" title="Set a local icon override for this character folder">Set icon</button>
            </td>
            <td>${esc(folder)}</td>
            <td><input type="color" class="gm-color-input" data-folder="${esc(folder)}" value="${esc(color || '#4a4f66')}" title="Marker color for ${esc(folder || 'this character')}"></td>
            <td>${s.taken ? `#${s.occupied_by_client_id}` : '<span class="dim">free</span>'}</td>
        </tr>`;
    }

    /** Resolves each visible row's icon by DOM position (rows render in the
     * same order as `slots`), the same lazy resolve('char_icon', folder)
     * convention the Clients tab and the area graph use. */
    _loadSlotIcons(slots) {
        if (!this._localContent) return;
        const rows = Array.from(this._slotsTbody.children);
        slots.forEach((s, i) => {
            const folder = s.folder;
            const row = rows[i];
            if (!folder || !row) return;
            this._localContent.resolve('char_icon', folder).then((url) => {
                if (!url) return;
                const slot = row.querySelector('.gm-icon-slot[data-role="icon"]');
                if (!slot) return;
                const img = document.createElement('img');
                img.className = 'gm-char-icon-img';
                img.alt = folder;
                img.src = url;
                img.addEventListener('error', () => { img.remove(); });
                slot.innerHTML = '';
                slot.appendChild(img);
            }).catch(() => { /* keep the text fallback */ });
        });
    }

    _onSlotsTableClick(e) {
        const btn = e.target.closest('button[data-action="set-icon"]');
        if (!btn) return;
        this._promptSlotIconOverride(btn.dataset.folder);
    }

    _promptSlotIconOverride(folder) {
        if (!this._localContent) return;
        if (!folder) { this.shell.toast('This slot has no character folder to override.', 'error'); return; }
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'image/*';
        input.addEventListener('change', async () => {
            const file = input.files && input.files[0];
            if (!file) return;
            try {
                await this._localContent.setOverride('char_icon', folder, file);
                this.shell.toast(`Icon override saved for ${folder}.`, 'success');
                this._loadSlotIcons(this._slots);
            } catch (e) {
                this.shell.toast('Failed to save icon override: ' + e.message, 'error');
            }
        });
        input.click();
    }

    _onSlotsTableChange(e) {
        const input = e.target.closest('input.gm-color-input');
        if (!input || !this._localContent) return;
        const folder = input.dataset.folder;
        if (!folder) { this.shell.toast('This slot has no character folder to attach a color to.', 'error'); return; }
        this._localContent.setClientColor(folder, input.value);
        this.shell.toast(`Color saved for ${folder}.`, 'success');
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
