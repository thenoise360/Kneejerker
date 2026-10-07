/***** home.js *****/
import {
    updateLastUpdatedTime,
    isUserActive
} from './utils.js';
import { planWeekRender } from './weekState.js';
import { initializeLiveGameweek, stopLiveGameweekPolling } from './liveGameweek.js';
import { initializeWeekV2 } from './weekV2.js';
import { safeLocalStorage } from './lib/safeStorage.js';

document.addEventListener('DOMContentLoaded', function () {
    initializeHome();
});

// 06.0: renders whichever gw-panel matches the state the server computed
// (live / closed / none) and shows the one-shot transition message when a
// gameweek has just flipped from live to closed.
function initializeWeekState() {
    const container = document.getElementById('this-week-view');
    if (!container) return;

    const gwState = {
        state: container.dataset.gwState || 'none',
        gameweek: container.dataset.gwNumber ? parseInt(container.dataset.gwNumber, 10) : null,
    };

    const plan = planWeekRender(gwState, safeLocalStorage(window));

    ['live', 'closed', 'none'].forEach((panelName) => {
        const panel = document.getElementById(`gw-panel-${panelName}`);
        if (panel) panel.style.display = panelName === plan.panel ? 'block' : 'none';
    });

    const banner = document.getElementById('gw-transition-banner');
    if (banner) {
        if (plan.showTransition) {
            banner.textContent = plan.message;
            banner.style.display = 'inline-block';
        } else {
            banner.style.display = 'none';
        }
    }

    // liveGameweek.js reads localStorage directly, which throws when site data is
    // blocked. Catching it here means a failure in live mode can never stop the
    // This week / Last week toggles from being bound.
    try {
        if (plan.panel === 'live') {
            initializeLiveGameweek();
        } else {
            stopLiveGameweekPolling();
        }
    } catch (err) {
        console.error('Live gameweek could not start or stop', err);
    }
}

// sessionStorage can throw in some browsers (blocked site data), so every
// access is wrapped in try/catch. Without it we simply start on 'this-week'.
function readLens() {
    try {
        return sessionStorage.getItem('weekLens') || 'this-week';
    } catch {
        return 'this-week';
    }
}

function saveLens(lens) {
    try {
        sessionStorage.setItem('weekLens', lens);
    } catch {
        // Not remembered, but the toggle still works for this page view.
    }
}

// We need to handle both initial load and AJAX navigation
function initializeHome() {
    // Run the recap first: it already copes with blocked storage, so nothing
    // that throws further down can stop the recap loading.
    initializeWeekV2();
    initializeWeekState();

    const toggleThisWeek = document.getElementById('lens-this-week');
    const toggleLastWeek = document.getElementById('lens-last-week');
    const thisWeekView = document.getElementById('this-week-view');
    const lastWeekView = document.getElementById('last-week-view');
    if (!toggleThisWeek || !toggleLastWeek || !thisWeekView || !lastWeekView) return;

    const state = {
        weekLens: readLens()
    };

    function updateUI() {
        if (state.weekLens === 'this-week') {
            toggleThisWeek.classList.remove('secondary');
            toggleLastWeek.classList.add('secondary');
            thisWeekView.style.display = 'block';
            lastWeekView.style.display = 'none';
        } else {
            toggleLastWeek.classList.remove('secondary');
            toggleThisWeek.classList.add('secondary');
            lastWeekView.style.display = 'block';
            thisWeekView.style.display = 'none';
        }
    }

    toggleThisWeek.onclick = () => {
        if (state.weekLens === 'this-week') return;
        state.weekLens = 'this-week';
        saveLens('this-week');
        updateUI();
    };
    toggleLastWeek.onclick = () => {
        if (state.weekLens === 'last-week') return;
        state.weekLens = 'last-week';
        saveLens('last-week');
        updateUI();
    };

    updateUI();
}

window.initializeHomePage = initializeHome;
