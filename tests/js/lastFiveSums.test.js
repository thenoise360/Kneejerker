import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

// Guard: pages that print last-five totals must add them with sumNumbers
// (which coerces text to numbers) and print them with formatPoints.
for (const name of ['radar.js', 'discovery.js']) {
    const src = readFileSync(new URL(`../../FPL_site/static/scripts/${name}`, import.meta.url), 'utf8');
    test(`${name} has no raw reduce sum of last-five values`, () => {
        assert.ok(!/reduce\(\(a, b\) => a \+ b/.test(src));
    });
    test(`${name} says "points", not "pts"`, () => {
        assert.ok(!/\bpts\b/.test(src));
    });
}
