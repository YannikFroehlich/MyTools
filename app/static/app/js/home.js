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

    const suggestions = [
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

    if (input) {
        input.focus();
    }

    function renderSuggestions(value) {
        suggestionsBox.innerHTML = "";

        const searchValue = value.toLowerCase().trim();

        if (!searchValue) {
            suggestionsBox.style.display = "none";
            return;
        }

        const filteredSuggestions = suggestions.filter(item =>
            item.toLowerCase().includes(searchValue)
        );

        if (filteredSuggestions.length === 0) {
            suggestionsBox.style.display = "none";
            return;
        }

        filteredSuggestions.forEach(item => {
            const suggestionItem = document.createElement("div");
            suggestionItem.classList.add("suggestion-item");

            suggestionItem.innerHTML = `
                <i class="fa-solid fa-magnifying-glass"></i>
                <span>${item}</span>
            `;

            suggestionItem.addEventListener("click", () => {
                input.value = item;
                suggestionsBox.style.display = "none";
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

    input.addEventListener("input", () => {
        renderSuggestions(input.value);
    });

    form.addEventListener("submit", (event) => {
        event.preventDefault();
        searchGoogle(input.value);
    });

    document.addEventListener("click", (event) => {
        if (!form.contains(event.target)) {
            suggestionsBox.style.display = "none";
        }
    });

    openShortcutModalButtons.forEach(button => {
        button.addEventListener("click", () => {
            const sectionId = button.dataset.sectionId;
            const sectionName = button.dataset.sectionName;

            shortcutSectionIdInput.value = sectionId;
            shortcutModalSectionName.textContent = `für "${sectionName}"`;

            shortcutModal.classList.add("show");
        });
    });

    if (closeShortcutModalButton && shortcutModal) {
        closeShortcutModalButton.addEventListener("click", () => {
            shortcutModal.classList.remove("show");
        });

        shortcutModal.addEventListener("click", (event) => {
            if (event.target === shortcutModal) {
                shortcutModal.classList.remove("show");
            }
        });
    }

    if (openSectionModalButton && closeSectionModalButton && sectionModal) {
        openSectionModalButton.addEventListener("click", () => {
            sectionModal.classList.add("show");
        });

        closeSectionModalButton.addEventListener("click", () => {
            sectionModal.classList.remove("show");
        });

        sectionModal.addEventListener("click", (event) => {
            if (event.target === sectionModal) {
                sectionModal.classList.remove("show");
            }
        });
    }
});