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

// One chip per missing player: the name, then their chance of playing in a
// smaller tag. Laid out as a wrapping row so a long list never pushes the card wide.
function missingChip(player) {
    return `<li class="strength-missing-chip">${escapeHtml(player.name)}`
        + ` <span class="strength-missing-chance">${escapeHtml(player.chance)}% chance</span></li>`;
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
    // tone and versus come from the server's thresholds, the same ones as the headline.
    const tone = ['same', 'worse', 'better'].includes(entry.tone) ? entry.tone : 'same';
    return { value: now, marker: usual, min: GAUGE_MIN, max: GAUGE_MAX, words: entry.words,
             tone, versus: typeof entry.versus === 'string' ? entry.versus : '' };
}

export function gaugeInputs(payload) {
    const gauge = payload.gauge;
    if (!gauge) return null;
    const attack = oneGauge(gauge.attack);
    const defence = oneGauge(gauge.defence);
    return attack || defence ? { attack, defence } : null;
}

// figures: the two numbers that sit under this gauge, already written by the caller.
// input is null when the server could not place the dial; the figures still show.
function gaugeBlock(input, labels, figures) {
    const figureHtml = `<dl class="strength-figures">
            <div><dt>This week</dt><dd>${escapeHtml(figures.now)}</dd></div>
            <div><dt>Usual</dt><dd>${escapeHtml(figures.usual)}</dd></div>
        </dl>
        <div class="strength-figures-unit">${escapeHtml(figures.unit)}</div>`;
    if (!input) {
        return `<div class="strength-gauge"><div class="strength-figures-title">${escapeHtml(labels.centre)}</div>${figureHtml}</div>`;
    }
    const svg = renderGauge({
        value: input.value, marker: input.marker, min: input.min, max: input.max,
        leftLabel: labels.left, rightLabel: labels.right, centreLabel: labels.centre,
        ariaLabel: input.words, tone: input.tone,
    });
    // The comparison in words, in the same colour as the dial, so the colour
    // is never the only clue.
    const versus = input.versus
        ? `<div class="strength-versus strength-versus--${input.tone}">${escapeHtml(input.versus)}</div>`
        : '';
    return `<div class="strength-gauge">${svg}
        ${versus}
        ${figureHtml}
    </div>`;
}

export function renderStrength(payload) {
    // Anything that is not "ready" (for example "not_ready") carries its own calm message.
    if (payload.status !== 'ready') {
        return renderMessage(payload.message);
    }
    // Only draw the absentees if somebody is actually missing.
    const missing = payload.missing && payload.missing.length
        ? `<div class="strength-missing">
            <div class="strength-missing-title">Missing or doubtful this week</div>
            <ul class="strength-missing-list">${payload.missing.map(missingChip).join('')}</ul>
        </div>`
        : '';
    // A missing or broken gauge is left out, but its figures still show.
    const inputs = gaugeInputs(payload) || { attack: null, defence: null };
    // Each gauge carries its own figures underneath, so the numbers sit next to
    // the picture they explain instead of in a separate list.
    const gauges = `<div class="strength-gauges">
            ${gaugeBlock(inputs.attack, { left: 'Weaker', right: 'Stronger', centre: 'Attack' },
                { now: oneDecimal(payload.scored_adjusted), usual: oneDecimal(payload.scored), unit: 'goals a game against an average side' })}
            ${gaugeBlock(inputs.defence, { left: 'Leakier', right: 'Tighter', centre: 'Defence' },
                { now: oneDecimal(payload.conceded_adjusted), usual: oneDecimal(payload.conceded), unit: 'goals conceded a game against an average side' })}
        </div>`;
    // The key only makes sense when at least one dial is drawn.
    const legend = inputs.attack || inputs.defence
        ? `<div class="strength-legend"><span><i class="strength-swatch-tick" aria-hidden="true"></i>Usual</span><span><i class="strength-swatch-dot" aria-hidden="true"></i>This week</span></div>`
        : '';
    // Template literal: backticks let us write HTML across several lines and
    // drop values in with ${...}. Every value goes through escapeHtml.
    return `
        <div class="card" id="team-strength">
            <div class="eyebrow-sm">how strong are they this week</div>
            <h3 class="outlook-phrase strength-verdict">${escapeHtml(payload.headline)}</h3>
            <p class="sub">${escapeHtml(payload.reason)}</p>
            ${gauges}
            ${legend}
            ${missing}
        </div>`;
}

// The loading placeholder, same markup as the template's first paint.
export function renderStrengthSkeleton() {
    return `
        <div class="card" aria-busy="true" aria-label="Loading team strength">
            <div class="skeleton" style="height:18px; width:60%;"></div>
        </div>`;
}
