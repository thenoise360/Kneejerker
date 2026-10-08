import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { buildStatBlock, buildChartLegend, COMPARISON_COLORS } from '../../FPL_site/static/scripts/lib/statBlock.js';

// Snapshots captured from the original discovery.js implementation before it was moved.
const snap = Object.fromEntries(
    JSON.parse(readFileSync(new URL('./fixtures/statBlock.snap.json', import.meta.url), 'utf8')).map((s) => [s.name, s.html])
);
const P = [{ name: 'Haaland' }, { name: 'Salah' }, { name: 'Palmer' }];

test('colours are teal, pink and plum in order', () => {
    assert.deepEqual(COMPARISON_COLORS, ['var(--teal)', 'var(--pink)', 'var(--plum-tint)']);
});

test('output matches the original Discovery markup', () => {
    assert.equal(buildStatBlock('Points', P.slice(0, 2), (p, i) => ({ value: [6, 9][i], display: String([6, 9][i]) })), snap['two players basic']);
    assert.equal(
        buildStatBlock('Season points', P.slice(0, 2), (p, i) => ({ value: [40, 42][i], display: String([40, 42][i]) }),
            { avgValue: 30, min: 0, max: 60, axisLabels: ['Easier', 'Tougher'], compareText: 'Lower is easier' }),
        snap['shared avg and options']);
    assert.equal(
        buildStatBlock('Goals', P, (p, i) => ({ value: [5, 6, 5.5][i], display: String([5, 6, 5.5][i]), avgValue: [3, 4, 3][i] })),
        snap['per-player avg three close']);
    assert.equal(buildStatBlock('Assists', P.slice(0, 2), (p, i) => (i ? { value: null, display: '—' } : { value: 2, display: '2' })), snap['null value']);
    assert.equal(buildStatBlock('X', P.slice(0, 2), () => null), snap['no result']);
});

test('legend matches the original markup', () => {
    assert.equal(buildChartLegend([{ label: 'Haaland', color: 'var(--teal)' }, { label: 'Average', color: 'x', dashed: true }]), snap.legend);
});

test('names are escaped in titles and the legend', () => {
    const html = buildStatBlock('Points', [{ name: '<b>x</b>' }], () => ({ value: 1, display: '1' }));
    assert.ok(!html.includes('<b>'));
    assert.ok(!buildChartLegend([{ label: '<i>', color: 'red' }]).includes('<i>'));
});
