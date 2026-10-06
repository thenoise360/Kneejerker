/***** weekV2.js *****/
// DOM glue for the rebuilt Week tab (behind FEATURE_WEEK_V2). All the
// decisions about *what* to show live in the pure modules under lib/; this
// file only reads the page, fetches data, and puts HTML on the page.
import { renderGuestRecap, renderPersonalRecap, renderTeamPrompt, renderMessage, RECAP_LOAD_FAILED } from './lib/recapView.js';
import { safeLocalStorage } from './lib/safeStorage.js';
import { readTeamId, saveTeamId, clearTeamId } from './lib/teamId.js';
import { welcomeBackMessage, readLastVisit, recordVisit } from './lib/returningUser.js';

export function initializeWeekV2() {
    const lastWeekView = document.getElementById('last-week-view');
    // The flag-off page has no data-week-v2 attribute, so this is a no-op there.
    if (!lastWeekView || lastWeekView.dataset.weekV2 !== 'true') return;
    showWelcomeBack(lastWeekView);
    loadLastWeekRecap(lastWeekView);
}

function showWelcomeBack(lastWeekView) {
    const banner = document.getElementById('welcome-back-banner');
    // Read the previous visit *before* recording this one.
    const message = welcomeBackMessage({
        lastVisitIso: readLastVisit(safeLocalStorage(window)),
        lastWeekGameweek: lastWeekView.dataset.gameweek ? Number(lastWeekView.dataset.gameweek) : null,
        lastWeekDeadlineIso: lastWeekView.dataset.deadline || null,
        thisWeekGameweek: lastWeekView.dataset.thisWeekGameweek ? Number(lastWeekView.dataset.thisWeekGameweek) : null,
    });
    recordVisit(safeLocalStorage(window), new Date());
    if (banner && message) {
        banner.textContent = message;  // textContent never interprets HTML
        banner.hidden = false;
    }
}

async function loadLastWeekRecap(lastWeekView) {
    const gameweek = lastWeekView.dataset.gameweek;
    const guestSlot = document.getElementById('last-week-recap-slot');
    const personalSlot = document.getElementById('personal-recap-slot');
    if (!gameweek || !guestSlot) return;  // server already rendered a friendly message

    const teamId = readTeamId(safeLocalStorage(window));
    const query = new URLSearchParams({ gameweek });
    if (teamId !== null) query.set('team_id', String(teamId));

    try {
        const res = await fetch(`/api/week/last-week-recap?${query}`);
        if (!res.ok) throw new Error(`status ${res.status}`);
        const data = await res.json();
        if (data.status !== 'ready') {
            guestSlot.innerHTML = renderMessage(data.message);
            return;
        }
        guestSlot.innerHTML = renderGuestRecap(data.guest, data.gameweek);
        if (personalSlot) {
            personalSlot.innerHTML = data.personal
                ? renderPersonalRecap(data.personal, data.gameweek)
                : renderTeamPrompt();
            bindTeamForm(lastWeekView);
            bindChangeTeam(personalSlot, lastWeekView);
        }
    } catch (err) {
        console.error('Failed to load last week recap', err);
        guestSlot.innerHTML = renderMessage(RECAP_LOAD_FAILED);
    }
}

// "Not your team? Change it": forget the saved number and show the prompt again.
function bindChangeTeam(personalSlot, lastWeekView) {
    const button = document.getElementById('recap-change-team');
    if (!button) return;
    button.addEventListener('click', () => {
        clearTeamId(safeLocalStorage(window));
        personalSlot.innerHTML = renderTeamPrompt();
        bindTeamForm(lastWeekView);
    });
}

// The form is re-created each time the slot is redrawn, so the listener is
// attached fresh every time rather than once on page load.
function bindTeamForm(lastWeekView) {
    const form = document.getElementById('recap-team-form');
    const input = document.getElementById('recap-team-input');
    if (!form || !input) return;
    form.addEventListener('submit', (event) => {
        event.preventDefault();  // stop the browser reloading the page
        if (saveTeamId(safeLocalStorage(window), input.value) === null) {
            input.setCustomValidity('Please enter the number only, for example 1234567.');
            input.reportValidity();
            return;
        }
        loadLastWeekRecap(lastWeekView);
    });
    input.addEventListener('input', () => input.setCustomValidity(''));
}
