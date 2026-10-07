# This Week hub: the four weekly decisions — Implementation roadmap

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the This Week tab into a hub where the user makes four weekly decisions (injuries, transfers, chips, captain and vice) and leaves with a saved, editable plan to carry out in the official app.

**Architecture:** Python owns a deterministic rules engine (pure functions plus thin fetchers, the same split as `weekDecision.py`) and one JSON route. Jinja renders a read-only hub server-side, and plain JavaScript modules add the decision screens, the phrase bank and a plan kept in browser storage. Everything sits behind `THIS_WEEK_HUB` until launch.

**Tech Stack:** Python 3.11, Flask, `mysql.connector` through `dataModels.connect_db()`, `requests` for the official game's public API, Jinja2, vanilla ES modules (no build step), pytest + pytest-bdd, `node --test`.

**Spec:** `docs/superpowers/specs/2026-10-07-this-week-hub-brief.md`

## How this roadmap is cut

This follows the same approach as `2026-10-06-kneejerker-roadmap.md`:

- **Fixed time, flexible scope.** Every task is at most 2 developer days. If a task is heading past its estimate, cut scope and record what was dropped as a new task. Don't stretch the time box.
- **Each release is one pull request that someone can actually use.** With the flag on, every release leaves the hub in a working state. A release never ships half a screen.
- **Plan in detail just in time.** Step-by-step test-driven plans (with code) are written one release at a time, just before that release starts. Release 1 gets its detailed plan once the open decisions below are answered. Later releases are planned in detail after the previous one ships, so each plan reflects what earlier releases taught us.
- **Most valuable first.** Captaincy applies every week and needs no new data, so it ships before anything that depends on unresolved rules (free transfers, selling prices).

## Global Constraints

- Feature flag `THIS_WEEK_HUB`, read in `FPL_site/config.py` as `os.getenv('THIS_WEEK_HUB', '0') == '1'` on both configs (same pattern as the retired `FEATURE_WEEK_V2`). When the flag is off, `/this-week` renders exactly what it renders today.
- No acronyms in user-facing copy: "Gameweek 14", "the official game", "Captain"/"Vice", "points per million", "costs you 4 points". No "EO".
- Plan language: never imply we changed their team. Always say "make this change in the official app before the deadline".
- Tone: clever mate, not smug spreadsheet. Advice is a suggestion: "Here's our lean, your call".
- Tokens: Plus Jakarta Sans; Plum `#4B145B`, Teal `#29C2B2`, Pink `#F67CB0`, Charcoal `#333333`, Off-white `#F9F9F9`, Grey `#E5E5E5`; 12px card radius; pill buttons; contrast ≥ 4.5:1; never a colour-only signal; usable at 375px.
- Rules engine: deterministic, with no randomness and no language-model calls. Every number shown comes from a backend function.
- Tests never touch MySQL or the live API (`KJ_SKIP_DB_INIT=1`, monkeypatched fetchers). Every new route is added to `tests/test_regression_routes.py` with the flag both on and off.
- JavaScript: one `state` object, render functions that redraw from state, one delegated click listener on `data-action`, Enter/Space on every `role="button"`. Comment the *why* in plain English, because this code is learning material.
- **We never act on the manager's behalf.** The plan helps them decide, they make the change in the official app, and we keep the plan so Last week can reflect on it ("you chose X, here's how it went, and why").
- Plans for a known team are stored **on the server** in `weekly_plans`. Guests, and any save that fails, fall back to the browser. Every browser storage read and write goes through `safeLocalStorage()` plus try/catch. The page must work with storage blocked and with JavaScript off.
- Plans can only be written **before that gameweek's deadline** (the server checks this against `resolve_week`), so a plan is a true record of what was intended at the time.
- Out of scope, do not touch: Discovery, Radar, player bottom sheet, Team page, match prediction engine, Live Gameweek panel (`#gw-panel-live` and `liveGameweek.js`), prediction scripts, authentication.
- Branch from `main` (head `5f7960b8`). The current checkout, `area2-prediction-log`, is 10 commits behind it.

## Review Focus

These are the inputs most likely to hurt a real user that no task's happy-path tests cover. Each line is pinned to a test in the task that owns it.

