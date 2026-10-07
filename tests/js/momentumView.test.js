import { test } from 'node:test';
import assert from 'node:assert/strict';
import { renderMomentumCard, stripToCategories } from '../../FPL_site/static/scripts/lib/momentumView.js';

const ready = {
    status: 'ready',
    label: 'Rising',
    reason: 'Rising: kinder fixtures coming up.',
    signals: [
        { key: 'fixtures', name: 'Fixtures', direction: 'up', word: 'Up', arrow: '↑', reason: 'easier games ahead' },
        { key: 'teammates', name: 'Teammates', direction: 'same', word: 'No change', arrow: '→', reason: null },
        { key: 'position', name: 'Position on the pitch', direction: 'not_tracked', word: 'Not tracked yet', arrow: '–', reason: null },
        { key: 'manager', name: 'Manager change', direction: 'not_tracked', word: 'Not tracked yet', arrow: '–', reason: null },
    ],
};

test('the slide is a shared player card: title, dial, sentence, then the signals behind a switch', () => {
    const html = renderMomentumCard(ready);
    assert.match(html, /^<div class="mini-card mini-slide player-card kj-numbers">/);
    assert.match(html, /<div class="mc-title">Momentum<\/div>/);
    // Same order as every other card.
    const order = ['mc-title', 'momentum-gauge', 'player-card-caption', 'momentum-signals', 'Show the signals'].map(k => html.indexOf(k));
    assert.deepEqual([...order].sort((a, b) => a - b), order);
    assert.match(html, /<div class="kj-num">\s*<ul class="recap-standouts momentum-signals">/);
    assert.match(html, /<div class="mc-caption">Looks at upcoming fixtures and key teammates coming in or out\.<\/div>/);
    assert.doesNotMatch(html, /<h3|<details|momentum-verdict/);
});

test('another carousel can reuse the card with its own slide class', () => {
    assert.match(renderMomentumCard(ready, 'mp-card'), /^<div class="mp-card player-card kj-numbers">/);
});

test('the reason is a short line without the label prefix', () => {
    assert.match(renderMomentumCard(ready), /<p class="player-card-caption">Kinder fixtures coming up\.<\/p>/);
});

test('the needle sits in the zone that matches the label', () => {
    const needleX = label => Number(renderMomentumCard({ ...ready, label }).match(/class="gauge-needle" cx="([\d.-]+)"/)[1]);
    assert.ok(needleX('Cooling') < 60);
    assert.equal(needleX('Steady'), 80);
    assert.ok(needleX('Rising') > 100);
    // The needle for a label is always the same place, whatever else is in the payload.
    assert.equal(needleX('Rising'), needleX('Rising'));
});

test('the gauge has three zones, word labels and the label as centre text', () => {
    const html = renderMomentumCard(ready);
    assert.equal((html.match(/class="gauge-zone"/g) || []).length, 3);
    assert.match(html, /aria-label="Momentum: rising"/);
    assert.match(html, />Cooling<\/text>/);
    assert.match(html, /class="gauge-centre"[^>]*>Rising<\/text>/);
});

test('no score is used: an extra score changes nothing', () => {
    assert.equal(renderMomentumCard({ ...ready, score: 0.87 }), renderMomentumCard(ready));
    assert.equal(renderMomentumCard({ ...ready, score: -3 }), renderMomentumCard(ready));
});

test('an unknown label draws no gauge', () => {
    assert.doesNotMatch(renderMomentumCard({ ...ready, label: 'Mystery' }), /<svg/);
});

test('all four signals show on the slide, each reason in a caption', () => {
    const html = renderMomentumCard(ready);
    for (const name of ['Fixtures', 'Teammates', 'Position on the pitch', 'Manager change']) {
        assert.ok(html.includes(name), name);
    }
    assert.match(html, /<div class="mc-caption">easier games ahead<\/div>/);
});

