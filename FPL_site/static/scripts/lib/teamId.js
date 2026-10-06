/***** teamId.js *****/
// Remembers which Fantasy Premier League team number is the visitor's, in
// the browser only (localStorage) - it is never stored on our server.
// Uses the same key as liveGameweek.js so entering it once works everywhere.
export const TEAM_ID_KEY = 'kj-fpl-team-id';

const MAX_DIGITS = 10;

// Returns a positive whole number, or null for anything else. A regular
// expression (/^\d+$/) checks the text is digits only, which rules out
// things like "1e5" or "-4" that Number() would otherwise accept.
export function parseTeamId(raw) {
    const text = String(raw ?? '').trim();
    if (!/^\d+$/.test(text) || text.length > MAX_DIGITS) return null;
    const id = Number(text);
    return id >= 1 ? id : null;
}

// localStorage can throw (private browsing, blocked cookies), so every
// access is wrapped in try/catch and falls back to "no team known".
export function readTeamId(storage) {
    try {
        return parseTeamId(storage.getItem(TEAM_ID_KEY));
    } catch {
        return null;
    }
}

export function saveTeamId(storage, raw) {
    const id = parseTeamId(raw);
    if (id === null) return null;
    try {
        storage.setItem(TEAM_ID_KEY, String(id));
    } catch {
        // Still return the id so this page view can use it.
    }
    return id;
}

// Forgets the saved team number, so a mistyped one can be replaced.
// Safe to call with blocked (null) storage.
export function clearTeamId(storage) {
    try {
        storage.removeItem(TEAM_ID_KEY);
    } catch {
        // Nothing stored, or storage blocked: either way there is nothing to forget.
    }
}
