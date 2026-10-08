/***** playerInfoCopy.js *****/
// Every sentence the player rows, player sheet and compare view say lives here,
// so the tone stays in one place (same idea as hubCopy.js). Pure functions:
// numbers and keys come from the server, words come from here. No acronyms.

export const COPY = {
    captainTitle: 'Captain and vice',
    readOnlyNote: 'Make this change in the official app before the deadline.',
    noLean: "Captain numbers aren't in yet. Check back soon.",
    leanHeading: 'Our lean',
    alternativesHeading: 'Top alternatives',
    restHeading: 'Rest of your squad',
    captainBadge: 'Captain',
    viceBadge: 'Vice',
    compare: 'Compare',
    comparing: 'Comparing',
    back: 'Back',
    close: 'Close',
    last5Heading: 'Last 5 games',
    momentumHeading: 'Momentum',
    nextHeading: 'Next 3 fixtures',
    noRecentGames: 'No games played in the last five gameweeks yet.',
    noMomentum: "Momentum isn't available for this player yet.",
    noNextFixtures: 'No fixtures to show yet.',
    noMatchThisWeek: 'No match this week.',
    loadFailed: "We couldn't load the player details just now. Try again in a moment.",
    expectedBlockLabel: 'Expected points (official game)',
    noPrediction: 'No expected points yet',
    compareHeading: 'Side by side',
    nextFixturesCompareHeading: 'Next fixtures',
};

export function priceText(tenths) {
    if (tenths === null || tenths === undefined || Number.isNaN(Number(tenths))) return '';
    return `£${(Number(tenths) / 10).toFixed(1)}m`;
}

export function venueText(isHome) {
    return isHome ? 'home' : 'away';
}

const DIFFICULTY_WORDS = { easier: 'easier', average: 'average', tougher: 'tougher' };

export function difficultyWord(difficulty) {
    return DIFFICULTY_WORDS[difficulty] || '';
}

// "vs BOU (home) · easier". The difficulty part is left off when we don't know it.
export function fixtureText(thisWeek) {
    if (!thisWeek) return COPY.noMatchThisWeek;
    const base = `vs ${thisWeek.opponent_short} (${venueText(thisWeek.is_home)})`;
    const word = difficultyWord(thisWeek.difficulty);
    return word ? `${base} · ${word}` : base;
}

export function expectedPointsText(value) {
    if (value === null || value === undefined) return COPY.noPrediction;
    return `The official game expects ${Number(value).toFixed(1)} points`;
}

export function pointsWord(n) {
    return n === 1 ? '1 point' : `${n} points`;
}

export function formStripLabel(points) {
    if (!points || points.length === 0) return 'No recent games';
    return `Points in the last ${points.length} games, oldest first: ${points.join(', ')}`;
}

export function viceLine(captainName) {
    return `Steps in if ${captainName} doesn't play`;
}

export function noGamesAgainst(opponent) {
    return `No games against ${opponent} in the last two seasons.`;
}

export function compareBarText(selectedCount) {
    if (selectedCount === 0) return 'Tap Compare on two players to see them side by side.';
    if (selectedCount === 1) return 'Pick one more player to compare.';
    return '';
}

export function compareButtonText(nameA, nameB) {
    return `Compare ${nameA} and ${nameB}`;
}

export function gameLine(game) {
    const parts = [`${game.minutes} minutes`];
    if (game.goals) parts.push(game.goals === 1 ? '1 goal' : `${game.goals} goals`);
    if (game.assists) parts.push(game.assists === 1 ? '1 assist' : `${game.assists} assists`);
    return parts.join(', ');
}

export function positionAverageText(value) {
    if (value === null || value === undefined) return '';
    return `Average ${Number(value).toFixed(1)} for the position`;
}
