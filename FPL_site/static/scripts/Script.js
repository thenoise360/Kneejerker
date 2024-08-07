document.addEventListener('DOMContentLoaded', function () {
    console.log('Document loaded');

    const burgerIcon = document.getElementById('burgerIcon');
    const mobileMenuItems = document.getElementById('mobileMenuItems');
    let isMenuOpen = false; // Flag to track the state of the menu

    // Toggle mobile menu open/close
    if (burgerIcon && mobileMenuItems) {
        burgerIcon.addEventListener('click', function (e) {
            e.stopPropagation(); // Prevent click from bubbling up

            // Prevent multiple clicks
            if (isMenuOpen) {
                return;
            }
            isMenuOpen = true;

            console.log('Burger icon clicked');
            burgerIcon.classList.toggle('open');
            mobileMenuItems.classList.toggle('open');

            // Log the current state of the classes
            console.log('Burger icon classes:', burgerIcon.classList);
            console.log('Mobile menu classes:', mobileMenuItems.classList);

            // Reset the flag after a short delay
            setTimeout(() => {
                isMenuOpen = false;
            }, 300); // Adjust the delay as necessary
        });

        // Close mobile menu when a link is clicked
        mobileMenuItems.querySelectorAll('.listItem').forEach(item => {
            item.addEventListener('click', function (e) {
                e.stopPropagation(); // Prevent click from bubbling up
                console.log('Menu item clicked');
                burgerIcon.classList.remove('open');
                mobileMenuItems.classList.remove('open');
            });
        });
    } else {
        console.error('Burger icon or mobile menu items not found');
    }

    // Function to fetch and update content
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
                if (mainContent) {
                    mainContent.innerHTML = html;
                } else {
                    console.error('Main content element not found');
                }

                if (updateHistory) {
                    history.pushState({ url: url }, '', url); // Update the URL without reloading the page
                }

                initializePage(url, mainContent); // Initialize page-specific elements and data
                updateBreadcrumbs(url); // Update breadcrumbs
            })
            .catch(error => console.error('Error loading the content:', error));
    }

    // Function to initialize page-specific elements and data
    function initializePage(url, mainContent) {
        if (url.includes('/compare')) {
            initializeComparePage();
        }

        if (url.includes('/players')) {
            initializePlayerPage();
        }

        // Add more conditions for other pages as needed
    }

    // Function to general initialization for all pages
    function initializeGeneralData() {
        // Load any data that should be available on initial site load
        fetch('/get_players')
            .then(response => response.json())
            .then(players => {
                console.log(players);
            })
            .catch(error => console.error('Error loading general data:', error));

        fetch('/get_players_by_team')
            .then(response => response.json())
            .then(players => {
                console.log(players);
            })
            .catch(error => console.error('Error loading general data:', error));

        fetch('/get_players_by_position')
            .then(response => response.json())
            .then(players => {
                console.log(players);
            })
            .catch(error => console.error('Error loading general data:', error));
    }

    // Placeholder for initializePlayerPage function
    function initializePlayerPage() {
        console.log('Player page initialized');
    }

    // Function to update breadcrumbs based on URL
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

    // General initialization on page load
    initializeGeneralData();
});
