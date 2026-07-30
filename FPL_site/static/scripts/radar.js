/***** radar.js *****/
import {
    updateLastUpdatedTime,
    formatOwnership,
    isUserActive
} from './utils.js';
import {
    difficultyColor,
    buildSparkline,
    describeFixtureRun,
    buildFixtureChips,
    buildOwnershipArea,
    SEASON_STATS,
    formatStatValue,
    summaryRow
} from './visuals.js';
import { trackPlayerSummary } from './analytics.js';

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
            const [summaryArr, fixtures, positionData, last5Data, indexScores] = await Promise.all([
                fetchJsonSafe(`/get_player_summary?id=${playerId}`),
                fetchJsonSafe(`/get_next_5_gameweeks?id=${playerId}`),
                fetchJsonSafe('/api/top-5-players'),
                fetchJsonSafe(`/get_player_last_5_points?id=${playerId}`),
                fetchJsonSafe('/get_player_index_scores')
            ]);

            const summary = Array.isArray(summaryArr) ? summaryArr[0] : summaryArr;
            if (!summary || !summary.name) {
                sheetContent.innerHTML = '<p class="sub">Couldn\'t load this player\'s profile right now.</p>';
                return;
            }

            currentCards = buildMiniCards(summary, fixtures, positionData, last5Data, indexScores);
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

    function buildMiniCards(summary, fixtures, positionData, last5Data, indexScores) {
        const safeLast5 = Array.isArray(last5Data) ? last5Data : [];
        const last5Values = safeLast5.map(d => d.points);
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

        return [
            buildFormCard(last5Values, avg5Values),
            buildFixtureCard(fixtures),
            buildSeasonNumbersCard(summary),
            buildSetPieceCard(summary),
            buildRatingBreakdownCard(indexEntry, indexScores),
            buildMarketActivityCard(summary),
            buildSummaryCard(summary, fixtures, last5Values, avg5Values, indexEntry)
        ];
    }

    function emptyStateCard(title, message) {
        return `<div class="mini-card mini-slide">
            <div class="mc-title">${title}</div>
            <div class="empty-state">${message}</div>
        </div>`;
    }

    function buildFormCard(last5, avg5) {
        if (!last5.length) {
            return emptyStateCard('Form — last 5 vs average', "No recent gameweek data for this player yet.");
        }
        return `<div class="mini-card mini-slide">
            <div class="mc-title">Form — last 5 vs average</div>
            <div style="margin: 10px 0;">${buildSparkline(last5, avg5)}</div>
            <div class="mc-caption">${describeForm(last5, avg5)}</div>
        </div>`;
    }

    function describeForm(last5, avg5) {
        const total = last5.reduce((a, b) => a + b, 0);
        const avgTotal = avg5.reduce((a, b) => a + b, 0);
        if (total === 0 && avgTotal === 0) {
            return "No points on the board across these 5 gameweeks yet.";
        }
        const mean = total / last5.length;
        const variance = last5.reduce((a, v) => a + Math.pow(v - mean, 2), 0) / last5.length;
        const stdDev = Math.sqrt(variance);
        if (mean > 0 && stdDev > mean * 0.6) {
            return `Streaky — swinging between ${Math.min(...last5)} and ${Math.max(...last5)} points across these 5 gameweeks.`;
        }
        if (total > avgTotal) {
            return `Consistently above the position average over these 5 gameweeks (${total} vs ${avgTotal} points).`;
        }
        if (total < avgTotal) {
            return `Below the position average over these 5 gameweeks (${total} vs ${avgTotal} points).`;
        }
        return "Right in line with the position average over these 5 gameweeks.";
    }

    function buildFixtureCard(fixtures) {
        if (!fixtures || fixtures.length === 0) {
            return emptyStateCard('Upcoming Fixtures', "No fixture data available for this player right now.");
        }

        const chips = buildFixtureChips(fixtures);

        const avgDots = fixtures.map(f => `<div class="diff-dot" style="background:${difficultyColor(f.leagueAverageDifficulty)};" title="League average difficulty for gameweek ${f.gameweek}: ${f.leagueAverageDifficulty ?? 'not available'}"></div>`).join('');

        return `<div class="mini-card mini-slide">
            <div class="mc-title">Upcoming Fixtures</div>
            <div class="fixture-chip-row">${chips}</div>
            <div class="fixture-compare-row">
                <span class="fixture-compare-label">League average</span>
                <div class="fixture-dot-row">${avgDots}</div>
            </div>
            <div class="mc-caption">${describeFixtureRun(fixtures)}</div>
        </div>`;
    }


    function buildSeasonNumbersCard(summary) {
        if (!summary.metrics || summary.metrics.length === 0) {
            return emptyStateCard('Season Numbers', "Season totals aren't available for this player right now.");
        }
        const metricsByTitle = {};
        summary.metrics.forEach(m => { metricsByTitle[m.title] = m; });

        const cells = SEASON_STATS
            .filter(s => !s.positionsOnly || s.positionsOnly.includes(summary.position_name))
            .map(s => {
                const m = metricsByTitle[s.metricTitle];
                if (!m) return '';
                return `<div>
                    <div class="val">${formatStatValue(m.value)}</div>
                    <div class="lbl">${s.label}</div>
                    <div class="lbl-avg">Position average: ${formatStatValue(m.averageValue)}</div>
                </div>`;
            }).join('');

        // Pre-season, these figures are still last season's final tally - the
        // FPL API itself doesn't zero them out until gameweek 1 locks, so
        // label that plainly rather than presenting them as this season's.
        const title = summary.is_pre_season ? 'Season Numbers (Last Season)' : 'Season Numbers';
        const caption = summary.is_pre_season
            ? `Still last season's final numbers - these will reset once gameweek 1 locks. Position average alongside for now.`
            : `Season totals so far, with the average for other ${(summary.position_name || 'players').toLowerCase()}s alongside.`;

        return `<div class="mini-card mini-slide">
            <div class="mc-title">${title}</div>
            <div class="season-grid">${cells}</div>
            <div class="mc-caption">${caption}</div>
        </div>`;
    }

    // 02.7: one line per duty the player actually holds - no comma-joined
    // sentence, no blank/negative lines for duties they don't have.
    function buildSetPieceCard(summary) {
        const duties = summary.setPieceDuties || [];
        if (!duties.length) {
            return emptyStateCard('Set-Piece Duties', "No set-piece duty for this player right now.");
        }
        return `<div class="mini-card mini-slide">
            <div class="mc-title">Set-Piece Duties</div>
            <div class="set-piece-lines">
                ${duties.map(d => `<div class="set-piece-line">${d.text}</div>`).join('')}
            </div>
        </div>`;
    }

    function buildRatingBreakdownCard(entry, indexScores) {
        if (!entry) {
            return emptyStateCard('Rating Breakdown', "A rating breakdown isn't available for this player right now.");
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

        return `<div class="mini-card mini-slide">
            <div class="mc-title">Rating Breakdown</div>
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
            </div>
            <div class="mc-caption">This score comes directly from these two numbers - points scored for every pound of value, multiplied by how rare a pick they are - with nothing hidden.</div>
        </div>`;
    }

    function buildMarketActivityCard(summary) {
        const marketLabel = summary.is_pre_season ? "Total Season" : "This Week";
        return `<div class="mini-card mini-slide">
            <div class="mc-title">Market Activity (${marketLabel})</div>
            <div style="display:flex; flex-direction:column; gap:12px; margin-top:10px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-size:13px; color:#777;">Ownership</span>
                    <span style="font-weight:700;">${summary.selected_by_percent}%</span>
                </div>
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-size:13px; color:#777;">Transfers In</span>
                    <span style="font-weight:700; color:var(--teal);">+${formatTransferCount(summary.transfers_in_event)}</span>
                </div>
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-size:13px; color:#777;">Transfers Out</span>
                    <span style="font-weight:700; color:var(--pink);">${summary.transfers_out_event > 0 ? '-' : ''}${formatTransferCount(summary.transfers_out_event)}</span>
                </div>
            </div>
            <div class="mc-caption">${summary.is_pre_season ? "Pre-season data reflects total season movement." : "Reflects movement in the current gameweek."}</div>
        </div>`;
    }

    // Summary (replaces the old "Verdict" card): one consolidated view of
    // every earlier card's headline figure, each against its own real
    // comparison point - no invented opinion text, just the same numbers
    // shown again with a bar so the pattern reads at a glance.
    function buildSummaryCard(summary, fixtures, last5, avg5, indexEntry) {
        const rows = [];

        if (last5.length) {
            const total = last5.reduce((a, b) => a + b, 0);
            const avgTotal = avg5.reduce((a, b) => a + b, 0);
            const max = Math.max(total, avgTotal, 1);
            rows.push(summaryRow('Form, last 5 gameweeks', `${total} pts`, `Position average: ${avgTotal} pts`, (total / max) * 100, (avgTotal / max) * 100));
        }

        const realFixtures = (fixtures || []).filter(f => f.homeOrAway !== 'Blank');
        if (realFixtures.length) {
            const avgDiff = realFixtures.reduce((a, f) => a + f.difficulty, 0) / realFixtures.length;
            const withLeagueAvg = realFixtures.filter(f => f.leagueAverageDifficulty !== null && f.leagueAverageDifficulty !== undefined);
            const leagueAvgDiff = withLeagueAvg.length
                ? withLeagueAvg.reduce((a, f) => a + f.leagueAverageDifficulty, 0) / withLeagueAvg.length
                : null;
            // Difficulty runs 1 (kindest) to 5 (toughest), so invert it for the
            // bar: a longer bar should always read as the easier run.
            const easePct = ((5 - avgDiff) / 4) * 100;
            const leagueEasePct = leagueAvgDiff !== null ? ((5 - leagueAvgDiff) / 4) * 100 : 50;
            const compareText = leagueAvgDiff !== null ? `League average: ${leagueAvgDiff.toFixed(1)}/5` : 'League average not available';
            rows.push(summaryRow('Next 5 fixtures difficulty', `${avgDiff.toFixed(1)}/5`, compareText, easePct, leagueEasePct));
        }

        const pointsMetric = (summary.metrics || []).find(m => m.title === 'Points');
        if (pointsMetric) {
            const max = Math.max(pointsMetric.value, pointsMetric.averageValue, 1);
            const label = summary.is_pre_season ? 'Season points (last season)' : 'Season points';
            rows.push(summaryRow(label, formatStatValue(pointsMetric.value), `Position average: ${formatStatValue(pointsMetric.averageValue)}`, (pointsMetric.value / max) * 100, (pointsMetric.averageValue / max) * 100));
        }

        if (indexEntry) {
            const playerScore = Number(indexEntry.player_score);
            rows.push(summaryRow('Overall value score', `${playerScore.toFixed(0)}/100`, 'Scale: 0-100 across all players', playerScore, 50));
        }

        if (!rows.length) {
            return emptyStateCard('Summary', "Not enough data yet to summarise this player.");
        }

        return `<div class="mini-card mini-slide">
            <div class="mc-title">Summary</div>
            ${rows.join('')}
            <div class="mc-caption">Each row uses the same numbers as the earlier cards - solid bar is this player, the marker is the average it's being judged against.</div>
        </div>`;
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
