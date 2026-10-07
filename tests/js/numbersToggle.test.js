import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { numbersToggle, NUMBERS_LABEL } from '../../FPL_site/static/scripts/lib/numbersToggle.js';

test('the switch is a real checkbox inside a label, with words', () => {
    const html = numbersToggle();
    assert.match(html, /^<label class="numbers-toggle"><input type="checkbox" class="numbers-toggle-input"> <span>Show the numbers<\/span><\/label>$/);
    assert.equal(NUMBERS_LABEL, 'Show the numbers');
});

test('the stylesheet hides opt-in numbers until their card switch is ticked', () => {
    const css = readFileSync(new URL('../../FPL_site/static/content/style.css', import.meta.url), 'utf8');
    assert.match(css, /\.kj-numbers:not\(:has\(\.numbers-toggle-input:checked\)\) \.kj-num \{ display: none !important; \}/);
});
