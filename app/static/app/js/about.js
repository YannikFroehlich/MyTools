document.addEventListener("DOMContentLoaded", () => {
    const cards = document.querySelectorAll(
        ".about-hero-text, .about-hero-card, .about-stat-card, .about-card, .about-timeline"
    );

    cards.forEach((card) => {
        card.addEventListener("mousemove", (event) => {
            const rect = card.getBoundingClientRect();

            const x = event.clientX - rect.left;
            const y = event.clientY - rect.top;

            card.style.setProperty("--mouse-x", `${x}px`);
            card.style.setProperty("--mouse-y", `${y}px`);
        });
    });

    const timelineItems = document.querySelectorAll(".timeline-item");

    timelineItems.forEach((item, index) => {
        item.style.opacity = "0";
        item.style.transform = "translateY(12px)";
        item.style.transition = "opacity 0.35s ease, transform 0.35s ease";

        setTimeout(() => {
            item.style.opacity = "1";
            item.style.transform = "translateY(0)";
        }, 300 + index * 100);
    });
});