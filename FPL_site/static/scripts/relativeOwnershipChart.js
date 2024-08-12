import { renderBarChart } from './chartUtils.js';
export function initializeRelativeOwnershipChart() {
    fetch('/api/relative-ownership')
        .then(response => response.json())
        .then(data => {
            const sortedData = data.labels.map((label, index) => ({
                label: label,
                newValue: data.newValues[index],
                oldValue: data.oldValues[index],
                change: data.newValues[index] - data.oldValues[index]
            })).sort((a, b) => a.change - b.change);

            const labels = sortedData.map(item => item.label);
            const values = sortedData.map(item => item.change);
            const formattedValues = sortedData.map(item => `${item.oldValue}% → ${item.newValue}%`);

            renderBarChart('relative-ownership', labels, values, formattedValues);
        })
        .catch(error => console.error('Error fetching relative ownership data:', error));
}
