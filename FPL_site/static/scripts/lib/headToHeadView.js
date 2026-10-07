/***** headToHeadView.js *****/
// Pure functions that turn a club's last meetings with an opponent into words and
// HTML strings. No DOM access, so Node can test them. club.js puts the result on
// the page inside an expanded fixture row.
import { escapeHtml } from './escapeHtml.js';

// Number words, so the default copy says "three" rather than "3".
const NUMBER_WORDS = { 2: 'two', 3: 'three', 4: 'four', 5: 'five' };

// The one-meeting lines, keyed by that meeting's result.
const SINGLE = {
    won: 'Won the last meeting',
    drew: 'Drew the last meeting',
    lost: 'Lost the last meeting',
};

// One plain sentence about the recent record. Boundaries:
//   0 meetings            -> none in the data (Premier League only, since 2021)
//   1 meeting             -> that result
//   2 or more, none lost  -> unbeaten
//   2 or more, none won   -> haven't beaten them
//   anything else         -> mixed
export function meetingsSummary(meetings) {
    const list = Array.isArray(meetings) ? meetings : [];
    if (list.length === 0) return 'No Premier League meetings in recent seasons';
    if (list.length === 1) return SINGLE[list[0].result] || 'No Premier League meetings in recent seasons';

    const word = NUMBER_WORDS[list.length] || String(list.length);
    const anyLost = list.some((m) => m.result === 'lost');
    const anyWon = list.some((m) => m.result === 'won');
    if (!anyLost) return `Unbeaten in the last ${word} meetings`;
    if (!anyWon) return `Haven't beaten them in the last ${word} meetings`;
    return 'Mixed results lately';
}

// "2025/26 · home · won 3–1" - these are the numbers, so they only show once the row is open.
export function meetingLine(m) {
    return `${m.season_label} · ${m.is_home ? 'home' : 'away'} · ${m.result} ${m.score}`;
}

// The whole "Last meetings" block. Every value goes through escapeHtml.
export function renderLastMeetings(meetings) {
    const list = Array.isArray(meetings) ? meetings : [];
    const items = list.map((m) => `<li>${escapeHtml(meetingLine(m))}</li>`).join('');
    return `<div class="h2h-block">`
        + `<div class="h2h-title">Last meetings</div>`
        + `<div class="h2h-summary">${escapeHtml(meetingsSummary(list))}</div>`
        + (items ? `<ul class="h2h-list">${items}</ul>` : '')
        + `<div class="h2h-note">Worth knowing, not a reason on its own.</div>`
        + `</div>`;
}
