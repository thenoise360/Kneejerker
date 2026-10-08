import { test } from 'node:test';
import assert from 'node:assert/strict';
import { toggleSelection, initialSelection, playerContextUrl, contextKey } from '../../FPL_site/static/scripts/lib/compareSelection.js';

test('ticking adds, ticking again removes', () => {
    assert.deepEqual(toggleSelection([], 5), ['5']);
    assert.deepEqual(toggleSelection(['5'], 5), []);
});

test('a third tick drops the oldest', () => {
    assert.deepEqual(toggleSelection(['1', '2'], 3), ['2', '3']);
});

test('the lean starts ticked', () => {
    assert.deepEqual(initialSelection({ suggested: { id: 351 } }), ['351']);
    assert.deepEqual(initialSelection({ suggested: null }), []);
    assert.deepEqual(initialSelection(null), []);
});

test('the details address carries the ids and the gameweek when known', () => {
    assert.equal(playerContextUrl([1, 2], 6), '/api/week/player-context?ids=1%2C2&gameweek=6');
    assert.equal(playerContextUrl(['7'], null), '/api/week/player-context?ids=7');
});

test('cache key follows the order given', () => {
    assert.equal(contextKey([1, 2]), '1,2');
});
