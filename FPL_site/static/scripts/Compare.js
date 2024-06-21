document.addEventListener('DOMContentLoaded', function () {
    console.log('DOMContentLoaded event triggered');

    if (window.location.pathname.includes('/compare')) {
        console.log('Initializing Compare Page');
        initializeComparePage();
    }
});

// Initialize the Compare page
function initializeComparePage() {
    console.log('initializeComparePage function called');

    // Fetch and initialize pills
    Promise.all([
        fetch('/get_players').then(response => response.json()),
        fetch('/get_players_by_team').then(response => response.json()),
        fetch('/get_players_by_position').then(response => response.json())
    ]).then(([allPlayers, playersByTeam, playersByPosition]) => {
        const playerData = {
            'All Players': allPlayers,
            'By Team': playersByTeam,
            'By Position': playersByPosition
        };
        initializePills(playerData);

        // Make "All Players" pill active by default and populate the dropdowns
        populateDropdown('player1Dropdown', allPlayers);
        populateDropdown('player2Dropdown', allPlayers);
        document.querySelector('.pill[data-structure="All Players"]').classList.add('active');
        document.querySelector('.pill[data-structure="All Players"]').click();

        // Attach event listener to the compare button
        document.getElementById('compareButton').addEventListener('click', function () {
            comparePlayers();
        });

        // Add event listeners for custom dropdowns
        setupCustomDropdown('player1Dropdown');
        setupCustomDropdown('player2Dropdown');
    }).catch(error => console.error('Error loading player data:', error));
}

// Function to initialize pills for different player structures
function initializePills(playerData) {
    console.log('initializePills function called');
    const pillContainer = document.getElementById('pillContainer');
    pillContainer.innerHTML = Object.keys(playerData).map(key => `
        <div class="pill" data-structure="${key}">${key}</div>
    `).join('');

    document.querySelectorAll('.pill').forEach(pill => {
        pill.addEventListener('click', function () {
            console.log('Pill clicked:', this.dataset.structure);
            const structure = this.dataset.structure;
            const players = playerData[structure];

            // Remove 'active' class from all pills
            document.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
            // Add 'active' class to the clicked pill
            this.classList.add('active');

            if (structure === 'All Players') {
                populateDropdown('player1Dropdown', players);
                populateDropdown('player2Dropdown', players);
            } else {
                console.log(`Loading data for ${structure}:`, players);
                populateDropdownWithCategories('player1Dropdown', players);
                populateDropdownWithCategories('player2Dropdown', players);
            }
        });
    });
}

// Function to populate custom dropdown for "All Players"
function populateDropdown(dropdownId, players) {
    console.log('populateDropdown function called for', dropdownId);
    const dropdown = document.getElementById(dropdownId).querySelector('.dropdown-content');
    if (!dropdown) {
        console.error(`Dropdown content element not found for ${dropdownId}`);
        return;
    }
    dropdown.innerHTML = players.map(player => `
        <div class="option" data-id="${player.id}">${player.full_name}</div>
    `).join('');

    setupCustomDropdown(dropdownId);
}

// Function to populate custom dropdown with categories (teams or positions)
function populateDropdownWithCategories(dropdownId, players) {
    console.log('populateDropdownWithCategories function called for', dropdownId);
    const dropdown = document.getElementById(dropdownId).querySelector('.dropdown-content');
    if (!dropdown) {
        console.error(`Dropdown content element not found for ${dropdownId}`);
        return;
    }
    dropdown.innerHTML = Object.keys(players).map(category => `
        <div class="option" data-category="${category}">${category}</div>
    `).join('');

    setupTwoLayerDropdown(dropdownId, players);
}

// Function to set up custom dropdown behavior
function setupCustomDropdown(dropdownId) {
    console.log('setupCustomDropdown function called for', dropdownId);
    const dropdown = document.getElementById(dropdownId);
    const selected = dropdown.querySelector('.selected');
    const options = dropdown.querySelector('.options');
    const searchInput = dropdown.querySelector('.search-input');

    if (!selected || !options) {
        console.error(`Dropdown elements not found for ${dropdownId}`);
        return;
    }

    dropdown.addEventListener('click', function (e) {
        if (e.target === selected) {
            dropdown.classList.toggle('open');
        }
    });

    options.addEventListener('click', function (e) {
        if (e.target.classList.contains('option')) {
            selected.textContent = e.target.textContent;
            selected.dataset.id = e.target.dataset.id;
            dropdown.classList.remove('open'); // Close the dropdown
        }
    });
    searchInput.addEventListener('input', function () {
        const searchTerm = this.value.toLowerCase();
        const items = dropdown.querySelectorAll('.option');
        items.forEach(item => {
            const text = item.textContent.toLowerCase();
            item.style.display = text.includes(searchTerm) ? '' : 'none';
        });
    });

    document.addEventListener('click', function (e) {
        if (!dropdown.contains(e.target) && !e.target.classList.contains('search-input')) {
            dropdown.classList.remove('open');
        }
    });
}

