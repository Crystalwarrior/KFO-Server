/**
 * gm-graph.js
 * GraphRenderer is a pure rendering component (composed into
 * AreasGraphTab, not inherited) that draws the hub's area graph as
 * hand-rolled SVG: areas are nodes, area links are directed edges. No
 * external graph library -- layout is a small hand-written
 * Fruchterman-Reingold-style force simulation run once per structural
 * change, and movement is animated by walking a token along the
 * matching edge path (or a straight fallback) with requestAnimationFrame.
 */

const GR_SVG_NS = 'http://www.w3.org/2000/svg';
const GR_XLINK_NS = 'http://www.w3.org/1999/xlink';

function grEl(tag, attrs) {
    const el = document.createElementNS(GR_SVG_NS, tag);
    if (attrs) {
        for (const key in attrs) {
            const value = attrs[key];
            if (value === undefined || value === null) continue;
            el.setAttribute(key, value);
        }
    }
    return el;
}

class GraphRenderer {
    constructor(svgElement, options) {
        this._svg = svgElement;
        this._onNodeClick = (options && options.onNodeClick) || (() => {});
        this._thumbBaseUrl = '';

        this._nodes = new Map();       // area_id -> {area, x, y}
        this._edgePaths = new Map();   // "from->to" -> <path> element
        this._lastIdSet = '';
        this._lastEdgeSig = '';

        this._nodeW = 150;
        this._nodeH = 96;
        this._width = 1000;
        this._height = 640;

        this._svg.innerHTML = '';
        this._buildDefs();
        this._layerEdges = grEl('g', { class: 'gr-edges' });
        this._layerNodes = grEl('g', { class: 'gr-nodes' });
        this._layerTokens = grEl('g', { class: 'gr-tokens' });
        this._svg.appendChild(this._layerEdges);
        this._svg.appendChild(this._layerNodes);
        this._svg.appendChild(this._layerTokens);

        this._measure();
        window.addEventListener('resize', () => this._measure());
    }

    setThumbBaseUrl(url) { this._thumbBaseUrl = url || ''; }

    _measure() {
        const rect = this._svg.getBoundingClientRect();
        if (rect.width > 100) this._width = rect.width;
        if (rect.height > 100) this._height = rect.height;
    }

    _buildDefs() {
        const defs = grEl('defs');
        const marker = grEl('marker', {
            id: 'gr-arrow', viewBox: '0 0 10 10', refX: 9, refY: 5,
            markerWidth: 7, markerHeight: 7, orient: 'auto-start-reverse',
        });
        marker.appendChild(grEl('path', { d: 'M0,0 L10,5 L0,10 z', class: 'gr-arrowhead' }));
        defs.appendChild(marker);
        this._svg.appendChild(defs);
    }

    /**
     * Push a fresh hub snapshot ({hub_id, hub_name, areas}) from
     * GET /api/gm/areas. Node positions are kept stable across
     * occupancy-only updates; layout is only recomputed when the set
     * of area ids or the link topology actually changed.
     */
    setData(hubData) {
        const areas = hubData.areas || [];
        const idSet = areas.map((a) => a.id).sort((a, b) => a - b).join(',');
        const edgeSig = this._edgeSignature(areas);
        const structuralChange = idSet !== this._lastIdSet || edgeSig !== this._lastEdgeSig;
        this._lastIdSet = idSet;
        this._lastEdgeSig = edgeSig;

        const prevPositions = new Map();
        this._nodes.forEach((node, id) => prevPositions.set(id, { x: node.x, y: node.y }));

        this._nodes = new Map();
        areas.forEach((area) => {
            const prev = prevPositions.get(area.id);
            this._nodes.set(area.id, {
                area,
                x: prev ? prev.x : this._width / 2,
                y: prev ? prev.y : this._height / 2,
            });
        });

        if (structuralChange || prevPositions.size === 0) {
            this._runLayout(areas);
        }
        this._render(areas);
    }

    _edgeSignature(areas) {
        const parts = [];
        areas.forEach((a) => {
            (a.links || []).forEach((l) => parts.push(`${a.id}>${l.target_id}:${l.locked ? 1 : 0}:${l.hidden ? 1 : 0}`));
            if (a.fully_connected) parts.push(`${a.id}:*`);
        });
        return parts.sort().join('|');
    }

