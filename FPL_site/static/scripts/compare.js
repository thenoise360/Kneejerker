import { trackComparison } from './analytics.js';

// DOMContentLoaded event handler
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
    3: '/static/content/Tshirts/sleeves-red-white-football-shirt-svgrepo-com.svg', // Arsenal
    7: '/static/content/Tshirts/sleeves-maroon-skyblue-football-shirt-svgrepo-com.svg', // Aston Villa
    91: '/static/content/Tshirts/stripes-red-black-football-shirt-svgrepo-com.svg', // Bournemouth
    94: '/static/content/Tshirts/stripes-white-red-football-shirt-svgrepo-com.svg', // Brentford
    36: '/static/content/Tshirts/stripes-white-blue-football-shirt-svgrepo-com.svg', // Brighton
    90: '/static/content/Tshirts/sleeves-maroon-skyblue-football-shirt-svgrepo-com.svg', // Burnley
    8: '/static/content/Tshirts/plain-blue-football-shirt-svgrepo-com.svg', // Chelsea
    31: '/static/content/Tshirts/halves-red-blue-football-shirt-svgrepo-com.svg', // Crystal Palace
    11: '/static/content/Tshirts/plain-navy-football-shirt-svgrepo-com.svg', // Everton
    54: '/static/content/Tshirts/plain-white-football-shirt-svgrepo-com.svg', // Fulham
    40: '/static/content/Tshirts/sleeves-blue-white-football-shirt-svgrepo-com.svg', // Ipswich Town
    2: '/static/content/Tshirts/plain-white-football-shirt-svgrepo-com.svg', // Leeds
    13: '/static/content/Tshirts/plain-navy-football-shirt-svgrepo-com.svg', // Leicester
    14: '/static/content/Tshirts/plain-red-football-shirt-svgrepo-com.svg', // Liverpool
    102: '/static/content/Tshirts/vertical-orange-black-football-shirt-svgrepo-com.svg', // Luton
    43: '/static/content/Tshirts/plain-skyblue-football-shirt-svgrepo-com.svg', // Man City
    1: '/static/content/Tshirts/plain-red-football-shirt-svgrepo-com.svg', // Man Utd
    4: '/static/content/Tshirts/stripes-white-black-football-shirt-svgrepo-com.svg', // Newcastle
    17: '/static/content/Tshirts/plain-red-football-shirt-svgrepo-com.svg', // Nottingham Forest
    49: '/static/content/Tshirts/unknown-football-shirt-svgrepo-com.svg', // Sheffield Utd
    20: '/static/content/Tshirts/sash-white-red-football-shirt-svgrepo-com.svg', // Southampton
    6: '/static/content/Tshirts/plain-white-football-shirt-svgrepo-com.svg', // Spurs
    21: '/static/content/Tshirts/sleeves-maroon-skyblue-football-shirt-svgrepo-com.svg', // West Ham
    39: '/static/content/Tshirts/plain-orange-football-shirt-svgrepo-com.svg', // Wolves
    'Unknown': '/static/content/Tshirts/unknown-football-shirt-svgrepo-com.svg', // Default for unknown teams
};

function initializeComparePage() {

    Promise.all([
        fetch('/get_players').then(r => r.json()),
        fetch('/get_players_by_team').then(r => r.json()),
        fetch('/get_players_by_position').then(r => r.json()),
        fetch('/get_player_index_scores').then(r => {
            if (!r.ok) throw new Error('Failed to fetch index scores');
            return r.json();
        })
    ])
    .then(([allPlayers, playersByTeam, playersByPosition, playerIndexScores]) => {

        if (!Array.isArray(allPlayers)) {
            console.error('Expected array for allPlayers, got:', allPlayers);
            return;
        }

        // Merge index scores with player data
        allPlayers.forEach(player => {
            const indexScore = playerIndexScores.find(score => score.id === player.id);
            player.player_index_score = indexScore ? indexScore.player_score : 'TBD';
        });

        const playerData = {
            'All Players': allPlayers,
            'By Team': playersByTeam,
            'By Position': playersByPosition
        };

        console.log('playerData keys:', Object.keys(playerData));
        initializePills(playerData);

        // Flatten players for dropdowns
        const flattenedPlayersByTeam = flattenPlayersData(playersByTeam);
        const flattenedPlayersByPosition = flattenPlayersData(playersByPosition);

        // Populate the default view
        populateDropdown('player1Dropdown', allPlayers);
        populateDropdown('player2Dropdown', allPlayers);
        const defaultPill = document.querySelector('.pill[data-structure="All Players"]');
        if (defaultPill) {
            defaultPill.classList.add('active');
            defaultPill.click();
        }

        // Compare button logic
        document.getElementById('compareButton').addEventListener('click', function () {
            comparePlayers(allPlayers);
        });

        // Set up dropdowns
        setupCustomDropdown('player1Dropdown', flattenedPlayersByTeam);
        setupCustomDropdown('player2Dropdown', flattenedPlayersByTeam);
    })
    .catch(error => {
        console.error('Something went wrong loading comparison data:', error);
    });
}


