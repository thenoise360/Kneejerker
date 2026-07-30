/***** club.js *****/
import { trackFixtureOutlookTap } from './analytics.js';
import { createRangeBar } from './rangeBar.js';

document.addEventListener('DOMContentLoaded', () => {
    initializeClubPage();
});

function initializeClubPage() {
    const content = document.getElementById('club-content');
    if (!content) return;

    const teamId = content.dataset.teamId;
    if (!teamId) return;

    fetchOutlook(teamId);
}

async function fetchOutlook(teamId) {
    const titleEl = document.getElementById('club-title');
    const listEl = document.getElementById('club-fixture-list');

    try {
        const res = await fetch(`/api/club/${teamId}/fixture-outlook`);
        if (!res.ok) throw new Error(`status ${res.status}`);
        const data = await res.json();

        if (titleEl) titleEl.textContent = data.team_name;
        renderFixtureList(listEl, teamId, data, data.fixtures || []);
    } catch (err) {
        console.error('Failed to load fixture outlook', err);
        if (titleEl) titleEl.textContent = 'Fixture outlook';
        if (listEl) listEl.innerHTML = '<p class="sub">Couldn\'t load fixtures right now.</p>';
    }
}

function renderFixtureList(container, teamId, teamData, fixtures) {
    if (!container) return;

    if (!fixtures.length) {
        container.innerHTML = '<p class="sub">No upcoming fixtures to show yet.</p>';
        return;
    }

    container.innerHTML = '';
    fixtures.forEach(f => {
        const row = document.createElement('div');
        row.className = 'card outlook-row';
        row.dataset.gameweek = f.gameweek;
        row.dataset.opponent = f.opponent_name;
        
        row.innerHTML = `
            <div class="outlook-summary">
                <span class="outlook-phrase">${outlookPhrase(f)}</span>
                <span class="outlook-gw">Gameweek ${f.gameweek}</span>
            </div>
            <div class="outlook-detail"></div>
        `;

        row.addEventListener('click', (e) => {
            const isExpanding = !row.classList.contains('expanded');
            
            // Close other expanded rows (accordion style)
            container.querySelectorAll('.outlook-row.expanded').forEach(r => {
                if (r !== row) r.classList.remove('expanded');
            });

            if (isExpanding) {
                trackFixtureOutlookTap(teamId, f.opponent_name, f.gameweek);
                renderDetailView(row.querySelector('.outlook-detail'), teamData.team_name, f);
                row.classList.add('expanded');
            } else {
                row.classList.remove('expanded');
            }
        });

        container.appendChild(row);
    });
}

function renderDetailView(container, teamName, f) {
    // Only render if empty to avoid re-calculating or duplicate content
    if (container.children.length > 0) return;

    const ownBar = createRangeBar(f.own, { label: teamName, color: 'var(--plum)' });
    const oppBar = createRangeBar(f.opponent, { label: f.opponent_name, color: 'var(--teal)' });
    
    const rationale = document.createElement('div');
    rationale.className = 'outlook-rationale';
    rationale.textContent = generateRationale(f);

    container.appendChild(ownBar);
    container.appendChild(oppBar);
    container.appendChild(rationale);
}

function generateRationale(f) {
    const own = f.own;
    const opp = f.opponent;
    
    // Evidence-based rationale using Dixon-Coles ratings (log-scale)
    const attackText = own.attack > 0.15 ? "Strong attacking form" :
                      own.attack < -0.15 ? "Struggling for goals" : "Steady attacking form";
                      
    const defenseText = opp.defence > 0.15 ? "a vulnerable defence" :
                       opp.defence < -0.15 ? "a disciplined backline" : "a standard defensive setup";
                       
    const location = f.is_home ? "at home" : "away from home";
    
    return `${attackText} meets ${defenseText} ${location}. Based on these factors, the model predicts a range of expected goals as shown above.`;
}

/* ================================================================
   TIERING + PHRASE BANK - deterministic, no language model calls.
   The engine (Ticket 01) only ever returns raw mean/low/high goal
   figures; the plain-language framing lives entirely here, at the
   presentation layer, per that ticket's explicit split.
   ================================================================ */
function outlookTier(own, opponent) {
    const diff = own.mean - opponent.mean;
    if (diff >= 1.0) return 'comfortable';
    if (diff >= 0.35) return 'favoured';
    if (diff > -0.35) return 'even';
    if (diff > -1.0) return 'underdog';
    return 'tough';
}

const PHRASES = {
    outlook: {
        comfortable: (versus) => `Should be comfortable ${versus}.`,
        favoured:    (versus) => `Should have the edge ${versus}.`,
        even:        (versus) => `Could go either way ${versus}.`,
        underdog:    (versus) => `A tough ask ${versus}.`,
        tough:       (versus) => `Could be a rough one ${versus}.`
    }
};

function outlookPhrase(fixture) {
    const tier = outlookTier(fixture.own, fixture.opponent);
    const versus = fixture.is_home ? `at home to ${fixture.opponent_name}` : `away to ${fixture.opponent_name}`;
    return PHRASES.outlook[tier](versus);
}