// Function to set up two-layer dropdown behavior
function setupTwoLayerDropdown(dropdownId, players) {
    console.log('setupTwoLayerDropdown function called for', dropdownId);
    const dropdown = document.getElementById(dropdownId);
    const selected = dropdown.querySelector('.selected');
    const options = dropdown.querySelector('.options');
    const searchInput = dropdown.querySelector('.search-input');

    if (!selected || !options || !searchInput) {
        console.error(`Dropdown elements not found for ${dropdownId}`);
        return;
    }

    dropdown.addEventListener('click', function (e) {
        if (!e.target.classList.contains('search-input')) {
            if (e.target.classList.contains('option')) {
                const category = e.target.dataset.category;
                console.log('Option clicked:', category);
                showSecondLayer(dropdownId, category, players[category]);
            } else {
                dropdown.classList.toggle('open');
            }
        }
    });

    searchInput.addEventListener('input', function () {
        const searchTerm = this.value.toLowerCase();
        const items = dropdown.querySelectorAll('.second-layer .option');
        items.forEach(item => {
            const text = item.textContent.toLowerCase();
            item.style.display = text.includes(searchTerm) ? '' : 'none';
        });
    });

    document.addEventListener('click', function (e) {
        if (!dropdown.contains(e.target) && !e.target.classList.contains('search-input')) {
            dropdown.classList.remove('open');
        }
    });
}


// Function to show the second layer of the dropdown
function showSecondLayer(dropdownId, category, items) {
    console.log('showSecondLayer function called for', dropdownId, 'and category', category);
    const dropdown = document.getElementById(dropdownId);
    const options = dropdown.querySelector('.options');
    if (!options) {
        console.error(`Dropdown options element not found for ${dropdownId}`);
        return;
    }
    options.innerHTML = `
        <div class="back-button">Back</div>
        <div class="search-bar">
            <span class="material-icons">search</span>
            <input type="text" class="search-input" placeholder="Search...">
        </div>
        <div class="second-layer">
            <div class="category-title">${category}</div>
            ${Object.entries(items).map(([name, id]) => `
                <div class="option" data-id="${id}">${name}</div>
            `).join('')}
        </div>
    `;

    dropdown.querySelector('.back-button').addEventListener('click', function () {
        populateDropdownWithCategories(dropdownId, items);  // Repopulate the first layer
    });

    options.addEventListener('click', function (e) {
        if (e.target.classList.contains('option')) {
            const selected = dropdown.querySelector('.selected');
            selected.textContent = e.target.textContent;
            selected.dataset.id = e.target.dataset.id;
            dropdown.classList.remove('open'); // Close the dropdown after selection
        }
    });

    const searchInput = options.querySelector('.search-input');
    searchInput.addEventListener('input', function () {
        const searchTerm = this.value.toLowerCase();
        const items = options.querySelectorAll('.second-layer .option');
        items.forEach(item => {
            const text = item.textContent.toLowerCase();
            item.style.display = text.includes(searchTerm) ? '' : 'none';
        });
    });
}


// Function for user action - Compare Players
function comparePlayers() {
    const id1 = document.querySelector('#player1Dropdown .selected').dataset.id;
    const id2 = document.querySelector('#player2Dropdown .selected').dataset.id;
    console.log('Comparing players:', id1, id2);
    fetch(`/compare_players?id1=${id1}&id2=${id2}`)
        .then(response => response.json())
        .then(data => {
            displayComparisonData(data);
        })
        .catch(error => console.error('Error comparing players:', error));
}

// Display comparison data in the comparison result
function displayComparisonData(data) {
    const player1 = data[0];
    const player2 = data[1];
    console.log('Comparison data:', data);

    const comparisonResult = document.getElementById('comparisonResult');
    comparisonResult.innerHTML = createComparisonCards(player1, player2);
}

// Function to create comparison cards
function createComparisonCards(player1, player2) {
    const categories = Object.keys(player1);

    return categories.map(category => `
        <div class="card">
            <h2>${formatText(category)}</h2>
            ${createMetricRows(player1[category], player2[category])}
        </div>
    `).join('');
}

// Function to create metric rows
function createMetricRows(player1Metrics, player2Metrics) {
    return Object.keys(player1Metrics).map(metric => `
        <div class="metric-row">
            <div class="value-left ${player1Metrics[metric] > player2Metrics[metric] ? 'highlight' : ''}">${player1Metrics[metric]}</div>
            <div class="metric">${formatText(metric)}</div>
            <div class="value-right ${player2Metrics[metric] > player1Metrics[metric] ? 'highlight' : ''}">${player2Metrics[metric]}</div>
        </div>
    `).join('');
}

// Function to format text to sentence case and replace underscores with spaces
function formatText(text) {
    const result = text.replace(/_/g, ' ');
    return result.charAt(0).toUpperCase() + result.slice(1).toLowerCase();
}

// Initialize general data on initial site load
function initializeGeneralData() {
    console.log('General data initialized');
}

// Call initializeGeneralData
initializeGeneralData();
