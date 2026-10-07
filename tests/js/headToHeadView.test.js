import { test } from 'node:test';
import assert from 'node:assert/strict';
import { meetingsSummary, meetingLine, renderLastMeetings } from '../../FPL_site/static/scripts/lib/headToHeadView.js';

const m = (result, extra = {}) => ({ season_label: '2025/26', is_home: true, result, score: '3–1', ...extra });

test('no meetings', () => {
    assert.equal(meetingsSummary([]), 'No Premier League meetings in recent seasons');
    assert.equal(meetingsSummary(undefined), 'No Premier League meetings in recent seasons');
});

test('exactly one meeting, each result', () => {
    assert.equal(meetingsSummary([m('won')]), 'Won the last meeting');
    assert.equal(meetingsSummary([m('drew')]), 'Drew the last meeting');
    assert.equal(meetingsSummary([m('lost')]), 'Lost the last meeting');
});

test('two meetings: boundary of unbeaten, winless and mixed', () => {
    assert.equal(meetingsSummary([m('won'), m('won')]), 'Unbeaten in the last two meetings');
    assert.equal(meetingsSummary([m('won'), m('drew')]), 'Unbeaten in the last two meetings');
    assert.equal(meetingsSummary([m('drew'), m('drew')]), 'Unbeaten in the last two meetings');
    assert.equal(meetingsSummary([m('lost'), m('lost')]), "Haven't beaten them in the last two meetings");
    assert.equal(meetingsSummary([m('drew'), m('lost')]), "Haven't beaten them in the last two meetings");
    assert.equal(meetingsSummary([m('won'), m('lost')]), 'Mixed results lately');
});

test('three meetings use a number word, never a digit', () => {
    assert.equal(meetingsSummary([m('won'), m('drew'), m('won')]), 'Unbeaten in the last three meetings');
    assert.equal(meetingsSummary([m('lost'), m('drew'), m('lost')]), "Haven't beaten them in the last three meetings");
    assert.equal(meetingsSummary([m('won'), m('lost'), m('drew')]), 'Mixed results lately');
    assert.doesNotMatch(meetingsSummary([m('won'), m('won'), m('won')]), /\d/);
});

test('a line reads season, venue, result and score', () => {
    assert.equal(meetingLine(m('won')), '2025/26 · home · won 3–1');
    assert.equal(meetingLine(m('lost', { is_home: false, score: '0–2' })), '2025/26 · away · lost 0–2');
});

test('block shows the summary, the list, and the background caveat', () => {
    const html = renderLastMeetings([m('won'), m('drew')]);
    assert.match(html, /Last meetings/);
    assert.match(html, /Unbeaten in the last two meetings/);
    assert.match(html, /2025\/26 · home · won 3–1/);
    assert.match(html, /Worth knowing, not a reason on its own/);
});

test('block with no meetings has no list', () => {
    const html = renderLastMeetings([]);
    assert.match(html, /No Premier League meetings in recent seasons/);
    assert.doesNotMatch(html, /<li/);
});

test('values are escaped', () => {
    const html = renderLastMeetings([m('won', { season_label: '<b>x</b>', score: '<i>' })]);
    assert.doesNotMatch(html, /<b>x/);
    assert.doesNotMatch(html, /<i>/);
});
