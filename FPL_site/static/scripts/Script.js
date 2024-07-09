document.addEventListener('DOMContentLoaded', function () {
    console.log('Script loaded');

    const burgerIcon = document.getElementById('burgerIcon');
    const mobileMenuItems = document.getElementById('mobileMenuItems');
    const mainContent = document.querySelector('main');
    const breadcrumbs = document.getElementById('breadcrumbs');

    if (burgerIcon && mobileMenuItems) {
        // Toggle mobile menu open/close
        burgerIcon.addEventListener('click', function () {
            burgerIcon.classList.toggle('open');
            mobileMenuItems.classList.toggle('open');
        });

        // Close mobile menu when a link is clicked
        mobileMenuItems.querySelectorAll('.listItem').forEach(item => {
            item.addEventListener('click', function () {
                burgerIcon.classList.remove('open');
                mobileMenuItems.classList.remove('open');
            });
        });
    } else {
        console.error('Burger icon or mobile menu items not found');
    }

    // Attach click event listeners to each navigation link
    document.querySelectorAll('.listItem').forEach(item => {
        item.addEventListener('click', function (e) {
            e.preventDefault();  // Stop the link from triggering a page reload
            const contentUrl = this.getAttribute('href');
            fetchContent(contentUrl, mainContent);

            // Close the mobile menu if open
            if (mobileMenuItems.classList.contains('open')) {
                mobileMenuItems.classList.remove('open');
                burgerIcon.classList.remove('open');
            }
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

    // General initialization for all pages
    initializeGeneralData();
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
            updateBreadcrumbs(url); // Update breadcrumbs
        })
        .catch(error => console.error('Error loading the content:', error));
}


// Initialize page-specific elements and data
function initializePage(url, mainContent) {
    if (url.includes('/compare')) {
        initializeComparePage();
    }

    if (url.includes('/players')) {
        initializePlayerPage();
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

// Initialize page-specific elements and data
function initializePage(url, mainContent) {
    if (url.includes('/compare')) {
        initializeComparePage();
    }

    if (url.includes('/players')) {
        initializePlayerPage();
    }

    // Add more conditions for other pages as needed
}

// Placeholder for initializePlayerPage function
function initializePlayerPage() {
    console.log('Player page initialized');
}

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
            updateBreadcrumbs(url); // Update breadcrumbs
        })
        .catch(error => console.error('Error loading the content:', error));
}

// Update breadcrumbs based on URL
function updateBreadcrumbs(url) {
    const breadcrumbs = document.getElementById('breadcrumbs');
    let breadcrumbText = '';

    if (url.includes('/compare')) {
        breadcrumbText = 'Compare';
    } else if (url.includes('/players') || url.includes('/player')) {
        breadcrumbText = 'Player';
    } else if (url.includes('/team')) {
        breadcrumbText = 'Team';
    } else {
        breadcrumbText = 'Home';
    }

    if (breadcrumbs) {
        breadcrumbs.innerHTML = `<span>${breadcrumbText}</span>`;
    } else {
        console.error('Breadcrumb element not found');
    }
}