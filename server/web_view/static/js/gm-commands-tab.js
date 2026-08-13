/**
 * gm-commands-tab.js
 * CommandsTab: a free-form command console (any "/cmd args" -- leading
 * slash optional -- runs via the run endpoint) plus a searchable, grouped
 * COOKBOOK rendered from the server's auto-generated command list
 * (`GET /api/gm/commands`, backed by `CommandLister` -- see gm_panel.py).
 *
 * The cookbook is a UX aid only, grouped by the `server/commands/` submodule
 * each command is defined in: clicking an entry prefills the console input,
 * it never blocks or gates anything -- there is no client-side notion of a
 * curated/allowed subset any more than there ever was server-side. Real
 * authorization happens server-side on every run, so a permission-denied or
 * unknown command just shows up as an error line in the console, same as
 * typing it in-game would.
 *
 * This is the single console for BOTH GMs and admins. The Admin tab no longer
 * has its own command runner; admin-only extras (the `ooc` say command and hub
 * travel) are exposed here, and the cookbook is toggleable via
 * `#commandsCookbookToggleBtn`.
 */

/** Fallback used only if the list response omits docs_url. */
const GM_COMMANDS_DOCS_URL = 'https://github.com/Crystalwarrior/KFO-Server/blob/master/docs/commands.md';

class CommandsTab extends TabBase {
    constructor(shell, api, root) {
        super(shell, api, root);

        this._groups = [];      // [{module, commands: [{name, summary, usage}]}]
        this._docsUrl = GM_COMMANDS_DOCS_URL;
        this._searchQuery = '';
        // Modules the GM has manually collapsed. Groups default to open;
        // a search always force-opens whatever group has a match,
        // regardless of this set, so a collapsed group's commands are
        // never hidden from search results.
        this._collapsedModules = new Set();
        this._lastOutputEl = null;
        this._groupsEl = null;

        // Travel scope (hub-bound GM vs. server-scoped admin) + console history
        // + the cookbook show/hide preference.
        this._scope = null;
        this._cmdHistory = [];
        this._cmdHistoryIdx = -1;
        this._cookbookVisible = this._readCookbookPref();

        this._catalogEl = root.querySelector('#commandCatalog');
        this._output = root.querySelector('#commandsOutput');
        this._rawInput = root.querySelector('#commandsRawInput');
        this._scopeBar = root.querySelector('#commandsScopeBar');
        this._cookbookToggleBtn = root.querySelector('#commandsCookbookToggleBtn');
        // The static template's placeholder pre-dates the free-form runner;
        // refresh it at runtime rather than editing the template.
        this._rawInput.placeholder = '/cmd args  (any command -- the leading / is optional; the server enforces permissions)';

        // OOC/IC monitor toggles. Frames arrive over the shared /ws/gm/live
        // (via ApiClient pub/sub) as {type: 'monitor_ooc'|'monitor_ic', data}.
        this._oocMonitorActive = false;
        this._icMonitorActive = false;
        this._oocMonitorCb = root.querySelector('#commandsOocMonitorCb');
        this._icMonitorCb = root.querySelector('#commandsIcMonitorCb');
        this._oocMonitorCb.addEventListener('change', (e) => this._toggleMonitor('ooc', e.target.checked));
        this._icMonitorCb.addEventListener('change', (e) => this._toggleMonitor('ic', e.target.checked));
        this.api.on('monitor_ooc', (data) => this._onMonitorFrame('ooc', data));
        this.api.on('monitor_ic', (data) => this._onMonitorFrame('ic', data));

        root.querySelector('#commandsRunBtn').addEventListener('click', () => this._runRaw());
        this._rawInput.addEventListener('keydown', (e) => this._onInputKeydown(e));
        this._cookbookToggleBtn.addEventListener('click', () => this._toggleCookbook());

        this._applyCookbookVisibility();
        this._injectStyles();
    }

    async activate() {
        super.activate();
        if (!this._groups.length) await this._loadCatalog();
        await this._loadScope();
    }

