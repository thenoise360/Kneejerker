/***** safeStorage.js *****/
// In some browsers (Safari with blocked site data, some private modes) even
// *reading* window.localStorage throws an error. Wrapping that one read in
// try/catch means the rest of the page can carry on without remembering
// anything. Returns the storage object, or null if it isn't available.
export function safeLocalStorage(win) {
    try {
        return win.localStorage ?? null;
    } catch {
        return null;
    }
}
