document.addEventListener("DOMContentLoaded", () => {
    console.log("App.js is linked and running!");
    console.log("JavaScript file is loaded!");

    // Add a button to change the background color
    const colorButton = document.createElement("button");
    colorButton.textContent = "Change Background Color";
    document.body.appendChild(colorButton);

    colorButton.addEventListener("click", () => {
        const randomColor = `#${Math.floor(Math.random() * 16777215).toString(16)}`;
        document.body.style.backgroundColor = randomColor;
    });

    // Add a real-time clock
    const clock = document.createElement("div");
    clock.style.fontSize = "2rem";
    clock.style.marginTop = "20px";
    document.body.appendChild(clock);

    function updateClock() {
        const now = new Date();
        clock.textContent = now.toLocaleTimeString();
    }

    setInterval(updateClock, 1000);
    updateClock(); // Initialize clock immediately
});