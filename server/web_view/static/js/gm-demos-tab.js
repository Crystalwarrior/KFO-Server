/**
 * gm-demos-tab.js
 * DemosTab: visual interface for the Automation Demos system
 * (scripting.py + script_runner.py, the /demo command). Browse the
 * area's stored demo scripts (evidence items), view/edit their content
 * with the instruction set documented alongside, run/stop/manage demos
 * in the GM's current area, and surface script variables/state.
 */

/** Static instruction cheat-sheet, mirroring docs/demo_scripting.md. */
const DEMO_HELP_HTML = `
<h3>Demo Scripting Reference</h3>
<p>Scripts live in an evidence item's description and run with <code>/demo &lt;id&gt;</code>.
Lines end with a newline, or with <code>%</code> for packets/commands (which may span
several physical lines). <code>//</code> starts a comment.</p>

<h4>Instructions</h4>
<table>
<thead><tr><th>Instruction</th><th>What it does</th></tr></thead>
<tbody>
<tr><td><code>wait &lt;ms&gt;</code></td><td>Pause for milliseconds</td></tr>
<tr><td><code>MS#...#%</code>, <code>CT#...#%</code>, etc.</td><td>Send an AO packet to everyone in the area</td></tr>
<tr><td><code>/command args%</code></td><td>Run an OOC command as the area's character</td></tr>
<tr><td><code>set &lt;var&gt; &lt;value&gt;</code></td><td>Store a value in a variable</td></tr>
<tr><td><code>get &lt;var&gt; &lt;source&gt;</code></td><td>Read live server state into a variable</td></tr>
<tr><td><code>concat &lt;var&gt; &lt;value&gt; [sep]</code></td><td>Append text to a string variable</td></tr>
<tr><td><code>rand &lt;var&gt; &lt;min&gt; &lt;max&gt;</code></td><td>Store a random whole number</td></tr>
<tr><td><code>save &lt;char&gt; &lt;key&gt; &lt;value&gt;</code></td><td>Persist a value into a character's data</td></tr>
<tr><td><code>if &lt;a&gt; &lt;op&gt; &lt;b&gt; &lt;label&gt;</code></td><td>Jump to a label when the comparison is true</td></tr>
<tr><td><code>label &lt;name&gt;</code></td><td>Mark a spot to jump to</td></tr>
<tr><td><code>goto &lt;name&gt;</code></td><td>Jump to a label, remembering where you came from</td></tr>
<tr><td><code>return</code></td><td>Jump back to the matching <code>goto</code>; ends the script if there's nowhere to return to</td></tr>
</tbody>
</table>

<h4>Packet headers</h4>
<p>A demo may broadcast: <code>MS</code> <code>CT</code> <code>MC</code> <code>BN</code>
<code>HP</code> <code>RT</code> <code>JD</code> <code>GM</code> <code>ST</code>.
Packets don't change area state persistently (unlike the equivalent <code>/</code> commands) --
prefer <code>/bg</code>, <code>/subtheme</code> etc. when you want the change to stick for
new arrivals too.</p>

<h4>Variables in text</h4>
<p><code>&lt;!name&gt;</code> anywhere in a packet or command substitutes the current value of
<code>name</code>. Comparisons use <code>== != &lt; &gt; &lt;= &gt;=</code> (or the words
<code>eq ne lt gt le ge</code>).</p>

<h4>Escapes</h4>
<p>Need a literal <code>#</code>, <code>&amp;</code>, <code>%</code> or <code>$</code> in text?
Write <code>&lt;num&gt;</code>, <code>&lt;and&gt;</code>, <code>&lt;percent&gt;</code>,
<code>&lt;dollar&gt;</code>.</p>

<h4>Reading live state: paths</h4>
<table>
<thead><tr><th>Path</th><th>Points at</th></tr></thead>
<tbody>
<tr><td><code>clients.count</code> / <code>client[i].&lt;field&gt;</code></td><td>People in the area (id, name, char_name, char_id, char_folder, showname, pos, pair, iniswap, hidden_in, is_cm, is_gm, is_afk, hidden, blinded, sneaking, frozen, ...)</td></tr>
<tr><td><code>afk[i].&lt;field&gt;</code></td><td>Same fields, only AFK-marked people</td></tr>
<tr><td><code>timer[i].&lt;field&gt;</code></td><td><code>timer[0]</code> is hub-wide, 1-20 are the area's own (remaining_ms, static_ms, set, started)</td></tr>
<tr><td><code>evidence[i].&lt;field&gt;</code></td><td>name, desc, image, pos, show_in_dark, hiding, can_hide_in, can_take, editable</td></tr>
<tr><td><code>links[i].&lt;field&gt;</code></td><td>target, target_pos, evidence, password, locked, hidden, can_peek</td></tr>
<tr><td><code>area.&lt;field&gt;</code></td><td>Everything about the current area (name, background, locked, evidence_mod, hp_def, hp_pro, music, ...)</td></tr>
<tr><td><code>hub.&lt;field&gt;</code></td><td>The hub (name, char_list_ref, move_delay, can_gm, ...)</td></tr>
<tr><td><code>char[&lt;name&gt;].&lt;key&gt;</code></td><td>A character's saved Character Data (id or quoted folder name)</td></tr>
</tbody>
</table>
<p>Counting starts at 0. Swap <code>[i]</code> for <code>.count</code> to get a total. For
safety, mod-only details like IP/HDID hashes and <code>is_mod</code> are never exposed to
scripts.</p>

<h4>Character data</h4>
<p><code>save &lt;char&gt; &lt;key&gt; &lt;value&gt;</code> writes and persists immediately;
<code>char[...]</code> reads it back. This is the shared "blackboard" between demos,
triggers and timers.</p>

<h4>Triggers &amp; timers</h4>
<p><code>/trigger join|leave /demo N</code> and evidence <code>present</code> triggers fire a
command when something happens; <code>&lt;cid&gt;</code>/<code>&lt;showname&gt;</code>/<code>&lt;char&gt;</code>
in the queued command are replaced with the triggering player. <code>/timer N /demo M</code>
queues a demo to run when timer N expires.</p>

<h4>When things go wrong</h4>
<p>Any error prints <code>[Demo] [ERROR] ...</code> to the area and stops the script (HP bars
and background are restored). A script that runs too long stops itself at the configured step
cap. <code>/stop_demo</code> stops playback at any time.</p>
`;

