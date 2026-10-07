import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createLatestGuard } from '../../FPL_site/static/scripts/lib/latestOnly.js';

test('an earlier token is stale once a later one has started', () => {
    const guard = createLatestGuard();
    const first = guard.start();
    const second = guard.start();
    assert.equal(guard.isLatest(first), false);
    assert.equal(guard.isLatest(second), true);
});

test('a lone token is current', () => {
    const guard = createLatestGuard();
    assert.equal(guard.isLatest(guard.start()), true);
});

test('guards are independent of each other', () => {
    const a = createLatestGuard();
    const b = createLatestGuard();
    const tokenA = a.start();
    b.start();
    b.start();
    assert.equal(a.isLatest(tokenA), true);
});
