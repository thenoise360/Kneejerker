/***** strengthView.js *****/
// Pure functions that turn team strength data into HTML strings. No DOM
// access here, so they can be tested in Node. club.js puts them on the page.
import { escapeHtml } from './escapeHtml.js';
import { renderMessage } from './recapView.js';

// Shown if the strength request itself fails (no connection, server down).
export const STRENGTH_LOAD_FAILED = {
    title: "We couldn't load team strength",
    body: 'Nothing is wrong on your side. Try again in a moment.',
};

// One line per missing player. The chance is a number, so it stays in the expander.
function missingRow(player) {
    return `<li>${escapeHtml(player.name)}: ${escapeHtml(player.chance)}% chance of playing</li>`;
}

// Always show one decimal place, so 1 is written as 1.0 and every figure lines up.
function oneDecimal(value) {
    return Number(value).toFixed(1);
}

export function renderStrength(payload) {
    // Anything that is not "ready" (for example "not_ready") carries its own calm message.
    if (payload.status !== 'ready') {
        return renderMessage(payload.message);
    }
    // Only draw the list of absentees if somebody is actually missing.
    const missingList = payload.missing && payload.missing.length
        ? `<ul class="recap-standouts">${payload.missing.map(missingRow).join('')}</ul>`
        : '';
    // Template literal: backticks let us write HTML across several lines and
    // drop values in with ${...}. Every value goes through escapeHtml.
    return `
        <div class="card" id="team-strength">
            <div class="eyebrow-sm">how strong are they this week</div>
            <h3 class="recap-verdict">${escapeHtml(payload.headline)}</h3>
            <p>${escapeHtml(payload.reason)}</p>
            <details class="recap-details">
                <summary>See the numbers</summary>
                <p class="sub">Goals a game against an average side: ${escapeHtml(oneDecimal(payload.scored))} (${escapeHtml(oneDecimal(payload.scored_adjusted))} with this week's absences)</p>
                <p class="sub">Goals conceded a game against an average side: ${escapeHtml(oneDecimal(payload.conceded))} (${escapeHtml(oneDecimal(payload.conceded_adjusted))} with this week's absences)</p>
                ${missingList}
            </details>
        </div>`;
}

// The loading placeholder, same markup as the template's first paint.
export function renderStrengthSkeleton() {
    return `
        <div class="card" aria-busy="true" aria-label="Loading team strength">
            <div class="skeleton" style="height:18px; width:60%;"></div>
        </div>`;
}
