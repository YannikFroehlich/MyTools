document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("google-search-form");
    const input = document.getElementById("google-search-input");
    const suggestionsBox = document.getElementById("suggestions-box");
    const labelsElement = document.getElementById("home-labels");
    const labels = labelsElement ? JSON.parse(labelsElement.textContent) : {};

    const shortcutModal = document.getElementById("shortcut-modal");
    const closeShortcutModalButton = document.getElementById("close-shortcut-modal");
    const shortcutModalTitle = document.getElementById("shortcut-modal-title");
    const shortcutForm = shortcutModal?.querySelector(".shortcut-form");
    const shortcutFormActionInput = document.getElementById("shortcut-form-action");
    const shortcutIdInput = document.getElementById("shortcut-id");
    const shortcutSectionIdInput = document.getElementById("shortcut-section-id");
    const shortcutNameInput = document.getElementById("shortcut-name");
    const shortcutUrlInput = document.getElementById("shortcut-url");
    const shortcutCustomIconInput = document.getElementById("shortcut-custom-icon");
    const shortcutImageInput = document.getElementById("shortcut-image");
    const shortcutFileName = document.getElementById("shortcut-file-name");
    const shortcutRemoveImageInput = document.getElementById("shortcut-remove-image");
    const shortcutRemoveImageButton = document.getElementById("shortcut-remove-image-button");
    const shortcutModalSectionName = document.getElementById("shortcut-modal-section-name");

    const sectionModal = document.getElementById("section-modal");
    const openSectionModalButton = document.getElementById("open-section-modal");
    const closeSectionModalButton = document.getElementById("close-section-modal");
    const sectionModalTitle = document.getElementById("section-modal-title");
    const sectionForm = sectionModal?.querySelector(".shortcut-form");
    const sectionFormActionInput = document.getElementById("section-form-action");
    const editSectionIdInput = document.getElementById("edit-section-id");
    const sectionNameInput = document.getElementById("section-name");
    const sectionSubmitButton = document.getElementById("section-submit-button");

    const widgetModal = document.getElementById("widget-modal");
    const openWidgetModalButton = document.getElementById("open-widget-modal");
    const closeWidgetModalButton = document.getElementById("close-widget-modal");
    const widgetModalTitle = document.getElementById("widget-modal-title");
    const widgetForm = widgetModal?.querySelector(".shortcut-form");
    const widgetFormActionInput = document.getElementById("widget-form-action");
    const widgetIdInput = document.getElementById("widget-id");
    const widgetTitleInput = document.getElementById("widget-title");
    const widgetTypeInput = document.getElementById("widget-type");
    const widgetWeatherLocationInput = document.getElementById("widget-weather-location");
    const widgetWeatherLocationField = document.getElementById("widget-weather-location-field");
    const widgetClockDesignInput = document.getElementById("widget-clock-design");
    const widgetClockDesignField = document.getElementById("widget-clock-design-field");
    const widgetClockStyleInput = document.getElementById("widget-clock-style");
    const widgetClockStyleField = document.getElementById("widget-clock-style-field");
    const widgetClockOptionButtons = widgetModal
        ? [...widgetModal.querySelectorAll("[data-clock-option-target]")]
        : [];
    const widgetSubmitButton = document.getElementById("widget-submit-button");

    let suggestions = [];
    let currentFirstSuggestion = "";
    let activeSuggestionIndex = 0;

    function formatLabel(template, replacements = {}) {
        return Object.entries(replacements).reduce(
            (text, [key, value]) => text.replaceAll(`%(${key})s`, value),
            template
        );
    }

    function hideSuggestions() {
        if (suggestionsBox) {
            suggestionsBox.innerHTML = "";
            suggestionsBox.style.display = "none";
        }

        currentFirstSuggestion = "";
        activeSuggestionIndex = 0;
    }

    function focusSearchInput() {
        if (
            input &&
            !shortcutModal?.classList.contains("show") &&
            !sectionModal?.classList.contains("show") &&
            !widgetModal?.classList.contains("show")
        ) {
            input.focus();
        }
    }

    function closeModal(modal) {
        modal?.classList.remove("show");
        setTimeout(focusSearchInput, 100);
    }

    function openModal(modal) {
        hideSuggestions();
        input?.blur();
        modal?.classList.add("show");
    }

    setTimeout(focusSearchInput, 100);

    function getCurrentLocale() {
        const htmlLang = document.documentElement.lang || "de";

        if (htmlLang.toLowerCase().startsWith("en")) {
            return "en-US";
        }

        return "de-DE";
    }

    function updateClockWidgets() {
        const now = new Date();
        const locale = getCurrentLocale();

        const time = new Intl.DateTimeFormat(locale, {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
        }).format(now);
        const date = new Intl.DateTimeFormat(locale, {
            day: "2-digit",
            month: "long",
            year: "numeric",
        }).format(now);
        const weekday = new Intl.DateTimeFormat(locale, {
            weekday: "long",
        }).format(now);

        const seconds = now.getSeconds();
        const minutes = now.getMinutes();
        const hours = now.getHours();

        const secondDegrees = seconds * 6;
        const minuteDegrees = (minutes * 6) + (seconds * 0.1);
        const hourDegrees = ((hours % 12) * 30) + (minutes * 0.5);

        document.querySelectorAll("[data-clock-widget]").forEach(clock => {
            clock.querySelector("[data-clock-time]").textContent = time;
            clock.querySelector("[data-clock-date]").textContent = date;
            clock.querySelector("[data-clock-weekday]").textContent = weekday;

            const hourHand = clock.querySelector("[data-clock-hour-hand]");
            const minuteHand = clock.querySelector("[data-clock-minute-hand]");
            const secondHand = clock.querySelector("[data-clock-second-hand]");

            if (hourHand) hourHand.style.transform = `translateX(-50%) rotate(${hourDegrees}deg)`;
            if (minuteHand) minuteHand.style.transform = `translateX(-50%) rotate(${minuteDegrees}deg)`;
            if (secondHand) secondHand.style.transform = `translateX(-50%) rotate(${secondDegrees}deg)`;
        });
    }

    if (document.querySelector("[data-clock-widget]")) {
        updateClockWidgets();
        setInterval(updateClockWidgets, 1000);
    }

    fetch("/static/app/data/suggestions.json")
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP Fehler: ${response.status}`);
            }

            return response.json();
        })
        .then(data => {
            suggestions = Array.isArray(data) ? data : [];
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

    function updateActiveSuggestion() {
        if (!suggestionsBox) {
            return;
        }

        const items = [...suggestionsBox.querySelectorAll(".suggestion-item")];

        items.forEach((item, index) => {
            item.classList.toggle("active-suggestion", index === activeSuggestionIndex);
        });

        currentFirstSuggestion = items[activeSuggestionIndex]?.dataset.value || "";
    }

    function renderSuggestions(value) {
        if (!suggestionsBox) {
            return;
        }

        suggestionsBox.innerHTML = "";
        currentFirstSuggestion = "";
        activeSuggestionIndex = 0;

        const filteredSuggestions = getFilteredSuggestions(value);

        if (filteredSuggestions.length === 0) {
            hideSuggestions();
            return;
        }

        filteredSuggestions.forEach((item, index) => {
            const suggestionItem = document.createElement("div");
            suggestionItem.classList.add("suggestion-item");
            suggestionItem.dataset.value = item;

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
                input.value = item;
                hideSuggestions();
                searchGoogle(item);
            });

            suggestionsBox.appendChild(suggestionItem);
        });

        currentFirstSuggestion = filteredSuggestions[0];
        suggestionsBox.style.display = "block";
    }

    function getDirectUrl(query) {
        const trimmedQuery = query.trim();

        if (!trimmedQuery || /\s/.test(trimmedQuery)) {
            return null;
        }

        const hasProtocol = /^https?:\/\//i.test(trimmedQuery);
        const looksLikeLocalhost = /^(localhost|127(?:\.\d{1,3}){3}|0\.0\.0\.0)(?::\d{1,5})?(?:[/?#].*)?$/i.test(trimmedQuery);
        const looksLikeIpAddress = /^(?:\d{1,3}\.){3}\d{1,3}(?::\d{1,5})?(?:[/?#].*)?$/.test(trimmedQuery);
        const looksLikeDomain = /^(?:[a-z0-9-]+\.)+[a-z]{2,}(?::\d{1,5})?(?:[/?#].*)?$/i.test(trimmedQuery);
        const looksLikeWwwDomain = /^www\./i.test(trimmedQuery);

        if (!hasProtocol && !looksLikeDomain && !looksLikeWwwDomain && !looksLikeLocalhost && !looksLikeIpAddress) {
            return null;
        }

        const urlCandidate = hasProtocol
            ? trimmedQuery
            : looksLikeLocalhost || looksLikeIpAddress
                ? `http://${trimmedQuery}`
                : `https://${trimmedQuery}`;

        try {
            const url = new URL(urlCandidate);

            if (!['http:', 'https:'].includes(url.protocol)) {
                return null;
            }

            return url.href;
        } catch (error) {
            return null;
        }
    }

    function searchGoogle(query) {
        const trimmedQuery = query.trim();

        if (!trimmedQuery) {
            return;
        }

        const directUrl = getDirectUrl(trimmedQuery);

        if (directUrl) {
            window.location.href = directUrl;
            return;
        }

        window.location.href = `https://www.google.com/search?q=${encodeURIComponent(trimmedQuery)}`;
    }

    if (input) {
        input.addEventListener("input", () => {
            renderSuggestions(input.value);
        });

        input.addEventListener("keydown", (event) => {
            const items = suggestionsBox ? [...suggestionsBox.querySelectorAll(".suggestion-item")] : [];

            if ((event.key === "ArrowDown" || event.key === "ArrowUp") && items.length > 0) {
                event.preventDefault();

                activeSuggestionIndex = event.key === "ArrowDown"
                    ? (activeSuggestionIndex + 1) % items.length
                    : (activeSuggestionIndex - 1 + items.length) % items.length;

                updateActiveSuggestion();
                return;
            }

            if (event.key === "Tab" && currentFirstSuggestion) {
                event.preventDefault();
                input.value = currentFirstSuggestion;
                hideSuggestions();
                return;
            }

            if (event.key === "Enter" && items.length > 0 && currentFirstSuggestion) {
                event.preventDefault();
                input.value = currentFirstSuggestion;
                hideSuggestions();
                searchGoogle(currentFirstSuggestion);
                return;
            }

            if (event.key === "Escape") {
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

    function setCheckedRadio(container, name, value, fallbackValue = "") {
        const radios = container ? [...container.querySelectorAll(`input[name='${name}']`)] : [];
        const selected = radios.find(radio => radio.value === value) || radios.find(radio => radio.value === fallbackValue) || radios[0];

        radios.forEach(radio => {
            radio.checked = radio === selected;
        });
    }

    function syncClockOptionCards(input) {
        if (!input) return;

        widgetClockOptionButtons
            .filter(button => button.dataset.clockOptionTarget === input.id)
            .forEach(button => {
                button.classList.toggle("is-active", button.dataset.clockOptionValue === input.value);
            });
    }

    function setClockOption(input, value, fallbackValue = "") {
        if (!input) return;

        const options = widgetClockOptionButtons.filter(button => button.dataset.clockOptionTarget === input.id);
        const nextValue = options.some(button => button.dataset.clockOptionValue === value)
            ? value
            : fallbackValue;

        input.value = nextValue;
        syncClockOptionCards(input);
    }

    function resetShortcutForm() {
        shortcutForm?.reset();

        if (shortcutFormActionInput) shortcutFormActionInput.value = "add_shortcut";
        if (shortcutIdInput) shortcutIdInput.value = "";
        if (shortcutNameInput) shortcutNameInput.value = "";
        if (shortcutUrlInput) shortcutUrlInput.value = "";
        if (shortcutCustomIconInput) shortcutCustomIconInput.value = "";
        if (shortcutRemoveImageInput) shortcutRemoveImageInput.value = "";
        if (shortcutRemoveImageButton) shortcutRemoveImageButton.hidden = true;
        if (shortcutFileName) shortcutFileName.textContent = labels.noFileSelected || "Keine Datei ausgewählt";
        if (shortcutModalTitle) shortcutModalTitle.textContent = labels.newShortcut || "Neue Verknüpfung";
        setCheckedRadio(shortcutForm, "icon", "fa-brands fa-youtube");
    }

    shortcutImageInput?.addEventListener("change", () => {
        const fileName = shortcutImageInput.files?.[0]?.name;
        if (shortcutFileName) {
            shortcutFileName.textContent = fileName || labels.noFileSelected || "Keine Datei ausgewählt";
        }
        if (fileName && shortcutRemoveImageInput) {
            shortcutRemoveImageInput.value = "";
        }
    });

    shortcutRemoveImageButton?.addEventListener("click", () => {
        if (shortcutRemoveImageInput) shortcutRemoveImageInput.value = "1";
        if (shortcutImageInput) shortcutImageInput.value = "";
        if (shortcutFileName) shortcutFileName.textContent = labels.noFileSelected || "Keine Datei ausgewählt";
        shortcutRemoveImageButton.hidden = true;
    });

    function openAddShortcutModal(sectionId, sectionName) {
        resetShortcutForm();

        if (shortcutSectionIdInput) shortcutSectionIdInput.value = sectionId;
        if (shortcutModalSectionName) {
            shortcutModalSectionName.textContent = formatLabel(
                labels.shortcutForSection || 'für "%(section)s"',
                { section: sectionName }
            );
        }

        openModal(shortcutModal);
        setTimeout(() => shortcutNameInput?.focus(), 100);
    }

    function openEditShortcutModal(card) {
        resetShortcutForm();

        const shortcutId = card.dataset.shortcutId || "";
        const sectionId = card.closest(".shortcuts-grid")?.dataset.sectionId || card.dataset.shortcutSectionId || "";
        const sectionName = card.closest(".shortcuts-section")?.querySelector("h2")?.textContent?.trim() || "";
        const name = card.dataset.shortcutName || card.querySelector("a span")?.textContent?.trim() || "";
        const url = card.dataset.shortcutUrl || card.querySelector("a")?.getAttribute("href") || "";
        const icon = card.dataset.shortcutIcon || "";
        const hasImage = card.dataset.shortcutHasImage === "true";

        if (shortcutFormActionInput) shortcutFormActionInput.value = "edit_shortcut";
        if (shortcutIdInput) shortcutIdInput.value = shortcutId;
        if (shortcutSectionIdInput) shortcutSectionIdInput.value = sectionId;
        if (shortcutNameInput) shortcutNameInput.value = name;
        if (shortcutUrlInput) shortcutUrlInput.value = url;
        if (shortcutModalTitle) shortcutModalTitle.textContent = labels.editShortcut || "Verknüpfung bearbeiten";
        if (shortcutModalSectionName) {
            shortcutModalSectionName.textContent = sectionName
                ? formatLabel(labels.shortcutInSection || 'in "%(section)s"', { section: sectionName })
                : "";
        }
        if (shortcutRemoveImageButton) shortcutRemoveImageButton.hidden = !hasImage;
        if (hasImage && shortcutFileName) {
            shortcutFileName.textContent = labels.currentImage || "Aktuelles Bild vorhanden";
        }

        const matchingIcon = shortcutForm?.querySelector(`input[name='icon'][value="${CSS.escape(icon)}"]`);

        if (matchingIcon) {
            setCheckedRadio(shortcutForm, "icon", icon);
            if (shortcutCustomIconInput) shortcutCustomIconInput.value = "";
        } else {
            setCheckedRadio(shortcutForm, "icon", "fa-solid fa-link");
            if (shortcutCustomIconInput) shortcutCustomIconInput.value = icon;
        }

        openModal(shortcutModal);
        setTimeout(() => shortcutNameInput?.focus(), 100);
    }

    document.querySelectorAll(".open-shortcut-modal").forEach(button => {
        button.addEventListener("click", () => {
            openAddShortcutModal(button.dataset.sectionId, button.dataset.sectionName);
        });
    });

    document.querySelectorAll(".edit-shortcut-button").forEach(button => {
        button.addEventListener("click", event => {
            event.preventDefault();
            event.stopPropagation();

            const card = button.closest(".shortcut-card");

            if (card) {
                openEditShortcutModal(card);
            }
        });
    });

    if (window.matchMedia("(hover: none), (pointer: coarse)").matches) {
        document.querySelectorAll(".shortcut-card").forEach(card => {
            let revealTimer = null;
            let suppressNextClick = false;

            card.addEventListener("pointerdown", event => {
                if (event.pointerType === "mouse" || event.target.closest(".shortcut-card-actions")) {
                    return;
                }

                revealTimer = window.setTimeout(() => {
                    document.querySelectorAll(".shortcut-card.actions-open").forEach(openCard => {
                        if (openCard !== card) {
                            openCard.classList.remove("actions-open");
                        }
                    });

                    card.classList.add("actions-open");
                    suppressNextClick = true;
                }, 450);
            });

            card.addEventListener("pointerup", () => {
                window.clearTimeout(revealTimer);
            });

            card.addEventListener("pointercancel", () => {
                window.clearTimeout(revealTimer);
            });

            card.addEventListener("click", event => {
                if (!suppressNextClick) {
                    return;
                }

                event.preventDefault();
                event.stopPropagation();
                suppressNextClick = false;
            }, true);
        });

        document.addEventListener("click", event => {
            if (event.target.closest(".shortcut-card")) {
                return;
            }

            document.querySelectorAll(".shortcut-card.actions-open").forEach(card => {
                card.classList.remove("actions-open");
            });
        });
    }


    function setWidgetFieldVisible(field, input, isVisible) {
        if (field) {
            field.style.display = isVisible ? "flex" : "none";
            field.hidden = !isVisible;
        }

        if (input) {
            input.disabled = !isVisible;
        }
    }

    function toggleWidgetTypeFields() {
        const currentWidgetType = widgetTypeInput?.value || "weather";
        const isWeatherWidget = currentWidgetType === "weather";
        const isClockWidget = currentWidgetType === "clock";

        setWidgetFieldVisible(
            widgetWeatherLocationField,
            widgetWeatherLocationInput,
            isWeatherWidget
        );

        setWidgetFieldVisible(
            widgetClockDesignField,
            widgetClockDesignInput,
            isClockWidget
        );

        setWidgetFieldVisible(
            widgetClockStyleField,
            widgetClockStyleInput,
            isClockWidget
        );
    }

    function resetWidgetForm() {
        widgetForm?.reset();

        if (widgetFormActionInput) widgetFormActionInput.value = "add_widget";
        if (widgetIdInput) widgetIdInput.value = "";
        if (widgetTitleInput) widgetTitleInput.value = "";
        if (widgetTypeInput) widgetTypeInput.value = "weather";
        if (widgetWeatherLocationInput) widgetWeatherLocationInput.value = "";
        setClockOption(widgetClockDesignInput, "minimal", "minimal");
        setClockOption(widgetClockStyleInput, "classic", "classic");
        if (widgetModalTitle) widgetModalTitle.textContent = labels.newWidget || "Neues Widget";
        if (widgetSubmitButton) widgetSubmitButton.textContent = labels.addWidget || "Widget hinzufügen";

        setCheckedRadio(widgetForm, "widget_color", "blue");
        toggleWidgetTypeFields();
    }

    function openAddWidgetModal() {
        resetWidgetForm();
        openModal(widgetModal);
        setTimeout(() => widgetTitleInput?.focus(), 100);
    }

    function openEditWidgetModal(button) {
        const widgetCard = button.closest(".home-widget");
        if (!widgetCard) return;

        resetWidgetForm();

        if (widgetFormActionInput) widgetFormActionInput.value = "edit_widget";
        if (widgetIdInput) widgetIdInput.value = widgetCard.dataset.widgetId || "";
        if (widgetTitleInput) widgetTitleInput.value = widgetCard.dataset.widgetTitle || "";
        if (widgetTypeInput) widgetTypeInput.value = widgetCard.dataset.widgetType || "weather";
        if (widgetWeatherLocationInput) widgetWeatherLocationInput.value = widgetCard.dataset.widgetWeatherLocation || "";
        setClockOption(widgetClockDesignInput, widgetCard.dataset.widgetClockDesign || "minimal", "minimal");
        setClockOption(widgetClockStyleInput, widgetCard.dataset.widgetClockStyle || "classic", "classic");
        if (widgetModalTitle) widgetModalTitle.textContent = labels.editWidget || "Widget bearbeiten";
        if (widgetSubmitButton) widgetSubmitButton.textContent = labels.saveWidget || "Widget speichern";

        setCheckedRadio(widgetForm, "widget_color", widgetCard.dataset.widgetColor || "blue", "blue");
        toggleWidgetTypeFields();

        openModal(widgetModal);
        setTimeout(() => widgetTitleInput?.focus(), 100);
    }

    openWidgetModalButton?.addEventListener("click", openAddWidgetModal);
    widgetTypeInput?.addEventListener("change", toggleWidgetTypeFields);

    widgetClockOptionButtons.forEach(button => {
        button.addEventListener("click", () => {
            const input = document.getElementById(button.dataset.clockOptionTarget);
            setClockOption(input, button.dataset.clockOptionValue, input?.value);
        });
    });

    document.querySelectorAll(".edit-widget-button").forEach(button => {
        button.addEventListener("click", event => {
            event.preventDefault();
            event.stopPropagation();
            openEditWidgetModal(button);
        });
    });

    if (closeWidgetModalButton && widgetModal) {
        closeWidgetModalButton.addEventListener("click", () => closeModal(widgetModal));
        widgetModal.addEventListener("click", event => {
            if (event.target === widgetModal) closeModal(widgetModal);
        });
    }

    if (closeShortcutModalButton && shortcutModal) {
        closeShortcutModalButton.addEventListener("click", () => closeModal(shortcutModal));
        shortcutModal.addEventListener("click", event => {
            if (event.target === shortcutModal) closeModal(shortcutModal);
        });
    }

    function resetSectionForm() {
        sectionForm?.reset();

        if (sectionFormActionInput) sectionFormActionInput.value = "add_section";
        if (editSectionIdInput) editSectionIdInput.value = "";
        if (sectionNameInput) sectionNameInput.value = "";
        if (sectionModalTitle) sectionModalTitle.textContent = labels.newSection || "Neuer Bereich";
        if (sectionSubmitButton) sectionSubmitButton.textContent = labels.createSection || "Bereich erstellen";
        setCheckedRadio(sectionForm, "section_color", "blue");
    }

    function openAddSectionModal() {
        resetSectionForm();
        openModal(sectionModal);
        setTimeout(() => sectionNameInput?.focus(), 100);
    }

    function openEditSectionModal(button) {
        resetSectionForm();

        if (sectionFormActionInput) sectionFormActionInput.value = "edit_section";
        if (editSectionIdInput) editSectionIdInput.value = button.dataset.sectionId || "";
        if (sectionNameInput) sectionNameInput.value = button.dataset.sectionName || "";
        if (sectionModalTitle) sectionModalTitle.textContent = labels.editSection || "Bereich bearbeiten";
        if (sectionSubmitButton) sectionSubmitButton.textContent = labels.saveChanges || "Änderungen speichern";

        setCheckedRadio(sectionForm, "section_color", button.dataset.sectionColor || "blue", "blue");

        openModal(sectionModal);
        setTimeout(() => sectionNameInput?.focus(), 100);
    }

    openSectionModalButton?.addEventListener("click", openAddSectionModal);

    document.querySelectorAll(".edit-section-button").forEach(button => {
        button.addEventListener("click", event => {
            event.preventDefault();
            event.stopPropagation();
            openEditSectionModal(button);
        });
    });

    if (closeSectionModalButton && sectionModal) {
        closeSectionModalButton.addEventListener("click", () => closeModal(sectionModal));
        sectionModal.addEventListener("click", event => {
            if (event.target === sectionModal) closeModal(sectionModal);
        });
    }

    /* ── Pointer Drag & Drop: Shortcuts + Sections ── */

    function getCsrfToken() {
        const csrfInput = document.querySelector("input[name='csrfmiddlewaretoken']");
        return csrfInput ? csrfInput.value : "";
    }

    function postJson(payload) {
        return fetch(window.location.href, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCsrfToken()
            },
            body: JSON.stringify(payload)
        }).catch(error => {
            console.error("Änderung konnte nicht gespeichert werden:", error);
        });
    }

    function updateEmptyStates() {
        document.querySelectorAll(".shortcuts-grid").forEach(grid => {
            const emptyState = grid.querySelector(".empty-shortcuts");
            const hasShortcuts = grid.querySelectorAll(".shortcut-card").length > 0;

            if (emptyState) {
                emptyState.hidden = hasShortcuts;
            }

            grid.classList.toggle("is-empty", !hasShortcuts);
        });
    }

    function saveShortcutOrder() {
        const payload = [];

        document.querySelectorAll(".shortcuts-grid").forEach(grid => {
            const sectionId = grid.dataset.sectionId;

            grid.querySelectorAll(".shortcut-card").forEach((card, index) => {
                card.dataset.shortcutSectionId = sectionId;

                payload.push({
                    id: card.dataset.shortcutId,
                    section_id: sectionId,
                    order: index
                });
            });
        });

        return postJson({
            action: "update_shortcut_order",
            shortcuts: payload
        });
    }

    function saveHomeLayoutOrder() {
        const items = [...document.querySelectorAll("#sections-wrapper > .home-layout-item")]
            .filter(item => item.dataset.isDefaultSection !== "true")
            .map((item, index) => ({
                type: item.dataset.layoutItemType,
                id: item.dataset.sectionId || "",
                order: index + 1
            }));

        return postJson({
            action: "update_home_layout_order",
            items
        });
    }

    function saveSectionOrder() {
        return saveHomeLayoutOrder();
    }

    function saveWidgetOrder() {
        const widgets = [...document.querySelectorAll(".home-widget")].map((widget, index) => ({
            id: widget.dataset.widgetId,
            order: index
        }));

        return postJson({
            action: "update_widget_order",
            widgets
        });
    }

    function createPlaceholder(element, extraClass) {
        const rect = element.getBoundingClientRect();
        const placeholder = document.createElement("div");
        placeholder.className = `drag-placeholder ${extraClass}`;
        placeholder.style.width = `${rect.width}px`;
        placeholder.style.height = `${rect.height}px`;
        return placeholder;
    }

    function setFloatingElement(element, rect) {
        element.classList.add("pointer-dragging");
        element.style.position = "fixed";
        element.style.left = `${rect.left}px`;
        element.style.top = `${rect.top}px`;
        element.style.width = `${rect.width}px`;
        element.style.height = `${rect.height}px`;
        element.style.zIndex = "20000";
        element.style.pointerEvents = "none";
        element.style.margin = "0";
    }

    function moveFloatingElement(element, clientX, clientY, offsetX, offsetY) {
        element.style.left = `${clientX - offsetX}px`;
        element.style.top = `${clientY - offsetY}px`;
    }

    function resetFloatingElement(element) {
        element.classList.remove("pointer-dragging");
        element.style.position = "";
        element.style.left = "";
        element.style.top = "";
        element.style.width = "";
        element.style.height = "";
        element.style.zIndex = "";
        element.style.pointerEvents = "";
        element.style.margin = "";
    }

    function getElementUnderPointer(clientX, clientY, selector) {
        const target = document.elementFromPoint(clientX, clientY);
        return target?.closest(selector) || null;
    }

    function getShortcutInsertBefore(grid, clientY) {
        const cards = [...grid.querySelectorAll(".shortcut-card:not(.pointer-dragging)")];

        for (const card of cards) {
            const box = card.getBoundingClientRect();
            const middle = box.top + box.height / 2;

            if (clientY < middle) {
                return card;
            }
        }

        return null;
    }

    function getLayoutInsertBefore(wrapper, clientY) {
        const items = [...wrapper.querySelectorAll(":scope > .home-layout-item:not(.pointer-dragging)")]
            .filter(item => item.dataset.isDefaultSection !== "true");

        for (const item of items) {
            const box = item.getBoundingClientRect();
            const middle = box.top + box.height / 2;

            if (clientY < middle) {
                return item;
            }
        }

        return null;
    }

    function startPointerShortcutDrag(event, handle) {
        if (event.button !== 0) {
            return;
        }

        const card = handle.closest(".shortcut-card");
        const startGrid = card?.closest(".shortcuts-grid");

        if (!card || !startGrid) {
            return;
        }

        event.preventDefault();
        hideSuggestions();

        const rect = card.getBoundingClientRect();
        const offsetX = event.clientX - rect.left;
        const offsetY = event.clientY - rect.top;
        const placeholder = createPlaceholder(card, "shortcut-placeholder");

        startGrid.insertBefore(placeholder, card);
        document.body.appendChild(card);
        setFloatingElement(card, rect);
        moveFloatingElement(card, event.clientX, event.clientY, offsetX, offsetY);
        updateEmptyStates();

        function onPointerMove(moveEvent) {
            moveEvent.preventDefault();
            moveFloatingElement(card, moveEvent.clientX, moveEvent.clientY, offsetX, offsetY);

            const grid = getElementUnderPointer(moveEvent.clientX, moveEvent.clientY, ".shortcuts-grid");

            document.querySelectorAll(".shortcuts-grid").forEach(item => {
                item.classList.toggle("drag-over", item === grid);
            });

            if (!grid) {
                return;
            }

            const emptyState = grid.querySelector(".empty-shortcuts");
            if (emptyState) {
                emptyState.hidden = true;
            }

            const before = getShortcutInsertBefore(grid, moveEvent.clientY);

            if (before) {
                grid.insertBefore(placeholder, before);
            } else {
                grid.appendChild(placeholder);
            }

            updateEmptyStates();
        }

        function onPointerUp(upEvent) {
            document.removeEventListener("pointermove", onPointerMove);
            document.removeEventListener("pointerup", onPointerUp);
            document.removeEventListener("pointercancel", onPointerUp);

            placeholder.replaceWith(card);
            resetFloatingElement(card);

            document.querySelectorAll(".shortcuts-grid").forEach(grid => {
                grid.classList.remove("drag-over");
            });

            updateEmptyStates();
            saveShortcutOrder();
        }

        document.addEventListener("pointermove", onPointerMove, { passive: false });
        document.addEventListener("pointerup", onPointerUp, { once: true });
        document.addEventListener("pointercancel", onPointerUp, { once: true });
    }

    function startPointerSectionDrag(event, handle) {
        if (event.button !== 0) {
            return;
        }

        const layoutItem = handle.closest(".home-layout-item");
        const wrapper = document.getElementById("sections-wrapper");
        const addSectionCard = document.getElementById("open-section-modal");

        if (!layoutItem || !wrapper || !addSectionCard || layoutItem.dataset.isDefaultSection === "true") {
            return;
        }

        event.preventDefault();
        hideSuggestions();

        const rect = layoutItem.getBoundingClientRect();
        const offsetX = event.clientX - rect.left;
        const offsetY = event.clientY - rect.top;
        const placeholder = createPlaceholder(layoutItem, "section-placeholder");

        wrapper.insertBefore(placeholder, layoutItem);
        document.body.appendChild(layoutItem);
        setFloatingElement(layoutItem, rect);
        moveFloatingElement(layoutItem, event.clientX, event.clientY, offsetX, offsetY);

        function onPointerMove(moveEvent) {
            moveEvent.preventDefault();
            moveFloatingElement(layoutItem, moveEvent.clientX, moveEvent.clientY, offsetX, offsetY);

            const before = getLayoutInsertBefore(wrapper, moveEvent.clientY);

            if (before) {
                wrapper.insertBefore(placeholder, before);
            } else {
                wrapper.insertBefore(placeholder, addSectionCard);
            }
        }

        function onPointerUp() {
            document.removeEventListener("pointermove", onPointerMove);
            document.removeEventListener("pointerup", onPointerUp);
            document.removeEventListener("pointercancel", onPointerUp);

            placeholder.replaceWith(layoutItem);
            resetFloatingElement(layoutItem);
            saveHomeLayoutOrder();
        }

        document.addEventListener("pointermove", onPointerMove, { passive: false });
        document.addEventListener("pointerup", onPointerUp, { once: true });
        document.addEventListener("pointercancel", onPointerUp, { once: true });
    }


    function startPointerWidgetDrag(event, handle) {
        if (event.button !== undefined && event.button !== 0) return;

        const widget = handle.closest(".home-widget");
        const grid = document.getElementById("widgets-grid");

        if (!widget || !grid) return;

        event.preventDefault();
        handle.setPointerCapture?.(event.pointerId);

        const rect = widget.getBoundingClientRect();
        const pointerOffsetX = event.clientX - rect.left;
        const pointerOffsetY = event.clientY - rect.top;
        const placeholder = createPlaceholder(widget, "widget-placeholder");

        widget.before(placeholder);
        setFloatingElement(widget, rect);
        widget.classList.add("widget-dragging");
        document.body.appendChild(widget);

        function onPointerMove(moveEvent) {
            moveEvent.preventDefault();

            widget.style.left = `${moveEvent.clientX - pointerOffsetX}px`;
            widget.style.top = `${moveEvent.clientY - pointerOffsetY}px`;

            const widgetCards = [...grid.querySelectorAll(".home-widget")];
            const afterElement = widgetCards.find(card => {
                const cardRect = card.getBoundingClientRect();
                const cardMiddleY = cardRect.top + cardRect.height / 2;
                const cardMiddleX = cardRect.left + cardRect.width / 2;

                if (moveEvent.clientY < cardRect.top || moveEvent.clientY > cardRect.bottom) {
                    return false;
                }

                return moveEvent.clientY < cardMiddleY || moveEvent.clientX < cardMiddleX;
            });

            if (afterElement) {
                grid.insertBefore(placeholder, afterElement);
            } else {
                grid.appendChild(placeholder);
            }
        }

        function onPointerUp() {
            document.removeEventListener("pointermove", onPointerMove);
            document.removeEventListener("pointerup", onPointerUp);
            document.removeEventListener("pointercancel", onPointerUp);

            widget.classList.remove("widget-dragging");
            placeholder.replaceWith(widget);
            resetFloatingElement(widget);
            saveWidgetOrder();
        }

        document.addEventListener("pointermove", onPointerMove, { passive: false });
        document.addEventListener("pointerup", onPointerUp, { once: true });
        document.addEventListener("pointercancel", onPointerUp, { once: true });
    }

    document.querySelectorAll(".shortcut-drag-handle").forEach(handle => {
        handle.addEventListener("pointerdown", event => startPointerShortcutDrag(event, handle));
    });

    document.querySelectorAll(".section-drag-handle").forEach(handle => {
        handle.addEventListener("pointerdown", event => startPointerSectionDrag(event, handle));
    });

    document.querySelectorAll(".widget-drag-handle").forEach(handle => {
        handle.addEventListener("pointerdown", event => startPointerWidgetDrag(event, handle));
    });

    updateEmptyStates();
    toggleWidgetTypeFields();
});


