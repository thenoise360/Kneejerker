/***** hubView.js *****/
// Turns the hub's JSON into HTML. Pure: it returns a string and never touches
// the page, so Node can test it. The markup deliberately mirrors
// templates/partials/week_hub.html: the server draws it first (so the page
// works without JavaScript), then this redraws it with friendlier words.
import { escapeHtml } from './escapeHtml.js';
import { headlineSentence, rowSentence } from './hubCopy.js';

// The order the four decisions appear in, everywhere.
export const DECISION_ORDER = ['injuries', 'transfers', 'chips', 'captaincy'];

const TITLES = { injuries: 'Injuries', transfers: 'Transfers', chips: 'Chips', captaincy: 'Captain and vice' };

// Each state gets an icon AND words. aria-hidden stops screen readers reading
// the icon, because the words already say the same thing.
const BADGES = {
    needs_look: ['!', 'Needs a look'],
    nothing_to_do: ['✓', 'Nothing to do this week'],
    decided: ['✓', 'Decided'],
    needs_team: ['+', 'Add your team'],
};

function badge(state) {
    const [icon, label] = BADGES[state] || ['•', 'Coming soon'];
    return `<span class="hub-badge hub-badge--${escapeHtml(state)}"><span aria-hidden="true">${icon}</span> ${label}</span>`;
}

// The captain row opens the options view when there is a lean to look into.
// The page script listens for clicks on rows marked data-opens.
function row(key, decision) {
    const opens = key === 'captaincy' && decision.suggested;
    const attrs = opens ? ' data-opens="captain" role="button" tabindex="0"' : '';
    const more = opens ? '<span class="hub-row-more">See the options</span>' : '';
    return `
        <li class="card hub-row${opens ? ' hub-row--tappable' : ''}" data-key="${key}" data-state="${escapeHtml(decision.state)}"${attrs}>
            <div class="hub-row-head"><span class="hub-row-title">${TITLES[key]}</span>${badge(decision.state)}</div>
            <p class="sub">${escapeHtml(rowSentence(key, decision))}</p>${more}
        </li>`;
}

export function renderHubBody(data) {
    if (!data || data.status !== 'ready') {
        return `
            <div class="card">
                <h3 class="recap-verdict">We couldn't load this week's decisions</h3>
                <p>Nothing is wrong on your side. Try again in a moment.</p>
            </div>`;
    }
    // Decisions that aren't built yet are left out rather than shown half-done.
    const rows = DECISION_ORDER
        .filter((key) => data.decisions[key] && data.decisions[key].state !== 'not_ready')
        .map((key) => row(key, data.decisions[key]))
        .join('');
    // escapeHtml runs on the finished sentence, because player names come from outside data.
    return `
        <div class="card hub-headline">
            <div class="eyebrow-sm">The big one this week</div>
            <h3 class="recap-verdict">${escapeHtml(headlineSentence(data.headline))}</h3>
        </div>
        <h3>This week's decisions</h3>
        <ul class="hub-rows">${rows}</ul>
        <p class="sub">More decisions are on the way. We'll add them here as they're ready.</p>`;
}
