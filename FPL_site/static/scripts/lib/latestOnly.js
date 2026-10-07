/***** latestOnly.js *****/
// Guards against slow, out-of-date answers. Pure: no DOM access.
//
// Imagine you ask the server for a page of data, change your mind, and ask
// again. The second answer might arrive first, and then the slow first answer
// arrives and paints over it. That would show stale information.
//
// The fix: before each request, call start() to get a numbered ticket. When
// an answer arrives, only use it if its ticket is still the newest one.
export function createLatestGuard() {
    let newest = 0;
    return {
        // Hands out the next ticket; every earlier ticket becomes stale.
        start() {
            newest += 1;
            return newest;
        },
        // True only for the most recently issued ticket.
        isLatest(token) {
            return token === newest;
        },
    };
}
