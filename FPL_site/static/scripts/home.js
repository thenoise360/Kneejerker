/***** home.js *****/
import {
    updateLastUpdatedTime,
    isUserActive
} from './utils.js';
import { planWeekRender } from './weekState.js';
import { initializeLiveGameweek, stopLiveGameweekPolling } from './liveGameweek.js';

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

    const plan = planWeekRender(gwState, window.localStorage);

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

    if (plan.panel === 'live') {
        initializeLiveGameweek();
    } else {
        stopLiveGameweekPolling();
    }
}

// We need to handle both initial load and AJAX navigation
function initializeHome() {
    initializeWeekState();

    const toggleThisWeek = document.getElementById('lens-this-week');
    const toggleLastWeek = document.getElementById('lens-last-week');
    const thisWeekView = document.getElementById('this-week-view');
    const lastWeekView = document.getElementById('last-week-view');
    if (!toggleThisWeek || !toggleLastWeek || !thisWeekView || !lastWeekView) return;

    const state = {
        weekLens: sessionStorage.getItem('weekLens') || 'this-week'
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
            fetchAlexData();
        }
    }

    toggleThisWeek.onclick = () => {
        if (state.weekLens === 'this-week') return;
        state.weekLens = 'this-week';
        sessionStorage.setItem('weekLens', 'this-week');
        updateUI();
    };
    toggleLastWeek.onclick = () => {
        if (state.weekLens === 'last-week') return;
        state.weekLens = 'last-week';
        sessionStorage.setItem('weekLens', 'last-week');
        updateUI();
    };

    updateUI();
}

async function fetchAlexData() {
    const totwContainer = document.getElementById('alex-totw-card');
    if (!totwContainer) return;

    try {
        const res = await fetch('/api/top-5-players');
        if (!res.ok) throw new Error("Failed to fetch top players");
        const topPlayersByPos = await res.json();

        // Flatten and sort to get a "Team of the Week" (just top performers generally).
        // top_5_players_last_5_weeks() gives each player's per-gameweek scores rather
        // than a single total, so sum their last-5 window to rank them here.
        let allTopPlayers = [];
        for (const pos in topPlayersByPos) {
            const players = topPlayersByPos[pos].players || [];
            allTopPlayers = allTopPlayers.concat(players.map(p => ({
                web_name: p.name,
                total_points: (p.scores || []).reduce((a, b) => a + b, 0)
            })));
        }
        allTopPlayers.sort((a, b) => b.total_points - a.total_points);
        const totw = allTopPlayers.slice(0, 11);

        renderTotw(totwContainer, totw);
    } catch (err) {
        console.error("Failed to fetch Alex data", err);
        totwContainer.innerHTML = '<h3>Team of the Week</h3><p class="sub">Error loading data.</p>';
    }
}

function renderTotw(container, totw) {
    const totwHeadline = totw.length > 0
        ? `Top performers from last week are in!`
        : `No data available for last week yet.`;

    const maxPts = totw.length > 0 ? Math.max(...totw.map(p => p.total_points)) : 1;

    container.innerHTML = `
        <div style="display:flex; align-items:center; gap:12px;">
            <div class="action-icon" style="font-size:22px;">🏆</div>
            <div class="t" style="font-size:14px; font-weight:700;">${totwHeadline}</div>
        </div>
        <div class="accordion-item totw-accordion" id="totw-accordion">
            <div class="accordion-head" id="totw-toggle" role="button" tabindex="0" style="margin-top:12px; border-top:1px solid var(--grey); padding-top:10px; cursor:pointer; display:flex; justify-content:space-between;">
                <span style="font-size:12.5px; font-weight:700; color:var(--plum);">See the top scorers</span>
                <span class="chev">▾</span>
            </div>
            <div class="accordion-body" id="totw-body" style="display:none; margin-top:10px;">
                ${totw.map(p => `
                    <div style="padding:7px 0; border-bottom:1px solid var(--grey);">
                        <div style="display:flex; justify-content:space-between; font-size:13px; margin-bottom:4px;">
                            <span>${p.web_name}</span>
                            <span style="font-weight:700;">${p.total_points} pts</span>
                        </div>
                        <div class="bar-track" style="height:6px; background:var(--grey);"><div class="bar-fill" style="width:${((p.total_points / maxPts) * 100).toFixed(0)}%; height:100%; background:var(--teal);"></div></div>
                    </div>
                `).join('')}
            </div>
        </div>
    `;

    const toggle = document.getElementById('totw-toggle');
    const body = document.getElementById('totw-body');
    const chev = toggle?.querySelector('.chev');

    if (toggle && body) {
        toggle.onclick = () => {
            const isHidden = body.style.display === 'none';
            body.style.display = isHidden ? 'block' : 'none';
            if (chev) chev.style.transform = isHidden ? 'rotate(180deg)' : 'rotate(0deg)';
        };
    }
}

window.initializeHomePage = initializeHome;
