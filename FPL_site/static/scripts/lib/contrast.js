/***** contrast.js *****/
// Text is only readable if it stands out enough from its background. The web
// accessibility guidelines (WCAG) measure that as a "contrast ratio" from 1
// (identical colours) to 21 (black on white), and ask for at least 4.5 for
// normal-sized text. This works the ratio out so a test can prove a colour
// is safe, instead of us judging it by eye.

// Turns "#RRGGBB" (or "#RGB") into a brightness figure between 0 and 1 that
// accounts for how the eye sees green as brighter than blue.
export function relativeLuminance(hex) {
    let h = String(hex).replace('#', '');
    if (h.length === 3) h = h.split('').map(c => c + c).join('');
    const [r, g, b] = [0, 2, 4].map(i => {
        const channel = parseInt(h.slice(i, i + 2), 16) / 255;
        // Screens store colour on a curve; undo it to get true light levels.
        return channel <= 0.03928 ? channel / 12.92 : Math.pow((channel + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

// (lighter + 0.05) / (darker + 0.05). Order of the two colours doesn't matter.
export function contrastRatio(hexA, hexB) {
    const a = relativeLuminance(hexA);
    const b = relativeLuminance(hexB);
    const [lighter, darker] = a >= b ? [a, b] : [b, a];
    return (lighter + 0.05) / (darker + 0.05);
}
