document.addEventListener('DOMContentLoaded', function () {
    console.log('DOMContentLoaded event triggered');

    if (window.location.pathname.includes('/compare')) {
        console.log('Initializing Compare Page');
        initializeComparePage();
    }
});

// Utility function to format numbers with commas as thousand separators
function formatNumberWithCommas(number) {
    return number.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}


// Team to T-shirt image mapping
const teamTshirts = {
    1: '/static/content/Tshirts/sleeves-red-white-football-shirt-svgrepo-com.svg', // Arsenal
    2: '/static/content/Tshirts/sleeves-maroon-skyblue-football-shirt-svgrepo-com.svg', // Aston Villa
    3: '/static/content/Tshirts/vertical-black-red-football-shirt-svgrepo-com.svg', // Bournemouth
    4: '/static/content/Tshirts/stripes-white-red-football-shirt-svgrepo-com', // Brentford
    5: '/static/content/Tshirts/stripes-white-blue-football-shirt-svgrepo-com.svg', // Brighton
    6: '/static/content/Tshirts/sleeves-maroon-skyblue-football-shirt-svgrepo-com.svg', // Burnley
    7: '/static/content/Tshirts/plain-blue-football-shirt-svgrepo-com.svg', // Chelsea
    8: '/static/content/Tshirts/halves-red-blue-football-shirt-svgrepo-com.svg', // Crystal Palace
    9: '/static/content/Tshirts/plain-navy-football-shirt-svgrepo-com.svg', // Everton
    10: '/static/content/Tshirts/plain-white-football-shirt-svgrepo-com.svg', // Fulham
    99: '/static/content/Tshirts/sleeves-blue-white-football-shirt-svgrepo-com.svg', // Ipswich Town
    99: '/static/content/Tshirts/plain-white-football-shirt-svgrepo-com.svg', // Leeds
    99: '/static/content/Tshirts/plain-navy-football-shirt-svgrepo-com.svg', // Leicester
    11: '/static/content/Tshirts/plain-red-football-shirt-svgrepo-com.svg', // Liverpool
    12: '/static/content/Tshirts/vertical-orange-black-football-shirt-svgrepo-com.svg', // Luton
    13: '/static/content/Tshirts/plain-skyblue-football-shirt-svgrepo-com.svg', // Man City
    14: '/static/content/Tshirts/plain-red-football-shirt-svgrepo-com.svg', // Man Utd
    15: '/static/content/Tshirts/stripes-white-black-football-shirt-svgrepo-com.svg', // Newcastle
    16: '/static/content/Tshirts/plain-red-football-shirt-svgrepo-com.svg', // Nottingham Forest
    17: '/static/content/Tshirts/unknown-football-shirt-svgrepo-com.svg', // Sheffield Utd
    99: '/static/content/Tshirts/sash-white-red-football-shirt-svgrepo-com.svg', // Southampton
    18: '/static/content/Tshirts/plain-white-football-shirt-svgrepo-com.svg', // Spurs
    19: '/static/content/Tshirts/sleeves-maroon-skyblue-football-shirt-svgrepo-com.svg', // West Ham
    20: '/static/content/Tshirts/plain-orange-football-shirt-svgrepo-com.svg', // Wolves
    'Unknown': '/static/content/Tshirts/unknown-football-shirt-svgrepo-com.svg', // Default for unknown teams
};

