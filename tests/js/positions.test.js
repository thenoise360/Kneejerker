import test from 'node:test';
import assert from 'node:assert/strict';
import { positionLabel, POSITION_LABELS } from '../../FPL_site/static/scripts/lib/positions.js';

test('every position code becomes a plain word', () => {
    assert.equal(positionLabel('GKP'), 'Goalkeeper');
    assert.equal(positionLabel('DEF'), 'Defender');
    assert.equal(positionLabel('MID'), 'Midfielder');
    assert.equal(positionLabel('FWD'), 'Forward');
});
test('unknown codes pass through and missing ones are empty', () => {
    assert.equal(positionLabel('XYZ'), 'XYZ');
    assert.equal(positionLabel(undefined), '');
    assert.equal(positionLabel(null), '');
});
test('the label map is exported for lookups by code', () => {
    assert.equal(POSITION_LABELS.MID, 'Midfielder');
});

test('managers get a plain label and the ALL fallback is hidden', () => {
    assert.equal(positionLabel('MGR'), 'Manager');
    assert.equal(positionLabel('ALL'), '');
});
