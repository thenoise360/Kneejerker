/***** statBlock.js *****/
// The Discovery comparison style, shared with the This Week decision views:
// a bar with one coloured dot per player, plus a colour-key legend. Pure
// string builders, so Node can test them. Moved out of discovery.js unchanged
// apart from escaping player names.
import { escapeHtml } from './escapeHtml.js';

// One colour per slot, applied in selection order.
export const COMPARISON_COLORS = ['var(--teal)', 'var(--pink)', 'var(--plum-tint)'];

/**
 * Small colour-key legend: one dot + label per player, plus an optional
 * dashed-line entry for an average series.
 * entries: [{ label, color, dashed? }]
 */
export function buildChartLegend(entries) {
    return `<div class="chart-legend">${entries.map(e => `
        <div class="chart-legend-item">
            <span class="chart-legend-dot${e.dashed ? ' dashed' : ''}"${e.dashed ? '' : ` style="background:${e.color};"`}></span>
            <span>${escapeHtml(e.label)}</span>
        </div>
    `).join('')}</div>`;
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
export function buildStatBlock(label, players, valueFn, options = {}) {
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
            ? `<div class="mp-stat-avg-tick" style="left:${pctOf(r.avgValue)}%; border-color:${COMPARISON_COLORS[i]};" title="${escapeHtml(players[i].name)}'s average: ${r.avgValue}"></div>`
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
            <div class="mp-stat-dot" style="left:${pct}%; background:${COMPARISON_COLORS[i]};" title="${escapeHtml(players[i].name)}: ${r.display}"></div>`;
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
