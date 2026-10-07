# Brief: This Week — the four weekly decisions

*Saved verbatim from the product owner's brief, 2026-10-07. The roadmap that implements it is
`docs/superpowers/plans/2026-10-07-this-week-hub-roadmap.md`.*

## Read this first

You're working on Kneejerker, a mobile-first companion for the official Fantasy Premier League game. Stack: Python 3.11, Flask, MySQL via pymysql, Jinja2 server-rendered templates, vanilla JavaScript with no build step. Deployed on a free-tier dyno (expect cold starts).

The product owner is learning JavaScript through this project. Every JavaScript file you write is also learning material: comment the *why* in plain English, not just the *what*. Prefer readable over clever.

**Reference prototype:** `kneejerker-product-prototype_5.html` (put it in `docs/prototypes/`). It shows the intended behaviour. It is not code to copy wholesale: it uses hardcoded mock data, has logic bugs (listed below) and breaks the copy rules. Use it for behaviour, flow and tone.

## What we're building

The This Week front page becomes a weekly decision hub. Each week the user makes four decisions, and each one ends up as a line in their **plan**:

1. **Injuries:** what to do with each flagged player (bench, transfer out, play).
2. **Transfers:** first *should I make one?*, then *who out, who in?* Holding is a valid answer.
3. **Chips:** play one or hold.
4. **Captain and vice-captain.**

**Hard constraint:** we cannot write to the official game. The user decides here, then makes the change in the official app. So the plan is the core output. It has to persist and be editable.

### Front page behaviour

- **One headline decision at the top**, chosen by a deterministic priority order. Use the first rule that fires:
  1. Injury or suspension doubt on a starter.
  2. A blank fixture for one or more starters.
  3. Unused free transfers.
  4. Captain choice (fallback; always applies).

  Keep this order as a single constant so it's easy to reorder. It is still open to change.
- **The four decisions listed underneath.** Each decision is in one of three states:
  - **Needs a look:** something is flagged, with a one-line reason.
  - **Nothing to do this week:** pre-resolved by the engine (for example, chips → hold). It counts as done unless the user opens it. Visually quiet.
  - **Decided:** the user confirmed it, so it's ticked and in the plan.
- **Plan tab:** every decision with a "Change" action, exactly as in the prototype.

## Architecture decision (settled)

- **Python owns the rules engine.** Port the prototype's pure functions (`assessRisk`, `recommendChip`, `consistencyTier`, `minutesTier`, `fixtureTrend`, transfer planning, headline selection) into a Python service module. They must stay deterministic, with no randomness and no language-model calls, and be tested with pytest.
- **Flask exposes one JSON endpoint** for the week, for example `GET /api/this-week?team_id=...`. It returns tiers and facts, not prose. Example shape:

  ```json
  {
    "gameweek": 6,
    "deadline": "2026-10-10T10:00:00Z",
    "headline": { "decision": "injuries", "reason_key": "starter_doubt", "player": "Rice" },
    "decisions": {
      "injuries":  { "state": "needs_look", "players": [ { "name": "Rice", "risk_pct": 75, "tier": "high", "reasons": ["..."] } ] },
      "transfers": { "state": "needs_look", "free_transfers": 1, "bank": 1.3, "options": [ ... ] },
      "chips":     { "state": "nothing_to_do", "lean": "hold", "reason_key": "no_signal" },
      "captaincy": { "state": "needs_look", "suggested": "Haaland", "vice": "Salah", "shortlist": [ ... ] }
    }
  }
  ```

- **JavaScript owns everything stateful and visual.** That covers the phrase bank (selects sentences from tiers), rendering, the decision flow, and the plan in browser storage.
- **Progressive enhancement.** The Jinja template renders a usable read-only version of the hub server-side; JavaScript layers the interaction on top.

## Data: check these from first principles

Use the official game's public endpoints. Verify each assumption against a real response before building on it.

- **`bootstrap-static`:** players, availability (`chance_of_playing_next_round`, `news`, `status`), gameweeks and deadlines, chip windows.
- **`fixtures`:** blanks and doubles.
- **The upcoming gameweek's picks are not public until after the deadline.** Squad = last finished gameweek's picks (`entry/{id}/event/{gw}/picks/`) plus any transfers made since (`entry/{id}/transfers/`). Confirm this, and test the edge case of a user who has already made transfers this week.
- **Bank** comes from `entry_history.bank` in the picks response (in tenths of a million).
- **The free-transfers count is not exposed directly.** Derive it from `entry/{id}/history/`: one free transfer per gameweek, capped (read the cap from `game_settings.max_extra_free_transfers`), and reset by wildcard and free-hit weeks. Write this as its own tested function with fixtures covering the rollover, cap and chip-reset cases. **If any rule is ambiguous, stop and flag it rather than guessing.**
- **Chips used:** from `entry/{id}/history/` → `chips`. Respect the two-halves chip windows in `bootstrap-static`.

