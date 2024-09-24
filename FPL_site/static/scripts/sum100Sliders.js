document.addEventListener("DOMContentLoaded", function() {
    const sliders = document.querySelectorAll('.form-range.slider');
    const labels = document.querySelectorAll('.slider-label-value');
    const submitButton = document.getElementById('submit-btn');

    // Function to update slider labels
    function updateLabels() {
        sliders.forEach((slider, index) => {
            labels[index].textContent = `${Math.round(slider.value)}%`;
        });
    }

    // Function to update the background of all sliders dynamically
    function updateAllSlidersBackground() {
        sliders.forEach(slider => {
            const value = (slider.value - slider.min) / (slider.max - slider.min) * 100;
            // Set the background gradient to fill the slider based on the value
            slider.style.backgroundImage = `linear-gradient(to right, var(--primary-color) ${value}%, var(--black-30) ${value}%)`;
        });
    }

    // Function to enable/disable the submit button
    function checkButtonState() {
        const total = Array.from(sliders).reduce((acc, slider) => acc + parseInt(slider.value), 0);
        submitButton.disabled = total !== 100;
    }

    // Function to adjust sliders proportionally when one slider changes
    function adjustSliders(changedSlider) {
        const numSliders = sliders.length;
        const currentSliderValue = parseInt(changedSlider.value);
        const remainingPercentage = 100 - currentSliderValue;

        // Get all other sliders except the changed one
        const otherSliders = Array.from(sliders).filter(slider => slider !== changedSlider);

        // Calculate the total of other sliders
        let otherSlidersTotal = otherSliders.reduce((acc, slider) => acc + parseInt(slider.value), 0);

        // If the other sliders total to 0, distribute the remaining percentage equally
        if (otherSlidersTotal === 0) {
            const equalValue = remainingPercentage / otherSliders.length;
            otherSliders.forEach(slider => {
                slider.value = Math.round(equalValue);
            });
        } else {
            // Adjust other sliders proportionally
            otherSliders.forEach(slider => {
                const currentValue = parseInt(slider.value);
                const newValue = (remainingPercentage * currentValue) / otherSlidersTotal;
                slider.value = Math.max(0, Math.min(100, Math.round(newValue)));
            });
        }

        // After adjustments, update everything
        updateLabels();
        updateAllSlidersBackground(); // Ensure all sliders get their background updated
        checkButtonState();
    }

    // Add event listener to each slider
    sliders.forEach(slider => {
        // Initial background setup for all sliders
        updateAllSlidersBackground();

        // Handle slider input event
        slider.addEventListener('input', function() {
            adjustSliders(slider);  // Adjust sliders dynamically
        });
    });

    // Initial setup
    updateLabels();
    checkButtonState();
});
