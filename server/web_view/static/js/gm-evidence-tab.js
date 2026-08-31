/**
 * gm-evidence-tab.js
 * EvidenceTab: visual interface for an area's Evidence list. Under the
 * hood each item's `desc` field doubles as a demo script for the
 * Automation Demos system (scripting.py + script_runner.py, the /demo
 * command) -- that coupling is unchanged, only the panel's user-facing
 * vocabulary is "Evidence" now (was "Demos").
 *
 * Adds an area picker (the read/edit/run/stop endpoints work on any area of
 * the hub -- Run/Stop act on the picked area, not the GM's live one) and
 * per-item icon resolution/override via the injected GMLocalContent.
 */

/** The standard AO courtroom positions, used to populate the Pos dropdown
 * when the area's `pos_lock` is empty (no locked positions = any position
 * is meaningful, so offer the well-known ones). */
const EVIDENCE_DEFAULT_POS = ['all', 'hidden', 'wit', 'def', 'pro', 'hlp', 'hld', 'jud', 'sea', 'jur'];

class EvidenceTab extends TabBase {
    /**
     * @param {GMPanelShell} shell
     * @param {ApiClient} api
     * @param {HTMLElement} root
     * @param {?GMLocalContent} localContent - optional; resolves each
     *   item's icon (kind 'evidence') and backs the per-item override
     *   button. Safe to omit -- icons just stay on the text fallback.
     */
    constructor(shell, api, root, localContent) {
        super(shell, api, root);
        this._localContent = localContent || null;

        this._areaId = null;
        this._areaName = '';
        this._hubAreas = [];
        this._evidenceList = [];
        this._selectedEvidenceId = null;
        this._reloadRetried = false;
        // Last persisted snapshot of every editable field, used as the
        // baseline for dirty tracking; null while no item is loaded.
        this._savedSnapshot = null;
        this._saving = false;

        this._areaLabel = root.querySelector('#evidenceAreaLabel');
        this._areaSelect = root.querySelector('#evidenceAreaSelect');
        this._tbody = root.querySelector('#evidenceTbody');
        this._nameInput = root.querySelector('#evidenceNameInput');
        this._imageInput = root.querySelector('#evidenceImageInput');
        this._iconPreview = root.querySelector('#evidenceIconPreview');
        this._iconOverrideBtn = root.querySelector('#evidenceIconOverrideBtn');
        // The evidence description (desc) doubles as the demo script -- this
        // editor is where a GM reads/writes it as plain item text; the Demos
        // tab is the richer Text/Visual authoring surface for the same field.
        this._editor = root.querySelector('#evidenceScriptEditor');
        this._warningsEl = root.querySelector('#evidenceParseWarnings');
        this._posInput = root.querySelector('#evidencePosInput');
        this._posAddSelect = root.querySelector('#evidencePosAddSelect');
        this._posOptions = root.querySelector('#evidencePosOptions');
        this._posPool = [];
        this._showInDarkSelect = root.querySelector('#evidenceShowInDarkSelect');
        this._canHideInCheck = root.querySelector('#evidenceCanHideInCheck');
        this._canTakeCheck = root.querySelector('#evidenceCanTakeCheck');
        this._editableCheck = root.querySelector('#evidenceEditableCheck');
        this._triggersInput = root.querySelector('#evidenceTriggersInput');
        this._packSelect = root.querySelector('#evidencePackSelect');
        this._packOverlayCheck = root.querySelector('#evidencePackOverlayCheck');
        this._packNameInput = root.querySelector('#evidencePackNameInput');
        this._areaSelect.addEventListener('change', () => this._onAreaPicked());
        root.querySelector('#evidenceRefreshBtn').addEventListener('click', () => this.reload());
        root.querySelector('#evidenceNewBtn').addEventListener('click', () => this._newEvidence());
        root.querySelector('#evidenceStopAllBtn').addEventListener('click', () => this._stopAll());
        root.querySelector('#evidenceSaveBtn').addEventListener('click', () => this._saveItem());
        root.querySelector('#evidenceEditScriptBtn').addEventListener('click', () => this._editScript());
        root.querySelector('#evidenceDeleteBtn').addEventListener('click', () => this._delete());
        root.querySelector('#evidencePackLoadBtn').addEventListener('click', () => this._loadPack());
        root.querySelector('#evidencePackSaveBtn').addEventListener('click', () => this._savePack());
        this._iconOverrideBtn.addEventListener('click', () => this._promptIconOverride());
        this._tbody.addEventListener('click', (e) => this._onTableClick(e));
        this._posAddSelect.addEventListener('change', () => this._onPosAdd());

        // Warn before the browser closes the page with unsaved item edits.
        window.addEventListener('beforeunload', (e) => {
            if (this._dirty && this._selectedEvidenceId !== null) {
                e.preventDefault();
                e.returnValue = '';
            }
        });
    }

