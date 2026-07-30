/***** clubs.js *****/

document.addEventListener('DOMContentLoaded', () => {
    fetchClubs();
});

async function fetchClubs() {
    const listEl = document.getElementById('clubs-list');
    if (!listEl) return;

    try {
        const res = await fetch('/api/clubs');
        if (!res.ok) throw new Error(`status ${res.status}`);
        const teams = await res.json();
        renderClubsList(listEl, teams);
    } catch (err) {
        console.error('Failed to load clubs list', err);
        listEl.innerHTML = '<p class="sub">Couldn\'t load clubs right now.</p>';
    }
}

function renderClubsList(container, teams) {
    if (!teams || !teams.length) {
        container.innerHTML = '<p class="sub">No clubs to show yet.</p>';
        return;
    }

    container.innerHTML = teams.map(t => `
        <a class="fixture-row-item outlook-row" href="/club/${t.id}">
            <span class="outlook-phrase">${t.name}</span>
            <span class="outlook-gw">${t.short_name}</span>
        </a>
    `).join('');
}
