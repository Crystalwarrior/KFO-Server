/**
 * gm-utils.js
 * Small stateless helper functions shared across the GM panel's tab
 * classes. Deliberately not classes themselves -- there's no instance
 * state here, just pure formatting helpers, so wrapping them in a class
 * would just be ceremony.
 */

/** HTML-escape a value for safe interpolation into innerHTML strings. */
function esc(value) {
    const div = document.createElement('div');
    div.textContent = value === undefined || value === null ? '' : String(value);
    return div.innerHTML;
}

/** Format an arbitrary JSON-safe value (scalar/list/dict) for display. */
function fmtValue(value) {
    if (value === undefined || value === null) return '';
    if (Array.isArray(value)) return value.map(fmtValue).join(' ');
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
}

/** Shorten a string to at most `n` characters, adding an ellipsis. */
function truncateText(s, n) {
    if (!s) return '';
    return s.length > n ? s.slice(0, n - 1) + '…' : s;
}

/**
 * Shared client/occupant label builder (v6 brief, ITEM 2) -- the ONE place
 * that turns a ClientSerializer-shaped record into a human-readable label,
 * so the area inspector's occupant list (gm-areas-tab.js) and the Clients
 * tab's rows (gm-clients-tab.js) describe a given client identically
 * instead of drifting apart. Callers use whichever pieces fit their own
 * layout (see `.html` for the full concatenated form the inspector uses,
 * or the individual `*Html` fields when some parts -- an icon column, a
 * showname column, ... -- already exist elsewhere in that view, e.g. the
 * Clients tab's table).
 *
 * Produces, in order: a mini char icon (an EMPTY placeholder <span> --
 * icon resolution goes through GMLocalContent, which is async and cached
 * per-tab, so this helper stays synchronous/pure; the caller resolves the
 * folder and injects an <img> into the placeholder itself, exactly like
 * the existing per-tab icon-loading routines already do -- the icon is
 * purely optional decoration and must never block the text from
 * rendering), role badges in priority order ("[MOD][GM][CM]", only the
 * ones that apply, from the client's own serialized flags), "[id]",
 * the character folder (iniswapped: "base/iniswap"; not iniswapped: just
 * the base folder), "<pos>" (the client's current position, DROPPED
 * entirely when `opts.dropPos` is true -- the containing area's pos_lock
 * has exactly one entry, so everyone present is necessarily there -- or
 * when the client has no pos at all), and finally ": showname" only when
 * a showname is set. Every dynamic piece is esc()d before it's placed in
 * the returned HTML strings.
 *
 * @param {object} client - a ClientSerializer-shaped record: {id,
 *   char_name, iniswap, showname, pos, is_mod, is_hub_gm, is_area_cm}.
 *   Missing/falsy fields degrade gracefully (e.g. an id-only stub still
 *   produces "[icon][id]" with nothing else).
 * @param {object} [opts]
 * @param {boolean} [opts.dropPos=false] - true when the containing area's
 *   pos_lock has exactly 1 entry (see above).
 * @param {string} [opts.iconSlotClass='gm-label-icon-slot'] - class on the
 *   empty icon placeholder <span>, carrying `data-cid="<id>"` so a caller's
 *   own async icon resolution can find and fill it in later (scope the
 *   query to your own container, e.g. `popover.querySelectorAll(...)`, so
 *   two lists on screen at once never collide over the same id).
 * @returns {{iconHtml: string, badgesHtml: string, idHtml: string,
 *   folderHtml: string, posHtml: string, shownameHtml: string,
 *   html: string}} `html` is the full label in the order documented
 *   above; the rest are its individual (already esc()d/safe) pieces for
 *   callers that only need some of them.
 */
function buildClientLabel(client, opts) {
    opts = opts || {};
    const iconSlotClass = opts.iconSlotClass || 'gm-label-icon-slot';
    const id = (client && client.id !== undefined && client.id !== null) ? client.id : '';

    const iconHtml = `<span class="${esc(iconSlotClass)}" data-cid="${esc(id)}"></span>`;

    let badgesHtml = '';
    if (client) {
        if (client.is_mod) badgesHtml += '[MOD]';
        if (client.is_hub_gm) badgesHtml += '[GM]';
        if (client.is_area_cm) badgesHtml += '[CM]';
    }

    const idHtml = `[${esc(id)}]`;

    const baseFolder = (client && client.char_name) || '';
    const iniswapFolder = (client && client.iniswap) || '';
    const folder = iniswapFolder ? `${baseFolder}/${iniswapFolder}` : baseFolder;
    const folderHtml = folder ? esc(folder) : '';

    const pos = client && client.pos;
    const posHtml = (!opts.dropPos && pos) ? esc(`<${pos}>`) : '';

    const showname = client && client.showname;
    const shownameHtml = showname ? esc(showname) : '';

    const html = `${iconHtml}${badgesHtml}${idHtml}` +
        (folderHtml ? ` ${folderHtml}` : '') +
        (posHtml ? ` ${posHtml}` : '') +
        (shownameHtml ? `: ${shownameHtml}` : '');

    return { iconHtml, badgesHtml, idHtml, folderHtml, posHtml, shownameHtml, html };
}
