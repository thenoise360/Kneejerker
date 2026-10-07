import test from 'node:test';
import assert from 'node:assert/strict';
import { SEASON_STATS } from '../../FPL_site/static/scripts/visuals.js';

test('season stat labels use the pound sign, never GBP', () => {
    for (const s of SEASON_STATS) assert.ok(!/GBP/.test(s.label), s.label);
    assert.ok(SEASON_STATS.some(s => s.label === 'Points per £1m'));
});
