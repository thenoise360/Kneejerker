import { renderBarChart } from './chartUtils.js';
import { updateLastUpdatedTime, formatNumber, formatOwnership, isUserActive, callUpdateEndpoint, truncateLabel } from './utils.js';

document.addEventListener('DOMContentLoaded', function () {
    const pills = document.querySelectorAll('.pill');
    const charts = document.querySelectorAll('.chart');
    const lastUpdatedTime = document.getElementById('last-updated-time');
    const descriptions = {
        'net-transfers-in': document.getElementById('description-net-transfers-in'),
        'net-transfers-out': document.getElementById('description-net-transfers-out'),
        'relative-ownership': document.getElementById('description-relative-ownership')
    };
    const chartInstances = {};
    let lastUpdatedTimestamp = Date.now();

    function fetchChartData(url, chartId) {
        fetch(url)
            .then(response => response.json())
            .then(data => {
                let sortedData, labels, values, formattedValues;

                if (chartId === 'net-transfers-in') {
                    // Sort by value in descending order (highest to lowest)
                    sortedData = data.labels.map((label, index) => ({
                        label: truncateLabel(label),
                        value: data.values[index]
                    })).sort((a, b) => a.value - b.value);

                    labels = sortedData.map(item => item.label);
                    values = sortedData.map(item => item.value);
                    formattedValues = sortedData.map(item => formatNumber(item.value));

                    renderBarChart(chartId, labels, values, formattedValues);
                } else if (chartId === 'net-transfers-out') {
                    // Sort by value in ascending order (most negative to least negative)
                    sortedData = data.labels.map((label, index) => ({
                        label: truncateLabel(label),
                        value: data.values[index]
                    })).sort((a, b) => a.value - b.value);

                    labels = sortedData.map(item => item.label);
                    values = sortedData.map(item => item.value);
                    formattedValues = sortedData.map(item => formatNumber(-item.value));

                    renderBarChart(chartId, labels, values, formattedValues);
                } else if (chartId === 'relative-ownership') {
                    // Sort by change in descending order (highest change first)
                    sortedData = data.labels.map((label, index) => ({
                        label: truncateLabel(label),
                        change: data.newValues[index] - data.oldValues[index]
                    })).sort((a, b) => a.change - b.change);

                    labels = sortedData.map(item => item.label);
                    values = sortedData.map(item => item.change);
                    formattedValues = sortedData.map(item => formatOwnership(
                        data.oldValues[data.labels.indexOf(item.label)],
                        data.newValues[data.labels.indexOf(item.label)]
                    ));

                    renderBarChart(chartId, labels, values, formattedValues);
                }

                lastUpdatedTimestamp = Date.now();
                updateLastUpdatedTime();
            })
            .catch(error => console.error('Error fetching chart data:', error));
    }

    function initializeCharts() {
        fetchChartData('/api/net-transfers-in', 'net-transfers-in');
        fetchChartData('/api/net-transfers-out', 'net-transfers-out');
        fetchChartData('/api/relative-ownership', 'relative-ownership');
    }

    pills.forEach(pill => {
        pill.addEventListener('click', function () {
            pills.forEach(p => p.classList.remove('active'));
            this.classList.add('active');

            charts.forEach(chart => chart.classList.remove('active'));
            Object.values(descriptions).forEach(desc => {
                if (desc) {
                    desc.style.display = 'none';
                }
            });

            const target = document.getElementById(this.dataset.target);
            if (target) {
                target.classList.add('active');
                descriptions[this.dataset.target].style.display = 'block';
                fetchChartData(`/api/${this.dataset.target}`, this.dataset.target);
            } else {
                console.error(`Target element for ${this.dataset.target} not found.`);
            }

            // Ensure chart is resized properly
            Object.keys(chartInstances).forEach(chartId => {
                chartInstances[chartId]?.resize();
            });
        });
    });

    initializeCharts();
    isUserActive(initializeCharts);

    window.addEventListener('resize', function () {
        Object.keys(chartInstances).forEach(chartId => {
            chartInstances[chartId]?.resize();
        });
    });

    setInterval(updateLastUpdatedTime, 30000);
});
