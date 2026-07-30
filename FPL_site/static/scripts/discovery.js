/**
 * Discovery Page functionality (Ticket 04.2)
 * Handles search-as-you-type with debouncing and result rendering.
 */
import {
    buildSparkline,
    buildFixtureChips,
    describeFixtureRun,
    buildOwnershipArea,
    buildMultiLineChart,
    buildChartLegend,
    SEASON_STATS,
    formatStatValue,
    summaryRow
} from './visuals.js';

let allPlayers = [];
let selectedPlayers = [];
let panelMetricIndex = 0;
let panelData = null;

// Caches recently-fetched player data for this page session, so re-selecting
// a player already seen (search -> tray -> remove -> re-add, or toggling
// between single-player and comparison views) doesn't re-fetch data that
// hasn't changed.
const playerDataCache = new Map(); // playerId -> { summary, fixtures, last5, ownership }
let indexScoresCache = null; // shared/global list, fetched once
const averagesCache = new Map(); // 'GKP'|'DEF'|'MID'|'FWD'|'overall' -> { avgPoints, avgOwnership, avgLabel }

// One colour per tray slot, applied in selection order - reused for a player's
// chart line, legend dot, and tray chip avatar so the mapping is traceable
// across the whole comparison panel.
const COMPARISON_COLORS = ['var(--teal)', 'var(--pink)', 'var(--plum-tint)'];

// Plain-language position labels for the average-line legend, matching the
// GKP/DEF/MID/FWD -> full-name convention already used in radar.js.
const POSITION_LABELS = { GKP: 'Goalkeeper', DEF: 'Defender', MID: 'Midfielder', FWD: 'Forward' };

const TRAY_CAP = 3;

/**
 * Adds a player to the comparison tray (Ticket 04.3, cap raised to 3).
 * @param {number} playerId - The ID of the player to add.
 * @param {Object} [playerObject] - Optional player object if already known.
 */
function addToTray(playerId, playerObject = null) {
    // 1. Check if already present
    if (selectedPlayers.some(p => p.id === playerId)) return;

    // 2. Check if tray is full
    if (selectedPlayers.length >= TRAY_CAP) {
        showTrayToast(`Comparing works best with up to ${TRAY_CAP} - remove one to add another`);
        return;
    }

    // 3. Find player object from cache or provided object
    const player = playerObject || allPlayers.find(p => p.id === playerId);
    if (!player) {
        console.warn(`Discovery: Player ${playerId} not found.`);
        return;
    }

    // 4. Add to tray
    selectedPlayers.push(player);
    renderTray();
    updateCategorySelectionStates();
    closeSearchResults();
}

/**
 * Removes a player from the comparison tray (Ticket 04.3).
 * @param {number} playerId - The ID of the player to remove.
 */
function removeFromTray(playerId) {
    selectedPlayers = selectedPlayers.filter(p => p.id !== playerId);
    renderTray();
    updateCategorySelectionStates();
}

/**
 * Renders the comparison tray (Ticket 04.3).
 * Shows an empty-state hint or chips for selected players.
 */
function renderTray() {
    const trayContainer = document.getElementById('discovery-tray');
    const panelContainer = document.getElementById('mode-panel-container');
    if (!trayContainer) return;

    if (selectedPlayers.length === 0) {
        trayContainer.innerHTML = '<div class="tray-empty-hint">Tap a player to start comparing</div>';
        if (panelContainer) panelContainer.style.display = 'none';
        return;
    }

    const isComparing = selectedPlayers.length >= 2;

    trayContainer.innerHTML = '';
    selectedPlayers.forEach((player, i) => {
        const chip = document.createElement('div');
        chip.className = 'tray-chip';
        chip.dataset.playerId = player.id;
        const avatarStyle = isComparing ? ` style="background:${COMPARISON_COLORS[i]};"` : '';
        chip.innerHTML = `
            <div class="chip-avatar"${avatarStyle}>${getInitials(player.full_name)}</div>
            <div class="chip-name">${player.full_name}</div>
            <div class="chip-remove" data-action="remove">
                <i class="bi bi-x"></i>
            </div>
        `;
        trayContainer.appendChild(chip);
    });

    // Handle Mode Panel: none (0), single-player (04.13, exactly 1), comparison (04.14, 2-3)
    if (panelContainer) {
        if (selectedPlayers.length === 1) {
            renderSinglePlayerPanel(selectedPlayers[0].id);
        } else if (isComparing) {
            renderComparisonPanel(selectedPlayers.map(p => p.id));
        } else {
            panelContainer.style.display = 'none';
        }
    }
}

/**
 * Clears and hides the search results dropdown. Called whenever a player is
 * added to the tray (from a search result row, or from a category/search
 * card) so a still-open (or stale "no results") dropdown never sits on top
 * of the tray chip / mode panel it just triggered.
 */
function closeSearchResults() {
    const searchInput = document.getElementById('player-search');
    const resultsContainer = document.getElementById('discovery-search-results');
    if (searchInput) searchInput.value = '';
    if (resultsContainer) {
        resultsContainer.innerHTML = '';
        resultsContainer.style.display = 'none';
    }
}

/**
 * Gets initials from a full name.
 * @param {string} name
 * @returns {string}
 */
function getInitials(name) {
    if (!name) return '?';
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
}

let toastTimeout;
/**
 * Shows a friendly inline message when the 2-player cap is hit.
 * @param {string} message 
 */
