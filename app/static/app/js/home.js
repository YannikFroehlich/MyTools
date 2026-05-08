document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("google-search-form");
    const input = document.getElementById("google-search-input");
    const suggestionsBox = document.getElementById("suggestions-box");

    const shortcutModal = document.getElementById("shortcut-modal");
    const openShortcutModalButtons = document.querySelectorAll(".open-shortcut-modal");
    const closeShortcutModalButton = document.getElementById("close-shortcut-modal");
    const shortcutSectionIdInput = document.getElementById("shortcut-section-id");
    const shortcutModalSectionName = document.getElementById("shortcut-modal-section-name");

    const sectionModal = document.getElementById("section-modal");
    const openSectionModalButton = document.getElementById("open-section-modal");
    const closeSectionModalButton = document.getElementById("close-section-modal");

    let suggestions = [];
    let currentFirstSuggestion = "";

    function hideSuggestions() {
        if (suggestionsBox) {
            suggestionsBox.innerHTML = "";
            suggestionsBox.style.display = "none";
        }

        currentFirstSuggestion = "";
    }

    function focusSearchInput() {
        if (input && !shortcutModal?.classList.contains("show") && !sectionModal?.classList.contains("show")) {
            input.focus();
        }
    }

    setTimeout(focusSearchInput, 100);

    fetch("/static/app/data/suggestions.json")
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP Fehler: ${response.status}`);
            }

            return response.json();
        })
        .then(data => {
            if (Array.isArray(data)) {
                suggestions = data;
            } else {
                console.error("suggestions.json muss ein Array sein.");
                suggestions = [];
            }
        })
        .catch(error => {
            console.error("Fehler beim Laden der Suggestions:", error);
            suggestions = [
                "Wetter heute",
                "Google Maps",
                "YouTube",
                "Twitch",
                "GitHub",
                "Django Dokumentation",
                "Python Tutorial",
                "OpenWeather API",
                "HTML CSS JavaScript",
                "ChatGPT",
                "Fritzbox VPN einrichten",
                "CasaOS installieren",
                "WireGuard Easy CasaOS"
            ];
        });

    function getFilteredSuggestions(value) {
        const searchValue = value.toLowerCase().trim();

        if (!searchValue) {
            return [];
        }

        const startsWithMatches = suggestions.filter(item =>
            item.toLowerCase().startsWith(searchValue)
        );

        const includesMatches = suggestions.filter(item =>
            !item.toLowerCase().startsWith(searchValue) &&
            item.toLowerCase().includes(searchValue)
        );

        return [...startsWithMatches, ...includesMatches].slice(0, 8);
    }

    function renderSuggestions(value) {
        if (!suggestionsBox) {
            return;
        }

        suggestionsBox.innerHTML = "";
        currentFirstSuggestion = "";

        const filteredSuggestions = getFilteredSuggestions(value);

        if (filteredSuggestions.length === 0) {
            hideSuggestions();
            return;
        }

        currentFirstSuggestion = filteredSuggestions[0];

        filteredSuggestions.forEach((item, index) => {
            const suggestionItem = document.createElement("div");
            suggestionItem.classList.add("suggestion-item");

            if (index === 0) {
                suggestionItem.classList.add("active-suggestion");
            }

            const icon = document.createElement("i");
            icon.className = "fa-solid fa-magnifying-glass";

            const text = document.createElement("span");
            text.textContent = item;

            suggestionItem.appendChild(icon);
            suggestionItem.appendChild(text);

            suggestionItem.addEventListener("click", () => {
                if (!input) {
                    return;
                }

                input.value = item;
                hideSuggestions();
                searchGoogle(item);
            });

            suggestionsBox.appendChild(suggestionItem);
        });

        suggestionsBox.style.display = "block";
    }

    function searchGoogle(query) {
        const trimmedQuery = query.trim();

        if (!trimmedQuery) {
            return;
        }

        window.location.href = `https://www.google.com/search?q=${encodeURIComponent(trimmedQuery)}`;
    }

    if (input) {
        input.addEventListener("input", () => {
            renderSuggestions(input.value);
        });

        input.addEventListener("keydown", (event) => {
            if (event.key === "Tab" && currentFirstSuggestion) {
                event.preventDefault();

                input.value = currentFirstSuggestion;
                hideSuggestions();
            }

            if (event.key === "Escape") {
                hideSuggestions();
            }

            if (event.key === "Enter") {
                hideSuggestions();
            }
        });
    }

    if (form) {
        form.addEventListener("submit", (event) => {
            event.preventDefault();

            if (input) {
                searchGoogle(input.value);
            }
        });
    }

    document.addEventListener("click", (event) => {
        if (form && !form.contains(event.target)) {
            hideSuggestions();
        }
    });

    openShortcutModalButtons.forEach(button => {
        button.addEventListener("click", () => {
            const sectionId = button.dataset.sectionId;
            const sectionName = button.dataset.sectionName;

            hideSuggestions();

            if (input) {
                input.blur();
            }

            if (shortcutSectionIdInput) {
                shortcutSectionIdInput.value = sectionId;
            }

            if (shortcutModalSectionName) {
                shortcutModalSectionName.textContent = `für "${sectionName}"`;
            }

            if (shortcutModal) {
                shortcutModal.classList.add("show");
            }
        });
    });

    if (closeShortcutModalButton && shortcutModal) {
        closeShortcutModalButton.addEventListener("click", () => {
            shortcutModal.classList.remove("show");
            setTimeout(focusSearchInput, 100);
        });

        shortcutModal.addEventListener("click", (event) => {
            if (event.target === shortcutModal) {
                shortcutModal.classList.remove("show");
                setTimeout(focusSearchInput, 100);
            }
        });
    }

    if (openSectionModalButton && sectionModal) {
        openSectionModalButton.addEventListener("click", () => {
            hideSuggestions();

            if (input) {
                input.blur();
            }

            sectionModal.classList.add("show");
        });
    }

    if (closeSectionModalButton && sectionModal) {
        closeSectionModalButton.addEventListener("click", () => {
            sectionModal.classList.remove("show");
            setTimeout(focusSearchInput, 100);
        });

        sectionModal.addEventListener("click", (event) => {
            if (event.target === sectionModal) {
                sectionModal.classList.remove("show");
                setTimeout(focusSearchInput, 100);
            }
        });
    }
});