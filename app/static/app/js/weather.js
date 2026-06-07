document.addEventListener("DOMContentLoaded", () => {
    console.log("weather.js geladen");

    /* ───────────────── SEARCH FOCUS ───────────────── */

    const searchInput = document.querySelector(".weather-search-form input");

    setTimeout(() => {
        if (searchInput) {
            searchInput.focus();
        }
    }, 100);

    if (searchInput) {
        searchInput.addEventListener("focus", () => {
            const form = searchInput.closest(".weather-search-form");
            if (form) {
                form.style.transition =
                    "box-shadow 0.3s ease, border-color 0.3s ease, transform 0.2s ease";
            }
        });
    }


    /* ───────────────── SERVER-SAVED LOCATIONS UX ───────────────── */

    const savedLocationsCard = document.querySelector(".saved-locations-card");
    const savedLocationButtons = document.querySelectorAll(".saved-location-button, .compact-location-button");
    const deleteLocationButtons = document.querySelectorAll(".saved-location-delete, .compact-location-delete");
    const defaultLocationButtons = document.querySelectorAll(".compact-location-default");
    const addLocationForm = document.querySelector(".saved-location-add-form");
    const addLocationInput = document.querySelector(".saved-location-add-input");
    const saveCurrentLocationForms = document.querySelectorAll(".save-current-location-form, .compact-save-current-form");

    /*
        Erwartete HTML-Struktur ungefähr:

        <div class="weather-card saved-locations-card">
            <h2>Gespeicherte Orte</h2>

            <div class="saved-location-list">
                <form method="GET">
                    <input type="hidden" name="city" value="{{ location.name }}">
                    <button class="saved-location-button" type="submit">
                        Berlin
                    </button>
                </form>

                <form method="POST">
                    {% csrf_token %}
                    <input type="hidden" name="action" value="delete_weather_location">
                    <input type="hidden" name="location_id" value="{{ location.id }}">
                    <button class="saved-location-delete" type="submit">
                        <i class="fa-solid fa-xmark"></i>
                    </button>
                </form>
            </div>

            <form method="POST" class="saved-location-add-form">
                {% csrf_token %}
                <input type="hidden" name="action" value="add_weather_location">
                <input class="saved-location-add-input" name="location_name">
                <button type="submit">Hinzufügen</button>
            </form>

            <form method="POST" class="save-current-location-form">
                {% csrf_token %}
                <input type="hidden" name="action" value="add_weather_location">
                <input type="hidden" name="location_name" value="{{ city }}">
                <button class="save-current-location-button" type="submit">
                    Aktuellen Ort speichern
                </button>
            </form>
        </div>
    */

    if (savedLocationsCard) {
        savedLocationsCard.style.opacity = "0";
        savedLocationsCard.style.transform = "translateY(16px)";
        savedLocationsCard.style.transition = "opacity 0.45s ease, transform 0.45s ease";

        setTimeout(() => {
            savedLocationsCard.style.opacity = "1";
            savedLocationsCard.style.transform = "translateY(0)";
        }, 120);
    }

    savedLocationButtons.forEach((button, index) => {
        button.style.opacity = "0";
        button.style.transform = "translateY(10px) scale(0.98)";
        button.style.transition =
            "opacity 0.35s ease, transform 0.35s ease, border-color 0.2s ease, background-color 0.2s ease";

        setTimeout(() => {
            button.style.opacity = "1";
            button.style.transform = "translateY(0) scale(1)";
        }, 170 + index * 55);

        button.addEventListener("click", () => {
            button.classList.add("is-loading");

            const icon = button.querySelector("i");
            if (icon) {
                icon.className = "fa-solid fa-spinner fa-spin";
            }
        });
    });

    deleteLocationButtons.forEach((button) => {
        button.addEventListener("click", (event) => {
            const locationName = button.dataset.locationName || "diesen Ort";
            const confirmed = confirm(`Möchtest du ${locationName} wirklich löschen?`);

            if (!confirmed) {
                event.preventDefault();
                return;
            }

            button.classList.add("is-deleting");
            button.disabled = true;

            const icon = button.querySelector("i");
            if (icon) {
                icon.className = "fa-solid fa-spinner fa-spin";
            }
        });
    });

    if (addLocationForm && addLocationInput) {
        addLocationForm.addEventListener("submit", (event) => {
            const value = addLocationInput.value.trim();

            if (!value) {
                event.preventDefault();
                addLocationInput.focus();
                addLocationInput.classList.add("input-shake");

                setTimeout(() => {
                    addLocationInput.classList.remove("input-shake");
                }, 450);

                return;
            }

            const submitButton = addLocationForm.querySelector("button[type='submit']");
            if (submitButton) {
                submitButton.disabled = true;
                submitButton.classList.add("is-loading");
                submitButton.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i>`;
            }
        });
    }

    saveCurrentLocationForms.forEach((form) => {
        form.addEventListener("submit", () => {
            const button = form.querySelector("button[type='submit']");
            if (!button) {
                return;
            }

            button.disabled = true;
            button.classList.add("is-loading");
            button.innerHTML = button.classList.contains("compact-save-current-button")
                ? `<i class="fa-solid fa-spinner fa-spin"></i>`
                : `<i class="fa-solid fa-spinner fa-spin"></i><span>Speichern...</span>`;
        });
    });

    defaultLocationButtons.forEach((button) => {
        button.addEventListener("click", () => {
            button.disabled = true;
            button.classList.add("is-loading");

            const icon = button.querySelector("i");
            if (icon) {
                icon.className = "fa-solid fa-spinner fa-spin";
            }
        });
    });


    /* ───────────────── TEMPERATUR-ZÄHLER-ANIMATION ───────────────── */

    const tempEl = document.querySelector(".temperature");

    if (tempEl) {
        const originalTemperatureText = tempEl.textContent.trim();
        const temperatureSuffix = originalTemperatureText.replace(/^[\d.,\-\s]+/, "") || "°C";
        const target = parseFloat(originalTemperatureText.replace(",", "."));

        if (!isNaN(target)) {
            let start = target - 12;
            const duration = 700;
            const startTime = performance.now();

            const tick = (now) => {
                const progress = Math.min((now - startTime) / duration, 1);
                const eased = 1 - Math.pow(1 - progress, 3);
                const current = Math.round(start + (target - start) * eased);

                tempEl.textContent = current + temperatureSuffix;

                if (progress < 1) {
                    requestAnimationFrame(tick);
                }
            };

            requestAnimationFrame(tick);
        }
    }


    /* ───────────────── DETAIL-ITEMS EINBLENDEN ───────────────── */

    const detailItems = document.querySelectorAll(".detail-item");

    detailItems.forEach((item, index) => {
        item.style.opacity = "0";
        item.style.transform = "translateX(14px)";
        item.style.transition = "opacity 0.4s ease, transform 0.4s ease";

        setTimeout(() => {
            item.style.opacity = "1";
            item.style.transform = "translateX(0)";
        }, 180 + index * 80);
    });


    /* ───────────────── HOURLY ITEMS EINBLENDEN ───────────────── */

    const hourlyItems = document.querySelectorAll(".hourly-item");

    hourlyItems.forEach((item, index) => {
        item.style.opacity = "0";
        item.style.transform = "translateY(12px)";
        item.style.transition = "opacity 0.35s ease, transform 0.35s ease";

        setTimeout(() => {
            item.style.opacity = "1";
            item.style.transform = "translateY(0)";
        }, 250 + index * 45);
    });


    /* ───────────────── FORECAST ITEMS EINBLENDEN ───────────────── */

    const forecastItems = document.querySelectorAll(".forecast-item");

    forecastItems.forEach((item, index) => {
        item.style.opacity = "0";
        item.style.transform = "translateY(14px)";
        item.style.transition = "opacity 0.4s ease, transform 0.4s ease";

        setTimeout(() => {
            item.style.opacity = "1";
            item.style.transform = "translateY(0)";
        }, 300 + index * 60);
    });


    /* ───────────────── WETTER-ICON HOVER ───────────────── */

    const weatherIcon = document.querySelector(".current-main img");

    if (weatherIcon) {
        weatherIcon.addEventListener("mouseenter", () => {
            weatherIcon.style.transition = "filter 0.3s ease, transform 0.3s ease";
            weatherIcon.style.filter =
                "drop-shadow(0 4px 24px rgba(var(--theme-accent-end-rgb), 0.65))";
            weatherIcon.style.transform = "scale(1.08)";
        });

        weatherIcon.addEventListener("mouseleave", () => {
            weatherIcon.style.filter =
                "drop-shadow(0 4px 16px rgba(var(--theme-accent-end-rgb), 0.35))";
            weatherIcon.style.transform = "scale(1)";
        });
    }


    /* ───────────────── SEARCH BUTTON RIPPLE ───────────────── */

    const searchBtn = document.querySelector(".weather-search-form button");

    if (searchBtn) {
        searchBtn.addEventListener("click", function () {
            const ripple = document.createElement("span");

            ripple.style.cssText = `
                position: absolute;
                border-radius: 50%;
                background: rgba(255, 255, 255, 0.35);
                width: 60px;
                height: 60px;
                left: 50%;
                top: 50%;
                transform: translate(-50%, -50%) scale(0);
                animation: rippleAnim 0.45s ease-out forwards;
                pointer-events: none;
            `;

            this.style.position = "relative";
            this.style.overflow = "hidden";
            this.appendChild(ripple);

            setTimeout(() => {
                ripple.remove();
            }, 500);
        });

        if (!document.getElementById("ripple-style")) {
            const style = document.createElement("style");
            style.id = "ripple-style";
            style.textContent = `
                @keyframes rippleAnim {
                    to {
                        transform: translate(-50%, -50%) scale(2.2);
                        opacity: 0;
                    }
                }

                .input-shake {
                    animation: inputShake 0.42s ease;
                }

                @keyframes inputShake {
                    0%, 100% {
                        transform: translateX(0);
                    }

                    20% {
                        transform: translateX(-6px);
                    }

                    40% {
                        transform: translateX(6px);
                    }

                    60% {
                        transform: translateX(-4px);
                    }

                    80% {
                        transform: translateX(4px);
                    }
                }
            `;

            document.head.appendChild(style);
        }
    }
});
