import { test } from 'node:test';
import assert from 'node:assert/strict';
import { LAST_VISIT_KEY, welcomeBackMessage, readLastVisit, recordVisit } from '../../FPL_site/static/scripts/lib/returningUser.js';

const base = { lastWeekGameweek: 5, lastWeekDeadlineIso: '2026-10-03T10:00:00Z', thisWeekGameweek: 6 };

test('first ever visit gets no message', () => {
    assert.equal(welcomeBackMessage({ ...base, lastVisitIso: null }), null);
});

test('visited after last week\'s deadline: no message', () => {
    assert.equal(welcomeBackMessage({ ...base, lastVisitIso: '2026-10-04T09:00:00Z' }), null);
});

test('away since before last week\'s deadline: warm welcome pointing at this week', () => {
    const msg = welcomeBackMessage({ ...base, lastVisitIso: '2026-09-01T09:00:00Z' });
    assert.equal(msg, "Welcome back! Gameweek 5 played out while you were away. Here's how it went, and what matters for gameweek 6.");
});

test('no upcoming gameweek (off-season) still welcomes', () => {
    const msg = welcomeBackMessage({ ...base, thisWeekGameweek: null, lastVisitIso: '2026-09-01T09:00:00Z' });
    assert.equal(msg, "Welcome back! Gameweek 5 played out while you were away. Here's how it went.");
});

test('missing or garbled data never shows a message', () => {
    assert.equal(welcomeBackMessage({ ...base, lastVisitIso: 'garbage' }), null);
    assert.equal(welcomeBackMessage({ ...base, lastWeekDeadlineIso: '', lastVisitIso: '2026-09-01T09:00:00Z' }), null);
    assert.equal(welcomeBackMessage({ ...base, lastWeekGameweek: null, lastVisitIso: '2026-09-01T09:00:00Z' }), null);
});

test('records and reads the last visit, surviving blocked storage', () => {
    const data = {};
    const storage = { getItem: (k) => data[k] ?? null, setItem: (k, v) => { data[k] = v; } };
    recordVisit(storage, new Date('2026-10-06T12:00:00Z'));
    assert.equal(readLastVisit(storage), '2026-10-06T12:00:00.000Z');
    assert.equal(LAST_VISIT_KEY in data, true);
    const blocked = { getItem() { throw new Error('x'); }, setItem() { throw new Error('x'); } };
    assert.equal(readLastVisit(blocked), null);
    assert.doesNotThrow(() => recordVisit(blocked, new Date()));
});
