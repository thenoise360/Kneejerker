import { test } from 'node:test';
import assert from 'node:assert/strict';
import { renderDecision } from '../../FPL_site/static/scripts/lib/decisionView.js';

const decision = {
    kind: 'captain', title: 'Captain: Salah stands out',
    reason: "Across every team, Salah is the strongest option we're seeing. It's your call.",
    details: ['Our prediction for Salah: about 8.0 points'],
};

test('decision shows title and reason by default, numbers in details', () => {
    const html = renderDecision({ decision, based_on: 'everyone', squad_gameweek: null });
    const [before, inside] = html.split('<details');
    assert.match(before, /Captain: Salah stands out/);
    assert.match(before, /your call/);
    assert.doesNotMatch(before, /8\.0/);
    assert.match(inside, /about 8\.0 points/);
});

test('says which team it is based on', () => {
    const html = renderDecision({ decision, based_on: 'your_team', squad_gameweek: 5 });
    assert.match(html, /Based on your team from gameweek 5/);
});

test('no decision shows the calm message', () => {
    const html = renderDecision({ decision: null, message: { title: 'Nothing pressing yet', body: 'Check back.' } });
    assert.match(html, /Nothing pressing yet/);
});

test('icon is paired with a text label, never colour alone', () => {
    const html = renderDecision({ decision: { ...decision, kind: 'availability' }, based_on: 'everyone' });
    assert.match(html, /aria-hidden="true"/);
    assert.match(html, /Player availability/);
});

test('decision heading carries the readable verdict class', () => {
    const html = renderDecision({ decision, based_on: 'everyone', squad_gameweek: null });
    assert.match(html, /<h3 class="recap-verdict">Captain: Salah stands out<\/h3>/);
});

test('no digit appears before the details element', () => {
    const captain = {
        kind: 'captain', title: 'Captain: Salah stands out',
        reason: "Across every team, Salah is the strongest option we're seeing. It's your call.",
        details: ['We expect Salah to be involved in about 1.2 goals this week'],
    };
    // Everyone view, so there is no "Based on your team from gameweek N" line.
    const html = renderDecision({ decision: captain, based_on: 'everyone', squad_gameweek: null });
    const [before, inside] = html.split('<details');
    // Escaped apostrophes (&#39;) contain digits but are not numbers a reader sees.
    // Tags such as <h3> also contain digits, so only the visible text is checked.
    const visible = before.replace(/<[^>]*>/g, ' ').replace(/&#\d+;/g, "'");
    assert.doesNotMatch(visible, /\d/);
    assert.match(inside, /1\.2 goals/);
});

test('skeleton is marked busy', async () => {
    const { renderDecisionSkeleton } = await import('../../FPL_site/static/scripts/lib/decisionView.js');
    assert.match(renderDecisionSkeleton(), /aria-busy="true"/);
});
