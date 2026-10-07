/***** hubCopy.js *****/
// The This Week hub's phrase bank. The server sends *facts and keys*
// ("starter_doubt", "Rice", tier "high"); this file decides the *words*.
//
// Why keep words out of the server? Tone is a product decision that changes
// often, and keeping every sentence in one file makes it easy to review for
// tone and acronyms. It is also pure: no DOM, no fetch, no randomness, so the
// same facts always give the same sentence and Node can test it directly.

// "A", "A and B", "A, B and C": how people actually list names out loud.
export function joinNames(names) {
    if (names.length <= 1) return names.join('');
    return `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`;
}

// One function per reason key, looked up by name. A lookup object like this
// replaces a long chain of if/else, and adding a new key is one new line.
const HEADLINES = {
    // The server says *why* (reason); the wording follows it. An unknown or
    // missing reason falls back to the plain "doubt" sentence.
    starter_doubt: (h) => {
        if (h.reason === 'ruled_out') return `${h.player} looks set to miss this one. Worth sorting before you do anything else. Your call.`;
        if (h.reason === 'missed_last_game') return `${h.player} didn't feature last game. Worth checking they're fit before the deadline.`;
        return `${h.player} is a doubt this week. Worth a look before you lock anything else in.`;
    },
    starter_blank: (h) => (h.players.length === 1
        ? `${h.player} has no match this gameweek, so they'd score nothing if they start.`
        : `${joinNames(h.players)} have no match this gameweek, so they'd score nothing if they start.`),
    unused_free_transfers: (h) => `You've got ${h.count} free transfer${h.count === 1 ? '' : 's'} sitting there. Worth seeing if one helps.`,
    captain_choice: (h) => `Our lean for captain is ${h.player}. Your call, as always.`,
    captain_no_prediction: () => "Our captain numbers aren't in yet this week, so this one's all yours for now.",
};

export function headlineSentence(headline) {
    const write = HEADLINES[headline.reason_key];
    // An unknown key should never show raw code words to a user.
    return write ? write(headline) : "Here's what we'd look at first this week.";
}

export function rowSentence(key, decision) {
    if (decision.state === 'needs_team') return "Add your team number and we'll check your players.";
    if (key === 'injuries') {
        const names = (decision.players || []).map((p) => p.name);
        if (names.length === 0) return 'Everyone looks fit. Nothing to do here this week.';
        return names.length === 1
            ? `${names[0]} needs a look before the deadline.`
            : `${names.length} players need a look: ${joinNames(names)}.`;
    }
    if (key === 'captaincy') {
        if (!decision.suggested) return "Captain numbers aren't in yet. Check back soon.";
        return decision.vice
            ? `Our lean: ${decision.suggested.name}, with ${decision.vice.name} as vice. Your call.`
            : `Our lean: ${decision.suggested.name}. Your call.`;
    }
    return '';
}

// The sentence under the team form when the number didn't work out. Same three
// sentences the server draws, so the page reads the same with or without
// JavaScript. Anything else (a good number, a guest) needs no message.
const TEAM_STATUS_SENTENCES = {
    not_found: "We couldn't find that team number. Check it and try again.",
    unavailable: "We couldn't reach the official game just now, so this is for everyone. Try again in a moment.",
    invalid: 'Team numbers are numbers only, for example 1234567.',
};

export function teamStatusSentence(teamStatus) {
    return TEAM_STATUS_SENTENCES[teamStatus] || '';
}
