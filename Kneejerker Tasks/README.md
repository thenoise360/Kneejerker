# Kneejerker Phase 1 - Task Backlog

Phase 1 of the site rework: bring the Home page up to the new design system
and interaction model, wired to the existing MySQL-backed Flask app -
no backend logic changes except where explicitly noted.

## How this is organised

Each numbered folder is a **list**: a finite, focused set of tickets that
together produce one output. Work through lists in order - later lists
depend on earlier ones.

| List | Output | Depends on |
|---|---|---|
| `00-design-system-foundations` | Updated tokens + shared component CSS | - |
| `01-top-5-movers-list` | The "Top 5 in / Top 5 out" transfers view | `00` |
| `02-player-profile-bottom-sheet` | Tap-through player profile | `00`, and `01.1` for the entry point |
| `03-housekeeping-and-security` | Two small, independent fixes | - (can run any time) |

Each ticket file follows the same shape:

- **User story** - who wants this and why
- **Objective / outcome** - what "done" looks like, one sentence
- **Scope** - explicit in-scope and out-of-scope bullets
- **BDD scenarios** - Given/When/Then, testable
- **Definition of done** - a checklist
- **Technical notes** - pointers to real function/file names in this repo,
  and to the reference prototype where a pattern is being copied

## Important context for whoever (human or AI) picks this up

- There's a reference file, `kneejerker-product-prototype.html`, that
  defines the target visual/interaction patterns. **It is a throwaway
  design mockup, not production code** - no real backend, hardcoded fake
  player data, includes a "demo controls" panel that must never be ported.
  Extract only: CSS tokens/components, markup patterns, and the JS
  math/logic for real features (bar scaling, sparkline axis, etc.).
- No acronyms anywhere in user-facing copy or UI labels - spell everything
  out in plain language. This is a hard product requirement.
- Every number shown on screen must trace back to an existing backend
  function. Nothing invented client-side.
- Mobile-first. Primary target viewport: 375-430px wide.

## Note on duplicates in this Drive folder

Each list folder also contains earlier Google-Doc versions of these same
tickets (created before we switched to plain .md files for Claude Code).
The .md files are the current source of truth - safe to delete the
Google-Doc duplicates once you've confirmed the .md versions look right.