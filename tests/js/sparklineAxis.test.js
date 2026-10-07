import test from 'node:test';
import assert from 'node:assert/strict';
import { buildSparkline } from '../../FPL_site/static/scripts/visuals.js';

test('the sparkline axis maximum is a whole number', () => {
    const html = buildSparkline([1, 2, 3, 2, 1], [4.67, 4.67, 4.67, 4.67, 4.67]);
    assert.ok(!html.includes('4.67</text>'));
    assert.ok(html.includes('>5</text>'));
});
