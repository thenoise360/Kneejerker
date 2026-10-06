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

const PASSED = 'The deadline has passed. Your team is locked in for this gameweek.';
const UNDER_HOUR = 'Under an hour to go. If you change nothing, your team stays as it is.';

test('1ms before the deadline is still open; 1ms after has passed', () => {
    assert.equal(describeDeadline('2026-10-06T10:00:00Z', at('2026-10-06T09:59:59.999Z'), TZ), UNDER_HOUR);
    assert.equal(describeDeadline('2026-10-06T10:00:00Z', at('2026-10-06T10:00:00.001Z'), TZ), PASSED);
});

test('59m59s is under an hour; exactly 60m reads as today', () => {
    assert.equal(describeDeadline('2026-10-06T10:00:00Z', at('2026-10-06T09:00:01Z'), TZ), UNDER_HOUR);
    assert.equal(describeDeadline('2026-10-06T10:00:00Z', at('2026-10-06T09:00:00Z'), TZ), "Deadline's today at 11:00.");
});

test('Tuesday 20:00 to Thursday 06:00 is two calendar days, never "1 days"', () => {
    assert.equal(describeDeadline('2026-10-08T05:00:00Z', at('2026-10-06T19:00:00Z'), TZ),
        'About 2 days to go. Plenty of time.');
});

test('six calendar days is "About 6 days"; seven is over a week', () => {
    assert.equal(describeDeadline('2026-10-12T17:30:00Z', at('2026-10-06T09:00:00Z'), TZ),
        'About 6 days to go. Plenty of time.');
    assert.equal(describeDeadline('2026-10-13T17:30:00Z', at('2026-10-06T09:00:00Z'), TZ),
        'Over a week to go. Plenty of time.');
});

test('autumn clock change (25 hour day): today and tomorrow stay right', () => {
    // 2026-10-24T23:30Z is 00:30 on 25 October in London; the clocks go back that night.
    const now = at('2026-10-24T23:30:00Z');
    assert.equal(describeDeadline('2026-10-25T18:30:00Z', now, TZ), "Deadline's today at 18:30.");
    assert.equal(describeDeadline('2026-10-26T18:30:00Z', now, TZ), "Deadline's tomorrow at 18:30.");
});

test('spring clock change (23 hour day): tomorrow stays right', () => {
    // 2026-03-28T23:30Z is 23:30 on 28 March in London; the clocks go forward that night.
    const now = at('2026-03-28T23:30:00Z');
    assert.equal(describeDeadline('2026-03-29T17:30:00Z', now, TZ), "Deadline's tomorrow at 18:30.");
    assert.equal(describeDeadline('2026-03-30T17:30:00Z', now, TZ), 'About 2 days to go. Plenty of time.');
});

test('the same moment can be today in Sydney and tomorrow in London', () => {
    const now = at('2026-10-06T15:00:00Z'); // 16:00 6 Oct in London, 02:00 7 Oct in Sydney
    const deadline = '2026-10-07T10:00:00Z';
    assert.equal(describeDeadline(deadline, now, 'Europe/London'), "Deadline's tomorrow at 11:00.");
    assert.equal(describeDeadline(deadline, now, 'Australia/Sydney'), "Deadline's today at 21:00.");
});

test('an invalid now gives null instead of throwing', () => {
    assert.equal(describeDeadline('2026-10-06T10:00:00Z', new Date('nonsense'), TZ), null);
});
