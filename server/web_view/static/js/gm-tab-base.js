/**
 * gm-tab-base.js
 * TabBase is the one sanctioned inheritance hierarchy in the frontend:
 * a genuine is-a relationship between the shell's five tabs. GMPanelShell
 * calls activate()/deactivate()/onEvent(msg) polymorphically without
 * knowing which concrete tab it's talking to.
 */

class TabBase {
    /**
     * @param {GMPanelShell} shell
     * @param {ApiClient} api
     * @param {HTMLElement} root - this tab's <section> container
     */
    constructor(shell, api, root) {
        this.shell = shell;
        this.api = api;
        this.root = root;
        this._active = false;
        // When true, the shell also delivers WS events to this tab while
        // it's in the background (not just while active). Subclasses that
        // want their state to stay fresh across tab switches opt in.
        this.backgroundEvents = false;
    }

    get isActive() { return this._active; }

    /** Called by the shell when this tab becomes the visible one. */
    activate() { this._active = true; }

    /** Called by the shell when another tab becomes visible. */
    deactivate() { this._active = false; }

    /** Called by the shell for every WS push event this tab should see. */
    onEvent(msg) { /* no-op by default */ }
}