    /** Late-inject local content resolution (mirrors AreasGraphTab). */
    setLocalContent(localContent) {
        this._localContent = localContent || null;
    }

    async activate() {
        super.activate();
        await this._loadAreaOptions();
        if (this._areaId === null) this._areaId = this._currentAreaId();
        await this.reload();
        await this._loadPacks();
        this._startPolling();
    }

    deactivate() {
        super.deactivate();
        // Persist any unsaved edits before the user switches to another
        // tab. Fire-and-forget: _autoSave captures the item id up front, so
        // a late completion can't touch a newer item's baseline.
        if (this._dirty && this._selectedEvidenceId !== null) this._autoSave();
        this._stopPolling();
    }

    onEvent(msg) {
        if (msg.type === 'areas_changed') {
            this._loadAreaOptions();
            return;
        }
    }

    // --- polling: WS is the fast path; this is the catch-all -------------

    _startPolling() {
        if (typeof this.api.startPolling === 'function') {
            this.api.startPolling('evidence', () => this.reload(), 4000);
        }
    }

    _stopPolling() {
        if (typeof this.api.stopPolling === 'function') this.api.stopPolling('evidence');
    }

    /** The GM's live current area id, tracked live by the shell (header
     * identity) -- used to mark "(current)" in the picker and as its
     * fallback target. */
    _currentAreaId() {
        return this.shell.gmIdentity ? this.shell.gmIdentity.area_id : null;
    }

    /** If the picked area no longer exists (removed, or ids renumbered by
     * swap/remove), fall back to the GM's live current area, else the first
     * remaining area. Clears any selected evidence item since ids may have
     * shifted. Returns true if the picked id changed. */
    _syncAreaId() {
        if (this._hubAreas.some((a) => a.id === this._areaId)) return false;
        const current = this._currentAreaId();
        const fallback = this._hubAreas.some((a) => a.id === current)
            ? current
            : (this._hubAreas.length ? this._hubAreas[0].id : null);
        this._areaId = fallback;
        this._selectedEvidenceId = null;
        this._clearEditor();
        return true;
    }

    async _loadAreaOptions() {
        try {
            const data = await this.api.getAreas();
            this._hubAreas = data.areas || [];
            const current = this._currentAreaId();
            this._areaSelect.innerHTML = this._hubAreas.map((a) => {
                const label = `${a.id}: ${a.name}${a.id === current ? ' (current)' : ''}`;
                return `<option value="${a.id}">${esc(label)}</option>`;
            }).join('');
            const healed = this._syncAreaId();
            if (this._areaId !== null && this._hubAreas.some((a) => a.id === this._areaId)) {
                this._areaSelect.value = String(this._areaId);
            }
            this._refreshPosOptions();
            // The picked area vanished while we were showing it -- reload so
            // the list reflects a real area instead of erroring forever.
            if (healed && this.isActive && this._areaId !== null) await this.reload();
        } catch (e) {
            // non-fatal: picker just stays as-is
        }
    }

    async _onAreaPicked() {
        if (!(await this._guardUnsaved())) return;
        const val = parseInt(this._areaSelect.value, 10);
        if (Number.isNaN(val)) return;
        this._areaId = val;
        this._selectedEvidenceId = null;
        this._clearEditor();
        await this.reload();
    }

