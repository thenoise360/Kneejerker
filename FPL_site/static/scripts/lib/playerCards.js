/***** playerCards.js *****/
// The player carousels on Radar (the bottom sheet) and Discover (the panel)
// show the same kinds of card. This module keeps them consistent in two ways:
//
// 1. ORDER. Both pages use CARD_ORDER. A page that has fewer cards (Discover
//    has no Momentum, Set pieces or Rating) shows the ones it has in the same
//    relative order, so swiping feels the same on both.
//
// 2. ANATOMY. Every card is built by playerCard(), so every card reads the
//    same way, top to bottom:
//      title -> the visual -> one plain sentence -> optional extra -> switch
//    Text is left aligned. A dial or chart fills the visual area. Anything
//    marked "kj-num" is opt in, and the "Show the numbers" switch always sits
//    last, in the same place, on every card that has something to reveal.
//
// Pure functions that return HTML strings: no DOM access, so they run in Node tests.
import { escapeHtml } from './escapeHtml.js';
import { numbersToggle } from './numbersToggle.js';
import { sumNumbers, formatPoints } from './numbers.js';
import { SEASON_STATS, formatStatValue, summaryRow } from '../visuals.js';

export const CARD_ORDER = ['form', 'momentum', 'fixtures', 'season', 'ownership', 'setPieces', 'rating', 'summary'];

export const CARD_TITLES = {
    form: 'Form, last 5 vs average',
    momentum: 'Momentum',
    fixtures: 'Next 5 fixtures',
    season: 'Season numbers',
    ownership: 'Ownership',
    setPieces: 'Set pieces',
    rating: 'Rating breakdown',
    summary: 'Summary',
};

// { form: '<div…>', fixtures: '<div…>' } -> the cards as a list, in CARD_ORDER.
// Keys a page did not build (or built as '') are skipped.
export function inCardOrder(cardsByKey) {
    return CARD_ORDER.filter(key => cardsByKey[key]).map(key => cardsByKey[key]);
}

// The same switch on every card, but only when the card has something to reveal.
// The lookahead stops "kj-numbers" (the container class) counting as "kj-num".
const OPT_IN = /\bkj-num(?![\w-])/;

/**
 * One carousel card.
 * @param {Object} parts
 * @param {string} parts.title - plain text; escaped here.
 * @param {string} [parts.visual] - HTML for the chart, dial, list or grid.
 * @param {string} [parts.caption] - one plain sentence; escaped here.
 * @param {string} [parts.captionHtml] - use instead of caption when the sentence carries markup (legend dots).
 * @param {string} [parts.extra] - HTML that follows the sentence (for example last season's line).
 * @param {string} [parts.wrapperClass] - the page's own slide class, so its carousel can size it.
 * @param {string} [parts.toggleLabel] - the switch wording, when what it reveals is not numbers.
 */
export function playerCard({ title, visual = '', caption = '', captionHtml = '', extra = '', wrapperClass = '', toggleLabel }) {
    const sentence = captionHtml || (caption ? escapeHtml(caption) : '');
    const body = `<div class="mc-title">${escapeHtml(title)}</div>`
        + (visual ? `<div class="player-card-visual">${visual}</div>` : '')
        + (sentence ? `<p class="player-card-caption">${sentence}</p>` : '')
        + extra;
    const optIn = OPT_IN.test(body);
    const classes = [wrapperClass, 'player-card', optIn ? 'kj-numbers' : ''].filter(Boolean).join(' ');
    return `<div class="${classes}">${body}${optIn ? numbersToggle(toggleLabel) : ''}</div>`;
}

// A card with nothing to draw yet: the title, then a calm sentence where the visual would be.
export function emptyPlayerCard(title, message, { wrapperClass = '', extra = '' } = {}) {
    return playerCard({ title, visual: `<div class="empty-state">${escapeHtml(message)}</div>`, extra, wrapperClass });
}

// One sentence about the last five gameweeks. The comparison is whatever average
// the page has (Radar: the position average; Discover: the same, or everyone's).
export function describeForm(last5, avg5, averageName = 'the position average') {
    const total = sumNumbers(last5);
    const avgTotal = sumNumbers(avg5);
    if (total === 0 && avgTotal === 0) {
        return 'No points on the board across these 5 gameweeks yet.';
    }
    const mean = total / last5.length;
    const variance = last5.reduce((a, v) => a + Math.pow(v - mean, 2), 0) / last5.length;
    const stdDev = Math.sqrt(variance);
    if (mean > 0 && stdDev > mean * 0.6) {
        return `Streaky: swinging between ${Math.min(...last5)} and ${Math.max(...last5)} points across these 5 gameweeks.`;
    }
    if (total > avgTotal) {
        return `Above ${averageName} over these 5 gameweeks (${formatPoints(total)} vs ${formatPoints(avgTotal)} points).`;
    }
    if (total < avgTotal) {
        return `Below ${averageName} over these 5 gameweeks (${formatPoints(total)} vs ${formatPoints(avgTotal)} points).`;
    }
    return `Right in line with ${averageName} over these 5 gameweeks.`;
}

