/***** numbers.js *****/
// The server sends some totals as text (for example "13") because the
// database hands back exact decimals. In JavaScript, "0" + "2" is "02", not
// 2, so adding them up naively glues the digits together. These helpers
// turn everything into real numbers first and tidy the result for display.

// Adds up a list of values. Anything that isn't a finite number (null,
// undefined, "abc", NaN) is skipped rather than poisoning the total.
export function sumNumbers(values) {
    if (!Array.isArray(values)) return 0;
    return values.reduce((total, raw) => {
        // Number(null) is 0 and Number('') is 0, which is harmless to add.
        const n = Number(raw);
        return Number.isFinite(n) ? total + n : total;
    }, 0);
}

// Rounds to one decimal place and drops a trailing ".0", so 16.240000000000002
// shows as "16.2" and 15 shows as "15". Missing values show as "0".
export function formatPoints(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return '0';
    return String(Math.round(n * 10) / 10);
}
