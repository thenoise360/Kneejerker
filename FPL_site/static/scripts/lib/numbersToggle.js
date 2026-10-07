/***** numbersToggle.js *****/
// Every card makes one point by default. The figures behind that point are
// opt in: a small "Show the numbers" switch at the bottom of the card reveals
// them in place, inside the same dial, row or tile, rather than as a separate
// list underneath.
//
// How it works, with no JavaScript at all:
//   - the card's outer element gets the class "kj-numbers";
//   - every figure that should wait for the switch gets the class "kj-num";
//   - numbersToggle() below gives the switch, a checkbox inside a label.
// style.css hides each .kj-num until the checkbox in its card is ticked
// (using the CSS :has() selector). Because it is pure CSS, it keeps working
// when a carousel redraws a card from an HTML string.
//
// Browsers too old for :has() simply show the numbers all the time, so nobody
// ever loses information.

export const NUMBERS_LABEL = 'Show the numbers';

export function numbersToggle(label = NUMBERS_LABEL) {
    // A real checkbox inside a label: keyboard (Space) and screen readers work
    // without any extra code, and the label text says what it does.
    return `<label class="numbers-toggle"><input type="checkbox" class="numbers-toggle-input"> <span>${label}</span></label>`;
}
