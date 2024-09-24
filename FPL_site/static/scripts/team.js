document.getElementById('submit-btn').addEventListener('click', function () {
    const sliders = document.querySelectorAll('.form-range.slider');
    const sliderValues = Array.from(sliders).map(slider => slider.value);

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

            // Create rows for each position
            const gkRow = document.createElement('div');
            gkRow.classList.add('players-row');

            const defRow = document.createElement('div');
            defRow.classList.add('players-row');

            const midRow = document.createElement('div');
            midRow.classList.add('players-row');

            const attRow = document.createElement('div');
            attRow.classList.add('players-row');

            // Iterate through the returned team and distribute players by position
            data.team.forEach(player => {
                const playerElement = document.createElement('div');
                playerElement.classList.add('player-card');

                // Create the player price element
                const priceElement = document.createElement('div');
                priceElement.classList.add('player-price');
                priceElement.textContent = `£${player.now_cost.toFixed(1)}M`;

                // Create the player shirt image
                const shirtElement = document.createElement('img');
                shirtElement.classList.add('player-shirt');
                const shirtSrc = teamTshirts[player.team_code] || teamTshirts['Unknown'];
                shirtElement.src = shirtSrc;

                // Create the player info (name + projected points)
                const playerNameElement = document.createElement('div');
                playerNameElement.classList.add('player-info');
                playerNameElement.textContent = `${player.web_name}`;
                
                const performanceElement = document.createElement('div');
                performanceElement.classList.add('player-info');
                performanceElement.textContent = `${player.predicted_performance.toFixed(2)} pts`;

                // Append all elements to the player card
                playerElement.appendChild(priceElement);
                playerElement.appendChild(shirtElement);
                playerElement.appendChild(playerNameElement);
                playerElement.appendChild(performanceElement);

                // Add the player card to the correct row based on element_type
                if (player.element_type === 1) {
                    gkRow.appendChild(playerElement);  // Goalkeeper
                } else if (player.element_type === 2) {
                    defRow.appendChild(playerElement);  // Defenders
                } else if (player.element_type === 3) {
                    midRow.appendChild(playerElement);  // Midfielders
                } else if (player.element_type === 4) {
                    attRow.appendChild(playerElement);  // Attackers
                }
            });

            // Append the rows to the pitch container
            pitchContainer.appendChild(gkRow);
            pitchContainer.appendChild(defRow);
            pitchContainer.appendChild(midRow);
            pitchContainer.appendChild(attRow);

            // Hide the loading overlay and show the team
            document.getElementById('loading-overlay').style.display = 'none';
            document.getElementById('team-locations').style.display = 'block';
        } else {
            // Handle error case
            document.getElementById('loading-text').textContent = 'An error occurred, please try again.';
        }
    })
    .catch(error => {
        // Handle server errors or network errors
        document.getElementById('loading-text').textContent = 'Server error. Please refresh.';
    });
});
