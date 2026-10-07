import test from 'node:test';
import assert from 'node:assert/strict';
import { buildFixtureList, difficultyWord, lastTimeStats } from '../../FPL_site/static/scripts/lib/fixtureList.js';

const away = { gameweek: 12, teamName: 'CRY', teamFullName: 'Crystal Palace', homeOrAway: 'Away', difficulty: 4 };
const home = { gameweek: 13, teamName: 'ARS', teamFullName: 'Arsenal', homeOrAway: 'Home', difficulty: 2 };
const blank = { gameweek: 14, teamName: '-', teamFullName: '', homeOrAway: 'Blank', difficulty: 'None' };
const text = html => html.replace(/<[^>]*>/g, ' ').replace(/&#39;/g, "'").replace(/\s+/g, ' ').trim();

test('difficulty words are Kind, Fair and Tough', () => {
    assert.equal(difficultyWord(1), 'Kind');
    assert.equal(difficultyWord(2), 'Kind');
    assert.equal(difficultyWord(3), 'Fair');
    assert.equal(difficultyWord(4), 'Tough');
    assert.equal(difficultyWord(5), 'Tough');
});

test('a fixture row reads gameweek, opponent and venue, then the difficulty word', () => {
    const t = text(buildFixtureList([away]));
    assert.equal(t, 'Gameweek 12 · Crystal Palace, away · Tough');
    assert.equal(text(buildFixtureList([home])), 'Gameweek 13 · Arsenal, home · Kind');
});

test('one row per gameweek, and a blank week says No game', () => {
    const html = buildFixtureList([away, home, blank]);
    assert.equal((html.match(/class="fixture-list-row/g) || []).length, 3);
    assert.equal(text(buildFixtureList([blank])), 'Gameweek 14 · No game');
});

test('every value is escaped', () => {
    const evil = { ...away, teamFullName: '<img src=x onerror=1>' };
    assert.ok(!buildFixtureList([evil]).includes('<img'));
});

test('no GW and no three-letter team codes appear', () => {
    const t = text(buildFixtureList([away, home, blank]));
    assert.ok(!/\bGW\b/.test(t));
    assert.ok(!/\b(CRY|ARS)\b/.test(t));
    assert.ok(!/\((H|A)\)/.test(t));
});

test('empty input gives an empty string', () => {
    assert.equal(buildFixtureList([]), '');
    assert.equal(buildFixtureList(undefined), '');
});

test('visuals.js has no GW text left', async () => {
    const { readFileSync } = await import('node:fs');
    const src = readFileSync(new URL('../../FPL_site/static/scripts/visuals.js', import.meta.url), 'utf8');
    assert.ok(!/\bGW\b/.test(src));
});

// ---- "last time against them" -------------------------------------------------

const played = (points, extra = {}) => ({
    kind: 'played', points, minutes: 90, result: 'won 3–1', is_home: true, club: null, ...extra
});

test('the caption under a row is the tier word, on both sides of each boundary', () => {
    const cap = (points) => {
        const html = buildFixtureList([{ ...away, lastTime: played(points) }]);
        return (html.match(/<span class="fixture-list-caption">([^<]*)/) || [])[1];
    };
    assert.equal(cap(8), 'Big return last time');
    assert.equal(cap(7), 'Steady return last time');
    assert.equal(cap(3), 'Steady return last time');
    assert.equal(cap(2), 'Quiet game last time');
});

test('the caption follows the row text without changing it', () => {
    const html = buildFixtureList([{ ...away, lastTime: played(9) }]);
    assert.ok(text(html).startsWith('Gameweek 12 · Crystal Palace, away · Tough Big return last time'));
    assert.equal(text(buildFixtureList([away])), 'Gameweek 12 · Crystal Palace, away · Tough');
});

test('did not play and not facing them have their own words; a new player has none', () => {
    const row = (lastTime) => text(buildFixtureList([{ ...away, lastTime }]));
    assert.ok(row({ kind: 'did_not_play' }).includes("Didn't play in this fixture last season"));
    assert.ok(row({ kind: 'no_meeting' }).includes("Didn't face them last season"));
    // The data only covers one season of the player, so it must not claim a first meeting.
    assert.ok(!row({ kind: 'no_meeting' }).includes('First meeting'));
    assert.equal(row({ kind: 'new_player' }), 'Gameweek 12 · Crystal Palace, away · Tough');
    assert.equal(row(null), 'Gameweek 12 · Crystal Palace, away · Tough');
});

test('a changed club is named, and an escaped value stays escaped', () => {
    const t = text(buildFixtureList([{ ...away, lastTime: played(5, { club: 'Brighton' }) }]));
    assert.ok(t.includes('Steady return last time · Last season, for Brighton'));
    const evil = buildFixtureList([{ ...away, lastTime: played(5, { club: '<img src=x>' }) }]);
    assert.ok(!evil.includes('<img'));
});

test('blank weeks get no caption', () => {
    assert.ok(!buildFixtureList([{ ...blank, lastTime: null }]).includes('fixture-list-caption'));
});

test('each played row carries its own points, minutes and result under the caption', () => {
    const html = buildFixtureList([
        { ...away, lastTime: played(9) },
        { ...home, lastTime: played(1, { minutes: 1, result: 'lost 0–2', is_home: false }) },
        blank
    ]);
    const rows = html.split('<li').slice(1).map(text);
    assert.ok(rows[0].includes('Big return last time 9 points · 90 minutes · won 3–1 at home'));
    assert.ok(rows[1].includes('1 point · 1 minute · lost 0–2 away'));
    assert.ok(!rows[2].includes('point'));
});

test('one list and nothing else: no separate See the numbers block', () => {
    const html = buildFixtureList([{ ...away, lastTime: played(9) }, { ...home, lastTime: { kind: 'no_meeting' } }]);
    assert.ok(!html.includes('<details'));
    assert.ok(html.startsWith('<ul') && html.endsWith('</ul>'));
});

test('rows with no meeting numbers get no stats line', () => {
    assert.equal(lastTimeStats({ kind: 'did_not_play' }), '');
    assert.equal(lastTimeStats({ kind: 'no_meeting' }), '');
    assert.equal(lastTimeStats(null), '');
});

test('last-time copy has no acronyms or team codes', () => {
    const t = text(buildFixtureList([{ ...away, lastTime: played(9, { club: 'Brighton' }) }]));
    assert.ok(!/\b(GW|FPL|CRY|BHA)\b/.test(t));
});
