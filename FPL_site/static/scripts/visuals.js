/**
 * visuals.js - Shared rendering logic for data visuals like sparklines and fixture chips.
 */

export function difficultyColor(diff) {
    if (diff === 'None' || diff === null || diff === undefined) return '#c9c4cc';
    if (diff <= 2) return '#01FC7A';
    if (diff <= 3) return '#e5e5e5';
    // Darkened from the original #FF1751 - that shade only hit ~3.3:1 contrast
    // with dark text (fails WCAG AA's 4.5:1 for normal-size text either way).
    if (diff <= 4) return '#D4145A';
    return '#80072D';
}

/**
 * Text colour to pair with difficultyColor()'s background so fixture-chip
 * text stays WCAG AA compliant (>=4.5:1) at every difficulty level - the two
 * darkest bands (4 and 5) need white text, not the default charcoal.
 */
export function difficultyTextColor(diff) {
    if (diff !== 'None' && diff !== null && diff !== undefined && diff >= 4) return '#ffffff';
    return '#333333';
}

/**
 * Low-level zero-anchored line/area chart primitive shared by the single-series
 * sparkline/ownership charts and the Discovery comparison panel's multi-player
 * overlaid charts (04.14 follow-up).
 *
 * series: [{ color, values }] - 1-3 solid lines, one per player.
 * avgSeries: optional array of the same length, drawn as one dashed grey line.
 * formatValue: number -> axis label string (raw for points, "x.x%" for ownership).
 * area: fill each series under its line (used for the ownership chart).
 */
export function buildMultiLineChart({ series, avgSeries, w, h, padTop, padBottom, padLeft, padRight, formatValue, area = false, areaOpacity = 0.18 }) {
    const len = series[0] ? series[0].values.length : (avgSeries ? avgSeries.length : 0);
    if (len === 0) return '<p class="sub">No data</p>';

    const allValues = series.flatMap(s => s.values).concat(avgSeries || []);
    const max = Math.max(...allValues, area ? 0.1 : 1);
    const innerW = w - padLeft - padRight, innerH = h - padTop - padBottom;
    const x = i => padLeft + (len > 1 ? i * (innerW / (len - 1)) : innerW / 2);
    const y = v => (h - padBottom) - (v / max) * innerH;

    let parts = [
        `<line x1="${padLeft}" y1="${padTop}" x2="${padLeft}" y2="${h - padBottom}" stroke="#e5e5e5" stroke-width="1"/>`,
        `<text x="0" y="${h - padBottom + 3}" font-size="9" fill="#999">${formatValue(0)}</text>`,
        `<text x="0" y="${padTop + 8}" font-size="9" fill="#999">${formatValue(max)}</text>`
    ];

    if (avgSeries && avgSeries.length === len) {
        const avgPts = avgSeries.map((v, i) => `${x(i)},${y(v)}`).join(' ');
        parts.push(`<polyline points="${avgPts}" fill="none" stroke="#c9c4cc" stroke-width="1.5" stroke-dasharray="3,3"/>`);
    }

    series.forEach(s => {
        const pts = s.values.map((v, i) => `${x(i)},${y(v)}`).join(' ');
        if (area) {
            const areaPts = `${x(0)},${h - padBottom} ${pts} ${x(s.values.length - 1)},${h - padBottom}`;
            parts.push(`<polygon points="${areaPts}" fill="${s.color}" opacity="${areaOpacity}"/>`);
        }
        parts.push(`<polyline points="${pts}" fill="none" stroke="${s.color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>`);

        // Optional end-of-line tag (e.g. player initials) so a line's identity
        // is readable directly off the chart, not just via the legend below.
        if (s.label) {
            const lastX = x(s.values.length - 1);
            const lastY = y(s.values[s.values.length - 1]);
            parts.push(`<circle cx="${lastX}" cy="${lastY}" r="9" fill="${s.color}" stroke="#fff" stroke-width="1.5"/>`);
            parts.push(`<text x="${lastX}" y="${lastY + 3}" font-size="8" font-weight="700" fill="#fff" text-anchor="middle">${s.label}</text>`);
        }
    });

    return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" style="max-width:100%; overflow:visible;">${parts.join('')}</svg>`;
}

/**
 * Small colour-key legend for the comparison charts: one dot + label per
 * player, plus an optional dashed-line entry for the average series.
 * entries: [{ label, color, dashed? }]
 */
