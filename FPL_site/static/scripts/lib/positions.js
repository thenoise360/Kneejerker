/***** positions.js *****/
// The database stores a player's position as a short code like "MID".
// Short codes are for the code, not for people, so anything shown on screen
// goes through positionLabel() to become a plain word like "Midfielder".
// The codes themselves are still used behind the scenes (for example to ask
// for the right position average), so never overwrite them with the labels.
export const POSITION_LABELS = { GKP: 'Goalkeeper', DEF: 'Defender', MID: 'Midfielder', FWD: 'Forward' };

// Returns the plain word for a code. An unknown code is returned unchanged
// rather than hidden, and a missing one becomes an empty string.
export function positionLabel(code) {
    if (code === null || code === undefined) return '';
    return POSITION_LABELS[code] || String(code);
}
