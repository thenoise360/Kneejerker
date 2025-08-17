// analytics.js (ES module)
const hasConsent = localStorage.getItem("analyticsConsent") === "true";
let mixpanelActive = false;

// Small helper to dynamically load the SDK only when needed
function loadScript(src) {
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = src;
    s.async = true;
    s.onload = resolve;
    s.onerror = reject;
    document.head.appendChild(s);
  });
}

// Immediately-invoked setup that respects consent
(async () => {
  if (!hasConsent) {
    console.log("⛔ Mixpanel not loaded - no consent");
    return;
  }

  try {
    // Load the Mixpanel browser SDK on-demand
    await loadScript("https://cdn.jsdelivr.net/npm/mixpanel-browser/dist/mixpanel.min.js");

    if (window.mixpanel && typeof window.mixpanel.init === "function") {
      window.mixpanel.init(window.MIXPANEL_TOKEN, {
        debug: true,
        track_pageview: true,
        persistence: "localStorage",
      });
      console.log("✅ Mixpanel initialized");

      window.mixpanel.track("Page Loaded", {
        path: window.location.pathname,
        title: document.title,
      });

      mixpanelActive = true;
    } else {
      console.warn("⚠️ Mixpanel SDK present but init not available");
    }
  } catch (err) {
    console.warn("⚠️ Failed to load Mixpanel SDK", err);
  }
})();

// ---- Safe wrapper (no-ops when inactive) ----
function safeTrack(name, data) {
  if (mixpanelActive && window.mixpanel) {
    window.mixpanel.track(name, data);
  }
}

// --- Public Exports (safe to import anywhere) ---
export function trackPlayerClick(playerId, playerName) {
  safeTrack("Player Clicked", { id: playerId, name: playerName });
}

export function identifyUser(userId, traits = {}) {
  if (mixpanelActive && window.mixpanel) {
    window.mixpanel.identify(userId);
    if (window.mixpanel.people && typeof window.mixpanel.people.set === "function") {
      window.mixpanel.people.set(traits);
    }
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
  safeTrack("Top Player Carousel Viewed", { position, player: playerName });
}

export function trackTeamOptimization(sliders) {
  safeTrack("Team Optimized", {
    pointsWeight: sliders[0],
    formWeight: sliders[1],
    minutesWeight: sliders[2]
  });
}
