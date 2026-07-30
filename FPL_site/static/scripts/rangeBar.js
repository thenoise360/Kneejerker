/***** rangeBar.js (Ticket 04) *****/

/**
 * Renders a horizontal range bar showing expected goals.
 *
 * @param {Object} data - { low, high, mean }
 * @param {Object} options - { min, max, color, label }
 * @returns {HTMLElement}
 */
export function createRangeBar(data, { min = 0, max = 5, color = 'var(--plum)', label = '' } = {}) {
    const toPct = (v) => Math.max(0, Math.min(100, ((v - min) / (max - min)) * 100));

    const l = toPct(data.low);
    const h = toPct(data.high);
    const m = toPct(data.mean);

    const el = document.createElement('div');
    el.className = 'range-bar-container';
    el.innerHTML = `
        <div class="range-bar-info">
            <span class="range-bar-team">${label}</span>
            <span class="range-bar-val">${data.mean.toFixed(1)} <span class="range-bar-bounds">(${data.low.toFixed(1)}–${data.high.toFixed(1)})</span></span>
        </div>
        <div class="range-bar-track">
            <div class="range-bar-zone" style="left:${l}%; width:${Math.max(2, h - l)}%; background:${color}"></div>
            <div class="range-bar-marker" style="left:${m}%"></div>
        </div>
    `;
    return el;
}
