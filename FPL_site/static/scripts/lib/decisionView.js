/***** decisionView.js *****/
// Turns the week's biggest decision into HTML. Pure: no DOM access.
import { escapeHtml } from './escapeHtml.js';
import { renderMessage } from './recapView.js';

// Each kind gets an icon AND a word, so meaning never depends on colour alone.
// aria-hidden hides the decorative icon from screen readers; they read the word.
const KIND_LABELS = {
    availability: { icon: '🩹', label: 'Player availability' },
    captain: { icon: '⭐', label: 'Captain choice' },
};

export function renderDecision(payload) {
    if (!payload.decision) return renderMessage(payload.message);
    const d = payload.decision;
    const kind = KIND_LABELS[d.kind] || { icon: '•', label: 'Decision' };
    const basedOn = payload.based_on === 'your_team' && payload.squad_gameweek
        ? `<p class="sub">Based on your team from gameweek ${escapeHtml(payload.squad_gameweek)}.</p>`
        : '';
    const details = (d.details || []).map((line) => `<li>${escapeHtml(line)}</li>`).join('');
    // recap-verdict: the global ".card h3" style is small, uppercase and too
    // pale to read well, so the verdict reuses the readable heading class.
    return `
        <div class="card" id="week-decision">
            <div class="eyebrow-sm"><span aria-hidden="true">${kind.icon}</span> ${kind.label}</div>
            <h3 class="recap-verdict">${escapeHtml(d.title)}</h3>
            <p>${escapeHtml(d.reason)}</p>
            ${basedOn}
            <details class="recap-details">
                <summary>See the numbers</summary>
                <ul class="recap-standouts">${details}</ul>
            </details>
        </div>`;
}

// The loading placeholder, shared by the template's first paint and by reloads
// in weekV2.js. aria-busy tells screen readers the content is still arriving.
export function renderDecisionSkeleton() {
    return `
        <div class="card" aria-busy="true" aria-label="Loading this week's decision">
            <div class="skeleton" style="height:18px; width:55%; margin-bottom:10px;"></div>
            <div class="skeleton" style="height:14px; width:85%;"></div>
        </div>`;
}
