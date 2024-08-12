import { truncateLabel } from './utils.js'; // Make sure to import the truncateLabel function

export function renderBarChart(chartId, labels, values, formattedValues) {
    const chartDom = document.getElementById(chartId);
    const chart = echarts.init(chartDom, null, { renderer: 'svg' });

    const maxIndex = values.indexOf(Math.max(...values));  // Identify the bar with the maximum value

    // Define grid settings for different chart types
    const gridSettings = {
        netTransfers: {
            left: window.innerWidth <= 768 ? '8%' : '3%',
            right: window.innerWidth <= 768 ? '15%' : '3%'
        },
        relativeOwnership: {
            left: window.innerWidth <= 768 ? '10%' : '3%',
            right: window.innerWidth <= 768 ? '30%' : '20%'
        }
    };

    const grid = chartId === 'net-transfers' ? gridSettings.netTransfers : gridSettings.relativeOwnership;

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
            data: labels.map(label => truncateLabel(label)),  // Truncate labels based on length
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
                barCategoryGap: '4px',
                itemStyle: {
                    color: function (params) {
                        return params.dataIndex === maxIndex ? 'var(--primary-color)' : 'var(--black-20)';
                    },
                    emphasis: {
                        itemStyle: {
                            color: function (params) {
                                return params.dataIndex === maxIndex ? 'var(--primary-color)' : 'var(--black-20)';
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
            left: grid.left,
            right: grid.right,
            bottom: '3%',
            top: '3%',
            containLabel: true
        }
    };

    chart.setOption(option);
    applyCustomClasses(chartId, 'bar');  // Apply custom styles after setting the chart options

    // Ensure the chart is resized correctly after rendering
    chart.resize();
}

export function applyCustomClasses(chartId, chartType) {
    const chartContainer = document.getElementById(chartId);
    const svg = chartContainer.querySelector('svg');

    if (svg) {
        svg.classList.add('custom-svg');

        if (chartType === 'bar') {
            const bars = svg.querySelectorAll('g > rect:not([width="100%"])'); // Target only bars, excluding full-width background rect
            bars.forEach((bar, index) => {
                bar.classList.add('custom-bar');
                if (index === 9) {
                    bar.classList.add('primary-bar');
                }
            });
        } else if (chartType === 'line') {
            const lines = svg.querySelectorAll('.echarts-line');
            lines.forEach((line, index) => {
                if (index === 0) {
                    line.classList.add('custom-line', 'player-line');
                } else if (index === 1) {
                    line.classList.add('custom-line', 'average-line');
                }
            });

            const areas = svg.querySelectorAll('.echarts-area');
            areas.forEach(area => {
                area.classList.add('custom-area');
            });

            const hoverLabels = svg.querySelectorAll('.echarts-tooltip');
            hoverLabels.forEach(label => {
                label.classList.add('custom-hover-label');
            });
        }

        const labels = svg.querySelectorAll('text');
        labels.forEach(label => {
            label.classList.add('custom-label');
        });

        svg.setAttribute('width', '100%');
        svg.setAttribute('height', '400');
    }
}
export function renderLineChart(chartId, weeks, scores, averageScores, difficulty, allScores, playerName) {
    const chartDom = document.getElementById(chartId);
    if (typeof echarts === 'undefined') {
        console.error('ECharts is not defined. Ensure ECharts is included in your HTML.');
        return;
    }

    const maxScore = Math.ceil(Math.max(...allScores) / 5) * 5;

    // Ensure the container width is 100% for responsiveness
    chartDom.style.width = '100%';

    // Initialize the chart instance
    const myChart = echarts.init(chartDom, null, { renderer: 'svg' });

    const option = {
        tooltip: {
            trigger: 'axis',
            backgroundColor: '#4D4D4D',
            borderColor: '#4D4D4D',
            textStyle: {
                color: '#FFFFFF',
                fontSize: 14
            },
            formatter: function (params) {
                if (!params.length) return ''; // Ensure params is valid

                const playerData = params[0].data || 'N/A';
                const avgData = params[1]?.data || 'N/A'; // Check if the average data exists
                const weekIndex = params[0].axisValue - 1;

                // Check if difficulty exists for the given weekIndex
                const difficultyValue = (difficulty && difficulty[weekIndex] !== undefined)
                    ? difficulty[weekIndex]
                    : 'N/A';

                return `
                    <div style="line-height:1.5;">
                        <div style="display:flex; justify-content: space-between;">
                            <span>${params[0].seriesName || 'Player'}</span>
                            <span>${playerData} points</span>
                        </div>
                        <div style="display:flex; justify-content: space-between;">
                            <span>${params[1]?.seriesName || 'Avg'}</span>
                            <span>${avgData} points</span>
                        </div>
                        <hr style="border-top:1px solid #999;margin: 8px 0;">
                        <div style="display:flex; justify-content: space-between;">
                            <span>Difficulty</span>
                            <span>${difficultyValue}</span>
                        </div>
                    </div>`;
            },
            position: function (pos, params, dom, rect, size) {
                if (!rect || !dom) return; // Safeguard to avoid accessing properties of null

                const [pointX] = pos;  // Coordinates of the tooltip
                const tooltipWidth = size.contentSize[0];  // Tooltip width
                const chartWidth = size.viewSize[0];  // Chart width

                // Determine the position of the tooltip
                let xPos;
                if (pointX < tooltipWidth / 2) {
                    xPos = 0; // Align the left edge of the tooltip with the line for the first value
                } else if (pointX > chartWidth - tooltipWidth / 2) {
                    xPos = chartWidth - tooltipWidth; // Align the right edge of the tooltip with the line for the last value
                } else {
                    xPos = pointX - tooltipWidth / 2; // Center the tooltip over the line
                }

                const yPos = rect ? rect.y - dom.offsetHeight - 10 : 0; // Adjust yPos safely
                return [xPos, yPos];
            }
        },
        xAxis: {
            type: 'category',
            data: weeks,
            boundaryGap: false,
            axisLine: {
                lineStyle: {
                    color: '#999',
                    width: 2
                }
            },
            axisTick: {
                show: false
            },
            axisLabel: {
                color: '#333',
                fontSize: 12
            }
        },
        yAxis: {
            type: 'value',
            max: maxScore,  // Use the calculated maxScore for the Y-axis
            axisLine: {
                lineStyle: {
                    color: '#999',
                    width: 2
                }
            },
            axisTick: {
                show: false
            },
            axisLabel: {
                color: '#333',
                fontSize: 12
            },
            splitLine: {
                show: false  // Remove horizontal lines
            }
        },
        series: [
            {
                name: playerName,
                type: 'line',
                data: scores,
                smooth: true,
                lineStyle: {
                    color: '#17A398',
                    width: 2,
                    type: 'solid'
                },
                itemStyle: {
                    opacity: 0
                },
                emphasis: {
                    itemStyle: {
                        opacity: 1,
                        color: '#FF5733',
                        borderColor: '#333',
                        borderWidth: 2
                    }
                },
                areaStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: 'rgba(23, 163, 152, 0.8)' },
                        { offset: 1, color: 'rgba(23, 163, 152, 0.4)' }
                    ])
                }
            },
            {
                name: 'Average',
                type: 'line',
                data: averageScores,
                lineStyle: {
                    type: 'dashed',
                    color: 'rgb(102, 102, 102)',
                    width: 2
                },
                itemStyle: {
                    opacity: 0
                },
                emphasis: {
                    itemStyle: {
                        opacity: 1,
                        color: 'rgb(102, 102, 102)'
                    }
                }
            }
        ],
        grid: {
            left: '10%',
            right: '10%',
            bottom: '10%',
            top: '20%',
            containLabel: true
        }
    };

    // Add hover and out event handling
    myChart.on('mouseover', function (params) {
        if (params.componentType === 'series') {
            myChart.dispatchAction({
                type: 'highlight',
                seriesIndex: params.seriesIndex,
                dataIndex: params.dataIndex
            });
        }
    });

    myChart.on('mouseout', function (params) {
        if (params.componentType === 'series') {
            myChart.dispatchAction({
                type: 'downplay',
                seriesIndex: params.seriesIndex,
                dataIndex: params.dataIndex
            });
        }
    });

    myChart.setOption(option);

    // Resize the chart to fit its container
    window.addEventListener('resize', () => {
        myChart.resize();
    });

    myChart.resize();  // Initial resize to ensure proper fit
}
