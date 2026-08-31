/**
 * gm-demos-tab.js
 * DemosTab ("Demos"): the authoring home for demo scripts, with two
 * sub-tabs that edit the same script text:
 *   - "Text" -- the plain script textarea (the classic editor, moved here
 *     from the Evidence tab) plus expression eval.
 *   - "Visual" -- a Blockly workspace (see gm-demo-blocks.js) where every
 *     workspace change regenerates the script text live.
 *
 * Scripts are deliberately treated as their own entity here. The tab talks
 * to "scripts" only through the thin DemosScriptStore adapter below; today
 * a script's storage happens to be an evidence item's `desc`, but evidence
 * and demo scripting are meant to be separated eventually, and when that
 * happens only the adapter's implementations change -- not this tab, the
 * blocks, or the generator.
 */

/**
 * The persistence seam for scripts. Each method is backed by the evidence
 * endpoints for now (the only storage that exists); swap the bodies for
 * real script endpoints when scripts stop living inside evidence `desc`.
 * The parse() method is deliberately NOT evidence-shaped -- it speaks the
 * scripting language itself via POST /api/gm/demos/parse.
 */
class DemosScriptStore {
    constructor(api) {
        this._api = api;
    }

    /** List the scripts of an area (currently: its evidence items). */
    listScripts(areaId) {
        return this._api.getEvidenceList(areaId);
    }

    /** Load one script (name/image/desc + parsed instructions + warnings). */
    loadScript(areaId, scriptId) {
        return this._api.getEvidenceItem(areaId, scriptId);
    }

    /** Save a script's text, keeping the item's name/image untouched. */
    saveScript(areaId, scriptId, desc) {
        return this._api.putEvidenceItem(areaId, scriptId, { name: '*', desc, image: '*' });
    }

    /** Create a new empty script and return {ok, id}. */
    createScript(areaId, name) {
        return this._api.newEvidenceItem(areaId, { name, desc: '', image: '' });
    }

    run(areaId, scriptId) { return this._api.runEvidence(areaId, scriptId); }
    stop(areaId) { return this._api.stopEvidence(areaId); }
    stopAll(areaId) { return this._api.stopAllEvidence(areaId); }
    status(areaId) { return this._api.getEvidenceStatus(areaId); }
    evalExpression(areaId, expression) { return this._api.evalExpression(areaId, expression); }

    /** Parse script text with the authoritative server parser. */
    parse(text, areaId) {
        return this._api.parseScript(text, areaId);
    }
}

class DemosTab extends TabBase {
    /**
     * @param {GMPanelShell} shell
     * @param {ApiClient} api
     * @param {HTMLElement} root
     */
    constructor(shell, api, root) {
        super(shell, api, root);

        this._store = new DemosScriptStore(api);

        this._areaId = null;
        this._hubAreas = [];
        this._scripts = [];
        this._selectedScriptId = null;
        this._itemName = '';
        this._itemImage = '';
        this._scriptText = '';
        // Parsed instructions straight from the server for the currently
        // loaded script; null once the text has been edited in any way.
        this._loadedInstructions = null;
        this._parseWarnings = [];
        this._pendingOpen = null;
        this._statusTimer = null;
        this._reloadRetried = false;
        // Last text persisted to the server (baseline for dirty tracking).
        this._savedText = '';
        this._saving = false;

        this._areaLabel = root.querySelector('#demosAreaLabel');
        this._areaSelect = root.querySelector('#demosAreaSelect');
        this._scriptSelect = root.querySelector('#demosScriptSelect');
        this._scriptHint = root.querySelector('#demosScriptHint');
        this._textEditor = root.querySelector('#demosScriptEditor');
        this._warningsEl = root.querySelector('#demosParseWarnings');
        this._evalInput = root.querySelector('#demosEvalInput');
        this._evalResult = root.querySelector('#demosEvalResult');
        this._evalBtn = root.querySelector('#demosEvalBtn');
        this._blocklyWrap = root.querySelector('#demosBlockly');
        this._blocklyWarningsEl = root.querySelector('#demosBlocklyWarnings');
        this._statusBox = root.querySelector('#demosStatusBox');
        this._runBtn = root.querySelector('#demosRunBtn');
        this._stopBtn = root.querySelector('#demosStopBtn');

        this._visualEditor = new DemoBlockEditor(this._blocklyWrap, (text, warnings) => {
            this._onVisualChange(text, warnings);
        });

        // --- Sub-tab navigation ---
        this._subtabButtons = Array.from(root.querySelectorAll('.gm-subtab[data-subtab]'));
        this._subtabBodies = Array.from(root.querySelectorAll('.gm-demos-body[data-subtab]'));
        this._subtabButtons.forEach((btn) => {
            btn.addEventListener('click', () => this._setSubtab(btn.dataset.subtab));
        });

        this._areaSelect.addEventListener('change', () => this._onAreaPicked());
        this._scriptSelect.addEventListener('change', () => this._onScriptPicked());
        root.querySelector('#demosRefreshBtn').addEventListener('click', () => this.reload());
        root.querySelector('#demosNewBtn').addEventListener('click', () => this._newScript());
        root.querySelector('#demosSaveBtn').addEventListener('click', () => this._save());
        root.querySelector('#demosStopAllBtn').addEventListener('click', () => this._stopAll());
        this._runBtn.addEventListener('click', () => this._run());
        this._stopBtn.addEventListener('click', () => this._stop());
        this._evalBtn.addEventListener('click', () => this._evaluate());
        this._textEditor.addEventListener('input', () => this._onTextInput());

        // Warn before the browser closes the page with unsaved script edits.
        window.addEventListener('beforeunload', (e) => {
            if (this._dirty && this._selectedScriptId !== null) {
                e.preventDefault();
                e.returnValue = '';
            }
        });
    }

