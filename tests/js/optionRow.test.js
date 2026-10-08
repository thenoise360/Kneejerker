import { test } from 'node:test';
import assert from 'node:assert/strict';
import { renderOptionRow, formBarPercents, renderFormStrip } from '../../FPL_site/static/scripts/lib/optionRow.js';

const haaland = {
    id: 351, name: 'Haaland', team_short: 'MCI', position: 'Forward', price: 145, expected_points: 7.4,
    this_week: { opponent_short: 'BOU', is_home: true, difficulty: 'easier' }, recent_points: [2, 13, 6, 2, 9],
};

test('a row shows name, team, price, fixture, expected points and a compare toggle', () => {
    const html = renderOptionRow(haaland);
    assert.match(html, /Haaland/);
    assert.match(html, /MCI · £14\.5m/);
    assert.match(html, /vs BOU \(home\) · easier/);
    assert.match(html, /The official game expects 7\.4 points/);
    assert.match(html, /data-action="toggle-compare"[^>]*aria-pressed="false">Compare</);
    assert.match(html, /data-action="open-player" data-id="351"/);
});

test('selected rows say so for screen readers and in words', () => {
    const html = renderOptionRow(haaland, { selected: true });
    assert.match(html, /aria-pressed="true">Comparing</);
});

test('missing data is said plainly and the rest still renders', () => {
    const html = renderOptionRow({ id: 1, name: 'Nobody', expected_points: null, this_week: null, recent_points: [] });
    assert.match(html, /No expected points yet/);
    assert.match(html, /No match this week/);
    assert.match(html, /form-strip--empty/);
});

test('difficulty is left off when unknown', () => {
    const html = renderOptionRow({ ...haaland, this_week: { opponent_short: 'BOU', is_home: false, difficulty: null } });
    assert.match(html, /vs BOU \(away\)</);
});

test('badges and notes appear when given', () => {
    const html = renderOptionRow(haaland, { badge: 'Captain', note: "Steps in if Salah doesn't play" });
    assert.match(html, /option-badge">Captain/);
    assert.match(html, /Steps in if Salah/);
});

test('outside text is escaped', () => {
    const html = renderOptionRow({ ...haaland, name: '<script>x</script>', team_short: '"><b>' });
    assert.ok(!html.includes('<script>'));
    assert.ok(!html.includes('<b>'));
});

test('bar heights scale to the best game with a stub for blanks', () => {
    assert.deepEqual(formBarPercents([2, 13, 6, 2, 9]), [15, 100, 46, 15, 69]);
    assert.deepEqual(formBarPercents([0, -1, 4]), [4, 4, 100]);
    assert.match(renderFormStrip([2, 13]), /aria-label="Points in the last 2 games, oldest first: 2, 13"/);
});