    /** Small hand-rolled force-directed layout (Fruchterman-Reingold). */
    _runLayout(areas) {
        const nodes = Array.from(this._nodes.values());
        const n = nodes.length;
        if (n === 0) return;
        const w = Math.max(this._width, 300);
        const h = Math.max(this._height, 300);
        const margin = 90;

        if (n === 1) {
            nodes[0].x = w / 2;
            nodes[0].y = h / 2;
            return;
        }

        const idToIdx = new Map();
        nodes.forEach((node, i) => idToIdx.set(node.area.id, i));
        const edges = [];
        areas.forEach((a) => {
            const i = idToIdx.get(a.id);
            (a.links || []).forEach((l) => {
                const j = idToIdx.get(l.target_id);
                if (j !== undefined && j !== i) edges.push([i, j]);
            });
        });

        // Seed on a circle so the simulation starts from a non-degenerate layout.
        nodes.forEach((node, i) => {
            const angle = (i / n) * Math.PI * 2;
            const radius = Math.min(w, h) / 3;
            node.x = w / 2 + Math.cos(angle) * radius;
            node.y = h / 2 + Math.sin(angle) * radius;
        });

        const area = w * h;
        const k = Math.sqrt(area / n) * 0.9;
        let temperature = Math.max(w, h) / 10;
        const iterations = 220;

        for (let iter = 0; iter < iterations; iter++) {
            const disp = nodes.map(() => ({ x: 0, y: 0 }));

            for (let i = 0; i < n; i++) {
                for (let j = i + 1; j < n; j++) {
                    const dx = nodes[i].x - nodes[j].x;
                    const dy = nodes[i].y - nodes[j].y;
                    const dist = Math.sqrt(dx * dx + dy * dy) || 0.01;
                    const force = (k * k) / dist;
                    const fx = (dx / dist) * force;
                    const fy = (dy / dist) * force;
                    disp[i].x += fx; disp[i].y += fy;
                    disp[j].x -= fx; disp[j].y -= fy;
                }
            }

            edges.forEach(([i, j]) => {
                const dx = nodes[i].x - nodes[j].x;
                const dy = nodes[i].y - nodes[j].y;
                const dist = Math.sqrt(dx * dx + dy * dy) || 0.01;
                const force = (dist * dist) / k;
                const fx = (dx / dist) * force;
                const fy = (dy / dist) * force;
                disp[i].x -= fx; disp[i].y -= fy;
                disp[j].x += fx; disp[j].y += fy;
            });

            // "Open hub" (fully_connected) areas: mild pull toward the centroid
            // instead of an O(n^2) explicit edge set.
            let cx = 0, cy = 0;
            nodes.forEach((node) => { cx += node.x; cy += node.y; });
            cx /= n; cy /= n;
            nodes.forEach((node, i) => {
                if (node.area.fully_connected) {
                    disp[i].x += (cx - node.x) * 0.03;
                    disp[i].y += (cy - node.y) * 0.03;
                }
            });

            nodes.forEach((node, i) => {
                const d = disp[i];
                const dist = Math.sqrt(d.x * d.x + d.y * d.y) || 0.01;
                const capped = Math.min(dist, temperature);
                node.x += (d.x / dist) * capped;
                node.y += (d.y / dist) * capped;
                node.x = Math.min(w - margin, Math.max(margin, node.x));
                node.y = Math.min(h - margin, Math.max(margin, node.y));
            });

            temperature *= 0.97;
        }
    }

