document.addEventListener('DOMContentLoaded', function () {
    console.log('Script loaded');

    const burgerIcon = document.getElementById('burgerIcon');
    const mobileMenuItems = document.getElementById('mobileMenuItems');
    const mainContent = document.querySelector('main');

    // Toggle mobile menu open/close
    burgerIcon.addEventListener('click', function () {
        burgerIcon.classList.toggle('open');
        mobileMenuItems.classList.toggle('open');
    });

    // Attach click event listeners to each navigation link
    document.querySelectorAll('.listItem').forEach(item => {
        item.addEventListener('click', function (e) {
            e.preventDefault();  // Stop the link from triggering a page reload
            const contentUrl = this.getAttribute('href');
            fetchContent(contentUrl, mainContent);
        });
    });

    // Initialize the page on load
    initializePage(window.location.pathname, mainContent);

    // Handle browser back and forward navigation
    window.addEventListener('popstate', function (event) {
        if (event.state && event.state.url) {
            fetchContent(event.state.url, document.querySelector('main'), false);
        }
    });
});

// Fetch content and replace main's innerHTML
function fetchContent(url, mainContent, updateHistory = true) {
    fetch(url, {
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.text();
        })
        .then(html => {
            mainContent.innerHTML = html;
            if (updateHistory) {
                history.pushState({ url: url }, '', url);  // Update the URL without reloading the page
            }
            initializePage(url, mainContent);  // Initialize page-specific elements and data
        })
        .catch(error => console.error('Error loading the content:', error));
}

// Initialize page-specific elements and data
function initializePage(url, mainContent) {
    if (url.includes('/compare')) {
        initializeComparePage();
    }
    // Add more conditions for other pages as needed
}

// General initialization for all pages
function initializeGeneralData() {
    // Load any data that should be available on initial site load
    // Example: Load list of players
    fetch('/get_players')
        .then(response => response.json())
        .then(players => {
            // Do something with the player list if needed globally
            console.log(players);
        })
        .catch(error => console.error('Error loading general data:', error));

    fetch('/get_players_by_team')
        .then(response => response.json())
        .then(players => {
            // Do something with the player list if needed globally
            console.log(players);
        })
        .catch(error => console.error('Error loading general data:', error));

    fetch('/get_players_by_position')
        .then(response => response.json())
        .then(players => {
            // Do something with the player list if needed globally
            console.log(players);
        })
        .catch(error => console.error('Error loading general data:', error));
}

// Initialize the Compare page
function initializeComparePage() {
    console.log('initializeComparePage function called');

    // Fetch and initialize pills
    Promise.all([
        fetch('/get_players').then(response => response.json()),
        fetch('/get_players_by_team').then(response => response.json()),
        fetch('/get_players_by_position').then(response => response.json())
    ]).then(([allPlayers, players
