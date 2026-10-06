import test from 'node:test';
import assert from 'node:assert/strict';
import { planWeekRender } from '../../FPL_site/static/scripts/weekState.js';

function stubStorage() {
    const data = {};
    return {
        getItem: (k) => (k in data ? data[k] : null),
        setItem: (k, v) => { data[k] = String(v); },
    };
}

test('first visit to a closed gameweek gives no transition', () => {
    const plan = planWeekRender({ state: 'closed', gameweek: 5 }, stubStorage());
    assert.equal(plan.panel, 'closed');
    assert.equal(plan.showTransition, false);
});

test('live then closed shows the transition exactly once', () => {
    const storage = stubStorage();
    planWeekRender({ state: 'live', gameweek: 5 }, storage);
    const first = planWeekRender({ state: 'closed', gameweek: 5 }, storage);
    const second = planWeekRender({ state: 'closed', gameweek: 5 }, storage);
    assert.equal(first.showTransition, true);
    assert.equal(second.showTransition, false);
});

test('an unknown state gives panel none', () => {
    const plan = planWeekRender({ state: 'none', gameweek: null }, stubStorage());
    assert.equal(plan.panel, 'none');
});

test('blocked storage (null) is treated as nothing stored, with no error', () => {
    const closed = planWeekRender({ state: 'closed', gameweek: 5 }, null);
    assert.deepEqual(closed, { panel: 'closed', showTransition: false, message: null });
    const live = planWeekRender({ state: 'live', gameweek: 5 }, null);
    assert.equal(live.panel, 'live');
    assert.equal(live.showTransition, false);
});
