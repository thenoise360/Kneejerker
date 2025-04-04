const COOKIE_NAME = "mixpanel_opt_in";
const COOKIE_EXPIRY_DAYS = 90;

function setCookie(name, value, days) {
  const expires = new Date(Date.now() + days * 86400 * 1000).toUTCString();
  document.cookie = `${name}=${value}; expires=${expires}; path=/; SameSite=Lax`;
}

function getCookie(name) {
  return document.cookie.split('; ').find(row => row.startsWith(name + '='))?.split('=')[1];
}

function showCookieBanner() {
  document.getElementById('cookie-banner').style.display = 'block';
}

function hideCookieBanner() {
  document.getElementById('cookie-banner').style.display = 'none';
}

function handleConsent(optIn) {
  setCookie(COOKIE_NAME, optIn, COOKIE_EXPIRY_DAYS);
  optIn ? mixpanel.opt_in_tracking() : mixpanel.opt_out_tracking();
  hideCookieBanner();
}

// On load
window.addEventListener("DOMContentLoaded", () => {
  const choice = getCookie(COOKIE_NAME);
  if (!choice) showCookieBanner();
  else {
    // Refresh cookie expiry
    setCookie(COOKIE_NAME, choice, COOKIE_EXPIRY_DAYS);
    choice === "true" ? mixpanel.opt_in_tracking() : mixpanel.opt_out_tracking();
  }

  document.getElementById("accept-cookies")?.addEventListener("click", () => handleConsent(true));
  document.getElementById("decline-cookies")?.addEventListener("click", () => handleConsent(false));
});
