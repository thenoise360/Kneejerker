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
            })
            .catch(error => console.error('Error loading the content:', error));
    }

    // Function to initialize page-specific elements and data
    function initializePage(url, mainContent) {
        if (url.includes('/radar')) {
            if (typeof initializeRadarPage === 'function') {
                initializeRadarPage();
            }
        }

        if (url === '/' || url.includes('/this-week') || url.endsWith('.com/') || url.endsWith('.com')) {
            if (typeof initializeHomePage === 'function') {
                initializeHomePage();
            }
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


    // Renders a live "Deadline in Xd Yh Zm" countdown into `span`, ticking every minute
    function startDeadlineCountdown(span, deadlineDate) {
        const render = () => {
            const diff = deadlineDate - new Date();
            if (diff <= 0) {
                span.textContent = 'Deadline passed';
                return;
            }
            const days = Math.floor(diff / (1000 * 60 * 60 * 24));
            const hours = Math.floor((diff / (1000 * 60 * 60)) % 24);
            const mins = Math.floor((diff / (1000 * 60)) % 60);
            span.textContent = `Deadline in ${days}d ${hours}h ${mins}m`;
        };
        render();
        setInterval(render, 60000);
    }

    // Function to update header with GW and deadline
    function updateHeaderInfo() {
        fetch('/api/header-info')
            .then(response => response.json())
            .then(data => {
                if (data.current_gw) {
                    const gwPill = document.getElementById('current-gw-pill');
                    if (gwPill) gwPill.textContent = `GW ${data.current_gw}`;
                }
                
                if (data.deadline) {
                    const deadlineSpan = document.getElementById('deadline');
                    if (deadlineSpan) {
                        startDeadlineCountdown(deadlineSpan, new Date(data.deadline));
                    }
                }
            })
            .catch(error => console.error('Error fetching header info:', error));
    }

    updateHeaderInfo();

    // General initialization on page load
    initializeGeneralData();
});
