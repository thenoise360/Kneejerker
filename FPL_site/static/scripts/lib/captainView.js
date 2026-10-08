/***** captainView.js *****/
// The read-only "Captain and vice" view opened from the hub's captaincy row.
// Pure: takes decisions.captaincy and the ids ticked for compare, returns HTML.
import { escapeHtml } from './escapeHtml.js';
import { renderOptionRow } from './optionRow.js';
import { COPY, viceLine, compareBarText, compareButtonText } from './playerInfoCopy.js';

const e = escapeHtml;

// Every option the view can show, in one list, so names can be found by id.
export function allOptions(captaincy) {
    const c = captaincy || {};
    return [c.suggested, c.vice, ...(c.shortlist || []), ...(c.others || [])].filter(Boolean);
}

export function optionById(captaincy, id) {
    return allOptions(captaincy).find((o) => String(o.id) === String(id)) || null;
}

function compareBar(captaincy, selectedIds) {
    const ids = selectedIds.slice(0, 2);
    if (ids.length === 2) {
        const a = optionById(captaincy, ids[0]);
        const b = optionById(captaincy, ids[1]);
        if (a && b) {
            return `<div class="compare-bar"><button type="button" class="btn-pill" data-action="open-compare">${e(compareButtonText(a.name, b.name))}</button></div>`;
        }
    }
    return `<div class="compare-bar"><p class="sub">${e(compareBarText(ids.length))}</p></div>`;
}

function group(title, options, selectedIds) {
    if (!options || options.length === 0) return '';
    const rows = options.map((o) => renderOptionRow(o, { selected: selectedIds.includes(String(o.id)) })).join('');
    return `<h4 class="sheet-section-title">${e(title)}</h4><ul class="option-list">${rows}</ul>`;
}

export function renderCaptainView(captaincy, selectedIds = []) {
    const selected = selectedIds.map(String);
    const c = captaincy || {};
    const head = `
        <div class="sheet-topbar"><button type="button" class="sheet-close" data-action="close">${COPY.close}</button></div>
        <h3 class="player-sheet-name">${e(COPY.captainTitle)}</h3>
        <p class="sub">${e(COPY.readOnlyNote)}</p>`;
    if (!c.suggested) {
        return `<div class="captain-view">${head}<p>${e(COPY.noLean)}</p></div>`;
    }
    const leanRows = [renderOptionRow(c.suggested, { selected: selected.includes(String(c.suggested.id)), badge: COPY.captainBadge })];
    if (c.vice) {
        leanRows.push(renderOptionRow(c.vice, {
            selected: selected.includes(String(c.vice.id)), badge: COPY.viceBadge, note: viceLine(c.suggested.name),
        }));
    }
    // The lean is shown above, so don't list it again as an alternative.
    const leanIds = new Set([c.suggested, c.vice].filter(Boolean).map((o) => String(o.id)));
    const alternatives = (c.shortlist || []).filter((o) => !leanIds.has(String(o.id)));
    return `
        <div class="captain-view">
            ${head}
            <h4 class="sheet-section-title">${e(COPY.leanHeading)}</h4>
            <ul class="option-list">${leanRows.join('')}</ul>
            ${group(COPY.alternativesHeading, alternatives, selected)}
            ${group(COPY.restHeading, c.others, selected)}
            ${compareBar(c, selected)}
        </div>`;
}
