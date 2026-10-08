/***** optionRow.js *****/
// One compact row per captain (or, later, transfer) option. Pure: returns an
// HTML string. The page's click handling reads the data-action attributes.
import { escapeHtml } from './escapeHtml.js';
import { COPY, priceText, fixtureText, predictedPointsText, formStripLabel } from './playerInfoCopy.js';

// Bar heights are a share of the best game in the strip. Zero or negative
// scores still get a thin stub so the five games always show as five bars.
export function formBarPercents(points) {
    const best = Math.max(1, ...points.map((p) => (p > 0 ? p : 0)));
    return points.map((p) => (p > 0 ? Math.max(8, Math.round((p / best) * 100)) : 4));
}

export function renderFormStrip(points) {
    const list = Array.isArray(points) ? points : [];
    if (list.length === 0) return '<span class="form-strip form-strip--empty" aria-hidden="true"></span>';
    const percents = formBarPercents(list);
    const bars = list
        .map((p, i) => `<span class="form-bar" style="height:${percents[i]}%" title="${escapeHtml(p)}"></span>`)
        .join('');
    return `<span class="form-strip" role="img" aria-label="${escapeHtml(formStripLabel(list))}">${bars}</span>`;
}

// options.badge: 'Captain' / 'Vice' / undefined. options.note: a small line under the name.
export function renderOptionRow(option, { selected = false, badge = '', note = '' } = {}) {
    const meta = [option.team_short, priceText(option.price)].filter(Boolean).map(escapeHtml).join(' · ');
    const badgeHtml = badge ? `<span class="option-badge">${escapeHtml(badge)}</span>` : '';
    const noteHtml = note ? `<div class="option-note">${escapeHtml(note)}</div>` : '';
    return `
        <li class="option-row${selected ? ' option-row--selected' : ''}" data-id="${escapeHtml(option.id)}">
            <div class="option-main">
                <button type="button" class="option-name" data-action="open-player" data-id="${escapeHtml(option.id)}">${escapeHtml(option.name)}</button>${badgeHtml}
                <div class="option-meta">${meta}</div>
                ${noteHtml}
                <div class="option-fixture">${escapeHtml(fixtureText(option.this_week))}</div>
                <div class="option-points">${escapeHtml(predictedPointsText(option.predicted_points))}</div>
            </div>
            <div class="option-side">
                ${renderFormStrip(option.recent_points)}
                <button type="button" class="option-compare" data-action="toggle-compare" data-id="${escapeHtml(option.id)}" aria-pressed="${selected ? 'true' : 'false'}">${selected ? COPY.comparing : COPY.compare}</button>
            </div>
        </li>`;
}
