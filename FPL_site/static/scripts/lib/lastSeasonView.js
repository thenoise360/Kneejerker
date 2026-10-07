/***** lastSeasonView.js *****/
// A one-line reminder of how last season went, shown on the player's Form card
// while this season is too young for the form chart to say much.
// History is background ("worth knowing"), never a reason to pick, so the
// wording stays gentle. The numbers are opt in, on a quieter line right underneath.
import { escapeHtml } from './escapeHtml.js';

// Once a player has made 6 appearances this season the chart has a real
// sample, so we stop showing last season. 5 or fewer appearances still shows.
export const MAX_THIS_SEASON_APPEARANCES = 5;

// Decides whether to show the line at all. Number() turns "3" into 3, and a
// missing count becomes NaN, which fails the check, so we show nothing
// rather than guess.
export function shouldShowLastSeason(payload) {
    if (!payload || payload.this_season_appearances === null || payload.this_season_appearances === undefined) return false;
    const seen = Number(payload.this_season_appearances);
    return Number.isFinite(seen) && seen <= MAX_THIS_SEASON_APPEARANCES;
}

// Returns the HTML to place inside the Form card, or '' when nothing should show.
// payload.headline and payload.detail are written by the server.
export function buildLastSeasonHtml(payload) {
    if (!shouldShowLastSeason(payload) || !payload.headline) return '';
    const headline = `<div class="mc-caption last-season-line">${escapeHtml(payload.headline)}</div>`;
    // Players who did not play last season have no numbers to show.
    if (!payload.detail) return headline;
    // The detail is opt in (kj-num): the Form card's own "Show the numbers" switch reveals it.
    return `${headline}
        <div class="mc-caption last-season-detail kj-num">${escapeHtml(payload.detail)}</div>`;
}
