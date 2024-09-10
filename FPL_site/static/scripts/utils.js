export function updateLastUpdatedTime() {
    const lastUpdatedTime = document.getElementById('last-updated-time');
    const now = new Date();
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    lastUpdatedTime.textContent = `${hours}:${minutes}`;
}

export function formatNumber(value) {
    if (window.innerWidth <= 768) { // Mobile view
        if (value >= 1000000) {
            return (value / 1000000).toFixed(2) + 'M';
        } else {
            return value.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ","); 
        }
    }
    // Desktop view: format with thousand separators
    return value.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

export function formatOwnership(oldValue, newValue) {
    return `${oldValue}% \u2192 ${newValue}%`;
}

export function isUserActive(initializeCharts) {
    let lastActiveTime = Date.now();

    function updateActivity() {
        lastActiveTime = Date.now();
    }

    window.addEventListener('mousemove', updateActivity);
    window.addEventListener('keydown', updateActivity);

}

export function truncateLabel(label, maxLength = 20) {
    return label.length > maxLength ? label.substring(label.length, maxLength - 3) + '...' : label;
}
