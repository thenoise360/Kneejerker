/***** gauge.js *****/
// A semicircle gauge drawn as an inline SVG string. No DOM access, so it can
// be tested in Node. The SVG carries words only, never digits: the card that
// uses it writes the figures underneath, next to the gauge they belong to.
import { escapeHtml } from './escapeHtml.js';

const CX = 80;       // centre of the semicircle
const CY = 76;
const RADIUS = 60;
const GAP_DEGREES = 3;   // breathing room between zone segments
// Darker teal for the "usual" tick, so it holds at least 3:1 against white (home.css uses the same value).
export const MARKER_COLOUR = '#0B7A6E';
const MARKER_HALF_LENGTH = 7;   // the tick is 14 units long, centred on the arc

// The fill and needle colour says how this week compares with usual:
// plum when it is as expected, brand red when it is worse, brand green when
// it is better. The red and green are the same ones the fixture pills use.
// Colour is never the only signal: the card writes the comparison in words too.
export const TONE_COLOURS = {
    same: 'var(--plum)',
    worse: '#D4145A',
    better: '#01FC7A',
};

function toneColour(tone) {
    return TONE_COLOURS[tone] || TONE_COLOURS.same;
}

function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
}

// 180 degrees at min (far left), 0 at max (far right), 90 in the middle.
export function valueToAngle(value, min, max) {
    const fraction = (clamp(value, min, max) - min) / (max - min);
    return 180 - fraction * 180;
}

function round(n) {
    return Math.round(n * 100) / 100;
}

function point(angle, radius) {
    const radians = angle * Math.PI / 180;
    return [round(CX + radius * Math.cos(radians)), round(CY - radius * Math.sin(radians))];
}

// An arc along the dial from one angle down to a smaller one, drawn left to right.
function arcPath(fromAngle, toAngle) {
    const [x1, y1] = point(fromAngle, RADIUS);
    const [x2, y2] = point(toAngle, RADIUS);
    return `M ${x1} ${y1} A ${RADIUS} ${RADIUS} 0 0 1 ${x2} ${y2}`;
}

function zoneArcs(zones, min, max, value) {
    const v = clamp(value, min, max);
    return zones.map((zone, index) => {
        const last = index === zones.length - 1;
        // The zone the needle sits in is filled; the others stay as track.
        const active = v >= zone.from && (v < zone.to || last);
        const start = valueToAngle(zone.from, min, max) - (index === 0 ? 0 : GAP_DEGREES / 2);
        const end = valueToAngle(zone.to, min, max) + (last ? 0 : GAP_DEGREES / 2);
        return `<path class="gauge-zone" d="${arcPath(start, end)}" fill="none" stroke="${active ? 'var(--plum)' : 'var(--grey-mid)'}" stroke-width="10"/>`;
    }).join('');
}

export function renderGauge({ value, min, max, marker = null, leftLabel, rightLabel, centreLabel, ariaLabel, zones = null, tone = 'same' }) {
    const colour = toneColour(tone);
    const track = zones && zones.length
        ? zoneArcs(zones, min, max, value)
        : `<path class="gauge-track" d="${arcPath(180, 0)}" fill="none" stroke="var(--grey)" stroke-width="10" stroke-linecap="round"/>`
        + (clamp(value, min, max) > min
            ? `<path class="gauge-fill" d="${arcPath(180, valueToAngle(value, min, max))}" fill="none" stroke="${colour}" stroke-width="10" stroke-linecap="round"/>`
            : '');
    let markerTick = '';
    if (marker !== null && marker !== undefined) {
        const angle = valueToAngle(marker, min, max);
        const [x1, y1] = point(angle, RADIUS - MARKER_HALF_LENGTH);
        const [x2, y2] = point(angle, RADIUS + MARKER_HALF_LENGTH);
        markerTick = `<line class="gauge-marker" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${MARKER_COLOUR}" stroke-width="3" stroke-linecap="round"/>`;
    }
    const [nx, ny] = point(valueToAngle(value, min, max), RADIUS);
    return `<svg class="gauge" viewBox="0 0 160 100" style="width:100%; max-width:200px;" role="img" aria-label="${escapeHtml(ariaLabel)}">`
        + track + markerTick
        + `<circle class="gauge-needle" cx="${nx}" cy="${ny}" r="6" fill="${colour}" stroke="#fff" stroke-width="2"/>`
        + `<text class="gauge-end" x="2" y="96" text-anchor="start" font-size="14" fill="#666">${escapeHtml(leftLabel)}</text>`
        + `<text class="gauge-end" x="158" y="96" text-anchor="end" font-size="14" fill="#666">${escapeHtml(rightLabel)}</text>`
        + `<text class="gauge-centre" x="${CX}" y="${CY - 8}" text-anchor="middle" font-size="14" font-weight="700" fill="var(--charcoal)">${escapeHtml(centreLabel)}</text>`
        + `</svg>`;
}
