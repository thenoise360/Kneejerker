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

// The dial runs from 0.4 to 1.8 times the league average, not 0.5 to 1.5: top
// sides score well over 1.5 times the average, and a narrower range would pin
// their needle and "usual" tick against the end of the scale.
const GAUGE_MIN = 0.4;
const GAUGE_MAX = 1.8;

// Where each gauge's needle and "usual" tick sit, as a share of the league
// average goals scored. The server works these out (unrounded, with the words
// that describe them) so the gauges always agree with the headline. A gauge
// whose figures are missing or not numbers is left out rather than drawn wrong.
function oneGauge(entry) {
    if (!entry || typeof entry.words !== 'string') return null;
    const { now, usual } = entry;
    if (typeof now !== 'number' || typeof usual !== 'number' || !Number.isFinite(now) || !Number.isFinite(usual)) return null;
    return { value: now, marker: usual, min: GAUGE_MIN, max: GAUGE_MAX, words: entry.words };
}

export function gaugeInputs(payload) {
    const gauge = payload.gauge;
    if (!gauge) return null;
    const attack = oneGauge(gauge.attack);
    const defence = oneGauge(gauge.defence);
    return attack || defence ? { attack, defence } : null;
}

function gaugeBlock(input, labels) {
    const svg = renderGauge({
        value: input.value, marker: input.marker, min: input.min, max: input.max,
        leftLabel: labels.left, rightLabel: labels.right, centreLabel: labels.centre,
        ariaLabel: input.words,
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
            ${inputs.attack ? gaugeBlock(inputs.attack, { left: 'Weaker', right: 'Stronger', centre: 'Attack' }) : ''}
            ${inputs.defence ? gaugeBlock(inputs.defence, { left: 'Leakier', right: 'Tighter', centre: 'Defence' }) : ''}
        </div>`
        : '';
    // Template literal: backticks let us write HTML across several lines and
    // drop values in with ${...}. Every value goes through escapeHtml.
    return `
        <div class="card" id="team-strength">
            <div class="eyebrow-sm">how strong are they this week</div>
            <h3 class="outlook-phrase strength-verdict">${escapeHtml(payload.headline)}</h3>
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
