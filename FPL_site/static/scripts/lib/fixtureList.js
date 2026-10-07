/***** fixtureList.js *****/
// Upcoming fixtures as a short list, one row per gameweek:
//   Gameweek 12 · Crystal Palace, away · [Tough]
// A list of full words fits a phone screen where a row of little chips with
// team abbreviations did not. The difficulty is written as a word inside a
// coloured pill, so the meaning never depends on colour alone.
import { escapeHtml } from './escapeHtml.js';
import { difficultyColor, difficultyTextColor } from '../visuals.js';

// FPL rates a fixture 1 (easiest) to 5 (hardest). We group that into three
// plain words that match the three colour bands the pill uses.
export function difficultyWord(difficulty) {
    const n = Number(difficulty);
    if (difficulty === null || difficulty === undefined || difficulty === 'None' || !Number.isFinite(n)) return '';
    if (n <= 2) return 'Kind';
    if (n <= 3) return 'Fair';
    return 'Tough';
}

function pill(difficulty) {
    const word = difficultyWord(difficulty);
    if (!word) return '';
    return `<span class="fixture-list-pill" style="background:${difficultyColor(difficulty)}; color:${difficultyTextColor(difficulty)};">${word}</span>`;
}

// options.compact makes the rows slightly smaller (used when stacking one
// list per player in the comparison view).
export function buildFixtureList(fixtures, options = {}) {
    if (!Array.isArray(fixtures) || fixtures.length === 0) return '';
    const rows = fixtures.map(f => {
        const week = `Gameweek ${escapeHtml(f.gameweek)}`;
        if (f.homeOrAway === 'Blank') {
            return `<li class="fixture-list-row fixture-list-blank"><span>${week}</span> · <span>No game</span></li>`;
        }
        // Prefer the full team name; fall back to whatever name we were given.
        const team = escapeHtml(f.teamFullName || f.teamName);
        const venue = f.homeOrAway === 'Home' ? 'home' : 'away';
        return `<li class="fixture-list-row"><span>${week}</span> · <span>${team}, ${venue}</span> · ${pill(f.difficulty)}</li>`;
    }).join('');
    return `<ul class="fixture-list${options.compact ? ' fixture-list-compact' : ''}">${rows}</ul>`;
}
