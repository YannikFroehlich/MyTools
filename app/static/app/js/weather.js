document.addEventListener("DOMContentLoaded", () => {

    /* ── Search Focus ── */
    const searchInput = document.querySelector(".weather-search-form input");
    if (searchInput) {
        searchInput.addEventListener("focus", () => {
            searchInput.parentElement.style.transition = "box-shadow 0.3s ease, border-color 0.3s ease, transform 0.2s ease";
        });
    }

    /* ── Temperatur-Zähler-Animation ── */
    const tempEl = document.querySelector(".temperature");
    if (tempEl) {
        const target = parseFloat(tempEl.textContent);
        if (!isNaN(target)) {
            let start = target - 12;
            const duration = 700;
            const startTime = performance.now();

            const tick = (now) => {
                const progress = Math.min((now - startTime) / duration, 1);
                const eased = 1 - Math.pow(1 - progress, 3);
                const current = Math.round(start + (target - start) * eased);
                tempEl.textContent = current + "°C";
                if (progress < 1) requestAnimationFrame(tick);
            };
            requestAnimationFrame(tick);
        }
    }

    /* ── Detail-Items: gestaffelt einblenden ── */
    const detailItems = document.querySelectorAll(".detail-item");
    detailItems.forEach((item, i) => {
        item.style.opacity = "0";
        item.style.transform = "translateX(14px)";
        item.style.transition = "opacity 0.4s ease, transform 0.4s ease";
        setTimeout(() => {
            item.style.opacity = "1";
            item.style.transform = "translateX(0)";
        }, 180 + i * 80);
    });

    /* ── Hourly Items: gestaffelt einblenden ── */
    const hourlyItems = document.querySelectorAll(".hourly-item");
    hourlyItems.forEach((item, i) => {
        item.style.opacity = "0";
        item.style.transform = "translateY(12px)";
        item.style.transition = "opacity 0.35s ease, transform 0.35s ease";
        setTimeout(() => {
            item.style.opacity = "1";
            item.style.transform = "translateY(0)";
        }, 250 + i * 45);
    });

    /* ── Forecast Items: gestaffelt einblenden ── */
    const forecastItems = document.querySelectorAll(".forecast-item");
    forecastItems.forEach((item, i) => {
        item.style.opacity = "0";
        item.style.transform = "translateY(14px)";
        item.style.transition = "opacity 0.4s ease, transform 0.4s ease";
        setTimeout(() => {
            item.style.opacity = "1";
            item.style.transform = "translateY(0)";
        }, 300 + i * 60);
    });

    /* ── Sun Items: Fade-In ── */
    const sunItems = document.querySelectorAll(".sun-item");
    sunItems.forEach((item, i) => {
        item.style.opacity = "0";
        item.style.transform = "scale(0.9)";
        item.style.transition = "opacity 0.45s ease, transform 0.45s cubic-bezier(0.34, 1.56, 0.64, 1)";
        setTimeout(() => {
            item.style.opacity = "1";
            item.style.transform = "scale(1)";
        }, 400 + i * 100);
    });

    /* ── Wetter-Icon: Glow-Pulse beim Hover ── */
    const weatherIcon = document.querySelector(".current-main img");
    if (weatherIcon) {
        weatherIcon.addEventListener("mouseenter", () => {
            weatherIcon.style.transition = "filter 0.3s ease, transform 0.3s ease";
            weatherIcon.style.filter = "drop-shadow(0 4px 24px rgba(79, 183, 255, 0.65))";
            weatherIcon.style.transform = "scale(1.08)";
        });
        weatherIcon.addEventListener("mouseleave", () => {
            weatherIcon.style.filter = "drop-shadow(0 4px 16px rgba(79, 183, 255, 0.35))";
            weatherIcon.style.transform = "scale(1)";
        });
    }

    /* ── Search Button: Ripple-Effekt ── */
    const searchBtn = document.querySelector(".weather-search-form button");
    if (searchBtn) {
        searchBtn.addEventListener("click", function (e) {
            const ripple = document.createElement("span");
            ripple.style.cssText = `
                position: absolute;
                border-radius: 50%;
                background: rgba(255,255,255,0.35);
                width: 60px; height: 60px;
                left: 50%; top: 50%;
                transform: translate(-50%, -50%) scale(0);
                animation: rippleAnim 0.45s ease-out forwards;
                pointer-events: none;
            `;
            this.style.position = "relative";
            this.style.overflow = "hidden";
            this.appendChild(ripple);
            setTimeout(() => ripple.remove(), 500);
        });

        if (!document.getElementById("ripple-style")) {
            const style = document.createElement("style");
            style.id = "ripple-style";
            style.textContent = `
                @keyframes rippleAnim {
                    to { transform: translate(-50%, -50%) scale(2.2); opacity: 0; }
                }
            `;
            document.head.appendChild(style);
        }
    }

});