1. **A free hit last week.** The squad reverts afterwards, and the free hit week's transfers show up in `/transfers/` (verified on entry 1, gameweek 5). Expected: the squad is the pre-free-hit squad and those transfers are ignored. Owner: task 1.3.
2. **Transfers already made for the upcoming gameweek.** Expected: they are applied to the squad and bank, the transferred-in player takes the outgoing player's starting slot, and the free-transfer count drops. Owners: tasks 1.3 and 4.1.
3. **Storage blocked, or JavaScript off.** Expected: the read-only hub still renders with the server-side headline and rows, and nothing throws. Owners: tasks 1.6 and 2.1.
4. **A move the bank can't cover.** Expected: it is never offered as affordable, and copy never shows a negative bank. Owner: task 4.3.
5. **The official API is slow or down on a cold start.** Expected: the guest hub is still rendered from the database, with a calm "couldn't load your team" line and no 500. Owner: task 1.5.
6. **A plan save that arrives after the deadline, for a team that doesn't exist, or with a malformed or oversized body.** Expected: it is rejected with a 4xx, nothing is written, and the browser keeps the plan locally with a calm message. Owner: task 2.1b.

---

## Recon findings (Slice 0)

| Question | Finding | Consequence |
|---|---|---|
| Gameweek state resolver? | **Exists:** `FPL_site/weekResolver.py` `resolve_week(events, now)` → `this_week.mode` ∈ upcoming/live/confirming/pre_season/off_season/unavailable. Called by `dataModels.get_week_view_state()`. | Reuse as-is. The hub only renders when `mode == 'upcoming'`. |
| Team ID capture/storage | Browser only: `static/scripts/lib/teamId.js` stores it under localStorage key `kj-fpl-team-id`, shared with the live tab. It is entered via the last-week recap form or the live form. The server never stores it; routes take `?team_id=` and validate it with `views._parse_team_id`. | The plan store keys off the same id. Without JavaScript the server can't know the team (see decision D2). |
| Where This Week lives | Route `/this-week` (`views.home`) → `home.html` → `partials/week_v2.html`, `#gw-panel-closed` → `#decision-hub` / `#decision-slot`. JavaScript: `weekV2.js` (glue) plus pure modules in `static/scripts/lib/`. | The hub replaces `#decision-slot` contents when the flag is on. |
| Existing official-API helpers | `lastWeekRecap.fetch_entry_picks(entry_id, gw)` → `('ok'|'not_found'|'unavailable', data)`. `dataModels.FPL_API`. `weekDecision.py` already has `squad_from_picks`, `availability_from_rows` (DB), `involvement_predictions`, `fixtures_by_team`, `DOUBT_BELOW = 75`, and a **two-rule headline** (starter doubt → captain). | Extend, don't duplicate. The new engine reuses these and the old "biggest decision" is superseded at launch. |
| Overlap | `/api/week/this-week-decision` plus `decisionView.js` already ship a single "biggest decision" card. | It stays untouched while the flag is off. It is only retired in Release 7, with your go-ahead. |
| Stack differences from the brief | The brief says pymysql and `/services/`, `/routes/`, `/static/js/` folders. The repo uses `mysql.connector` through `connect_db()`, flat `FPL_site/*.py` modules, routes in `views.py`, and JavaScript in `static/scripts/` and `static/scripts/lib/`. | Follow the repo (proposed file map below). Moving files around is out of scope. |
| Prototype | `docs/prototypes/kneejerker-product-prototype_5.html` (added 2026-10-07). Its notes are below. | Reference only. Never port its mock data. |

### Prototype 5: what to keep and what to fix

Behaviour to carry over:
- **Hub:** a notice at the top says we can't change their team; a "N of 4 decided" progress pill; one card per decision (`role="button"`, `data-action="open-action"`, `data-key`) with a status badge.
- **Captain screen** (`renderCaptaincyAction`):
  - a captain card with reasons, and a vice card saying "Steps in if {captain} doesn't play";
  - "Top alternatives": three from the squad, each with "Make captain" and "Make vice" buttons;
  - "Rest of your squad" with the same two buttons;
  - a save button, then the line saying we can't set this in the official app.
- **Injuries screen** (`renderInjuriesAction`):
  - one card per flagged player, with a risk badge, a fitness icon row (last 5 minutes) and a bookings icon row;
  - reasons, plus Bench / Transfer out / Play buttons;
  - confirm is disabled until every player has a choice;
  - "Transfer out" shows "We'll bring this into the Transfers screen as your starting point".
- **Transfers screen** (`buildActionInfo('transfers')`, `getOptionsFor`):
  - shows the bank;
  - names the injury hand-off;
  - a suggested move as two columns (out → in) showing form ("{n} of 5 above average") and price;
  - a "Want to go further?" second move with a break-even estimate, `ceil(4 / points-per-game gap)` gameweeks;
  - "Hold" is always offered.
