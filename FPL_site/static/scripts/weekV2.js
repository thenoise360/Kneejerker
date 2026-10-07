/***** weekV2.js *****/
// DOM glue for the rebuilt Week tab. All the
// decisions about *what* to show live in the pure modules under lib/; this
// file only reads the page, fetches data, and puts HTML on the page.
import { renderGuestRecap, renderPersonalRecap, renderTeamPrompt, renderMessage, renderRecapSkeleton, RECAP_LOAD_FAILED } from './lib/recapView.js';
import { safeLocalStorage } from './lib/safeStorage.js';
import { readTeamId, saveTeamId, clearTeamId, parseTeamId } from './lib/teamId.js';
import { renderHubBody } from './lib/hubView.js';
import { welcomeBackMessage, readLastVisit, recordVisit } from './lib/returningUser.js';
import { createLatestGuard } from './lib/latestOnly.js';
import { renderDecision, renderDecisionSkeleton } from './lib/decisionView.js';
import { describeDeadline } from './lib/deadlineCopy.js';

// How often the deadline wording is refreshed while the page stays open.
const DEADLINE_REFRESH_MS = 60 * 1000;
// Remembered at module level so a second run of the setup can stop the first timer.
let deadlineTimer = null;
// One guard per slot: a slow older answer must never overwrite a newer one.
const recapGuard = createLatestGuard();
const decisionGuard = createLatestGuard();
const hubGuard = createLatestGuard();
// A team number we know about for this visit only. When the browser blocks
// storage we can't remember a number, but we must still use it for the page the
// person is looking at, or the hub would swap their team for the guest view.
let sessionTeamId = null;