    async _loadCatalog() {
        try {
            const data = await this.api.getCommandGroups();
            this._groups = data.groups || [];
            this._docsUrl = data.docs_url || GM_COMMANDS_DOCS_URL;
            this._renderCatalog();
        } catch (e) {
            this._catalogEl.innerHTML = `<div class="gm-empty">Failed to load command list: ${esc(e.message)}</div>`;
        }
    }

    async _loadScope() {
        try {
            this._scope = await this.api.getCommandScope();
            this._renderScope();
        } catch (e) {
            this._scope = null;
            if (this._scopeBar) this._scopeBar.textContent = '';
        }
    }

    _renderScope() {
        if (!this._scopeBar) return;
        const scope = this._scope;
        if (!scope) { this._scopeBar.textContent = ''; return; }
        // Travel moved to the header (gm-shell.js) -- this bar is now a plain
        // label: admins see their current (travelable) hub, GMs their bound one.
        const label = scope.can_travel ? 'Current hub' : 'Bound to hub';
        this._scopeBar.textContent =
            `${label}: ${scope.current_hub_name || ('#' + scope.current_hub_id)}`;
    }

    _toggleCookbook() {
        this._cookbookVisible = !this._cookbookVisible;
        this._persistCookbookPref();
        this._applyCookbookVisibility();
    }

    _readCookbookPref() {
        try {
            return localStorage.getItem('gmCommandsCookbookVisible') !== '0';
        } catch (e) {
            return true;
        }
    }

    _persistCookbookPref() {
        try {
            localStorage.setItem('gmCommandsCookbookVisible', this._cookbookVisible ? '1' : '0');
        } catch (e) {
            // Storage may be unavailable (private mode / quota); the in-memory
            // toggle still works for this session.
        }
    }

    _applyCookbookVisibility() {
        if (this._catalogEl) this._catalogEl.style.display = this._cookbookVisible ? '' : 'none';
        if (this._cookbookToggleBtn) this._cookbookToggleBtn.textContent = this._cookbookVisible ? 'Hide Cookbook' : 'Show Cookbook';
    }