- **Chips screen:** a "This week's signals" list (squad form, bench fixtures, blank/double, availability concerns), then "Our lean this week: …", then the options.
- **Plan tab** (`renderPlan`):
  - a banner whose headline depends on progress, plus one icon per decision;
  - one row per decision, with a "Change" button when decided and "Decide" when not;
  - captain rows show the captain and "Vice: …"; injury rows show "player → choice".

Fix in the port:
- Bugs 1–4 from the brief are confirmed at these places:
  - Bug 1: `bankAfterFirst` can go negative when the price gap is bigger than the bank.
  - Bug 2: "Free — no hit needed" is hardcoded at line 889.
  - Bug 3: `bring-in-free` and `bring-in-hit` are both offered for the same swap.
  - Bug 4: chips always ask for a choice.
- Bug 5 ("Five short decisions", "This week's 5 decisions", which lists "your transfer call" as a separate item) lives **only in the prototype's onboarding. The app has no onboarding**, so the fix is to make sure no hub copy carries a count other than four. Building onboarding is not in this brief.
- Acronyms to replace:
  - "C"/"VC" buttons → "Make captain"/"Make vice";
  - "Save X (C) and Y (VC)" → "Save Haaland as captain and Salah as vice";
  - "pts/£m" → "points per million", "pts/game" → "points a game";
  - "-4 hit" → "costs you 4 points";
  - "FPL" → "the official game";
  - "full XI" → "a full team".
- Colour-only signals: the plan tab's risk dot gets a text label; the difficulty colours get numbers.
- Tone: the plan headline "Kickoff's covered. Go be smug." stays only if you're happy with it, since the brief says "not smug". The default is "Kickoff's covered. Nice work."
- Not carried over (out of scope or not real):
  - the guided/instinct mode choice;
  - the friends league;
  - the "See why →" compare sheet and the player passport (the player bottom sheet is out of scope);
  - the "returning after 3 gameweeks" demo banner (Release 6.2 does the real one);
  - all mock data.

**API facts verified against live responses (2026-10-07):**
- `bootstrap-static.game_settings.max_extra_free_transfers = 4`. `chips` lists each chip twice, once per half: events 1/2–19 and 20–38. Next event is gameweek 6, deadline `2026-10-10T10:00:00Z`.
- `entry/{id}/history/` gives `current[]` with `event_transfers`, `event_transfers_cost` and `bank`, plus `chips[]` with `{name, event}`.
- `entry/{id}/transfers/` gives `{element_in, element_in_cost, element_out, element_out_cost, event, time}`, including transfers made during a **free hit week**.
- `entry/{id}/event/{gw}/picks/` gives `active_chip` and `entry_history.bank` (tenths of a million).
- `entry/{id}/` gives `last_deadline_bank` and `last_deadline_total_transfers`.

## Open decisions (answer before the release that needs them)

| # | Question | Blocks | Recommended default |
|---|---|---|---|
| Q1 | ~~Prototype 5 missing~~ **Resolved 2026-10-07**: added to `docs/prototypes/`. Remaining sub-question: keep "Go be smug"? | Task 6.1 | Use "Kickoff's covered. Nice work." |
| Q2 | **Free-transfer rules are ambiguous.** The brief says wildcard and free hit *reset* free transfers. My understanding of the rules since 2024/25 is that saved free transfers are *kept* through a wildcard or free hit. It's also unclear whether that week still earns +1, whether the cap is 1 + `max_extra_free_transfers` (= 5), and how one-off league-wide top-ups (which are not in the API) are handled. Per the brief: **stop and flag.** | Task 4.1 | **Resolved 2026-10-07: the manager reads it from the official app.** The count is only in the logged-in `my-team` endpoint (403 without a login, and authentication is out of scope), so we never fetch it. The transfers screen asks "How many free transfers does the official app show you?" and pre-fills our best guess from history (4.1). The manager's number always wins and is saved in the plan. |
| Q3 | Selling prices aren't public. A player bought at £6.0m who has risen to £6.4m sells for £6.2m, so a bank check that uses current prices can wrongly approve or wrongly block a move. | Task 4.2 | Derive purchase prices: `element_in_cost` from `/transfers/` for players bought by transfer, or the starting squad's gameweek-1 `value` in `elementsummary_history`. Selling price = purchase + floor(rise / 2). |
| Q4 | **Resolved 2026-10-07.** The brief puts the phrase bank in JavaScript, but the no-JavaScript hub needs words too. | Release 1 | **Agreed:** Jinja renders short **factual** lines per `reason_key` (for example, "Rice: 75% chance of playing") from a small Jinja macro. JavaScript upgrades them to the conversational phrase bank. No prose is duplicated. |
| Q5 | Without JavaScript, the server can't see the localStorage team id. | Release 1 | The read-only hub has a plain `<form method="get">` with `team_id`, so `/this-week?team_id=123` renders the personal hub server-side. JavaScript keeps using localStorage. |
| Q6 | Yellow-card ban thresholds aren't in the API. | Task 1.2 | One constant `BOOKING_BANS = [(19, 5), (32, 10)]` (by gameweek, cards) with a season note, flagged in the code. |
| Q7 | Should the first decision screen persist? | Release 2 | **Yes.** Plan storage ships with the captain screen. The Plan *tab* still comes in Release 6. |
| Q8 | **Resolved 2026-10-07: plans are stored in a server table** so Last week can reflect on them. This breaks the current promise in `teamId.js` that the team number "is never stored on our server", so the privacy page and that comment change in task 2.1c. `privacy.html` isn't in the brief's list of files to touch, but this decision makes the change necessary. | Release 2 | Keep plans for the current season plus one. "Forget my plans" deletes them. There's no login, so a plan for a team number can be written by anyone who knows it: low harm, because it only affects that team's own reflection. Mitigations: deadline lock, the team must exist, size limits, one row per team per gameweek. |