    async reload() {
        try {
            const data = await this.api.getEvidenceList(this._areaId);
            this._areaId = data.area_id;
            this._areaName = data.area_name;
            this._evidenceList = data.evidence || [];
            this._areaLabel.textContent = `Area ${data.area_id}: ${data.area_name}`;
            if (this._hubAreas.some((a) => a.id === this._areaId)) {
                this._areaSelect.value = String(this._areaId);
            }
            this._refreshPosOptions();
            this._renderList();
            if (this._selectedEvidenceId !== null && !this._evidenceList.some((d) => d.id === this._selectedEvidenceId)) {
                this._selectedEvidenceId = null;
                this._clearEditor();
            }
        } catch (e) {
            // The picked area may have been removed/renumbered out from under
            // us -- re-sync the picker once and retry before giving up.
            if (!this._reloadRetried && /area_not_found/.test(e.message || '')) {
                this._reloadRetried = true;
                try {
                    await this._loadAreaOptions();
                } finally {
                    this._reloadRetried = false;
                }
                return this.reload();
            }
            this.shell.toast('Failed to load evidence: ' + e.message, 'error');
        }
    }

    _renderList() {
        if (!this._evidenceList.length) {
            this._tbody.innerHTML = '<tr><td colspan="5" class="gm-empty">No evidence in this area.</td></tr>';
            return;
        }
        this._tbody.innerHTML = this._evidenceList.map((d) => {
            const warn = (d.parse_warnings && d.parse_warnings.length)
                ? ` <span class="gm-warn-dot" title="${esc(d.parse_warnings.join('; '))}">!</span>` : '';
            const status = d.is_running
                ? '<span class="badge running">RUNNING</span>'
                : `<span class="dim">${d.instruction_count} steps</span>`;
            const rowClass = d.id === this._selectedEvidenceId ? ' class="selected"' : '';
            return `<tr${rowClass} data-id="${d.id}">
                <td class="mono">${d.id}</td>
                <td><span class="gm-icon-slot" data-evi="${d.id}"><span class="gm-icon-fallback">${esc((d.name || '?').slice(0, 1).toUpperCase())}</span></span></td>
                <td>${esc(d.name)}${warn}</td>
                <td>${status}</td>
                <td><button class="btn-sm" data-action="open" data-id="${d.id}">Open</button></td>
            </tr>`;
        }).join('');
        this._loadListIcons();
    }

    async _loadListIcons() {
        if (!this._localContent) return;
        this._evidenceList.forEach((d) => {
            if (!d.image) return;
            this._localContent.resolve('evidence', d.image).then((url) => {
                if (!url) return;
                const slot = this._tbody.querySelector(`.gm-icon-slot[data-evi="${d.id}"]`);
                if (!slot) return;
                const img = document.createElement('img');
                img.className = 'gm-char-icon-img';
                img.alt = d.image;
                img.src = url;
                img.addEventListener('error', () => { img.remove(); });
                slot.innerHTML = '';
                slot.appendChild(img);
            }).catch(() => { /* keep the text fallback */ });
        });
    }

    async _onTableClick(e) {
        const row = e.target.closest('tr[data-id]');
        if (!row) return;
        if (!(await this._guardUnsaved())) return;
        this._openEvidence(parseInt(row.dataset.id, 10));
    }

    async _openEvidence(id) {
        try {
            const d = await this.api.getEvidenceItem(this._areaId, id);
            this._selectedEvidenceId = id;
            this._nameInput.value = d.name || '';
            this._imageInput.value = d.image || '';
            this._editor.value = d.desc || '';
            this._editor.readOnly = false;
            this._renderWarnings(d.parse_warnings || []);
            this._populateProps(d);
            // Baseline everything (name, image, desc, props) after all the
            // fields are populated, so only real edits count as dirty.
            this._savedSnapshot = this._captureSnapshot();
            this._renderList();
            this._loadDetailIcon();
        } catch (e) {
            this.shell.toast('Failed to load evidence item: ' + e.message, 'error');
        }
    }

    _loadDetailIcon() {
        this._iconPreview.innerHTML = '<span class="gm-icon-fallback">?</span>';
        const image = this._imageInput.value;
        if (!this._localContent || !image) return;
        this._localContent.resolve('evidence', image).then((url) => {
            if (!url) return;
            const img = document.createElement('img');
            img.className = 'gm-char-icon-img gm-char-icon-img-lg';
            img.alt = image;
            img.src = url;
            img.addEventListener('error', () => { img.remove(); });
            this._iconPreview.innerHTML = '';
            this._iconPreview.appendChild(img);
        }).catch(() => { /* keep the fallback */ });
    }

