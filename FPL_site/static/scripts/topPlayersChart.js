import { renderLineChart } from './chartUtils.js';

document.addEventListener('DOMContentLoaded', function () {
    const positionDropdown = document.getElementById('positionDropdown');
    const carouselInner = document.getElementById('carouselInner');
    const carouselIndicators = document.getElementById('carouselIndicators');

    function fetchPlayerData(position) {
        // Call your backend route: /api/top-5-players?position=X
        fetch(`/api/top-5-players?position=${position}`)
            .then(response => response.json())
            .then(data => {
                if (
                    !data ||
                    !data[position] ||
                    !data[position].players ||
                    !data[position].averageScores
                ) {
                    console.error(`Invalid data format for position: ${position}`, data);
                    return;
                }

                // Destructure from the returned JSON
                const players = data[position].players;       // Array of top 5 players
                const averageScores = data[position].averageScores; // Position-wide weekly averages

                // This array is used for auto-scaling the chart’s y-axis
                // by scanning the min/max of all player scores
                const allScores = players.reduce((acc, player) => {
                    return acc.concat(player.scores);
                }, []);

                // Clear any existing carousel items
                carouselIndicators.innerHTML = '';
                carouselInner.innerHTML = '';

                players.forEach((player, index) => {
                    // CREATE CAROUSEL INDICATOR
                    const indicator = document.createElement('button');
                    indicator.setAttribute('type', 'button');
                    indicator.setAttribute('data-bs-target', '#playerCarousel');
                    indicator.setAttribute('data-bs-slide-to', index);
                    indicator.className = (index === 0) ? 'active' : '';
                    indicator.setAttribute('aria-current', (index === 0) ? 'true' : 'false');
                    indicator.setAttribute('aria-label', `Slide ${index + 1}`);
                    carouselIndicators.appendChild(indicator);

                    // CREATE CAROUSEL ITEM
                    const carouselItem = document.createElement('div');
                    carouselItem.className = (index === 0) ? 'carousel-item active' : 'carousel-item';

                    // Build the HTML for the chart card
                    carouselItem.innerHTML = `
                        <div class="chart-card">
                            <div class="chart-card-header">
                                <span class="chart-rank">#${index + 1}</span>
                                <span class="chart-player">${player.name}</span>
                            </div>
                            <div class="chart-card-body">
                                <div class="chart-total-row">
                                    <span class="chart-total">${player.scores.reduce((a, b) => a + b, 0)}</span>
                                    <span class="vs-total">vs. ${averageScores.reduce((a, b) => a + b, 0)}</span>
                                </div>
                                <div class="chart-total-descriptions">
                                    <span class="chart-description">Points vs. average</span>
                                </div>
                            </div>
                            <div id="chart-${index + 1}" class="line-chart"></div>
                        </div>
                    `;

                    carouselInner.appendChild(carouselItem);

                    // RENDER THE CHART for the first carousel item immediately
                    if (index === 0) {
                        // IMPORTANT: Pass player.name as the last argument
                        renderLineChart(
                            `chart-${index + 1}`,   // chart container ID
                            player.weeks,          // X-axis: GWs
                            player.scores,         // Y-axis: player's points
                            averageScores,         // Another series for average
                            player.difficulty,     // Fixture difficulty array
                            allScores,             // For auto-scaling the axis
                            player.name            // So tooltips show player’s name
                        );
                    }
                });

                // When the carousel slides to a new item, render the chart if not rendered
                document.getElementById('playerCarousel').addEventListener('slid.bs.carousel', function (e) {
                    const newIndex = e.to;
                    const chartId = `chart-${newIndex + 1}`;
                    const player = players[newIndex];

                    // If this chart isn't rendered yet, do it now
                    if (document.getElementById(chartId).children.length === 0) {
                        // Again, pass all 7 arguments
                        renderLineChart(
                            chartId,
                            player.weeks,
                            player.scores,
                            averageScores,
                            player.difficulty,
                            allScores,
                            player.name
                        );
                    }
                });
            })
            .catch(error => console.error('Error fetching player data:', error));
    }

    // Initial load: fetch data for "midfielders"
    fetchPlayerData('midfielders');

    // Change position via dropdown
    positionDropdown.addEventListener('change', function () {
        fetchPlayerData(this.value);
    });
});
