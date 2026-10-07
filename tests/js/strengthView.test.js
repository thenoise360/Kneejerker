import { test } from 'node:test';
import assert from 'node:assert/strict';
import { renderStrength, renderStrengthSkeleton } from '../../FPL_site/static/scripts/lib/strengthView.js';

const ready = {
    status: 'ready',
    team_name: 'Arsenal',
    headline: "Arsenal's attack is weaker this week",
    reason: 'Saka is likely to miss out.',
    scored: 1.5,
    scored_adjusted: 1.2,
    conceded: 1.0,
    conceded_adjusted: 1.1,
    missing: [{ name: 'Saka', position: 'midfielder', role: 'attack', share: 0.3, chance: 25 }],
};

test('verdict and reason first, with no digits before the details', () => {
    const html = renderStrength(ready);
    const [before, inside] = html.split('<details');
    assert.match(before, /<h3 class="recap-verdict">Arsenal&#39;s attack is weaker this week<\/h3>/);
    assert.match(before, /<p>Saka is likely to miss out\.<\/p>/);
    // Look at the visible text only: drop tags (h3 has a digit) and escape codes such as &#39;.
    assert.doesNotMatch(before.replace(/<[^>]*>/g, '').replace(/&#\d+;/g, ''), /\d/);
    assert.match(inside, /<summary>See the numbers<\/summary>/);
});

test('numbers live inside the details', () => {
    const inside = renderStrength(ready).split('<details')[1];
    assert.match(inside, /Goals a game against an average side: 1\.5 \(1\.2 with this week's absences\)/);
    assert.match(inside, /Goals conceded a game against an average side: 1\.0 \(1\.1 with this week's absences\)/);
    assert.match(inside, /<li>Saka: 25% chance of playing<\/li>/);
});

test('escapes every value', () => {
    const html = renderStrength({ ...ready, headline: '<b>x</b>', missing: [{ name: '<i>Bad</i>', chance: 0 }] });
    assert.doesNotMatch(html, /<b>x|<i>Bad/);
    assert.match(html, /&lt;i&gt;Bad&lt;\/i&gt;: 0% chance of playing/);
});

test('not_ready renders the calm message', () => {
    const html = renderStrength({ status: 'not_ready', message: { title: 'On its way', body: 'Check back.' } });
    assert.match(html, /<h3 class="recap-verdict">On its way<\/h3>/);
    assert.doesNotMatch(html, /<details/);
});

test('skeleton is busy', () => {
    assert.match(renderStrengthSkeleton(), /aria-busy="true"/);
});
