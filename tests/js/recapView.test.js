import { test } from 'node:test';
import assert from 'node:assert/strict';
import { escapeHtml } from '../../FPL_site/static/scripts/lib/escapeHtml.js';
import { renderGuestRecap, renderMessage, RECAP_LOAD_FAILED } from '../../FPL_site/static/scripts/lib/recapView.js';

const guest = {
    headline: 'A fairly typical week',
    reason: 'Haaland led the way with a hat-trick.',
    average_score: 48,
    highest_score: 126,
    standouts: [{ id: 1, name: 'Haaland', team: 'Manchester City', points: 17, reason: 'a hat-trick' }],
};

test('escapes player names', () => {
    assert.equal(escapeHtml(`<b>O'Brien</b> & co`), '&lt;b&gt;O&#39;Brien&lt;/b&gt; &amp; co');
    assert.equal(escapeHtml(null), '');
});

test('guest recap: verdict and reason first, then the figures as tiles and the standouts', () => {
    const html = renderGuestRecap(guest, 5);
    const [beforeTiles, tilesOn] = html.split('<div class="stat-tiles">');
    assert.match(beforeTiles, /A fairly typical week/);
    assert.match(beforeTiles, /Haaland led the way with a hat-trick\./);
    assert.doesNotMatch(beforeTiles, /48/);
    // Numbers are part of the card now, not behind a "See the numbers" expander.
    assert.doesNotMatch(html, /<details|See the numbers/);
    assert.match(tilesOn, /<span class="stat-tile-value">48<\/span><span class="stat-tile-label">Average points<\/span>/);
    assert.match(tilesOn, /<span class="stat-tile-value">126<\/span><span class="stat-tile-label">Highest points<\/span>/);
    assert.match(tilesOn, /Standout players/);
    assert.match(tilesOn, /A hat-trick/);
    assert.match(tilesOn, /Manchester City/);
});

test('guest recap without a highest score omits it', () => {
    const html = renderGuestRecap({ ...guest, highest_score: null }, 5);
    assert.doesNotMatch(html, /Highest points/);
});

test('guest recap escapes hostile names', () => {
    const hostile = { ...guest, standouts: [{ ...guest.standouts[0], name: '<img src=x>' }] };
    assert.doesNotMatch(renderGuestRecap(hostile, 5), /<img/);
});

test('message card renders title and body', () => {
    const html = renderMessage({ title: 'Nearly ready', body: 'Check back soon.' });
    assert.match(html, /Nearly ready/);
    assert.match(html, /Check back soon\./);
});

test('load-failure copy is calm and acronym free', () => {
    const text = RECAP_LOAD_FAILED.title + ' ' + RECAP_LOAD_FAILED.body;
    assert.doesNotMatch(text, /\b(FPL|GW|error)\b/i);
});

test('verdict headings carry the recap-verdict class so they pass contrast', () => {
    assert.match(renderGuestRecap(guest, 5), /<h3 class="recap-verdict">/);
    assert.match(renderMessage({ title: 'Not ready', body: 'Soon' }), /<h3 class="recap-verdict">/);
});

import { renderPersonalRecap, renderTeamPrompt } from '../../FPL_site/static/scripts/lib/recapView.js';

const personal = {
    status: 'ok', score: 61, average_score: 48, verdict: 'Above average. Nicely done.',
    verdict_tier: 'above',
    right_call: { tier: 'captain', title: 'Your captain call', reason: 'Captaining Salah paid off.', name: 'Salah', points: 12 },
};

test('personal recap: verdict and right call first, then your score beside the average', () => {
    const html = renderPersonalRecap(personal, 5);
    const [beforeTiles, tilesOn] = html.split('<div class="stat-tiles">');
    assert.match(beforeTiles, /Above average\. Nicely done\./);
    assert.match(beforeTiles, /Your captain call/);
    assert.doesNotMatch(beforeTiles.split('recap-call-points')[0], /61/);
    assert.match(tilesOn, /stat-tile--highlight"><span class="stat-tile-value">61<\/span><span class="stat-tile-label">Your points/);
    assert.match(tilesOn, /<span class="stat-tile-value">48<\/span><span class="stat-tile-label">Average points/);
    assert.doesNotMatch(html, /<details/);
});

test('personal recap: verdict heading carries the contrast-safe class', () => {
    assert.match(renderPersonalRecap(personal, 5), /<h3 class="recap-verdict">Above average/);
});

test('personal recap: team not found shows the server message', () => {
    const html = renderPersonalRecap({ status: 'team_not_found', message: { title: "We couldn't find that team", body: 'Double-check.' } }, 5);
    assert.match(html, /couldn&#39;t find that team/);
    assert.match(html, /recap-team-form/);  // offers to try another number
});

test('team prompt has an accessible labelled input', () => {
    const html = renderTeamPrompt();
    assert.match(html, /<label for="recap-team-input"/);
    assert.match(html, /inputmode="numeric"/);
    assert.doesNotMatch(html, /\bFPL\b/);
});

test('team prompt form skips native validation so our warm message shows', () => {
    assert.match(renderTeamPrompt(), /<form id="recap-team-form"[^>]*\bnovalidate\b/);
    assert.match(renderTeamPrompt(), /pattern="\[0-9\]\*"/);
});

test('personal recap: missing right call still renders without throwing', () => {
    const html = renderPersonalRecap({ ...personal, right_call: null }, 5);
    assert.match(html, /Above average\. Nicely done\./);
    assert.doesNotMatch(html, /undefined|<strong>/);
});

test('personal recap: the verdict and the call wording contain no digits', () => {
    const html = renderPersonalRecap(personal, 5);
    // Only the heading and the call sentence; the points tag and tiles come after.
    const words = html.split('<span class="recap-call-points">')[0];
    // The "your gameweek 5" label is the one allowed number; strip it, then no digits may remain.
    const visible = words.replace(/<[^>]+>/g, ' ').replace(/gameweek \d+/g, 'gameweek');
    assert.doesNotMatch(visible, /\d/);
});

test('personal recap: the right-call points sit on the call line', () => {
    const html = renderPersonalRecap(personal, 5);
    assert.match(html, /Captaining Salah paid off\. <span class="recap-call-points">Salah: 12 points<\/span><\/p>/);
});

test('personal recap: no right-call points line when points is not set', () => {
    const html = renderPersonalRecap({ ...personal, right_call: { ...personal.right_call, points: null } }, 5);
    assert.doesNotMatch(html, /recap-call-points|null|undefined/);
});

test('personal recap: the ok card offers a way to change the team', () => {
    const html = renderPersonalRecap(personal, 5);
    assert.match(html, /<button type="button" class="btn-pill secondary" id="recap-change-team">Not your team\? Change it<\/button>/);
});

test('personal recap: the change-team button is not on non-ok cards', () => {
    const html = renderPersonalRecap({ status: 'team_not_found', message: { title: 'T', body: 'B' } }, 5);
    assert.doesNotMatch(html, /recap-change-team/);
});

test('personal recap: unavailable shows the message only, with no team prompt', () => {
    const html = renderPersonalRecap({ status: 'unavailable', message: { title: "We can't reach your team", body: 'Try again soon.' } }, 5);
    assert.match(html, /Try again soon\./);
    assert.doesNotMatch(html, /recap-team-form|recap-change-team/);
});
