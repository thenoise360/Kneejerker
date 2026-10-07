import test from 'node:test';
import assert from 'node:assert/strict';
import { shouldShowLastSeason, buildLastSeasonHtml, MAX_THIS_SEASON_APPEARANCES } from '../../FPL_site/static/scripts/lib/lastSeasonView.js';

const played = {
    played: true, headline: 'Last season: a regular points-scorer (Brighton)',
    detail: 'about 6.1 points a game across 34 games', this_season_appearances: 2
};
const text = html => html.replace(/<[^>]*>/g, '').replace(/&#39;/g, "'").replace(/\s+/g, ' ').trim();

test('shown for 0 to 5 appearances this season, hidden from 6', () => {
    assert.equal(MAX_THIS_SEASON_APPEARANCES, 5);
    assert.equal(shouldShowLastSeason({ ...played, this_season_appearances: 0 }), true);
    assert.equal(shouldShowLastSeason({ ...played, this_season_appearances: 5 }), true);
    assert.equal(shouldShowLastSeason({ ...played, this_season_appearances: 6 }), false);
    assert.equal(shouldShowLastSeason({ ...played, this_season_appearances: 30 }), false);
});

test('hidden when there is no payload or no sample count', () => {
    assert.equal(shouldShowLastSeason(null), false);
    assert.equal(shouldShowLastSeason(undefined), false);
    assert.equal(shouldShowLastSeason({ headline: 'x' }), false);
});

test('builds the headline with the numbers on a quieter line underneath', () => {
    const html = buildLastSeasonHtml(played);
    assert.ok(!html.includes('<details'));
    assert.ok(html.includes('<div class="mc-caption last-season-detail">about 6.1 points a game across 34 games</div>'));
    assert.equal(text(html), 'Last season: a regular points-scorer (Brighton) about 6.1 points a game across 34 games');
    // The headline comes first, so it reads before the numbers.
    assert.ok(html.indexOf('Last season:') < html.indexOf('last-season-detail'));
});

test('a player who did not play has a headline and no details', () => {
    const html = buildLastSeasonHtml({ played: false, headline: "Didn't play last season", this_season_appearances: 1 });
    assert.equal(text(html), "Didn't play last season");
    assert.ok(!html.includes('<details'));
});

test('empty string when it should not show', () => {
    assert.equal(buildLastSeasonHtml({ ...played, this_season_appearances: 6 }), '');
    assert.equal(buildLastSeasonHtml(null), '');
});

test('every value is escaped', () => {
    const html = buildLastSeasonHtml({ ...played, headline: '<b>x</b>', detail: '<img src=x>' });
    assert.ok(!html.includes('<b>') && !html.includes('<img'));
});

test('no acronyms in the copy', () => {
    assert.ok(!/\b(GW|FPL)\b/.test(text(buildLastSeasonHtml(played))));
});
