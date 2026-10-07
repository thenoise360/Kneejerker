/***** momentumView.js *****/
// Pure functions that turn player momentum into HTML strings. No DOM access
// here, so they can be tested in Node. radar.js puts them in the player sheet.
import { escapeHtml } from './escapeHtml.js';
import { renderMessage } from './recapView.js';

// Every card in the player sheet carousel is wrapped like this, so the
// slides line up and the layout holds on a narrow phone.
function slide(inner) {
    return `<div class="mini-card mini-slide">${inner}</div>`;
}

// One row per signal. The arrow is decoration (hidden from screen readers),
// and the word beside it carries the meaning, so colour is never the only clue.
function signalRow(signal) {
    // Only draw the small explanation line if the server sent one.
    const reason = signal.reason ? `<div class="sub">${escapeHtml(signal.reason)}</div>` : '';
    return `<li><span aria-hidden="true">${escapeHtml(signal.arrow)}</span> `
        + `${escapeHtml(signal.name)}: ${escapeHtml(signal.word)}${reason}</li>`;
}

export function renderMomentumCard(payload) {
    // Anything that is not "ready" carries its own calm message.
    if (payload.status !== 'ready') {
        return slide(renderMessage(payload.message));
    }
    const signals = payload.signals || [];
    return slide(`
        <div class="mc-title">Momentum</div>
        <h3 class="recap-verdict">${escapeHtml(payload.label)}</h3>
        <p>${escapeHtml(payload.reason)}</p>
        <details>
            <summary>See each signal</summary>
            <ul class="recap-standouts">${signals.map(signalRow).join('')}</ul>
        </details>`);
}

// A single line for a list of players. Used by the Discover strip.
export function renderStripItem(item) {
    return `<li><strong>${escapeHtml(item.name)}</strong> `
        + `<span class="sub">${escapeHtml(item.team)}: ${escapeHtml(item.reason)}</span></li>`;
}
