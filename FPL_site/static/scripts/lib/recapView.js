/***** recapView.js *****/
// Pure functions that turn recap data into HTML strings. No DOM access here,
// so they can be tested in Node. weekV2.js puts the strings on the page.
import { escapeHtml } from './escapeHtml.js';

// Shown if the recap request itself fails (no connection, server down).
export const RECAP_LOAD_FAILED = {
    title: "We couldn't load last week's recap",
    body: 'Nothing is wrong on your side. Try again in a moment.',
};

// "a hat-trick" -> "A hat-trick" (used where a reason starts a line).
function capitalise(text) {
    const s = String(text ?? '');
    return s.charAt(0).toUpperCase() + s.slice(1);
}

function standoutRow(player) {
    return `
        <li class="recap-standout">
            <div class="recap-standout-head">
                <span>${escapeHtml(player.name)} <span class="sub">${escapeHtml(player.team)}</span></span>
                <span class="recap-points">${escapeHtml(player.points)} points</span>
            </div>
            <p class="sub">${escapeHtml(capitalise(player.reason))}</p>
        </li>`;
}

export function renderGuestRecap(guest, gameweek) {
    // Template literal: the backticks let us write HTML across several lines
    // and drop values in with ${...}. Every value goes through escapeHtml.
    const highest = guest.highest_score
        ? ` · Highest score: ${escapeHtml(guest.highest_score)} points`
        : '';
    return `
        <div class="card" id="guest-recap">
            <div class="eyebrow-sm">gameweek ${escapeHtml(gameweek)}, for everyone</div>
            <h3 class="recap-verdict">${escapeHtml(guest.headline)}</h3>
            <p>${escapeHtml(guest.reason)}</p>
            <details class="recap-details">
                <summary>See the numbers</summary>
                <p class="sub">Average score: ${escapeHtml(guest.average_score)} points${highest}</p>
                <ul class="recap-standouts">${guest.standouts.map(standoutRow).join('')}</ul>
            </details>
        </div>`;
}

export function renderMessage(message) {
    return `
        <div class="card">
            <h3 class="recap-verdict">${escapeHtml(message.title)}</h3>
            <p class="sub">${escapeHtml(message.body)}</p>
        </div>`;
}