    _render(areas) {
        this._layerNodes.innerHTML = '';
        this._layerEdges.innerHTML = '';
        this._edgePaths = new Map();

        const w = Math.max(this._width, 300);
        const h = Math.max(this._height, 300);
        this._svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
        this._svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');

        // Faint implicit edges for "open hub" (fully_connected) areas first,
        // drawn once per unordered pair so they don't double up.
        areas.forEach((a) => {
            if (!a.fully_connected) return;
            const from = this._nodes.get(a.id);
            if (!from) return;
            areas.forEach((b) => {
                if (b.id === a.id) return;
                if (a.id > b.id && b.fully_connected) return; // already drawn from the other side
                const to = this._nodes.get(b.id);
                if (!to) return;
                this._layerEdges.appendChild(grEl('line', {
                    x1: from.x, y1: from.y, x2: to.x, y2: to.y, class: 'gr-edge gr-edge-implicit',
                }));
            });
        });

        // Explicit directed links. A mutual pair (A->B and B->A) is drawn as
        // two independent curved arrows so /onelink asymmetry stays visible.
        areas.forEach((a) => {
            const from = this._nodes.get(a.id);
            if (!from) return;
            (a.links || []).forEach((link) => {
                const to = this._nodes.get(link.target_id);
                if (!to) return;
                const reciprocal = this._hasLink(areas, link.target_id, a.id);
                const d = this._edgePathD(from, to, reciprocal);
                const classes = ['gr-edge'];
                if (link.locked) classes.push('gr-edge-locked');
                if (link.hidden) classes.push('gr-edge-hidden');
                const pathEl = grEl('path', {
                    d, class: classes.join(' '), fill: 'none', 'marker-end': 'url(#gr-arrow)',
                });
                this._layerEdges.appendChild(pathEl);
                this._edgePaths.set(`${a.id}->${link.target_id}`, pathEl);
            });
        });

        areas.forEach((a) => {
            const pos = this._nodes.get(a.id);
            if (!pos) return;
            this._layerNodes.appendChild(this._buildNode(a, pos));
        });
    }

    _hasLink(areas, fromId, toId) {
        const a = areas.find((x) => x.id === fromId);
        if (!a) return false;
        return (a.links || []).some((l) => l.target_id === toId);
    }

    _edgePathD(from, to, curve) {
        const dx = to.x - from.x, dy = to.y - from.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const ux = dx / dist, uy = dy / dist;
        const nodeRadius = 58;
        const sx = from.x + ux * nodeRadius, sy = from.y + uy * nodeRadius;
        const ex = to.x - ux * nodeRadius, ey = to.y - uy * nodeRadius;
        if (!curve) return `M ${sx} ${sy} L ${ex} ${ey}`;
        const mx = (sx + ex) / 2, my = (sy + ey) / 2;
        const nx = -uy, ny = ux;
        const bend = 22;
        const cx = mx + nx * bend, cy = my + ny * bend;
        return `M ${sx} ${sy} Q ${cx} ${cy} ${ex} ${ey}`;
    }

    _buildNode(area, pos) {
        const classes = ['gr-node'];
        if (area.locked) classes.push('gr-node-locked');
        if (area.dark) classes.push('gr-node-dark');
        const g = grEl('g', {
            class: classes.join(' '),
            transform: `translate(${pos.x - this._nodeW / 2}, ${pos.y - this._nodeH / 2})`,
            'data-area-id': area.id,
        });

        g.appendChild(grEl('rect', { width: this._nodeW, height: this._nodeH, rx: 10, ry: 10, class: 'gr-node-card' }));

        const clipId = `gr-clip-${area.id}`;
        const clip = grEl('clipPath', { id: clipId });
        clip.appendChild(grEl('rect', { width: this._nodeW, height: 44, rx: 10, ry: 10 }));
        g.appendChild(clip);

        const thumbGroup = grEl('g', { 'clip-path': `url(#${clipId})` });
        const fallback = grEl('rect', { width: this._nodeW, height: 44, class: 'gr-thumb-fallback' });
        thumbGroup.appendChild(fallback);
        if (this._thumbBaseUrl && area.background) {
            const href = `${this._thumbBaseUrl}${encodeURIComponent(area.background)}.png`;
            const img = grEl('image', {
                x: 0, y: 0, width: this._nodeW, height: 44, preserveAspectRatio: 'xMidYMid slice',
            });
            img.setAttributeNS(GR_XLINK_NS, 'href', href);
            img.setAttribute('href', href);
            fallback.style.display = 'none';
            img.addEventListener('error', () => {
                img.style.display = 'none';
                fallback.style.display = '';
            });
            thumbGroup.appendChild(img);
        }
        const bgLabel = grEl('text', { x: this._nodeW / 2, y: 26, 'text-anchor': 'middle', class: 'gr-thumb-label' });
        bgLabel.textContent = area.background || '(no background)';
        thumbGroup.appendChild(bgLabel);
        g.appendChild(thumbGroup);

        const nameText = grEl('text', { x: 8, y: 60, class: 'gr-node-name' });
        nameText.textContent = `${area.id}: ${truncateText(area.name, 20)}`;
        g.appendChild(nameText);

        const statusBits = [];
        if (area.locked) statusBits.push('LOCKED');
        if (area.dark) statusBits.push('DARK');
        if (area.status) statusBits.push(area.status);
        const statusText = grEl('text', { x: 8, y: 73, class: 'gr-node-status' });
        statusText.textContent = statusBits.join(' · ');
        g.appendChild(statusText);

        const countText = grEl('text', { x: this._nodeW - 6, y: 73, 'text-anchor': 'end', class: 'gr-node-count' });
        const ids = area.client_ids || [];
        countText.textContent = `${ids.length} here`;
        g.appendChild(countText);

        const chipsGroup = grEl('g', { transform: 'translate(8, 80)' });
        const maxChips = 8;
        ids.slice(0, maxChips).forEach((cid, i) => {
            const isGm = (area.gm_client_ids || []).includes(cid);
            const isCm = (area.cm_client_ids || []).includes(cid);
            const chipClasses = ['gr-chip'];
            if (isGm) chipClasses.push('gr-chip-gm');
            else if (isCm) chipClasses.push('gr-chip-cm');
            const chip = grEl('circle', { r: 6, cx: i * 15 + 6, cy: 6, class: chipClasses.join(' ') });
            const title = grEl('title');
            title.textContent = `Client #${cid}`;
            chip.appendChild(title);
            chipsGroup.appendChild(chip);
        });
        if (ids.length > maxChips) {
            const more = grEl('text', { x: maxChips * 15 + 8, y: 10, class: 'gr-chip-more' });
            more.textContent = `+${ids.length - maxChips}`;
            chipsGroup.appendChild(more);
        }
        g.appendChild(chipsGroup);

        g.addEventListener('click', () => this._onNodeClick(area.id));
        return g;
    }

