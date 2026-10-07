import { test } from 'node:test';
import assert from 'node:assert/strict';
import { renderGauge, valueToAngle } from '../../FPL_site/static/scripts/lib/gauge.js';

const base = { value: 1, min: 0.5, max: 1.5, leftLabel: 'Weaker', rightLabel: 'Stronger', centreLabel: 'Attack', ariaLabel: 'Attack: <about> average' };

function textContents(svg) {
    return [...svg.matchAll(/<text[^>]*>([^<]*)<\/text>/g)].map(m => m[1]);
}
function needle(svg) {
    const m = svg.match(/<circle class="gauge-needle" cx="([\d.-]+)" cy="([\d.-]+)"/);
    return m && [m[1], m[2]];
}

test('angle is 180 at min, 0 at max, 90 in the middle', () => {
    assert.equal(valueToAngle(0.5, 0.5, 1.5), 180);
    assert.equal(valueToAngle(1.5, 0.5, 1.5), 0);
    assert.equal(valueToAngle(1, 0.5, 1.5), 90);
});

test('role img and escaped aria-label', () => {
    const svg = renderGauge(base);
    assert.match(svg, /role="img"/);
    assert.match(svg, /aria-label="Attack: &lt;about&gt; average"/);
});

test('no digits in any text content, and labels are escaped', () => {
    const svg = renderGauge({ ...base, leftLabel: '<b>L</b>' });
    for (const t of textContents(svg)) assert.doesNotMatch(t, /\d/);
    assert.ok(!svg.includes('<b>L</b>'));
    assert.deepEqual(textContents(svg).length, 3);
});

test('out of range values are clamped', () => {
    assert.deepEqual(needle(renderGauge({ ...base, value: 9 })), needle(renderGauge({ ...base, value: 1.5 })));
    assert.deepEqual(needle(renderGauge({ ...base, value: -9 })), needle(renderGauge({ ...base, value: 0.5 })));
});

test('marker is omitted when null and present otherwise', () => {
    assert.doesNotMatch(renderGauge(base), /gauge-marker/);
    assert.match(renderGauge({ ...base, marker: 1.1 }), /gauge-marker/);
});

test('zones give one arc path per zone', () => {
    const zones = [{ from: 0, to: 1, label: 'A' }, { from: 1, to: 2, label: 'B' }, { from: 2, to: 3, label: 'C' }];
    const svg = renderGauge({ ...base, min: 0, max: 3, value: 1.5, zones });
    assert.equal((svg.match(/class="gauge-zone"/g) || []).length, 3);
    assert.doesNotMatch(svg, /gauge-fill/);
});

test('scales to its container', () => {
    assert.match(renderGauge(base), /width:100%; max-width:200px/);
    assert.match(renderGauge(base), /viewBox="0 0 160 90"/);
});