    async _promptIconOverride() {
        if (!this._localContent) { this.shell.toast('Local content is not available.', 'error'); return; }
        const image = this._imageInput.value.trim();
        if (!image) { this.shell.toast('Set an image name first.', 'error'); return; }
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'image/*';
        input.addEventListener('change', async () => {
            const file = input.files && input.files[0];
            if (!file) return;
            try {
                await this._localContent.setOverride('evidence', image, file);
                this.shell.toast(`Icon override saved for ${image}.`, 'success');
                this._loadDetailIcon();
                this._loadListIcons();
            } catch (e) {
                this.shell.toast('Failed to save icon override: ' + e.message, 'error');
            }
        });
        input.click();
    }

    /** Refresh the "Add pos…" dropdown: always 'all' and 'hidden', then the
     * picked area's `pos_lock` names (falling back to the common courtroom
     * positions when the area has no locked positions). Deduped
     * case-insensitively, keeping first-seen order. */
    _refreshPosOptions() {
        const area = this._hubAreas.find((a) => a.id === this._areaId);
        const locked = (area && Array.isArray(area.pos_lock) ? area.pos_lock : []).map((p) => String(p));
        const pool = locked.length ? ['all', 'hidden', ...locked] : EVIDENCE_DEFAULT_POS;
        const seen = new Set();
        this._posPool = [];
        for (const p of pool) {
            const key = p.trim().toLowerCase();
            if (!key || seen.has(key)) continue;
            seen.add(key);
            this._posPool.push(p.trim());
        }
        if (this._posAddSelect) {
            this._posAddSelect.innerHTML = '<option value="">Add pos…</option>'
                + this._posPool.map((p) => `<option value="${esc(p)}">${esc(p)}</option>`).join('');
        }
        // The datalist offers the same suggestions inline while typing.
        if (this._posOptions) {
            this._posOptions.innerHTML = this._posPool
                .map((p) => `<option value="${esc(p)}">${esc(p)}</option>`).join('');
        }
    }

    /** The "Add pos…" dropdown appends a position to the comma-separated
     * text field instead of replacing it (so hlp, def, pro… can be built up
     * pick by pick). 'all' and 'hidden' are terminal -- they replace. */
    _onPosAdd() {
        const picked = this._posAddSelect.value;
        if (!picked) return;
        this._posAddSelect.value = '';
        if (picked === 'all' || picked === 'hidden') {
            this._posInput.value = picked;
            return;
        }
        const current = this._posInput.value.split(',').map((s) => s.trim()).filter((s) => s.length > 0);
        if (current.some((p) => p.toLowerCase() === picked.toLowerCase())) {
            this.shell.toast(`Pos "${picked}" is already in the list.`, 'info');
            return;
        }
        current.push(picked);
        this._posInput.value = current.join(', ');
    }

    _clearEditor() {
        this._nameInput.value = '';
        this._imageInput.value = '';
        this._editor.value = '';
        this._savedSnapshot = null;
        this._editor.readOnly = false;
        this._warningsEl.innerHTML = '';
        this._iconPreview.innerHTML = '<span class="gm-icon-fallback">?</span>';
        this._posInput.value = 'all';
        this._posAddSelect.value = '';
        this._showInDarkSelect.value = '0';
        this._canHideInCheck.checked = false;
        this._canTakeCheck.checked = true;
        this._editableCheck.checked = true;
        this._triggersInput.value = '';
    }

    /** Reflect an evidence item's property fields into the editor. */
    _populateProps(d) {
        this._posInput.value = (d.pos !== undefined && d.pos !== null) ? String(d.pos) : 'all';
        this._showInDarkSelect.value = String(d.show_in_dark !== undefined && d.show_in_dark !== null ? d.show_in_dark : 0);
        this._canHideInCheck.checked = !!d.can_hide_in;
        this._canTakeCheck.checked = d.can_take !== false;
        this._editableCheck.checked = d.editable !== false;
        this._triggersInput.value = this._triggersToText(d.triggers);
    }

