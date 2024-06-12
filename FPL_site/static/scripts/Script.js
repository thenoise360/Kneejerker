document.addEventListener('DOMContentLoaded', function () {
    console.log('Script loaded');

    const burgerIcon = document.getElementById('burgerIcon');
    const mobileMenuItems = document.getElementById('mobileMenuItems');
    const mainContent = document.querySelector('main');

    // Toggle mobile menu open/close
    burgerIcon.addEventListener('click', function () {
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
}

// Initialize the Compare page
function initializeComparePage() {
    // Fetch player data
    fetch('/get_players')
        .then(response => response.json())
        .then(players => {
            // Populate both dropdowns with player data
            populateDropdown('player1Dropdown', players);
            populateDropdown('player2Dropdown', players);

            // Attach event listener to the compare button
            document.getElementById('compareButton').addEventListener('click', function () {
                comparePlayers();
            });

            // Add event listeners for custom dropdowns
            setupCustomDropdown('player1Dropdown');
            setupCustomDropdown('player2Dropdown');
        })
        .catch(error => console.error('Error loading player data:', error));
}

// Function to populate custom dropdown
function populateDropdown(dropdownId, players) {
    const dropdown = document.getElementById(dropdownId).querySelector('.options');
    dropdown.innerHTML = players.map(player => `
        <div class="option" data-id="${player.id}">${player.full_name}</div>
    `).join('');
}

// Function to set up custom dropdown behavior
function setupCustomDropdown(dropdownId) {
    const dropdown = document.getElementById(dropdownId);
    const selected = dropdown.querySelector('.selected');
    const options = dropdown.querySelector('.options');

    dropdown.addEventListener('click', function () {
        dropdown.classList.toggle('open');
    });

    options.addEventListener('click', function (e) {
        if (e.target.classList.contains('option')) {
            selected.textContent = e.target.textContent;
            selected.dataset.id = e.target.dataset.id;
            dropdown.classList.remove('open');
        }
    });

    document.addEventListener('click', function (e) {
        if (!dropdown.contains(e.target)) {
            dropdown.classList.remove('open');
        }
    });
}

// Function for user action - Compare Players
function comparePlayers() {
    const id1 = document.querySelector('#player1Dropdown .selected').dataset.id;
    const id2 = document.querySelector('#player2Dropdown .selected').dataset.id;
    fetch(`/compare_players?id1=${id1}&id2=${id2}`)
        .then(response => response.json())
        .then(data => {
            displayPlayerData(data[0], 'player1Details');
            displayPlayerData(data[1], 'player2Details');
        })
        .catch(error => console.error('Error comparing players:', error));
}

// Display player data in the comparison result
function displayPlayerData(player, elementId) {
    const container = document.getElementById(elementId);
    if (player) {
        container.innerHTML = `<h4>${player.first_name} ${player.second_name}</h4>
            <p>Points per Game: ${player.points_per_game}</p>
            <p>Goals Scored: ${player.goals_scored}</p>
            <p>Assists: ${player.assists}</p>`;
    } else {
        container.innerHTML = "<p>No data available for this player.</p>";
    }
}

// Initialize general data on initial site load
initializeGeneralData();
