import { renderBarChart, applyCustomClasses } from './chartUtils.js';
import { formatNumber } from './utils.js';

export function initializeNetTransfersChart() {
    fetch('/api/net-transfers')
        .then(response => response.json())
        .then(data => {
            const sortedData = data.labels.map((label, index) => ({
                label: label,
                value: data.values[index]
            })).sort((a, b) => a.value - b.value);

            const labels = sortedData.map(item => item.label);
            const values = sortedData.map(item => item.value);
            const formattedValues = sortedData.map(item => formatNumber(item.value));

            renderBarChart('net-transfers', labels, values, formattedValues);

            // Ensure custom styles are applied
            applyCustomClasses('net-transfers');
        })
        .catch(error => console.error('Error fetching net transfers data:', error));
}
