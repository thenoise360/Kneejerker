# Decision screens: supporting player information — Design

Date: 2026-10-08. Branch: `this-week-player-info` (from `this-week-hub-r1`).
Approved in chat by the user 2026-10-08 ("reuse the comparison style of our discovery page").

## Why

When the manager opens the Captain and vice choice (and later the Transfers choice) they need the
evidence behind each option: fixture context, predicted points, recent form, momentum, and past
games against this week's opponent, plus a side-by-side compare of two options.

## Scope

In: captain lean re-ranked by predicted points; per-option summary facts in the hub JSON; a new
player-context route; a read-only "Captain and vice" detail view opened from the hub's captaincy
row, with a player sheet and a two-player compare in the Discovery comparison style; reusable
row/sheet/compare modules that the Release 4 transfers screen will reuse.

Out (unchanged roadmap work): saving a captain/vice choice (Release 2 plan storage, `PUT
/api/week/plan`), the transfers screen itself (Release 4), predicted points beyond this gameweek
(the model only stores one gameweek).

## Global rules

- Every number traces to a backend function; JSON carries facts and keys, never prose.
- All sentences live in JavaScript phrase-bank modules (`hubCopy.js` pattern). No acronyms:
  "expected points", "Captain", "Vice", "Make captain"/"Make vice" — never xP, C, VC, EO.
- Mobile first, 375–430px. No horizontal scroll.
- Never fit models in a request: read the official game's stored expected points
  (`bootstrapstatic_elements.ep_next`, latest snapshot, through `connect_db()`), stored match predictions, `elementsummary_history`.
- Entities across seasons are matched by `code` (player and team), never by `id`.
- Tests never touch MySQL or the live API; monkeypatch fetchers. Add the new route to
  `tests/test_regression_routes.py`.

## 1. Captain lean ranks by expected points

`hubRules._ranked_options` sorts by the official game's expected points for the next gameweek
(`bootstrapstatic_elements.ep_next`, each player's row from the latest snapshot of the season, read by
`playerContext.fetch_expected_points`) instead of `involvement_predictions`.
Why not `player_predictions`: its `predicted_performance` is a 5-gameweek aggregate, not points for one
gameweek, so it must not be ranked or shown as points. Our own model will replace this source later,
behind the same fetcher. Same filters as today (has a match, not
a worry). Ties break on name. A player with no stored value is ranked after everyone with one
(not dropped). The hub row and headline follow automatically. `expected_involvement` is replaced
by `expected_points` in option objects; update every consumer (Jinja macro, `hubCopy.js`, tests).

## 2. Option summary (in `/api/week/this-week` → `decisions.captaincy`)

`shortlist` keeps its meaning (ranked fit starters with a match; guest: top three overall). New
`others`: the rest of the squad (bench and starters not in the shortlist), same object shape, so the
view can show "Rest of your squad". Guests get `others: []`.

Option object (both lists):

```json
{
  "id": 351, "name": "Haaland", "team_short": "MCI", "position": "Forward",
  "price": 145,                      // tenths of a million
  "expected_points": 7.5,            // null if not stored
  "this_week": {"opponent_short": "BOU", "is_home": true, "difficulty": "easier"},  // null if no match
  "recent_points": [2, 13, 6, 2, 9]  // last up to 5 finished gameweeks, oldest first
}
```

`difficulty` is `"easier" | "average" | "tougher" | null`, computed by one pure function shared
with section 3: same rule as `playerMomentum.fixtures_signal` (attackers: own expected goals vs the
team's baseline scored; defenders and goalkeepers: opponent expected goals vs baseline conceded;
±20% boundary, `FIXTURE_CHANGE_FROM`). Reuse, don't copy, that logic.

## 3. `GET /api/week/player-context?ids=1,2[&gameweek=N]`

1 or 2 ids, else 400. Unknown ids are omitted. DB down → 200 `{"status": "unavailable"}`, never 500.

```json
{
  "status": "ready", "gameweek": 6,
  "players": [{
    "id": 351, "name": "Haaland", "team_short": "MCI", "position": "Forward", "price": 145,
    "expected_points": 7.5,
    "position_average_expected_points": 3.1,
    "recent_games": [{"gameweek": 1, "opponent_short": "WOL", "is_home": false,
                      "minutes": 90, "goals": 2, "assists": 0, "points": 13}],   // up to 5, oldest first
    "momentum": {"label": "Rising", "signals": [...]},   // playerMomentum.player_momentum output, or null
    "next_fixtures": [{"gameweek": 6, "opponent_short": "BOU", "is_home": true, "difficulty": "easier"}],  // up to 3
    "vs_opponent": {"opponent_short": "BOU",
                    "games": [{"season": 2025, "gameweek": 12, "is_home": false, "minutes": 90, "points": 8}]}
  }]
}
```

`vs_opponent` covers this season and last season (`elementsummary_history.year_start`), matching the
player by `code` and the opponent by team `code` per season. No match this week → `vs_opponent: null`.
No past meetings → `games: []`.

Backend layout: new `FPL_site/playerContext.py` — thin fetchers (cursor in, rows out) plus pure
functions (`fixture_difficulty`, `recent_games`, `games_against`, `build_player_context`). Route in
`views.py` stays thin. Behaviour in `features/this_week/player_context.feature`.

## 4. Front end

- **Reuse Discovery's comparison style.** Move `buildStatBlock` and `buildChartLegend` (and
  `COMPARISON_COLORS`) out of `discovery.js` into pure `static/scripts/lib/statBlock.js`;
  `discovery.js` imports them with identical output. Move the `.mp-stat-*` and `.chart-legend*` CSS
  from `discovery.css` to `style.css` so both pages get it. Discovery must look unchanged.
- **`lib/optionRow.js`** (pure): one compact row per option — name, team, price; "vs BOU (home) ·
  easier"; "7.4 predicted points"; a 5-bar form strip (reuse the sparkline/bar idea, CSS only); a
  "Compare" toggle. Phrase bank in `lib/playerInfoCopy.js`.
- **`lib/playerSheet.js`** (pure): single player → sections Last 5 games, Momentum, Next 3 fixtures,
  Against {team} (or "No games against {team} in the last two seasons"). Two players → Discovery
  comparison: a shared legend plus stat blocks (predicted points with position-average marker,
  average points last 5, minutes last 5, points against this opponent) and a two-column fixture
  list. Skeleton loader while fetching. Missing pieces say so plainly; the rest still renders.
- **Captain and vice view** (`weekV2.js` wiring): tapping the hub's captaincy row opens the view
  (in the global bottom sheet from `layout.html`): our lean as Captain, the vice ("Steps in if
  {captain} doesn't play"), "Top alternatives" (shortlist), "Rest of your squad" (others). Tapping
  a name opens the player sheet; selecting two "Compare" toggles opens the compare (the lean is
  pre-selected as one of the two). Read-only for now: one line says "Make this change in the
  official app before the deadline". Saving arrives with Release 2.
- Node tests for every pure module under `tests/js/`.

## Testing

pytest-bdd: ranking by predicted points (including missing predictions); difficulty boundaries at
exactly ±20%; `games_against` across seasons where team ids changed but codes match; route 400 on
0 or 3 ids; route never 500. Node: row/sheet/compare renderers, escaping of names, missing-data copy,
`statBlock` output identical for Discovery's existing inputs.
