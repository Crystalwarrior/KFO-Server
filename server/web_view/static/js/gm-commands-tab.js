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

        this._catalogEl = root.querySelector('#commandCatalog');
        this._output = root.querySelector('#commandsOutput');
        this._rawInput = root.querySelector('#commandsRawInput');
        // The static template's placeholder pre-dates the free-form runner;
        // refresh it at runtime rather than editing the template.
        this._rawInput.placeholder = '/cmd args  (any command -- the leading / is optional; the server enforces permissions)';

        root.querySelector('#commandsRunBtn').addEventListener('click', () => this._runRaw());
        this._rawInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') { e.preventDefault(); this._runRaw(); }
        });

        this._injectStyles();
    }

    async activate() {
        super.activate();
        if (!this._groups.length) await this._loadCatalog();
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
            .gm-command-cookbook-head { display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap; }
            .gm-command-cookbook-head h3 { margin: 0; margin-right: auto; }
            .gm-cookbook-search { flex: 1 1 12rem; min-width: 8rem; }
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
