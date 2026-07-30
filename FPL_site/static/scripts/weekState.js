/***** weekState.js *****/
// 06.0: pure decision logic for the Week tab's live/closed state controller.
// Kept free of DOM access so it can be verified in isolation against a
// stubbed storage object before being wired into home.js's rendering.

const LAST_STATE_KEY_PREFIX = 'kj-gw-last-state-';
const TRANSITION_SHOWN_KEY_PREFIX = 'kj-gw-transition-shown-';

// gwState: { state: 'live' | 'closed' | 'none', gameweek: number | null }
// storage: anything with getItem/setItem (e.g. window.localStorage, or a
//          stub in tests) - persists what state each gameweek was last seen
//          in, so the transition message can be shown exactly once per
//          gameweek's live -> closed flip.
export function planWeekRender(gwState, storage) {
    const state = gwState && gwState.state;
    const gw = gwState && gwState.gameweek;

    if (state !== 'live' && state !== 'closed') {
        return { panel: 'none', showTransition: false, message: null };
    }

    if (gw == null) {
        return { panel: state, showTransition: false, message: null };
    }

    const lastStateKey = LAST_STATE_KEY_PREFIX + gw;
    const shownKey = TRANSITION_SHOWN_KEY_PREFIX + gw;

    let showTransition = false;

    if (state === 'closed') {
        const lastSeen = storage.getItem(lastStateKey);
        const alreadyShown = storage.getItem(shownKey) === 'true';

        // Only a genuine live -> closed flip earns the transition message -
        // opening the tab for the first time on an already-closed gameweek
        // shouldn't announce a transition the user never actually saw happen.
        if (lastSeen === 'live' && !alreadyShown) {
            showTransition = true;
            storage.setItem(shownKey, 'true');
        }
    }

    storage.setItem(lastStateKey, state);

    return {
        panel: state,
        showTransition,
        message: showTransition
            ? `Gameweek ${gw}'s in the books — here's what's next`
            : null,
    };
}