class DemosTab extends TabBase {
    constructor(shell, api, root) {
        super(shell, api, root);

        this._areaId = null;
        this._areaName = '';
        this._demos = [];
        this._selectedDemoId = null;
        this._statusTimer = null;

        this._areaLabel = root.querySelector('#demosAreaLabel');
        this._tbody = root.querySelector('#demosTbody');
        this._nameInput = root.querySelector('#demoNameInput');
        this._imageInput = root.querySelector('#demoImageInput');
        this._editor = root.querySelector('#demoScriptEditor');
        this._warningsEl = root.querySelector('#demoParseWarnings');
        this._statusBox = root.querySelector('#demoStatusBox');
        this._evalInput = root.querySelector('#demoEvalInput');
        this._evalResult = root.querySelector('#demoEvalResult');
        this._packSelect = root.querySelector('#demoPackSelect');
        this._packOverlayCheck = root.querySelector('#demoPackOverlayCheck');
        this._packNameInput = root.querySelector('#demoPackNameInput');
        this._helpBox = root.querySelector('#demoHelpBox');

        root.querySelector('#demosRefreshBtn').addEventListener('click', () => this.reload());
        root.querySelector('#demoNewBtn').addEventListener('click', () => this._newDemo());
        root.querySelector('#demoStopAllBtn').addEventListener('click', () => this._stopAll());
        root.querySelector('#demoSaveBtn').addEventListener('click', () => this._saveScript());
        root.querySelector('#demoRunBtn').addEventListener('click', () => this._run());
        root.querySelector('#demoStopBtn').addEventListener('click', () => this._stop());
        root.querySelector('#demoDeleteBtn').addEventListener('click', () => this._delete());
        root.querySelector('#demoEvalBtn').addEventListener('click', () => this._evaluate());
        root.querySelector('#demoPackLoadBtn').addEventListener('click', () => this._loadPack());
        root.querySelector('#demoPackSaveBtn').addEventListener('click', () => this._savePack());
        root.querySelector('#demoHelpToggleBtn').addEventListener('click', () => this._toggleHelp());
        this._tbody.addEventListener('click', (e) => this._onTableClick(e));

        this._helpBox.innerHTML = DEMO_HELP_HTML;
    }

