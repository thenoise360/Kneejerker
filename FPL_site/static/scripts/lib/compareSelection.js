/***** compareSelection.js *****/
// Which two players are ticked for the side-by-side compare, and the address
// the player details are fetched from. Pure, so Node can test them.

// Ticking a player that is already ticked un-ticks it. Ticking a third drops
// the one ticked longest ago, so there are never more than two.
export function toggleSelection(selected, id) {
    const key = String(id);
    if (selected.includes(key)) return selected.filter((s) => s !== key);
    return [...selected, key].slice(-2);
}

// The lean (our suggested captain) starts ticked, so one tap compares it with another player.
export function initialSelection(captaincy) {
    return captaincy && captaincy.suggested ? [String(captaincy.suggested.id)] : [];
}

export function playerContextUrl(ids, gameweek) {
    const query = new URLSearchParams({ ids: ids.map(String).join(',') });
    if (gameweek !== null && gameweek !== undefined && gameweek !== '') query.set('gameweek', String(gameweek));
    return `/api/week/player-context?${query}`;
}

// Same two players in either order share one cached answer.
export function contextKey(ids) {
    return ids.map(String).join(',');
}