function showTrayToast(message) {
    let toast = document.getElementById('tray-toast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'tray-toast';
        toast.className = 'tray-toast';
        document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.classList.add('show');
    
    clearTimeout(toastTimeout);
    toastTimeout = setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

/**
 * Loads the full player list from the existing backend source.
 * Cached locally for fast client-side filtering.
 */
async function loadPlayers() {
    try {
        const response = await fetch('/get_players');
        if (!response.ok) throw new Error('Failed to fetch players');
        allPlayers = await response.json();
        console.log(`Discovery: Loaded ${allPlayers.length} players for search.`);
    } catch (error) {
        console.error('Discovery: Error loading players:', error);
    }
}

/**
 * Debounce helper to limit function execution frequency.
 * @param {Function} func - The function to debounce.
 * @param {number} wait - Delay in milliseconds.
 */
function debounce(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}


/**
 * Filters the player list and triggers rendering.
 * @param {string} query - The search query.
 */
function runSearch(query) {
    const resultsContainer = document.getElementById('discovery-search-results');
    if (!resultsContainer) return;

    // Requirement: Clear results if input is cleared or too short
    if (!query || query.trim().length < 3) {
        resultsContainer.innerHTML = '';
        resultsContainer.style.display = 'none';
        return;
    }

    const searchTerms = query.toLowerCase().trim().split(' ');
    
    const filtered = allPlayers.filter(p => {
        const fullName = p.full_name.toLowerCase();
        const teamName = p.team_name.toLowerCase();
        // Match if all search terms appear in either name or team
        return searchTerms.every(term => fullName.includes(term) || teamName.includes(term));
    });

    renderSearchResults(filtered, query.trim());
}

/**
 * Renders the filtered results or a no-match message.
 * @param {Array} results - Filtered player list.
 * @param {string} query - The search query for the empty state message.
 */
function renderSearchResults(results, query) {
    const resultsContainer = document.getElementById('discovery-search-results');
    if (!resultsContainer) return;

    resultsContainer.innerHTML = '';
    resultsContainer.style.display = 'block';

    if (results.length === 0) {
        const noResults = document.createElement('div');
        noResults.className = 'search-no-results';
        noResults.textContent = `No players match '${query}'`;
        resultsContainer.appendChild(noResults);
        return;
    }

    // Render up to 50 results for performance
    const displayResults = results.slice(0, 50);

    displayResults.forEach(player => {
        const row = document.createElement('div');
        row.className = 'search-result-row';
        row.innerHTML = `
            <div class="result-info">
                <div class="result-name">${player.full_name}</div>
                <div class="result-meta">${player.team_name} • ${player.position}</div>
            </div>
            <div class="result-action">
                <i class="bi bi-plus-circle"></i>
            </div>
        `;
        row.addEventListener('click', () => {
            addToTray(player.id, player);
        });
        resultsContainer.appendChild(row);
    });
}

/**
 * Renders a horizontally-scrolling category of player cards (Ticket 04.4).
 * When slotId is given, replaces that skeleton placeholder in place (see
 * loadDiscoveryCategories) rather than appending to the end - each category
 * loads independently and in parallel, so append-order can't be relied on.
 * @param {Object} config - Title, subtitle, and players array.
 * @param {string} [slotId]
 */
function renderCategory(config, slotId) {
    const categorySection = document.createElement('div');
    categorySection.className = 'category-section';
    if (slotId) categorySection.id = slotId;

    // Header
    const header = document.createElement('div');
    header.className = 'category-header';
    header.innerHTML = `
        <h3 class="category-title">${config.title}</h3>
        <p class="category-subtitle">${config.subtitle}</p>
    `;
    categorySection.appendChild(header);

    // Carousel
    const carousel = document.createElement('div');
    carousel.className = 'category-scroll';

    config.players.forEach(player => {
        const card = createPlayerCard(player);
        carousel.appendChild(card);
    });

    categorySection.appendChild(carousel);

    const slot = slotId ? document.getElementById(slotId) : null;
    if (slot) {
        slot.replaceWith(categorySection);
    } else {
        const categoriesContainer = document.getElementById('discovery-categories');
        if (categoriesContainer) categoriesContainer.appendChild(categorySection);
    }
}

/**
 * Grey pulsing placeholder for one category section, shown immediately on
 * page load (before any category data has arrived) so the page's eventual
 * shape is visible right away instead of staying blank while the 5 category
 * fetches are in flight.
 * @param {string} slotId
 */
function buildCategorySkeleton(slotId) {
    const cardSkeleton = `
        <div class="p-card-skeleton">
            <div class="p-card-top">
                <div class="skeleton" style="width:32px; height:32px; border-radius:50%; flex-shrink:0;"></div>
                <div class="p-card-info">
                    <div class="skeleton" style="width:75%; height:13px; margin-bottom:6px;"></div>
                    <div class="skeleton" style="width:50%; height:10px;"></div>
                </div>
            </div>
            <div class="skeleton" style="width:100%; height:40px;"></div>
            <div class="skeleton" style="width:90%; height:11px;"></div>
        </div>
    `;
    return `
        <div class="category-section" id="${slotId}">
            <div class="category-header">
                <div class="skeleton" style="width:160px; height:16px; margin-bottom:6px;"></div>
                <div class="skeleton" style="width:220px; height:12px;"></div>
            </div>
            <div class="category-scroll">${cardSkeleton.repeat(3)}</div>
        </div>
    `;
}

/**
 * Creates a player card element.
 * @param {Object} player 
 * @returns {HTMLElement}
 */
function createPlayerCard(player) {
    const card = document.createElement('div');
    const isSelected = selectedPlayers.some(p => p.id === player.id);
    card.className = `p-card ${isSelected ? 'selected' : ''}`;
    card.dataset.playerId = player.id;
    
    card.innerHTML = `
        <div class="p-card-top">
            <div class="p-card-avatar">${getInitials(player.full_name)}</div>
            <div class="p-card-info">
                <div class="p-card-name">${player.full_name}</div>
                <div class="p-card-meta">${player.team_name} • ${player.position}</div>
            </div>
            <div class="p-card-check" style="${isSelected ? '' : 'display:none'}">
                <i class="bi bi-check-circle-fill"></i>
            </div>
        </div>
        <div class="p-card-visual">
            <div class="sparkline-placeholder"></div>
        </div>
        <div class="p-card-why">
            ${player.why || 'Quietly delivering consistent returns.'}
        </div>
    `;

    card.addEventListener('click', () => {
        if (selectedPlayers.some(p => p.id === player.id)) {
            removeFromTray(player.id);
        } else {
            addToTray(player.id, player);
        }
    });

    return card;
}

/**
 * Updates the visual selected state of all category cards to match the tray.
 */
function updateCategorySelectionStates() {
    const cards = document.querySelectorAll('.p-card');
    cards.forEach(card => {
        const playerId = parseInt(card.dataset.playerId);
        const isSelected = selectedPlayers.some(p => p.id === playerId);
        
        if (isSelected) {
            card.classList.add('selected');
            const check = card.querySelector('.p-card-check');
            if (check) check.style.display = '';
        } else {
            card.classList.remove('selected');
            const check = card.querySelector('.p-card-check');
            if (check) check.style.display = 'none';
        }
    });
}

/**
 * Works out which average to show alongside the comparison charts: a
 * position-specific average when every given player shares the same
 * position, otherwise a leaguewide "overall" average.
 * @param {Array<Object>} players
 */
function averagesRequestFor(players) {
    const positions = [...new Set(players.map(p => p.position))];
    if (positions.length === 1 && POSITION_LABELS[positions[0]]) {
        return { position: positions[0], label: `${POSITION_LABELS[positions[0]]} average` };
    }
    return { position: null, label: 'Overall average' };
}

/**
 * Fetches the average-points/average-ownership reference line for the given
 * set of players from /get_comparison_averages (position-scoped or overall -
 * see averagesRequestFor). Cached per position/'overall' for the session.
 * @param {Array<Object>} players
 */
async function fetchAverages(players) {
    const { position, label } = averagesRequestFor(players);
    const cacheKey = position || 'overall';
    if (averagesCache.has(cacheKey)) {
        return averagesCache.get(cacheKey);
    }
    const url = position ? `/get_comparison_averages?position=${position}` : '/get_comparison_averages';
    const data = await fetch(url).then(r => r.json());
    const result = { avgPoints: data.points || [], avgOwnership: data.ownership || [], avgLabel: label };
    averagesCache.set(cacheKey, result);
    return result;
}

/**
 * Fetches one player's summary/fixtures/last5/ownership, using the session
 * cache when this player has already been loaded.
 * @param {number} playerId
 */
async function fetchPlayerData(playerId) {
    if (playerDataCache.has(playerId)) return playerDataCache.get(playerId);

    const [summary, fixtures, last5, ownership] = await Promise.all([
        fetch(`/get_player_summary?id=${playerId}`).then(r => r.json()),
        fetch(`/get_next_5_gameweeks?id=${playerId}`).then(r => r.json()),
        fetch(`/get_player_last_5_points?id=${playerId}`).then(r => r.json()),
        fetch(`/get_player_ownership_history?id=${playerId}`).then(r => r.json())
    ]);

    const data = { summary: Array.isArray(summary) ? summary[0] : summary, fixtures, last5, ownership };
    playerDataCache.set(playerId, data);
    return data;
}

/**
 * Fetches the global player index-score list once per session (same source
 * radar.js's player profile bottom sheet uses for its Rating Breakdown/
 * Overall value score).
 */
async function fetchIndexScores() {
    if (indexScoresCache) return indexScoresCache;
    indexScoresCache = await fetch('/get_player_index_scores').then(r => r.json()).catch(() => []);
    return indexScoresCache;
}

/**
 * Matches a player's own index-score entry, excluding the synthetic "Mean"
 * row and guarding against a DB/live-API identity mismatch during a season
 * rollover - same safety check as radar.js's player bottom sheet.
 * @param {Object} summary
 * @param {Array<Object>} indexScores
 */
function resolveIndexEntry(summary, indexScores) {
    const raw = (indexScores || []).find(r => r.id === summary.id && r.web_name !== 'Mean') || null;
    return (raw && raw.web_name === summary.name) ? raw : null;
}

/**
 * Grey pulsing placeholder shown while the mode panel's data is loading -
 * mirrors the eventual card shape (header, one metric card, controls) so
 * switching players doesn't leave the page looking unresponsive/blank.
 */
function buildPanelSkeleton() {
    return `
        <div class="mp-header">
            <div class="skeleton" style="width:140px; height:20px; margin:0 auto;"></div>
        </div>
        <div class="mp-track-container">
            <div class="mp-card">
                <div class="skeleton" style="width:110px; height:11px; margin-bottom:16px;"></div>
                <div class="mp-visual">
                    <div class="skeleton" style="width:100%; height:90px;"></div>
                </div>
                <div class="skeleton" style="width:75%; height:12px; margin-top:8px;"></div>
            </div>
        </div>
        <div class="mp-controls">
            <div class="skeleton" style="width:40px; height:40px; border-radius:50%;"></div>
            <div class="mp-dots">${Array(5).fill('<div class="mp-dot"></div>').join('')}</div>
            <div class="skeleton" style="width:40px; height:40px; border-radius:50%;"></div>
        </div>
    `;
}

/**
 * Renders the comparison metric swipe panel (Ticket 04.14, generalised to
 * 2-3 players).
 * @param {Array<number>} playerIds
 */
async function renderComparisonPanel(playerIds) {
    const container = document.getElementById('mode-panel-container');
    if (!container) return;

    const cacheKey = [...playerIds].sort((a,b) => a-b).join(',');

    // Show loading state if switching comparison group
    if (!panelData || !panelData.isComparison || panelData.cacheKey !== cacheKey) {
        container.innerHTML = buildPanelSkeleton();
        container.style.display = 'block';
        panelMetricIndex = 0;

        try {
            const [results, averages, indexScores] = await Promise.all([
                Promise.all(playerIds.map(async (playerId) => {
                    const { summary: s, fixtures, last5, ownership } = await fetchPlayerData(playerId);
                    return {
                        id: playerId,
                        name: s.name,
                        form: last5.map(d => d.points),
                        fixtures: fixtures,
                        ownership: ownership,
                        summary: s
                    };
                })),
                fetchAverages(selectedPlayers),
                fetchIndexScores()
            ]);

            results.forEach(p => { p.indexEntry = resolveIndexEntry(p.summary, indexScores); });

            panelData = {
                isComparison: true,
                cacheKey: cacheKey,
                players: results,
                ...averages
            };
        } catch (error) {
            console.error("Discovery: Failed to load comparison data", error);
            container.innerHTML = '<div class="mp-header"><p class="sub">Error loading comparison data.</p></div>';
            return;
        }
    }

    updatePanelUI();
}

/**
 * Renders the single-player metric swipe panel (Ticket 04.13).
 * @param {number} playerId 
 */
async function renderSinglePlayerPanel(playerId) {
    const container = document.getElementById('mode-panel-container');
    if (!container) return;

    // Show loading state if switching players
    if (!panelData || panelData.isComparison || panelData.id !== playerId) {
        container.innerHTML = buildPanelSkeleton();
        container.style.display = 'block';
        panelMetricIndex = 0;
        
        try {
            const player = selectedPlayers.find(p => p.id === playerId) || null;
            const [{ summary: s, fixtures, last5, ownership }, averages, indexScores] = await Promise.all([
                fetchPlayerData(playerId),
                fetchAverages(player ? [player] : []),
                fetchIndexScores()
            ]);

            panelData = {
                id: playerId,
                isComparison: false,
                name: s.name,
                form: last5.map(d => d.points),
                avgForm: averages.avgPoints,
                avgOwnership: averages.avgOwnership,
                avgLabel: averages.avgLabel,
                fixtures: fixtures,
                ownership: ownership,
                summary: s,
                indexEntry: resolveIndexEntry(s, indexScores)
            };
        } catch (error) {
            console.error("Discovery: Failed to load panel data", error);
            container.innerHTML = '<div class="mp-header"><p class="sub">Error loading player data.</p></div>';
            return;
        }
    }

    updatePanelUI();
}

/**
 * One metric's worth of comparison content: a horizontal bar with one
 * coloured dot per player - value labelled directly above the dot - plus a
 * dotted average marker, so the comparison reads as a shape, not a stack of
 * numbers. Player names/colours are shown once, via a shared legend built
 * by the caller (buildChartLegend) rather than repeated under every block.
 * Shared by the comparison Season Numbers and Summary metrics.
 * @param {string} label - the metric name, e.g. "Points" or "Season points".
 * @param {Array<Object>} players
 * @param {(player: Object, index: number) => {value: number|null, display: string, avgValue?: number}} valueFn
 *   avgValue, if given, is THAT player's own average - drawn as a small dotted
 *   tick in their own colour (used when players' averages genuinely differ,
 *   e.g. by position). Use options.avgValue instead for a single shared average.
 * @param {Object} [options]
 * @param {number} [options.avgValue] - a single shared average, drawn as one dashed grey line (omit when each player's own average differs - see valueFn's avgValue)
 * @param {number} [options.min] - explicit scale min (default 0)
 * @param {number} [options.max] - explicit scale max (defaults to the largest value/average seen)
 * @param {[string, string]} [options.axisLabels] - what the left/right ends of the bar mean, e.g. ['Easier', 'Tougher'] (defaults to the numeric min/max)
 * @param {string} [options.compareText] - one shared caption under the block, e.g. a scale explainer
 */
function buildStatBlock(label, players, valueFn, options = {}) {
    const results = players.map((p, i) => valueFn(p, i) || { value: null, display: '—' });
    const min = options.min != null ? options.min : 0;
    const numericValues = results.map(r => r.value).filter(v => v !== null && v !== undefined);
    const perPlayerAvgs = results.map(r => r.avgValue).filter(v => v !== null && v !== undefined);
    const scaleValues = [...numericValues, ...perPlayerAvgs];
    if (options.avgValue != null) scaleValues.push(options.avgValue);
    const max = options.max != null ? options.max : Math.max(...scaleValues, min + 1);
    const range = (max - min) || 1;
    const pctOf = v => Math.max(0, Math.min(100, ((v - min) / range) * 100));

    const avgTicks = options.avgValue != null
        ? `<div class="mp-stat-avg-marker" style="left:${pctOf(options.avgValue)}%;"></div>`
        : results.map((r, i) => (r.avgValue !== null && r.avgValue !== undefined)
            ? `<div class="mp-stat-avg-tick" style="left:${pctOf(r.avgValue)}%; border-color:${COMPARISON_COLORS[i]};" title="${players[i].name}'s average: ${r.avgValue}"></div>`
            : '').join('');

    // Collision avoidance: when 2-3 players' values sit close enough together
    // that their labels would overlap and become unreadable, alternate the
    // close ones between above the dot (default) and below the track.
    const DOT_VALUE_COLLISION_PCT = 15; // roughly the width a 3-digit label needs
    const sortedByPct = results
        .map((r, i) => (r.value !== null && r.value !== undefined) ? { i, pct: pctOf(r.value) } : null)
        .filter(Boolean)
        .sort((a, b) => a.pct - b.pct);
    const belowLevel = new Array(results.length).fill(false);
    for (let k = 1; k < sortedByPct.length; k++) {
        if (sortedByPct[k].pct - sortedByPct[k - 1].pct < DOT_VALUE_COLLISION_PCT) {
            belowLevel[sortedByPct[k].i] = !belowLevel[sortedByPct[k - 1].i];
        }
    }

    const dots = results.map((r, i) => {
        if (r.value === null || r.value === undefined) return '';
        const pct = pctOf(r.value);
        const valueClass = belowLevel[i] ? 'mp-stat-dot-value below' : 'mp-stat-dot-value';
        return `<div class="${valueClass}" style="left:${pct}%; color:${COMPARISON_COLORS[i]};">${r.display}</div>
            <div class="mp-stat-dot" style="left:${pct}%; background:${COMPARISON_COLORS[i]};" title="${players[i].name}: ${r.display}"></div>`;
    }).join('');

    const axisLeft = options.axisLabels ? options.axisLabels[0] : `${Math.round(min)}`;
    const axisRight = options.axisLabels ? options.axisLabels[1] : `${Math.round(max)}`;

    return `<div class="mp-stat-block">
        <div class="mp-stat-label">${label}</div>
        <div class="mp-stat-bar-wrap">
            <div class="mp-stat-bar-track">${avgTicks}${dots}</div>
        </div>
        <div class="mp-stat-axis-labels">
            <span>${axisLeft}</span>
            <span>${axisRight}</span>
        </div>
        ${options.compareText ? `<div class="mp-stat-compare">${options.compareText}</div>` : ''}
    </div>`;
}

/**
 * Season Numbers content for a single player - same metrics/labels as
 * radar.js's player bottom sheet Season Numbers card (02.5).
 * @param {Object} summary
 */
function buildSeasonNumbersSingle(summary) {
    if (!summary.metrics || summary.metrics.length === 0) {
        return { visual: '<p class="mp-note">Season totals aren\'t available for this player right now.</p>', note: '' };
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

    const note = summary.is_pre_season
        ? `Still last season's final numbers - these reset once gameweek 1 locks. Position average alongside for now.`
        : `Season totals so far, with the average for other ${(summary.position_name || 'players').toLowerCase()}s alongside.`;

    return { visual: `<div class="season-grid">${cells}</div>`, note };
}

/**
 * Season Numbers content for 2-3 players - each player's own value plus
 * their own position average, one metric block per row, stacked full-width
 * (mobile-first, not the side-by-side columns Fixtures used to use).
 * @param {Array<Object>} players
 */
function buildSeasonNumbersComparison(players) {
    const applicableStats = SEASON_STATS.filter(s =>
        !s.positionsOnly || players.some(p => s.positionsOnly.includes(p.summary.position_name))
    );
    if (!applicableStats.length) {
        return { visual: '<p class="mp-note">Season totals aren\'t available for these players right now.</p>', note: '' };
    }
    // Each player's average is drawn as their own dotted tick (via valueFn's
    // avgValue), not one shared options.avgValue line - their "position
    // average" genuinely differs player to player when comparing across
    // positions, so one dashed line for all of them would misrepresent it.
    const blocks = applicableStats.map(s => buildStatBlock(s.label, players, (p) => {
        if (s.positionsOnly && !s.positionsOnly.includes(p.summary.position_name)) return { value: null, display: '—' };
        const m = (p.summary.metrics || []).find(mm => mm.title === s.metricTitle);
        if (!m) return { value: null, display: '—' };
        return { value: Number(m.value) || 0, display: formatStatValue(m.value), avgValue: Number(m.averageValue) || 0 };
    })).join('');
    const legend = buildChartLegend(players.map((p, i) => ({ label: p.name, color: COMPARISON_COLORS[i] })));

    return {
        visual: `<div class="mp-stat-list">${blocks}</div>${legend}`,
        note: `The dotted tick under each dot is that player's own position average.`
    };
}

/**
 * Summary content for a single player - same 4 rows as radar.js's player
 * bottom sheet Summary card, reusing the shared summaryRow() bar+marker.
 * @param {Object} panelDataSingle
 */
function buildSummarySingle(panelDataSingle) {
    const { summary, fixtures, form, avgForm, avgLabel, indexEntry } = panelDataSingle;
    const rows = [];

    if (form.length) {
        const total = form.reduce((a, b) => a + b, 0);
        const avgTotal = (avgForm || []).reduce((a, b) => a + b, 0);
        const max = Math.max(total, avgTotal, 1);
        rows.push(summaryRow('Form, last 5 gameweeks', `${total} pts`, `${avgLabel}: ${avgTotal} pts`, (total / max) * 100, (avgTotal / max) * 100));
    }

    const realFixtures = (fixtures || []).filter(f => f.homeOrAway !== 'Blank');
    if (realFixtures.length) {
        const avgDiff = realFixtures.reduce((a, f) => a + f.difficulty, 0) / realFixtures.length;
        const withLeagueAvg = realFixtures.filter(f => f.leagueAverageDifficulty !== null && f.leagueAverageDifficulty !== undefined);
        const leagueAvgDiff = withLeagueAvg.length
            ? withLeagueAvg.reduce((a, f) => a + f.leagueAverageDifficulty, 0) / withLeagueAvg.length
            : null;
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
        return { visual: '<p class="mp-note">Not enough data yet to summarise this player.</p>', note: '' };
    }
    return { visual: `<div class="mp-summary-rows">${rows.join('')}</div>`, note: "Each row uses the same numbers as the earlier cards - solid bar is this player, the marker is the average it's being judged against." };
}

/**
 * Summary content for 2-3 players - the same headline figures as the
 * single-player Summary card, generalised into one stacked block per row
 * (mobile-first) instead of a single-player bar+marker.
 * @param {Object} panelDataComparison
 */
function buildSummaryComparison(panelDataComparison) {
    const players = panelDataComparison.players;
    const blocks = [];

    const avgPointsTotal = (panelDataComparison.avgPoints || []).reduce((a, b) => a + b, 0);
    blocks.push(buildStatBlock(
        'Form, last 5 gameweeks', players,
        (p) => {
            const total = p.form.reduce((a, b) => a + b, 0);
            return { value: total, display: `${total} pts` };
        },
        { avgValue: avgPointsTotal, compareText: `Dotted line: ${panelDataComparison.avgLabel.toLowerCase()} (${avgPointsTotal} pts)` }
    ));

    if (players.some(p => (p.fixtures || []).some(f => f.homeOrAway !== 'Blank'))) {
        // Each player's own tick is their own league-average comparison point
        // (same figure the single-player version compares to) - these can
        // genuinely differ fixture-set to fixture-set, so each gets its own
        // dotted tick rather than one shared line.
        blocks.push(buildStatBlock('Next 5 fixtures difficulty', players, (p) => {
            const real = (p.fixtures || []).filter(f => f.homeOrAway !== 'Blank');
            if (!real.length) return { value: null, display: '—' };
            const avgDiff = real.reduce((a, f) => a + f.difficulty, 0) / real.length;
            const withLeagueAvg = real.filter(f => f.leagueAverageDifficulty !== null && f.leagueAverageDifficulty !== undefined);
            const leagueAvgDiff = withLeagueAvg.length
                ? withLeagueAvg.reduce((a, f) => a + f.leagueAverageDifficulty, 0) / withLeagueAvg.length
                : null;
            return { value: avgDiff, display: `${avgDiff.toFixed(1)}/5`, avgValue: leagueAvgDiff };
        }, { min: 1, max: 5, axisLabels: ['Easier', 'Tougher'] }));
    }

    if (players.some(p => (p.summary.metrics || []).some(m => m.title === 'Points'))) {
        blocks.push(buildStatBlock('Season points', players, (p) => {
            const m = (p.summary.metrics || []).find(mm => mm.title === 'Points');
            return m ? { value: Number(m.value) || 0, display: formatStatValue(m.value), avgValue: Number(m.averageValue) || 0 } : { value: null, display: '—' };
        }));
    }

    if (players.some(p => p.indexEntry)) {
        blocks.push(buildStatBlock('Overall value score', players, (p) => (
            p.indexEntry
                ? { value: Number(p.indexEntry.player_score), display: `${Number(p.indexEntry.player_score).toFixed(0)}/100` }
                : { value: null, display: '—' }
        ), { avgValue: 50, max: 100, compareText: 'Scale: 0-100 across all players' }));
    }

    if (!blocks.length) {
        return { visual: '<p class="mp-note">Not enough data yet to summarise these players.</p>', note: '' };
    }
    const legend = buildChartLegend(players.map((p, i) => ({ label: p.name, color: COMPARISON_COLORS[i] })));
    return { visual: `<div class="mp-stat-list">${blocks.join('')}</div>${legend}`, note: '' };
}

/**
 * Updates the Mode Panel UI based on current panelData and panelMetricIndex.
 */
function updatePanelUI() {
    const container = document.getElementById('mode-panel-container');
    if (!container || !panelData) return;

    let headerHtml = '';
    let contentHtml = '';
    const metricTitles = ['Recent Form', 'Next 5 Fixtures', 'Ownership Trend', 'Season Numbers', 'Summary'];
    const currentTitle = metricTitles[panelMetricIndex];

    if (panelData.isComparison) {
        const players = panelData.players; // 2-3, driven by the tray (cap: TRAY_CAP)
        const playerLegendEntries = players.map((p, i) => ({ label: p.name, color: COMPARISON_COLORS[i] }));
        const avgLegendEntry = { label: panelData.avgLabel, dashed: true };

        headerHtml = `<h4 class="mp-player-name">Comparison</h4>`;

        let visualHtml = '';
        let noteHtml = '';

        if (panelMetricIndex === 0) { // Form - one shared chart, one line per player, plus the average
            const chart = buildMultiLineChart({
                series: players.map((p, i) => ({ color: COMPARISON_COLORS[i], values: p.form, label: getInitials(p.name) })),
                avgSeries: panelData.avgPoints,
                w: 260, h: 90, padTop: 6, padBottom: 14, padLeft: 22, padRight: 4,
                formatValue: v => `${v}`
            });
            visualHtml = `<div class="mp-visual">${chart}</div>${buildChartLegend([...playerLegendEntries, avgLegendEntry])}`;
            noteHtml = `<p class="mp-note">Dashed line shows the ${panelData.avgLabel.toLowerCase()} over the same 5 gameweeks. The dot at the end of each line is that player's own initial.</p>`;
        } else if (panelMetricIndex === 1) { // Fixtures - mobile-first: one full-width row per player, stacked vertically
            visualHtml = `
                <div class="mp-fixture-list">
                    ${players.map((p, i) => `
                        <div class="mp-fixture-player">
                            <div class="mp-player-name"><span class="chart-legend-dot" style="background:${COMPARISON_COLORS[i]};"></span>${p.name}</div>
                            <div class="fixture-chip-row">${buildFixtureChips(p.fixtures)}</div>
                            <p class="mp-note">${describeFixtureRun(p.fixtures)}</p>
                        </div>
                    `).join('')}
                </div>
            `;
        } else if (panelMetricIndex === 2) { // Ownership - one shared chart, one line per player, plus the average
            const chart = buildMultiLineChart({
                series: players.map((p, i) => ({ color: COMPARISON_COLORS[i], values: p.ownership, label: getInitials(p.name) })),
                avgSeries: panelData.avgOwnership,
                w: 260, h: 90, padTop: 6, padBottom: 16, padLeft: 24, padRight: 4,
                formatValue: v => `${v.toFixed(1)}%`
            });
            visualHtml = `<div class="mp-visual">${chart}</div>${buildChartLegend([...playerLegendEntries, avgLegendEntry])}`;
            noteHtml = `
                <div class="mp-comparison-note-row">
                    ${players.map((p, i) => `<p class="mp-note"><span class="chart-legend-dot" style="background:${COMPARISON_COLORS[i]};"></span>${p.name}: ${p.summary.selected_by_percent}% ownership.</p>`).join('')}
                </div>
            `;
        } else if (panelMetricIndex === 3) { // Season Numbers
            const { visual, note } = buildSeasonNumbersComparison(players);
            visualHtml = visual;
            noteHtml = note ? `<p class="mp-note">${note}</p>` : '';
        } else { // Summary
            const { visual, note } = buildSummaryComparison(panelData);
            visualHtml = visual;
            noteHtml = note ? `<p class="mp-note">${note}</p>` : '';
        }

        contentHtml = `
            <div class="mp-card">
                <span class="mp-metric-title">${currentTitle}</span>
                ${visualHtml}
                ${noteHtml}
            </div>
        `;
    } else {
        headerHtml = `<h4 class="mp-player-name">${panelData.name}</h4>`;

        let visualHtml = '';
        let noteText = '';
        if (panelMetricIndex === 0) {
            visualHtml = buildSparkline(panelData.form, panelData.avgForm);
            noteText = 'Consistent delivery over the last 5 gameweeks.';
        } else if (panelMetricIndex === 1) {
            visualHtml = `<div class="fixture-chip-row">${buildFixtureChips(panelData.fixtures)}</div>`;
            noteText = describeFixtureRun(panelData.fixtures);
        } else if (panelMetricIndex === 2) {
            visualHtml = buildOwnershipArea(panelData.ownership, panelData.avgOwnership);
            noteText = `Currently owned by ${panelData.summary.selected_by_percent}% of managers.`;
        } else if (panelMetricIndex === 3) {
            const { visual, note } = buildSeasonNumbersSingle(panelData.summary);
            visualHtml = visual;
            noteText = note;
        } else {
            const { visual, note } = buildSummarySingle(panelData);
            visualHtml = visual;
            noteText = note;
        }

        contentHtml = `
            <div class="mp-card">
                <span class="mp-metric-title">${currentTitle}</span>
                <div class="mp-visual">${visualHtml}</div>
                ${noteText ? `<p class="mp-note">${noteText}</p>` : ''}
            </div>
        `;
    }

    container.innerHTML = `
        <div class="mp-header">
            ${headerHtml}
        </div>
        
        <div class="mp-track-container">
            ${contentHtml}
        </div>

        <div class="mp-controls">
            <button class="mp-btn" id="mp-prev" ${panelMetricIndex === 0 ? 'disabled' : ''}>
                <i class="bi bi-chevron-left"></i>
            </button>
            <div class="mp-dots">
                ${metricTitles.map((_, i) => `<div class="mp-dot ${i === panelMetricIndex ? 'active' : ''}"></div>`).join('')}
            </div>
            <button class="mp-btn" id="mp-next" ${panelMetricIndex === metricTitles.length - 1 ? 'disabled' : ''}>
                <i class="bi bi-chevron-right"></i>
            </button>
        </div>
    `;

    // Bind events
    document.getElementById('mp-prev').onclick = () => {
        if (panelMetricIndex > 0) {
            panelMetricIndex--;
            updatePanelUI();
        }
    };
    document.getElementById('mp-next').onclick = () => {
        if (panelMetricIndex < metricTitles.length - 1) {
            panelMetricIndex++;
            updatePanelUI();
        }
    };
}
function initializeDiscovery() {
    const searchInput = document.getElementById('player-search');
    if (searchInput) {
        // Requirement: ~250ms debounce
        const debouncedSearch = debounce((e) => runSearch(e.target.value), 250);
        searchInput.addEventListener('input', debouncedSearch);
        
        // Handle case where user clears input via 'x' button (in some browsers)
        searchInput.addEventListener('search', (e) => runSearch(e.target.value));
    }

    // Event delegation for tray remove buttons
    const trayContainer = document.getElementById('discovery-tray');
    if (trayContainer) {
        trayContainer.addEventListener('click', (e) => {
            const removeBtn = e.target.closest('[data-action="remove"]');
            if (removeBtn) {
                const chip = removeBtn.closest('.tray-chip');
                if (chip) {
                    removeFromTray(parseInt(chip.dataset.playerId));
                }
            }
        });
    }

    // Load real and placeholder categories
    loadDiscoveryCategories();

    // Initial tray render
    renderTray();

    loadPlayers();
}

const CATEGORY_SLOTS = {
    underTheRadar: 'category-under-the-radar',
    worthWatching: 'category-worth-watching',
    mostConsistent: 'category-most-consistent',
    momentum: 'category-momentum',
    newManager: 'category-new-manager'
};

/**
 * Loads and renders discovery categories from real backend sources. Renders
 * a skeleton placeholder for all 5 immediately, then fires all 5 fetches in
 * parallel rather than one after another - each independently swaps its own
 * skeleton for real content (or removes it, for New manager in charge, if
 * it comes back empty) as soon as its own fetch resolves.
 */
async function loadDiscoveryCategories() {
    const categoriesContainer = document.getElementById('discovery-categories');
    if (!categoriesContainer) return;

    categoriesContainer.innerHTML = Object.values(CATEGORY_SLOTS).map(buildCategorySkeleton).join('');

    await Promise.all([
        loadUnderTheRadarCategory(),
        loadWorthWatchingCategory(),
        loadMostConsistentCategory(),
        loadMomentumCategory(),
        loadNewManagerCategory()
    ]);
}

// 1. Under the radar (Ticket 04.8)
async function loadUnderTheRadarCategory() {
    const slotId = CATEGORY_SLOTS.underTheRadar;
    try {
        const response = await fetch('/get_under_the_radar');
        if (response.ok) {
            const players = await response.json();
            renderCategory({ title: "Under the radar", subtitle: "Low ownership, quietly delivering", players }, slotId);
        } else {
            console.error('Discovery: Failed to fetch "Under the radar" players');
            document.getElementById(slotId)?.remove();
        }
    } catch (error) {
        console.error('Discovery: Error loading "Under the radar":', error);
        document.getElementById(slotId)?.remove();
    }
}

// 2. Worth watching this week (Ticket 04.9)
async function loadWorthWatchingCategory() {
    const slotId = CATEGORY_SLOTS.worthWatching;
    try {
        const response = await fetch('/get_worth_watching');
        if (response.ok) {
            const players = await response.json();
            renderCategory({
                title: "Worth watching this week",
                subtitle: "Good form meeting a kind run of games",
                players: players.map(p => ({
                    id: p.id,
                    full_name: p.web_name, // Backend uses web_name
                    team_name: p.team_name,
                    position: p.position || "ALL", // Fallback if not provided
                    why: p.why
                }))
            }, slotId);
        } else {
            console.error('Discovery: Failed to fetch "Worth watching this week" players');
            document.getElementById(slotId)?.remove();
        }
    } catch (error) {
        console.error('Discovery: Error loading "Worth watching this week":', error);
        document.getElementById(slotId)?.remove();
    }
}

// 3. Rarely lets you down (Ticket 04.10)
async function loadMostConsistentCategory() {
    const slotId = CATEGORY_SLOTS.mostConsistent;
    try {
        const response = await fetch('/get_most_consistent');
        if (response.ok) {
            const players = await response.json();
            renderCategory({
                title: "Rarely lets you down",
                subtitle: "Consistent returns, minimum variance",
                players: players.map(p => ({
                    id: p.id,
                    full_name: p.name,
                    team_name: p.team,
                    position: p.position,
                    why: p.why
                }))
            }, slotId);
        } else {
            console.error('Discovery: Failed to fetch "Rarely lets you down" players');
            document.getElementById(slotId)?.remove();
        }
    } catch (error) {
        console.error('Discovery: Error loading "Rarely lets you down":', error);
        document.getElementById(slotId)?.remove();
    }
}

// 4. Everyone's jumping on (Ticket 04.11)
async function loadMomentumCategory() {
    const slotId = CATEGORY_SLOTS.momentum;
    try {
        const response = await fetch('/get_momentum');
        if (response.ok) {
            const players = await response.json();
            renderCategory({
                title: "Everyone's jumping on",
                subtitle: "Ownership climbing fast - bandwagon or smart money?",
                players: players.map(p => ({
                    id: p.id,
                    full_name: p.name,
                    team_name: p.team,
                    position: p.position,
                    why: p.why
                }))
            }, slotId);
        } else {
            console.error('Discovery: Failed to fetch "Everyone\'s jumping on" players');
            document.getElementById(slotId)?.remove();
        }
    } catch (error) {
        console.error('Discovery: Error loading "Everyone\'s jumping on":', error);
        document.getElementById(slotId)?.remove();
    }
}

// 5. New manager in charge (Ticket 04.12) - hidden entirely (skeleton removed,
// nothing rendered in its place) when zero teams currently qualify.
async function loadNewManagerCategory() {
    const slotId = CATEGORY_SLOTS.newManager;
    try {
        const response = await fetch('/get_new_manager');
        if (response.ok) {
            const players = await response.json();
            if (players && players.length > 0) {
                renderCategory({
                    title: "New manager in charge",
                    subtitle: "Tactics are shifting - could change who starts",
                    players: players.map(p => ({
                        id: p.id,
                        full_name: p.name,
                        team_name: p.team,
                        position: p.position,
                        why: p.why
                    }))
                }, slotId);
            } else {
                document.getElementById(slotId)?.remove();
            }
        } else {
            console.error('Discovery: Failed to fetch "New manager in charge" players');
            document.getElementById(slotId)?.remove();
        }
    } catch (error) {
        console.error('Discovery: Error loading "New manager in charge":', error);
        document.getElementById(slotId)?.remove();
    }
}

// Ensure initialization
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeDiscovery);
} else {
    initializeDiscovery();
}
