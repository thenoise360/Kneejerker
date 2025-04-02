/***** home.js *****/
import { renderBarChart } from './chartUtils.js';
import { 
    updateLastUpdatedTime, 
    formatNumber, 
    formatOwnership, 
    isUserActive, 
    truncateLabel 
} from './utils.js';

document.addEventListener('DOMContentLoaded', function () {

    /* ------------------ Loader / Overlay Logic ------------------ */

    function showLoader() {
        const loader = document.getElementById('loader');
        if (loader) loader.style.display = 'flex';
    }

    function hideLoader() {
        const loader = document.getElementById('loader');
        if (loader) loader.style.display = 'none';
    }

    const overlay = document.getElementById('dictionary-overlay');
    const dictionaryText = document.querySelector('.dictionary-content');
    const currentURL = window.location.href;

    if (currentURL.includes('kneejerker.co.uk') || currentURL.includes('heroku') || currentURL.includes('localhost')) {
        overlay.style.display = 'flex';  // Show the overlay
    }

    let overlayVisibleTime = 0;
    const minimumOverlayDuration = 6000;

    function showOverlay() {
        overlay.classList.remove('fade-out');
        overlay.style.display = 'flex';
        dictionaryText.style.opacity = '0';

        setTimeout(() => {
            dictionaryText.style.opacity = '1';
        }, 100);

        overlayVisibleTime = Date.now();
    }

    function hideOverlay() {
        const elapsedTime = Date.now() - overlayVisibleTime;
        const remainingTime = minimumOverlayDuration - elapsedTime;

        setTimeout(() => {
            overlay.classList.add('fade-out');
            setTimeout(() => {
                overlay.style.display = 'none';
                overlay.classList.remove('fade-out');
            }, 500);
        }, remainingTime > 0 ? remainingTime : 0);
    }

    showOverlay();
    setTimeout(() => {
        hideOverlay();
    }, minimumOverlayDuration);

    /* ------------------ Global Vars & DOM Elements ------------------ */

    const pills = document.querySelectorAll('.pill');
    const charts = document.querySelectorAll('.chart');
    const descriptions = {
        'net-transfers-in': document.getElementById('description-net-transfers-in'),
        'net-transfers-out': document.getElementById('description-net-transfers-out'),
        'relative-ownership': document.getElementById('description-relative-ownership')
    };

    // Keep references to ECharts chart instances
    const chartInstances = {};

    // Keep references to each chart's "sortedData", plus a quick map from playerId -> dataIndex for highlight
    // e.g. chartDataMap[chartId] = {
    //     sortedData: [...],
    //     playerIndexMap: { [playerId]: dataIndex, ... }
    // }
    const chartDataMap = {};

    // Only ONE global selected player across all charts
    let selectedPlayerId = null;

    let lastUpdatedTimestamp = Date.now();

    /* ------------------ Chart Highlight Logic Across All Charts ------------------ */

    /**
     * highlightAllCharts: given a playerId, highlight that player's bar
     * in *each* chart if it exists, else no highlight if absent.
     */
    function highlightAllCharts(playerId) {
        Object.keys(chartDataMap).forEach(chartId => {
            const { playerIndexMap } = chartDataMap[chartId];
            const chartInstance = chartInstances[chartId];
            if (!chartInstance) return;

            // Check if this playerId is in that chart
            if (playerIndexMap[playerId] !== undefined) {
                const dataIndex = playerIndexMap[playerId];
                // Re-apply coloring so only that bar is primary
                chartInstance.setOption({
                    series: [{
                        itemStyle: {
                            color: function (params) {
                                return params.dataIndex === dataIndex 
                                    ? 'var(--primary-color)'
                                    : 'var(--black-20)';
                            }
                        },
                        emphasis: {
                            itemStyle: {
                                color: 'inherit',
                                opacity: 0.8
                            }
                        }
                    }]
                });
            } else {
                // This chart doesn't have that player. Color all bars default.
                chartInstance.setOption({
                    series: [{
                        itemStyle: {
                            color: 'var(--black-20)'
                        },
                        emphasis: {
                            itemStyle: {
                                color: 'inherit',
                                opacity: 0.8
                            }
                        }
                    }]
                });
            }
        });
    }

    /* ------------------ Debounce Utility ------------------ */
    function debounce(func, delay) {
        let timer;
        return function (...args) {
            const context = this;
            clearTimeout(timer);
            timer = setTimeout(() => func.apply(context, args), delay);
        };
    }
    
    // Debounced selectPlayer
    const debouncedSelectPlayer = debounce(selectPlayer, 2000);

    /* ------------------ Click Handling for a Single Chart ------------------ */

    function initializeChartClickHandling(chartInstance, chartId) {
        chartInstance.on('click', (params) => {
            if (
                (params.componentType === 'series' || params.componentType === 'label') &&
                params.dataIndex != null
            ) {
                const dataObj = chartDataMap[chartId].sortedData[params.dataIndex];
                if (!dataObj) return;

                const newPlayerId = dataObj.id;
                if (!newPlayerId) return;

                // Update the global selection
                selectedPlayerId = newPlayerId;

                // Apply highlight on *all* charts for that player
                highlightAllCharts(selectedPlayerId);

                // Trigger your existing "selectPlayer" logic
                selectPlayer(newPlayerId);
            }
        });

        // Optional: hover highlight
        chartInstance.on('mousemove', function (params) {
            if (params.componentType === 'series') {
                chartInstance.dispatchAction({
                    type: 'highlight',
                    seriesIndex: 0,
                    dataIndex: params.dataIndex,
                });
            }
        });
        chartInstance.on('mouseout', function () {
            chartInstance.dispatchAction({
                type: 'downplay',
                seriesIndex: 0,
            });
        });
    }

    /* ------------------ Fetch & Render Chart Data ------------------ */

    function fetchChartData(url, chartId) {
        fetch(url)
            .then(response => response.json())
            .then(data => {
                if (!data.labels || data.labels.length === 0) {
                    console.error(`No data available for chart: ${chartId}`);
                    return;
                }

                let sortedData, labels, values, formattedValues, playerIndexMap = {};

                if (chartId === 'net-transfers-in') {
                    sortedData = data.labels.map((label, index) => ({
                        label: truncateLabel(label),
                        value: data.values[index],
                        id: data.ids ? data.ids[index] : null
                    })).sort((a, b) => a.value - b.value);

                    labels = sortedData.map(item => item.label);
                    values = sortedData.map(item => item.value);
                    formattedValues = sortedData.map(item => formatNumber(item.value));

                } else if (chartId === 'net-transfers-out') {
                    sortedData = data.labels.map((label, index) => ({
                        label: truncateLabel(label),
                        value: data.values[index],
                        id: data.ids ? data.ids[index] : null
                    })).sort((a, b) => a.value - b.value);

                    labels = sortedData.map(item => item.label);
                    values = sortedData.map(item => item.value);
                    formattedValues = sortedData.map(item => formatNumber(-item.value)); // negative

                } else if (chartId === 'relative-ownership') {
                    sortedData = data.labels.map((label, index) => ({
                        label: truncateLabel(label),
                        change: data.newValues[index] - data.oldValues[index],
                        id: data.ids ? data.ids[index] : null
                    })).sort((a, b) => a.change - b.change);

                    labels = sortedData.map(item => item.label);
                    values = sortedData.map(item => item.change);
                    formattedValues = sortedData.map(item =>
                        formatOwnership(
                            data.oldValues[data.labels.indexOf(item.label)],
                            data.newValues[data.labels.indexOf(item.label)]
                        )
                    );
                }

                // Build the quick playerIndexMap
                sortedData.forEach((obj, idx) => {
                    if (obj.id != null) {
                        playerIndexMap[obj.id] = idx;
                    }
                });

                // Store chart data for highlighting
                chartDataMap[chartId] = {
                    sortedData,
                    playerIndexMap
                };

                // Render chart
                renderBarChart(chartId, labels, values, formattedValues);

                // Save the ECharts instance
                const chartInstance = echarts.getInstanceByDom(document.getElementById(chartId));
                chartInstances[chartId] = chartInstance;

                if (chartInstance) {
                    initializeChartClickHandling(chartInstance, chartId);

                    // If we already have a globally selected player, highlight it if it's in this chart
                    if (selectedPlayerId) {
                        highlightAllCharts(selectedPlayerId);
                    } 
                    else {
                        // If no global selection yet, and this is the FIRST chart, auto-select first bar
                        // We'll define "net-transfers-in" as the first chart that auto-selects.
                        if (chartId === 'net-transfers-in' && sortedData.length > 0) {
                            const firstObj = sortedData[sortedData.length - 1];
                            if (firstObj.id) {
                                selectedPlayerId = firstObj.id;
                                highlightAllCharts(selectedPlayerId);
                                selectPlayer(selectedPlayerId);
                            }
                        }
                        // For the other charts, we do NOT auto-select anything if global is null
                    }
                }

                lastUpdatedTimestamp = Date.now();
                updateLastUpdatedTime();
            })
            .catch(error => console.error('Error fetching chart data:', error));
    }

    /* ------------------ Player Info & Alternatives ------------------ */

    function updateAlternativePlayers(players) {
        // 1) We only want up to 4 real players
        const truncatedPlayers = players.slice(0, 4);
    
        // 2) We always want at least 2 slots visible
        //    so if there's 1 or 0 players, we still show 2 placeholders.
        let displayCount = Math.max(truncatedPlayers.length, 2);
    
        // But we won't exceed 6 total placeholders.
        // If your requirement is strictly "up to 4" in total, we can do:
        displayCount = Math.min(displayCount, 4);
    
        // Grab all 6 placeholders from the DOM
        const allPlaceholders = Array.from(document.querySelectorAll('.alternatives-details .alternative-player'));
    
        // Loop through all 6 placeholders
        for (let i = 0; i < allPlaceholders.length; i++) {
            const container = allPlaceholders[i];
    
            if (i < displayCount) {
                // We want to show this slot
                container.style.display = 'block';
    
                if (i < truncatedPlayers.length) {
                    // Fill with real player data
                    const player = truncatedPlayers[i];
                    
                    //  If you’re using your existing code:
                    const altPlayerName = container.querySelector('.alt-player');
                    const altShirt = container.querySelector('.alternatives-shirt');
                    const altTeamName = container.querySelector('.alt-player-team-name');
                    const altValue = container.querySelector('.alt-player-value');
                    const altForm = container.querySelector('.alt-player-form');
    
                    altPlayerName.textContent = player.web_name ?? '-';
                    altShirt.src = player.shirt ?? '/static/content/Tshirts/unknown-football-shirt-svgrepo-com.svg';
                    altTeamName.textContent = player.team_name ?? '-';
                    altValue.textContent = player.now_cost 
                        ? '£' + (player.now_cost / 10).toFixed(1)
                        : '£-.-';
                    altForm.textContent = player.form ?? '-';
    
                    // If you want it clickable -> debouncedSelectPlayer
                    container.onclick = () => debouncedSelectPlayer(player.id);
    
                } else {
                    // We have fewer real players than displayCount, so this is a "placeholder" row
                    // Just fill with generic dashes or whatever you want to display
                    const altPlayerName = container.querySelector('.alt-player');
                    const altShirt = container.querySelector('.alternatives-shirt');
                    const altTeamName = container.querySelector('.alt-player-team-name');
                    const altValue = container.querySelector('.alt-player-value');
                    const altForm = container.querySelector('.alt-player-form');
    
                    altPlayerName.textContent = '-';
                    altShirt.src = '/static/content/Tshirts/unknown-football-shirt-svgrepo-com.svg';
                    altTeamName.textContent = '-';
                    altValue.textContent = '£-.-';
                    altForm.textContent = '-';
    
                    // Remove any existing click
                    container.onclick = null;
                }
            } else {
                // Past our displayCount => hide
                container.style.display = 'none';
            }
        }
    }
    

    function selectPlayer(playerId) {

        // 1) Update the global ID
        selectedPlayerId = playerId;

        // 2) Immediately highlight on all charts
        highlightAllCharts(playerId);

        showLoader();
        Promise.all([
            fetch(`/get_player_summary?id=${playerId}`).then(r => r.ok ? r.json() : Promise.reject(r.status)),
            fetch(`/get_next_5_gameweeks?id=${playerId}`).then(r => r.ok ? r.json() : Promise.reject(r.status)),
            fetch(`/get_player_alternates?id=${playerId}`).then(r => r.ok ? r.json() : Promise.reject(r.status))
        ])
        .then(([playerDataResponse, fixtures, altPlayers]) => {
            if (Array.isArray(playerDataResponse) && playerDataResponse.length > 0) {
                const playerData = playerDataResponse[0];
                if (playerData && Array.isArray(playerData.metrics)) {
                    playerData.fixtures = fixtures;
                    populatePlayerSummary(playerData);
                    updateFixtureDetails(playerData);
                } else {
                    console.error("Invalid player data:", playerData);
                }
            } else {
                console.error("Unexpected response format:", playerDataResponse);
            }
            updateAlternativePlayers(altPlayers);
        })
        .finally(() => hideLoader())
        .catch(error => {
            console.error('Error fetching player data or alt players:', error);
            hideLoader();
        });
    }

    /* ------------------ Populate Player Summary + Fixtures ------------------ */

    function populatePlayerSummary(player) {
        const carouselIndicators = document.getElementById('carouselIndicators');
        const summaryCarouselInner = document.getElementById('summaryCarouselInner');
    
        if (!carouselIndicators || !summaryCarouselInner) {
            console.error("Carousel elements not found in the DOM.");
            return;
        }
        if (!player || !player.metrics || !Array.isArray(player.metrics)) {
            console.error("Invalid player data provided.");
            return;
        }
    
        const metricGroups = [];
        const metricsPerGroup = 3;
        for (let i = 0; i < player.metrics.length; i += metricsPerGroup) {
            metricGroups.push(player.metrics.slice(i, i + metricsPerGroup));
        }
    
        // Carousel indicators
        carouselIndicators.innerHTML = metricGroups.map((_, index) => `
            <button type="button" data-bs-target="#summaryCarousel" data-bs-slide-to="${index}"
              ${index === 0 ? 'class="active" aria-current="true"' : ''} aria-label="Slide ${index + 1}"></button>
        `).join('');
    
        // Carousel items
        summaryCarouselInner.innerHTML = metricGroups.map((group, groupIndex) => `
            <div class="carousel-item ${groupIndex === 0 ? 'active' : ''}">
                <div class="heading-row">
                    ${group.map(metric => `<div class="measure-title">${metric.title}</div>`).join('')}
                </div>
                <div class="player-values">
                    ${group.map(metric => `<div class="measure-values">${metric.value}</div>`).join('')}
                </div>
                <div class="average-values">
                    ${group.map(metric => `<div class="average-values">${metric.averageValue}</div>`).join('')}
                </div>
            </div>
        `).join('');
    
        // Reinitialize Carousel
        const myCarousel = document.querySelector('#summaryCarousel');
        if (myCarousel) {
            const carouselInstance = bootstrap.Carousel.getInstance(myCarousel);
            if (carouselInstance) carouselInstance.dispose();
            new bootstrap.Carousel(myCarousel);
        }
    
        // Basic info
        document.getElementById('player-summary-name').textContent = player.name || 'Unknown';
        document.getElementById('chance-next-round').textContent = player.news || '';
    
        const chanceElement = document.getElementById('chance-next-round');
        chanceElement.className = '';
        chanceElement.classList.add("chance-next-round-" + player.chance_of_playing);
        chanceElement.style.display = '';
    
        document.getElementById('player-value').textContent 
            = "\u00A3" + (player.value ?? 0);
    
        // Yellow card section
        const yellowCardsElement = document.getElementById('yellow-cards');
        if (yellowCardsElement && player.suspension) {
            const yellowCards = player.suspension.total_yellow_cards || 0;
            const yellowsLeft = player.suspension.yellow_cards_needed || 0;
    
            // Determine image path
            const cardImagePath = `/static/content/referee-cards/${yellowCards >= 5 ? '5-plus-yellow' : yellowCards + '-yellow'}.png`;
    
            // Set image and text
            yellowCardsElement.innerHTML = `
                <img src="${cardImagePath}" alt="${yellowCards} yellow cards" class="yellow-card-img">
                <div class="yellow-card-info">
                    <span class="supporting-metrics-values">${yellowCards}</span>
                </div>
            `;
        }
        
        // Yellow card section
        const suspensionsYellowsLeftElement = document.getElementById('suspensions-yellows-left');

        if (suspensionsYellowsLeftElement) {
            if (player.suspension) {
                const yellowCardsNeeded = player.suspension.yellow_cards_needed || 0;
                const yellowCards = player.suspension.yellow_cards || 0;
                const yellowCardsRemaining = yellowCardsNeeded - yellowCards;

                // Update the text content with a valid message
                suspensionsYellowsLeftElement.textContent = 
                    `${yellowCardsRemaining > 0 ? yellowCardsRemaining : 0} yellow cards to a suspension`;
            } else {
                // If no suspension data is available, set a default message
                suspensionsYellowsLeftElement.textContent = 'No suspension data available';
            }
        } else {
            console.error("Element with ID 'suspensions-yellows-left' not found in the DOM.");
        }

        document.getElementById('position-name').textContent 
            = player.position_name || 'Position';
        document.querySelector('.coat-hanger .shirt').src 
            = player.shirtImage || '/static/content/Tshirts/unknown-football-shirt-svgrepo-com.svg';
        document.querySelector('.coat-hanger .player-team-name').textContent 
            = player.team_name || '-';
    }    

    function generateCompositeShirt(shirtUrl1, shirtUrl2) {
        const svgNS = "http://www.w3.org/2000/svg";
    
        const svg = document.createElementNS(svgNS, "svg");
        svg.setAttribute("width", "50");
        svg.setAttribute("height", "50");
        svg.setAttribute("viewBox", "0 0 100 100");
        svg.style.display = "block"; // Match <img> behavior
    
        // Define <defs> and mask
        const defs = document.createElementNS(svgNS, "defs");
        const mask = document.createElementNS(svgNS, "mask");
        mask.setAttribute("id", "diagonal-mask-" + Math.random()); // avoid ID collision
        const maskShape = document.createElementNS(svgNS, "polygon");
        maskShape.setAttribute("points", "0,100 100,0 100,100");
        maskShape.setAttribute("fill", "white");
        mask.appendChild(maskShape);
        defs.appendChild(mask);
        svg.appendChild(defs);
    
        const backShirt = document.createElementNS(svgNS, "image");
        backShirt.setAttributeNS("http://www.w3.org/1999/xlink", "href", shirtUrl1);
        backShirt.setAttribute("width", "100");
        backShirt.setAttribute("height", "100");
    
        const frontShirt = document.createElementNS(svgNS, "image");
        frontShirt.setAttributeNS("http://www.w3.org/1999/xlink", "href", shirtUrl2);
        frontShirt.setAttribute("width", "100");
        frontShirt.setAttribute("height", "100");
        frontShirt.setAttribute("mask", `url(#${mask.getAttribute('id')})`);
    
        svg.appendChild(backShirt);
        svg.appendChild(frontShirt);
    
        return svg;
    }    

    function updateFixtureDetails(player) {
        if (!Array.isArray(player.fixtures)) return;
    
        // Group fixtures by gameweek
        const fixtureMap = {};
        player.fixtures.forEach(fix => {
            if (!fixtureMap[fix.gameweek]) fixtureMap[fix.gameweek] = [];
            fixtureMap[fix.gameweek].push(fix);
        });
    
        const gameweeks = Object.keys(fixtureMap).sort((a, b) => a - b);
    
        gameweeks.forEach((gw, index) => {
            const fixtures = fixtureMap[gw];
            const fixtureElement = document.getElementById(`fixture-${index + 1}`);
            const venueElement = document.getElementById(`venue-${index + 1}`);
            const coatHanger = document.querySelector(`.team-shirts .coat-hanger:nth-child(${index + 1})`);
    
            if (!fixtureElement || !venueElement || !coatHanger) return;
    
            // Clear the coat hanger completely — SVG or IMG — and reset to base shirt
            coatHanger.innerHTML = '';
            const newImg = document.createElement("img");
            newImg.classList.add("shirt");
            newImg.src = '/static/content/Tshirts/unknown-football-shirt-svgrepo-com.svg';
            coatHanger.appendChild(newImg);
    
            const shirtElement = coatHanger.querySelector(".shirt");
    
            if (fixtures.length === 2) {
                const [fix1, fix2] = fixtures;
                fixtureElement.textContent = `${fix1.teamName} + ${fix2.teamName}`;
                fixtureElement.className = `difficulty-${Math.max(fix1.difficulty, fix2.difficulty)}`;
                const composite = generateCompositeShirt(fix1.shirtImage, fix2.shirtImage);
                coatHanger.replaceChild(composite, shirtElement);
                venueElement.textContent = 'Double';
                venueElement.className = 'home';
            } else {
                const fix = fixtures[0];
                fixtureElement.textContent = fix.teamName;
                fixtureElement.className = `difficulty-${fix.difficulty}`;
                shirtElement.src = fix.shirtImage;
                venueElement.textContent = fix.homeOrAway;
                venueElement.className = fix.homeOrAway.toLowerCase();
            }
        });
    }    

    /* ------------------ Initialize / Refresh Charts ------------------ */

    function initializeCharts() {
        fetchChartData('/api/net-transfers-in', 'net-transfers-in');
        fetchChartData('/api/net-transfers-out', 'net-transfers-out');
        fetchChartData('/api/relative-ownership', 'relative-ownership');
    }

    // Pills: switch chart view
    pills.forEach(pill => {
        pill.addEventListener('click', function () {
            pills.forEach(p => p.classList.remove('active'));
            this.classList.add('active');

            charts.forEach(chart => chart.classList.remove('active'));
            Object.values(descriptions).forEach(desc => {
                if (desc) desc.style.display = 'none';
            });

            const target = document.getElementById(this.dataset.target);
            if (target) {
                target.classList.add('active');
                descriptions[this.dataset.target].style.display = 'block';
                fetchChartData(`/api/${this.dataset.target}`, this.dataset.target);
            } else {
                console.error(`Target element for ${this.dataset.target} not found.`);
            }

            // Resize
            Object.keys(chartInstances).forEach(chartId => {
                chartInstances[chartId]?.resize();
            });
        });
    });

    // Run once on page load
    initializeCharts();

    // If user becomes active after inactivity
    isUserActive(initializeCharts);

    // On window resize
    window.addEventListener('resize', function () {
        Object.keys(chartInstances).forEach(chartId => {
            chartInstances[chartId]?.resize();
        });
    });

    // Update the "Last Updated" time every 30s
    setInterval(updateLastUpdatedTime, 30000);

    // OPTIONAL auto-refresh every 60s if desired
    /*
    setInterval(() => {
        updateLastUpdatedTime();
        initializeCharts();
    }, 60000);
    */
});