// Season totals as big numbers. The position average under each is opt in.
// Returns null when there are no totals, so the caller can show an empty card.
export function seasonNumbers(summary) {
    if (!summary || !summary.metrics || summary.metrics.length === 0) return null;
    const metricsByTitle = {};
    summary.metrics.forEach(m => { metricsByTitle[m.title] = m; });
    const cells = SEASON_STATS
        .filter(s => !s.positionsOnly || s.positionsOnly.includes(summary.position_name))
        .map(s => {
            const m = metricsByTitle[s.metricTitle];
            if (!m) return '';
            return `<div>
                <div class="val">${escapeHtml(formatStatValue(m.value))}</div>
                <div class="lbl">${escapeHtml(s.label)}</div>
                <div class="lbl-avg kj-num">Position average: ${escapeHtml(formatStatValue(m.averageValue))}</div>
            </div>`;
        }).join('');
    // Pre-season, the official game still shows last season's final totals until
    // gameweek 1 locks, so say so plainly rather than present them as this season's.
    const position = (summary.position_name || 'player').toLowerCase();
    return {
        title: summary.is_pre_season ? 'Season numbers (last season)' : CARD_TITLES.season,
        visual: `<div class="season-grid">${cells}</div>`,
        caption: summary.is_pre_season
            ? "Still last season's final numbers. These reset once gameweek 1 locks."
            : `Season totals so far for this ${position}.`,
    };
}

function fixtureDifficulty(fixtures) {
    const real = (fixtures || []).filter(f => f.homeOrAway !== 'Blank');
    if (!real.length) return null;
    const avgDiff = real.reduce((a, f) => a + f.difficulty, 0) / real.length;
    const withLeague = real.filter(f => f.leagueAverageDifficulty !== null && f.leagueAverageDifficulty !== undefined);
    const leagueAvg = withLeague.length
        ? withLeague.reduce((a, f) => a + f.leagueAverageDifficulty, 0) / withLeague.length
        : null;
    return { avgDiff, leagueAvg };
}

// Every earlier card's headline figure as a bar against its own comparison
// point. The comparison wording under each bar is opt in (summaryRow marks it).
export function summaryRows({ summary, fixtures, form, avgForm, averageLabel = 'Position average', indexEntry }) {
    const rows = [];
    if (form && form.length) {
        const total = sumNumbers(form);
        const avgTotal = sumNumbers(avgForm);
        const max = Math.max(total, avgTotal, 1);
        rows.push(summaryRow('Form, last 5 gameweeks', `${formatPoints(total)} points`, `${averageLabel}: ${formatPoints(avgTotal)} points`, (total / max) * 100, (avgTotal / max) * 100));
    }
    const diff = fixtureDifficulty(fixtures);
    if (diff) {
        // Difficulty runs 1 (kindest) to 5 (toughest), so invert it for the
        // bar: a longer bar always reads as the easier run.
        const easePct = ((5 - diff.avgDiff) / 4) * 100;
        const leagueEasePct = diff.leagueAvg !== null ? ((5 - diff.leagueAvg) / 4) * 100 : 50;
        const compareText = diff.leagueAvg !== null ? `League average: ${diff.leagueAvg.toFixed(1)}/5` : 'League average not available';
        rows.push(summaryRow('Next 5 fixtures difficulty', `${diff.avgDiff.toFixed(1)}/5`, compareText, easePct, leagueEasePct));
    }
    const pointsMetric = ((summary && summary.metrics) || []).find(m => m.title === 'Points');
    if (pointsMetric) {
        const max = Math.max(pointsMetric.value, pointsMetric.averageValue, 1);
        const label = summary.is_pre_season ? 'Season points (last season)' : 'Season points';
        rows.push(summaryRow(label, formatStatValue(pointsMetric.value), `Position average: ${formatStatValue(pointsMetric.averageValue)}`, (pointsMetric.value / max) * 100, (pointsMetric.averageValue / max) * 100));
    }
    if (indexEntry) {
        const playerScore = Number(indexEntry.player_score);
        rows.push(summaryRow('Overall value score', `${playerScore.toFixed(0)}/100`, 'Scale: 0 to 100 across all players', playerScore, 50));
    }
    if (!rows.length) return null;
    return {
        visual: `<div class="summary-rows">${rows.join('')}</div>`,
        caption: 'The bar is this player; the marker is the average they are judged against.',
    };
}
