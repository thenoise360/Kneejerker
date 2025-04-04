const mixpanel = window.mixpanel;
const hasConsent = localStorage.getItem("analyticsConsent") === "true";

let mixpanelActive = false;

if (hasConsent) {
  mixpanel.init(window.MIXPANEL_TOKEN, {
    debug: true,
    track_pageview: true,
    persistence: 'localStorage',
  });
  console.log("✅ Mixpanel initialized");
  mixpanel.track("Page Loaded", {
    path: window.location.pathname,
    title: document.title,
  });
  mixpanelActive = true;
} else {
  console.log("⛔ Mixpanel not loaded - no consent");
}

// Safe wrapper
function safeTrack(name, data) {
  if (mixpanelActive) {
    mixpanel.track(name, data);
  }
}

// --- Public Exports ---
export function trackPlayerClick(playerId, playerName) {
  safeTrack("Player Clicked", { id: playerId, name: playerName });
}

export function identifyUser(userId, traits = {}) {
  if (mixpanelActive) {
    mixpanel.identify(userId);
    mixpanel.people.set(traits);
  }
}

export function trackPlayerSummary(playerId, playerName) {
  safeTrack("Player Summary Viewed", { id: playerId, name: playerName });
}

export function trackComparison(id1, id2, name1, name2) {
  safeTrack("Player Comparison", {
    player1_id: id1,
    player1_name: name1,
    player2_id: id2,
    player2_name: name2
  });
}

export function trackCarousel(position, playerName) {
  safeTrack("Top Player Carousel Viewed", {
    position: position,
    player: playerName
  });
}

export function trackTeamOptimization(sliders) {
  safeTrack("Team Optimized", {
    pointsWeight: sliders[0],
    formWeight: sliders[1],
    minutesWeight: sliders[2]
  });
}
