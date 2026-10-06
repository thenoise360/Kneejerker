/***** deadlineCopy.js *****/
// Turns the deadline into calm, human wording ("Deadline's tomorrow at
// 18:30") instead of a ticking countdown. Times are shown in the visitor's
// own time zone unless one is passed in (tests pass one so they're stable).
const HOUR_MS = 60 * 60 * 1000;
const DAY_MS = 24 * HOUR_MS;

// "2026-10-06" for a date as seen in a given time zone. Intl.DateTimeFormat
// is the browser's built-in date formatter; 'en-CA' happens to format dates
// as year-month-day, which makes two days easy to compare as text.
// If timeZone is undefined, the browser uses the visitor's own time zone.
function dayKey(date, timeZone) {
    return new Intl.DateTimeFormat('en-CA', { timeZone, year: 'numeric', month: '2-digit', day: '2-digit' }).format(date);
}

// "18:30" for a date as seen in a given time zone. 'en-GB' gives a 24-hour
// clock, so we never have to deal with "6:30 pm".
function clockTime(date, timeZone) {
    return new Intl.DateTimeFormat('en-GB', { timeZone, hour: '2-digit', minute: '2-digit' }).format(date);
}

export function describeDeadline(deadlineIso, now, timeZone = undefined) {
    // new Date(...) gives an "Invalid Date" for unreadable text, whose
    // getTime() is NaN ("not a number"), so we check for that.
    const deadline = new Date(deadlineIso ?? '');
    if (deadlineIso == null || Number.isNaN(deadline.getTime())) return null;

    const remaining = deadline.getTime() - now.getTime();
    if (remaining <= 0) return 'The deadline has passed. Your team is locked in for this gameweek.';
    if (remaining < HOUR_MS) return 'Under an hour to go. If you change nothing, your team stays as it is.';

    // Compare calendar days in the chosen time zone, not 24-hour spans,
    // so "tomorrow" means tomorrow on the visitor's clock.
    const deadlineDay = dayKey(deadline, timeZone);
    if (deadlineDay === dayKey(now, timeZone)) return `Deadline's today at ${clockTime(deadline, timeZone)}.`;
    if (deadlineDay === dayKey(new Date(now.getTime() + DAY_MS), timeZone)) {
        return `Deadline's tomorrow at ${clockTime(deadline, timeZone)}.`;
    }
    if (remaining < 7 * DAY_MS) return `About ${Math.round(remaining / DAY_MS)} days to go. Plenty of time.`;
    return 'Over a week to go. Plenty of time.';
}
