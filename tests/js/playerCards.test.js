import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
    CARD_ORDER, CARD_TITLES, inCardOrder, playerCard, emptyPlayerCard, describeForm, seasonNumbers, summaryRows
} from '../../FPL_site/static/scripts/lib/playerCards.js';

const text = html => html.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();

test('one order for both carousels, and every key has a title', () => {
    assert.deepEqual(CARD_ORDER, ['form', 'momentum', 'fixtures', 'season', 'ownership', 'setPieces', 'rating', 'summary']);
    for (const key of CARD_ORDER) assert.ok(CARD_TITLES[key], key);
});

test('cards come out in the shared order whatever order they were built in, skipping missing ones', () => {
    assert.deepEqual(inCardOrder({ summary: 'S', form: 'F', momentum: '', fixtures: 'X' }), ['F', 'X', 'S']);
});

test('every card reads title, visual, sentence, extra, then the switch', () => {
    const html = playerCard({ title: 'T', visual: '<i>v</i>', caption: 'Sentence.', extra: '<b class="kj-num">e</b>', wrapperClass: 'mini-card' });
    assert.match(html, /^<div class="mini-card player-card kj-numbers"><div class="mc-title">T<\/div><div class="player-card-visual"><i>v<\/i><\/div><p class="player-card-caption">Sentence\.<\/p><b class="kj-num">e<\/b><label class="numbers-toggle">/);
});

test('the switch only appears when something on the card is opt in', () => {
    const plain = playerCard({ title: 'T', visual: '<div class="kj-numbers-ish">v</div>' });
    assert.doesNotMatch(plain, /numbers-toggle|kj-numbers"/);
    assert.match(playerCard({ title: 'T', visual: '<span class="a kj-num b">1</span>' }), /numbers-toggle/);
    assert.match(playerCard({ title: 'T', extra: '<div class="kj-num">x</div>', toggleLabel: 'Show the signals' }), /Show the signals/);
});

test('title and caption are escaped; captionHtml is trusted markup from the caller', () => {
    const html = playerCard({ title: '<b>', caption: '<i>' });
    assert.doesNotMatch(html, /<b>|<i>/);
    assert.match(playerCard({ title: 'T', captionHtml: '<span class="dot"></span>Saka' }), /<span class="dot"><\/span>Saka/);
});

test('an empty card keeps the same anatomy', () => {
    const html = emptyPlayerCard('Set pieces', 'No duty.', { wrapperClass: 'mp-card' });
    assert.match(html, /^<div class="mp-card player-card"><div class="mc-title">Set pieces<\/div><div class="player-card-visual"><div class="empty-state">No duty\.<\/div>/);
});

test('form sentence: streaky, above, below, level and empty, with the given average name', () => {
    assert.match(describeForm([0, 12, 0, 13, 1], [3, 3, 3, 3, 3]), /^Streaky: swinging between 0 and 13 points/);
    assert.equal(describeForm([6, 7, 6, 7, 6], [3, 3, 3, 3, 3]), 'Above the position average over these 5 gameweeks (32 vs 15 points).');
    assert.equal(describeForm([2, 3, 2, 3, 2], [4, 4, 4, 4, 4], 'the midfielder average'), 'Below the midfielder average over these 5 gameweeks (12 vs 20 points).');
    assert.equal(describeForm([3, 3, 3, 3, 3], [3, 3, 3, 3, 3]), 'Right in line with the position average over these 5 gameweeks.');
    assert.equal(describeForm([0, 0], [0, 0]), 'No points on the board across these 5 gameweeks yet.');
});

test('season numbers: big values, with the position average opt in', () => {
    const s = seasonNumbers({ position_name: 'Midfielder', metrics: [{ title: 'Points', value: 41, averageValue: 22 }] });
    assert.equal(s.title, 'Season numbers');
    assert.match(s.visual, /<div class="val">41<\/div>/);
    assert.match(s.visual, /<div class="lbl-avg kj-num">Position average: 22<\/div>/);
    assert.equal(s.caption, 'Season totals so far for this midfielder.');
    assert.equal(seasonNumbers({ metrics: [] }), null);
    assert.equal(seasonNumbers({ is_pre_season: true, metrics: [{ title: 'Points', value: 1, averageValue: 1 }] }).title, 'Season numbers (last season)');
});

test('summary rows: comparison lines are opt in; nothing to show gives null', () => {
    const rows = summaryRows({ summary: { metrics: [{ title: 'Points', value: 41, averageValue: 22 }] }, fixtures: [], form: [5, 5], avgForm: [2, 2] });
    assert.match(rows.visual, /<div class="summary-row-compare kj-num">Position average: 4 points<\/div>/);
    assert.match(text(rows.visual), /Season points 41/);
    assert.equal(summaryRows({ summary: { metrics: [] }, fixtures: [], form: [], avgForm: [] }), null);
});
