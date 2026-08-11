/**
 * gm-shell.js
 * GMPanelShell is the app shell: it holds the tab instances in a Map,
 * tracks which one is active, renders the nav bar/toast banner, and
 * routes WebSocket events to the active tab's onEvent(msg) (and to any
 * background tab that opted into live updates). It never inspects a
 * tab's internals -- only the TabBase interface.
 */

class GMPanelShell {
    constructor(api, root) {
        this.api = api;
        this.root = root;
        this.tabs = new Map();
        this.activeTabName = null;
        this.gmIdentity = null;

        this._navEl = root.querySelector('#tabBar');
        this._toastContainer = root.querySelector('#toastContainer');
        this._identityEl = root.querySelector('#gmIdentity');
        this._wsDot = root.querySelector('#wsDot');
        this._wsStatus = root.querySelector('#wsStatus');

        this._bindNav();
        root.querySelector('#logoutBtn').addEventListener('click', () => this.logout());

        this.api.onUnauthorized(() => this._onUnauthorized());
        this.api.on('_open', () => this._setWsStatus(true));
        this.api.on('_close', () => this._setWsStatus(false));
        this.api.on('_error', () => this._setWsStatus(false));
        this.api.on('*', (msg) => this._handleWsMessage(msg));
    }

    /** @param {string} name @param {TabBase} tabInstance */
    registerTab(name, tabInstance) {
        this.tabs.set(name, tabInstance);
    }

    async start() {
        try {
            const session = await this.api.getSession();
            this._setIdentity(session);
        } catch (e) {
            window.location.href = '/';
            return;
        }
        this.api.connectWebSocket();
        this.switchTab('areas');
    }

    _bindNav() {
        this._navEl.querySelectorAll('.gm-tab').forEach((el) => {
            el.addEventListener('click', () => this.switchTab(el.dataset.tab));
        });
    }

    _setIdentity(gm) {
        this.gmIdentity = gm;
        const name = gm.showname || gm.name || `Client ${gm.client_id}`;
        this._identityEl.textContent =
            `${name} — Hub ${gm.hub_id}: ${gm.hub_name} — Area ${gm.area_id}${gm.is_mod ? ' — MOD' : ' — GM'}`;
    }

    switchTab(name) {
        if (!this.tabs.has(name) || this.activeTabName === name) return;
        if (this.activeTabName && this.tabs.has(this.activeTabName)) {
            this.tabs.get(this.activeTabName).deactivate();
        }
        this.activeTabName = name;
        this._navEl.querySelectorAll('.gm-tab').forEach((el) => {
            el.classList.toggle('active', el.dataset.tab === name);
        });
        this.root.querySelectorAll('.gm-tab-panel').forEach((el) => {
            el.classList.toggle('active', el.id === `tab-${name}`);
        });
        this.tabs.get(name).activate();
    }

    toast(message, kind) {
        const el = document.createElement('div');
        el.className = `gm-toast gm-toast-${kind || 'info'}`;
        el.textContent = message;
        this._toastContainer.appendChild(el);
        requestAnimationFrame(() => el.classList.add('visible'));
        setTimeout(() => {
            el.classList.remove('visible');
            setTimeout(() => { if (el.parentNode) el.parentNode.removeChild(el); }, 300);
        }, 4200);
    }

    _setWsStatus(connected) {
        this._wsDot.classList.toggle('connected', connected);
        this._wsStatus.textContent = connected ? 'Live' : 'Disconnected';
    }

    _onUnauthorized() {
        this.toast('Your GM session is no longer valid. Redirecting to sign in…', 'error');
        this.api.disconnectWebSocket();
        setTimeout(() => { window.location.href = '/'; }, 1200);
    }

    _handleWsMessage(msg) {
        if (msg.type === 'pong') return;

        if (msg.type === 'session_ended') {
            this.toast(`Session ended: ${msg.data.reason || 'unknown reason'}`, 'error');
            this.api.disconnectWebSocket();
            setTimeout(() => { window.location.href = '/'; }, 1500);
            return;
        }

        if (msg.type === 'hub_switched') {
            this.toast(`Your hub changed to ${msg.data.new_hub_name}. Reloading panel state…`, 'info');
            if (this.gmIdentity) this.gmIdentity.hub_id = msg.data.new_hub_id;
            this._reloadAllTabs();
            return;
        }

        if (msg.type === 'hello') {
            // Server-confirmed identity; nothing to render, just keep it fresh.
            if (this.gmIdentity) Object.assign(this.gmIdentity, msg.data);
            return;
        }

        const active = this.activeTabName ? this.tabs.get(this.activeTabName) : null;
        if (active) active.onEvent(msg);
        this.tabs.forEach((tab, name) => {
            if (name !== this.activeTabName && tab.backgroundEvents) tab.onEvent(msg);
        });
    }

    _reloadAllTabs() {
        const name = this.activeTabName;
        if (name && this.tabs.has(name)) {
            this.tabs.get(name).deactivate();
            this.activeTabName = null;
            this.switchTab(name);
        }
    }

    async logout() {
        try { await this.api.logout(); } catch (e) { /* proceed to redirect regardless */ }
        this.api.disconnectWebSocket();
        window.location.href = '/';
    }
}