## Prototype bugs to fix in the port

1. **Transfers never check the bank.** A move costing more than the bank must not be offered, or must be labelled as needing funds from elsewhere. The copy must never show a negative bank.
2. **"Free, no hit needed" is hardcoded.** It must come from the derived free-transfers count.
3. **The free-transfer and four-point-cost options contradict each other.** With a free transfer available, offer the free move. Only offer a move that costs points when there are no free transfers left, or as a *second* move. Never offer both for the same swap.
4. **Chips always demand a decision.** When the lean is "hold", pre-resolve the decision to *nothing to do*.
5. **The onboarding copy still says "five decisions".** It is four.

## Copy rules (definition of done on every slice)

- **No acronyms anywhere in user-facing text.** This replaces `GW14` → "Gameweek 14", "FPL" → "the official game", `C`/`VC` → "Captain"/"Vice", `pts/£m` → "points per million", "-4 hit" → "costs you 4 points", and removes the "EO" glossary entry.
- **Tone:** clever mate, not smug spreadsheet. Advice as suggestion, never command ("Here's our lean, your call").
- **Plan language:** never imply we changed their team. Always "make this change in the official app before the deadline".
- **Design tokens:** Plus Jakarta Sans; Plum `#4B145B`, Teal `#29C2B2`, Pink `#F67CB0`, Charcoal `#333333`, Off-white `#F9F9F9`, Grey `#E5E5E5`. Cards have a 12px radius; buttons are pill-shaped. Contrast must be at least 4.5:1, with no colour-only signals (pair colour with a label or icon), and the layout must be usable at 375px wide.

## Build slices

Build serially. Each slice ships on its own behind a feature flag (`THIS_WEEK_HUB`). Use test-driven development: pytest (with pytest-bdd for behaviour scenarios) for Python, and Node's built-in test runner for pure JavaScript functions. At most two parallel subagents, each in its own git worktree, and only for independent subtasks within a slice.

**Slice 0: Recon (no code).** Read the repo and report back before writing anything. Find:
- Whether a gameweek state resolver already exists. A slice for one was planned; reuse it if it exists.
- How team ID is currently captured and stored.
- Where This Week currently lives.
- Any existing helpers for the official game's endpoints.

Propose file locations in line with the existing structure (organised by function: `/services/`, `/routes/`, `/static/js/`, and so on).

**Slice 1: Squad context service (Python).** Team ID → squad, bank, free transfers, chips remaining. All the derivations above, with tests.

**Slice 2: Rules engine (Python).** Port the pure functions, with the bugs fixed, plus headline selection and the three-state resolution per decision. This slice produces the JSON endpoint. Write behaviour scenarios for:
- every headline rule;
- the "nothing to do" path for each decision;
- the bank check;
- the free versus paid transfer cases.

**Slice 3: Hub, read-only.** A Jinja-rendered headline plus the four decision rows with their states. No interaction yet.

**Slice 4: Decision screens, one at a time.** Order: Captain and vice (applies every week), then Injuries, Transfers, Chips. Carry over the prototype's injuries → transfers hand-off: a player marked "transfer out" becomes the transfer starting point.

**Slice 5: Plan and persistence.**
- Store the plan in browser storage, keyed by `team_id` and gameweek.
- Wrap every read and write in try/catch, and make sure the page still works when storage is unavailable.
- Show the Plan tab with "Change" on every row.
- When the gameweek changes, start a fresh plan and add a gentle welcome-back line if last week's plan was never finished. No guilt copy.

**JavaScript expectations (all slices):**
- One `state` object.
- Render functions that redraw from state.
- One delegated click listener using `data-action`.
- Keyboard support for anything with `role="button"`.

These are the concepts the product owner is learning, so keep them recognisable and well commented.

## Out of scope: do not touch

Discovery tab, Radar tab, player profile bottom sheet, Team page, the match prediction engine, the Live Gameweek tab, the existing prediction scripts, authentication, and any route or template not listed above.

**If a change seems to require touching any of these, stop and flag it. Do not modify, remove or simplify existing functionality to make your work easier.**

## Definition of done (every slice)

- Tests written first and passing; behaviour scenarios readable by a non-engineer.
- Behind the feature flag; deployable on its own.
- No acronyms in user-facing copy; tone and design token rules met.
- Works at 375px wide, keyboard-navigable, and degrades gracefully without JavaScript or storage.
- A short summary at the end: what changed, which files, anything flagged, and one thing worth the product owner reading in the JavaScript to learn from.
