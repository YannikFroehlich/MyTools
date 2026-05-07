document.addEventListener("DOMContentLoaded", () => {

    /* ── Aktuelle Stunde markieren ── */
    const nowHour = new Date().getHours();
    const hourlyItems = document.querySelectorAll(".hourly-item");
    if (hourlyItems.length) {
        const hourTimes = [...hourlyItems].map(el =>
            parseInt(el.querySelector(".hour-time")?.textContent ?? "-1")
        );
        // Nächsten Stunden-Block finden
        let closest = 0;
        let minDiff = Infinity;
        hourTimes.forEach((h, i) => {
            const diff = Math.abs(h - nowHour);
            if (diff < minDiff) { minDiff = diff; closest = i; }
        });
        hourlyItems[closest]?.classList.add("is-now");
    }

    /* ── Temperatur-Zähler-Animation ── */
    const tempEl = document.querySelector(".temperature");
    if (tempEl) {
        // Wert sicher lesen (gradient text enthält nur Zahlen + °C)
        const raw = tempEl.textContent.replace("°C", "").trim();
        const target = parseFloat(raw);
        if (!isNaN(target)) {
            const start = target - 14;
            const duration = 750;
            const startTime = performance.now();

            const tick = (now) => {
                const progress = Math.min((now - startTime) / duration, 1);
                const eased = 1 - Math.pow(1 - progress, 3);
                const current = (start + (target - start) * eased).toFixed(1);
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
        item.style.transform = "translateX(16px)";
        item.style.transition = "opacity 0.4s ease, transform 0.4s ease";
        setTimeout(() => {
            item.style.opacity = "1";
            item.style.transform = "translateX(0)";
        }, 200 + i * 80);
    });

    /* ── Hourly Items: gestaffelt einblenden ── */
    hourlyItems.forEach((item, i) => {
        item.style.opacity = "0";
        item.style.transform = "translateY(14px)";
        item.style.transition = "opacity 0.38s ease, transform 0.38s ease";
        setTimeout(() => {
            item.style.opacity = "1";
            item.style.transform = "translateY(0)";
        }, 260 + i * 40);
    });

    /* ── Forecast Items: gestaffelt einblenden ── */
    const forecastItems = document.querySelectorAll(".forecast-item");
    forecastItems.forEach((item, i) => {
        item.style.opacity = "0";
        item.style.transform = "translateY(16px)";
        item.style.transition = "opacity 0.4s ease, transform 0.4s ease";
        setTimeout(() => {
            item.style.opacity = "1";
            item.style.transform = "translateY(0)";
        }, 320 + i * 55);
    });

    /* ── Sun Items: Fade-In mit Scale ── */
    const sunItems = document.querySelectorAll(".sun-item");
    sunItems.forEach((item, i) => {
        item.style.opacity = "0";
        item.style.transform = "scale(0.88)";
        item.style.transition = "opacity 0.5s ease, transform 0.5s cubic-bezier(0.34, 1.56, 0.64, 1)";
        setTimeout(() => {
            item.style.opacity = "1";
            item.style.transform = "scale(1)";
        }, 420 + i * 110);
    });

    /* ── Wetter-Icon: Glow-Pulse beim Hover ── */
    const weatherIcon = document.querySelector(".current-main img");
    if (weatherIcon) {
        weatherIcon.addEventListener("mouseenter", () => {
            weatherIcon.style.filter = "drop-shadow(0 4px 28px rgba(79, 183, 255, 0.7))";
            weatherIcon.style.transform = "scale(1.09)";
            weatherIcon.style.transition = "filter 0.3s ease, transform 0.3s cubic-bezier(0.34,1.56,0.64,1)";
        });
        weatherIcon.addEventListener("mouseleave", () => {
            weatherIcon.style.filter = "drop-shadow(0 4px 20px rgba(79, 183, 255, 0.45))";
            weatherIcon.style.transform = "scale(1)";
        });
    }

    /* ── Search Button: Ripple-Effekt ── */
    const searchBtn = document.querySelector(".weather-search-form button");
    if (searchBtn) {
        if (!document.getElementById("ripple-style")) {
            const style = document.createElement("style");
            style.id = "ripple-style";
            style.textContent = `
                @keyframes rippleAnim {
                    to { transform: translate(-50%, -50%) scale(2.4); opacity: 0; }
                }
            `;
            document.head.appendChild(style);
        }

        searchBtn.addEventListener("click", function () {
            const ripple = document.createElement("span");
            ripple.style.cssText = `
                position: absolute;
                border-radius: 50%;
                background: rgba(255,255,255,0.3);
                width: 64px; height: 64px;
                left: 50%; top: 50%;
                transform: translate(-50%, -50%) scale(0);
                animation: rippleAnim 0.5s ease-out forwards;
                pointer-events: none;
                z-index: 0;
            `;
            this.appendChild(ripple);
            setTimeout(() => ripple.remove(), 550);
        });
    }

    /* ── Suchleiste: Enter-Taste ── */
    const searchInput = document.querySelector(".weather-search-form input");
    if (searchInput) {
        // Fokus beim Laden wenn kein Wert
        if (!searchInput.value) searchInput.focus();
    }

});