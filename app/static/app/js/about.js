document.addEventListener("DOMContentLoaded", () => {
    const animatedItems = document.querySelectorAll(
        ".about-hero-copy, .about-hero-panel, .about-principle, .about-section, .about-info-panel"
    );

    animatedItems.forEach((item, index) => {
        item.style.opacity = "0";
        item.style.transform = "translateY(14px)";
        item.style.transition = "opacity 0.42s ease, transform 0.42s ease";

        setTimeout(() => {
            item.style.opacity = "1";
            item.style.transform = "translateY(0)";
        }, 80 + index * 45);
    });

    const linkCards = document.querySelectorAll(".about-link-card");

    linkCards.forEach((card, index) => {
        card.style.opacity = "0";
        card.style.transform = "translateY(10px)";
        card.style.transition = "opacity 0.32s ease, transform 0.32s ease, border-color 0.18s ease, box-shadow 0.18s ease, background-color 0.18s ease";

        setTimeout(() => {
            card.style.opacity = "1";
            card.style.transform = "translateY(0)";
        }, 260 + index * 24);
    });
});
