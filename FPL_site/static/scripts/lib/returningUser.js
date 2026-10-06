/***** returningUser.js *****/
// Works out whether someone has been away since before last gameweek's
// deadline, so the page can welcome them back warmly instead of assuming
// they know what happened.
export const LAST_VISIT_KEY = 'kj-last-visit';

export function welcomeBackMessage({ lastVisitIso, lastWeekGameweek, lastWeekDeadlineIso, thisWeekGameweek }) {
    if (!lastVisitIso || !lastWeekDeadlineIso || lastWeekGameweek == null) return null;

    // Date.parse turns an ISO date string into milliseconds since 1970,
    // which makes "is this before that?" a simple number comparison.
    // It returns NaN ("not a number") for text it can't read.
    const lastVisit = Date.parse(lastVisitIso);
    const deadline = Date.parse(lastWeekDeadlineIso);
    if (Number.isNaN(lastVisit) || Number.isNaN(deadline)) return null;
    if (lastVisit >= deadline) return null;

    const next = thisWeekGameweek != null ? `, and what matters for gameweek ${thisWeekGameweek}` : '';
    return `Welcome back! Gameweek ${lastWeekGameweek} played out while you were away. Here's how it went${next}.`;
}

export function readLastVisit(storage) {
    try {
        return storage.getItem(LAST_VISIT_KEY);
    } catch {
        return null;
    }
}

export function recordVisit(storage, now) {
    try {
        storage.setItem(LAST_VISIT_KEY, now.toISOString());
    } catch {
        // Not remembering a visit is harmless: they just won't get a welcome back.
    }
}
