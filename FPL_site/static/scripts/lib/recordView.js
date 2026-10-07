/***** recordView.js *****/
// Pure functions that turn the prediction record into HTML strings. No DOM
// access here, so they can be tested in Node. club.js puts them on the page.
import { escapeHtml } from './escapeHtml.js';
import { renderMessage } from './recapView.js';

// Shown if the record request itself fails (no connection, server down).
export const RECORD_LOAD_FAILED = {
    title: "We couldn't load our track record",
    body: 'Nothing is wrong on your side. Try again in a moment.',
};

// The wording for each verdict. The words carry the meaning, never colour.
const VERDICT_WORDS = {
    better: 'Better than expected',
    as_expected: 'As expected',
    worse: 'Worse than expected',
};

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
    'August', 'September', 'October', 'November', 'December'];

// Turn '2026-10-08' into '8 October 2026'. We split the text ourselves instead
// of using Date, because Date can shift the day by one in some time zones.
function longDate(iso) {
    const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso));
    if (!match) return String(iso);
    return `${Number(match[3])} ${MONTHS[Number(match[2]) - 1]} ${match[1]}`;
}

// One line per finished game. The scores are numbers, so they stay in the expander.
function gameRow(game) {
    const where = game.is_home ? 'home to' : 'away at';
    const verdict = VERDICT_WORDS[game.verdict] || '';
    return `<li>Gameweek ${escapeHtml(game.gameweek)}, ${where} ${escapeHtml(game.opponent)}: `
        + `we expected ${escapeHtml(game.predicted_for)}–${escapeHtml(game.predicted_against)}, `
        + `it finished ${escapeHtml(game.actual_for)}–${escapeHtml(game.actual_against)} (${verdict})</li>`;
}

export function renderRecord(payload) {
    // Anything that is not "ready" carries its own calm message.
    if (payload.status !== 'ready') {
        return renderMessage(payload.message);
    }
    const games = payload.games || [];
    // Day one: nothing to count or label yet. The reason already says when we started.
    if (!games.length) {
        return `
        <div class="card" id="prediction-record">
            <div class="eyebrow-sm">how our predictions are doing</div>
            <h3 class="recap-verdict">${escapeHtml(payload.headline)}</h3>
            <p>${escapeHtml(payload.reason)}</p>
        </div>`;
    }
    // The icon is hidden from screen readers; the words alone say "early days".
    const early = payload.early_days_label
        ? `<p class="sub"><span aria-hidden="true">ⓘ</span> ${escapeHtml(payload.early_days_label)}</p>`
        : '';
    const list = `<ul class="recap-standouts">${games.map(gameRow).join('')}</ul>`;
    const started = payload.started_on
        ? `<p class="sub">We started keeping score on ${escapeHtml(longDate(payload.started_on))}.</p>`
        : '';
    return `
        <div class="card" id="prediction-record">
            <div class="eyebrow-sm">how our predictions are doing</div>
            <h3 class="recap-verdict">${escapeHtml(payload.headline)}</h3>
            <p>${escapeHtml(payload.reason)}</p>
            ${early}
            <details class="recap-details">
                <summary>See the numbers</summary>
                ${list}
            </details>
            ${started}
        </div>`;
}

// The loading placeholder, same markup as the template's first paint.
export function renderRecordSkeleton() {
    return `
        <div class="card" aria-busy="true" aria-label="Loading our track record">
            <div class="skeleton" style="height:18px; width:60%;"></div>
        </div>`;
}
