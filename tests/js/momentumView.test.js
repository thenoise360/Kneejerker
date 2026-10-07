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

test('default view is the label and reason only', () => {
    const [before] = renderMomentumCard(ready).split('<details');
    assert.match(before, /<h3 class="recap-verdict momentum-verdict">Rising<\/h3>/);
    assert.match(before, /<p[^>]*>Kinder fixtures coming up\.<\/p>/);
    assert.doesNotMatch(before, /Teammates/);
});

test('it is a carousel slide', () => {
    assert.match(renderMomentumCard(ready), /^\s*<div class="mini-card mini-slide">/);
});

test('all four signals sit inside the details', () => {
    const html = renderMomentumCard(ready);
    const inside = html.split('<details')[1];
    assert.match(inside, /<summary>See each signal<\/summary>/);
    for (const name of ['Fixtures', 'Teammates', 'Position on the pitch', 'Manager change']) {
        assert.ok(inside.includes(name), name);
    }
    assert.match(inside, /<div class="sub">easier games ahead<\/div>/);
});

test('every arrow is paired with a word', () => {
    const inside = renderMomentumCard(ready).split('<details')[1];
    assert.match(inside, /<span aria-hidden="true">↑<\/span> Fixtures: Up/);
    assert.match(inside, /<span aria-hidden="true">→<\/span> Teammates: No change/);
    assert.match(inside, /<span aria-hidden="true">–<\/span> Position on the pitch: Not tracked yet/);
    assert.match(inside, /<span aria-hidden="true">–<\/span> Manager change: Not tracked yet/);
});

test('the details use recap-details so the focus outline applies', () => {
    assert.match(renderMomentumCard(ready), /<details class="recap-details">/);
});

test('the heading uses the momentum-verdict class', () => {
    assert.match(renderMomentumCard(ready), /<h3 class="recap-verdict momentum-verdict">Rising<\/h3>/);
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
    assert.match(html, /<h3 class="recap-verdict">Not yet<\/h3>/);
    assert.doesNotMatch(html, /<details/);
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
