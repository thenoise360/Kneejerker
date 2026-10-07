/***** weekV2.js *****/
// DOM glue for the rebuilt Week tab (behind FEATURE_WEEK_V2). All the
// decisions about *what* to show live in the pure modules under lib/; this
// file only reads the page, fetches data, and puts HTML on the page.
import { renderGuestRecap, renderPersonalRecap, renderTeamPrompt, renderMessage, RECAP_LOAD_FAILED } from './lib/recapView.js';
import { safeLocalStorage } from './lib/safeStorage.js';
import { readTeamId, saveTeamId, clearTeamId } from './lib/teamId.js';
import { welcomeBackMessage, readLastVisit, recordVisit } from './lib/returningUser.js';
import { renderDecision } from './lib/decisionView.js';
import { describeDeadline } from './lib/deadlineCopy.js';

// How often the deadline wording is refreshed while the page stays open.
const DEADLINE_REFRESH_MS = 60 * 1000;
// Remembered at module level so a second run of the setup can stop the first timer.
let deadlineTimer = null;

export function initializeWeekV2() {
    const lastWeekView = document.getElementById('last-week-view');
    // The flag-off page has no data-week-v2 attribute, so this is a no-op there.
    if (!lastWeekView || lastWeekView.dataset.weekV2 !== 'true') return;
    showWelcomeBack(lastWeekView);
    loadLastWeekRecap(lastWeekView);
    showDeadline();
    loadDecision();
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
        loadDecision();  // no team number any more, so This week falls back to the everyone view
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
        loadDecision();  // a saved team number also personalises This week
    });
    input.addEventListener('input', () => input.setCustomValidity(''));
}

// Writes the calm deadline wording, then keeps it fresh. The wording depends on
// the time now (for example "tomorrow" becomes "today", then "has passed"), so
// we re-run it every minute while the page is open.
function showDeadline() {
    const el = document.getElementById('deadline-copy');
    if (!el || !el.dataset.deadline) return;

    function update() {
        // No time zone passed, so the browser shows the visitor's local time.
        el.textContent = describeDeadline(el.dataset.deadline, new Date()) || '';
    }
    update();

    // Switching tabs re-runs this setup without a page reload. Clear the old
    // timer first, or every visit would stack up another timer that never stops.
    if (deadlineTimer !== null) clearInterval(deadlineTimer);
    deadlineTimer = setInterval(update, DEADLINE_REFRESH_MS);
}

async function loadDecision() {
    const hub = document.getElementById('decision-hub');
    const slot = document.getElementById('decision-slot');
    if (!hub || !slot || !hub.dataset.gameweek) return;

    const query = new URLSearchParams({ gameweek: hub.dataset.gameweek });
    if (hub.dataset.lastGameweek) query.set('last_gameweek', hub.dataset.lastGameweek);
    // safeLocalStorage copes with blocked storage, so a failure here never
    // leaves the loading skeleton spinning.
    const teamId = readTeamId(safeLocalStorage(window));
    if (teamId !== null) query.set('team_id', String(teamId));

    try {
        const res = await fetch(`/api/week/this-week-decision?${query}`);
        if (!res.ok) throw new Error(`status ${res.status}`);
        slot.innerHTML = renderDecision(await res.json());
    } catch (err) {
        console.error("Failed to load this week's decision", err);
        slot.innerHTML = renderMessage({
            title: "We couldn't load this week's decision",
            body: 'Nothing is wrong on your side. Try again in a moment.',
        });
    }
}
