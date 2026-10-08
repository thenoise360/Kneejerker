import { test } from 'node:test';
import assert from 'node:assert/strict';
import { renderHubBody } from '../../FPL_site/static/scripts/lib/hubView.js';

const data = {
    status: 'ready', based_on: 'your_team',
    headline: { decision: 'captaincy', reason_key: 'captain_choice', player: '<b>Haaland</b>' },
    decisions: {
        injuries: { state: 'nothing_to_do', players: [] },
        transfers: { state: 'not_ready' }, chips: { state: 'not_ready' },
        captaincy: { state: 'needs_look', suggested: { name: 'Haaland' }, vice: { name: 'Salah' }, shortlist: [] },
    },
};

test('matches the server markup hooks', () => {
    const html = renderHubBody(data);
    assert.match(html, /class="card hub-headline"/);
    assert.match(html, /data-key="captaincy" data-state="needs_look"/);
    assert.doesNotMatch(html, /data-key="transfers"/);
});

test('escapes names so player data can never inject HTML', () => {
    assert.doesNotMatch(renderHubBody(data), /<b>Haaland<\/b>/);
});

test('every state badge has words next to its icon', () => {
    assert.match(renderHubBody(data), /<span aria-hidden="true">✓<\/span> Nothing to do this week/);
});

test('the captain row is tappable only when there is a lean to look into', () => {
    const withLean = renderHubBody(data);
    assert.match(withLean, /data-key="captaincy"[^>]*data-opens="captain" role="button" tabindex="0"/);
    assert.match(withLean, /See the options/);
    const noLean = renderHubBody({ ...data, decisions: { ...data.decisions, captaincy: { state: 'needs_look', suggested: null, shortlist: [] } } });
    assert.ok(!noLean.includes('data-opens'));
});

test('an unavailable hub shows the calm message', () => {
    assert.match(renderHubBody({ status: 'unavailable' }), /We couldn't load this week's decisions/);
});
