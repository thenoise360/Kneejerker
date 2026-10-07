import { test } from 'node:test';
import assert from 'node:assert/strict';
import { renderRecord, renderRecordSkeleton } from '../../FPL_site/static/scripts/lib/recordView.js';

const game = (over = {}) => ({
    gameweek: 3, opponent: 'Chelsea', is_home: true,
    predicted_for: 2, predicted_against: 1, actual_for: 3, actual_against: 1,
    verdict: 'better', ...over,
});
const ready = {
    status: 'ready', team_name: 'Arsenal',
    headline: 'Our read on Arsenal has held up well',
    reason: 'Most results landed close to what we expected.',
    early_days: true, early_days_label: 'Early days — this gets more reliable as the season goes on.',
    started_on: '2026-10-08', games: [game()],
};
// Visible text only: drop tags and escape codes.
const text = (html) => html.replace(/<[^>]*>/g, '').replace(/&#\d+;/g, '');

test('verdict and reason first, no digits before the details', () => {
    const html = renderRecord({ ...ready, early_days: false, early_days_label: null });
    const before = html.split('<details')[0];
    assert.match(before, /<h3 class="recap-verdict">Our read on Arsenal has held up well<\/h3>/);
    assert.match(before, /<p>Most results landed close to what we expected\.<\/p>/);
    assert.doesNotMatch(text(before), /\d/);
    assert.match(html, /<summary>See the numbers<\/summary>/);
});

test('early days label has an aria-hidden icon and text', () => {
    const html = renderRecord(ready);
    assert.match(html, /<p class="sub"><span aria-hidden="true">ⓘ<\/span> Early days/);
    assert.doesNotMatch(renderRecord({ ...ready, early_days_label: null }), /Early days/);
});

test('per-game wording for home, away and each verdict', () => {
    const html = renderRecord({ ...ready, games: [
        game(),
        game({ gameweek: 4, opponent: 'Spurs', is_home: false, actual_for: 1, actual_against: 1, verdict: 'as_expected' }),
        game({ gameweek: 5, opponent: 'Fulham', actual_for: 0, verdict: 'worse' }),
    ] });
    const inside = html.split('<details')[1];
    assert.match(inside, /<li>Gameweek 3, home to Chelsea: we expected 2\.0–1\.0, it finished 3–1 \(Better than expected\)<\/li>/);
    assert.match(inside, /<li>Gameweek 4, away at Spurs: we expected 2\.0–1\.0, it finished 1–1 \(As expected\)<\/li>/);
    assert.match(inside, /Gameweek 5, home to Fulham: .*\(Worse than expected\)/);
});

test('started-on footer is formatted and omitted when missing', () => {
    assert.match(renderRecord(ready), /We started keeping score on 8 October 2026\./);
    assert.doesNotMatch(renderRecord({ ...ready, started_on: null }), /started keeping score/);
});

test('not ready payload shows its message', () => {
    const html = renderRecord({ status: 'not_ready', message: { title: 'Soon', body: 'Check back.' } });
    assert.match(html, /Soon/);
});

test('escapes every value', () => {
    const html = renderRecord({ ...ready, headline: '<b>x</b>', reason: '<i>y</i>',
        early_days_label: '<u>z</u>', games: [game({ opponent: '<script>1</script>' })] });
    assert.doesNotMatch(html, /<b>x|<i>y|<u>z|<script>/);
});

test('skeleton is marked busy', () => {
    assert.match(renderRecordSkeleton(), /aria-busy="true"/);
});

test('day one: only eyebrow, verdict and reason (no label, no details, no footer)', () => {
    const html = renderRecord({ ...ready, games: [], headline: 'No finished games logged yet',
        reason: 'We started keeping score on 8 October 2026. Check back after the next game.' });
    assert.match(html, /<h3 class="recap-verdict">No finished games logged yet<\/h3>/);
    assert.doesNotMatch(html, /<details|Early days|aria-hidden/);
    assert.equal(html.match(/started keeping score/g).length, 1);
});

test('with games, the started-on date appears only once', () => {
    const html = renderRecord(ready);
    assert.equal(html.match(/8 October 2026/g).length, 1);
});

test('predictions always show one decimal; actual scores stay whole', () => {
    const html = renderRecord({ ...ready, games: [game({ predicted_for: 1, predicted_against: 0, actual_for: 2, actual_against: 0 })] });
    assert.match(html, /we expected 1\.0–0\.0, it finished 2–0 /);
});