// Initialize the Compare page
function initializeComparePage() {
    console.log('initializeComparePage function called');

    // Fetch and initialize pills
    Promise.all([
        fetch('/get_players').then(response => response.json()),
        fetch('/get_players_by_team').then(response => response.json()),
        fetch('/get_players_by_position').then(response => response.json()),
        fetch('/get_player_index_scores').then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
    ]).then(([allPlayers, playersByTeam, playersByPosition, playerIndexScores]) => {
        // Merge index scores with player data
        allPlayers.forEach(player => {
            const indexScore = playerIndexScores.find(score => score.id === player.id);
            if (indexScore) {
                player.player_index_score = indexScore.index;
            } else {
                player.player_index_score = 'TBD';
            }
        });

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
            comparePlayers(allPlayers);
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
        <div class="option" data-id="${player.id}" data-team="${player.team}">${player.full_name}</div>
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
            selected.dataset.team = e.target.dataset.team;
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
            ${Object.entries(items).map(([name, player]) => `
                <div class="option" data-id="${player.id}" data-team="${player.team}">${name}</div>
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
            selected.dataset.team = e.target.dataset.team;
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
function comparePlayers(allPlayers) {
    const player1Dropdown = document.querySelector('#player1Dropdown .selected');
    const player2Dropdown = document.querySelector('#player2Dropdown .selected');

    const id1 = player1Dropdown.dataset.id;
    const id2 = player2Dropdown.dataset.id;

    const player1 = allPlayers.find(player => player.id == id1);
    const player2 = allPlayers.find(player => player.id == id2);

    const team1 = player1.team;
    const team2 = player2.team;

    console.log('Comparing players:', id1, id2);
    fetch(`/compare_players?id1=${id1}&id2=${id2}`)
        .then(response => response.json())
        .then(data => {
            displayComparisonData(data, player1, player2, team1, team2);
        })
        .catch(error => console.error('Error comparing players:', error));
}

// Function to display comparison data in the comparison result
function displayComparisonData(data, player1, player2, team1, team2) {
    const comparisonResult = document.getElementById('comparisonResult');

    // Fetch net transfers and then create the player comparison card
    Promise.all([
        fetch(`/get_player_net_transfers?id=${player1.id}`).then(response => response.json()),
        fetch(`/get_player_net_transfers?id=${player2.id}`).then(response => response.json())
    ]).then(([netTransfers1, netTransfers2]) => {
        player1.net_transfers = netTransfers1.net_transfers;
        player2.net_transfers = netTransfers2.net_transfers;

        // Create player comparison card
        const playerComparisonCard = createPlayerComparisonCard(player1, player2, team1, team2);
        const comparisonCards = createComparisonCards(data);

        comparisonResult.innerHTML = playerComparisonCard + comparisonCards;
    }).catch(error => console.error('Error loading net transfers:', error));
}

// Function to create player comparison card
function createPlayerComparisonCard(player1, player2, team1, team2) {
    const tshirt1 = teamTshirts[team1] || teamTshirts['Unknown'];
    const tshirt2 = teamTshirts[team2] || teamTshirts['Unknown'];

    const player1Score = formatNumberWithCommas(Math.round(player1.player_index_score));
    const player2Score = formatNumberWithCommas(Math.round(player2.player_index_score));

    const netTransfers1 = formatNumberWithCommas(player1.net_transfers || 0);
    const netTransfers2 = formatNumberWithCommas(player2.net_transfers || 0);

    return `
        <div class="comparison-card">
            <div class="player-info">
                <div class="player">
                    <img src="${tshirt1}" alt="${team1} Shirt">
                    <div class="player-name">${player1.full_name}</div>
                </div>
                <span class="spacer"></span>
                <div class="player">
                    <img src="${tshirt2}" alt="${team2} Shirt">
                    <div class="player-name">${player2.full_name}</div>
                </div>
            </div>
            <div class="player-score">
                <span class="player-score-value ${player1.player_index_score > player2.player_index_score ? 'highlight-player-score' : ''}">${player1Score}</span>
                <span class="player-score-title">Player Score</span>
                <span class="player-score-value ${player2.player_index_score > player1.player_index_score ? 'highlight-player-score' : ''}">${player2Score}</span>
            </div>
            <div class="divider"></div>
            <div class="net-transfers">
                <div class="net-transfer">
                    <div class="net-transfer-value">${netTransfers1}</div>
                    <div class="net-transfer-label">Net Transfers</div>
                </div>
                <span class="spacer"></span>
                <div class="net-transfer">
                    <div class="net-transfer-value">${netTransfers2}</div>
                    <div class="net-transfer-label">Net Transfers</div>
                </div>
            </div>
        </div>
    `;
}


// Function to create comparison cards
function createComparisonCards(data) {
    const categories = Object.keys(data[0]);

    return categories.map(category => `
        <div class="card">
            <h2>${formatText(category)}</h2>
            ${createMetricRows(data[0][category], data[1][category])}
        </div>
    `).join('');
}

// Function to create metric rows
function createMetricRows(player1Metrics, player2Metrics) {
    if (!player1Metrics || !player2Metrics) {
        console.error('Metrics data missing', player1Metrics, player2Metrics); // Debugging
        return '';
    }

    return Object.keys(player1Metrics).map(metric => `
        <div class="metric-row">
            <div class="value-left ${player1Metrics[metric] > player2Metrics[metric] ? 'highlight' : ''}">${formatNumberWithCommas(Math.round(player1Metrics[metric]) || 0)}</div>
            <div class="metric">${formatText(metric)}</div>
            <div class="value-right ${player2Metrics[metric] > player1Metrics[metric] ? 'highlight' : ''}">${formatNumberWithCommas(Math.round(player2Metrics[metric]) || 0)}</div>
        </div>
    `).join('');
}

// Function to format text to sentence case and replace underscores with spaces
function formatText(text) {
    if (typeof text === 'string') {
        const result = text.replace(/_/g, ' ');
        return result.charAt(0).toUpperCase() + result.slice(1).toLowerCase();
    }
    return text;
}

// Initialize general data on initial site load
function initializeGeneralData() {
    console.log('General data initialized');
}

// Call initializeGeneralData
initializeGeneralData();
