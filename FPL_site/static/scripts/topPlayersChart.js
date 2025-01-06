/***** chartPosition.js (example) *****/
import { renderLineChart } from './chartUtils.js';

document.addEventListener('DOMContentLoaded', function () {
    const positionDropdown = document.getElementById('positionDropdown');
    const carouselInner = document.getElementById('carouselInner');
    const carouselIndicators = document.getElementById('carouselIndicators');
    const carouselElem = document.getElementById('playerCarousel');

    /**
     * Fetch player data for a given position (e.g., "midfielders", "forwards", etc.)
     * and rebuild the carousel with the new data.
     */
    function fetchPlayerData(position) {
        fetch(`/api/top-5-players?position=${position}`)
            .then(response => response.json())
            .then(data => {
                // Basic validation
                if (!data || !data[position] || !data[position].players || !data[position].averageScores) {
                    console.error(`Invalid data format for position: ${position}`, data);
                    return;
                }

                // Dispose of any existing Bootstrap carousel instance
                const oldCarousel = bootstrap.Carousel.getInstance(carouselElem);
                if (oldCarousel) {
                    oldCarousel.dispose();
                }

                // Remove old 'slid.bs.carousel' event listeners
                carouselElem.removeEventListener('slid.bs.carousel', handleSlide);

                // Clear old indicators & items
                carouselIndicators.innerHTML = '';
                carouselInner.innerHTML = '';

                // Extract new data
                const players = data[position].players;        // Top 5 players
                const averageScores = data[position].averageScores; // Weekly average for this position

                // allScores for auto-scaling chart Y-axis
                const allScores = players.reduce((acc, player) => acc.concat(player.scores), []);

                // Build new indicators and carousel items
                players.forEach((player, index) => {
                    // 1) Create carousel indicator
                    const indicator = document.createElement('button');
                    indicator.setAttribute('type', 'button');
                    indicator.setAttribute('data-bs-target', '#playerCarousel');
                    indicator.setAttribute('data-bs-slide-to', index.toString());
                    indicator.className = (index === 0) ? 'active' : '';
                    indicator.setAttribute('aria-current', (index === 0) ? 'true' : 'false');
                    indicator.setAttribute('aria-label', `Slide ${index + 1}`);

                    // Add the indicator to the DOM
                    carouselIndicators.appendChild(indicator);

                    // 2) Create the carousel item
                    const carouselItem = document.createElement('div');
                    carouselItem.className = (index === 0) ? 'carousel-item active' : 'carousel-item';

                    // Build the HTML content
                    carouselItem.innerHTML = `
                        <div class="chart-card">
                            <div class="chart-card-header">
                                <span class="chart-rank">#${index + 1}</span>
                                <span class="chart-player">${player.name}</span>
                            </div>
                            <div class="chart-card-body">
                                <div class="chart-total-row">
                                    <span class="chart-total">
                                        ${player.scores.reduce((a, b) => a + b, 0)}
                                    </span>
                                    <span class="vs-total">
                                        vs. ${averageScores.reduce((a, b) => a + b, 0).toFixed(1)}
                                    </span>
                                </div>
                                <div class="chart-total-descriptions">
                                    <span class="chart-description">Points vs. average</span>
                                </div>
                            </div>
                            <div id="chart-${index + 1}" class="line-chart"></div>
                        </div>
                    `;

                    // Add this new item to the carousel
                    carouselInner.appendChild(carouselItem);

                    // Render the chart immediately for the first item
                    if (index === 0) {
                        renderLineChart(
                            `chart-${index + 1}`,  // ID of the chart container
                            player.weeks,         // X-axis: GWs
                            player.scores,        // Player’s points
                            averageScores,        // Position-wide average
                            player.difficulty,    // Difficulty array
                            allScores,            // For Y-axis scaling
                            player.name           // Tooltip label
                        );
                    }
                });

                /**
                 * New event listener for the newly rebuilt carousel.
                 * Renders a chart on the newly active slide if it isn't already rendered.
                 */
                function handleSlide(e) {
                    const newIndex = e.to;
                    const chartId = `chart-${newIndex + 1}`;
                    const player = players[newIndex];

                    // If the chart container is empty, render now
                    if (document.getElementById(chartId).children.length === 0) {
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
                }

                // Attach the new event listener for slide transitions
                carouselElem.addEventListener('slid.bs.carousel', handleSlide);

                // Re-initialize the carousel with the new items
                new bootstrap.Carousel(carouselElem);
            })
            .catch(error => console.error('Error fetching player data:', error));
    }

    // Initially load midfielders
    fetchPlayerData('midfielders');

    // On dropdown change, load the selected position
    positionDropdown.addEventListener('change', function () {
        fetchPlayerData(this.value);
    });
});
