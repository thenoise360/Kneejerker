/***** weekV2.js *****/
// DOM glue for the rebuilt Week tab. All the
// decisions about *what* to show live in the pure modules under lib/; this
// file only reads the page, fetches data, and puts HTML on the page.
import { renderGuestRecap, renderPersonalRecap, renderTeamPrompt, renderMessage, renderRecapSkeleton, RECAP_LOAD_FAILED } from './lib/recapView.js';
import { safeLocalStorage } from './lib/safeStorage.js';
import { readTeamId, saveTeamId, clearTeamId, parseTeamId } from './lib/teamId.js';
import { renderHubBody } from './lib/hubView.js';
import { teamStatusSentence } from './lib/hubCopy.js';
import { welcomeBackMessage, readLastVisit, recordVisit } from './lib/returningUser.js';
import { createLatestGuard } from './lib/latestOnly.js';
import { renderDecision, renderDecisionSkeleton } from './lib/decisionView.js';
import { describeDeadline } from './lib/deadlineCopy.js';
import { renderCaptainView } from './lib/captainView.js';
import { renderPlayerSheet, renderPlayerSheetSkeleton, renderPlayerSheetMessage } from './lib/playerSheet.js';
import { toggleSelection, initialSelection, playerContextUrl, contextKey } from './lib/compareSelection.js';
import { COPY } from './lib/playerInfoCopy.js';

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
// The captain choice from the latest hub answer, and what the open sheet is doing.
let lastCaptaincy = null;
let compareSelected = [];
const sheetGuard = createLatestGuard();
const contextCache = new Map();  // "1,2" -> players, so reopening a sheet doesn't refetch

export function initializeWeekV2() {
    const lastWeekView = document.getElementById('last-week-view');
    // Only the Week page marks last-week-view with data-week-v2, so other pages do nothing here.
    if (!lastWeekView || lastWeekView.dataset.weekV2 !== 'true') return;
    // First, so the recap, decision and hub all start from the same team number.
    adoptTeamFromAddress();
    showWelcomeBack(lastWeekView);
    loadLastWeekRecap(lastWeekView);
    showDeadline();
    loadDecision();
    bindHubTeamForm(lastWeekView);
    bindCaptainRow();
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

    // Saved number first, then the visit-only one (see sessionTeamId above).
    const teamId = readTeamId(safeLocalStorage(window)) ?? sessionTeamId;
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
        if (saveTeamId(safeLocalStorage(window), input.value) === null) {
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
    const teamId = readTeamId(safeLocalStorage(window)) ?? sessionTeamId;
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
// If someone arrives that way we use that number for this visit. We do NOT save
// it yet: nobody has checked it is a real team, and a typo saved forever would
// keep showing the wrong view. loadHub saves it once the server says it's real.
function adoptTeamFromAddress() {
    const params = new URLSearchParams(window.location.search);
    if (!params.has('team_id')) return;
    const fromAddress = parseTeamId(params.get('team_id'));
    if (fromAddress !== null) sessionTeamId = fromAddress;
    // Take the number out of the address bar (keeping any other parameters) so
    // it doesn't leak into analytics page views, browser history or shared links.
    params.delete('team_id');
    const rest = params.toString();
    try {
        window.history.replaceState(null, '', window.location.pathname + (rest ? `?${rest}` : '') + window.location.hash);
    } catch {
        // Cosmetic and privacy only; the page works the same if this fails.
    }
}

// With JavaScript we can do better than a page reload: fetch just the hub for
// the typed number. preventDefault() stops the browser's own form submit.
function bindHubTeamForm(lastWeekView) {
    const form = document.getElementById('hub-team-form');
    const input = document.getElementById('hub-team-input');
    if (!form || !input) return;
    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        // Decide validity ourselves with parseTeamId (it returns null for
        // anything that isn't a good number). Saving is left until the server
        // confirms the team exists, so a typo never gets remembered.
        const typed = parseTeamId(input.value);
        if (typed === null) {
            input.setCustomValidity('Please enter the number only, for example 1234567.');
            input.reportValidity();
            return;
        }
        sessionTeamId = typed;  // used for this visit while we check it
        const data = await loadHub();
        // loadHub has saved the number by now if the server confirmed it. Only
        // then do the other sections switch to this team, so all three agree.
        if (data && data.team_status === 'ok') {
            loadDecision();
            if (lastWeekView) loadLastWeekRecap(lastWeekView);
        }
    });
    input.addEventListener('input', () => input.setCustomValidity(''));
}

// Fetches the hub as JSON and redraws its body with the conversational wording.
// If anything goes wrong we simply keep what the server already drew: that
// version is plainer, but it's correct, so there's nothing to "fix" on screen.
// Returns the response data, or null when it failed or a newer request took over,
// so callers only act on an answer that is still current.
async function loadHub() {
    const hub = document.getElementById('this-week-hub');
    const body = document.getElementById('hub-body');
    const teamSlot = document.getElementById('hub-team-slot');
    const teamStatus = document.getElementById('hub-team-status');
    if (!hub || !body || !hub.dataset.gameweek) return null;

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
        if (!hubGuard.isLatest(token)) return null;
        if (data.status === 'ready') {
            body.innerHTML = renderHubBody(data);
            lastCaptaincy = (data.decisions && data.decisions.captaincy) || null;
            hub.dataset.basedOn = data.based_on;
            // A known team doesn't need the "your team number" form any more.
            if (teamSlot) teamSlot.hidden = data.based_on === 'your_team';
            // textContent never interprets HTML; '' clears an old message.
            if (teamStatus) teamStatus.textContent = teamStatusSentence(data.team_status);
            if (teamId !== null) settleTeamNumber(teamId, data.team_status);
        }
        return data;
    } catch (err) {
        console.error("Failed to load this week's hub", err);
        return null;
    } finally {
        if (hubGuard.isLatest(token)) body.removeAttribute('aria-busy');
    }
}