export function initializeWeekV2() {
    const lastWeekView = document.getElementById('last-week-view');
    // Only the Week page marks last-week-view with data-week-v2, so other pages do nothing here.
    if (!lastWeekView || lastWeekView.dataset.weekV2 !== 'true') return;
    showWelcomeBack(lastWeekView);
    loadLastWeekRecap(lastWeekView);
    showDeadline();
    loadDecision();
    adoptTeamFromAddress();
    bindHubTeamForm();
    loadHub();
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

    const token = recapGuard.start();  // taken before the await, so older requests go stale
    guestSlot.innerHTML = renderRecapSkeleton();

    try {
        const res = await fetch(`/api/week/last-week-recap?${query}`);
        if (!res.ok) throw new Error(`status ${res.status}`);
        const data = await res.json();
        if (!recapGuard.isLatest(token)) return;  // a newer request has taken over
        if (data.status !== 'ready') {
            guestSlot.innerHTML = renderMessage(data.message);
            if (personalSlot) personalSlot.innerHTML = '';  // don't leave an old team's card showing
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
        if (!recapGuard.isLatest(token)) return;
        guestSlot.innerHTML = renderMessage(RECAP_LOAD_FAILED);
        if (personalSlot) personalSlot.innerHTML = '';
    }
}

// "Not your team? Change it": forget the saved number and show the prompt again.
function bindChangeTeam(personalSlot, lastWeekView) {
    const button = document.getElementById('recap-change-team');
    if (!button) return;
    button.addEventListener('click', () => {
        clearTeamId(safeLocalStorage(window));
        sessionTeamId = null;  // forget the visit-only copy too, or loadHub would still use it
        personalSlot.innerHTML = renderTeamPrompt();
        bindTeamForm(lastWeekView);
        loadDecision();  // no team number any more, so This week falls back to the everyone view
        loadHub();  // the hub personalises too
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
        // Decide validity ourselves: saveTeamId also returns null when storage is
        // blocked, and a perfectly good number shouldn't be rejected for that.
        const typed = parseTeamId(input.value);
        if (typed === null) {
            input.setCustomValidity('Please enter the number only, for example 1234567.');
            input.reportValidity();
            return;
        }
        loadLastWeekRecap(lastWeekView);
        loadDecision();  // a saved team number also personalises This week
        loadHub();  // the hub personalises too
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
        // If the visitor has moved to another tab, this element is gone from the
        // page, so stop the timer instead of letting it run forever.
        if (!el.isConnected) {
            clearInterval(deadlineTimer);
            deadlineTimer = null;
            return;
        }
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

    const token = decisionGuard.start();  // taken before the await, so older requests go stale
    slot.innerHTML = renderDecisionSkeleton();

    try {
        const res = await fetch(`/api/week/this-week-decision?${query}`);
        if (!res.ok) throw new Error(`status ${res.status}`);
        const data = await res.json();
        if (!decisionGuard.isLatest(token)) return;  // a newer request has taken over
        slot.innerHTML = renderDecision(data);
    } catch (err) {
        console.error("Failed to load this week's decision", err);
        if (!decisionGuard.isLatest(token)) return;
        slot.innerHTML = renderMessage({
            title: "We couldn't load this week's decision",
            body: 'Nothing is wrong on your side. Try again in a moment.',
        });
    }
}

// Without JavaScript, the hub's form reloads the page as /this-week?team_id=123.
// If someone arrives that way, remember the number they typed, the same as the
// other team forms do, so the next visit is personal straight away.
function adoptTeamFromAddress() {
    const fromAddress = parseTeamId(new URLSearchParams(window.location.search).get('team_id'));
    if (fromAddress === null) return;
    sessionTeamId = fromAddress;  // still works for this visit if storage is blocked
    saveTeamId(safeLocalStorage(window), fromAddress);
}

// With JavaScript we can do better than a page reload: save the number, then
// fetch just the hub. preventDefault() stops the browser's own form submit.
function bindHubTeamForm() {
    const form = document.getElementById('hub-team-form');
    const input = document.getElementById('hub-team-input');
    if (!form || !input) return;
    form.addEventListener('submit', (event) => {
        event.preventDefault();
        if (saveTeamId(safeLocalStorage(window), input.value) === null) {
            input.setCustomValidity('Please enter the number only, for example 1234567.');
            input.reportValidity();
            return;
        }
        sessionTeamId = typed;
        saveTeamId(safeLocalStorage(window), typed);  // remember it for next time, if storage allows
        loadHub();
        loadDecision();
    });
    input.addEventListener('input', () => input.setCustomValidity(''));
}

// Fetches the hub as JSON and redraws its body with the conversational wording.
// If anything goes wrong we simply keep what the server already drew: that
// version is plainer, but it's correct, so there's nothing to "fix" on screen.
async function loadHub() {
    const hub = document.getElementById('this-week-hub');
    const body = document.getElementById('hub-body');
    const teamSlot = document.getElementById('hub-team-slot');
    if (!hub || !body || !hub.dataset.gameweek) return;

    const query = new URLSearchParams({ gameweek: hub.dataset.gameweek });
    if (hub.dataset.lastGameweek) query.set('last_gameweek', hub.dataset.lastGameweek);
    // Saved number first; otherwise the visit-only one (see sessionTeamId above).
    const teamId = readTeamId(safeLocalStorage(window)) ?? sessionTeamId;
    if (teamId !== null) query.set('team_id', String(teamId));

    const token = hubGuard.start();  // a newer request makes this one stale
    body.setAttribute('aria-busy', 'true');
    try {
        const res = await fetch(`/api/week/this-week?${query}`);
        if (!res.ok) throw new Error(`status ${res.status}`);
        const data = await res.json();
        if (!hubGuard.isLatest(token)) return;
        if (data.status === 'ready') {
            body.innerHTML = renderHubBody(data);
            hub.dataset.basedOn = data.based_on;
            // A known team doesn't need the "your team number" form any more.
            if (teamSlot) teamSlot.hidden = data.based_on === 'your_team';
        }
    } catch (err) {
        console.error("Failed to load this week's hub", err);
    } finally {
        if (hubGuard.isLatest(token)) body.removeAttribute('aria-busy');
    }
}
