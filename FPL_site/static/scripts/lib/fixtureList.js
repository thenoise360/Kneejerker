/***** fixtureList.js *****/
// Upcoming fixtures as a short list, one row per gameweek:
//   Gameweek 12 · Crystal Palace, away · [Tough]
// A list of full words fits a phone screen where a row of little chips with
// team abbreviations did not. The difficulty is written as a word inside a
// coloured pill, so the meaning never depends on colour alone.
import { escapeHtml } from './escapeHtml.js';
import { difficultyColor, difficultyTextColor } from '../visuals.js';
import { numbersToggle } from './numbersToggle.js';

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

// What the player scored the last time they met this opponent, as a plain word.
// These lines match playerHistory.py on the server: 8 or more is a big return,
// 3 to 7 is steady, and 2 or less is quiet. History is background, so the
// wording is gentle and never tells anyone what to do.
const BIG_RETURN_FROM = 8;
const STEADY_RETURN_FROM = 3;

export function lastTimeTier(points) {
    const n = Number(points);
    if (n >= BIG_RETURN_FROM) return 'Big return last time';
    if (n >= STEADY_RETURN_FROM) return 'Steady return last time';
    return 'Quiet game last time';
}

// The small line under a row, or '' when there is nothing to say.
// f.lastTime comes from the server: { kind: 'played' | 'did_not_play' | 'no_meeting' | 'new_player' } or null.
export function lastTimeCaption(lastTime) {
    if (!lastTime) return '';
    if (lastTime.kind === 'played') {
        // 'club' is only set when the player has since changed club.
        const club = lastTime.club ? ` · Last season, for ${lastTime.club}` : '';
        return lastTimeTier(lastTime.points) + club;
    }
    if (lastTime.kind === 'did_not_play') return "Didn't play in this fixture last season";
    if (lastTime.kind === 'no_meeting') return "Didn't face them last season";
    return ''; // new players have no history to talk about
}

// The numbers behind a "played" caption, as a short line: "9 points · 90 minutes · won 3–1 at home".
// They are opt in: hidden until "Show the numbers" is on, then shown right under
// the caption of the row they belong to. '' for anything else.
export function lastTimeStats(lastTime) {
    if (!lastTime || lastTime.kind !== 'played') return '';
    const points = `${lastTime.points} ${Number(lastTime.points) === 1 ? 'point' : 'points'}`;
    const minutes = `${lastTime.minutes} ${Number(lastTime.minutes) === 1 ? 'minute' : 'minutes'}`;
    return `${points} · ${minutes} · ${lastTime.result} ${lastTime.is_home ? 'at home' : 'away'}`;
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
        const caption = lastTimeCaption(f.lastTime);
        const stats = lastTimeStats(f.lastTime);
        const statsHtml = stats ? `<span class="fixture-list-stats kj-num">${escapeHtml(stats)}</span>` : '';
        const captionHtml = caption ? ` <span class="fixture-list-caption">${escapeHtml(caption)}${statsHtml}</span>` : '';
        return `<li class="fixture-list-row"><span>${week}</span> · <span>${team}, ${venue}</span> · ${pill(f.difficulty)}${captionHtml}</li>`;
    }).join('');
    const list = `<ul class="fixture-list${options.compact ? ' fixture-list-compact' : ''}">${rows}</ul>`;
    // Only offer the switch when at least one row has numbers to reveal. The list and
    // the switch share one wrapper, so a flex container (Discovery's panel) sees a
    // single child and never lays them side by side.
    const hasStats = fixtures.some(f => f.homeOrAway !== 'Blank' && lastTimeStats(f.lastTime));
    if (!hasStats) return list;
    return `<div class="fixture-list-block kj-numbers">${list}${numbersToggle()}</div>`;
}
