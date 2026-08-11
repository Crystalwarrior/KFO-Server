/**
 * gm-commands-tab.js
 * CommandsTab: a free-form command console (any "/cmd args" -- leading
 * slash optional -- runs via the run endpoint) plus a searchable COOKBOOK
 * rendered from the server's GMCommandCatalog. The catalog is a curation
 * aid only: clicking an entry prefills the console input, it never blocks
 * or gates anything. Real authorization happens server-side on every run,
 * so a permission-denied or unknown command just shows up as an error
 * line in the console, same as typing it in-game would.
 */

/** Fallback used only if the catalog response omits docs_url. */
const GM_COMMANDS_DOCS_URL = 'https://github.com/Crystalwarrior/KFO-Server/blob/master/docs/commands.md';

class CommandsTab extends TabBase {
    constructor(shell, api, root) {
        super(shell, api, root);

        this._catalog = [];
        this._docsUrl = GM_COMMANDS_DOCS_URL;
        this._searchQuery = '';
        this._lastOutputEl = null;
        this._catalogListEl = null;

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
        if (!this._catalog.length) await this._loadCatalog();
    }

    async _loadCatalog() {
        try {
            const data = await this.api.getCommandCatalog();
            this._catalog = data.commands || [];
            this._docsUrl = data.docs_url || GM_COMMANDS_DOCS_URL;
            this._renderCatalog();
        } catch (e) {
            this._catalogEl.innerHTML = `<div class="gm-empty">Failed to load command catalog: ${esc(e.message)}</div>`;
        }
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
            <div class="gm-command-cookbook-list" id="commandsCatalogList"></div>`;

        this._catalogListEl = this._catalogEl.querySelector('#commandsCatalogList');
        const searchInput = this._catalogEl.querySelector('#commandsCatalogSearch');
        searchInput.value = this._searchQuery;
        searchInput.addEventListener('input', () => {
            this._searchQuery = searchInput.value;
            this._renderCatalogList();
        });
        this._catalogListEl.addEventListener('click', (e) => this._onCatalogClick(e));
        this._catalogListEl.addEventListener('keydown', (e) => {
            if (e.key !== 'Enter' && e.key !== ' ') return;
            const card = e.target.closest('.gm-command-cookbook-card');
            if (!card) return;
            e.preventDefault();
            this._prefillFromCatalog(card.dataset.cmd);
        });

        this._renderCatalogList();
    }

    _renderCatalogList() {
        if (!this._catalogListEl) return;
        if (!this._catalog.length) {
            this._catalogListEl.innerHTML = '<div class="gm-empty">No commands available to your GM scope.</div>';
            return;
        }
        const q = this._searchQuery.trim().toLowerCase();
        const filtered = !q ? this._catalog : this._catalog.filter((c) =>
            (c.name || '').toLowerCase().includes(q) ||
            (c.usage || '').toLowerCase().includes(q) ||
            (c.description || '').toLowerCase().includes(q));
        this._catalogListEl.innerHTML = filtered.length
            ? filtered.map((c) => this._cardHtml(c)).join('')
            : '<div class="gm-empty">No commands match your search.</div>';
    }

    _cardHtml(c) {
        return `<div class="gm-command-card gm-command-cookbook-card${c.destructive ? ' destructive' : ''}"
                     data-cmd="${esc(c.name)}" tabindex="0" role="button"
                     title="Click to prefill the console with this command">
            <div class="gm-command-usage">${esc(c.usage || '/' + c.name)}</div>
            <div class="gm-command-desc">${esc(c.description || '')}</div>
        </div>`;
    }

    _onCatalogClick(e) {
        const card = e.target.closest('.gm-command-cookbook-card');
        if (!card) return;
        this._prefillFromCatalog(card.dataset.cmd);
    }

    /** Prefills (never runs) the console input from a cookbook entry, so
     * the GM can fill in real argument values before hitting Run/Enter. */
    _prefillFromCatalog(name) {
        const entry = this._catalog.find((c) => c.name === name);
        const usage = (entry && entry.usage) || `/${name}`;
        this._rawInput.value = usage.startsWith('/') ? usage : `/${usage}`;
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

    /** The cookbook head/search/list is new markup this tab owns entirely
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
            .gm-command-cookbook-list { display: flex; flex-direction: column; gap: 0.4rem; overflow-y: auto; }
            .gm-command-cookbook-card { cursor: pointer; }
            .gm-command-cookbook-card:hover, .gm-command-cookbook-card:focus-visible { filter: brightness(1.08); outline: none; }
        `;
        document.head.appendChild(style);
    }
}
