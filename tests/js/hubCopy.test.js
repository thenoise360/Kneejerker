import { test } from 'node:test';
import assert from 'node:assert/strict';
import { headlineSentence, rowSentence, joinNames } from '../../FPL_site/static/scripts/lib/hubCopy.js';

const ACRONYMS = [/\bGW\s?\d/, /\bFPL\b/, /\bVC\b/, /\bpts\b/, /\bEO\b/, /\bxG\b/];
const HEADLINES = [
    { reason_key: 'starter_doubt', player: 'Rice', tier: 'high' },
    { reason_key: 'starter_doubt', player: 'Rice', tier: 'confirmed' },
    { reason_key: 'starter_blank', player: 'Saka', players: ['Saka', 'Rice'] },
    { reason_key: 'unused_free_transfers', count: 2 },
    { reason_key: 'captain_choice', player: 'Haaland' },
    { reason_key: 'captain_no_prediction', player: null },
];

test('every headline key has a sentence with no acronyms', () => {
    for (const h of HEADLINES) {
        const sentence = headlineSentence(h);
        assert.ok(sentence.length > 10, h.reason_key);
        for (const pattern of ACRONYMS) assert.doesNotMatch(sentence, pattern);
    }
});

test('the same input always gives the same sentence', () => {
    assert.equal(headlineSentence(HEADLINES[0]), headlineSentence({ ...HEADLINES[0] }));
});

test('advice is a suggestion, never an order', () => {
    assert.match(headlineSentence(HEADLINES[4]), /your call/i);
    assert.match(rowSentence('captaincy', { state: 'needs_look', suggested: { name: 'Haaland' }, vice: { name: 'Salah' } }), /your call/i);
});

test('names join naturally', () => {
    assert.equal(joinNames(['A']), 'A');
    assert.equal(joinNames(['A', 'B']), 'A and B');
    assert.equal(joinNames(['A', 'B', 'C']), 'A, B and C');
});

test('injury rows cover all three states', () => {
    assert.match(rowSentence('injuries', { state: 'needs_look', players: [{ name: 'Rice' }] }), /Rice/);
    assert.match(rowSentence('injuries', { state: 'nothing_to_do', players: [] }), /Nothing to do/);
    assert.match(rowSentence('injuries', { state: 'needs_team', players: [] }), /team number/);
});
