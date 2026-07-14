document.addEventListener("DOMContentLoaded", () => {
    const addForm = document.getElementById("shopping-add-form");
    const addCard = document.getElementById("shopping-add-card");
    const addToggle = document.getElementById("shopping-add-toggle");
    const addPanel = document.getElementById("shopping-add-panel");
    const nameInput = document.getElementById("shopping-name");
    const suggestionList = document.getElementById("shopping-suggestion-list");
    const advancedToggle = document.getElementById("shopping-advanced-toggle");
    const advancedPanel = document.getElementById("shopping-advanced-panel");
    const duplicateWarning = document.getElementById("shopping-duplicate-warning");
    const duplicateCopy = document.getElementById("shopping-duplicate-copy");
    const addDuplicateButton = document.getElementById("shopping-add-duplicate");
    const allowDuplicateInput = document.getElementById("shopping-allow-duplicate");
    const formStatus = document.getElementById("shopping-form-status");
    const barcodeInput = document.getElementById("shopping-barcode");
    const lookupButton = document.getElementById("shopping-product-lookup");
    const lookupStatus = document.getElementById("shopping-lookup-status");
    const preview = document.getElementById("shopping-product-preview");
    const previewImage = document.getElementById("shopping-product-image");
    const previewPlaceholder = document.getElementById("shopping-product-placeholder");
    const previewTitle = document.getElementById("shopping-product-title");
    const previewMeta = document.getElementById("shopping-product-meta");
    const cameraButton = document.getElementById("shopping-camera-open");
    const cameraCloseButton = document.getElementById("shopping-camera-close");
    const scannerDialog = document.getElementById("shopping-scanner-dialog");
    const cameraVideo = document.getElementById("shopping-camera-video");
    const scannerStatus = document.getElementById("shopping-scanner-status");
    const modeToolbar = document.getElementById("shopping-mode-toolbar");
    const modeExitButton = document.getElementById("shopping-mode-exit");
    const categoryGroups = document.getElementById("shopping-category-groups");
    const emptyState = document.getElementById("shopping-empty-state");

    const parseJsonScript = (id) => {
        const source = document.getElementById(id);
        if (!source) return [];
        try {
            const value = JSON.parse(source.textContent);
            return Array.isArray(value) ? value : [];
        } catch (_error) {
            return [];
        }
    };

    const suggestions = parseJsonScript("shopping-suggestions-data");
    let existingItems = parseJsonScript("shopping-existing-items-data");
    const modeStorageKey = "mytools-shopping-mode";
    let cameraStream = null;
    let barcodeDetector = null;
    let scanning = false;
    let scanFrameId = null;
    let lastScanAt = 0;

    const showToast = (message, level = "info", options = {}) => {
        if (window.MyToolsToast?.show) {
            return window.MyToolsToast.show(message, {level, ...options});
        }
        if (formStatus) {
            formStatus.textContent = message;
            formStatus.className = `shopping-form-status${level ? ` is-${level}` : ""}`;
        }
        return null;
    };

    const setFormStatus = (message, kind = "") => {
        if (!formStatus) return;
        formStatus.textContent = message;
        formStatus.className = `shopping-form-status${kind ? ` is-${kind}` : ""}`;
    };

    const setLookupStatus = (message, kind = "") => {
        if (!lookupStatus) return;
        lookupStatus.textContent = message;
        lookupStatus.className = `shopping-lookup-status${kind ? ` is-${kind}` : ""}`;
    };

    const setScannerStatus = (message, kind = "") => {
        if (!scannerStatus) return;
        scannerStatus.textContent = message;
        scannerStatus.className = `shopping-scanner-status${kind ? ` is-${kind}` : ""}`;
    };

    const setButtonLoading = (button, loading) => {
        if (!button) return;
        const icon = button.querySelector("i");
        if (loading) {
            button.disabled = true;
            button.classList.add("is-loading");
            if (icon) {
                icon.dataset.previousClass = icon.className;
                icon.className = "fa-solid fa-spinner";
            }
            return;
        }
        button.disabled = false;
        button.classList.remove("is-loading");
        if (icon?.dataset.previousClass) {
            icon.className = icon.dataset.previousClass;
            delete icon.dataset.previousClass;
        }
    };

    const readJsonResponse = async (response) => {
        try {
            return await response.json();
        } catch (_error) {
            return {ok: false, error: "Die Antwort konnte nicht verarbeitet werden."};
        }
    };

    let setAddPanelOpen = (_shouldOpen, _focusField = false) => {};
    if (addCard && addToggle && addPanel) {
        const mobileLayout = window.matchMedia("(max-width: 620px)");
        let mobileInitialized = false;

        setAddPanelOpen = (shouldOpen, focusField = false) => {
            addCard.classList.toggle("is-open", shouldOpen);
            addToggle.setAttribute("aria-expanded", shouldOpen ? "true" : "false");
            if (shouldOpen && focusField) {
                window.requestAnimationFrame(() => {
                    nameInput?.focus({preventScroll: true});
                    addCard.scrollIntoView({behavior: "smooth", block: "start"});
                });
            }
        };

        const syncAddPanel = () => {
            if (mobileLayout.matches) {
                addCard.classList.add("is-collapsible");
                addToggle.removeAttribute("aria-disabled");
                addToggle.tabIndex = 0;
                if (!mobileInitialized) {
                    setAddPanelOpen(window.location.hash === "#shopping-add-panel");
                    mobileInitialized = true;
                }
                return;
            }

            addCard.classList.remove("is-collapsible");
            addCard.classList.add("is-open");
            addToggle.setAttribute("aria-expanded", "true");
            addToggle.setAttribute("aria-disabled", "true");
            addToggle.tabIndex = -1;
        };

        addToggle.addEventListener("click", () => {
            if (!mobileLayout.matches) return;
            setAddPanelOpen(!addCard.classList.contains("is-open"), true);
        });
        if (typeof mobileLayout.addEventListener === "function") {
            mobileLayout.addEventListener("change", syncAddPanel);
        } else {
            mobileLayout.addListener(syncAddPanel);
        }
        syncAddPanel();
    }

    const setAdvancedOpen = (shouldOpen) => {
        if (!advancedPanel || !advancedToggle) return;
        advancedPanel.hidden = !shouldOpen;
        advancedToggle.setAttribute("aria-expanded", shouldOpen ? "true" : "false");
    };

    advancedToggle?.addEventListener("click", () => setAdvancedOpen(Boolean(advancedPanel?.hidden)));

    const getActiveCount = () => {
        const counter = document.querySelector('[data-shopping-count="active"]');
        return Number.parseInt(counter?.textContent || "0", 10) || 0;
    };

    const setShoppingMode = (active, persist = true) => {
        document.body.classList.toggle("shopping-mode-active", active);
        if (modeToolbar) modeToolbar.hidden = !active;
        document.querySelectorAll(".shopping-mode-trigger").forEach((button) => {
            button.setAttribute("aria-pressed", active ? "true" : "false");
        });
        if (persist) {
            try {
                if (active) sessionStorage.setItem(modeStorageKey, "1");
                else sessionStorage.removeItem(modeStorageKey);
            } catch (_error) {
                // The mode still works if session storage is unavailable.
            }
        }
        if (active) window.scrollTo({top: 0, behavior: "smooth"});
    };

    document.querySelectorAll(".shopping-mode-trigger").forEach((button) => {
        button.addEventListener("click", () => {
            if (getActiveCount() < 1) {
                showToast("Füge zuerst einen Artikel hinzu.", "info");
                setAddPanelOpen(true, true);
                return;
            }
            setShoppingMode(true);
        });
    });
    modeExitButton?.addEventListener("click", () => setShoppingMode(false));

    try {
        if (sessionStorage.getItem(modeStorageKey) === "1" && getActiveCount() > 0) {
            setShoppingMode(true, false);
        }
    } catch (_error) {
        // Ignore disabled session storage.
    }

    const focusAddForm = () => {
        setShoppingMode(false);
        setAddPanelOpen(true, true);
        window.setTimeout(() => nameInput?.focus(), 80);
    };

    document.querySelectorAll(".shopping-focus-add").forEach((button) => {
        button.addEventListener("click", (event) => {
            event.preventDefault();
            focusAddForm();
        });
    });

    const normalize = (value) => String(value || "").trim().toLocaleLowerCase("de-DE");

    const setNamedField = (name, value) => {
        const field = addForm?.elements.namedItem(name);
        if (field && "value" in field) field.value = value ?? "";
    };

    const hideSuggestions = () => {
        if (suggestionList) suggestionList.hidden = true;
        nameInput?.setAttribute("aria-expanded", "false");
    };

    const applySuggestion = (suggestion, submitImmediately = false) => {
        if (!addForm || !suggestion) return;
        setNamedField("name", suggestion.name);
        setNamedField("quantity", suggestion.quantity || "1");
        setNamedField("unit", suggestion.unit || "piece");
        setNamedField("unit_price", suggestion.unit_price || "");
        setNamedField("category", suggestion.category || "other");
        setNamedField("recurrence", suggestion.recurrence || "none");
        setNamedField("barcode", suggestion.barcode || "");
        setNamedField("brand", suggestion.brand || "");
        setNamedField("product_quantity", suggestion.product_quantity || "");
        setNamedField("image_url", suggestion.image_url || "");
        if (allowDuplicateInput) allowDuplicateInput.value = "0";
        hideSuggestions();
        updateDuplicateWarning();
        if (submitImmediately) addForm.requestSubmit();
        else addForm.elements.namedItem("quantity")?.focus();
    };

    const renderSuggestions = (query = "") => {
        if (!suggestionList || !nameInput || !suggestions.length) return;
        const normalizedQuery = normalize(query);
        const matches = suggestions
            .map((suggestion, index) => ({suggestion, index}))
            .filter(({suggestion}) => !normalizedQuery || normalize(suggestion.name).includes(normalizedQuery))
            .slice(0, 5);

        suggestionList.replaceChildren();
        matches.forEach(({suggestion}) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "shopping-suggestion-option";
            button.setAttribute("role", "option");

            const icon = document.createElement("i");
            icon.className = suggestion.kind === "frequent" ? "fa-solid fa-clock-rotate-left" : "fa-solid fa-plus";
            const copy = document.createElement("span");
            const title = document.createElement("strong");
            title.textContent = suggestion.name;
            const detail = document.createElement("small");
            detail.textContent = suggestion.kind === "frequent" ? `${suggestion.usage_count}× gekauft` : (suggestion.kind === "recent" ? "Zuletzt gekauft" : "Schnellstart");
            copy.append(title, detail);
            const hint = document.createElement("span");
            hint.textContent = "Übernehmen";
            button.append(icon, copy, hint);
            button.addEventListener("click", () => applySuggestion(suggestion));
            suggestionList.appendChild(button);
        });

        suggestionList.hidden = matches.length === 0;
        nameInput.setAttribute("aria-expanded", matches.length ? "true" : "false");
    };

    nameInput?.addEventListener("focus", () => renderSuggestions(nameInput.value));
    nameInput?.addEventListener("input", () => {
        if (allowDuplicateInput) allowDuplicateInput.value = "0";
        renderSuggestions(nameInput.value);
        updateDuplicateWarning();
    });
    nameInput?.addEventListener("keydown", (event) => {
        if (event.key === "Escape") hideSuggestions();
        if (event.key === "ArrowDown" && !suggestionList?.hidden) {
            event.preventDefault();
            suggestionList.querySelector("button")?.focus();
        }
    });
    document.addEventListener("click", (event) => {
        if (!event.target.closest(".shopping-field-name")) hideSuggestions();
    });

    document.querySelectorAll("[data-shopping-suggestion-index]").forEach((button) => {
        button.addEventListener("click", () => {
            const suggestion = suggestions[Number.parseInt(button.dataset.shoppingSuggestionIndex, 10)];
            if (suggestion) applySuggestion(suggestion, true);
        });
    });

    const findDuplicate = () => {
        if (!addForm) return null;
        const name = normalize(nameInput?.value);
        const barcode = String(barcodeInput?.value || "").replace(/\D/g, "");
        if (!name && !barcode) return null;
        return existingItems.find((item) => normalize(item.name) === name || (barcode && item.barcode === barcode)) || null;
    };

    function updateDuplicateWarning(forcedDuplicate = null) {
        if (!duplicateWarning) return null;
        const duplicate = forcedDuplicate || findDuplicate();
        duplicateWarning.hidden = !duplicate;
        if (duplicate && duplicateCopy) duplicateCopy.textContent = `${duplicate.name} ist bereits vorhanden.`;
        return duplicate;
    }

    barcodeInput?.addEventListener("input", () => {
        clearProductData();
        if (allowDuplicateInput) allowDuplicateInput.value = "0";
        updateDuplicateWarning();
    });

    addDuplicateButton?.addEventListener("click", () => {
        if (allowDuplicateInput) allowDuplicateInput.value = "1";
        if (duplicateWarning) duplicateWarning.hidden = true;
        addForm?.requestSubmit();
    });

    addForm?.addEventListener("submit", async (event) => {
        event.preventDefault();
        hideSuggestions();
        if (allowDuplicateInput?.value !== "1" && updateDuplicateWarning()) {
            setFormStatus("Prüfe den vorhandenen Artikel oder füge ihn bewusst doppelt hinzu.", "error");
            duplicateWarning?.scrollIntoView({behavior: "smooth", block: "nearest"});
            return;
        }

        const submitButton = addForm.querySelector('button[type="submit"]');
        setButtonLoading(submitButton, true);
        setFormStatus("Artikel wird hinzugefügt …", "loading");

        try {
            const response = await fetch(addForm.action || window.location.href, {
                method: "POST",
                body: new FormData(addForm),
                headers: {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"},
                credentials: "same-origin",
            });
            const payload = await readJsonResponse(response);
            if (response.status === 409 && payload.duplicate) {
                updateDuplicateWarning(payload.item);
                throw new Error(payload.error || "Der Artikel ist bereits vorhanden.");
            }
            if (!response.ok || !payload.ok) throw new Error(payload.error || "Artikel konnte nicht hinzugefügt werden.");

            existingItems.push(payload.item);
            setFormStatus(payload.message, "success");
            showToast(payload.message, "success");
            window.setTimeout(() => window.location.reload(), 420);
        } catch (error) {
            setFormStatus(error.message || "Artikel konnte nicht hinzugefügt werden.", "error");
            showToast(error.message || "Artikel konnte nicht hinzugefügt werden.", "error");
            setButtonLoading(submitButton, false);
        }
    });

    const clearProductData = () => {
        ["shopping-brand", "shopping-product-quantity", "shopping-image-url"].forEach((id) => {
            const field = document.getElementById(id);
            if (field) field.value = "";
        });
        if (preview) preview.hidden = true;
        if (previewImage) {
            previewImage.hidden = true;
            previewImage.removeAttribute("src");
        }
        if (previewPlaceholder) previewPlaceholder.hidden = false;
        setLookupStatus("");
    };

    const lookupProduct = async () => {
        if (!lookupButton || !addForm || !barcodeInput) return;
        const barcode = barcodeInput.value.replace(/[\s-]+/g, "");
        if (!/^\d{8,14}$/.test(barcode)) {
            setLookupStatus("Bitte gib einen Barcode mit 8 bis 14 Ziffern ein.", "error");
            barcodeInput.focus();
            return;
        }

        const url = addForm.dataset.productUrl.replace("00000000", encodeURIComponent(barcode));
        setButtonLoading(lookupButton, true);
        setLookupStatus("Produktdaten werden geladen …", "loading");

        try {
            const response = await fetch(url, {headers: {"Accept": "application/json"}, credentials: "same-origin"});
            const payload = await readJsonResponse(response);
            if (!response.ok || !payload.ok) throw new Error(payload.error || "Produkt konnte nicht geladen werden.");

            const product = payload.product || {};
            barcodeInput.value = product.barcode || barcode;
            if (nameInput && product.name) nameInput.value = product.name;
            setNamedField("brand", product.brand || "");
            setNamedField("product_quantity", product.quantity || "");
            setNamedField("image_url", product.image_url || "");
            if (previewTitle) previewTitle.textContent = product.name || "Produkt gefunden";
            if (previewMeta) previewMeta.textContent = [product.brand, product.quantity].filter(Boolean).join(" · ");
            if (previewImage && previewPlaceholder) {
                if (product.image_url) {
                    previewImage.src = product.image_url;
                    previewImage.hidden = false;
                    previewPlaceholder.hidden = true;
                } else {
                    previewImage.hidden = true;
                    previewPlaceholder.hidden = false;
                }
            }
            if (preview) preview.hidden = false;
            setLookupStatus("Produktdaten wurden übernommen.", "success");
            updateDuplicateWarning();
            nameInput?.focus();
        } catch (error) {
            clearProductData();
            setLookupStatus(error.message || "Produkt konnte nicht geladen werden.", "error");
        } finally {
            setButtonLoading(lookupButton, false);
        }
    };

    lookupButton?.addEventListener("click", lookupProduct);

    document.querySelectorAll(".shopping-inline-form").forEach((form) => {
        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            const button = form.querySelector('button[type="submit"]');
            const article = form.closest(".shopping-item");
            setButtonLoading(button, true);
            try {
                const response = await fetch(form.action, {
                    method: "POST",
                    body: new FormData(form),
                    headers: {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"},
                    credentials: "same-origin",
                });
                const payload = await readJsonResponse(response);
                if (!response.ok || !payload.ok) throw new Error(payload.error || "Änderungen konnten nicht gespeichert werden.");

                const item = payload.item;
                const quantityDisplay = article?.querySelector("[data-shopping-quantity-display]");
                const totalDisplay = article?.querySelector("[data-shopping-line-total]");
                const unitPriceDisplay = article?.querySelector("[data-shopping-unit-price]");
                if (quantityDisplay) quantityDisplay.textContent = item.quantity.replace(".", ",");
                if (item.line_total !== null) {
                    if (totalDisplay) totalDisplay.textContent = `${Number(item.line_total).toLocaleString("de-DE", {minimumFractionDigits: 2, maximumFractionDigits: 2})} €`;
                    if (unitPriceDisplay) unitPriceDisplay.textContent = `${Number(item.unit_price).toLocaleString("de-DE", {minimumFractionDigits: 2, maximumFractionDigits: 2})} € / ${item.unit_label}`;
                } else {
                    if (totalDisplay) totalDisplay.textContent = "—";
                    if (unitPriceDisplay) unitPriceDisplay.textContent = "Kein Preis";
                }
                showToast(payload.message, "success");
            } catch (error) {
                showToast(error.message || "Änderungen konnten nicht gespeichert werden.", "error");
            } finally {
                setButtonLoading(button, false);
            }
        });
    });

    const updateCount = (state, delta) => {
        let nextValue = 0;
        document.querySelectorAll(`[data-shopping-count="${state}"]`).forEach((counter) => {
            nextValue = Math.max(0, (Number.parseInt(counter.textContent || "0", 10) || 0) + delta);
            counter.textContent = String(nextValue);
        });
        return nextValue;
    };

    const removeArticleFromView = (article) => {
        if (!article) return;
        const state = article.dataset.shoppingState;
        const group = article.closest(".shopping-category-group");
        const card = article.closest("[data-shopping-card-state]");
        article.classList.add("is-removing");
        window.setTimeout(() => {
            article.remove();
            const nextCount = updateCount(state, -1);
            if (group) {
                const remainingInGroup = group.querySelectorAll(".shopping-item").length;
                const groupCounter = group.querySelector("[data-shopping-category-count]");
                if (groupCounter) groupCounter.textContent = String(remainingInGroup);
                if (remainingInGroup === 0) group.remove();
            }
            if (state === "active" && nextCount === 0) {
                if (categoryGroups) categoryGroups.hidden = true;
                if (emptyState) emptyState.hidden = false;
                setShoppingMode(false);
            } else if (state !== "active" && card && !card.querySelector(".shopping-item")) {
                card.remove();
            }
        }, 180);
    };

    document.querySelectorAll(".shopping-delete-form").forEach((form) => {
        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            const button = form.querySelector('button[type="submit"]');
            const article = form.closest(".shopping-item");
            const csrfToken = form.elements.namedItem("csrfmiddlewaretoken")?.value || "";
            setButtonLoading(button, true);
            try {
                const response = await fetch(form.action, {
                    method: "POST",
                    body: new FormData(form),
                    headers: {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"},
                    credentials: "same-origin",
                });
                const payload = await readJsonResponse(response);
                if (!response.ok || !payload.ok) throw new Error(payload.error || "Artikel konnte nicht gelöscht werden.");
                removeArticleFromView(article);
                showToast(payload.message, "success", {
                    actionLabel: "Rückgängig",
                    duration: 9000,
                    onAction: async () => {
                        const body = new FormData();
                        body.append("csrfmiddlewaretoken", csrfToken);
                        body.append("token", payload.restore_token);
                        const restoreResponse = await fetch(payload.restore_url, {
                            method: "POST",
                            body,
                            headers: {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"},
                            credentials: "same-origin",
                        });
                        const restorePayload = await readJsonResponse(restoreResponse);
                        if (!restoreResponse.ok || !restorePayload.ok) {
                            showToast(restorePayload.error || "Wiederherstellen fehlgeschlagen.", "error");
                            return;
                        }
                        showToast(restorePayload.message, "success");
                        window.setTimeout(() => window.location.reload(), 260);
                    },
                });
            } catch (error) {
                setButtonLoading(button, false);
                showToast(error.message || "Artikel konnte nicht gelöscht werden.", "error");
            }
        });
    });

    const setEditPanel = (targetId, shouldOpen) => {
        const panel = document.getElementById(targetId);
        if (!panel) return;
        panel.hidden = !shouldOpen;
        document.querySelectorAll(`[data-edit-target="${targetId}"]`).forEach((button) => {
            if (button.classList.contains("shopping-edit-toggle")) button.setAttribute("aria-expanded", shouldOpen ? "true" : "false");
        });
        if (shouldOpen) panel.querySelector("input")?.focus();
    };

    document.querySelectorAll(".shopping-edit-toggle").forEach((button) => {
        button.addEventListener("click", () => {
            const panel = document.getElementById(button.dataset.editTarget);
            setEditPanel(button.dataset.editTarget, Boolean(panel?.hidden));
        });
    });
    document.querySelectorAll(".shopping-edit-cancel").forEach((button) => {
        button.addEventListener("click", () => setEditPanel(button.dataset.editTarget, false));
    });
    document.querySelectorAll(".shopping-confirm-form").forEach((form) => {
        form.addEventListener("submit", (event) => {
            const message = form.dataset.confirm;
            if (message && !window.confirm(message)) event.preventDefault();
        });
    });

    const stopCamera = () => {
        scanning = false;
        if (scanFrameId !== null) {
            window.cancelAnimationFrame(scanFrameId);
            scanFrameId = null;
        }
        if (cameraStream) {
            cameraStream.getTracks().forEach((track) => track.stop());
            cameraStream = null;
        }
        if (cameraVideo) cameraVideo.srcObject = null;
        barcodeDetector = null;
    };

    const closeScanner = () => {
        stopCamera();
        if (scannerDialog?.open) scannerDialog.close();
    };

    const scannerErrorMessage = (error) => {
        if (error?.name === "NotAllowedError") return "Der Kamerazugriff wurde nicht erlaubt. Du kannst den Barcode manuell eingeben.";
        if (error?.name === "NotFoundError") return "Auf diesem Gerät wurde keine Kamera gefunden.";
        if (error?.name === "NotReadableError") return "Die Kamera wird gerade von einer anderen Anwendung verwendet.";
        return error?.message || "Die Kamera konnte nicht gestartet werden.";
    };

    const handleDetectedBarcode = async (rawValue) => {
        const barcode = String(rawValue || "").replace(/[^0-9]/g, "");
        if (!/^\d{8,14}$/.test(barcode) || !barcodeInput) return false;
        scanning = false;
        barcodeInput.value = barcode;
        setScannerStatus(`Barcode ${barcode} erkannt.`, "success");
        if (navigator.vibrate) navigator.vibrate(80);
        closeScanner();
        await lookupProduct();
        return true;
    };

    const scanVideoFrame = async (timestamp) => {
        if (!scanning || !barcodeDetector || !cameraVideo) return;
        if (timestamp - lastScanAt < 180 || cameraVideo.readyState < 2) {
            scanFrameId = window.requestAnimationFrame(scanVideoFrame);
            return;
        }
        lastScanAt = timestamp;
        try {
            const results = await barcodeDetector.detect(cameraVideo);
            for (const result of results) {
                if (await handleDetectedBarcode(result.rawValue)) return;
            }
        } catch (error) {
            if (error?.name === "SecurityError") {
                setScannerStatus("Der Browser hat die Barcode-Erkennung blockiert.", "error");
                stopCamera();
                return;
            }
        }
        if (scanning) scanFrameId = window.requestAnimationFrame(scanVideoFrame);
    };

    const startScanner = async () => {
        if (!scannerDialog || typeof scannerDialog.showModal !== "function") {
            setLookupStatus("Der Kamera-Scanner wird von diesem Browser nicht unterstützt. Bitte gib den Barcode manuell ein.", "error");
            return;
        }
        if (!scannerDialog.open) scannerDialog.showModal();
        setScannerStatus("Kamera wird vorbereitet …");
        try {
            if (!window.isSecureContext) throw new Error("Der Kamera-Scanner benötigt eine sichere HTTPS-Verbindung.");
            if (!("BarcodeDetector" in window)) throw new Error("Dieser Browser unterstützt keine Barcode-Erkennung. Bitte gib den Code manuell ein.");
            if (!navigator.mediaDevices?.getUserMedia) throw new Error("Der Kamerazugriff wird von diesem Browser nicht unterstützt.");

            const preferredFormats = ["ean_13", "ean_8", "upc_a", "upc_e", "code_128"];
            const supportedFormats = await window.BarcodeDetector.getSupportedFormats();
            const formats = preferredFormats.filter((format) => supportedFormats.includes(format));
            if (!formats.length) throw new Error("Auf diesem Gerät ist kein passendes Barcode-Format verfügbar.");

            barcodeDetector = new window.BarcodeDetector({formats});
            setScannerStatus("Kamerazugriff wird angefragt …");
            cameraStream = await navigator.mediaDevices.getUserMedia({
                audio: false,
                video: {facingMode: {ideal: "environment"}, width: {ideal: 1280}, height: {ideal: 960}},
            });
            cameraVideo.srcObject = cameraStream;
            await cameraVideo.play();
            setScannerStatus("Barcode in den Rahmen halten.");
            scanning = true;
            lastScanAt = 0;
            scanFrameId = window.requestAnimationFrame(scanVideoFrame);
        } catch (error) {
            stopCamera();
            setScannerStatus(scannerErrorMessage(error), "error");
        }
    };

    cameraButton?.addEventListener("click", startScanner);
    cameraCloseButton?.addEventListener("click", closeScanner);
    scannerDialog?.addEventListener("cancel", (event) => { event.preventDefault(); closeScanner(); });
    scannerDialog?.addEventListener("click", (event) => { if (event.target === scannerDialog) closeScanner(); });
    window.addEventListener("pagehide", stopCamera);
    document.addEventListener("visibilitychange", () => { if (document.hidden && cameraStream) closeScanner(); });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && document.body.classList.contains("shopping-mode-active")) setShoppingMode(false);
    });
});
