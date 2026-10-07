import { test } from 'node:test';
import assert from 'node:assert/strict';
import { renderMomentumCard } from '../../FPL_site/static/scripts/lib/momentumView.js';

const ready = {
    status: 'ready',
    label: 'Rising',
    reason: 'a kinder run of fixtures',
    signals: [
        { key: 'fixtures', name: 'Fixtures', direction: 'up', word: 'Up', arrow: '↑', reason: 'easier games ahead' },
        { key: 'teammates', name: 'Teammates', direction: 'flat', word: 'No change', arrow: '→', reason: null },
        { key: 'position', name: 'Position', direction: 'not_tracked', word: 'Not tracked yet', arrow: '–', reason: null },
        { key: 'manager', name: 'Manager', direction: 'not_tracked', word: 'Not tracked yet', arrow: '–', reason: null },
    ],
};

test('default view is the label and reason only', () => {
    const [before] = renderMomentumCard(ready).split('<details');
    assert.match(before, /<h3 class="recap-verdict">Rising<\/h3>/);
    assert.match(before, /<p[^>]*>a kinder run of fixtures<\/p>/);
    assert.doesNotMatch(before, /Teammates/);
});

test('it is a carousel slide', () => {
    assert.match(renderMomentumCard(ready), /^\s*<div class="mini-card mini-slide">/);
});

test('all four signals sit inside the details', () => {
    const html = renderMomentumCard(ready);
    const inside = html.split('<details')[1];
    assert.match(inside, /<summary>See each signal<\/summary>/);
    for (const name of ['Fixtures', 'Teammates', 'Position', 'Manager']) {
        assert.ok(inside.includes(name), name);
    }
    assert.match(inside, /<div class="sub">easier games ahead<\/div>/);
});

test('every arrow is paired with a word', () => {
    const inside = renderMomentumCard(ready).split('<details')[1];
    assert.match(inside, /<span aria-hidden="true">↑<\/span> Fixtures: Up/);
    assert.match(inside, /<span aria-hidden="true">→<\/span> Teammates: No change/);
    assert.match(inside, /<span aria-hidden="true">–<\/span> Position: Not tracked yet/);
    assert.match(inside, /<span aria-hidden="true">–<\/span> Manager: Not tracked yet/);
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