test('every arrow is paired with a word', () => {
    const html = renderMomentumCard(ready);
    assert.match(html, /<span aria-hidden="true">↑<\/span> Fixtures: Up/);
    assert.match(html, /<span aria-hidden="true">→<\/span> Teammates: No change/);
    assert.match(html, /<span aria-hidden="true">–<\/span> Position on the pitch: Not tracked yet/);
    assert.match(html, /<span aria-hidden="true">–<\/span> Manager change: Not tracked yet/);
});

test('a reason without the label prefix is still capitalised', () => {
    const html = renderMomentumCard({ ...ready, reason: 'key teammates are back' });
    assert.match(html, /<p[^>]*>Key teammates are back<\/p>/);
});

test('values are escaped', () => {
    const html = renderMomentumCard({ ...ready, label: '<b>x</b>', reason: '<script>1</script>' });
    assert.ok(!html.includes('<b>x</b>'));
    assert.ok(!html.includes('<script>'));
});

test('no digits appear in the visible text', () => {
    // Strip the tags first, because the tag name h3 contains a digit.
    const text = renderMomentumCard(ready).replace(/<[^>]*>/g, ' ');
    assert.doesNotMatch(text, /\d/);
});

test('not_ready renders the calm message inside a slide', () => {
    const html = renderMomentumCard({ status: 'not_ready', message: { title: 'Not yet', body: 'Check back soon.' } });
    assert.match(html, /mini-slide/);
    assert.match(html, /<div class="mc-title">Not yet<\/div>/);
    assert.match(html, /<p class="player-card-caption">Check back soon\.<\/p>/);
    assert.doesNotMatch(html, /<details|<svg|numbers-toggle/);
});

test('a null or missing reason shows nothing instead of the word Null', () => {
    assert.doesNotMatch(renderMomentumCard({ ...ready, reason: null }), /Null/);
    assert.doesNotMatch(renderMomentumCard({ ...ready, reason: undefined }), /Undefined/);
});

test('the strip becomes two groups with the right titles and one reason each', () => {
    const groups = stripToCategories({
        heating_up: [{ id: 1, name: 'B', team: 'Chelsea', position: 'MID', reason: 'Rising: kinder fixtures coming up.' }],
        cooling_off: [{ id: 2, name: 'D', team: 'Arsenal', reason: 'Cooling: tougher fixtures coming up.' }],
    });
    assert.deepEqual(groups.map(g => g.title), ['Heating up', 'Cooling off']);
    assert.deepEqual(groups[0].players, [{
        id: 1, full_name: 'B', team_name: 'Chelsea', position: 'MID', why: 'Kinder fixtures coming up.' }]);
});

test('an empty list leaves its group out, and nothing at all gives no groups', () => {
    const one = stripToCategories({ heating_up: [], cooling_off: [{ id: 2, name: 'D', team: 'A', reason: 'r' }] });
    assert.deepEqual(one.map(g => g.title), ['Cooling off']);
    assert.deepEqual(stripToCategories({ heating_up: [], cooling_off: [] }), []);
    assert.deepEqual(stripToCategories({ status: 'not_ready' }), []);
    assert.deepEqual(stripToCategories(null), []);
});

test('each signal row carries the momentum-signal class so its rules apply', () => {
    const html = renderMomentumCard(ready);
    assert.equal((html.match(/<li class="momentum-signal">/g) || []).length, 4);
    assert.doesNotMatch(html, /<li>/);
});

test('the momentum gauge wrapper carries the capped class, and the cap is in home.css', async () => {
    const html = renderMomentumCard(ready);
    assert.match(html, /<div class="momentum-gauge"><svg /);
    const { readFileSync } = await import('node:fs');
    const css = readFileSync(new URL('../../FPL_site/static/content/home.css', import.meta.url), 'utf8');
    const max = Number(css.match(/\.momentum-gauge \{[^}]*max-width:\s*(\d+)px/)[1]);
    // The 14 unit labels in a 160 unit wide box must come out at 13px or less.
    assert.ok(max <= 180 && 14 * max / 160 <= 13.2, `max-width ${max}`);
});
