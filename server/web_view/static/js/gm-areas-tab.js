/**
 * gm-areas-tab.js
 * AreasGraphTab: hub/area graph view. Owns a GraphRenderer for the SVG
 * itself and layers a click-to-open roster/background popover and the
 * WS-driven movement animation on top of it.
 */

class AreasGraphTab extends TabBase {
    constructor(shell, api, root) {
        super(shell, api, root);
        this.backgroundEvents = true;

        this._hubData = null;
        this._thumbBaseUrl = '';
        this._popoverAreaId = null;

        this._svg = root.querySelector('#areaGraph');
        this._popover = root.querySelector('#areaPopover');
        this._hubLabel = root.querySelector('#areasHubLabel');

        this._renderer = new GraphRenderer(this._svg, {
            onNodeClick: (areaId) => this._openPopover(areaId),
        });

        root.querySelector('#areasRefreshBtn').addEventListener('click', () => this.reload());
        document.addEventListener('click', (e) => {
            if (this._popoverAreaId === null) return;
            if (this._popover.contains(e.target) || this._svg.contains(e.target)) return;
            this._closePopover();
        });
    }

    async activate() {
        super.activate();
        await this._loadThumbBaseUrl();
        await this.reload();
    }

    deactivate() {
        super.deactivate();
        this._closePopover();
    }

    async _loadThumbBaseUrl() {
        if (this._thumbBaseUrl) return;
        try {
            const data = await this.api.getBackgroundThumbBaseUrl();
            this._thumbBaseUrl = data.base_url || '';
            this._renderer.setThumbBaseUrl(this._thumbBaseUrl);
        } catch (e) {
            // Placeholder tiles are the safe default; nothing to do here.
        }
    }

    async reload() {
        try {
            const data = await this.api.getAreas();
            this._hubData = data;
            this._hubLabel.textContent = `Hub ${data.hub_id}: ${data.hub_name}`;
            this._renderer.setData(data);
            if (this._popoverAreaId !== null) this._refreshPopoverContent();
        } catch (e) {
            this.shell.toast('Failed to load areas: ' + e.message, 'error');
        }
    }

    onEvent(msg) {
        switch (msg.type) {
            case 'client_moved':
                this._onClientMoved(msg.data);
                break;
            case 'client_present':
                this.reload().then(() => this._renderer.flashNode(msg.data.area_id, 'gr-flash-join'));
                break;
            case 'client_absent':
            case 'client_disconnected':
            case 'hub_gm_roster_changed':
            case 'area_cm_roster_changed':
            case 'background_changed':
                this.reload();
                break;
            default:
                break;
        }
    }

    _onClientMoved(data) {
        if (!this._hubData) { this.reload(); return; }
        const inScopeFrom = data.from_hub_id === this._hubData.hub_id &&
            this._hubData.areas.some((a) => a.id === data.from_area_id);
        const inScopeTo = data.to_hub_id === this._hubData.hub_id &&
            this._hubData.areas.some((a) => a.id === data.to_area_id);
        if (!inScopeFrom && !inScopeTo) {
            this.reload();
            return;
        }
        this._renderer.animateMovement(
            data.client_id,
            inScopeFrom ? data.from_area_id : null,
            inScopeTo ? data.to_area_id : null,
            `#${data.client_id}`,
        );
        // Give the ~620ms token animation a moment to play before the
        // occupancy chips/counts snap to their new, authoritative state.
        setTimeout(() => this.reload(), 680);
    }

    _openPopover(areaId) {
        this._popoverAreaId = areaId;
        this._refreshPopoverContent();
        this._popover.classList.remove('hidden');
    }

    _closePopover() {
        this._popoverAreaId = null;
        this._popover.classList.add('hidden');
    }

    _refreshPopoverContent() {
        if (!this._hubData || this._popoverAreaId === null) return;
        const area = (this._hubData.areas || []).find((a) => a.id === this._popoverAreaId);
        if (!area) { this._closePopover(); return; }

        const clientIds = area.client_ids || [];
        const roster = clientIds.length
            ? clientIds.map((id) => {
                const isGm = (area.gm_client_ids || []).includes(id);
                const isCm = (area.cm_client_ids || []).includes(id);
                const badges = `${isGm ? ' <span class="badge gm">GM</span>' : ''}${isCm ? ' <span class="badge cm">CM</span>' : ''}`;
                return `<li>Client #${id}${badges}</li>`;
            }).join('')
            : '<li class="dim">Nobody here.</li>';

        this._popover.innerHTML = `
            <div class="area-popover-title">Area ${area.id}: ${esc(area.name)}</div>
            <div class="area-popover-sub">${area.locked ? 'LOCKED · ' : ''}${area.dark ? 'DARK · ' : ''}${esc(area.status || '')}</div>
            <ul class="area-popover-roster">${roster}</ul>
            <div class="area-popover-bg">
                <label>Background (this area only)</label>
                <div class="gm-inline-form">
                    <input type="text" id="popoverBgInput" value="${esc(area.background || '')}" placeholder="background name">
                    <input type="text" id="popoverOverlayInput" value="${esc(area.overlay || '')}" placeholder="overlay">
                </div>
                <button class="btn-sm" id="popoverBgSetBtn" style="margin-top:0.35rem;width:100%">Set Background</button>
            </div>
            <button class="btn-sm area-popover-close" id="popoverCloseBtn">Close</button>
        `;
        this._popover.querySelector('#popoverCloseBtn').addEventListener('click', () => this._closePopover());
        this._popover.querySelector('#popoverBgSetBtn').addEventListener('click', () => this._setBackground(area.id));
    }

    async _setBackground(areaId) {
        const bg = this._popover.querySelector('#popoverBgInput').value.trim();
        const overlay = this._popover.querySelector('#popoverOverlayInput').value.trim();
        if (!bg) { this.shell.toast('Background name is required.', 'error'); return; }
        try {
            const result = await this.api.setAreaBackground(areaId, bg, overlay);
            this.shell.toast((result.output || []).join(' ') || 'Background updated.', result.ok ? 'success' : 'error');
            await this.reload();
        } catch (e) {
            this.shell.toast('Failed to set background: ' + e.message, 'error');
        }
    }
}
