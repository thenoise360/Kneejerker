/***** strengthView.js *****/
// Pure functions that turn team strength data into HTML strings. No DOM
// access here, so they can be tested in Node. club.js puts them on the page.
import { escapeHtml } from './escapeHtml.js';
import { renderMessage } from './recapView.js';
import { renderGauge } from './gauge.js';

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

const GAUGE_MIN = 0.5;
const GAUGE_MAX = 1.5;

// Where each gauge's needle and "usual" tick sit, as a share of the league
// average goals scored. Returns null when the payload cannot support gauges
// (no league average, or no goals conceded to divide by).
export function gaugeInputs(payload) {
    const league = Number(payload.league_scored);
    if (!(league > 0) || !(payload.conceded > 0) || !(payload.conceded_adjusted > 0)) return null;
    return {
        attack: { value: payload.scored_adjusted / league, marker: payload.scored / league, min: GAUGE_MIN, max: GAUGE_MAX },
        // Higher means it concedes less, so a taller needle is always better.
        defence: { value: league / payload.conceded_adjusted, marker: league / payload.conceded, min: GAUGE_MIN, max: GAUGE_MAX },
    };
}

// Words for the aria-label: how this week compares with usual, and with the league.
function gaugeWords(name, input, worse, better) {
    const diff = input.value - input.marker;
    let versusUsual = 'the same as usual';
    if (Math.abs(diff) >= 0.03) {
        const size = Math.abs(diff) < 0.1 ? 'a little ' : '';
        versusUsual = `${size}${diff < 0 ? worse : better} than usual`;
    }
    let versusLeague = 'about average for the league';
    if (input.value < 0.9) versusLeague = 'below average for the league';
    else if (input.value > 1.1) versusLeague = 'above average for the league';
    return `${name}: ${versusUsual}, ${versusLeague}`;
}

function gaugeBlock(input, labels) {
    const svg = renderGauge({
        ...input,
        leftLabel: labels.left, rightLabel: labels.right, centreLabel: labels.centre,
        ariaLabel: gaugeWords(labels.centre, input, labels.left.toLowerCase(), labels.right.toLowerCase()),
    });
    // Each mark is paired with a word, so the legend never relies on colour.
    return `<div class="strength-gauge">${svg}
        <div class="strength-legend"><span><i class="strength-swatch-tick" aria-hidden="true"></i>Usual</span><span><i class="strength-swatch-dot" aria-hidden="true"></i>This week</span></div>
    </div>`;
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
    const inputs = gaugeInputs(payload);
    const gauges = inputs
        ? `<div class="strength-gauges">
            ${gaugeBlock(inputs.attack, { left: 'Weaker', right: 'Stronger', centre: 'Attack' })}
            ${gaugeBlock(inputs.defence, { left: 'Leakier', right: 'Tighter', centre: 'Defence' })}
        </div>`
        : '';
    // Template literal: backticks let us write HTML across several lines and
    // drop values in with ${...}. Every value goes through escapeHtml.
    return `
        <div class="card" id="team-strength">
            <div class="eyebrow-sm">how strong are they this week</div>
            <div class="outlook-phrase strength-verdict">${escapeHtml(payload.headline)}</div>
            <p class="sub">${escapeHtml(payload.reason)}</p>
            ${gauges}
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
