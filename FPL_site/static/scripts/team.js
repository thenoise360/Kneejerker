// Ensure the loading overlay is hidden initially
document.getElementById('loading-overlay').style.display = 'none';


document.getElementById('submit-btn').addEventListener('click', function() {
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
            // Update the "team-locations" div with the optimized team data
            const teamContainer = document.getElementById('team-locations');
            teamContainer.innerHTML = '';  // Clear previous content

            // Assuming data.team is an array of players (each player is a dictionary)
            data.team.forEach(player => {
                const playerElement = document.createElement('div');

                // Create a player string with details
                const playerInfo = `
                    ${player.first_name} ${player.second_name} - 
                    Performance: ${player.predicted_performance.toFixed(2)} points, 
                    Position: ${player.element_type}, 
                    Cost: £${player.now_cost}M, 
                    Starter: ${player.is_starter ? 'Yes' : 'No'}
                `;

                // Add player info to the element
                playerElement.textContent = playerInfo;

                // Append the player element to the teamContainer
                teamContainer.appendChild(playerElement);
            });

            // Hide the loading overlay
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

