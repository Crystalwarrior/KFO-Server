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