## File map

| File | Responsibility | Created in |
|---|---|---|
| `FPL_site/config.py` | `THIS_WEEK_HUB` flag | 1.1 |
| `FPL_site/squadContext.py` | Fetchers (`/history/`, `/transfers/`, picks) and pure derivations: squad, bank, free transfers, chips remaining, selling prices | 1.3, 4.1, 4.2, 5.1 |
| `FPL_site/hubSignals.py` | Pure player signal tiers: `assess_risk`, `minutes_tier`, `consistency_tier`, `fixture_trend`, plus their DB fetchers | 1.2 |
| `FPL_site/hubRules.py` | Pure decision resolution (three states per decision), `HEADLINE_RULES`, `select_headline`, transfer options, chip lean | 1.4, 4.3, 5.2 |
| `FPL_site/thisWeekHub.py` | Live-route entry point `get_this_week_hub(team_id)`: connects, fetches, composes | 1.5 |
| `FPL_site/views.py` | `GET /api/week/this-week`; `/this-week` passes the hub context when the flag is on | 1.5, 1.6 |
| `FPL_site/templates/partials/week_hub.html` | Server-rendered read-only hub (headline, four rows, team form) | 1.6 |
| `FPL_site/static/content/home.css` | Hub styles (tokens) | 1.6 |
| `FPL_site/static/scripts/lib/hubCopy.js` | Pure phrase bank: `reason_key` + tiers → sentence | 1.7 |
| `FPL_site/static/scripts/lib/planStore.js` | Browser fallback for guests and failed saves, keyed `kj-plan:{teamId or guest}:{gameweek}` | 2.1a |
| `FPL_site/weeklyPlans.py` | `weekly_plans` table: create-if-missing, upsert, load, delete; pure validation of the plan body | 2.1b |
| `FPL_site/planReflection.py` | Pure evaluation of last week's plan against what happened, plus fetchers for actual picks and points | 8.1, 8.2 |
| `FPL_site/static/scripts/lib/reflectionView.js` | Pure rendering of the plan reflection card | 8.3 |
| `FPL_site/static/scripts/lib/hubState.js` | Pure state transitions (`openDecision`, `decide`, `change`) | 2.2 |
| `FPL_site/static/scripts/thisWeekHub.js` | The `state` object, render functions, delegated listener, keyboard | 2.2 onwards |
| `features/this_week/*.feature` + `tests/step_defs/test_this_week_*.py` | Behaviour scenarios | each Python task |
| `tests/js/*.test.js` | Node tests for each `lib/` module | each JavaScript task |
| `docs/prototypes/kneejerker-product-prototype_5.html` | Reference only | 1.1 |

---

## Backlog

Estimates are in developer days (d). **∥** marks tasks that can run as parallel subagents (two at most, each in its own worktree). Each task's "Done when" scenarios become its first failing tests.

### Release 1: "See what this week needs" (read-only hub: headline, captain, injuries) — 9d

Detailed plan: [`2026-10-07-this-week-hub-release1.md`](2026-10-07-this-week-hub-release1.md).

