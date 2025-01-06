/***** topPlayersChart.js *****/
import { renderLineChart } from './chartUtils.js';

document.addEventListener('DOMContentLoaded', function () {
    const positionDropdown = document.getElementById('positionDropdown');

    /**
     * fetchPlayerData(position):
     * Fetches top-5 players for the given position, removes the old
     * #playerCarousel node, creates a fresh one, and reattaches it
     * to the same parent.
     */
    function fetchPlayerData(position) {
        console.log(`Fetching data for position: ${position}`);
        fetch(`/api/top-5-players?position=${position}`)
            .then(response => response.json())
            .then(data => {
                // Validate structure
                if (
                    !data ||
                    !data[position] ||
                    !data[position].players ||
                    !data[position].averageScores
                ) {
                    console.error(`Invalid data for position: ${position}`, data);
                    return;
                }

                // 1) Find the existing #playerCarousel (if it exists)
                const oldCarouselElem = document.getElementById('playerCarousel');
                if (!oldCarouselElem) {
                    console.error('No element with ID "playerCarousel" found in the DOM.');
                    return;
                }

                // We'll need the parent to re-insert a fresh node
                const parentNode = oldCarouselElem.parentNode;
                if (!parentNode) {
                    console.error('playerCarousel has no parent node!');
                    return;
                }

                // 2) Remove the old #playerCarousel
                parentNode.removeChild(oldCarouselElem);

                // 3) Create a brand-new carousel element
                const newCarouselElem = document.createElement('div');
                newCarouselElem.id = 'playerCarousel';
                newCarouselElem.className = 'carousel slide';
                // No auto-interval if you prefer manual control
                newCarouselElem.setAttribute('data-bs-interval', 'false');

                newCarouselElem.innerHTML = `
                    <div class="carousel-indicators" id="carouselIndicators"></div>
                    <div class="carousel-inner" id="carouselInner"></div>
                    <button class="carousel-control-prev" type="button" data-bs-target="#playerCarousel" data-bs-slide="prev">
                        <span class="carousel-control-prev-icon" aria-hidden="true"></span>
                        <span class="visually-hidden">Previous</span>
                    </button>
                    <button class="carousel-control-next" type="button" data-bs-target="#playerCarousel" data-bs-slide="next">
                        <span class="carousel-control-next-icon" aria-hidden="true"></span>
                        <span class="visually-hidden">Next</span>
                    </button>
                `;

                // 4) Insert the new carousel into the same parent
                parentNode.appendChild(newCarouselElem);

                // Grab references for indicators & inner
                const carouselIndicators = newCarouselElem.querySelector('#carouselIndicators');
                const carouselInner = newCarouselElem.querySelector('#carouselInner');

                if (!carouselIndicators || !carouselInner) {
                    console.error('Could not find #carouselIndicators or #carouselInner inside the new carousel.');
                    return;
                }

                // 5) Extract new data
                const players = data[position].players;
                const averageScores = data[position].averageScores;
                // For auto-scaling the chart Y-axis
                const allScores = players.reduce((acc, p) => acc.concat(p.scores), []);

                // 6) Build new indicators & slides
                players.forEach((player, index) => {
                    // INDICATOR
                    const indicator = document.createElement('button');
                    indicator.type = 'button';
                    indicator.setAttribute('data-bs-target', '#playerCarousel');
                    indicator.setAttribute('data-bs-slide-to', String(index));
                    indicator.setAttribute('aria-label', `Slide ${index + 1}`);
                    if (index === 0) {
                        indicator.classList.add('active');
                        indicator.setAttribute('aria-current', 'true');
                    }
                    carouselIndicators.appendChild(indicator);

                    // CAROUSEL ITEM
                    const itemDiv = document.createElement('div');
                    itemDiv.className = (index === 0) ? 'carousel-item active' : 'carousel-item';

                    // Example layout
                    itemDiv.innerHTML = `
                        <div class="chart-card">
                            <div class="chart-card-header">
                                <span class="chart-rank">#${index + 1}</span>
                                <span class="chart-player">${player.name}</span>
                            </div>
                            <div class="chart-card-body">
                                <div class="chart-total-row">
                                    <span class="chart-total">${
                                        player.scores.reduce((a, b) => a + b, 0)
                                    }</span>
                                    <span class="vs-total">vs. ${
                                        averageScores.reduce((a, b) => a + b, 0).toFixed(1)
                                    }</span>
                                </div>
                                <div class="chart-total-descriptions">
                                    <span class="chart-description">Points vs. average</span>
                                </div>
                            </div>
                            <div id="chart-${index + 1}" class="line-chart"></div>
                        </div>
                    `;
                    carouselInner.appendChild(itemDiv);

                    // Render the first chart right away
                    if (index === 0) {
                        renderLineChart(
                            `chart-${index + 1}`, // chart container ID
                            player.weeks,
                            player.scores,
                            averageScores,
                            player.difficulty,
                            allScores,
                            player.name
                        );
                    }
                });

                // 7) handleSlide references the *new* players array
                function handleSlide(e) {
                    console.log(`Slide event fired: newIndex = ${e.to}`);
                    const newIndex = e.to;
                    const chartId = `chart-${newIndex + 1}`;
                    const player = players[newIndex];

                    const chartElem = document.getElementById(chartId);
                    if (chartElem && chartElem.children.length === 0) {
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

                // 8) Add the event + init
                newCarouselElem.addEventListener('slid.bs.carousel', handleSlide);
                new bootstrap.Carousel(newCarouselElem, { interval: false });

                console.log(`Carousel rebuilt for position: ${position}`);
            })
            .catch(error => {
                console.error(`Error fetching player data for position=${position}:`, error);
            });
    }

    // If we have a positionDropdown, default to "midfielders" or whichever you want
    if (positionDropdown) {
        fetchPlayerData('midfielders');

        positionDropdown.addEventListener('change', function () {
            const newPos = this.value;
            console.log('Switching to position:', newPos);
            fetchPlayerData(newPos);
        });
    } else {
        console.error('No element with ID "positionDropdown" found in the DOM.');
    }
});