    async activate() {
        super.activate();
        await this.reload();
        await this._loadPacks();
        this._startStatusPolling();
    }

    deactivate() {
        super.deactivate();
        this._stopStatusPolling();
    }

    async reload() {
        try {
            const data = await this.api.getDemos(this._areaId);
            this._areaId = data.area_id;
            this._areaName = data.area_name;
            this._demos = data.demos || [];
            this._areaLabel.textContent = `Area ${data.area_id}: ${data.area_name}`;
            this._renderList();
            if (this._selectedDemoId !== null && !this._demos.some((d) => d.id === this._selectedDemoId)) {
                this._selectedDemoId = null;
                this._clearEditor();
            }
        } catch (e) {
            this.shell.toast('Failed to load demos: ' + e.message, 'error');
        }
    }

    _renderList() {
        if (!this._demos.length) {
            this._tbody.innerHTML = '<tr><td colspan="4" class="gm-empty">No demos in this area\'s evidence list.</td></tr>';
            return;
        }
        this._tbody.innerHTML = this._demos.map((d) => {
            const warn = (d.parse_warnings && d.parse_warnings.length)
                ? ` <span class="gm-warn-dot" title="${esc(d.parse_warnings.join('; '))}">!</span>` : '';
            const status = d.is_running
                ? '<span class="badge running">RUNNING</span>'
                : `<span class="dim">${d.instruction_count} steps</span>`;
            const rowClass = d.id === this._selectedDemoId ? ' class="selected"' : '';
            return `<tr${rowClass} data-id="${d.id}">
                <td class="mono">${d.id}</td>
                <td>${esc(d.name)}${warn}</td>
                <td>${status}</td>
                <td><button class="btn-sm" data-action="open" data-id="${d.id}">Open</button></td>
            </tr>`;
        }).join('');
    }

    _onTableClick(e) {
        const row = e.target.closest('tr[data-id]');
        if (!row) return;
        this._openDemo(parseInt(row.dataset.id, 10));
    }

    async _openDemo(id) {
        try {
            const d = await this.api.getDemo(this._areaId, id);
            this._selectedDemoId = id;
            this._nameInput.value = d.name || '';
            this._imageInput.value = d.image || '';
            this._editor.value = d.desc || '';
            this._editor.readOnly = !d.editable;
            this._renderWarnings(d.parse_warnings || []);
            this._renderList();
        } catch (e) {
            this.shell.toast('Failed to load demo: ' + e.message, 'error');
        }
    }

    _clearEditor() {
        this._nameInput.value = '';
        this._imageInput.value = '';
        this._editor.value = '';
        this._editor.readOnly = false;
        this._warningsEl.innerHTML = '';
    }

    _renderWarnings(warnings) {
        this._warningsEl.innerHTML = warnings.length
            ? `<div class="gm-warnings-box">${warnings.map((w) => `⚠ ${esc(w)}`).join('<br>')}</div>`
            : '';
    }

    _newDemo() {
        this._selectedDemoId = null;
        this._clearEditor();
        this._nameInput.value = 'New Demo';
        this._nameInput.focus();
        this._renderList();
    }

