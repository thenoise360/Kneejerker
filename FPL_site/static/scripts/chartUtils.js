/***** chartUtils.js *****/
import { truncateLabel } from './utils.js'; // Only if you actually need label truncation

/**
 * Renders a bar chart using ECharts.
 * @param {string} chartId - The DOM element ID to render the chart into.
 * @param {string[]} labels - Category labels on the y-axis.
 * @param {number[]} values - Numeric values on the x-axis.
 * @param {string[]} formattedValues - The text you want to display on each bar.
 */
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

    // If this chart is specifically the "net-transfers" one, use that grid, else use "relativeOwnership"
    const grid = (chartId === 'net-transfers') ? gridSettings.netTransfers : gridSettings.relativeOwnership;

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
            data: labels.map(label => truncateLabel(label)), // If you want to truncate long labels
            axisLabel: {
                color: 'black',
                fontSize: 14,
                fontFamily: 'inherit',
                padding: [0, 10, 0, 10],
                overflow: 'truncate',
                ellipsis: '...'
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
                // NORMAL state color
                itemStyle: {
                    color: function (params) {
                        return params.dataIndex === maxIndex
                          ? 'var(--primary-color)'
                          : 'var(--black-20)';
                      }
                    },
                    emphasis: {
                      itemStyle: {
                        color: 'inherit', 
                        opacity: 0.8
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
    applyCustomClasses(chartId, 'bar');  // Apply custom SVG classes after setting options

    // Ensure the chart is resized correctly after rendering
    chart.resize();
}

/**
 * Applies custom CSS classes to ECharts’ SVG elements for consistent styling.
 * @param {string} chartId - The DOM element ID where the chart is rendered.
 * @param {string} chartType - Either 'bar' or 'line', used to apply specific classes.
 */
export function applyCustomClasses(chartId, chartType) {
    const chartContainer = document.getElementById(chartId);
    const svg = chartContainer.querySelector('svg');

    if (svg) {
        svg.classList.add('custom-svg');

        if (chartType === 'bar') {
            // Target only the actual bars, not the background rect
            const bars = svg.querySelectorAll('g > rect:not([width="100%"])');
            bars.forEach((bar, index) => {
                bar.classList.add('custom-bar');
                // Example: highlight the 10th bar
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

        // Make the SVG fill the container
        svg.setAttribute('width', '100%');
        svg.setAttribute('height', '400');
    }
}

/**
 * Renders a line chart using ECharts, for player vs. average scores over multiple weeks.
 * @param {string} chartId - The DOM element ID to render the chart into.
 * @param {number[]} weeks - The x-axis categories (e.g. [15,16,17,18,19] or [1,2,3,4,5]).
 * @param {number[]} scores - The player's point totals for each corresponding week.
 * @param {number[]} averageScores - The average point totals for each corresponding week.
 * @param {number[]} difficulty - The fixture difficulty for each week, in the same order as `weeks`.
 * @param {number[]} allScores - All players’ scores used to set a max bound on the y-axis.
 * @param {string} playerName - The name shown in the tooltip (and series label).
 */
export function renderLineChart(chartId, weeks, scores, averageScores, difficulty, allScores, playerName) {
    const chartDom = document.getElementById(chartId);
    if (typeof echarts === 'undefined') {
        console.error('ECharts is not defined. Make sure you have imported ECharts in your HTML.');
        return;
    }

    // Calculate a "nice" max for the Y-axis
    const maxScore = Math.ceil(Math.max(...allScores) / 5) * 5;

    // Make the container 100% width for responsiveness
    chartDom.style.width = '100%';

    // Initialize ECharts instance
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
            // A custom formatter that shows player points, average points, and difficulty
            formatter: function (params) {
                if (!params.length) return '';

                // The first series is the player
                const playerData = params[0].data ?? 'N/A';
                // The second series is average (if it exists)
                const avgData = (params[1] && params[1].data != null)
                  ? params[1].data
                  : 'N/A';

                // Instead of using (axisValue - 1), find the index of axisValue in `weeks`.
                const axisVal = params[0].axisValue;
                const weekIndex = weeks.indexOf(Number(axisVal));

                // If we found a matching index, grab the difficulty, otherwise "N/A"
                const difficultyValue = (weekIndex !== -1 && difficulty[weekIndex] != null)
                  ? difficulty[weekIndex]
                  : 'N/A';

                // Player’s seriesName is your `playerName`
                const playerLabel = params[0].seriesName || 'Player';

                return `
                    <div style="line-height:1.5;">
                        <div style="display:flex; justify-content: space-between;">
                            <span class="category-label">${playerLabel}:</span>
                            <span class="category-value">${playerData} points</span>
                        </div>
                        <div style="display:flex; justify-content: space-between;">
                            <span class="category-label">Avg:</span>
                            <span class="category-value">${avgData} points</span>
                        </div>
                        <hr style="border-top:1px solid #999;margin: 8px 0;">
                        <div style="display:flex; justify-content: space-between;">
                            <span class="category-label">Difficulty:</span>
                            <span class="category-value">${difficultyValue}</span>
                        </div>
                    </div>
                `;
            },
            // Position logic to keep the tooltip within chart bounds
            position: function (pos, params, dom, rect, size) {
                if (!rect || !dom) return;

                const [pointX] = pos;
                const tooltipWidth = size.contentSize[0];
                const chartWidth = size.viewSize[0];

                let xPos;
                if (pointX < tooltipWidth / 2) {
                    xPos = 0;
                } else if (pointX > chartWidth - tooltipWidth / 2) {
                    xPos = chartWidth - tooltipWidth;
                } else {
                    xPos = pointX - tooltipWidth / 2;
                }

                // Place tooltip just above the line, if rect is known
                const yPos = rect ? rect.y - dom.offsetHeight - 10 : 0;
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
            max: maxScore,
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
                show: false // remove the horizontal lines
            }
        },
        series: [
            {
                name: playerName,
                type: 'line',
                data: scores,
                smooth: true,
                lineStyle: {
                    color: '#17A398', // normal line color
                    width: 2,
                    type: 'solid'
                },
                itemStyle: {
                    opacity: 0 // hidden dots unless hovered
                },
                emphasis: {
                    itemStyle: {
                        // Dot color on hover
                        opacity: 0.8,
                        color: '#17A398',
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
                        // Dot color for average line on hover
                        opacity: 0.8,
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

    // Optional: highlight behavior on hover
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

    // Render with our specified options
    myChart.setOption(option);

    // Make the chart responsive
    window.addEventListener('resize', () => {
        myChart.resize();
    });
    myChart.resize();

    // Apply custom line chart classes after the chart is set
    applyCustomClasses(chartId, 'line');
}
