import { test } from 'node:test';
import assert from 'node:assert/strict';
import { renderStrength, gaugeInputs, renderStrengthSkeleton } from '../../FPL_site/static/scripts/lib/strengthView.js';

const ready = {
    status: 'ready',
    team_name: 'Arsenal',
    headline: "Arsenal's attack is weaker this week",
    reason: 'Saka is likely to miss out.',
    scored: 1.5,
    scored_adjusted: 1.2,
    conceded: 1.0,
    conceded_adjusted: 1.1,
    league_scored: 1.5,
    missing: [{ name: 'Saka', position: 'midfielder', role: 'attack', share: 0.3, chance: 25 }],
};

test('verdict and reason first, with no digits before the details', () => {
    const html = renderStrength(ready);
    const [before, inside] = html.split('<details');
    assert.match(before, /<div class="outlook-phrase strength-verdict">Arsenal&#39;s attack is weaker this week<\/div>/);
    assert.match(before, /<p class="sub">Saka is likely to miss out\.<\/p>/);
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

test('two gauges render for a ready payload, each with a legend', () => {
    const html = renderStrength(ready);
    assert.equal((html.match(/<svg /g) || []).length, 2);
    assert.match(html, /aria-label="Attack: /);
    assert.match(html, /aria-label="Defence: /);
    assert.equal((html.match(/strength-swatch-tick/g) || []).length, 2);
    assert.equal((html.match(/strength-swatch-dot/g) || []).length, 2);
    assert.ok(html.includes('>Usual<') && html.includes('>This week<'));
});

test('gauge values are computed from the payload', () => {
    const g = gaugeInputs(ready);
    assert.ok(Math.abs(g.attack.value - 1.2 / 1.5) < 1e-9);
    assert.ok(Math.abs(g.attack.marker - 1.5 / 1.5) < 1e-9);
    assert.ok(Math.abs(g.defence.value - 1.5 / 1.1) < 1e-9);
    assert.ok(Math.abs(g.defence.marker - 1.5 / 1.0) < 1e-9);
    assert.equal(g.attack.min, 0.5);
    assert.equal(g.attack.max, 1.5);
});

test('aria labels are words only', () => {
    const labels = [...renderStrength(ready).matchAll(/aria-label="([^"]*)"/g)].map(m => m[1]);
    assert.ok(labels.length >= 2);
    for (const l of labels) assert.doesNotMatch(l, /\d/);
    assert.match(labels[0], /Attack: weaker than usual, below average for the league/);
});

test('missing or zero league_scored leaves the gauges out but keeps the rest', () => {
    for (const league_scored of [undefined, 0, null]) {
        const html = renderStrength({ ...ready, league_scored });
        assert.doesNotMatch(html, /<svg/);
        assert.match(html, /strength-verdict/);
        assert.match(html, /See the numbers/);
    }
});

test('no heading above 16 pixels: the verdict is not an h3', () => {
    assert.doesNotMatch(renderStrength(ready), /<h3/);
});
