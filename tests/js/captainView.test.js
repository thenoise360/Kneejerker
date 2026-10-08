import { test } from 'node:test';
import assert from 'node:assert/strict';
import { renderCaptainView, optionById, allOptions } from '../../FPL_site/static/scripts/lib/captainView.js';

const opt = (id, name, extra = {}) => ({
    id, name, team_short: 'MCI', position: 'Forward', price: 100, predicted_points: 5,
    this_week: { opponent_short: 'BOU', is_home: true, difficulty: 'average' }, recent_points: [1, 2, 3], ...extra,
});
const captaincy = {
    state: 'needs_look',
    suggested: opt(1, 'Haaland'),
    vice: opt(2, 'Salah'),
    shortlist: [opt(1, 'Haaland'), opt(2, 'Salah'), opt(3, 'Palmer')],
    others: [opt(4, 'Rice')],
};

test('shows the lean as Captain, the vice with its reason, and the sections', () => {
    const html = renderCaptainView(captaincy);
    assert.match(html, /Captain and vice/);
    assert.match(html, /Make this change in the official app before the deadline/);
    assert.match(html, /option-badge">Captain/);
    assert.match(html, /option-badge">Vice/);
    assert.match(html, /Steps in if Haaland doesn&#39;t play/);
    assert.match(html, /Top alternatives/);
    assert.match(html, /Rest of your squad/);
});

test('the lean is not repeated under Top alternatives', () => {
    const html = renderCaptainView(captaincy);
    const alternatives = html.split('Top alternatives')[1].split('Rest of your squad')[0];
    assert.match(alternatives, /Palmer/);
    assert.ok(!alternatives.includes('Haaland'));
    assert.ok(!alternatives.includes('Salah'));
});

test('guests have no rest-of-squad section', () => {
    const html = renderCaptainView({ ...captaincy, others: [] });
    assert.ok(!html.includes('Rest of your squad'));
});

test('no lean gives the plain message', () => {
    const html = renderCaptainView({ state: 'needs_look', suggested: null, vice: null, shortlist: [], others: [] });
    assert.match(html, /Captain numbers aren&#39;t in yet|Captain numbers aren't in yet/);
});

test('compare bar guides the pick and offers the button for two', () => {
    assert.match(renderCaptainView(captaincy, []), /Tap Compare on two players/);
    assert.match(renderCaptainView(captaincy, [1]), /Pick one more player/);
    const two = renderCaptainView(captaincy, [1, 3]);
    assert.match(two, /data-action="open-compare">Compare Haaland and Palmer</);
    assert.match(two, /aria-pressed="true">Comparing/);
});

test('names are escaped', () => {
    const html = renderCaptainView({ ...captaincy, suggested: opt(1, '<script>x</script>') });
    assert.ok(!html.includes('<script>'));
});

test('options can be found by id from any list', () => {
    assert.equal(optionById(captaincy, '4').name, 'Rice');
    assert.equal(optionById(captaincy, 99), null);
    assert.ok(allOptions(captaincy).length >= 4);
});
