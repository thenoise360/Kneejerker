# Spike: player momentum signals

**Question:** For each candidate momentum signal, what data do we have today? What's buildable now, and what should be reported as "not yet tracked"?

**Constraints from the brief:**
- Momentum is never based on minutes played, the Influence, Creativity and Threat index, or raw form. One big game skews form.
- The label is Rising, Steady or Cooling, with one plain-English reason.
- Each signal is shown with an arrow plus a word, never colour alone.
- Signals we don't track yet are returned as `not_tracked`, so they can be added later without a redesign.

All checks were read-only against the production database on 2026-10-07, in the 2026/27 season with 5 gameweeks played.

## Signal by signal

| Signal | Data available | Verdict |
|---|---|---|
| **Fixture difficulty** | `team_fixture_predictions`: the match engine's expected goals for and against, per team, for the next 5 gameweeks (5 gameweeks stored now), refreshed daily. `team_strength` (Area 2) adds absence-adjusted ratings. | **Build now.** Compare the team's average expected goals for (attackers and midfielders) or against (defenders and goalkeepers) over the next 3 gameweeks with the same figure for its season-average opponent. |
| **Teammates in or out** | `bootstrapstatic_elements` (latest snapshot) has `chance_of_playing_next_round`, `status`, and season `expected_goals` and `expected_assists` per player. `elementsummary_history` has `minutes` per player per gameweek (667 players, 5 rounds). | **Build now.** A key creative teammate is someone with at least 15% of the team's expected goals plus assists. If one is newly back (0 minutes last gameweek and now available), the signal goes up. If one is newly out (played last gameweek and now under 50% chance), it goes down. Minutes are used only to detect *who was missing*, never as the player's own signal. |
| **Position on the pitch** | The official Fantasy Premier League API gives only the broad position (goalkeeper, defender, midfielder, forward). There is no formation or role data anywhere we can use. | **Not yet tracked.** It needs a new data source, such as line-up and formation data, which is out of scope. |
| **Manager change** | `team_manager_appointments` has 2 rows for 2026, and **no code writes to it**: it is maintained by hand. | **Not yet tracked** for momentum. Hand-entered data with no update path would go stale silently. It becomes a candidate once an automated source exists. Discover's "New manager in charge" category keeps using the table as it does today. |

## Recommendation

Launch with **fixtures and teammates**, as you expected. Position and manager change are returned as `not_tracked`, and the player sheet shows them as "Not tracked yet".

Combine the signals like this:
- each tracked signal contributes −1, 0 or +1
- **Rising:** the total is at least +1
- **Cooling:** the total is at most −1
- **Steady:** anything else
- the reason comes from the strongest non-zero signal, or "Nothing much has changed for them this week" when the result is Steady

Discover's "Heating up / Cooling off" strip sorts on a hidden score: the signal sum plus small magnitudes to break ties. **The score is never displayed.**

The existing Discover category backed by `get_momentum_players()` is about ownership and already displays as "Everyone's jumping on", so there is no user-facing name clash. Internally the new code is called `playerMomentum` to keep the two apart.

## Risks
- **Early-season shares are noisy.** With 5 games played, a teammate's share can swing on one game. The 15% key-teammate threshold and the 3-gameweek fixture window keep the signal coarse on purpose.
- **Blank and double gameweeks.** A team with no fixture in the window gets a fixtures signal of 0 with the reason "No game this week". A double gameweek counts both fixtures.
