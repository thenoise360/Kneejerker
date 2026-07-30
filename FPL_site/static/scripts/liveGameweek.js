/***** liveGameweek.js *****/
// 06.1: live score + live league leaderboard for the Week tab's live panel.
// Talks to /api/live-gameweek, which does all the FPL API work (standings,
// picks, live per-player stats) server-side - this module is rendering only.

const TEAM_ID_STORAGE_KEY = 'kj-fpl-team-id';

// Not aggressive enough to risk rate-limiting the official API: each poll
// fans out to one picks request per league member (concurrently, server
// side), on top of the shared live-stats/fixtures calls, so this stays in
// the same ballpark as established third-party live trackers rather than
// polling every few seconds.
const POLL_INTERVAL_MS = 60 * 1000;

let pollTimer = null;
let visibilityHandler = null;

function getStoredTeamId(storage) {
    const raw = storage.getItem(TEAM_ID_STORAGE_KEY);
    return raw ? raw : null;
}

function setStoredTeamId(storage, teamId) {
    storage.setItem(TEAM_ID_STORAGE_KEY, String(teamId));
}

function clearStoredTeamId(storage) {
    storage.removeItem(TEAM_ID_STORAGE_KEY);
}

function stopPolling() {
    if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
    }
    if (visibilityHandler) {
        document.removeEventListener('visibilitychange', visibilityHandler);
        visibilityHandler = null;
    }
}

function renderScoreCard(myScore, bonusStillSettling) {
    if (!myScore) {
        return `
            <div class="card">
                <h3>Your live score</h3>
                <p class="sub">Couldn't find a score for that team this gameweek - double check the team number.</p>
            </div>
        `;
    }

    const transferRow = myScore.transfer_cost > 0
        ? `<div class="summary-row-head"><span class="summary-row-label">Transfer cost</span><span class="summary-row-value">-${myScore.transfer_cost}</span></div>`
        : '';

    return `
        <div class="card">
            <h3>Your live score</h3>
            <div style="font-size:32px; font-weight:800; color:var(--plum); margin-bottom:10px;">${myScore.total} pts</div>
            <div class="summary-row">
                <div class="summary-row-head"><span class="summary-row-label">Base points</span><span class="summary-row-value">${myScore.base_points}</span></div>
                <div class="summary-row-head">
                    <span class="summary-row-label">Bonus points${bonusStillSettling ? ' <span class="pill pink" style="margin-left:4px;">Still settling</span>' : ''}</span>
                    <span class="summary-row-value">${myScore.bonus_points}</span>
                </div>
                <div class="summary-row-head"><span class="summary-row-label">Defensive contribution points</span><span class="summary-row-value">${myScore.defensive_contribution_points}</span></div>
                ${transferRow}
            </div>
        </div>
    `;
}

function renderLeaderboardCard(league, myEntryId) {
    if (!league.entries || league.entries.length === 0) {
        return `
            <div class="card">
                <h3>${league.name}</h3>
                <p class="sub">No live standings available for this league right now.</p>
            </div>
        `;
    }

    const rows = league.entries.map((entry) => {
        const isMe = entry.entry_id === myEntryId;
        return `
            <div class="fixture-row-item" style="${isMe ? 'font-weight:700; color:var(--plum);' : ''}">
                <span>${entry.rank}. ${isMe ? 'You' : (entry.entry_name || entry.player_name || 'Unknown team')}</span>
                <span>${entry.live_total} pts</span>
            </div>
        `;
    }).join('');

    return `
        <div class="card">
            <h3>${league.name}</h3>
            ${rows}
        </div>
    `;
}

/**
 * Grey pulsing placeholder for the live score + leaderboard cards, shown
 * immediately when polling starts so the panel never sits blank while the
 * first /api/live-gameweek request is in flight (same style as the
 * Discover page's card skeletons).
 */
