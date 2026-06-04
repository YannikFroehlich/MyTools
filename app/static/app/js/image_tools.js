(() => {
    const root = document.querySelector("[data-image-tool]");
    if (!root) return;

    const input = document.getElementById("image-input");
    const pickButtons = root.querySelectorAll("[data-pick-image], [data-pick-image-secondary]");
    const emptyPicker = root.querySelector("[data-empty-picker]");
    const selectedInfo = root.querySelector("[data-selected-info]");
    const selectedPreview = root.querySelector("[data-selected-preview]");
    const selectedName = root.querySelector("[data-selected-name]");
    const selectedSize = root.querySelector("[data-selected-size]");
    const selectedFormat = root.querySelector("[data-selected-format]");
    const selectedDimensions = root.querySelector("[data-selected-dimensions]");
    const dropZone = root.querySelector("[data-drop-zone]");
    const convertButton = root.querySelector("[data-convert]");
    const formatInput = document.getElementById("image-format");
    const qualityInput = document.getElementById("image-quality");
    const widthInput = document.getElementById("image-width");
    const heightInput = document.getElementById("image-height");
    const scaleModeInput = document.getElementById("image-scale-mode");
    const scalePercentInput = document.getElementById("image-scale-percent");
    const smoothingInput = document.getElementById("image-smoothing");
    const bgInput = document.getElementById("image-bg");
    const noUpscaleInput = document.getElementById("image-no-upscale");
    const autoDownloadInput = document.getElementById("image-auto-download");
    const qualityLabel = document.getElementById("quality-label");
    const estimate = root.querySelector("[data-estimate]");
    const targetDimensions = root.querySelector("[data-target-dimensions]");
    const result = root.querySelector("[data-result]");
    const preview = root.querySelector("[data-preview]");
    const beforeSize = root.querySelector("[data-before-size]");
    const afterSize = root.querySelector("[data-after-size]");
    const savedSize = root.querySelector("[data-saved-size]");
    const outputMeta = root.querySelector("[data-output-meta]");
    const download = root.querySelector("[data-download]");
    const presetButtons = root.querySelectorAll("[data-preset]");

    let selectedFile = null;
    let selectedImageMeta = null;
    let lastObjectUrl = null;
    let selectedObjectUrl = null;

    const formatBytes = (bytes) => {
        if (!bytes) return "0 B";
        const units = ["B", "KB", "MB", "GB"];
        let value = bytes;
        let index = 0;
        while (value >= 1024 && index < units.length - 1) {
            value /= 1024;
            index += 1;
        }
        return `${value.toFixed(index ? 1 : 0)} ${units[index]}`;
    };

    const readableType = (type) => {
        if (!type) return "Unbekannt";
        return type.replace("image/", "").replace("jpeg", "jpg").toUpperCase();
    };

    const loadImage = (file) => new Promise((resolve, reject) => {
        const image = new Image();
        const url = URL.createObjectURL(file);
        image.onload = () => {
            URL.revokeObjectURL(url);
            resolve(image);
        };
        image.onerror = () => {
            URL.revokeObjectURL(url);
            reject(new Error("Das Bild konnte nicht geladen werden."));
        };
        image.src = url;
    });

    const getTargetSize = () => {
        if (!selectedImageMeta) return { width: 0, height: 0 };
        const originalWidth = selectedImageMeta.width;
        const originalHeight = selectedImageMeta.height;
        const mode = scaleModeInput.value;

        if (mode === "original") {
            return { width: originalWidth, height: originalHeight };
        }

        if (mode === "percent") {
            const percent = Math.min(100, Math.max(5, Number(scalePercentInput.value) || 100)) / 100;
            const scale = noUpscaleInput.checked ? Math.min(1, percent) : percent;
            return {
                width: Math.max(1, Math.round(originalWidth * scale)),
                height: Math.max(1, Math.round(originalHeight * scale)),
            };
        }

        const maxWidth = Math.max(64, Number(widthInput.value) || originalWidth);
        const maxHeight = Math.max(64, Number(heightInput.value) || originalHeight);
        let scale = Math.min(maxWidth / originalWidth, maxHeight / originalHeight);
        if (noUpscaleInput.checked) scale = Math.min(1, scale);
        return {
            width: Math.max(1, Math.round(originalWidth * scale)),
            height: Math.max(1, Math.round(originalHeight * scale)),
        };
    };

    const updateEstimate = () => {
        qualityLabel.textContent = `${Math.round(Number(qualityInput.value) * 100)}%`;
        const { width, height } = getTargetSize();
        if (width && height) {
            targetDimensions.textContent = `${width} × ${height}px`;
            estimate.hidden = false;
        }
    };

    const setPreset = (preset) => {
        presetButtons.forEach((button) => button.classList.toggle("active", button.dataset.preset === preset));
        if (preset === "small") {
            formatInput.value = "image/webp";
            qualityInput.value = "0.62";
            widthInput.value = "1280";
            heightInput.value = "720";
            scaleModeInput.value = "contain";
            smoothingInput.value = "medium";
        } else if (preset === "quality") {
            formatInput.value = "image/webp";
            qualityInput.value = "0.92";
            widthInput.value = "2560";
            heightInput.value = "1440";
            scaleModeInput.value = "contain";
            smoothingInput.value = "high";
        } else if (preset === "avatar") {
            formatInput.value = "image/webp";
            qualityInput.value = "0.86";
            widthInput.value = "512";
            heightInput.value = "512";
            scaleModeInput.value = "contain";
            smoothingInput.value = "high";
        } else {
            formatInput.value = "image/webp";
            qualityInput.value = "0.82";
            widthInput.value = "1920";
            heightInput.value = "1080";
            scaleModeInput.value = "contain";
            smoothingInput.value = "high";
        }
        updateEstimate();
    };

    const setFile = async (file) => {
        if (!file || !file.type.startsWith("image/")) return;
        selectedFile = file;
        result.hidden = true;
        beforeSize.textContent = formatBytes(file.size);

        try {
            const image = await loadImage(file);
            selectedImageMeta = {
                width: image.naturalWidth || image.width,
                height: image.naturalHeight || image.height,
            };
        } catch (error) {
            selectedImageMeta = null;
        }

        if (selectedObjectUrl) URL.revokeObjectURL(selectedObjectUrl);
        selectedObjectUrl = URL.createObjectURL(file);
        selectedPreview.src = selectedObjectUrl;
        selectedName.textContent = file.name;
        selectedSize.textContent = formatBytes(file.size);
        selectedFormat.textContent = readableType(file.type);
        selectedDimensions.textContent = selectedImageMeta ? `${selectedImageMeta.width} × ${selectedImageMeta.height}px` : "-";
        selectedInfo.hidden = false;
        if (emptyPicker) emptyPicker.hidden = true;
        dropZone.classList.add("has-file");
        convertButton.disabled = false;
        updateEstimate();
    };

    pickButtons.forEach((button) => button.addEventListener("click", () => input.click()));
    input.addEventListener("change", () => setFile(input.files[0]));

    [qualityInput, widthInput, heightInput, scaleModeInput, scalePercentInput, smoothingInput, noUpscaleInput].forEach((element) => {
        element.addEventListener("input", updateEstimate);
        element.addEventListener("change", updateEstimate);
    });

    presetButtons.forEach((button) => button.addEventListener("click", () => setPreset(button.dataset.preset)));

    ["dragenter", "dragover"].forEach((eventName) => {
        dropZone.addEventListener(eventName, (event) => {
            event.preventDefault();
            dropZone.classList.add("is-dragover");
        });
    });

    ["dragleave", "drop"].forEach((eventName) => {
        dropZone.addEventListener(eventName, (event) => {
            event.preventDefault();
            dropZone.classList.remove("is-dragover");
        });
    });

    dropZone.addEventListener("drop", (event) => setFile(event.dataTransfer.files[0]));

    convertButton.addEventListener("click", async () => {
        if (!selectedFile) return;
        convertButton.disabled = true;
        convertButton.classList.add("is-loading");
        try {
            const image = await loadImage(selectedFile);
            const target = getTargetSize();
            const outputType = formatInput.value;
            const canvas = document.createElement("canvas");
            canvas.width = target.width;
            canvas.height = target.height;

            const keepAlpha = outputType === "image/png" || outputType === "image/webp";
            const ctx = canvas.getContext("2d", { alpha: keepAlpha });
            ctx.imageSmoothingEnabled = true;
            ctx.imageSmoothingQuality = smoothingInput.value;

            if (outputType === "image/jpeg") {
                ctx.fillStyle = bgInput.value || "#ffffff";
                ctx.fillRect(0, 0, target.width, target.height);
            }

            ctx.drawImage(image, 0, 0, target.width, target.height);

            const quality = outputType === "image/png" ? undefined : Number(qualityInput.value);
            const blob = await new Promise((resolve) => canvas.toBlob(resolve, outputType, quality));
            if (!blob) throw new Error("Konvertierung fehlgeschlagen.");

            if (lastObjectUrl) URL.revokeObjectURL(lastObjectUrl);
            lastObjectUrl = URL.createObjectURL(blob);
            preview.src = lastObjectUrl;
            download.href = lastObjectUrl;
            const extension = outputType.split("/")[1].replace("jpeg", "jpg");
            download.download = `${selectedFile.name.replace(/\.[^.]+$/, "") || "bild"}-optimiert.${extension}`;

            afterSize.textContent = formatBytes(blob.size);
            const saved = selectedFile.size - blob.size;
            const savedPercent = selectedFile.size ? Math.round((saved / selectedFile.size) * 100) : 0;
            savedSize.textContent = saved > 0 ? `${formatBytes(saved)} weniger · ${savedPercent}%` : `${formatBytes(Math.abs(saved))} größer`;
            outputMeta.textContent = `${target.width} × ${target.height}px · ${readableType(outputType)}`;
            result.hidden = false;
            result.scrollIntoView({ behavior: "smooth", block: "nearest" });

            if (autoDownloadInput.checked) download.click();
        } catch (error) {
            alert(error.message || "Das Bild konnte nicht verarbeitet werden.");
        } finally {
            convertButton.disabled = false;
            convertButton.classList.remove("is-loading");
        }
    });

    updateEstimate();
})();
