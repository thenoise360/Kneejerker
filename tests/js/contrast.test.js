import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { contrastRatio } from '../../FPL_site/static/scripts/lib/contrast.js';

// Read the real token out of style.css so the test checks what ships.
const css = readFileSync(new URL('../../FPL_site/static/content/style.css', import.meta.url), 'utf8');
const pinkInk = (css.match(/--pink-ink:\s*(#[0-9a-fA-F]{6})/) || [])[1];

test('black on white is the maximum ratio of 21', () => {
    assert.ok(Math.abs(contrastRatio('#000000', '#FFFFFF') - 21) < 0.001);
});
test('charcoal text on white is readable', () => {
    assert.ok(contrastRatio('#333333', '#FFFFFF') >= 4.5);
});
test('--pink-ink is defined in style.css', () => {
    assert.ok(pinkInk, 'expected --pink-ink: #RRGGBB in :root');
});
test('--pink-ink is readable on white and on off-white', () => {
    assert.ok(contrastRatio(pinkInk, '#FFFFFF') >= 4.5);
    assert.ok(contrastRatio(pinkInk, '#F9F9F9') >= 4.5);
});
test('the plain brand pink is NOT safe for text (why the token exists)', () => {
    assert.ok(contrastRatio('#F67CB0', '#FFFFFF') < 4.5);
});
