import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
    renderPlayerSheet, renderPlayerSheetSkeleton, renderSinglePlayer, renderComparison,
} from '../../FPL_site/static/scripts/lib/playerSheet.js';

const haaland = {
    id: 351, name: 'Haaland', team_short: 'MCI', position: 'Forward', price: 145,
    predicted_points: 7.4, position_average_predicted_points: 3.1,
    recent_games: [
        { gameweek: 1, opponent_short: 'WOL', is_home: false, minutes: 90, goals: 2, assists: 0, points: 13 },
        { gameweek: 2, opponent_short: 'ARS', is_home: true, minutes: 80, goals: 0, assists: 1, points: 6 },
    ],
    momentum: { label: 'Rising', reason: 'Rising: kinder fixtures coming up.', signals: [] },
    next_fixtures: [{ gameweek: 6, opponent_short: 'BOU', is_home: true, difficulty: 'easier' }],
    vs_opponent: { opponent_short: 'BOU', games: [{ season: 2025, gameweek: 12, is_home: false, minutes: 90, points: 8 }] },
};
const salah = {
    id: 5, name: 'Salah', team_short: 'LIV', position: 'Midfielder', price: 130,
    predicted_points: 6.1, position_average_predicted_points: 3.4,
    recent_games: [{ gameweek: 1, opponent_short: 'CHE', is_home: true, minutes: 90, goals: 1, assists: 1, points: 9 }],
    momentum: null,
    next_fixtures: [{ gameweek: 6, opponent_short: 'EVE', is_home: false, difficulty: 'tougher' }],
    vs_opponent: { opponent_short: 'EVE', games: [] },
};

test('single player shows the four sections', () => {
    const html = renderPlayerSheet([haaland]);
    assert.match(html, /Last 5 games/);
    assert.match(html, /Momentum/);
    assert.match(html, /Next 3 fixtures/);
    assert.match(html, /Against BOU/);
    assert.match(html, /MCI · Forward · £14\.5m/);
    assert.match(html, /7\.4 predicted points/);
    assert.match(html, /Average 3\.1 for the position/);
    assert.match(html, /13 points/);
    assert.match(html, /90 minutes, 2 goals/);
    assert.match(html, /Gameweek 6 · BOU \(home\) · easier/);
});

test('momentum drops the repeated label prefix from the reason', () => {
    const html = renderSinglePlayer(haaland);
    assert.match(html, /<strong>Rising<\/strong>\. Kinder fixtures coming up\./);
});

test('missing pieces are said plainly and the rest still renders', () => {
    const html = renderSinglePlayer({
        ...salah, recent_games: [], next_fixtures: [], vs_opponent: { opponent_short: 'EVE', games: [] },
    });
    assert.match(html, /No games played in the last five gameweeks yet/);
    assert.match(html, /Momentum isn(&#39;|')t available for this player yet/);
    assert.match(html, /No fixtures to show yet/);
    assert.match(html, /No games against EVE in the last two seasons/);
    assert.match(html, /Salah/);
});

test('no match this week gives the plain message instead of an opponent section', () => {
    const html = renderSinglePlayer({ ...salah, vs_opponent: null });
    assert.match(html, /No match this week/);
});

test('no prediction is stated', () => {
    assert.match(renderSinglePlayer({ ...salah, predicted_points: null }), /No prediction yet/);
});

test('two players give the Discovery comparison with a shared legend', () => {
    const html = renderPlayerSheet([haaland, salah]);
    assert.match(html, /class="mp-stat-list"/);
    assert.equal((html.match(/class="chart-legend"/g) || []).length, 1);
    assert.match(html, /Predicted points/);
    assert.match(html, /Average points, last 5 games/);
    assert.match(html, /Minutes, last 5 games/);
    assert.match(html, /Average points against this week's opponent/);
    assert.match(html, /mp-stat-avg-tick/);
    assert.match(html, /class="compare-cols"/);
    assert.match(html, /Gameweek 6 · EVE \(away\) · tougher/);
    assert.match(html, /var\(--teal\)/);
    assert.match(html, /var\(--pink\)/);
});

test('compare shows a dash for a player who lacks a number', () => {
    const html = renderComparison([haaland, { ...salah, predicted_points: null, recent_games: [] }]);
    assert.match(html, /Predicted points/);
    // Only the player who has the number gets a dot in the bar.
    assert.equal((html.split('Predicted points')[1].split('mp-stat-block')[0].match(/mp-stat-dot"/g) || []).length, 1);
});

test('compare leaves out a stat neither player has', () => {
    const html = renderComparison([
        { ...haaland, vs_opponent: null }, { ...salah, vs_opponent: null },
    ]);
    assert.ok(!html.includes('against this week'));
});

test('names and team text are escaped', () => {
    const html = renderPlayerSheet([{ ...haaland, name: '<img src=x>', team_short: '<b>' }, salah]);
    assert.ok(!html.includes('<img'));
    assert.ok(!html.includes('<b>'));
    assert.ok(!renderSinglePlayer({ ...haaland, name: '<img src=x>' }).includes('<img'));
});

test('empty input and the skeleton', () => {
    assert.match(renderPlayerSheet([]), /couldn(&#39;|')t load the player details/);
    assert.match(renderPlayerSheetSkeleton(), /class="skeleton"/);
});