Value: a user with a saved team sees the one thing that matters this week, and why, plus captain and injury rows with states, including without JavaScript. Uses only data we already have. Transfers and chips show the existing "more on the way" line until they ship.

| Task | Est | What it delivers | Done when |
|---|---|---|---|
| **1.1 Flag and scaffolding** | 0.5 | `THIS_WEEK_HUB` in config (prototype already in `docs/prototypes/`). Regression gate parametrised over the flag. | Flag off: the `/this-week` HTML is byte-for-byte unchanged from main (snapshot markers). Flag on: still 200. |
| **1.2 Player signal tiers** ∥A | 1.5 | `hubSignals.py`: `assess_risk(player, signals, upcoming_gameweek) -> {pct, tier, reasons_keys}`, (`minutes_tier`, `consistency_tier` and `fixture_trend` move to 4.3/5.2, where they are first used). Fetcher for the last 5 rounds of minutes and yellow cards from `elementsummary_history` (verify the columns first). `reasons` become **keys plus facts**, not prose. | `chance_of_playing_next_round == 0` or `status in ('i','s','u')` → `confirmed`, 100. Last game 0 minutes against a normal 80 → 75/high. One card from a ban → 75. No signals → `low`. Each tier boundary has a test at its edge. |
| **1.3 Squad context v1** ∥B | 1.5 | `squadContext.py`: `fetch_history`, `fetch_transfers` (same `('ok'|'not_found'|'unavailable', data)` contract as `fetch_entry_picks`). Pure `current_squad(picks_by_gw, transfers, last_gw) -> [{id, starter, is_captain, is_vice}]` and `bank_now(picks, transfers, last_gw) -> tenths`. | Plain week: the squad equals the picks. **Transfers already made for next gameweek:** applied, and the incoming player inherits the outgoing player's starter flag. **Free hit last week:** uses the previous gameweek's picks and ignores the free hit week's transfers. Bank adjusts by in/out costs and is never negative. Wildcard week transfers are already reflected in the picks. |
| **1.4 Injuries and captaincy resolution and headline** | 1.5 | `hubRules.py`: `resolve_injuries(squad, risks) -> {state, players}`, `resolve_captaincy(squad, predictions, fixtures) -> {state, suggested, vice, shortlist}`, `HEADLINE_RULES = ('starter_doubt', 'starter_blank', 'unused_free_transfers', 'captain')`, `select_headline(context) -> {decision, reason_key, player}`. Rule 3 returns "doesn't fire" until Release 4. Feature `features/this_week/headline.feature`. | One scenario per headline rule firing, plus "the earlier rule wins". Injuries with no flagged starters → `nothing_to_do`. Captaincy is always `needs_look` (it applies every week). Reordering `HEADLINE_RULES` changes the outcome, tested. Blank: a starter whose team is absent from `fixtures_by_team`. |
| **1.5 JSON route** | 1 | `thisWeekHub.get_this_week_hub(team_id)` composes 1.2–1.4. `GET /api/week/this-week?team_id=` returns the brief's shape (transfers and chips: `{"state": "not_ready"}`). The three official-API calls run concurrently with timeouts. Guest (no team, unknown team, or API down) → `based_on: "everyone"` hub with a `team_status` field. | Route in the regression gate. 400 on a bad team id. API down → 200 guest hub plus `team_status: "unavailable"`, never 500. The JSON contains no prose fields. |
| **1.6 Read-only hub (Jinja)** | 1.5 | `partials/week_hub.html` included in `#gw-panel-closed` when the flag is on: the headline card, four rows each showing state as **icon plus label** ("Needs a look" / "Nothing to do this week" / "Decided"), factual lines from a Jinja macro per `reason_key` (Q4), and a `GET` team-number form (Q5). CSS uses the tokens. | Template tests for each state. JavaScript disabled → full read-only hub. `?team_id=` renders the personal version. No acronyms (test greps the rendered HTML for `\bGW\d`, `FPL`, `\bVC\b`, `pts`). Usable at 375px (manual check). |
| **1.7 Phrase bank and JavaScript upgrade** | 1.5 | `lib/hubCopy.js`: `headlineSentence`, `rowSentence`, plus `lib/hubView.js` `renderHubBody` mirroring the template. These are deterministic: the same tier always gives the same sentence. `weekV2.js` fetches `/api/week/this-week` when the hub is present and upgrades the factual lines in place. | Node tests: every `reason_key` has a sentence, no acronyms, suggestions not commands. Fetch failure leaves the server-rendered hub intact. |