    getNodeCenter(areaId) {
        const node = this._nodes.get(areaId);
        return node ? { x: node.x, y: node.y } : null;
    }

    /** Briefly highlight a node's border, e.g. on join/leave. */
    flashNode(areaId, cssClass) {
        const g = this._layerNodes.querySelector(`[data-area-id="${areaId}"]`);
        if (!g) return;
        g.classList.add(cssClass);
        setTimeout(() => g.classList.remove(cssClass), 700);
    }

    /**
     * Animate a token traveling from one area node to another along the
     * matching edge path, falling back to a straight line between node
     * centers when no direct edge/path exists. Always shows *some*
     * movement so the GM can see where a client came from and went, even
     * for teleports or areas outside the current snapshot.
     */
    animateMovement(clientId, fromAreaId, toAreaId, labelText) {
        const from = fromAreaId !== null && fromAreaId !== undefined ? this.getNodeCenter(fromAreaId) : null;
        const to = toAreaId !== null && toAreaId !== undefined ? this.getNodeCenter(toAreaId) : null;
        if (!from && !to) return;
        const start = from || to;
        const end = to || from;

        const token = grEl('g', { class: 'gr-token' });
        token.appendChild(grEl('circle', { r: 9, class: 'gr-token-dot' }));
        const label = grEl('text', { y: -13, 'text-anchor': 'middle', class: 'gr-token-label' });
        label.textContent = labelText !== undefined && labelText !== null ? String(labelText) : `#${clientId}`;
        token.appendChild(label);
        this._layerTokens.appendChild(token);

        const pathEl = (from && to) ? this._edgePaths.get(`${fromAreaId}->${toAreaId}`) : null;
        const duration = 620;
        const startTime = performance.now();

        const step = (now) => {
            const t = Math.min(1, (now - startTime) / duration);
            let x, y;
            if (pathEl) {
                const len = pathEl.getTotalLength();
                const pt = pathEl.getPointAtLength(len * t);
                x = pt.x; y = pt.y;
            } else {
                x = start.x + (end.x - start.x) * t;
                y = start.y + (end.y - start.y) * t;
            }
            token.setAttribute('transform', `translate(${x}, ${y})`);
            if (t < 1) {
                requestAnimationFrame(step);
            } else {
                token.classList.add('gr-token-arrived');
                setTimeout(() => { if (token.parentNode) token.parentNode.removeChild(token); }, 260);
            }
        };
        requestAnimationFrame(step);
    }
}
