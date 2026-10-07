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
    gauge: {
        attack: { now: 0.8, usual: 1, words: 'Attack: weaker than usual, below average for the league' },
        defence: { now: 1.364, usual: 1.5, words: 'Defence: leakier than usual, above average for the league' },
    },
    missing: [{ name: 'Saka', position: 'midfielder', role: 'attack', share: 0.3, chance: 25 }],
};

test('verdict and reason first, with no digits before the gauges', () => {
    const html = renderStrength(ready);
    const before = html.split('<div class="strength-gauges">')[0];
    assert.match(before, /<h3 class="outlook-phrase strength-verdict">Arsenal&#39;s attack is weaker this week<\/h3>/);
    assert.match(before, /<p class="sub">Saka is likely to miss out\.<\/p>/);
    // Look at the visible text only: drop tags (h3 has a digit) and escape codes such as &#39;.
    assert.doesNotMatch(before.replace(/<[^>]*>/g, '').replace(/&#\d+;/g, ''), /\d/);
    // The numbers are part of the card now, not behind "See the numbers".
    assert.doesNotMatch(html, /<details|See the numbers/);
});

test('each gauge carries its own figures: this week first, then usual', () => {
    const [attack, defence] = renderStrength(ready).split('<div class="strength-gauge">').slice(1);
    assert.match(attack, /<dt>This week<\/dt><dd>1\.2<\/dd><\/div>\s*<div><dt>Usual<\/dt><dd>1\.5<\/dd>/);
    assert.match(attack, /goals a game against an average side/);
    assert.match(defence, /<dt>This week<\/dt><dd>1\.1<\/dd><\/div>\s*<div><dt>Usual<\/dt><dd>1\.0<\/dd>/);
    assert.match(defence, /goals conceded a game against an average side/);
});

test('missing players are chips with their chance of playing', () => {
    const html = renderStrength(ready);
    assert.match(html, /Missing or doubtful this week/);
    assert.match(html, /<li class="strength-missing-chip">Saka <span class="strength-missing-chance">25% chance<\/span><\/li>/);
    assert.doesNotMatch(renderStrength({ ...ready, missing: [] }), /strength-missing/);
});

test('escapes every value', () => {
    const html = renderStrength({ ...ready, headline: '<b>x</b>', missing: [{ name: '<i>Bad</i>', chance: 0 }] });
    assert.doesNotMatch(html, /<b>x|<i>Bad/);
    assert.match(html, /&lt;i&gt;Bad&lt;\/i&gt; <span class="strength-missing-chance">0% chance/);
});

test('the dial colour and its words follow the server tone', () => {
    const toned = { ...ready, gauge: {
        attack: { ...ready.gauge.attack, tone: 'worse', versus: 'Weaker than usual' },
        defence: { ...ready.gauge.defence, tone: 'same', versus: 'The same as usual' } } };
    const [attack, defence] = renderStrength(toned).split('<div class="strength-gauge">').slice(1);
    assert.match(attack, /stroke="#D4145A"/);
    assert.match(attack, /<div class="strength-versus strength-versus--worse">Weaker than usual<\/div>/);
    assert.match(defence, /stroke="var\(--plum\)"/);
    assert.match(defence, /strength-versus--same">The same as usual/);
    // An unknown tone falls back to plum rather than an unstyled colour.
    const odd = renderStrength({ ...ready, gauge: { ...ready.gauge, attack: { ...ready.gauge.attack, tone: 'purple' } } });
    assert.doesNotMatch(odd, /strength-versus--purple|stroke="undefined"/);
});

test('not_ready renders the calm message', () => {
    const html = renderStrength({ status: 'not_ready', message: { title: 'On its way', body: 'Check back.' } });
    assert.match(html, /<h3 class="recap-verdict">On its way<\/h3>/);
    assert.doesNotMatch(html, /<details/);
});

test('skeleton is busy', () => {
    assert.match(renderStrengthSkeleton(), /aria-busy="true"/);
});

test('two gauges render for a ready payload, with one shared legend', () => {
    const html = renderStrength(ready);
    assert.equal((html.match(/<svg /g) || []).length, 2);
    assert.match(html, /aria-label="Attack: /);
    assert.match(html, /aria-label="Defence: /);
    assert.equal((html.match(/strength-swatch-tick/g) || []).length, 1);
    assert.equal((html.match(/strength-swatch-dot/g) || []).length, 1);
    assert.ok(html.includes('>Usual<') && html.includes('>This week<'));
});

test('gauge positions come straight from the server ratios', () => {
    const g = gaugeInputs(ready);
    assert.equal(g.attack.value, 0.8);
    assert.equal(g.attack.marker, 1);
    assert.equal(g.defence.value, 1.364);
    assert.equal(g.defence.marker, 1.5);
    for (const gauge of [g.attack, g.defence]) {
        assert.equal(gauge.min, 0.4);
        assert.equal(gauge.max, 1.8);
    }
});

test('the aria label is the server wording, with no digits', () => {
    const labels = [...renderStrength(ready).matchAll(/aria-label="([^"]*)"/g)].map(m => m[1]);
    assert.equal(labels[0], 'Attack: weaker than usual, below average for the league');
    assert.equal(labels[1], 'Defence: leakier than usual, above average for the league');
    for (const l of labels) assert.doesNotMatch(l, /\d/);
});

test('a missing gauge, or missing ratios, leaves the gauges out but keeps the rest', () => {
    const broken = [
        { gauge: undefined }, { gauge: null }, { gauge: {} },
        { gauge: { attack: { now: NaN, usual: 1, words: 'x' }, defence: { now: undefined, usual: 1, words: 'y' } } },
    ];
    for (const over of broken) {
        const html = renderStrength({ ...ready, ...over });
        assert.doesNotMatch(html, /<svg|NaN|strength-legend/);
        assert.match(html, /strength-verdict/);
        // The figures still show without their dials.
        assert.match(html, /<dd>1\.2<\/dd>/);
    }
});

test('one broken gauge is dropped and the other still draws', () => {
    const html = renderStrength({ ...ready, gauge: { ...ready.gauge, attack: { now: null, usual: 1, words: 'x' } } });
    assert.equal((html.match(/<svg /g) || []).length, 1);
    assert.doesNotMatch(html, /NaN/);
});

test('the verdict is a heading, styled by its own scoped class', () => {
    assert.match(renderStrength(ready), /<h3 class="outlook-phrase strength-verdict">/);
});

test('a slight headline never sits next to a gauge that says the same as usual', () => {
    // Server words for the reviewer reproduction: both figures round to 1.0 but the drop is slight.
    const html = renderStrength({
        ...ready, headline: "Arsenal's attack is a little weaker this week", scored: 1.0, scored_adjusted: 1.0,
        gauge: { ...ready.gauge, attack: { now: 0.71, usual: 0.75, words: 'Attack: a little weaker than usual, below average for the league' } },
    });
    assert.match(html, /a little weaker this week/);
    assert.doesNotMatch(html, /same as usual/);
    assert.match(html, /aria-label="Attack: a little weaker than usual/);
});

test('figures and missing players are opt in behind the card switch', () => {
    const html = renderStrength(ready);
    assert.match(html, /class="card kj-numbers" id="team-strength"/);
    assert.match(html, /<dl class="strength-figures kj-num">/);
    assert.match(html, /class="strength-missing kj-num"/);
    assert.match(html, /Show the numbers/);
    // Without a dial there is nothing else to look at, so the figures always show.
    const noDials = renderStrength({ ...ready, gauge: null });
    assert.match(noDials, /<dl class="strength-figures">/);
});
