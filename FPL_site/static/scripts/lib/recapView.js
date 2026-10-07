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

// A row of big-number tiles: [{ value, label }]. The verdict and reason come
// first and stay free of digits; the tiles then show the figures behind them,
// as part of the card rather than tucked away in an expander.
export function statTiles(tiles) {
    const cells = tiles
        .filter(t => t.value !== null && t.value !== undefined && t.value !== '')
        .map(t => `<div class="stat-tile${t.highlight ? ' stat-tile--highlight' : ''}">`
            + `<span class="stat-tile-value">${escapeHtml(t.value)}</span>`
            + `<span class="stat-tile-label">${escapeHtml(t.label)}</span></div>`)
        .join('');
    return cells ? `<div class="stat-tiles">${cells}</div>` : '';
}

export function renderGuestRecap(guest, gameweek) {
    // Template literal: the backticks let us write HTML across several lines
    // and drop values in with ${...}. Every value goes through escapeHtml.
    const tiles = statTiles([
        { value: guest.average_score, label: 'Average points' },
        { value: guest.highest_score, label: 'Highest points' },
    ]);
    const standouts = guest.standouts && guest.standouts.length
        ? `<div class="recap-section-title">Standout players</div>
            <ul class="recap-standouts">${guest.standouts.map(standoutRow).join('')}</ul>`
        : '';
    return `
        <div class="card" id="guest-recap">
            <div class="eyebrow-sm">gameweek ${escapeHtml(gameweek)}, for everyone</div>
            <h3 class="recap-verdict">${escapeHtml(guest.headline)}</h3>
            <p>${escapeHtml(guest.reason)}</p>
            ${tiles}
            ${standouts}
        </div>`;
}

export function renderMessage(message) {
    return `
        <div class="card">
            <h3 class="recap-verdict">${escapeHtml(message.title)}</h3>
            <p class="sub">${escapeHtml(message.body)}</p>
        </div>`;
}

// Asks for the team number, explained in plain words. Shown to guests and
// after a "not found", so the user is never stuck.
export function renderTeamPrompt() {
    return `
        <div class="card" id="recap-team-card">
            <h3 class="recap-verdict">See how your team did</h3>
            <form id="recap-team-form" class="recap-team-form" novalidate>
                <label for="recap-team-input" class="sub">
                    Your team number is in the web address of your Fantasy Premier League team page,
                    after "/entry/".
                </label>
                <div class="recap-team-row">
                    <input type="text" inputmode="numeric" pattern="[0-9]*" id="recap-team-input"
                           placeholder="e.g. 1234567" required>
                    <button type="submit" class="btn-pill">Show my recap</button>
                </div>
            </form>
        </div>`;
}

export function renderPersonalRecap(personal, gameweek) {
    // Anything other than "ok" (for example team_not_found) shows the server's
    // friendly message and lets the user try another number.
    // When the official site can't be reached the number may well be right,
    // so show the calm message alone and don't invite a change.
    if (personal.status === 'unavailable') {
        return renderMessage(personal.message);
    }
    if (personal.status !== 'ok') {
        return renderMessage(personal.message) + renderTeamPrompt();
    }
    const call = personal.right_call;
    // The right call and its points read as one line: "Captain call: Haaland delivered."
    // followed by a small tag with the points, when the server sent them.
    const callPoints = call && call.points != null && call.name
        ? ` <span class="recap-call-points">${escapeHtml(call.name)}: ${escapeHtml(call.points)} points</span>`
        : '';
    const callLine = call
        ? `<p class="recap-call"><strong>${escapeHtml(call.title)}:</strong> ${escapeHtml(call.reason)}${callPoints}</p>`
        : '';
    // Your score is highlighted; the average sits beside it for comparison.
    const tiles = statTiles([
        { value: personal.score, label: 'Your points', highlight: true },
        { value: personal.average_score, label: 'Average points' },
    ]);
    return `
        <div class="card" id="personal-recap">
            <div class="eyebrow-sm">your gameweek ${escapeHtml(gameweek)}</div>
            <h3 class="recap-verdict">${escapeHtml(personal.verdict)}</h3>
            ${callLine}
            ${tiles}
            <button type="button" class="btn-pill secondary" id="recap-change-team">Not your team? Change it</button>
        </div>`;
}

// The loading placeholder for the guest recap, same markup as the template's first paint.
export function renderRecapSkeleton() {
    return `
        <div class="card" aria-busy="true" aria-label="Loading last week's recap">
            <div class="skeleton" style="height:18px; width:60%; margin-bottom:10px;"></div>
            <div class="skeleton" style="height:14px; width:90%;"></div>
        </div>`;
}
