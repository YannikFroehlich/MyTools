document.addEventListener("DOMContentLoaded", () => {
    const addForm = document.getElementById("shopping-add-form");
    const barcodeInput = document.getElementById("shopping-barcode");
    const lookupButton = document.getElementById("shopping-product-lookup");
    const status = document.getElementById("shopping-lookup-status");
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
    const addCard = document.getElementById("shopping-add-card");
    const addToggle = document.getElementById("shopping-add-toggle");
    const addPanel = document.getElementById("shopping-add-panel");

    let cameraStream = null;
    let barcodeDetector = null;
    let scanning = false;
    let scanFrameId = null;
    let lastScanAt = 0;

    if (addCard && addToggle && addPanel) {
        const mobileLayout = window.matchMedia("(max-width: 620px)");
        let mobileInitialized = false;

        const setAddPanelOpen = (shouldOpen, focusField = false) => {
            addCard.classList.toggle("is-open", shouldOpen);
            addToggle.setAttribute("aria-expanded", shouldOpen ? "true" : "false");
            if (shouldOpen && focusField) {
                window.requestAnimationFrame(() => {
                    document.getElementById("shopping-name")?.focus({preventScroll: true});
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

            addCard.classList.remove("is-collapsible", "is-open");
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

    const setStatus = (message, kind = "") => {
        if (!status) return;
        status.textContent = message;
        status.className = `shopping-lookup-status${kind ? ` is-${kind}` : ""}`;
    };

    const setScannerStatus = (message, kind = "") => {
        if (!scannerStatus) return;
        scannerStatus.textContent = message;
        scannerStatus.className = `shopping-scanner-status${kind ? ` is-${kind}` : ""}`;
    };

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
        setStatus("");
    };

    const lookupProduct = async () => {
        if (!lookupButton || !addForm || !barcodeInput) return;

        const barcode = barcodeInput.value.replace(/[\s-]+/g, "");
        if (!/^\d{8,14}$/.test(barcode)) {
            setStatus("Bitte gib einen Barcode mit 8 bis 14 Ziffern ein.", "error");
            barcodeInput.focus();
            return;
        }

        const url = addForm.dataset.productUrl.replace("00000000", encodeURIComponent(barcode));
        lookupButton.disabled = true;
        lookupButton.classList.add("is-loading");
        setStatus("Produkt wird gesucht …", "loading");

        try {
            const response = await fetch(url, {
                headers: {"Accept": "application/json"},
                credentials: "same-origin",
            });
            const payload = await response.json();
            if (!response.ok || !payload.ok) {
                throw new Error(payload.error || "Produkt konnte nicht geladen werden.");
            }

            const product = payload.product || {};
            barcodeInput.value = product.barcode || barcode;
            const nameInput = document.getElementById("shopping-name");
            if (nameInput && product.name) nameInput.value = product.name;

            const brandInput = document.getElementById("shopping-brand");
            const quantityInput = document.getElementById("shopping-product-quantity");
            const imageInput = document.getElementById("shopping-image-url");
            if (brandInput) brandInput.value = product.brand || "";
            if (quantityInput) quantityInput.value = product.quantity || "";
            if (imageInput) imageInput.value = product.image_url || "";

            if (previewTitle) previewTitle.textContent = product.name || "Produkt gefunden";
            if (previewMeta) {
                previewMeta.textContent = [product.brand, product.quantity].filter(Boolean).join(" · ");
            }
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
            setStatus("Produktdaten wurden übernommen.", "success");
            if (nameInput) nameInput.focus();
        } catch (error) {
            clearProductData();
            setStatus(error.message || "Produkt konnte nicht geladen werden.", "error");
        } finally {
            lookupButton.disabled = false;
            lookupButton.classList.remove("is-loading");
        }
    };

    if (barcodeInput) {
        barcodeInput.addEventListener("input", clearProductData);
    }

    if (lookupButton) {
        lookupButton.addEventListener("click", lookupProduct);
    }

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
        if (error?.name === "NotAllowedError") {
            return "Der Kamerazugriff wurde nicht erlaubt. Du kannst den Barcode manuell eingeben.";
        }
        if (error?.name === "NotFoundError") {
            return "Auf diesem Gerät wurde keine Kamera gefunden.";
        }
        if (error?.name === "NotReadableError") {
            return "Die Kamera wird gerade von einer anderen Anwendung verwendet.";
        }
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
            setStatus("Der Kamera-Scanner wird von diesem Browser nicht unterstützt. Bitte gib den Barcode manuell ein.", "error");
            return;
        }

        if (!scannerDialog.open) scannerDialog.showModal();
        setScannerStatus("Kamera wird vorbereitet …");

        try {
            if (!window.isSecureContext) {
                throw new Error("Der Kamera-Scanner benötigt eine sichere HTTPS-Verbindung.");
            }
            if (!("BarcodeDetector" in window)) {
                throw new Error("Dieser Browser unterstützt keine Barcode-Erkennung. Bitte gib den Code manuell ein.");
            }
            if (!navigator.mediaDevices?.getUserMedia) {
                throw new Error("Der Kamerazugriff wird von diesem Browser nicht unterstützt.");
            }

            const preferredFormats = ["ean_13", "ean_8", "upc_a", "upc_e", "code_128"];
            const supportedFormats = await window.BarcodeDetector.getSupportedFormats();
            const formats = preferredFormats.filter((format) => supportedFormats.includes(format));
            if (!formats.length) {
                throw new Error("Auf diesem Gerät ist kein passendes Barcode-Format verfügbar.");
            }

            barcodeDetector = new window.BarcodeDetector({formats});
            setScannerStatus("Kamerazugriff wird angefragt …");
            cameraStream = await navigator.mediaDevices.getUserMedia({
                audio: false,
                video: {
                    facingMode: {ideal: "environment"},
                    width: {ideal: 1280},
                    height: {ideal: 960},
                },
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
    scannerDialog?.addEventListener("cancel", (event) => {
        event.preventDefault();
        closeScanner();
    });
    scannerDialog?.addEventListener("click", (event) => {
        if (event.target === scannerDialog) closeScanner();
    });
    window.addEventListener("pagehide", stopCamera);
    document.addEventListener("visibilitychange", () => {
        if (document.hidden && cameraStream) closeScanner();
    });

    const setEditPanel = (targetId, shouldOpen) => {
        const panel = document.getElementById(targetId);
        if (!panel) return;
        panel.hidden = !shouldOpen;
        document.querySelectorAll(`[data-edit-target="${targetId}"]`).forEach((button) => {
            if (button.classList.contains("shopping-edit-toggle")) {
                button.setAttribute("aria-expanded", shouldOpen ? "true" : "false");
            }
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
});
