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

// How many calendar days apart two dates are, as seen in a time zone.
// We count calendar days (today, tomorrow, the day after...) rather than
// dividing hours by 24, because a day is not always 24 hours long: when the
// clocks change it is 23 or 25. Counting hours would make "tomorrow" wrong
// on those days. Date.UTC turns a year/month/day into a UTC timestamp, and
// UTC has no clock changes, so every day there is exactly 24 hours and the
// subtraction is safe.
function daysApart(now, deadline, timeZone) {
    const toUtcDay = (key) => {
        const [year, month, day] = key.split('-').map(Number);
        return Date.UTC(year, month - 1, day);
    };
    return Math.round((toUtcDay(dayKey(deadline, timeZone)) - toUtcDay(dayKey(now, timeZone))) / DAY_MS);
}

export function describeDeadline(deadlineIso, now, timeZone = undefined) {
    // new Date(...) gives an "Invalid Date" for unreadable text, whose
    // getTime() is NaN ("not a number"), so we check for that. We check
    // "now" too, because Intl.DateTimeFormat throws on an invalid date.
    const deadline = new Date(deadlineIso ?? '');
    if (deadlineIso == null || Number.isNaN(deadline.getTime())) return null;
    if (!(now instanceof Date) || Number.isNaN(now.getTime())) return null;

    const remaining = deadline.getTime() - now.getTime();
    if (remaining <= 0) return 'The deadline has passed. Your team is locked in for this gameweek.';
    if (remaining < HOUR_MS) return 'Under an hour to go. If you change nothing, your team stays as it is.';

    const days = daysApart(now, deadline, timeZone);
    if (days <= 0) return `Deadline's today at ${clockTime(deadline, timeZone)}.`;
    if (days === 1) return `Deadline's tomorrow at ${clockTime(deadline, timeZone)}.`;
    // days is 2 or more here, so the word "days" is always plural.
    if (days < 7) return `About ${days} days to go. Plenty of time.`;
    return 'Over a week to go. Plenty of time.';
}