**Parallel lanes:** 1.2 ∥ 1.3. Then 1.4 → 1.5 → 1.6 → 1.7 run in series (1.6 can start once 1.5's JSON shape is frozen).

### Release 2: "Decide your captain and vice, and we'll remember it" — 6d

Value: the first real decision, saved on the server from the first week. As with the prediction log, every week without stored plans is history the reflection can never get back.

Value: the first real decision, made and kept across reloads.

| Task | Est | What it delivers | Done when |
|---|---|---|---|
| **2.1a Plan format plus browser fallback** ∥A | 1 | The plan format (`PLAN_VERSION`) is shared by browser and server: `{version, team_id, gameweek, decisions: {captaincy: {captain_id, vice_id}, injuries: {player_id: choice}, transfers: {...}, chips: {...}}, decided_at}`. Player **ids**, not names. `lib/planStore.js`: `loadLocalPlan`, `saveLocalPlan`, each wrapped in try/catch. | Blocked storage → an empty plan and `false`, no throw. Corrupt JSON → an empty plan. Separate teams and gameweeks stay separate. |
| **2.1b `weekly_plans` table and plan routes** ∥B | 1.5 | `weeklyPlans.py`: table `(team_id, year_start, gameweek, plan_json, lean_json, model_version, created_at, updated_at, PRIMARY KEY (team_id, year_start, gameweek))`, created if missing on first write. **`lean_json` (our suggestion and its reason keys) is computed by the server** from `get_this_week_hub(team_id)` on save, never trusted from the browser, so later "how good were our leans" figures are honest. Pure `validate_plan(body, week_state) -> (ok, error)`. Routes: `PUT /api/week/plan`, `GET /api/week/plan?team_id=&gameweek=`, `DELETE /api/week/plan?team_id=` ("forget my plans"). All three go into the regression gate. | Save before the deadline → 200 and the row is upserted. After the deadline → 409, nothing written. Unknown team → 404. Body over 8 KB or the wrong shape → 400. Database down → 503, and the browser keeps it locally. Two saves → one row, updated. Delete removes every gameweek for that team. |
| **2.1c Privacy and "Forget my plans"** | 0.5 | Update the privacy page and the `teamId.js` comment: we keep your weekly plan against your team number so we can look back on it with you, for this season and next. A "Forget my plans" link calls `DELETE`. A one-line notice appears on the first save. | The privacy page states what is stored and for how long. Forget → the next `GET` is empty. No acronyms. |
| **2.2 Hub controller skeleton** | 1.5 | `lib/hubState.js` (pure: `initialState(hubData, plan)`, `openDecision`, `closeDecision`, `decide(state, key, choice)`, `rowState(state, key)` → needs_look / nothing_to_do / decided) and `thisWeekHub.js` (one `state`, `render()`, one delegated `click` listener on `data-action`, Enter/Space for `role="button"`). Hub cards follow prototype `renderHub`: "N of 4 decided" pill, a status badge with icon plus label, and the "we can't change your team" notice. Heavily commented as learning material. | Node tests: `nothing_to_do` stays done unless opened. Decided overrides engine state. Keyboard: Enter/Space on a row opens it (manual check plus a test of the key handler function). |
| **2.3 Captain and vice screen** | 1.5 | Prototype `renderCaptaincyAction` layout: captain card with reasons, a vice card ("Steps in if … doesn't play"), "Top alternatives" (three from `captaincy.shortlist`) and "Rest of your squad", each with "Make captain"/"Make vice". Our lean is pre-selected. Making the current vice the captain swaps the two. Confirm → Decided, saved through `PUT /api/week/plan` (or the browser fallback for guests), with the line "Make this change in the official app before the deadline". | Picking the same player for both is prevented with a kind message. Reload, including on another device, keeps the decision. Server down → saved locally, with a calm "we'll keep it on this device" line. "Captain"/"Vice" are never abbreviated. |

### Release 3: "Sort out your injuries" — 1.5d

| Task | Est | What it delivers | Done when |
|---|---|---|---|
| **3.1 Injuries screen** | 1.5 | Prototype `renderInjuriesAction`: one card per flagged player with the risk badge (label plus %), fitness and bookings icon rows (each icon has text for screen readers), reasons, and Bench / Transfer out / Play. Confirm stays disabled until every player has a choice. Decided once every flagged player has a choice. "Transfer out" choices are stored as `state.handoff.transferOut` for Release 4. | No flagged players → the row is quiet `nothing_to_do` and opening it says so. Partial answers stay `needs_look`. Plan lines read "Bench Rice in the official app before the deadline". |

### Release 4: "Should I make a transfer?" — 7.5d

Value: the hardest weekly decision, with holding as a valid answer. **Blocked by Q2 and Q3.**

| Task | Est | What it delivers | Done when |
|---|---|---|---|
| **4.1 Free-transfer best guess plus confirm** ∥A | 1 | Pure `estimate_free_transfers(history_current, max_extra, upcoming_gw, transfers_made_this_week) -> {count, confident}`. This is only a pre-fill: `confident` is false whenever a wildcard or free hit was played since the manager last banked a transfer, so the copy says "check the official app" rather than guessing silently. A JavaScript stepper (0 to 1 + `max_extra`) lets the manager confirm or correct the number. The confirmed count drives the free and paid options. | Rollover, the cap, a paid transfer (never below 0), already transferred this week, a mid-season joiner, a chip week → `confident: false`. The confirmed number overrides the estimate in `transfer_options`. |
| **4.2 Selling prices** ∥B | 1.5 | Pure `selling_price(purchase, now) -> tenths` and `purchase_prices(transfers, start_values) -> {element: tenths}`, plus a fetcher for gameweek-1 values. | Rise of 0.4 → sells for +0.2. Rise of 0.3 → +0.1 (floor). Price drop → sells at the current price. A player bought, sold and bought again uses the latest purchase. |
| **4.3 Transfer options engine** | 2 | Runs in Python, with the confirmed count passed back as `?free_transfers=` so the rules stay server-side. `hubRules.transfer_options(squad, free_transfers, bank, selling_prices, candidates, handoff_out) -> {verdict: 'hold'|'consider', options: [...]}`. "Out" defaults to the injury hand-off, otherwise the coldest by `consistency_tier`. "In" is the same position with the best stored `player_predictions`. Affordability = bank + selling price ≥ cost; otherwise `needs_funds: true` (never offered as affordable). Free/paid follows bug 3. Feature `features/this_week/transfers.feature`. | Scenarios: bank check (affordable, short by £0.4m → labelled, never negative); free available → only the free move; no free transfers → one move that costs 4 points; second move costs points; never the same swap twice; hold when no move beats the threshold → `nothing_to_do` with lean "hold". |
| **4.4 Wire into hub plus headline rule 3** | 1 | `transfers` in the JSON (`free_transfers`, `bank`, `options`). `unused_free_transfers` headline rule live. Server-rendered row plus phrase-bank keys. | Headline scenario for rule 3, with rules 1–2 still winning. Row renders all three states. |
| **4.5 Transfers screen** | 2 | Step 1, "Should I make one?" (our lean, your call; hold is a first-class answer). Step 2, "Who out, who in?", starting from the injury hand-off. Layout follows prototype `buildActionInfo('transfers')`: bank, two-column out → in with form and price, and an optional "Want to go further?" second move with break-even `ceil(4 / gap)` gameweeks. No "See why" compare sheet. Plan lines say exactly what to do in the official app. | Holding → Decided, with the plan line "Hold your transfer: it rolls over to next week". Hand-off from injuries pre-selects the outgoing player. A move needing funds explains where the money would have to come from. |

### Release 5: "Chips: play one or hold" — 3.5d

| Task | Est | What it delivers | Done when |
|---|---|---|---|
| **5.1 Chips remaining** | 1 | Pure `chips_remaining(chips_used, chip_windows, upcoming_gw) -> [name]`, respecting the two halves in `bootstrap-static.chips`. | Used in the first half → available again in the second half. A first-half chip unused by gameweek 19 → gone in gameweek 20. A chip outside its window is not offered. |
| **5.2 Chip lean** | 1.5 | Port `recommend_chip` (blank → free hit; double plus steady form → triple captain; squad-wide cold → wildcard; bench signal → bench boost; else hold). Blank/double detection from `fixtures_fixtures`. **Hold → `nothing_to_do`** (bug 4). Wired into the JSON and the server-rendered row. | One scenario per lean, plus "hold is quiet". Only chips in `chips_remaining` can be suggested. |
| **5.3 Chips screen** | 1 | Prototype chips screen: a "This week's signals" list (squad form, bench fixtures, blank/double, availability concerns), then "Our lean this week", then only the *available* chips plus "Hold" as the default. | Opening a `nothing_to_do` row and confirming hold → Decided. The plan line names the chip in full ("Triple Captain", "Bench Boost"). |

### Release 6: "Your plan" — 3d

| Task | Est | What it delivers | Done when |
|---|---|---|---|
| **6.1 Plan tab** | 1.5 | Prototype `renderPlan`: a progress banner (headline from Q1), one icon per decision, and one row per decision with "Change" when decided and "Decide" when not (re-opens that screen). The injury risk dot gets a text label. The heading reminds the user to "make these changes in the official app before the deadline". | All four lines present. Change → edit → the plan updates. `nothing_to_do` lines read calmly ("Chips: holding this week"). |
| **6.2 Gameweek rollover** | 1 | A new gameweek starts a fresh plan, because the server key includes the gameweek. If last week's plan wasn't finished, show one gentle welcome-back line (no guilt). Local fallback plans more than two gameweeks old are pruned; server plans are kept for the reflection. A local plan saved while the server was down is uploaded on the next visit if its deadline hasn't passed. | Unfinished → line shown once. Finished → no line. Storage blocked → no line and no error. A pending local plan uploads, but only before the deadline. |
| **6.3 Copy sweep** | 0.5 | Bug 5: the app has no onboarding, so make sure no hub copy states a count other than four. Acronym and contrast check across every hub state. | The automated acronym test covers every rendered state. |

### Release 8: "How did your plan go?" (Last week reflection) — 4.5d

Value: the payoff for keeping the plan. Last week tells each manager what they planned, what they actually did, how it turned out, and why. It never shames them.

Can be built any time after Release 2 has stored at least one finished gameweek of plans. The Last week tab is part of the Week tab, so it is in scope, but the existing recap cards must not change.

| Task | Est | What it delivers | Done when |
|---|---|---|---|
| **8.1 Plan evaluation (pure)** | 2 | `planReflection.evaluate_plan(plan, lean, actual, points) -> [{decision, planned, did, outcome_tier, reason_key, facts}]`. "Did" comes from the public picks, transfers and chips after the deadline. Captaincy compares the captain's points with the vice's and our lean's. Transfers compare points in versus points out (minus any 4-point cost). Chips compare the chip's points against holding (for example, bench points for Bench Boost). Injuries: a benched doubt who played, or a player who played and didn't feature. Outcome tiers: `worked`, `close_call`, `didnt_work`, `not_carried_out`. | Behaviour scenarios: one per decision and tier, plus "planned it but didn't do it in the official app", "no plan saved" (nothing to reflect on, no guilt), and the free hit week. |
| **8.2 Reflection route** | 1 | `GET /api/week/plan-reflection?team_id=&gameweek=` loads the server plan and the actual picks/points (reusing `fetch_entry_picks` and `elementsummary_history`), then calls `evaluate_plan`. Added to the regression gate. | No plan → `{status: "no_plan"}`. Gameweek not final → `{status: "not_ready"}`. API down → 200 with `status: "unavailable"`, never 500. |
| **8.3 Reflection card** | 1.5 | `lib/reflectionView.js` plus phrase bank keys, rendered in `#personal-recap-slot` *below* the existing personal recap. Verdict plus one reason per decision, with the numbers behind an expander, "worked" credited to the manager, and "didn't work" framed as luck or new information, never as blame. | Node tests per tier. No acronyms. With no plan, the card simply doesn't appear. |

### Release 7: Launch — 1d (needs your explicit go-ahead)

| Task | Est | What it delivers | Done when |
|---|---|---|---|
| **7.1 Remove the flag** | 1 | `THIS_WEEK_HUB` removed. The superseded `/api/week/this-week-decision`, `decisionView.js` and the "more on the way" line are retired. | Full release gate green. Regression gate updated. Live smoke at 375px across every state. |

**Total: about 36 developer days across 8 releases. The largest single task is 2d.** Release 8 can come before Release 7 or after it.

## Release gate (every release)

Same as `2026-10-06-kneejerker-roadmap.md`:

1. Run `vs-env/Scripts/python.exe -m pytest -q` (green, and the count does not drop) and `npm test` (green).
2. Run `py_compile` and `node --check` on changed files.
3. Live smoke with the flag on and off: `curl` every page route and `/api/week/this-week` with and without `team_id`.
4. Browser pass at 375px: JavaScript off, then storage blocked.
5. One whole-branch review.
6. Product checklist: no acronyms, verdict plus reason, a suggestion rather than a command, nothing that shames the user.
7. A release summary that covers what changed, which files, anything flagged, and **one thing in the JavaScript worth reading to learn from**.
