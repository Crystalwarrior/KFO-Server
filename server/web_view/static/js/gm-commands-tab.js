/**
 * gm-commands-tab.js
 * CommandsTab: renders the server's curated GMCommandCatalog as forms,
 * plus a free-form command box and a scrollback console. The catalog is
 * a UX curation aid only -- real authorization happens server-side on
 * every run, so a rejected/permission-denied command just shows up as
 * an [ERROR] line here, same as typing it in-game would.
 */

class CommandsTab extends TabBase {
    constructor(shell, api, root) {
        super(shell, api, root);

        this._catalog = [];
        this._lastOutputEl = null;

        this._catalogEl = root.querySelector('#commandCatalog');
        this._output = root.querySelector('#commandsOutput');
        this._rawInput = root.querySelector('#commandsRawInput');

        root.querySelector('#commandsRunBtn').addEventListener('click', () => this._runRaw());
        this._rawInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') { e.preventDefault(); this._runRaw(); }
        });
    }

    async activate() {
        super.activate();
        if (!this._catalog.length) await this._loadCatalog();
    }

    async _loadCatalog() {
        try {
            const data = await this.api.getCommandCatalog();
            this._catalog = data.commands || [];
            this._renderCatalog();
        } catch (e) {
            this._catalogEl.innerHTML = `<div class="gm-empty">Failed to load command catalog: ${esc(e.message)}</div>`;
        }
    }

    _renderCatalog() {
        if (!this._catalog.length) {
            this._catalogEl.innerHTML = '<div class="gm-empty">No commands available to your GM scope.</div>';
            return;
        }
        this._catalogEl.innerHTML = '<h3>GM Commands</h3>' + this._catalog.map((c) => this._cardHtml(c)).join('');
        this._catalog.forEach((c) => {
            const form = this._catalogEl.querySelector(`form[data-cmd="${cssEscape(c.name)}"]`);
            if (form) form.addEventListener('submit', (e) => { e.preventDefault(); this._runFromForm(c, form); });
        });
    }

    _cardHtml(c) {
        const inputs = (c.args || []).map((a) => `
            <input type="text" class="gm-cmd-arg" data-arg="${esc(a.name)}"
                   placeholder="${esc(a.name)}${a.optional ? ' (optional)' : ''}" ${a.optional ? '' : 'required'}>
        `).join('');
        return `
            <form class="gm-command-card${c.destructive ? ' destructive' : ''}" data-cmd="${esc(c.name)}">
                <div class="gm-command-usage">${esc(c.usage)}</div>
                <div class="gm-command-desc">${esc(c.description)}</div>
                ${inputs ? `<div class="gm-command-args">${inputs}</div>` : ''}
                <button type="submit" class="btn-sm${c.destructive ? ' danger' : ''}">Run</button>
            </form>`;
    }

    _runFromForm(c, form) {
        const argInputs = Array.from(form.querySelectorAll('.gm-cmd-arg'));
        const parts = [];
        for (const input of argInputs) {
            const val = input.value.trim();
            if (!val && input.hasAttribute('required')) {
                this.shell.toast(`"${input.dataset.arg}" is required.`, 'error');
                return;
            }
            if (val) parts.push(val);
        }
        const arg = parts.join(' ');
        if (c.destructive && !confirm(`Run /${c.name}${arg ? ' ' + arg : ''}? This action is destructive.`)) return;
        this._run(c.name, arg);
    }

    _runRaw() {
        const raw = this._rawInput.value.trim();
        if (!raw) return;
        if (!raw.startsWith('/')) {
            this.shell.toast('Commands must start with /.', 'error');
            return;
        }
        const parts = raw.slice(1).split(/\s+/);
        const cmd = parts[0];
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
            this._replaceLastOutput(e.status === 403 ? 'This command is not in the GM command catalog.' : e.message, true);
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
}

/** Minimal CSS.escape shim for building attribute selectors from command names. */
function cssEscape(s) {
    return String(s).replace(/[^a-zA-Z0-9_-]/g, '\\$&');
}
