/***** playerSheet.js *****/
// The player sheet (one player) and the side-by-side compare (two players).
// Pure: takes the /api/week/player-context players and returns HTML strings.
// The compare reuses Discovery's bar-and-dot style via lib/statBlock.js.
import { escapeHtml } from './escapeHtml.js';
import { buildStatBlock, buildChartLegend, COMPARISON_COLORS } from './statBlock.js';
import {
    COPY, priceText, venueText, difficultyWord, expectedPointsText, pointsWord,
    gameLine, noGamesAgainst, positionAverageText,
} from './playerInfoCopy.js';

const e = escapeHtml;

export function renderPlayerSheetSkeleton() {
    return `
        <div class="player-sheet" aria-busy="true">
            <div class="skeleton" style="height:22px;width:55%;margin-bottom:10px;"></div>
            <div class="skeleton" style="height:14px;width:80%;margin-bottom:18px;"></div>
            <div class="skeleton" style="height:90px;margin-bottom:12px;"></div>
            <div class="skeleton" style="height:70px;"></div>
        </div>`;
}

export function renderPlayerSheetMessage(text) {
    return `<div class="player-sheet"><p class="sub">${e(text)}</p></div>`;
}

function mean(values) {
    const nums = values.filter((v) => typeof v === 'number');
    if (nums.length === 0) return null;
    return nums.reduce((a, b) => a + b, 0) / nums.length;
}

function oneDecimal(n) {
    return (Math.round(n * 10) / 10).toFixed(1);
}

function recentGames(player) {
    return Array.isArray(player.recent_games) ? player.recent_games : [];
}

function gamesAgainst(player) {
    return player.vs_opponent && Array.isArray(player.vs_opponent.games) ? player.vs_opponent.games : null;
}

function header(player) {
    const facts = [player.team_short, player.position, priceText(player.price)].filter(Boolean).map(e).join(' · ');
    const avg = positionAverageText(player.position_average_expected_points);
    return `
        <h3 class="player-sheet-name">${e(player.name)}</h3>
        <p class="sub">${facts}</p>
        <p class="player-sheet-predicted">${e(expectedPointsText(player.expected_points))}${avg ? ` <span class="sub">(${e(avg)})</span>` : ''}</p>`;
}

function last5Section(player) {
    const games = recentGames(player);
    const body = games.length === 0
        ? `<p class="sub">${e(COPY.noRecentGames)}</p>`
        : `<ul class="sheet-list">${games.map((g) => `
            <li><span>Gameweek ${e(g.gameweek)} · ${e(g.opponent_short)} (${venueText(g.is_home)})<span class="sub sheet-list-detail">${e(gameLine(g))}</span></span><strong>${e(pointsWord(g.points))}</strong></li>`).join('')}</ul>`;
    return section(COPY.last5Heading, body);
}

function momentumSection(player) {
    const m = player.momentum;
    let body;
    if (!m || !m.label) {
        body = `<p class="sub">${e(COPY.noMomentum)}</p>`;
    } else {
        // The stored reason starts with the label ("Rising: ..."), which is already the heading.
        let reason = m.reason ? String(m.reason) : '';
        const prefix = `${m.label}: `;
        if (reason.startsWith(prefix)) reason = reason.slice(prefix.length);
        reason = reason.charAt(0).toUpperCase() + reason.slice(1);
        body = `<p><strong>${e(m.label)}</strong>${reason ? `. ${e(reason)}` : ''}</p>`;
    }
    return section(COPY.momentumHeading, body);
}

function fixtureLine(f) {
    const word = difficultyWord(f.difficulty);
    return `Gameweek ${e(f.gameweek)} · ${e(f.opponent_short)} (${venueText(f.is_home)})${word ? ` · ${e(word)}` : ''}`;
}

function nextSection(player) {
    const list = Array.isArray(player.next_fixtures) ? player.next_fixtures : [];
    const body = list.length === 0
        ? `<p class="sub">${e(COPY.noNextFixtures)}</p>`
        : `<ul class="sheet-list">${list.map((f) => `<li><span>${fixtureLine(f)}</span></li>`).join('')}</ul>`;
    return section(COPY.nextHeading, body);
}

