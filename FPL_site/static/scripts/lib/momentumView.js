/***** momentumView.js *****/
// Pure functions that turn player momentum into HTML strings. No DOM access
// here, so they can be tested in Node. radar.js puts them in the player sheet.
import { escapeHtml } from './escapeHtml.js';
import { renderGauge } from './gauge.js';

// Every card in the player sheet carousel is wrapped like this, so the
// slides line up and the layout holds on a narrow phone.
function slide(inner) {
    return `<div class="mini-card mini-slide">${inner}</div>`;
}

// One row per signal. The arrow is decoration (hidden from screen readers),
// and the word beside it carries the meaning, so colour is never the only clue.
function signalRow(signal) {
    // Only draw the small explanation line if the server sent one.
    const reason = signal.reason ? `<div class="mc-caption">${escapeHtml(signal.reason)}</div>` : '';
    return `<li class="momentum-signal"><span aria-hidden="true">${escapeHtml(signal.arrow)}</span> `
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

// The three zones of the gauge. The needle sits at the middle of the zone the
// label names. It is never placed from a score (the score stays on the server).
const ZONES = [
    { from: 0, to: 1, label: 'Cooling' },
    { from: 1, to: 2, label: 'Steady' },
    { from: 2, to: 3, label: 'Rising' },
];

function zoneGauge(label) {
    const index = ZONES.findIndex(zone => zone.label === label);
    if (index === -1) return '';
    return `<div class="momentum-gauge">${renderGauge({
        value: index + 0.5, min: 0, max: 3, zones: ZONES,
        leftLabel: 'Cooling', rightLabel: 'Rising', centreLabel: label,
        ariaLabel: `Momentum: ${label.toLowerCase()}`,
    })}</div>`;
}

export function renderMomentumCard(payload) {
    // Anything that is not "ready" carries its own calm message, in the same slide style.
    if (payload.status !== 'ready') {
        return slide(`
        <div class="mc-title">${escapeHtml(payload.message.title)}</div>
        <div class="mc-caption">${escapeHtml(payload.message.body)}</div>`);
    }
    const signals = payload.signals || [];
    const reason = reasonWithoutLabel(payload.label, payload.reason);
    return slide(`
        <div class="mc-title">Momentum</div>
        ${zoneGauge(payload.label)}
        ${reason ? `<p class="sub">${escapeHtml(reason)}</p>` : ''}
        <ul class="recap-standouts momentum-signals">${signals.map(signalRow).join('')}</ul>
        <div class="mc-caption">Looks at upcoming fixtures and key teammates coming in or out.</div>`);
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
        { label: 'Rising', title: 'Heating up', subtitle: 'Players whose week looks better than last', list: strip?.heating_up },
        { label: 'Cooling', title: 'Cooling off', subtitle: 'Players whose week looks harder than last', list: strip?.cooling_off },
    ];
    return groups
        .filter(group => Array.isArray(group.list) && group.list.length > 0)
        .map(group => ({
            title: group.title,
            subtitle: group.subtitle,
            // The card wants these field names. The position is the short code the server sent.
            players: group.list.map(item => ({
                id: item.id, full_name: item.name, team_name: item.team, position: item.position || '', // The group title already says Heating up or Cooling off, so drop the label from the reason.
                why: reasonWithoutLabel(group.label, item.reason),
            })),
        }));
}
