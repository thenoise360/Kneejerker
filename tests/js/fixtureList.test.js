import test from 'node:test';
import assert from 'node:assert/strict';
import { buildFixtureList, difficultyWord } from '../../FPL_site/static/scripts/lib/fixtureList.js';

const away = { gameweek: 12, teamName: 'CRY', teamFullName: 'Crystal Palace', homeOrAway: 'Away', difficulty: 4 };
const home = { gameweek: 13, teamName: 'ARS', teamFullName: 'Arsenal', homeOrAway: 'Home', difficulty: 2 };
const blank = { gameweek: 14, teamName: '-', teamFullName: '', homeOrAway: 'Blank', difficulty: 'None' };
const text = html => html.replace(/<[^>]*>/g, '').replace(/\s+/g, ' ').trim();

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
