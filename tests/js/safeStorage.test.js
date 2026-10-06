import { test } from 'node:test';
import assert from 'node:assert/strict';
import { safeLocalStorage } from '../../FPL_site/static/scripts/lib/safeStorage.js';
import { readTeamId, saveTeamId } from '../../FPL_site/static/scripts/lib/teamId.js';
import { readLastVisit, recordVisit } from '../../FPL_site/static/scripts/lib/returningUser.js';

test('safeLocalStorage returns the storage when readable', () => {
    const storage = {};
    assert.equal(safeLocalStorage({ localStorage: storage }), storage);
});

test('safeLocalStorage returns null when reading the property throws', () => {
    const blocked = { get localStorage() { throw new Error('SecurityError'); } };
    assert.equal(safeLocalStorage(blocked), null);
    assert.equal(safeLocalStorage(undefined), null);
});

test('storage helpers tolerate null storage', () => {
    assert.equal(readTeamId(null), null);
    assert.equal(saveTeamId(null, '1234'), 1234);
    assert.equal(saveTeamId(null, 'abc'), null);
    assert.equal(readLastVisit(null), null);
    assert.doesNotThrow(() => recordVisit(null, new Date()));
});