    _onInputKeydown(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            this._runRaw();
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            if (this._cmdHistoryIdx > 0) {
                this._cmdHistoryIdx--;
                this._rawInput.value = this._cmdHistory[this._cmdHistoryIdx];
            }
        } else if (e.key === 'ArrowDown') {
            e.preventDefault();
            if (this._cmdHistoryIdx < this._cmdHistory.length - 1) {
                this._cmdHistoryIdx++;
                this._rawInput.value = this._cmdHistory[this._cmdHistoryIdx];
            } else {
                this._cmdHistoryIdx = this._cmdHistory.length;
                this._rawInput.value = '';
            }
        }
    }

    /** Every command across every group, flattened -- used for lookups
     * (prefill) that only need the name, not which module it's grouped
     * under. Command names are unique across the whole server.commands
     * namespace (resolve_command() maps a bare name to one function), so a
     * flat search-by-name is unambiguous. */
    _allCommands() {
        const out = [];
        this._groups.forEach((g) => (g.commands || []).forEach((c) => out.push(c)));
        return out;
    }

    _renderCatalog() {
        this._catalogEl.innerHTML = `
            <div class="gm-command-cookbook-head">
                <h3>Command Cookbook</h3>
                <input type="text" id="commandsCatalogSearch" class="gm-cookbook-search"
                       placeholder="Search commands…" autocomplete="off" spellcheck="false">
                <div class="gm-cookbook-collapse-btns">
                    <button type="button" id="commandsExpandAllBtn" class="btn-sm gm-cookbook-btn">Expand all</button>
                    <button type="button" id="commandsCollapseAllBtn" class="btn-sm gm-cookbook-btn">Collapse all</button>
                </div>
                <a href="${esc(this._docsUrl)}" target="_blank" rel="noopener noreferrer" class="gm-docs-link">Full command reference ↗</a>
            </div>
            <p class="dim gm-cookbook-hint">Click a command to prefill the console -- this is a reference, not a gate. Any command can be run free-form; the server enforces real permissions.</p>
            <div class="gm-command-cookbook-groups" id="commandsCatalogGroups"></div>`;

        this._groupsEl = this._catalogEl.querySelector('#commandsCatalogGroups');
        const searchInput = this._catalogEl.querySelector('#commandsCatalogSearch');
        searchInput.value = this._searchQuery;
        searchInput.addEventListener('input', () => {
            this._searchQuery = searchInput.value;
            this._renderCatalogList();
        });
        this._catalogEl.querySelector('#commandsExpandAllBtn').addEventListener('click', () => this._setAllGroupsCollapsed(false));
        this._catalogEl.querySelector('#commandsCollapseAllBtn').addEventListener('click', () => this._setAllGroupsCollapsed(true));
        this._groupsEl.addEventListener('click', (e) => this._onCatalogClick(e));
        this._groupsEl.addEventListener('keydown', (e) => {
            if (e.key !== 'Enter' && e.key !== ' ') return;
            const card = e.target.closest('.gm-command-cookbook-card');
            if (!card) return;
            e.preventDefault();
            this._prefillFromCatalog(card.dataset.cmd);
        });
        this._groupsEl.addEventListener('toggle', (e) => {
            const details = e.target.closest ? e.target.closest('details.gm-command-group') : null;
            if (!details) return;
            const module = details.dataset.module;
            if (details.open) this._collapsedModules.delete(module);
            else this._collapsedModules.add(module);
        }, true);

        this._renderCatalogList();
    }

    /** "Expand all" / "Collapse all" header buttons: act on every module
     * group at once by bulk-editing the same `_collapsedModules` set a
     * manual per-group toggle uses, then re-rendering -- so the result
     * persists across re-renders exactly like a manual collapse does, and
     * search's own force-open-on-match logic in _renderCatalogList()
     * (unchanged) still overrides it while a query is active. */
    _setAllGroupsCollapsed(collapsed) {
        if (collapsed) {
            this._groups.forEach((g) => this._collapsedModules.add(g.module));
        } else {
            this._collapsedModules.clear();
        }
        this._renderCatalogList();
    }

    _renderCatalogList() {
        if (!this._groupsEl) return;
        if (!this._groups.length) {
            this._groupsEl.innerHTML = '<div class="gm-empty">No commands available.</div>';
            return;
        }
        const q = this._searchQuery.trim().toLowerCase();
        const html = this._groups.map((g) => {
            const commands = !q ? (g.commands || []) : (g.commands || []).filter((c) =>
                (c.name || '').toLowerCase().includes(q) ||
                (c.summary || '').toLowerCase().includes(q) ||
                (c.usage || '').toLowerCase().includes(q));
            if (!commands.length) return '';
            const forceOpen = !!q;
            const open = forceOpen || !this._collapsedModules.has(g.module);
            return `<details class="gm-command-group" data-module="${esc(g.module)}" ${open ? 'open' : ''}>
                <summary class="gm-command-group-summary">${esc(g.module)}
                    <span class="gm-command-group-count">${commands.length}</span>
                </summary>
                <div class="gm-command-group-list">
                    ${commands.map((c) => this._cardHtml(c)).join('')}
                </div>
            </details>`;
        }).join('');
        this._groupsEl.innerHTML = html || '<div class="gm-empty">No commands match your search.</div>';
    }

    _cardHtml(c) {
        const usageHtml = c.usage ? `<div class="gm-command-usage">${esc(c.usage)}</div>` : '';
        const titleAttr = esc(c.usage || `/${c.name}`);
        return `<div class="gm-command-card gm-command-cookbook-card"
                     data-cmd="${esc(c.name)}" tabindex="0" role="button"
                     title="${titleAttr}">
            <div class="gm-command-name">/${esc(c.name)}</div>
            <div class="gm-command-summary">${esc(c.summary || '')}</div>
            ${usageHtml}
        </div>`;
    }

    _onCatalogClick(e) {
        const card = e.target.closest('.gm-command-cookbook-card');
        if (!card) return;
        this._prefillFromCatalog(card.dataset.cmd);
    }

    /** Prefills (never runs) the console input from a cookbook entry, so
     * the GM can fill in real argument values before hitting Run/Enter.
     * `usage` comes straight from the command's own docstring line(s)
     * containing "usage:" (see CommandLister._describe server-side), e.g.
     * "Usage: /overlay <background>" -- strip the leading label so what's
     * left is just the invocation snippet to prefill with. */
    _prefillFromCatalog(name) {
        const entry = this._allCommands().find((c) => c.name === name);
        if (!entry) return;
        const stripped = (entry.usage || '').replace(/\busage:\s*/gi, '').trim();
        const snippet = stripped || `/${entry.name}`;
        this._rawInput.value = snippet.startsWith('/') ? snippet : `/${snippet}`;
        this._rawInput.focus();
        const len = this._rawInput.value.length;
        this._rawInput.setSelectionRange(len, len);
    }

    _runRaw() {
        const raw = this._rawInput.value.trim();
        if (!raw) return;
        this._cmdHistory.push(raw);
        this._cmdHistoryIdx = this._cmdHistory.length;
        const body = raw.startsWith('/') ? raw.slice(1) : raw;
        const parts = body.split(/\s+/).filter(Boolean);
        const cmd = parts[0];
        if (!cmd) return;
        const arg = parts.slice(1).join(' ');
        this._rawInput.value = '';
        this._run(cmd, arg);
    }

    async _run(cmd, arg) {
        this._appendOutput(`/${cmd}${arg ? ' ' + arg : ''}`, 'Running…');
        try {
            const result = await this.api.runCommand(cmd, arg);
            const text = (result.output && result.output.length) ? result.output.join('\n') : 'Command executed (no output).';
            this._replaceLastOutput(text, !result.ok);
        } catch (e) {
            // Any failure -- unknown command, permission denial, transport
            // error -- surfaces here verbatim; the console never blocks a
            // command from being attempted in the first place.
            this._replaceLastOutput(e.message || 'Command failed.', true);
        }
    }

    _appendOutput(cmdLine, initialText) {
        const line = document.createElement('div');
        line.className = 'cmd-line';
        line.textContent = cmdLine;
        const out = document.createElement('div');
        out.className = 'cmd-output';
        out.textContent = initialText;
        this._output.appendChild(line);
        this._output.appendChild(out);
        this._lastOutputEl = out;
        this._output.scrollTop = this._output.scrollHeight;
    }

    _replaceLastOutput(text, isError) {
        if (!this._lastOutputEl) return;
        this._lastOutputEl.textContent = text;
        this._lastOutputEl.classList.toggle('cmd-error', !!isError);
        this._output.scrollTop = this._output.scrollHeight;
    }

    // --- OOC / IC monitors ----------------------------------------------

    async _toggleMonitor(kind, enabled) {
        const activeKey = kind === 'ooc' ? '_oocMonitorActive' : '_icMonitorActive';
        const cb = kind === 'ooc' ? this._oocMonitorCb : this._icMonitorCb;
        try {
            const data = await this.api.setMonitor(kind, enabled);
            this[activeKey] = !!data.monitoring;
            if (data.monitoring) {
                this._appendMonitorLine(
                    `[MONITOR] ${kind.toUpperCase()} monitoring enabled for ${data.area_name || '?'} (A${data.area_id})`, 'sys');
            } else {
                this._appendMonitorLine(`[MONITOR] ${kind.toUpperCase()} monitoring disabled`, 'sys');
            }
        } catch (e) {
            if (cb) cb.checked = false;
            this[activeKey] = false;
            this._appendMonitorLine(`[MONITOR] Failed to toggle ${kind.toUpperCase()} monitor: ${e.message}`, 'error');
        }
    }

    _onMonitorFrame(kind, data) {
        const active = kind === 'ooc' ? this._oocMonitorActive : this._icMonitorActive;
        if (!active) return;
        const where = `[A${data.area_id || '?'}]`;
        if (kind === 'ooc') {
            this._appendMonitorLine(`${where} ${data.name || '?'}: ${data.msg || ''}`, 'ooc');
        } else {
            const name = data.showname || data.char_name || `CID:${data.client_id === undefined ? '?' : data.client_id}`;
            const charPart = (data.showname && data.char_name && data.showname !== data.char_name)
                ? ` (${data.char_name})` : '';
            this._appendMonitorLine(`${where} ${name}${charPart}: ${data.text || ''}`, 'ic');
        }
    }

    _appendMonitorLine(msg, cls) {
        const line = document.createElement('div');
        line.className = 'cmd-line' + (cls === 'ooc' ? ' ooc-line' : cls === 'ic' ? ' ic-line' : cls === 'sys' ? ' sys-line' : ' cmd-error');
        line.textContent = msg;
        this._output.appendChild(line);
        this._output.scrollTop = this._output.scrollHeight;
    }

    /** The cookbook head/search/groups is new markup this tab owns entirely
     * (built at runtime, see _renderCatalog); its styling is scoped here
     * rather than in gm.css so this file stays self-contained. Injected
     * once per page load, guarded by id so re-construction never doubles
     * the <style> tag up. */
    _injectStyles() {
        if (document.getElementById('gm-commands-tab-styles')) return;
        const style = document.createElement('style');
        style.id = 'gm-commands-tab-styles';
        style.textContent = `
            .gm-command-console-head { display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap; }
            .gm-command-console-head h3 { margin: 0; margin-right: auto; }
            .gm-command-scope { display: inline-flex; align-items: center; gap: 0.4rem; font-size: 0.8rem; color: var(--gm-text-dim); flex-wrap: wrap; }
            .gm-command-monitor { display: inline-flex; align-items: center; gap: 0.3rem; font-size: 0.78rem; color: var(--gm-text-dim); cursor: pointer; user-select: none; }
            .gm-command-monitor input { cursor: pointer; }
            .gm-output .cmd-line.ooc-line { color: #8fc7ff; }
            .gm-output .cmd-line.ic-line { color: #ffd98f; }
            .gm-output .cmd-line.sys-line { color: var(--gm-accent2); }
            .gm-command-cookbook-head { display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap; }
            .gm-command-cookbook-head h3 { margin: 0; margin-right: auto; }
            .gm-cookbook-search { flex: 1 1 12rem; min-width: 8rem; }
            .gm-cookbook-collapse-btns { display: flex; gap: 0.35rem; flex-wrap: nowrap; }
            .gm-cookbook-btn { white-space: nowrap; }
            .gm-docs-link { white-space: nowrap; }
            .gm-cookbook-hint { margin: 0.25rem 0 0.5rem; }
            .gm-command-cookbook-groups { display: flex; flex-direction: column; gap: 0.5rem; overflow-y: auto; }

            .gm-command-group {
                border: 1px solid var(--gm-border); border-radius: 6px; background: var(--gm-panel-alt);
            }
            .gm-command-group-summary {
                cursor: pointer; list-style: none; padding: 0.4rem 0.6rem; font-weight: 600;
                font-size: 0.85rem; color: var(--gm-accent2); text-transform: uppercase; letter-spacing: 0.03em;
                display: flex; align-items: center; gap: 0.5rem; user-select: none;
            }
            .gm-command-group-summary::-webkit-details-marker { display: none; }
            .gm-command-group-summary::before {
                content: '▸'; display: inline-block; transition: transform 0.12s ease; font-size: 0.7rem;
            }
            .gm-command-group[open] > .gm-command-group-summary::before { transform: rotate(90deg); }
            .gm-command-group-count {
                margin-left: auto; font-weight: 400; text-transform: none; letter-spacing: 0;
                color: var(--gm-text-dim); font-size: 0.75rem;
            }
            .gm-command-group-list {
                display: flex; flex-direction: column; gap: 0.4rem; padding: 0 0.6rem 0.6rem;
            }

            .gm-command-cookbook-card { cursor: pointer; }
            .gm-command-cookbook-card:hover, .gm-command-cookbook-card:focus-visible { filter: brightness(1.08); outline: none; }
            .gm-command-name { font-family: var(--gm-mono, monospace); font-weight: 600; color: var(--gm-text); }
            .gm-command-summary { font-size: 0.8rem; color: var(--gm-text-dim); margin-top: 0.15rem; }
            .gm-command-usage {
                font-family: var(--gm-mono, monospace); font-size: 0.72rem; color: var(--gm-accent2);
                margin-top: 0.2rem; white-space: pre-wrap; word-break: break-word;
            }
        `;
        document.head.appendChild(style);
    }
}