    /** Open a specific script, switching this tab to it (used by the
     * Evidence tab's "Edit script in Demos" button). Safe to call before
     * the tab has activated: the request is remembered and consumed once
     * the area list has loaded. */
    openScript(areaId, scriptId) {
        this._pendingOpen = { areaId, scriptId };
        if (this.isActive) this._consumePendingOpen();
    }

    async _consumePendingOpen() {
        if (!this._pendingOpen) return;
        const { areaId, scriptId } = this._pendingOpen;
        this._pendingOpen = null;
        await this._loadAreaOptions();
        if (this._hubAreas.some((a) => a.id === areaId)) {
            this._areaId = areaId;
            this._areaSelect.value = String(areaId);
            await this.reload();
            await this._openScript(scriptId);
        }
    }

    async activate() {
        super.activate();
        await this._loadAreaOptions();
        if (this._areaId === null) this._areaId = this._currentAreaId();
        if (this._areaId === null && this._hubAreas.length) this._areaId = this._hubAreas[0].id;
        await this.reload();
        this._setSubtab(this._storedSubtab(), { skipSync: true });
        this._startPolling();
        this._startStatusPolling();
        // Any pending open must land before the visual sync runs, so the
        // workspace is built from the opened script -- not stale text.
        if (this._pendingOpen) await this._consumePendingOpen();
        if (this._activeSubtab === 'visual') await this._syncTextToVisual();
    }

    deactivate() {
        super.deactivate();
        // Persist any unsaved edit before the user switches to another tab.
        // Fire-and-forget: _autoSave captures the script id at start, so a
        // late completion can't dirty a newer script's baseline.
        if (this._dirty && this._selectedScriptId !== null) this._autoSave();
        this._stopPolling();
        this._stopStatusPolling();
    }

    onEvent(msg) {
        if (msg.type === 'areas_changed') {
            this._loadAreaOptions();
            return;
        }
    }

    // --- polling ----------------------------------------------------------

    _startPolling() {
        if (typeof this.api.startPolling === 'function') {
            this.api.startPolling('demos', () => this.reload(), 4000);
        }
    }

    _stopPolling() {
        if (typeof this.api.stopPolling === 'function') this.api.stopPolling('demos');
    }

    _startStatusPolling() {
        this._stopStatusPolling();
        this._refreshStatus();
        this._statusTimer = setInterval(() => this._refreshStatus(), 1000);
    }

    _stopStatusPolling() {
        if (this._statusTimer) { clearInterval(this._statusTimer); this._statusTimer = null; }
    }

