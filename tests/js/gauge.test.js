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

test('the marker is a short radial tick at the expected angle', () => {
    const svg = renderGauge({ ...base, marker: 0.75 });   // a quarter of the way: 135 degrees
    const m = svg.match(/class="gauge-marker" x1="([\d.-]+)" y1="([\d.-]+)" x2="([\d.-]+)" y2="([\d.-]+)"/);
    const [x1, y1, x2, y2] = m.slice(1).map(Number);
    const CX = 80, CY = 76;
    const angleOf = (x, y) => Math.atan2(CY - y, x - CX) * 180 / Math.PI;
    assert.ok(Math.abs(angleOf(x1, y1) - 135) < 0.5);
    assert.ok(Math.abs(angleOf(x2, y2) - 135) < 0.5);
    const length = Math.hypot(x2 - x1, y2 - y1);
    assert.ok(length > 13 && length < 15.5, `length ${length}`);
    // Inner end is closer to the centre than the outer end, and the arc radius lies between them.
    const r1 = Math.hypot(x1 - CX, y1 - CY), r2 = Math.hypot(x2 - CX, y2 - CY);
    assert.ok(r1 < 60 && r2 > 60);
    assert.match(svg, /class="gauge-marker"[^>]*stroke-width="3"/);
});

test('the marker colour and its legend swatch are at least 3:1 against white', async () => {
    const { MARKER_COLOUR } = await import('../../FPL_site/static/scripts/lib/gauge.js');
    const { contrastRatio } = await import('../../FPL_site/static/scripts/lib/contrast.js');
    const { readFileSync } = await import('node:fs');
    assert.ok(contrastRatio(MARKER_COLOUR, '#FFFFFF') >= 3);
    const css = readFileSync(new URL('../../FPL_site/static/content/home.css', import.meta.url), 'utf8');
    const swatch = css.match(/--teal-ink:\s*(#[0-9a-fA-F]{6})/)[1];
    assert.equal(swatch.toUpperCase(), MARKER_COLOUR);
    assert.ok(contrastRatio(swatch, '#FFFFFF') >= 3);
});

test('end labels are at least 11 pixels at a 130 pixel wide column and stay inside the box', () => {
    const svg = renderGauge(base);
    const sizes = [...svg.matchAll(/class="gauge-(?:end|centre)"[^>]*font-size="(\d+)"/g)].map(m => Number(m[1]));
    assert.equal(sizes.length, 3);
    for (const size of sizes) assert.ok(size * 130 / 160 >= 11, `size ${size}`);
    assert.match(svg, /text-anchor="start"/);
    assert.match(svg, /text-anchor="end"/);
});