function buildLiveSkeleton() {
    return `
        <div class="card">
            <div class="skeleton" style="width:120px; height:12px; margin-bottom:10px;"></div>
            <div class="skeleton" style="width:100px; height:32px; margin-bottom:10px;"></div>
            <div class="skeleton" style="width:100%; height:14px; margin-bottom:8px;"></div>
            <div class="skeleton" style="width:100%; height:14px; margin-bottom:8px;"></div>
            <div class="skeleton" style="width:70%; height:14px;"></div>
        </div>
        <div class="card">
            <div class="skeleton" style="width:140px; height:12px; margin-bottom:10px;"></div>
            <div class="skeleton" style="width:100%; height:16px; margin-bottom:8px;"></div>
            <div class="skeleton" style="width:100%; height:16px; margin-bottom:8px;"></div>
            <div class="skeleton" style="width:100%; height:16px;"></div>
        </div>
    `;
}

function renderLiveContent(container, data) {
    if (data.error === 'invalid_team_id') {
        container.innerHTML = `
            <div class="card">
                <p class="sub">Couldn't find that team number - double check it and try again.</p>
                <button type="button" class="btn-pill secondary" id="live-team-id-retry" style="width:auto; padding:8px 16px; margin-top:8px;">Try a different team</button>
            </div>
        `;
        const retry = document.getElementById('live-team-id-retry');
        if (retry) retry.onclick = () => resetTeamIdCapture();
        return;
    }

    if (data.error) {
        container.innerHTML = `
            <div class="card">
                <p class="sub">Couldn't load live scores right now - check back shortly.</p>
            </div>
        `;
        return;
    }

    const leaderboards = (data.leaderboards || [])
        .map((league) => renderLeaderboardCard(league, data.my_entry_id))
        .join('');

    container.innerHTML = renderScoreCard(data.my_score, data.bonus_still_settling) + leaderboards;
}

async function fetchAndRenderLiveGameweek(teamId) {
    const content = document.getElementById('live-gameweek-content');
    if (!content) return;

    try {
        const res = await fetch(`/api/live-gameweek?team_id=${encodeURIComponent(teamId)}`);
        const data = await res.json();
        renderLiveContent(content, data);
    } catch (err) {
        console.error('Failed to load live gameweek data', err);
        renderLiveContent(content, { error: 'network' });
    }
}

function startPolling(teamId) {
    stopPolling();

    const content = document.getElementById('live-gameweek-content');
    if (content) content.innerHTML = buildLiveSkeleton();

    fetchAndRenderLiveGameweek(teamId);

    pollTimer = setInterval(() => {
        if (document.visibilityState === 'visible') {
            fetchAndRenderLiveGameweek(teamId);
        }
    }, POLL_INTERVAL_MS);

    // Catch up immediately if the tab was backgrounded through a poll tick.
    visibilityHandler = () => {
        if (document.visibilityState === 'visible') {
            fetchAndRenderLiveGameweek(teamId);
        }
    };
    document.addEventListener('visibilitychange', visibilityHandler);
}

function resetTeamIdCapture() {
    const storage = window.localStorage;
    clearStoredTeamId(storage);
    stopPolling();

    const formCard = document.getElementById('live-team-id-card');
    const content = document.getElementById('live-gameweek-content');
    if (formCard) formCard.style.display = 'block';
    if (content) {
        content.style.display = 'none';
        content.innerHTML = '';
    }
}

export function initializeLiveGameweek() {
    const panel = document.getElementById('gw-panel-live');
    if (!panel) {
        stopPolling();
        return;
    }

    const formCard = document.getElementById('live-team-id-card');
    const content = document.getElementById('live-gameweek-content');
    const form = document.getElementById('live-team-id-form');
    const input = document.getElementById('live-team-id-input');
    if (!formCard || !content || !form || !input) return;

    const storage = window.localStorage;
    const storedTeamId = getStoredTeamId(storage);

    if (storedTeamId) {
        formCard.style.display = 'none';
        content.style.display = 'block';
        startPolling(storedTeamId);
    } else {
        formCard.style.display = 'block';
        content.style.display = 'none';
        stopPolling();
    }

    form.onsubmit = (event) => {
        event.preventDefault();
        const teamId = input.value.trim();
        if (!teamId) return;
        setStoredTeamId(storage, teamId);
        formCard.style.display = 'none';
        content.style.display = 'block';
        startPolling(teamId);
    };
}

export function stopLiveGameweekPolling() {
    stopPolling();
}
