import { trackTeamOptimization } from './analytics.js';

// Team to T-shirt image mapping
const teamTshirts = {
    3: '/static/content/Tshirts/sleeves-red-white-football-shirt-svgrepo-com.svg',
    7: '/static/content/Tshirts/sleeves-maroon-skyblue-football-shirt-svgrepo-com.svg',
    91: '/static/content/Tshirts/stripes-red-black-football-shirt-svgrepo-com.svg',
    94: '/static/content/Tshirts/stripes-white-red-football-shirt-svgrepo-com.svg',
    36: '/static/content/Tshirts/stripes-white-blue-football-shirt-svgrepo-com.svg',
    90: '/static/content/Tshirts/sleeves-maroon-skyblue-football-shirt-svgrepo-com.svg',
    8: '/static/content/Tshirts/plain-blue-football-shirt-svgrepo-com.svg',
    31: '/static/content/Tshirts/halves-red-blue-football-shirt-svgrepo-com.svg',
    11: '/static/content/Tshirts/plain-navy-football-shirt-svgrepo-com.svg',
    54: '/static/content/Tshirts/plain-white-football-shirt-svgrepo-com.svg',
    40: '/static/content/Tshirts/sleeves-blue-white-football-shirt-svgrepo-com.svg',
    2: '/static/content/Tshirts/plain-white-football-shirt-svgrepo-com.svg',
    13: '/static/content/Tshirts/plain-navy-football-shirt-svgrepo-com.svg',
    14: '/static/content/Tshirts/plain-red-football-shirt-svgrepo-com.svg',
    102: '/static/content/Tshirts/vertical-orange-black-football-shirt-svgrepo-com.svg',
    43: '/static/content/Tshirts/plain-skyblue-football-shirt-svgrepo-com.svg',
    1: '/static/content/Tshirts/plain-red-football-shirt-svgrepo-com.svg',
    4: '/static/content/Tshirts/stripes-white-black-football-shirt-svgrepo-com.svg',
    17: '/static/content/Tshirts/plain-red-football-shirt-svgrepo-com.svg',
    49: '/static/content/Tshirts/unknown-football-shirt-svgrepo-com.svg',
    20: '/static/content/Tshirts/sash-white-red-football-shirt-svgrepo-com.svg',
    6: '/static/content/Tshirts/plain-white-football-shirt-svgrepo-com.svg',
    21: '/static/content/Tshirts/sleeves-maroon-skyblue-football-shirt-svgrepo-com.svg',
    39: '/static/content/Tshirts/plain-orange-football-shirt-svgrepo-com.svg',
    'Unknown': '/static/content/Tshirts/unknown-football-shirt-svgrepo-com.svg',
};

function initializeTeamPage() {
    const submitButton = document.getElementById('submit-btn');
    if (!submitButton) {
        console.error('Submit button not found');
        return;
    }

    submitButton.addEventListener('click', function () {
        const sliders = document.querySelectorAll('.form-range.slider');
        const sliderValues = Array.from(sliders).map(slider => slider.value);
        trackTeamOptimization(sliderValues);

        // Show loading overlay
        document.getElementById('loading-overlay').style.display = 'block';
        document.getElementById('data-capture').style.display = 'none';

        // Send data to backend
        fetch('/run-team-optimization', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ sliders: sliderValues }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const pitchContainer = document.getElementById('players-container');
                pitchContainer.innerHTML = '';  // Clear previous content

                const gkRow = document.createElement('div');
                const defRow = document.createElement('div');
                const midRow = document.createElement('div');
                const attRow = document.createElement('div');
                [gkRow, defRow, midRow, attRow].forEach(row => row.classList.add('players-row'));

                data.team.forEach(player => {
                    const playerElement = document.createElement('div');
                    playerElement.classList.add('player-card');

                    const priceElement = document.createElement('div');
                    priceElement.classList.add('player-price');
                    priceElement.textContent = `£${player.now_cost.toFixed(1)}M`;

                    const shirtElement = document.createElement('img');
                    shirtElement.classList.add('player-shirt');
                    shirtElement.src = teamTshirts[player.team_code] || teamTshirts['Unknown'];

                    const playerNameElement = document.createElement('div');
                    playerNameElement.classList.add('player-info');
                    playerNameElement.textContent = `${player.web_name}`;

                    const performanceElement = document.createElement('div');
                    performanceElement.classList.add('player-info');
                    performanceElement.textContent = `${player.predicted_performance.toFixed(2)} pts`;

                    playerElement.appendChild(priceElement);
                    playerElement.appendChild(shirtElement);
                    playerElement.appendChild(playerNameElement);
                    playerElement.appendChild(performanceElement);

                    switch (player.element_type) {
                        case 1: gkRow.appendChild(playerElement); break;
                        case 2: defRow.appendChild(playerElement); break;
                        case 3: midRow.appendChild(playerElement); break;
                        case 4: attRow.appendChild(playerElement); break;
                    }
                });

                pitchContainer.appendChild(gkRow);
                pitchContainer.appendChild(defRow);
                pitchContainer.appendChild(midRow);
                pitchContainer.appendChild(attRow);

                document.getElementById('loading-overlay').style.display = 'none';
                document.getElementById('team-locations').style.display = 'block';
            } else {
                document.getElementById('loading-text').textContent = 'An error occurred, please try again.';
            }
        })
        .catch(error => {
            console.error(error);
            document.getElementById('loading-text').textContent = 'Server error. Please refresh.';
        });
    });
}

// Ensure initialization runs no matter when script loads
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeTeamPage);
} else {
    initializeTeamPage();
}