    /** `{present: "demo 3"}` -> `present demo 3`, one trigger per line. */
    _triggersToText(triggers) {
        return Object.entries(triggers || {})
            .filter(([, v]) => v !== '' && v !== null && v !== undefined)
            .map(([k, v]) => `${k} ${v}`)
            .join('\n');
    }

    /** `present demo 3` per line -> `{present: "demo 3"}` (key is the first
     * token, everything after it is the trigger's command+args). */
    _textToTriggers(text) {
        const out = {};
        for (const rawLine of text.split('\n')) {
            const line = rawLine.trim();
            if (!line) continue;
            const idx = line.indexOf(' ');
            if (idx <= 0) { out[line] = ''; continue; }
            out[line.slice(0, idx)] = line.slice(idx + 1).trim();
        }
        return out;
    }

    _collectProps() {
        return {
            pos: this._posInput.value.trim() || 'all',
            can_hide_in: this._canHideInCheck.checked,
            show_in_dark: parseInt(this._showInDarkSelect.value, 10),
            can_take: this._canTakeCheck.checked,
            editable: this._editableCheck.checked,
            triggers: this._textToTriggers(this._triggersInput.value),
        };
    }

    _renderWarnings(warnings) {
        this._warningsEl.innerHTML = warnings.length
            ? `<div class="gm-warnings-box">${warnings.map((w) => `⚠ ${esc(w)}`).join('<br>')}</div>`
            : '';
    }

    // --- dirty tracking & autosave ---------------------------------------

    /** Capture the current value of every editable field. Doubles as the
     * baseline for dirty tracking and as the basis for the autosave payload. */
    _captureSnapshot() {
        return {
            name: this._nameInput.value,
            image: this._imageInput.value,
            desc: this._editor.value,
            props: this._collectProps(),
        };
    }

    /** True when any editable field differs from the last persisted one. */
    get _dirty() {
        if (this._savedSnapshot === null) return false;
        const cur = this._captureSnapshot();
        const snap = this._savedSnapshot;
        return snap.name !== cur.name
            || snap.image !== cur.image
            || snap.desc !== cur.desc
            || JSON.stringify(snap.props) !== JSON.stringify(cur.props);
    }

    /**
     * Persist the current item (name, image, description and all property
     * fields) if anything has unsaved edits. Returns true when the item is
     * safely on the server (saved, or nothing to save). The payload is the
     * same shape the Save button sends; the area/evidence id is captured up
     * front so a save finishing after the user has moved on can't touch the
     * baseline of whatever is loaded then.
     */
    async _autoSave() {
        if (this._selectedEvidenceId === null || this._saving) return true;
        if (!this._dirty) return true;
        this._saving = true;
        const areaId = this._areaId;
        const evidenceId = this._selectedEvidenceId;
        const payload = {
            name: this._nameInput.value.trim() || 'Untitled',
            image: this._imageInput.value,
            desc: this._editor.value,
            props: this._collectProps(),
        };
        try {
            await this.api.putEvidenceItem(areaId, evidenceId, payload);
            if (this._selectedEvidenceId === evidenceId && this._areaId === areaId) {
                this._savedSnapshot = this._captureSnapshot();
                this.shell.toast('Autosaved.', 'success');
            }
            return true;
        } catch (e) {
            this.shell.toast('Autosave failed: ' + e.message, 'error');
            return false;
        } finally {
            this._saving = false;
        }
    }

    /**
     * Guard used before leaving the current evidence item (area switch, row
     * click, new item, pack load, Demos handoff): autosave unsaved changes,
     * and if that fails ask whether to proceed anyway. Returns true when
     * it's safe to proceed.
     */
    async _guardUnsaved() {
        if (!this._dirty || this._selectedEvidenceId === null) return true;
        if (await this._autoSave()) return true;
        return confirm("Could not autosave this evidence item's changes. Proceed and lose unsaved changes?");
    }

    async _newEvidence() {
        if (!(await this._guardUnsaved())) return;
        this._selectedEvidenceId = null;
        this._clearEditor();
        this._nameInput.value = 'New Evidence';
        this._nameInput.focus();
        this._renderList();
    }