    async _saveScript() {
        const name = this._nameInput.value.trim() || 'Untitled';
        const image = this._imageInput.value;
        const desc = this._editor.value;
        try {
            if (this._selectedDemoId === null) {
                const created = await this.api.newDemo(this._areaId, { name, desc, image });
                this.shell.toast('Demo created.', 'success');
                await this.reload();
                if (created && created.id !== undefined) await this._openDemo(created.id);
            } else {
                await this.api.putDemo(this._areaId, this._selectedDemoId, { name, desc, image });
                this.shell.toast('Demo saved.', 'success');
                const savedId = this._selectedDemoId;
                await this.reload();
                await this._openDemo(savedId);
            }
        } catch (e) {
            this.shell.toast('Failed to save demo: ' + e.message, 'error');
        }
    }

    async _delete() {
        if (this._selectedDemoId === null) { this.shell.toast('No demo selected.', 'error'); return; }
        if (!confirm('Delete this demo? This cannot be undone.')) return;
        try {
            await this.api.deleteDemo(this._areaId, this._selectedDemoId);
            this.shell.toast('Demo deleted.', 'success');
            this._selectedDemoId = null;
            this._clearEditor();
            await this.reload();
        } catch (e) {
            this.shell.toast('Failed to delete demo: ' + e.message, 'error');
        }
    }

    async _run() {
        if (this._selectedDemoId === null) { this.shell.toast('Select or save a demo first.', 'error'); return; }
        try {
            const result = await this.api.runDemo(this._areaId, this._selectedDemoId);
            this.shell.toast((result.output || []).join(' ') || 'Demo started.', result.ok ? 'success' : 'error');
            await this.reload();
            this._refreshStatus();
        } catch (e) {
            this.shell.toast('Failed to run demo: ' + e.message, 'error');
        }
    }

    async _stop() {
        try {
            const result = await this.api.stopDemo(this._areaId);
            this.shell.toast((result.output || []).join(' ') || 'Stopped.', result.ok ? 'success' : 'error');
            await this.reload();
            this._refreshStatus();
        } catch (e) {
            this.shell.toast('Failed to stop demo: ' + e.message, 'error');
        }
    }

    async _stopAll() {
        if (!confirm('Stop demos running in every area of this hub?')) return;
        try {
            const result = await this.api.stopAllDemos(this._areaId);
            this.shell.toast((result.output || []).join(' ') || 'Stopped all demos in the hub.', result.ok ? 'success' : 'error');
            this._refreshStatus();
        } catch (e) {
            this.shell.toast('Failed to stop all demos: ' + e.message, 'error');
        }
    }

    _startStatusPolling() {
        this._stopStatusPolling();
        this._refreshStatus();
        this._statusTimer = setInterval(() => this._refreshStatus(), 1000);
    }

    _stopStatusPolling() {
        if (this._statusTimer) { clearInterval(this._statusTimer); this._statusTimer = null; }
    }

    async _refreshStatus() {
        if (!this.isActive || this._areaId === null) return;
        try {
            const status = await this.api.getDemoStatus(this._areaId);
            this._renderStatus(status);
        } catch (e) {
            // transient poll failure -- leave the last known status showing
        }
    }

    _renderStatus(s) {
        if (!s.running) {
            this._statusBox.innerHTML = '<div class="dim">No demo running in this area.</div>';
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
            const result = await this.api.evalExpression(this._areaId, expr);
            this._evalResult.textContent = result.ok ? `= ${fmtValue(result.value)}` : `Error: ${result.error}`;
            this._evalResult.classList.toggle('error', !result.ok);
        } catch (e) {
            this._evalResult.textContent = 'Error: ' + e.message;
            this._evalResult.classList.add('error');
        }
    }

    async _loadPacks() {
        try {
            const data = await this.api.getDemoPacks();
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
        if (!overlay && !confirm(`Replace this area's evidence/demo list with "${name}"?`)) return;
        try {
            const result = await this.api.loadDemoPack(name, this._areaId, overlay);
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
            const result = await this.api.saveDemoPack(this._areaId, name);
            this.shell.toast((result.output || []).join(' ') || 'Pack saved.', result.ok ? 'success' : 'error');
            this._packNameInput.value = '';
            await this._loadPacks();
        } catch (e) {
            this.shell.toast('Failed to save pack: ' + e.message, 'error');
        }
    }

    _toggleHelp() {
        this._helpBox.classList.toggle('hidden');
    }
}