function againstSection(player) {
    const vs = player.vs_opponent;
    if (!vs) return section('Against this week\'s opponent', `<p class="sub">${e(COPY.noMatchThisWeek)}</p>`);
    const games = gamesAgainst(player) || [];
    const body = games.length === 0
        ? `<p class="sub">${e(noGamesAgainst(vs.opponent_short))}</p>`
        : `<ul class="sheet-list">${games.map((g) => `
            <li><span>${e(g.season)}, gameweek ${e(g.gameweek)} (${venueText(g.is_home)})<span class="sub sheet-list-detail">${e(g.minutes)} minutes</span></span><strong>${e(pointsWord(g.points))}</strong></li>`).join('')}</ul>`;
    return section(`Against ${vs.opponent_short}`, body);
}

function section(title, body) {
    return `<section class="sheet-section"><h4 class="sheet-section-title">${e(title)}</h4>${body}</section>`;
}

export function renderSinglePlayer(player) {
    return `
        <div class="player-sheet">
            ${header(player)}
            ${last5Section(player)}
            ${momentumSection(player)}
            ${nextSection(player)}
            ${againstSection(player)}
        </div>`;
}

// Stat blocks for the compare. Each returns '' when neither player has the number.
function expectedBlock(players) {
    if (players.every((p) => p.expected_points === null || p.expected_points === undefined)) return '';
    return buildStatBlock(COPY.expectedBlockLabel, players, (p) => {
        const has = p.expected_points !== null && p.expected_points !== undefined;
        const avg = p.position_average_expected_points;
        return {
            value: has ? p.expected_points : null,
            display: has ? oneDecimal(p.expected_points) : '—',
            avgValue: avg === null || avg === undefined ? undefined : avg,
        };
    }, { compareText: 'The dotted line is the average for that player\'s position.' });
}

function recentAverageBlock(players) {
    const avgs = players.map((p) => mean(recentGames(p).map((g) => g.points)));
    if (avgs.every((a) => a === null)) return '';
    return buildStatBlock('Average points, last 5 games', players, (p, i) => (
        avgs[i] === null ? { value: null, display: '—' } : { value: avgs[i], display: oneDecimal(avgs[i]) }
    ));
}

function minutesBlock(players) {
    const totals = players.map((p) => {
        const g = recentGames(p);
        return g.length === 0 ? null : g.reduce((sum, x) => sum + (x.minutes || 0), 0);
    });
    if (totals.every((t) => t === null)) return '';
    return buildStatBlock('Minutes, last 5 games', players, (p, i) => (
        totals[i] === null ? { value: null, display: '—' } : { value: totals[i], display: String(totals[i]) }
    ), { min: 0, max: 450 });
}

function againstBlock(players) {
    const avgs = players.map((p) => {
        const g = gamesAgainst(p);
        return g && g.length ? mean(g.map((x) => x.points)) : null;
    });
    if (avgs.every((a) => a === null)) return '';
    return buildStatBlock('Average points against this week\'s opponent', players, (p, i) => (
        avgs[i] === null ? { value: null, display: '—' } : { value: avgs[i], display: oneDecimal(avgs[i]) }
    ), { compareText: 'Games from this season and last season.' });
}

function fixtureColumns(players) {
    const columns = players.map((p, i) => {
        const list = Array.isArray(p.next_fixtures) ? p.next_fixtures : [];
        const rows = list.length === 0
            ? `<li class="sub">${e(COPY.noNextFixtures)}</li>`
            : list.map((f) => `<li>${fixtureLine(f)}</li>`).join('');
        return `
            <div class="compare-col">
                <div class="compare-col-name"><span class="chart-legend-dot" style="background:${COMPARISON_COLORS[i]};"></span>${e(p.name)}</div>
                <ul class="compare-fixtures">${rows}</ul>
            </div>`;
    }).join('');
    return section(COPY.nextFixturesCompareHeading, `<div class="compare-cols">${columns}</div>`);
}

export function renderComparison(players) {
    const legend = buildChartLegend(players.map((p, i) => ({ label: p.name, color: COMPARISON_COLORS[i] })));
    const blocks = [expectedBlock(players), recentAverageBlock(players), minutesBlock(players), againstBlock(players)]
        .filter(Boolean).join('');
    const stats = blocks ? `<div class="mp-stat-list">${blocks}</div>${legend}` : legend;
    return `
        <div class="player-sheet player-compare">
            <h3 class="player-sheet-name">${e(COPY.compareHeading)}</h3>
            ${stats}
            ${fixtureColumns(players)}
        </div>`;
}

// One entry point: one player gives the sheet, two give the compare.
export function renderPlayerSheet(players) {
    const list = Array.isArray(players) ? players : [];
    if (list.length === 0) return renderPlayerSheetMessage(COPY.loadFailed);
    if (list.length === 1) return renderSinglePlayer(list[0]);
    return renderComparison(list.slice(0, 2));
}
