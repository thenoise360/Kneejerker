import { test } from 'node:test';
import assert from 'node:assert/strict';
import { TEAM_ID_KEY, parseTeamId, readTeamId, saveTeamId } from '../../FPL_site/static/scripts/lib/teamId.js';

function memoryStorage(initial = {}) {
    const data = { ...initial };
    return { getItem: (k) => (k in data ? data[k] : null), setItem: (k, v) => { data[k] = String(v); }, data };
}

test('uses the same key as the live panel', () => {
    assert.equal(TEAM_ID_KEY, 'kj-fpl-team-id');
});

test('parses valid numbers and rejects junk', () => {
    assert.equal(parseTeamId('1234567'), 1234567);
    assert.equal(parseTeamId(' 42 '), 42);
    for (const junk of ['', 'abc', '-4', '0', '1e5', '12345678901', null, undefined]) {
        assert.equal(parseTeamId(junk), null, String(junk));
    }
});

test('read and save round-trip, and junk is never stored', () => {
    const storage = memoryStorage();
    assert.equal(readTeamId(storage), null);
    assert.equal(saveTeamId(storage, 'nope'), null);
    assert.equal(storage.data[TEAM_ID_KEY], undefined);
    assert.equal(saveTeamId(storage, '777'), 777);
    assert.equal(readTeamId(storage), 777);
});

test('blocked storage never throws', () => {
    const blocked = { getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); } };
    assert.equal(readTeamId(blocked), null);
    assert.equal(saveTeamId(blocked, '5'), 5);
});
