/***** weekV2.js *****/
// DOM glue for the rebuilt Week tab (behind FEATURE_WEEK_V2). All the
// decisions about *what* to show live in the pure modules under lib/; this
// file only fetches data and puts the resulting HTML on the page.
import { renderGuestRecap, renderMessage, RECAP_LOAD_FAILED } from './lib/recapView.js';

export function initializeWeekV2() {
    const lastWeekView = document.getElementById('last-week-view');
    // The flag-off page has no data-week-v2 attribute, so this is a no-op there.
    if (!lastWeekView || lastWeekView.dataset.weekV2 !== 'true') return;
    loadLastWeekRecap(lastWeekView);
}

async function loadLastWeekRecap(lastWeekView) {
    const gameweek = lastWeekView.dataset.gameweek;
    const slot = document.getElementById('last-week-recap-slot');
    // No finished gameweek: the server already rendered a friendly message.
    if (!gameweek || !slot) return;

    try {
        const res = await fetch(`/api/week/last-week-recap?gameweek=${encodeURIComponent(gameweek)}`);
        if (!res.ok) throw new Error(`status ${res.status}`);
        const data = await res.json();
        slot.innerHTML = data.status === 'ready'
            ? renderGuestRecap(data.guest, data.gameweek)
            : renderMessage(data.message);
    } catch (err) {
        console.error('Failed to load last week recap', err);
        slot.innerHTML = renderMessage(RECAP_LOAD_FAILED);
    }
}