// What to do with a team number once the server has judged it.
//  ok           -> a real team, so remember it for next visit (if storage allows).
//  not_found    -> a typo (or an old saved one): forget it so it can't stick forever.
//  unavailable  -> the official game may just be slow, so change nothing.
function settleTeamNumber(teamId, teamStatus) {
    if (teamStatus === 'ok') {
        saveTeamId(safeLocalStorage(window), teamId);
    } else if (teamStatus === 'not_found') {
        clearTeamId(safeLocalStorage(window));
        if (sessionTeamId === teamId) sessionTeamId = null;
    }
}

// ---------------------------------------------------------------------------
// Captain and vice view (read-only), shown in the global bottom sheet.
// What to show comes from lib/captainView.js and lib/playerSheet.js; this part
// only opens the sheet, fetches player details, and reacts to taps.
// ---------------------------------------------------------------------------

// One listener on the hub, because #hub-body is redrawn and its rows are replaced.
function bindCaptainRow() {
    const hub = document.getElementById('this-week-hub');
    if (!hub || hub.dataset.captainBound === 'true') return;
    hub.dataset.captainBound = 'true';
    const open = (event) => {
        const row = event.target.closest('[data-opens="captain"]');
        if (!row) return;
        event.preventDefault();
        openCaptainView();
    };
    hub.addEventListener('click', open);
    hub.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') open(event);
    });
}

function sheetElements() {
    const backdrop = document.getElementById('sheet-backdrop');
    const content = document.getElementById('sheet-content');
    return backdrop && content ? { backdrop, content } : null;
}

function closeSheet() {
    const els = sheetElements();
    if (els) els.backdrop.classList.remove('active');
    sheetGuard.start();  // anything still loading is now stale
}

function openCaptainView() {
    const els = sheetElements();
    if (!els || !lastCaptaincy) return;
    compareSelected = initialSelection(lastCaptaincy);
    els.backdrop.classList.add('active');
    // Assigned (not added) so reopening never stacks a second listener.
    els.backdrop.onclick = (event) => {
        if (event.target === els.backdrop || event.target.id === 'sheet-handle') closeSheet();
    };
    els.content.onclick = onSheetClick;
    showCaptainView();
}

function showCaptainView() {
    const els = sheetElements();
    if (!els) return;
    sheetGuard.start();
    const scroll = els.backdrop.querySelector('.sheet');
    const keep = scroll ? scroll.scrollTop : 0;
    els.content.innerHTML = renderCaptainView(lastCaptaincy, compareSelected);
    if (scroll) scroll.scrollTop = keep;
}

function onSheetClick(event) {
    const target = event.target.closest('[data-action]');
    if (!target) return;
    const { action, id } = target.dataset;
    if (action === 'close') closeSheet();
    else if (action === 'back') showCaptainView();
    else if (action === 'toggle-compare') {
        compareSelected = toggleSelection(compareSelected, id);
        showCaptainView();
    } else if (action === 'open-player') showPlayers([id]);
    else if (action === 'open-compare' && compareSelected.length === 2) showPlayers(compareSelected);
}

function backBar() {
    return `<div class="sheet-topbar"><button type="button" class="sheet-close" data-action="back">${COPY.back}</button></div>`;
}

async function fetchPlayers(ids) {
    const key = contextKey(ids);
    if (contextCache.has(key)) return contextCache.get(key);
    const hub = document.getElementById('this-week-hub');
    const res = await fetch(playerContextUrl(ids, hub ? hub.dataset.gameweek : null));
    if (!res.ok) throw new Error(`status ${res.status}`);
    const data = await res.json();
    if (data.status !== 'ready' || !Array.isArray(data.players)) return null;
    // Keep the order the person ticked them in, so colours match across views.
    const order = ids.map(String);
    const players = [...data.players].sort((a, b) => order.indexOf(String(a.id)) - order.indexOf(String(b.id)));
    contextCache.set(key, players);
    return players;
}

async function showPlayers(ids) {
    const els = sheetElements();
    if (!els) return;
    const token = sheetGuard.start();  // a newer tap makes this answer stale
    els.content.innerHTML = backBar() + renderPlayerSheetSkeleton();
    const scroller = els.backdrop.querySelector('.sheet');
    if (scroller) scroller.scrollTop = 0;
    try {
        const players = await fetchPlayers(ids);
        if (!sheetGuard.isLatest(token)) return;
        els.content.innerHTML = backBar() + (players && players.length
            ? renderPlayerSheet(players)
            : renderPlayerSheetMessage(COPY.loadFailed));
    } catch (err) {
        console.error('Failed to load player details', err);
        if (!sheetGuard.isLatest(token)) return;
        els.content.innerHTML = backBar() + renderPlayerSheetMessage(COPY.loadFailed);
    }
}
