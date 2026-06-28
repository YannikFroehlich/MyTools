(() => {
    const root = document.querySelector("[data-file-converter]");
    if (!root) return;

    const dropZone = root.querySelector("[data-drop-zone]");
    const fileInput = root.querySelector("[data-file-input]");
    const fileName = root.querySelector("[data-file-name]");
    const fileMeta = root.querySelector("[data-file-meta]");
    const targetSelect = root.querySelector("[data-target-select]");
    const hint = root.querySelector("[data-format-hint] span");
    const label = (key, fallback) => root.dataset[key] || fallback;

    const formatBytes = (bytes) => {
        const units = ["B", "KB", "MB", "GB"];
        let value = bytes || 0;
        let index = 0;
        while (value >= 1024 && index < units.length - 1) {
            value /= 1024;
            index += 1;
        }
        return `${value.toFixed(index ? 1 : 0)} ${units[index]}`;
    };

    const updateHint = () => {
        if (!hint || !targetSelect) return;
        if (targetSelect.value === "pdf") {
            hint.textContent = label("labelPdfHint", "PDF unterstützt Dokumente, Tabellen, Präsentationen, Textdateien und Bilder.");
            fileInput.setAttribute("accept", ".doc,.docx,.odt,.rtf,.txt,.html,.htm,.csv,.xls,.xlsx,.ods,.ppt,.pptx,.odp,.png,.jpg,.jpeg,.webp,.bmp,.gif");
        } else {
            hint.textContent = label("labelImageHint", "PNG, JPG und WEBP sind nur für Bilddateien verfügbar.");
            fileInput.setAttribute("accept", ".png,.jpg,.jpeg,.webp,.bmp,.gif");
        }
    };

    const setFile = (file) => {
        if (!file) return;
        fileName.textContent = file.name;
        fileMeta.textContent = `${formatBytes(file.size)} · ${file.type || label("labelUnknownFileType", "unbekannter Dateityp")}`;
        dropZone.classList.add("has-file");
    };

    fileInput?.addEventListener("change", () => setFile(fileInput.files[0]));
    targetSelect?.addEventListener("change", updateHint);

    ["dragenter", "dragover"].forEach((eventName) => {
        dropZone?.addEventListener(eventName, (event) => {
            event.preventDefault();
            dropZone.classList.add("is-dragover");
        });
    });

    ["dragleave", "drop"].forEach((eventName) => {
        dropZone?.addEventListener(eventName, (event) => {
            event.preventDefault();
            dropZone.classList.remove("is-dragover");
        });
    });

    dropZone?.addEventListener("drop", (event) => {
        const file = event.dataTransfer.files[0];
        if (!file) return;
        fileInput.files = event.dataTransfer.files;
        setFile(file);
    });

    updateHint();
})();