    /** The GM's live current area id (shell identity), for picker marking. */
    _currentAreaId() {
        return this.shell.gmIdentity ? this.shell.gmIdentity.area_id : null;
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
            if (this._areaId !== null && this._hubAreas.some((a) => a.id === this._areaId)) {
                this._areaSelect.value = String(this._areaId);
            } else if (this._hubAreas.length) {
                this._areaId = this._hubAreas[0].id;
                this._areaSelect.value = String(this._areaId);
            }
        } catch (e) {
            // non-fatal: picker stays as-is
        }
    }

    async _onAreaPicked() {
        if (!(await this._guardUnsaved())) return;
        const val = parseInt(this._areaSelect.value, 10);
        if (Number.isNaN(val)) return;
        this._areaId = val;
        this._clearSelection();
        await this.reload();
    }

    async reload() {
        try {
            const data = await this._store.listScripts(this._areaId);
            this._areaId = data.area_id;
            this._scripts = data.evidence || [];
            this._areaLabel.textContent = `Area ${data.area_id}: ${data.area_name}`;
            if (this._hubAreas.some((a) => a.id === this._areaId)) {
                this._areaSelect.value = String(this._areaId);
            }
            this._renderScriptSelect();
            this._updateRunStopState();
            if (this._selectedScriptId !== null && !this._scripts.some((s) => s.id === this._selectedScriptId)) {
                this._selectedScriptId = null;
                this._clearSelection();
            }
        } catch (e) {
            if (!this._reloadRetried && /area_not_found/.test(e.message || '')) {
                this._reloadRetried = true;
                try { await this._loadAreaOptions(); } finally { this._reloadRetried = false; }
                return this.reload();
            }
            this.shell.toast('Failed to load scripts: ' + e.message, 'error');
        }
    }

    _renderScriptSelect() {
        const options = this._scripts.map((s) => {
            const warn = (s.parse_warnings && s.parse_warnings.length) ? ' ⚠' : '';
            const steps = s.is_running ? ' (running)' : ` (${s.instruction_count} steps)`;
            return `<option value="${s.id}">${esc(s.name)}${warn}${steps}</option>`;
        }).join('');
        this._scriptSelect.innerHTML = options
            || '<option value="">(no scripts in this area)</option>';
        if (this._selectedScriptId !== null) {
            this._scriptSelect.value = String(this._selectedScriptId);
        }
    }

    async _onScriptPicked() {
        if (!(await this._guardUnsaved())) return;
        const val = parseInt(this._scriptSelect.value, 10);
        if (Number.isNaN(val)) return;
        this._openScript(val);
    }

    async _openScript(id, opts) {
        opts = opts || {};
        try {
            const d = await this._store.loadScript(this._areaId, id);
            this._selectedScriptId = id;
            this._itemName = d.name || '';
            this._itemImage = d.image || '';
            this._scriptText = d.desc || '';
            this._savedText = this._scriptText;
            this._loadedInstructions = d.instructions || null;
            this._parseWarnings = d.parse_warnings || [];
            this._textEditor.value = this._scriptText;
            this._scriptSelect.value = String(id);
            this._scriptHint.textContent = this._itemName ? `Editing: ${this._itemName}` : '';
            this._renderWarnings(this._parseWarnings, this._warningsEl);
            if (this._activeSubtab === 'visual' && !opts.skipImport) {
                this._visualEditor.importInstructions(this._loadedInstructions || []);
            }
            this._renderScriptSelect();
            this._updateRunStopState();
        } catch (e) {
            this.shell.toast('Failed to load script: ' + e.message, 'error');
        }
    }

    _clearSelection() {
        this._selectedScriptId = null;
        this._itemName = '';
        this._itemImage = '';
        this._scriptText = '';
        this._savedText = '';
        this._loadedInstructions = null;
        this._parseWarnings = [];
        this._textEditor.value = '';
        this._scriptHint.textContent = '';
        this._renderWarnings([], this._warningsEl);
        if (this._visualEditor.ready) this._visualEditor.clear();
        this._renderScriptSelect();
        this._updateRunStopState();
    }

    // --- Text/Visual sub-tab sync ----------------------------------------

    _storedSubtab() {
        try {
            return localStorage.getItem('gmDemosTab.subtab') || 'text';
        } catch (e) {
            return 'text';
        }
    }

    async _setSubtab(name, opts) {
        opts = opts || {};
        if (!this._subtabBodies.some((el) => el.dataset.subtab === name)) name = 'text';
        // Switching editors is safe to do while unsaved (the buffer survives),
        // but autosave first so the work is on the server either way.
        // Re-clicking the already-active sub-tab skips the guard but still
        // falls through to the re-sync below.
        if (name !== this._activeSubtab && !(await this._guardUnsaved())) return;
        this._subtabButtons.forEach((b) => b.classList.toggle('active', b.dataset.subtab === name));
        this._subtabBodies.forEach((el) => el.classList.toggle('hidden', el.dataset.subtab !== name));
        this._activeSubtab = name;
        try { localStorage.setItem('gmDemosTab.subtab', name); } catch (e) { /* best effort */ }
        if (opts.skipSync) return;
        if (name === 'visual') this._syncTextToVisual();
    }

    /**
     * Text -> Visual: rebuild the workspace from the current script text,
     * parsed by the authoritative server parser (never a JS re-implementation
     * of the grammar). Always parses -- even freshly-opened scripts -- so the
     * workspace is always an exact mirror of the text buffer.
     */
    async _syncTextToVisual() {
        try {
            const parsed = await this._store.parse(this._scriptText, this._areaId);
            // Give Blockly a visible, sized container before injecting.
            requestAnimationFrame(() => {
                this._visualEditor.importInstructions(parsed.instructions || []);
            });
        } catch (e) {
            this.shell.toast('Could not switch to blocks: ' + e.message, 'error');
            this._setSubtab('text', { skipSync: true });
        }
    }

    _onTextInput() {
        this._scriptText = this._textEditor.value;
        this._loadedInstructions = null;
    }

    /** Visual -> buffer: keep the script text and Text editor in sync. */
    _onVisualChange(text, warnings) {
        this._scriptText = text;
        this._loadedInstructions = null;
        this._textEditor.value = text;
        this._renderWarnings(warnings, this._blocklyWarningsEl);
    }

    _renderWarnings(warnings, el) {
        if (!el) return;
        el.innerHTML = warnings.length
            ? `<div class="gm-warnings-box">${warnings.map((w) => `⚠ ${esc(w)}`).join('<br>')}</div>`
            : '';
    }

    // --- dirty tracking & autosave ---------------------------------------

    /** True when the in-memory script text differs from the last persisted one. */
    get _dirty() {
        return this._savedText !== this._scriptText;
    }

    /**
     * Persist the current script text if it has unsaved edits. Returns true
     * when the text is safely on the server (saved, or nothing to save).
     * Uses no reload / workspace rebuild -- the manual Save button keeps
     * that heavier refresh. The area/script id is captured up front so a
     * save finishing after the user has moved on can't touch the baseline
     * of whatever script is loaded then.
     */
    async _autoSave() {
        if (this._selectedScriptId === null || !this._dirty || this._saving) return true;
        this._saving = true;
        const areaId = this._areaId;
        const scriptId = this._selectedScriptId;
        const text = this._scriptText;
        try {
            await this._store.saveScript(areaId, scriptId, text);
            if (this._selectedScriptId === scriptId && this._areaId === areaId) {
                this._savedText = text;
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
     * Guard used before leaving the current script view (sub-tab switch,
     * another script/area, new script): autosave unsaved edits, and if that
     * fails ask whether to proceed without saving. Returns true when it's
     * safe to proceed.
     */
    async _guardUnsaved() {
        if (!this._dirty || this._selectedScriptId === null) return true;
        if (await this._autoSave()) return true;
        return confirm('Could not autosave the current script. Proceed without saving?');
    }

    // --- actions ----------------------------------------------------------

    async _newScript() {
        const name = prompt('Name the new script:', 'New Script') || 'New Script';
        if (!(await this._guardUnsaved())) return;
        try {
            const created = await this._store.createScript(this._areaId, name);
            this.shell.toast('Script created.', 'success');
            await this.reload();
            if (created && created.id !== undefined) await this._openScript(created.id);
        } catch (e) {
            this.shell.toast('Failed to create script: ' + e.message, 'error');
        }
    }

    async _save() {
        if (this._selectedScriptId === null) {
            this.shell.toast('Select or create a script first.', 'error');
            return;
        }
        // Blocks are the source of truth in Visual mode and already pushed
        // to _scriptText by _onVisualChange on every edit.
        try {
            await this._store.saveScript(this._areaId, this._selectedScriptId, this._scriptText);
            this.shell.toast('Script saved.', 'success');
            const savedId = this._selectedScriptId;
            await this.reload();
            // Refresh instructions/warnings from the server without
            // disturbing the current workspace (blocks == saved text).
            await this._openScript(savedId, { skipImport: true });
        } catch (e) {
            this.shell.toast('Failed to save script: ' + e.message, 'error');
        }
    }

    _updateRunStopState() {
        this._runBtn.disabled = this._selectedScriptId === null;
        this._runBtn.title = this._selectedScriptId === null ? 'Select or create a script first.' : '';
    }

    async _run() {
        if (this._selectedScriptId === null) {
            this.shell.toast('Select or create a script first.', 'error');
            return;
        }
        try {
            const result = await this._store.run(this._areaId, this._selectedScriptId);
            this.shell.toast((result.output || []).join(' ') || 'Script started.', result.ok ? 'success' : 'error');
            this._refreshStatus();
        } catch (e) {
            this.shell.toast('Failed to run: ' + e.message, 'error');
        }
    }

    async _stop() {
        try {
            const result = await this._store.stop(this._areaId);
            this.shell.toast((result.output || []).join(' ') || 'Stopped.', result.ok ? 'success' : 'error');
            this._refreshStatus();
        } catch (e) {
            this.shell.toast('Failed to stop: ' + e.message, 'error');
        }
    }

    async _stopAll() {
        if (!confirm('Stop demos running in every area of this hub?')) return;
        try {
            const result = await this._store.stopAll(this._areaId);
            this.shell.toast((result.output || []).join(' ') || 'Stopped all demos in the hub.', result.ok ? 'success' : 'error');
            this._refreshStatus();
        } catch (e) {
            this.shell.toast('Failed to stop all: ' + e.message, 'error');
        }
    }

    async _refreshStatus() {
        if (!this.isActive || this._areaId === null) return;
        try {
            const status = await this._store.status(this._areaId);
            this._renderStatus(status);
        } catch (e) {
            // transient poll failure -- keep the last known status
        }
    }

    _renderStatus(s) {
        if (!s.running) {
            this._statusBox.innerHTML = '<div class="dim">No script running in this area.</div>';
            return;
        }
        const pct = s.instruction_count ? Math.min(100, Math.round((s.index / s.instruction_count) * 100)) : 0;
        const varsHtml = Object.entries(s.variables || {})
            .map(([k, v]) => `<tr><td class="mono">${esc(k)}</td><td>${esc(fmtValue(v))}</td></tr>`).join('');
        this._statusBox.innerHTML = `
            <div class="gm-progress"><div class="gm-progress-bar" style="width:${pct}%"></div></div>
            <div class="dim">Step ${s.index}/${s.instruction_count} · ${s.steps}/${s.max_steps} total steps taken</div>
            ${s.labels && s.labels.length ? `<div class="dim">Labels: ${esc(s.labels.join(', '))}</div>` : ''}
            ${s.modified_packets && s.modified_packets.length ? `<div class="dim">Modified packets (revert on stop): ${esc(s.modified_packets.join(', '))}</div>` : ''}
            ${varsHtml ? `<table class="gm-table gm-var-table"><thead><tr><th>Variable</th><th>Value</th></tr></thead><tbody>${varsHtml}</tbody></table>` : ''}
        `;
    }

    async _evaluate() {
        const expr = this._evalInput.value.trim();
        if (!expr || this._areaId === null) return;
        try {
            const result = await this._store.evalExpression(this._areaId, expr);
            this._evalResult.textContent = result.ok ? `= ${fmtValue(result.value)}` : `Error: ${result.error}`;
            this._evalResult.classList.toggle('error', !result.ok);
        } catch (e) {
            this._evalResult.textContent = 'Error: ' + e.message;
            this._evalResult.classList.add('error');
        }
    }
}
