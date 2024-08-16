export function updateLastUpdatedTime() {
    const lastUpdatedTime = document.getElementById('last-updated-time');
    const now = new Date();
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    lastUpdatedTime.textContent = `${hours}:${minutes}`;
}

export function formatNumber(value) {
    if (window.innerWidth <= 768) { // Mobile view
        if (value >= 100000) {
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

export function callUpdateEndpoint(initializeCharts) {
    fetch('/api/update-data')
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            console.log(data.message);
            initializeCharts(); // Re-initialize charts after update
        })
        .catch(error => console.error('Error:', error));
}

export function isUserActive(initializeCharts) {
    let lastActiveTime = Date.now();

    function updateActivity() {
        lastActiveTime = Date.now();
    }

    window.addEventListener('mousemove', updateActivity);
    window.addEventListener('keydown', updateActivity);

    setInterval(() => {
        if (Date.now() - lastActiveTime < 30000) {
            callUpdateEndpoint(initializeCharts);
        }
    }, 30000);
}

export function truncateLabel(label, maxLength = 20) {
    return label.length > maxLength ? label.substring(0, maxLength - 3) + '...' : label;
}