export function buildChartLegend(entries) {
    return `<div class="chart-legend">${entries.map(e => `
        <div class="chart-legend-item">
            <span class="chart-legend-dot${e.dashed ? ' dashed' : ''}"${e.dashed ? '' : ` style="background:${e.color};"`}></span>
            <span>${e.label}</span>
        </div>
    `).join('')}</div>`;
}

export function buildSparkline(last5, avg5) {
    if (!last5 || last5.length === 0) return '<p class="sub">No form data</p>';
    return buildMultiLineChart({
        series: [{ color: 'var(--teal)', values: last5 }],
        avgSeries: avg5,
        w: 260, h: 60, padTop: 6, padBottom: 14, padLeft: 22, padRight: 4,
        formatValue: v => `${v}`
    });
}

export function buildFixtureChips(fixtures) {
    if (!fixtures || fixtures.length === 0) return '';
    
    return fixtures.map(f => {
        if (f.homeOrAway === 'Blank') {
            return `<div class="fixture-chip fixture-chip-blank" title="No fixture in gameweek ${f.gameweek}">
                <span>GW${f.gameweek}</span><span>No fixture</span>
            </div>`;
        }
        return `<div class="fixture-chip" style="background:${difficultyColor(f.difficulty)}; color:${difficultyTextColor(f.difficulty)};" title="Gameweek ${f.gameweek}, difficulty ${f.difficulty} of 5">
            <span>${f.teamName}</span><span>${f.homeOrAway === 'Home' ? '(H)' : '(A)'}</span>
        </div>`;
    }).join('');
}

export function describeFixtureRun(fixtures) {
    const real = fixtures.filter(f => f.homeOrAway !== 'Blank');
    if (real.length < 2) {
        return "Not enough confirmed fixtures yet to call a trend.";
    }
    const first = real[0].difficulty;
    const last = real[real.length - 1].difficulty;
    if (last < first) return "Fixtures are easing up over this run.";
    if (last > first) return "Fixtures are toughening up over this run.";
    return "Fixtures are holding steady in difficulty over this run.";
}

/**
 * Builds a zero-anchored area chart for ownership trend.
 * @param {Array<number>} history - Array of ownership percentages.
 */
export function buildOwnershipArea(history, avgHistory) {
    if (!history || history.length < 2) return '<p class="sub">No trend data</p>';

    const rising = history[history.length - 1] >= history[0];
    const color = rising ? 'var(--teal)' : 'var(--pink)';

    return buildMultiLineChart({
        series: [{ color, values: history }],
        avgSeries: avgHistory,
        w: 260, h: 70, padTop: 6, padBottom: 16, padLeft: 24, padRight: 4,
        formatValue: v => `${v.toFixed(1)}%`,
        area: true
    });
}

// Season numbers grid (02.5): backend metric title -> plain-language label.
// "Points per GBP1m" is spelled out in full per the no-acronyms rule, even
// though the backend's own metric title still uses the "£1m" shorthand.
// Shared between the player profile bottom sheet (radar.js) and the
// Discovery comparison panel's Season Numbers metric.
export const SEASON_STATS = [
    { metricTitle: 'Points', label: 'Points' },
    { metricTitle: 'Goals', label: 'Goals' },
    { metricTitle: 'Assists', label: 'Assists' },
    { metricTitle: 'Clean sheets', label: 'Clean sheets', positionsOnly: ['Goalkeeper', 'Defender'] },
    { metricTitle: 'Bonus points', label: 'Bonus points' },
    { metricTitle: 'Points per £1m', label: 'Points per GBP1m' }
];

export function formatStatValue(v) {
    if (v === null || v === undefined) return '—';
    const num = Number(v);
    if (Number.isNaN(num)) return v;
    return Number.isInteger(num) ? num.toString() : num.toFixed(1);
}

/**
 * One labelled bar-with-marker row: a solid bar for the player's own value,
 * a marker for whatever it's being compared against. Shared between the
 * player profile bottom sheet's Summary card (radar.js) and the Discovery
 * comparison panel's single-player Summary metric.
 */
export function summaryRow(label, valueText, compareText, pct, comparePct) {
    const clampedPct = Math.max(0, Math.min(100, pct));
    const clampedComparePct = Math.max(0, Math.min(100, comparePct));
    return `<div class="summary-row">
        <div class="summary-row-head">
            <span class="summary-row-label">${label}</span>
            <span class="summary-row-value">${valueText}</span>
        </div>
        <div class="bar-track summary-bar-track">
            <div class="bar-fill" style="width:${clampedPct}%;"></div>
            <div class="bar-marker" style="left:${clampedComparePct}%;"></div>
        </div>
        <div class="summary-row-compare">${compareText}</div>
    </div>`;
}
