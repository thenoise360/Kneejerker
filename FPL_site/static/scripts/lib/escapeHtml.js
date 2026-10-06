/***** escapeHtml.js *****/
// Text from the server (like a player's name) is dropped into HTML strings.
// If that text contained characters such as < or &, the browser would read
// them as markup. This swaps each one for its harmless "entity" version, so
// the text always shows exactly as written.
export function escapeHtml(value) {
    return String(value ?? '')              // ?? turns null/undefined into ''
        .replace(/&/g, '&amp;')             // & first, or we'd double-escape the others
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}
