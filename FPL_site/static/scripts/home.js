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

    function updateLastUpdatedTime() {
        const now = new Date();
        const hours = String(now.getHours()).padStart(2, '0');
        const minutes = String(now.getMinutes()).padStart(2, '0');
        lastUpdatedTime.textContent = `${hours}:${minutes}`;
    }

    function applyCustomClasses(chartId) {
        const chartContainer = document.getElementById(chartId);
        const svg = chartContainer.querySelector('svg');

        if (svg) {
            // Example of adding classes
            svg.classList.add('custom-svg');
            const bars = svg.querySelectorAll('path'); // Bars in the chart
            bars.forEach((bar, index) => {
                bar.classList.add('custom-bar');
                if (index === 9) {
                    bar.classList.add('primary-bar');
                }
            });

            const labels = svg.querySelectorAll('text');
            labels.forEach(label => {
                label.classList.add('custom-label');
            });

            // Adjust SVG width to fill available space
            svg.setAttribute('width', '100%');
            svg.setAttribute('height', '400');
        }
    }

    function truncateLabel(label, maxLength = 20) {
        return label.length > maxLength ? label.substring(0, maxLength - 3) + '...' : label;
    }

    function formatNumber(value) {
        if (window.innerWidth <= 768) { // Mobile view
            return (value / 1000000).toFixed(2) + 'M';
        }
        return value.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    }

    function formatOwnership(oldValue, newValue) {
        return `${oldValue}% \u2192 ${newValue}%`; // Unicode right arrow
    }

    function fetchChartData(url, chartId) {
        fetch(url)
            .then(response => response.json())
            .then(data => {
                if (chartId === 'net-transfers') {
                    if (!data.labels || !data.values) {
                        console.error('Invalid data format:', data);
                        return;
                    }

                    const sortedData = data.labels.map((label, index) => ({
                        label: label,
                        value: data.values[index]
                    })).sort((a, b) => a.value - b.value);

                    const labels = sortedData.map(item => truncateLabel(item.label));
                    const values = sortedData.map(item => item.value);
                    const formattedValues = sortedData.map(item => formatNumber(item.value));

                    renderChart(chartId, labels, values, formattedValues);
                } else if (chartId === 'relative-ownership') {
                    if (!data.labels || !data.oldValues || !data.newValues) {
                        console.error('Invalid data format:', data);
                        return;
                    }

                    const sortedData = data.labels.map((label, index) => ({
                        label: label,
                        newValue: data.newValues[index],
                        oldValue: data.oldValues[index],
                        change: data.newValues[index] - data.oldValues[index]
                    })).sort((a, b) => a.change - b.change);

                    const labels = sortedData.map(item => truncateLabel(item.label));
                    const values = sortedData.map(item => item.change);
                    const formattedValues = sortedData.map(item => formatOwnership(item.oldValue, item.newValue));

                    renderChart(chartId, labels, values, formattedValues);
                }
                lastUpdatedTimestamp = Date.now();
                updateLastUpdatedTime();
            })
            .catch(error => console.error('Error fetching chart data:', error));
    }

    function renderChart(chartId, labels, values, formattedValues) {
        const chartDom = document.getElementById(chartId);
        chartDom.style.width = '100%';
        chartDom.style.height = '400px';

        if (chartInstances[chartId]) {
            chartInstances[chartId].dispose();
        }
        chartInstances[chartId] = echarts.init(chartDom, null, { renderer: 'svg' });

        const option = {
            xAxis: {
                type: 'value',
                show: false,
                axisLabel: {
                    fontSize: 14,
                    fontFamily: 'inherit'
                }
            },
            yAxis: {
                type: 'category',
                data: labels,
                axisLabel: {
                    color: 'black',
                    fontSize: 14,
                    fontFamily: 'inherit',
                    padding: [0, 10, 0, 10], // Add padding to the left of the labels
                    overflow: 'truncate', // Truncate long labels
                    ellipsis: '...' // Show ellipsis for truncated labels
                },
                axisLine: {
                    show: false
                },
                axisTick: {
                    show: false
                }
            },
            series: [
                {
                    type: 'bar',
                    data: values,
                    barCategoryGap: '16px',
                    itemStyle: {
                        color: function (params) {
                            return params.dataIndex === 9 ? 'var(--primary-color)' : 'var(--black-20)';
                        },
                        emphasis: {
                            itemStyle: {
                                color: function (params) {
                                    return params.dataIndex === 9 ? 'var(--primary-color)' : 'var(--black-20)';
                                }
                            }
                        }
                    },
                    label: {
                        show: true,
                        position: 'right',
                        color: 'black',
                        formatter: function (params) {
                            return formattedValues[params.dataIndex];
                        },
                        fontSize: 14,
                        fontFamily: 'inherit'
                    }
                }
            ],
            grid: {
                left: window.innerWidth <= 768 ? (chartId === 'net-transfers' ? '10%' : '10%') : '3%', // Adjust left padding for mobile view
                right: window.innerWidth <= 768 ? (chartId === 'net-transfers' ? '10%' : '30%') : (chartId === 'relative-ownership' ? '20%' : '0%'), // Adjust right padding for mobile view
                bottom: '3%',
                top: '3%',
                containLabel: true
            }
        };

        chartInstances[chartId].setOption(option);
        chartInstances[chartId].on('finished', function () {
            applyCustomClasses(chartId);
        });
    }

    function initializeCharts() {
        fetchChartData('/api/net-transfers', 'net-transfers');
        fetchChartData('/api/relative-ownership', 'relative-ownership');
    }

    pills.forEach(pill => {
        pill.addEventListener('click', function () {
            // Remove active class from all pills
            pills.forEach(p => p.classList.remove('active'));
            // Add active class to the clicked pill
            this.classList.add('active');

            // Hide all charts and descriptions
            charts.forEach(chart => chart.classList.remove('active'));
            Object.values(descriptions).forEach(desc => desc.style.display = 'none');

            // Show the target chart and description
            const target = document.getElementById(this.dataset.target);
            target.classList.add('active');
            descriptions[this.dataset.target].style.display = 'block';

            // Ensure the target chart is properly sized
            fetchChartData(`/api/${this.dataset.target}`, this.dataset.target);
        });
    });

    initializeCharts();

    // Function to call the Flask endpoint
    function callUpdateEndpoint() {
        fetch('/api/update-data')
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                console.log(data.message);
                // Optionally, update the charts here if needed
                initializeCharts();
            })
            .catch(error => console.error('Error:', error));
    }

    // Function to check if user is active
    function isUserActive() {
        let lastActiveTime = Date.now();

        function updateActivity() {
            lastActiveTime = Date.now();
        }

        window.addEventListener('mousemove', updateActivity);
        window.addEventListener('keydown', updateActivity);

        setInterval(() => {
            if (Date.now() - lastActiveTime < 30000) { // User is active within the last 30 seconds
                callUpdateEndpoint();
            }
        }, 30000); // Call every 30 seconds
    }

    isUserActive();

    // Resize charts on window resize
    window.addEventListener('resize', function () {
        Object.keys(chartInstances).forEach(chartId => {
            chartInstances[chartId].resize();
        });
    });

    // Update the time display every second
    setInterval(updateLastUpdatedTime, 1000);
});