// Function to initialize pills for different player structures
function initializePills(playerData) {
    console.log('initializePills function called');
    const pillContainer = document.getElementById('pillContainer');
    if (!pillContainer) {
        console.error('Pill container element not found');
        return;
    }

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

            // Reset selected state and update dropdowns
            resetDropdown('player1Dropdown');
            resetDropdown('player2Dropdown');

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

function resetDropdown(dropdownId) {
    const dropdown = document.getElementById(dropdownId);
    const selected = dropdown.querySelector('.selected');
    const options = dropdown.querySelector('.options .dropdown-content');

    // Reset selected text
    selected.textContent = 'Select an option';
    selected.dataset.id = '';
    selected.dataset.team = '';

    // Clear only the options within dropdown-content
    if (options) {
        options.innerHTML = '';
    }
}

// Add players into the dropdown
function populateDropdown(dropdownId, players) {
    console.log('populateDropdown function called for', dropdownId);
    const dropdown = document.getElementById(dropdownId);
    const dropdownContent = dropdown.querySelector('.options .dropdown-content');
    if (!dropdownContent) {
        console.error(`Dropdown content element not found for ${dropdownId}`);
        return;
    }
    dropdownContent.innerHTML = players.map(player => `
        <div class="option" data-id="${player.id}" data-team="${player.team}">${player.full_name}</div>
    `).join('');

    setupCustomDropdown(dropdownId, players);
}

function flattenPlayersData(playersByEntity) {
    const flattenedPlayers = [];
    for (const entity in playersByEntity) {
        if (playersByEntity.hasOwnProperty(entity)) {
            for (const player in playersByEntity[entity]) {
                if (playersByEntity[entity].hasOwnProperty(player)) {
                    flattenedPlayers.push(playersByEntity[entity][player]);
                }
            }
        }
    }
    return flattenedPlayers;
}

// Function to populate custom dropdown with categories (teams or positions)
function populateDropdownWithCategories(dropdownId, players) {
    console.log('populateDropdownWithCategories function called for', dropdownId);
    const dropdown = document.getElementById(dropdownId);
    const dropdownContent = dropdown.querySelector('.options .dropdown-content');
    if (!dropdownContent) {
        console.error(`Dropdown content element not found for ${dropdownId}`);
        return;
    }
    dropdownContent.innerHTML = Object.keys(players).map(category => `
        <div class="option" data-category="${category}">${category}</div>
    `).join('');

    setupTwoLayerDropdown(dropdownId, players);
}

function setupCustomDropdown(dropdownId, players) {
    console.log('setupCustomDropdown function called for', dropdownId);
    const dropdown = document.getElementById(dropdownId);
    const selected = dropdown.querySelector('.selected');
    const options = dropdown.querySelector('.options');
    let isDropdownOpen = false;

    if (!selected || !options) {
        console.error(`Dropdown elements not found for ${dropdownId}`);
        return;
    }

    selected.addEventListener('click', function (e) {
        e.stopPropagation();
        toggleDropdown(dropdown, !isDropdownOpen);
        isDropdownOpen = !isDropdownOpen;
    });

    options.addEventListener('click', function (e) {
        e.stopPropagation();
        const option = e.target.closest('.option'); // Ensure we get the correct element
        if (option && option.dataset.id) {
            selected.textContent = option.textContent;
            selected.dataset.id = option.dataset.id;
            selected.dataset.team = option.dataset.team;
            toggleDropdown(dropdown, false);
            isDropdownOpen = false;
        }
    });

    if (!options.querySelector('.search-container')) {
        const searchContainer = document.createElement('div');
        searchContainer.classList.add('search-container');
        searchContainer.innerHTML = `
            <span class="material-icons search-icon">search</span>
            <input type="text" class="search-input" placeholder="Search...">
        `;
        options.prepend(searchContainer);

        const searchInput = searchContainer.querySelector('.search-input');
        searchInput.addEventListener('input', function (e) {
            e.stopPropagation();
            const searchTerm = this.value.toLowerCase();
            const items = options.querySelectorAll('.option');
            items.forEach(item => {
                const text = item.textContent.toLowerCase();
                item.style.display = text.includes(searchTerm) ? '' : 'none';
            });
        });
    }

    document.addEventListener('click', function (e) {
        if (!dropdown.contains(e.target)) {
            toggleDropdown(dropdown, false);
            isDropdownOpen = false;
        }
    });

    // Populate dropdown with player options
    const dropdownContent = options.querySelector('.dropdown-content');
    if (!dropdownContent) {
        const newDropdownContent = document.createElement('div');
        newDropdownContent.classList.add('dropdown-content');
        options.appendChild(newDropdownContent);
    }

    options.querySelector('.dropdown-content').innerHTML = players.map(player => `
        <div class="option" data-id="${player.id}" data-team="${player.team}">${player.full_name}</div>
    `).join('');
}

function setupTwoLayerDropdown(dropdownId, players) {
    console.log('setupTwoLayerDropdown function called for', dropdownId);
    const dropdown = document.getElementById(dropdownId);
    const selected = dropdown.querySelector('.selected');
    const options = dropdown.querySelector('.options');
    const searchInput = dropdown.querySelector('.search-input');
    let isDropdownOpen = false;

    if (!selected || !options || !searchInput) {
        console.error(`Dropdown elements not found for ${dropdownId}`);
        return;
    }

    selected.addEventListener('click', function (e) {
        e.stopPropagation();
        toggleDropdown(dropdown, !isDropdownOpen);
        isDropdownOpen = !isDropdownOpen;
    });

    options.addEventListener('click', function (e) {
        e.stopPropagation();
        if (e.target.classList.contains('option')) {
            const category = e.target.dataset.category;
            if (category) {
                console.log('Option selected in', dropdownId, 'category:', category);
                showCategoryItems(dropdownId, category, players[category]);
            } else {
                selected.textContent = e.target.textContent;
                selected.dataset.id = e.target.dataset.id;
                selected.dataset.team = e.target.dataset.team;
                toggleDropdown(dropdown, false);
                isDropdownOpen = false;
            }
        }
    });

    searchInput.addEventListener('input', function (e) {
        e.stopPropagation();
        const searchTerm = this.value.toLowerCase();
        const items = options.querySelectorAll('.option');
        items.forEach(item => {
            const text = item.textContent.toLowerCase();
            item.style.display = text.includes(searchTerm) ? '' : 'none';
        });
    });

    document.addEventListener('click', function (e) {
        if (!dropdown.contains(e.target)) {
            toggleDropdown(dropdown, false);
            isDropdownOpen = false;
        }
    });
}

function toggleDropdown(dropdown, open) {
    if (open) {
        console.log('Dropdown is closed, adding "open" class');
        document.querySelectorAll('.custom-dropdown').forEach(dd => dd.classList.remove('open'));
        dropdown.classList.add('open');
    } else {
        console.log('Dropdown is open, removing "open" class');
        dropdown.classList.remove('open');
    }
}

function showCategoryItems(dropdownId, category, items) {
    console.log('showCategoryItems function called for', dropdownId, 'and category', category);
    const dropdown = document.getElementById(dropdownId);
    const options = dropdown.querySelector('.options');
    const searchBarHtml = `
        <div class="search-container">
            <span class="material-icons search-icon">search</span>
            <input type="text" class="search-input" placeholder="Search...">
        </div>
    `;
    const firstLayerHtml = options.innerHTML.replace(searchBarHtml, ''); // Remove the search bar HTML from the first layer

    if (!items) {
        console.error(`No items found for category ${category}`);
        return;
    }

    options.innerHTML = `
        <div class="back-button-container" style="position: sticky; top: 0; background-color: white; z-index: 1;">
            <span class="material-icons back-icon">chevron_left</span>
            <div class="back-button">Back</div>
            <span>//</span>
            <span class="category-title">${category}</span>
        </div>
        ${searchBarHtml}
        <div class="second-layer">
            ${Object.entries(items).map(([playerName, playerData]) => `
                <div class="option" data-id="${playerData.id}" data-team="${playerData.team}">${playerData.full_name}</div>
            `).join('')}
        </div>
    `;

    const backButton = dropdown.querySelector('.back-button');
    backButton.addEventListener('click', function () {
        options.innerHTML = `${searchBarHtml}${firstLayerHtml}`;
        initializeDropdown(dropdownId, { category: items }); // Re-initialize the first layer correctly
    });

    const searchInput = dropdown.querySelector('.search-input');
    searchInput.addEventListener('input', function () {
        const searchTerm = this.value.toLowerCase();
        const items = options.querySelectorAll('.second-layer .option');
        items.forEach(item => {
            const text = item.textContent.toLowerCase();
            item.style.display = text.includes(searchTerm) ? '' : 'none';
        });
    });

    options.addEventListener('click', function (e) {
        const option = e.target.closest('.option'); // Ensure we get the correct element
        if (option && option.dataset.id) {
            const selected = dropdown.querySelector('.selected');
            selected.textContent = option.textContent;
            selected.dataset.id = option.dataset.id;
            selected.dataset.team = option.dataset.team;
            toggleDropdown(dropdown, false); // Close the dropdown after selection
        }
    });
}

function comparePlayers(allPlayers) {
    const player1Dropdown = document.querySelector('#player1Dropdown .selected');
    const player2Dropdown = document.querySelector('#player2Dropdown .selected');

    const id1 = player1Dropdown.dataset.id;
    const id2 = player2Dropdown.dataset.id;

    if (!id1 || !id2) {
        console.error('Player IDs not found');
        return;
    }

    const player1 = allPlayers.find(player => player.id == id1);
    const player2 = allPlayers.find(player => player.id == id2);

    if (!player1 || !player2) {
        console.error('Players not found:', id1, id2);
        return;
    }

    const team1 = player1.team;
    const team2 = player2.team;

    console.log('Comparing players:', player1, player2); // Updated log

    trackComparison(id1, id2, player1.full_name, player2.full_name);

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
    const playerSummary = document.getElementById('playerSummary');

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

        playerSummary.innerHTML = playerComparisonCard
        comparisonResult.innerHTML = comparisonCards;

        // Hide controls and show edit icon
        toggleControls(false);
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
            <div id="average-score">Average: 22</div>
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
    if (typeof text === 'string') { // Corrected here
        const result = text.replace(/_/g, ' ');
        return result.charAt(0).toUpperCase() + result.slice(1).toLowerCase();
    }
    return text;
}

// Function to toggle the visibility of the controls and edit icon
function toggleControls(showControls) {
    const controlsContainer = document.querySelector('.controls-container');
    const editIcon = document.querySelector('.edit-icon');
    const editButton = document.querySelector('.edit');

    if (showControls) {
        controlsContainer.style.display = 'block';
        editIcon.style.display = 'none';
        editButton.style.display = 'none';
    } else {
        controlsContainer.style.display = 'none';
        editIcon.style.display = 'block';
        editButton.style.display = 'flex';
    }
}

// Initialize general data on initial site load
function initializeGeneralData() {
    console.log('General data initialized');
}

// Modify the event listener for the edit button
document.querySelector('.edit').addEventListener('click', function () {
    toggleControls(true);
    initializeComparePage(); // Reinitialize the compare page
});


// Call initializeGeneralData
initializeGeneralData();