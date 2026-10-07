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

// The wording for each verdict, with a small icon. The words carry the meaning,
// never colour: the badge colour (plum, brand red, brand green) only repeats it.
const VERDICTS = {
    better: { icon: '▲', words: 'Better than expected' },
    as_expected: { icon: '●', words: 'As expected' },
    worse: { icon: '▼', words: 'Worse than expected' },
};

// The newest games are shown straight away; any older ones sit behind a
// "Show earlier games" toggle so the card stays short on a phone.
const RECENT_GAMES = 5;

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
    'August', 'September', 'October', 'November', 'December'];

// Turn '2026-10-08' into '8 October 2026'. We split the text ourselves instead
// of using Date, because Date can shift the day by one in some time zones.
function longDate(iso) {
    const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso));
    if (!match) return String(iso);
    return `${Number(match[3])} ${MONTHS[Number(match[2]) - 1]} ${match[1]}`;
}

// Predictions always show one decimal (1.0, not 1), so they never look like a final score.
function oneDecimal(value) {
    return Number(value).toFixed(1);
}

// One row per finished game: who and where on top, then our prediction and
// the real score side by side, so the two can be compared at a glance.
function gameRow(game) {
    const where = game.is_home ? 'home to' : 'away at';
    const verdict = VERDICTS[game.verdict];
    const badge = verdict
        ? `<span class="record-verdict record-verdict--${escapeHtml(game.verdict)}"><span aria-hidden="true">${verdict.icon}</span> ${verdict.words}</span>`
        : '';
    return `<li class="record-game">
            <div class="record-game-head"><span>Gameweek ${escapeHtml(game.gameweek)}, ${where} ${escapeHtml(game.opponent)}</span>${badge}</div>
            <div class="record-scores">
                <div><span class="record-score-label">We expected</span> <span class="record-score">${escapeHtml(oneDecimal(game.predicted_for))}–${escapeHtml(oneDecimal(game.predicted_against))}</span></div>
                <div><span class="record-score-label">It finished</span> <span class="record-score">${escapeHtml(game.actual_for)}–${escapeHtml(game.actual_against)}</span></div>
            </div>
        </li>`;
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
    // The server sends games oldest first; the newest game is the most useful, so it goes on top.
    const newestFirst = games.slice().reverse();
    const recent = newestFirst.slice(0, RECENT_GAMES);
    const earlier = newestFirst.slice(RECENT_GAMES);
    const earlierBlock = earlier.length
        ? `<details class="record-earlier">
                <summary>Show earlier games</summary>
                <ul class="record-games">${earlier.map(gameRow).join('')}</ul>
            </details>`
        : '';
    const started = payload.started_on
        ? `<p class="sub">We started keeping score on ${escapeHtml(longDate(payload.started_on))}.</p>`
        : '';
    return `
        <div class="card" id="prediction-record">
            <div class="eyebrow-sm">how our predictions are doing</div>
            <h3 class="recap-verdict">${escapeHtml(payload.headline)}</h3>
            <p>${escapeHtml(payload.reason)}</p>
            ${early}
            <ul class="record-games">${recent.map(gameRow).join('')}</ul>
            ${earlierBlock}
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
