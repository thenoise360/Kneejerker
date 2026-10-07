/***** radar.js *****/
import {
    updateLastUpdatedTime,
    formatOwnership,
    isUserActive
} from './utils.js';
import {
    buildSparkline,
    describeFixtureRun
} from './visuals.js';
import { trackPlayerSummary } from './analytics.js';
import { renderMomentumCard } from './lib/momentumView.js';
import { buildFixtureList } from './lib/fixtureList.js';
import { buildLastSeasonHtml } from './lib/lastSeasonView.js';
import { escapeHtml } from './lib/escapeHtml.js';
import {
    CARD_TITLES, inCardOrder, playerCard, emptyPlayerCard, describeForm, seasonNumbers, summaryRows
} from './lib/playerCards.js';

document.addEventListener('DOMContentLoaded', function () {
    initializeRadar();
});

// We need to handle both initial load and AJAX navigation
function initializeRadar() {
    const content = document.getElementById('radar-content');
    if (!content) return;

    // State management
    const state = {
        samMetric: 'net',
        ownMetric: 'ownership_change', // 'ownership_change' or 'ownership' (pre-season fallback)
        topInPlayers: [],
        topOutPlayers: [],
        topOwnIn: [],
        topOwnOut: []
    };

    function updateUI() {
        renderSamLens();
    }

    function renderSamLens() {
        bindSamEvents();
        fetchSamData();
    }

    function bindSamEvents() {
        const toggleNet = document.getElementById('toggle-net');
        const toggleOwnership = document.getElementById('toggle-ownership');

        if (toggleNet && toggleOwnership) {
            toggleNet.onclick = () => {
                state.samMetric = 'net';
                toggleNet.classList.remove('secondary');
                toggleOwnership.classList.add('secondary');
                updateLists();
            };
            toggleOwnership.onclick = () => {
                state.samMetric = 'ownership';
                toggleOwnership.classList.remove('secondary');
                toggleNet.classList.add('secondary');
                updateLists();
            };
        }
    }

    const PRE_SEASON_CAPTIONS = {
        ownership: "No ownership change to show yet this pre-season - showing current ownership level instead."
    };

    function updateCaption() {
        const captionEl = document.getElementById('sam-metric-caption');
        if (!captionEl) return;
        if (state.samMetric === 'ownership' && state.ownMetric === 'ownership') {
            captionEl.textContent = PRE_SEASON_CAPTIONS.ownership;
        } else {
            captionEl.textContent = '';
        }
    }

    function updateLists() {
        updateCaption();
        if (state.samMetric === 'net') {
            // Pre-season these are genuinely 0 for every player - the FPL API
            // doesn't track transfers until gameweek 1 locks, so that's the
            // real count, not a missing-data state.
            renderPlayerList('top-5-in-list', state.topInPlayers, 'net');
            renderPlayerList('top-5-out-list', state.topOutPlayers.map(p => ({...p, value: -p.value})), 'net');
        } else {
            renderPlayerList('top-5-in-list', state.topOwnIn, 'ownership');
            renderPlayerList('top-5-out-list', state.topOwnOut, 'ownership');
        }
    }

    async function fetchSamData() {
        try {
            const [inRes, outRes, ownRes] = await Promise.all([
                fetch('/api/net-transfers-in'),
                fetch('/api/net-transfers-out'),
                fetch('/api/relative-ownership')
            ]);

            const [inData, outData, ownData] = await Promise.all([
                inRes.ok ? inRes.json() : null,
                outRes.ok ? outRes.json() : null,
                ownRes.ok ? ownRes.json() : null
            ]);

            if (inData && inData.labels) {
                state.topInPlayers = inData.labels.map((l, i) => ({
                    name: l,
                    value: inData.values[i],
                    id: inData.ids[i]
                })).sort((a, b) => b.value - a.value).slice(0, 5);
            }

            if (outData && outData.labels) {
                state.topOutPlayers = outData.labels.map((l, i) => ({
                    name: l,
                    value: outData.values[i],
                    id: outData.ids[i]
                })).sort((a, b) => b.value - a.value).slice(0, 5);
            }

            state.ownMetric = (ownData && ownData.metric) || 'ownership_change';

            if (ownData && ownData.labels) {
                if (state.ownMetric === 'ownership') {
                    // Pre-season fallback: backend already ranked this list -
                    // first 5 entries are the highest owned, last 5 are the
                    // lowest-but-relevant, so no "change" needs computing.
                    const movers = ownData.labels.map((l, i) => ({
                        name: l,
                        ownership: ownData.newValues[i],
                        id: ownData.ids[i]
                    }));
                    state.topOwnIn = movers.slice(0, 5);
                    state.topOwnOut = movers.slice(5, 10);
                } else {
                    const ownMovers = ownData.labels.map((l, i) => {
                        const oldPct = ownData.oldValues[i];
                        const newPct = ownData.newValues[i];
                        const relativeChange = oldPct > 0.1 ? ((newPct - oldPct) / oldPct) * 100 : (newPct - oldPct);
                        return { name: l, change: relativeChange, id: ownData.ids[i], ownership: newPct };
                    });

                    state.topOwnIn = ownMovers.filter(p => p.change > 0).sort((a,b) => b.change - a.change).slice(0, 5);
                    state.topOwnOut = ownMovers.filter(p => p.change < 0).sort((a,b) => a.change - b.change).slice(0, 5);
                }
            }

            updateLists();
        } catch (err) {
            console.error("Failed to fetch Sam data", err);
            const inList = document.getElementById('top-5-in-list');
            const outList = document.getElementById('top-5-out-list');
            if (inList) inList.innerHTML = '<p class="sub">Error loading data.</p>';
            if (outList) outList.innerHTML = '<p class="sub">Error loading data.</p>';
        }
    }

    function renderPlayerList(containerId, players, metric) {
        const container = document.getElementById(containerId);
        if (!container) return;

        if (!players.length) {
            container.innerHTML = '<p class="sub">No movers found.</p>';
            return;
        }

        const maxAbs = Math.max(...players.map(p => Math.abs(metric === 'net' ? p.value : (metric === 'ownership' ? p.ownership : p.change))), 1);

        container.innerHTML = players.map(p => {
            const val = metric === 'net' ? p.value : (metric === 'ownership' ? p.ownership : p.change);
            return `
                <div class="action-card" data-player-id="${p.id}">
                    <div class="left">
                        <span class="name">${p.name}</span>
                    </div>
                    <div class="right">
                        ${transferGlance(val, maxAbs, metric, p)}
                    </div>
                </div>
            `;
        }).join('');

        container.querySelectorAll('.action-card').forEach(card => {
            card.addEventListener('click', () => openPlayerProfile(card.dataset.playerId));
        });
    }

    function formatTransferCount(n) {
        const abs = Math.abs(n);
        if (abs >= 10000) return `${Math.round(abs / 1000)}k`;
        if (abs >= 1000) return `${(abs / 1000).toFixed(1)}k`;
        return `${abs}`;
    }

    function transferGlance(val, maxAbs, metric, player) {
        const pct = maxAbs > 0 ? Math.min(Math.abs(val) / maxAbs * 100, 100) : 0;
        const color = val >= 0 ? 'var(--teal)' : 'var(--pink)';

        let label = '';
        if (metric === 'net') {
            label = (val >= 0 ? '+' : '') + formatTransferCount(val);
        } else {
            // 'ownership' (pre-season fallback, or the ownership-change tab) -
            // always show the real ownership percentage, never a fake transfer count.
            label = (player && player.ownership !== undefined ? player.ownership : val).toFixed(1) + '%';
        }

        return `
            <div class="glance">
                <span>${label}</span>
                <div class="bar-track" style="width:60px; height:6px;">
                    <div class="bar-fill" style="width:${pct}%; background:${color};"></div>
                </div>
            </div>
        `;
    }

    /**
     * Grey pulsing placeholder for the player profile bottom sheet, shown
     * immediately on open while the profile's several fetches are in flight
     * (same style as the Discover page's card skeletons).
     */
    function buildProfileSkeleton() {
        return `
            <div class="skeleton" style="width:160px; height:20px; margin-bottom:12px;"></div>
            <div style="display:flex; gap:6px; margin-bottom:14px;">
                <div class="skeleton" style="width:70px; height:22px; border-radius:100px;"></div>
                <div class="skeleton" style="width:60px; height:22px; border-radius:100px;"></div>
                <div class="skeleton" style="width:50px; height:22px; border-radius:100px;"></div>
            </div>
            <div class="mini-card mini-slide">
                <div class="skeleton" style="width:140px; height:12px; margin-bottom:12px;"></div>
                <div class="skeleton" style="width:100%; height:90px; margin-bottom:10px;"></div>
                <div class="skeleton" style="width:80%; height:11px;"></div>
            </div>
        `;
    }

    let currentMiniIndex = 0;
    let currentCards = [];

    async function openPlayerProfile(playerId) {
        const backdrop = document.getElementById('sheet-backdrop');
        const sheetContent = document.getElementById('sheet-content');
        if (!backdrop || !sheetContent) return;

        sheetContent.innerHTML = buildProfileSkeleton();
        backdrop.classList.add('active');

        // Close logic: clicking backdrop or handle closes it
        backdrop.onclick = (e) => {
            if (e.target === backdrop || e.target.id === 'sheet-handle') {
                backdrop.classList.remove('active');
            }
        };

        try {
            const [summaryArr, fixtures, positionData, last5Data, indexScores, momentum, lastSeason] = await Promise.all([
                fetchJsonSafe(`/get_player_summary?id=${playerId}`),
                fetchJsonSafe(`/get_next_5_gameweeks?id=${playerId}`),
                fetchJsonSafe('/api/top-5-players'),
                fetchJsonSafe(`/get_player_last_5_points?id=${playerId}`),
                fetchJsonSafe('/get_player_index_scores'),
                fetchJsonSafe(`/api/player/${playerId}/momentum`),
                // Last season's baseline. A failed fetch gives null and the line is left out.
                fetchJsonSafe(`/api/player/${playerId}/last-season`)
            ]);

            const summary = Array.isArray(summaryArr) ? summaryArr[0] : summaryArr;
            if (!summary || !summary.name) {
                sheetContent.innerHTML = '<p class="sub">Couldn\'t load this player\'s profile right now.</p>';
                return;
            }

            currentCards = buildMiniCards(summary, fixtures, positionData, last5Data, indexScores, momentum, lastSeason);
            currentMiniIndex = 0;

            sheetContent.innerHTML = `
                <div class="profile-title" style="margin-bottom:0;">${summary.name}</div>
                <div style="display:flex; gap:6px; margin-bottom:14px; margin-top:4px;">
                    <span class="pill outline" style="color:#777; border-color:#ddd; padding: 4px 10px; border-radius: 100px; font-size: 12px;">${summary.team_name}</span>
                    <span class="pill" style="background:var(--plum); color:#fff; padding: 4px 10px; border-radius: 100px; font-size: 12px;">${summary.position_name}</span>
                    <span class="pill" style="background:var(--pink); color:#fff; padding: 4px 10px; border-radius: 100px; font-size: 12px;">£${summary.value.toFixed(1)}m</span>
                </div>

                <div class="mini-carousel" id="profile-carousel" style="margin-top: 15px;">
                    <div class="mini-track" id="mini-track">
                        ${currentCards.join('')}
                    </div>
                    <div class="mini-nav">
                        <button class="mini-nav-btn" id="mini-prev">‹</button>
                        <div class="mini-dots" id="mini-dots"></div>
                        <button class="mini-nav-btn" id="mini-next">›</button>
                    </div>
                </div>
            `;

            renderMiniCarousel();

            // Bind nav events
            document.getElementById('mini-prev').onclick = (e) => {
                e.stopPropagation();
                if (currentMiniIndex > 0) {
                    currentMiniIndex--;
                    renderMiniCarousel();
                }
            };
            document.getElementById('mini-next').onclick = (e) => {
                e.stopPropagation();
                if (currentMiniIndex < currentCards.length - 1) {
                    currentMiniIndex++;
                    renderMiniCarousel();
                }
            };

            trackPlayerSummary(playerId, summary.name);

        } catch (err) {
            console.error("Failed to load player profile", err);
            sheetContent.innerHTML = '<p class="sub">Error loading profile.</p>';
        }
    }

    function renderMiniCarousel() {
        const track = document.getElementById('mini-track');
        const dotsWrap = document.getElementById('mini-dots');
        const prevBtn = document.getElementById('mini-prev');
        const nextBtn = document.getElementById('mini-next');

        if (!track || !dotsWrap) return;

        track.style.transform = `translateX(-${currentMiniIndex * 100}%)`;
        dotsWrap.innerHTML = currentCards.map((_, i) => `<div class="mini-dot ${i === currentMiniIndex ? 'active' : ''}"></div>`).join('');
        
        if (prevBtn) prevBtn.disabled = currentMiniIndex === 0;
        if (nextBtn) nextBtn.disabled = currentMiniIndex === currentCards.length - 1;
    }

    const POSITION_DATA_KEYS = {
        'Goalkeeper': 'goalkeepers',
        'Defender': 'defenders',
        'Midfielder': 'midfielders',
        'Forward': 'forwards'
    };

    // Every slide uses this class so the carousel can size it.
    const SLIDE = 'mini-card mini-slide';

    function buildMiniCards(summary, fixtures, positionData, last5Data, indexScores, momentum, lastSeason) {
        const safeLast5 = Array.isArray(last5Data) ? last5Data : [];
        // Coerce to real numbers: older responses sent totals as text.
        const last5Values = safeLast5.map(d => Number(d.points) || 0);
        const positionKey = POSITION_DATA_KEYS[summary.position_name];
        const avg5Values = (positionData && positionKey && positionData[positionKey])
                     ? positionData[positionKey].averageScores
                     : last5Values.map(() => 0);

        // Exclude the synthetic "Mean" row this endpoint mixes into the same
        // list (its own id is an averaged, non-zero number - not a sentinel).
        // Also confirm the name matches: this endpoint reads the local
        // database (last ingested season) while the summary reads the live
        // FPL API, so during a season rollover the same id can briefly point
        // at two different players - showing a wrong-player number would be
        // worse than showing nothing.
        const rawIndexEntry = (indexScores || []).find(r => r.id === summary.id && r.web_name !== 'Mean') || null;
        const indexEntry = (rawIndexEntry && rawIndexEntry.web_name === summary.name) ? rawIndexEntry : null;

        // Built by key, then put in the shared order (playerCards.js), so this
        // sheet and the Discover panel always swipe through cards the same way.
        // Momentum is only there when its fetch worked; a failed fetch gives null.
        return inCardOrder({
            form: buildFormCard(last5Values, avg5Values, lastSeason),
            momentum: momentum ? renderMomentumCard(momentum, SLIDE) : '',
            fixtures: buildFixtureCard(fixtures),
            season: buildSeasonNumbersCard(summary),
            ownership: buildOwnershipCard(summary),
            setPieces: buildSetPieceCard(summary),
            rating: buildRatingBreakdownCard(indexEntry, indexScores),
            summary: buildSummaryCard(summary, fixtures, last5Values, avg5Values, indexEntry)
        });
    }

    function emptyStateCard(title, message, extra = '') {
        return emptyPlayerCard(title, message, { wrapperClass: SLIDE, extra });
    }

    function buildFormCard(last5, avg5, lastSeason) {
        // buildLastSeasonHtml gives '' once this season has 6 or more appearances,
        // so the line only ever appears while the chart has a small sample.
        const lastSeasonHtml = buildLastSeasonHtml(lastSeason);
        if (!last5.length) {
            return emptyStateCard(CARD_TITLES.form, 'No recent gameweek data for this player yet.', lastSeasonHtml);
        }
        return playerCard({
            title: CARD_TITLES.form,
            visual: buildSparkline(last5, avg5),
            caption: describeForm(last5, avg5),
            extra: lastSeasonHtml,
            wrapperClass: SLIDE
        });
    }

    function buildFixtureCard(fixtures) {
        if (!fixtures || fixtures.length === 0) {
            return emptyStateCard(CARD_TITLES.fixtures, 'No fixture data available for this player right now.');
        }
        return playerCard({
            title: CARD_TITLES.fixtures,
            visual: buildFixtureList(fixtures),
            caption: describeFixtureRun(fixtures),
            wrapperClass: SLIDE
        });
    }

    function buildSeasonNumbersCard(summary) {
        const season = seasonNumbers(summary);
        if (!season) {
            return emptyStateCard(CARD_TITLES.season, "Season totals aren't available for this player right now.");
        }
        return playerCard({ ...season, wrapperClass: SLIDE });
    }

    // One line per duty the player actually holds: no comma-joined sentence,
    // no blank or negative lines for duties they don't have.
    function buildSetPieceCard(summary) {
        const duties = summary.setPieceDuties || [];
        if (!duties.length) {
            return emptyStateCard(CARD_TITLES.setPieces, 'No set-piece duty for this player right now.');
        }
        return playerCard({
            title: CARD_TITLES.setPieces,
            visual: `<div class="set-piece-lines">${duties.map(d => `<div class="set-piece-line">${escapeHtml(d.text)}</div>`).join('')}</div>`,
            wrapperClass: SLIDE
        });
    }

    function buildRatingBreakdownCard(entry, indexScores) {
        if (!entry) {
            return emptyStateCard(CARD_TITLES.rating, "A rating breakdown isn't available for this player right now.");
        }

        // MySQL returns some of these as DECIMAL, which the backend's JSON
        // response renders as a string, not a number - coerce once up front
        // rather than crashing on .toFixed() further down.
        const playerScore = Number(entry.player_score);
        const pointsPerMill = Number(entry.points_per_mill);
        const notSelectedByPerc = Number(entry.not_selected_by_perc);

        const pool = (indexScores || []).filter(r => r.web_name !== 'Mean');
        const maxValue = Math.max(...pool.map(r => Number(r.points_per_mill)), 1);
        const maxScarcity = Math.max(...pool.map(r => Number(r.not_selected_by_perc)), 1);

        const overallPct = Math.max(0, Math.min(100, playerScore));
        const valuePct = Math.max(0, Math.min(100, (pointsPerMill / maxValue) * 100));
        const scarcityPct = Math.max(0, Math.min(100, (notSelectedByPerc / maxScarcity) * 100));

        return playerCard({
            title: CARD_TITLES.rating,
            visual: `
            <div class="rating-row">
                <div class="rating-row-head"><span>Overall value score</span><span>${overallPct.toFixed(0)}/100</span></div>
                <div class="bar-track"><div class="bar-fill" style="width:${overallPct}%;"></div></div>
            </div>
            <div class="rating-row">
                <div class="rating-row-head"><span>Points scored per pound spent</span><span>${pointsPerMill.toFixed(1)} points per £1m</span></div>
                <div class="bar-track"><div class="bar-fill" style="width:${valuePct}%;"></div></div>
            </div>
            <div class="rating-row">
                <div class="rating-row-head"><span>How rarely other squads own them</span><span>${notSelectedByPerc.toFixed(1)}% unowned</span></div>
                <div class="bar-track"><div class="bar-fill pink" style="width:${scarcityPct}%;"></div></div>
            </div>`,
            caption: 'Points for every pound of value, multiplied by how rare a pick they are. Nothing hidden.',
            wrapperClass: SLIDE
        });
    }

    // Ownership and this week's transfers, as label-and-value rows.
    function buildOwnershipCard(summary) {
        const when = summary.is_pre_season ? 'whole season' : 'this week';
        const out = summary.transfers_out_event;
        return playerCard({
            title: `${CARD_TITLES.ownership} (${when})`,
            visual: `<div class="stat-rows">
                <div class="stat-row"><span>Owned by</span><span>${escapeHtml(summary.selected_by_percent)}%</span></div>
                <div class="stat-row"><span>Transfers in</span><span class="stat-up">+${formatTransferCount(summary.transfers_in_event)}</span></div>
                <div class="stat-row"><span>Transfers out</span><span class="stat-down">${out > 0 ? '-' : ''}${formatTransferCount(out)}</span></div>
            </div>`,
            caption: summary.is_pre_season ? 'Pre-season, this is the whole of last season.' : 'Movement in the current gameweek.',
            wrapperClass: SLIDE
        });
    }

    // Summary: every earlier card's headline figure again, each against its
    // own real comparison point, with a bar so the pattern reads at a glance.
    function buildSummaryCard(summary, fixtures, last5, avg5, indexEntry) {
        const rows = summaryRows({ summary, fixtures, form: last5, avgForm: avg5, indexEntry });
        if (!rows) {
            return emptyStateCard(CARD_TITLES.summary, 'Not enough data yet to summarise this player.');
        }
        return playerCard({ title: CARD_TITLES.summary, ...rows, wrapperClass: SLIDE });
    }

    async function fetchJsonSafe(url) {
        try {
            const res = await fetch(url);
            if (!res.ok) return null;
            return await res.json();
        } catch (err) {
            console.error(`Failed to fetch ${url}`, err);
            return null;
        }
    }

    // Initial render
    updateUI();
}

window.initializeRadarPage = initializeRadar;
