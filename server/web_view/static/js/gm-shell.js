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

        // Single shared instance, constructor-injected into every tab that
        // wants it (Areas/Clients/Evidence) -- no global/singleton access.
        this.localContent = new GMLocalContent(api);

        this._navEl = root.querySelector('#tabBar');
        this._toastContainer = root.querySelector('#toastContainer');
        this._identityEl = root.querySelector('#gmIdentity');
        this._wsDot = root.querySelector('#wsDot');
        this._wsStatus = root.querySelector('#wsStatus');

        this._bindNav();
        root.querySelector('#logoutBtn').addEventListener('click', () => this.logout());

        const localContentBtn = root.querySelector('#localContentBtn');
        const localContentModal = root.querySelector('#localContentModal');
        if (localContentBtn && localContentModal) {
            this._localContentDialog = new LocalContentSettingsDialog(this, this.localContent, localContentModal);
            localContentBtn.addEventListener('click', () => this._localContentDialog.open());
        }

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
            // handle_session_get returns {ok, gm: {...}} -- the GM identity
            // lives under `.gm`, not on the envelope itself.
            this._setIdentity(session.gm);
            if (!session.gm || session.gm.role !== 'admin') this._hideAdminTab();
        } catch (e) {
            // Only bounce back to the sign-in page when the session is genuinely
            // gone (401). Any other failure (500, network hiccup) must NOT
            // redirect, or the panel can enter a fast reload loop.
            if (e && e.status === 401) {
                window.location.href = '/';
            } else {
                this.toast('Failed to load the GM panel: ' + ((e && e.message) || 'unknown error'), 'error');
            }
            return;
        }
        try {
            await this.localContent.init();
        } catch (e) {
            // Local content degrades to plain fallback tiles; never block startup on it.
        }
        this.api.connectWebSocket();
        this.switchTab('areas');
    }

    _bindNav() {
        this._navEl.querySelectorAll('.gm-tab').forEach((el) => {
            el.addEventListener('click', () => this.switchTab(el.dataset.tab));
        });
    }

    /** The Admin tab (log viewer + admin console) is only for admin-role
     * sessions. Hide it for everyone else -- live GMs and remote GMs. */
    _hideAdminTab() {
        const nav = this._navEl.querySelector('.gm-tab[data-tab="admin"]');
        if (nav) nav.remove();
        const panel = this.root.querySelector('#tab-admin');
        if (panel) panel.remove();
        this.tabs.delete('admin');
    }
    _setIdentity(gm) {
        this.gmIdentity = gm || null;
        this._renderIdentity();
    }

    /** Re-render the header identity line from the current `this.gmIdentity`
     * (call after mutating it in place, e.g. from a WS event). */
    _renderIdentity() {
        const gm = this.gmIdentity;
        if (!gm) { this._identityEl.textContent = ''; return; }
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
            if (this.gmIdentity) {
                this.gmIdentity.hub_id = msg.data.new_hub_id;
                this.gmIdentity.hub_name = msg.data.new_hub_name;
                this._renderIdentity();
            }
            this._reloadAllTabs();
            return;
        }

        if (msg.type === 'hello') {
            // Server-confirmed identity (sent once per WS connection): keep
            // the header's hub/area fields fresh even if we reconnected
            // mid-session and missed intervening events.
            if (this.gmIdentity) {
                this.gmIdentity.client_id = msg.data.gm_client_id;
                this.gmIdentity.hub_id = msg.data.hub_id;
                this.gmIdentity.hub_name = msg.data.hub_name;
                this.gmIdentity.area_id = msg.data.area_id;
                this._renderIdentity();
            }
            return;
        }

        if (msg.type === 'client_moved' && this.gmIdentity && msg.data.client_id === this.gmIdentity.client_id) {
            this.gmIdentity.area_id = msg.data.to_area_id;
            this._renderIdentity();
            // fall through: the active/background tabs still want this event.
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
