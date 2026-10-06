import { test } from 'node:test';
import assert from 'node:assert/strict';
import { describeDeadline } from '../../FPL_site/static/scripts/lib/deadlineCopy.js';

const TZ = 'Europe/London';
const at = (iso) => new Date(iso);

test('unreadable deadline gives null', () => {
    assert.equal(describeDeadline('nonsense', at('2026-10-06T09:00:00Z'), TZ), null);
    assert.equal(describeDeadline(null, at('2026-10-06T09:00:00Z'), TZ), null);
});

test('deadline already passed', () => {
    assert.equal(describeDeadline('2026-10-06T09:00:00Z', at('2026-10-06T09:00:00Z'), TZ),
        'The deadline has passed. Your team is locked in for this gameweek.');
});

test('under an hour: calm, not alarming', () => {
    assert.equal(describeDeadline('2026-10-06T10:00:00Z', at('2026-10-06T09:01:00Z'), TZ),
        "Under an hour to go. If you change nothing, your team stays as it is.");
});

test('later today, formats in the given time zone', () => {
    // 17:30 UTC is 18:30 in London during summer time.
    assert.equal(describeDeadline('2026-10-06T17:30:00Z', at('2026-10-06T09:00:00Z'), TZ),
        "Deadline's today at 18:30.");
});

test('tomorrow', () => {
    assert.equal(describeDeadline('2026-10-07T17:30:00Z', at('2026-10-06T09:00:00Z'), TZ),
        "Deadline's tomorrow at 18:30.");
});

test('a few days away', () => {
    assert.equal(describeDeadline('2026-10-09T17:30:00Z', at('2026-10-06T09:00:00Z'), TZ),
        'About 3 days to go. Plenty of time.');
});

test('over a week away', () => {
    assert.equal(describeDeadline('2026-10-20T17:30:00Z', at('2026-10-06T09:00:00Z'), TZ),
        'Over a week to go. Plenty of time.');
});
