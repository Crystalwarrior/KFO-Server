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

/** Insert (once) the stylesheet backing createGmSearchBox() and the
 * shared search-result/layout classes (.gm-search-row-hidden,
 * .gm-search-match, .gm-search-wrap/.gm-search-menu autocomplete). Kept
 * here (not gm.css) because gm.css/gm.html are not this package's to
 * edit -- same convention as the per-tab `_injectStyles()` calls. */
function _injectGmSearchStyles() {
    if (document.getElementById('gm-search-box-styles')) return;
    const style = document.createElement('style');
    style.id = 'gm-search-box-styles';
    style.textContent = `
        .gm-search-box {
            background: var(--gm-panel-alt); color: var(--gm-text); border: 1px solid var(--gm-border);
            border-radius: 4px; padding: 0.32rem 0.55rem; font-size: 0.8rem;
            min-width: 8rem; max-width: 14rem; flex: 0 1 auto;
        }
        .gm-search-box:focus { outline: none; border-color: var(--gm-accent); }
        .gm-search-box::placeholder { color: var(--gm-text-dim); }
        .gm-search-row { margin: 0 0 0.45rem; }
        .gm-search-row-hidden { display: none; }
        .gm-search-match { background: rgba(238, 240, 248, 0.09); box-shadow: inset 0 0 0 1px var(--gm-accent); }
        .gm-search-wrap { position: relative; flex: 0 1 auto; }
        .gm-search-menu {
            position: absolute; top: calc(100% + 4px); left: 0; z-index: 20;
            background: var(--gm-panel); border: 1px solid var(--gm-border); border-radius: 6px;
            max-height: 260px; overflow-y: auto; min-width: 15rem;
            box-shadow: 0 6px 18px rgba(0, 0, 0, 0.4);
        }
        .gm-search-menu.hidden { display: none; }
        .gm-search-item {
            display: block; width: 100%; text-align: left; background: none; border: none;
            color: var(--gm-text); font-size: 0.8rem; padding: 0.4rem 0.6rem; cursor: pointer;
        }
        .gm-search-item:hover { background: rgba(238, 240, 248, 0.08); }
        .gm-search-item .mono { color: var(--gm-text-dim); }
        .gm-search-menu-empty { padding: 0.4rem 0.6rem; font-size: 0.78rem; color: var(--gm-text-dim); }
    `;
    document.head.appendChild(style);
}

/** A compact toolbar search <input> shared across the panel tabs (see
 * gm-data-tab/gm-areas-tab/gm-clients-tab/gm-characters-tab). Fires
 * `onInput(query)` on every keystroke (and on the native clear button,
 * via the 'search' event). The owner decides what a query does -- live
 * row filtering, autocomplete focus, etc. */
function createGmSearchBox(placeholder, onInput) {
    _injectGmSearchStyles();
    const input = document.createElement('input');
    input.type = 'search';
    input.className = 'gm-search-box';
    input.placeholder = placeholder || 'Search…';
    input.autocomplete = 'off';
    input.spellcheck = false;
    input.addEventListener('input', () => onInput(input.value));
    input.addEventListener('search', () => onInput(input.value));
    return input;
}