/* ───────────────── Shortcut Drei-Punkte-Menü ───────────────── */

(function setupShortcutActionMenus() {
    const closeAllShortcutMenus = () => {
        document.querySelectorAll('.shortcut-card.actions-open').forEach((card) => {
            card.classList.remove('actions-open');
            const toggle = card.querySelector('.shortcut-menu-toggle');
            if (toggle) {
                toggle.setAttribute('aria-expanded', 'false');
            }
        });
    };

    document.addEventListener('click', (event) => {
        const toggle = event.target.closest('.shortcut-menu-toggle');

        if (toggle) {
            event.preventDefault();
            event.stopPropagation();

            const card = toggle.closest('.shortcut-card');
            const isOpen = card?.classList.contains('actions-open');

            closeAllShortcutMenus();

            if (card && !isOpen) {
                card.classList.add('actions-open');
                toggle.setAttribute('aria-expanded', 'true');
            }

            return;
        }

        if (!event.target.closest('.shortcut-actions-menu')) {
            closeAllShortcutMenus();
        }
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            closeAllShortcutMenus();
        }
    });

    document.addEventListener('click', (event) => {
        const menuButton = event.target.closest('.shortcut-actions-menu button');
        const menuForm = event.target.closest('.shortcut-actions-menu form');

        if (menuButton && !menuForm) {
            closeAllShortcutMenus();
        }
    });
})();
