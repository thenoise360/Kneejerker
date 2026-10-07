import test from 'node:test';
import assert from 'node:assert/strict';
import { sumNumbers, formatPoints } from '../../FPL_site/static/scripts/lib/numbers.js';

test('sumNumbers adds numeric strings instead of joining them', () => {
    assert.equal(sumNumbers(['0', '2', '13']), 15);
});
test('sumNumbers ignores values that are not finite numbers', () => {
    assert.equal(sumNumbers([1, null, undefined, 'x', NaN, 2]), 3);
    assert.equal(sumNumbers(undefined), 0);
});
test('formatPoints rounds to one decimal', () => {
    assert.equal(formatPoints(16.240000000000002), '16.2');
});
test('formatPoints drops a trailing .0', () => {
    assert.equal(formatPoints(15), '15');
    assert.equal(formatPoints(15.04), '15');
});
test('formatPoints shows 0 for missing values', () => {
    assert.equal(formatPoints(null), '0');
    assert.equal(formatPoints(undefined), '0');
});
