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

// The stored reason starts with the label ("Rising: kinder fixtures coming
// up."), but the label is already the heading. Drop that prefix and start
// the sentence with a capital letter, so the card does not say it twice.
function reasonWithoutLabel(label, reason) {
    // A missing reason (null or undefined) means no sentence, not the word "Null".
    if (reason === null || reason === undefined) return '';
    const text = String(reason);
    const prefix = `${label}: `;
    const rest = text.startsWith(prefix) ? text.slice(prefix.length) : text;
    return rest.charAt(0).toUpperCase() + rest.slice(1);
}

export function renderMomentumCard(payload) {
    // Anything that is not "ready" carries its own calm message.
    if (payload.status !== 'ready') {
        return slide(renderMessage(payload.message));
    }
    const signals = payload.signals || [];
    return slide(`
        <div class="mc-title">Momentum</div>
        <h3 class="recap-verdict momentum-verdict">${escapeHtml(payload.label)}</h3>
        <p>${escapeHtml(reasonWithoutLabel(payload.label, payload.reason))}</p>
        <details class="recap-details">
            <summary>See each signal</summary>
            <ul class="recap-standouts">${signals.map(signalRow).join('')}</ul>
        </details>`);
}

// A single line for a list of players. Used by the Discover strip.
export function renderStripItem(item) {
    return `<li><strong>${escapeHtml(item.name)}</strong> `
        + `<span class="sub">${escapeHtml(item.team)}: ${escapeHtml(item.reason)}</span></li>`;
}

// Turns the strip route's answer into the groups Discover draws. Each player
// gets exactly one reason. A group with nobody in it is left out, so an
// empty answer gives an empty list, and the page then hides the whole strip.
export function stripToCategories(strip) {
    const groups = [
        { title: 'Heating up', subtitle: 'Players whose week looks better than last', list: strip?.heating_up },
        { title: 'Cooling off', subtitle: 'Players whose week looks harder than last', list: strip?.cooling_off },
    ];
    return groups
        .filter(group => Array.isArray(group.list) && group.list.length > 0)
        .map(group => ({
            title: group.title,
            subtitle: group.subtitle,
            // The card wants these field names. There is no position here, so it is left blank.
            players: group.list.map(item => ({
                id: item.id, full_name: item.name, team_name: item.team, position: '', why: item.reason,
            })),
        }));
}
