import { test } from 'node:test';
import assert from 'node:assert/strict';
import { escapeHtml } from '../../FPL_site/static/scripts/lib/escapeHtml.js';
import { renderGuestRecap, renderMessage, RECAP_LOAD_FAILED } from '../../FPL_site/static/scripts/lib/recapView.js';

const guest = {
    headline: 'A fairly typical week',
    reason: 'Haaland led the way with a hat-trick.',
    average_score: 48,
    highest_score: 126,
    standouts: [{ id: 1, name: 'Haaland', team: 'Manchester City', points: 17, reason: 'a hat-trick' }],
};

test('escapes player names', () => {
    assert.equal(escapeHtml(`<b>O'Brien</b> & co`), '&lt;b&gt;O&#39;Brien&lt;/b&gt; &amp; co');
    assert.equal(escapeHtml(null), '');
});

test('guest recap shows verdict and reason by default, numbers inside details', () => {
    const html = renderGuestRecap(guest, 5);
    const [beforeDetails, insideDetails] = html.split('<details');
    assert.match(beforeDetails, /A fairly typical week/);
    assert.match(beforeDetails, /Haaland led the way with a hat-trick\./);
    assert.doesNotMatch(beforeDetails, /48/);
    assert.match(insideDetails, /See the numbers/);
    assert.match(insideDetails, /Average score: 48 points/);
    assert.match(insideDetails, /Highest score: 126 points/);
    assert.match(insideDetails, /A hat-trick/);
    assert.match(insideDetails, /Manchester City/);
});

test('guest recap without a highest score omits it', () => {
    const html = renderGuestRecap({ ...guest, highest_score: null }, 5);
    assert.doesNotMatch(html, /Highest score/);
});

test('guest recap escapes hostile names', () => {
    const hostile = { ...guest, standouts: [{ ...guest.standouts[0], name: '<img src=x>' }] };
    assert.doesNotMatch(renderGuestRecap(hostile, 5), /<img/);
});

test('message card renders title and body', () => {
    const html = renderMessage({ title: 'Nearly ready', body: 'Check back soon.' });
    assert.match(html, /Nearly ready/);
    assert.match(html, /Check back soon\./);
});

test('load-failure copy is calm and acronym free', () => {
    const text = RECAP_LOAD_FAILED.title + ' ' + RECAP_LOAD_FAILED.body;
    assert.doesNotMatch(text, /\b(FPL|GW|error)\b/i);
});