    async _saveItem() {
        const name = this._nameInput.value.trim() || 'Untitled';
        const image = this._imageInput.value;
        // The description IS the demo script (evidence `desc` doubles as it),
        // so the description editor writes the same field the Demos tab edits.
        const desc = this._editor.value;
        const savedId = this._selectedEvidenceId;
        const props = this._collectProps();
        try {
            if (this._selectedEvidenceId === null) {
                const created = await this.api.newEvidenceItem(this._areaId, { name, desc, image, props });
                this.shell.toast('Evidence created.', 'success');
                await this.reload();
                if (created && created.id !== undefined) await this._openEvidence(created.id);
            } else {
                await this.api.putEvidenceItem(this._areaId, savedId, { name, desc, image, props });
                this.shell.toast('Evidence saved.', 'success');
                await this.reload();
                await this._openEvidence(savedId);
            }
        } catch (e) {
            this.shell.toast('Failed to save evidence: ' + e.message, 'error');
        }
    }

    async _delete() {
        if (this._selectedEvidenceId === null) { this.shell.toast('No evidence item selected.', 'error'); return; }
        if (!confirm('Delete this evidence item? This cannot be undone.')) return;
        try {
            await this.api.deleteEvidenceItem(this._areaId, this._selectedEvidenceId);
            this.shell.toast('Evidence deleted.', 'success');
            this._selectedEvidenceId = null;
            this._clearEditor();
            await this.reload();
        } catch (e) {
            this.shell.toast('Failed to delete evidence: ' + e.message, 'error');
        }
    }

    /** Send the selected evidence item's script to the Demos tab, which now
     * owns script authoring (Text + Visual/Blockly). */
    async _editScript() {
        if (this._selectedEvidenceId === null) {
            this.shell.toast('Select an evidence item first.', 'error');
            return;
        }
        // The Demos tab will load the item fresh from the server, so persist
        // any unsaved description edit first.
        if (!(await this._guardUnsaved())) return;
        const demosTab = this.shell.tabs.get('demos');
        if (demosTab && typeof demosTab.openScript === 'function') {
            this.shell.switchTab('demos');
            demosTab.openScript(this._areaId, this._selectedEvidenceId);
        } else {
            this.shell.toast('The Demos tab is not available.', 'error');
        }
    }

    async _stopAll() {
        if (!confirm('Stop demos running in every area of this hub?')) return;
        try {
            const result = await this.api.stopAllEvidence(this._areaId);
            this.shell.toast((result.output || []).join(' ') || 'Stopped all demos in the hub.', result.ok ? 'success' : 'error');
        } catch (e) {
            this.shell.toast('Failed to stop all: ' + e.message, 'error');
        }
    }

    async _loadPacks() {
        try {
            const data = await this.api.getEvidencePacks();
            const packs = data.packs || [];
            this._packSelect.innerHTML = packs.length
                ? packs.map((p) => `<option value="${esc(p)}">${esc(p)}</option>`).join('')
                : '<option value="">(none saved)</option>';
        } catch (e) {
            // non-fatal: pack picker just stays empty
        }
    }

    async _loadPack() {
        const name = this._packSelect.value;
        if (!name) return;
        const overlay = this._packOverlayCheck.checked;
        if (!overlay && !confirm(`Replace this area's evidence list with "${name}"?`)) return;
        // Loading a pack replaces the list; keep any unsaved description edit.
        if (!(await this._guardUnsaved())) return;
        try {
            const result = await this.api.loadEvidencePack(name, this._areaId, overlay);
            this.shell.toast((result.output || []).join(' ') || 'Pack loaded.', result.ok ? 'success' : 'error');
            await this.reload();
        } catch (e) {
            this.shell.toast('Failed to load pack: ' + e.message, 'error');
        }
    }

    async _savePack() {
        const name = this._packNameInput.value.trim();
        if (!name) { this.shell.toast('Pack name is required.', 'error'); return; }
        try {
            const result = await this.api.saveEvidencePack(this._areaId, name);
            this.shell.toast((result.output || []).join(' ') || 'Pack saved.', result.ok ? 'success' : 'error');
            this._packNameInput.value = '';
            await this._loadPacks();
        } catch (e) {
            this.shell.toast('Failed to save pack: ' + e.message, 'error');
        }
    }

}
