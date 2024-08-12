import { renderBarChart } from './chartUtils.js';
import { updateLastUpdatedTime, formatNumber, formatOwnership, isUserActive, callUpdateEndpoint, truncateLabel } from './utils.js';

document.addEventListener('DOMContentLoaded', function () {
    const pills = document.querySelectorAll('.pill');
    const charts = document.querySelectorAll('.chart');
    const lastUpdatedTime = document.getElementById('last-updated-time');
    const descriptions = {
        'net-transfers': document.getElementById('description-net-transfers'),
        'relative-ownership': document.getElementById('description-relative-ownership')
    };
    const chartInstances = {};
    let lastUpdatedTimestamp = Date.now();

    function fetchChartData(url, chartId) {
        fetch(url)
            .then(response => response.json())
            .then(data => {
                if (chartId === 'net-transfers') {
                    const sortedData = data.labels.map((label, index) => ({
                        label: truncateLabel(label),
                        value: data.values[index]
                    })).sort((a, b) => a.value - b.value);

                    const labels = sortedData.map(item => item.label);
                    const values = sortedData.map(item => item.value);
                    const formattedValues = sortedData.map(item => formatNumber(item.value));

                    renderBarChart(chartId, labels, values, formattedValues);
                } else if (chartId === 'relative-ownership') {
                    const sortedData = data.labels.map((label, index) => ({
                        label: truncateLabel(label),
                        newValue: data.newValues[index],
                        oldValue: data.oldValues[index],
                        change: data.newValues[index] - data.oldValues[index]
                    })).sort((a, b) => a.change - b.change);

                    const labels = sortedData.map(item => item.label);
                    const values = sortedData.map(item => item.change);
                    const formattedValues = sortedData.map(item => formatOwnership(item.oldValue, item.newValue));

                    renderBarChart(chartId, labels, values, formattedValues);
                }
                lastUpdatedTimestamp = Date.now();
                updateLastUpdatedTime();
            })
            .catch(error => console.error('Error fetching chart data:', error));
    }

    function initializeCharts() {
        fetchChartData('/api/net-transfers', 'net-transfers');
        fetchChartData('/api/relative-ownership', 'relative-ownership');
    }

    pills.forEach(pill => {
        pill.addEventListener('click', function () {
            pills.forEach(p => p.classList.remove('active'));
            this.classList.add('active');

            charts.forEach(chart => chart.classList.remove('active'));
            Object.values(descriptions).forEach(desc => desc.style.display = 'none');

            const target = document.getElementById(this.dataset.target);
            target.classList.add('active');
            descriptions[this.dataset.target].style.display = 'block';

            fetchChartData(`/api/${this.dataset.target}`, this.dataset.target);

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
