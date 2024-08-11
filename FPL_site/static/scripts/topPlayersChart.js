import { renderLineChart } from './chartUtils.js';

document.addEventListener('DOMContentLoaded', function () {
    const positionDropdown = document.getElementById('positionDropdown');
    const carouselInner = document.getElementById('carouselInner');
    const carouselIndicators = document.getElementById('carouselIndicators');

    function fetchPlayerData(position) {
        fetch(`/api/top-5-players?position=${position}`)
            .then(response => response.json())
            .then(data => {
                if (!data || !data[position] || !data[position].players || !data[position].averageScores) {
                    console.error(`Invalid data format for position: ${position}`, data);
                    return;
                }

                const players = data[position].players;
                const averageScores = data[position].averageScores;

                // Generate the allScores array
                const allScores = players.reduce((acc, player) => {
                    return acc.concat(player.scores);
                }, []);

                carouselIndicators.innerHTML = '';
                carouselInner.innerHTML = '';

                players.forEach((player, index) => {
                    console.log('Full player data:', player); // Log the entire player object
                    console.log('Player:', player.name);
                    console.log('Difficulty:', player.difficulty);
                    console.log('Weeks:', player.weeks);
                    console.log('Scores:', player.scores);

                    // Carousel Indicator
                    const indicator = document.createElement('button');
                    indicator.setAttribute('type', 'button');
                    indicator.setAttribute('data-bs-target', '#playerCarousel');
                    indicator.setAttribute('data-bs-slide-to', index);
                    indicator.className = index === 0 ? 'active' : '';
                    indicator.setAttribute('aria-current', index === 0 ? 'true' : 'false');
                    indicator.setAttribute('aria-label', `Slide ${index + 1}`);
                    carouselIndicators.appendChild(indicator);

                    // Carousel Item
                    const carouselItem = document.createElement('div');
                    carouselItem.className = index === 0 ? 'carousel-item active' : 'carousel-item';
                    carouselItem.innerHTML = `
                        <div class="chart-card">
                            <div class="chart-card-header">
                                <span class="chart-rank">#${index + 1}</span>
                                <span class="chart-player">${player.name}</span>
                            </div>
                            <div class="chart-card-body">
                                <span class="chart-total">${player.scores.reduce((a, b) => a + b, 0)} vs. ${averageScores.reduce((a, b) => a + b, 0)}</span>
                                <div id="chart-${index + 1}" class="line-chart"></div>
                            </div>
                        </div>
                    `;
                    carouselInner.appendChild(carouselItem);

                    // Render chart only for the first item, others will be rendered when they become visible
                    if (index === 0) {
                        renderLineChart(`chart-${index + 1}`, player.weeks, player.scores, averageScores, player.difficulty, allScores);
                    }
                });

                // Add event listener for when a carousel item becomes active
                document.getElementById('playerCarousel').addEventListener('slid.bs.carousel', function (e) {
                    const newIndex = e.to;
                    const chartId = `chart-${newIndex + 1}`;
                    const player = players[newIndex];
                    if (document.getElementById(chartId).children.length === 0) {
                        renderLineChart(chartId, player.weeks, player.scores, averageScores, player.difficulty, allScores);
                    }
                });
            })
            .catch(error => console.error('Error fetching player data:', error));
    }

    fetchPlayerData('midfielders');

    positionDropdown.addEventListener('change', function () {
        fetchPlayerData(this.value);
    });
});
