(() => {
    const STORAGE_KEY = "mytools_color_palette_v1";
    const state = {
        color: "#7C3AED",
        palette: [],
        gradient: "linear-gradient(135deg, #7C3AED, #22D3EE)",
    };

    const els = {
        screenPickerButton: document.getElementById("screen-picker-button"),
        supportNote: document.getElementById("eyedropper-support-note"),
        nativePicker: document.getElementById("native-color-picker"),
        hexInput: document.getElementById("hex-value"),
        rgbInput: document.getElementById("rgb-value"),
        hslInput: document.getElementById("hsl-value"),
        currentHex: document.getElementById("current-hex"),
        currentRgb: document.getElementById("current-rgb"),
        mainSwatch: document.getElementById("main-swatch"),
        saveButton: document.getElementById("save-color-button"),
        randomButton: document.getElementById("random-color-button"),
        upload: document.getElementById("image-upload"),
        canvas: document.getElementById("image-canvas"),
        imageEmpty: document.getElementById("image-empty-state"),
        paletteList: document.getElementById("palette-list"),
        clearPalette: document.getElementById("clear-palette-button"),
        contrastPreview: document.getElementById("contrast-preview"),
        contrastWhite: document.getElementById("contrast-white"),
        contrastBlack: document.getElementById("contrast-black"),
        contrastRecommendation: document.getElementById("contrast-recommendation"),
        gradientPreview: document.getElementById("gradient-preview"),
        copyGradient: document.getElementById("copy-gradient-button"),
    };

    const ctx = els.canvas ? els.canvas.getContext("2d", { willReadFrequently: true }) : null;

    function clamp(value, min, max) {
        return Math.min(max, Math.max(min, value));
    }

    function normalizeHex(value) {
        let hex = String(value || "").trim().replace(/^#/, "");
        if (hex.length === 3) {
            hex = hex.split("").map((part) => part + part).join("");
        }
        if (!/^[0-9a-fA-F]{6}$/.test(hex)) {
            return null;
        }
        return `#${hex.toUpperCase()}`;
    }

    function hexToRgb(hex) {
        const clean = normalizeHex(hex);
        if (!clean) return null;
        const value = clean.slice(1);
        return {
            r: parseInt(value.slice(0, 2), 16),
            g: parseInt(value.slice(2, 4), 16),
            b: parseInt(value.slice(4, 6), 16),
        };
    }

    function rgbToHex(r, g, b) {
        return `#${[r, g, b].map((value) => clamp(value, 0, 255).toString(16).padStart(2, "0")).join("").toUpperCase()}`;
    }

    function rgbToHsl({ r, g, b }) {
        let red = r / 255;
        let green = g / 255;
        let blue = b / 255;

        const max = Math.max(red, green, blue);
        const min = Math.min(red, green, blue);
        let h = 0;
        let s = 0;
        const l = (max + min) / 2;

        if (max !== min) {
            const d = max - min;
            s = l > 0.5 ? d / (2 - max - min) : d / (max + min);

            switch (max) {
                case red:
                    h = (green - blue) / d + (green < blue ? 6 : 0);
                    break;
                case green:
                    h = (blue - red) / d + 2;
                    break;
                default:
                    h = (red - green) / d + 4;
                    break;
            }

            h /= 6;
        }

        return {
            h: Math.round(h * 360),
            s: Math.round(s * 100),
            l: Math.round(l * 100),
        };
    }

    function relativeLuminance({ r, g, b }) {
        const convert = (channel) => {
            const c = channel / 255;
            return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
        };
        return 0.2126 * convert(r) + 0.7152 * convert(g) + 0.0722 * convert(b);
    }

    function contrastRatio(rgbA, rgbB) {
        const l1 = relativeLuminance(rgbA);
        const l2 = relativeLuminance(rgbB);
        const lighter = Math.max(l1, l2);
        const darker = Math.min(l1, l2);
        return (lighter + 0.05) / (darker + 0.05);
    }

    function gradeContrast(ratio) {
        if (ratio >= 7) return "AAA";
        if (ratio >= 4.5) return "AA";
        if (ratio >= 3) return "Großer Text";
        return "Schwach";
    }

    function getReadableText(rgb) {
        const whiteRatio = contrastRatio(rgb, { r: 255, g: 255, b: 255 });
        const blackRatio = contrastRatio(rgb, { r: 0, g: 0, b: 0 });
        return whiteRatio >= blackRatio ? "#FFFFFF" : "#0F172A";
    }

    function toast(message) {
        const oldToast = document.querySelector(".color-toast");
        if (oldToast) oldToast.remove();

        const toastElement = document.createElement("div");
        toastElement.className = "color-toast";
        toastElement.textContent = message;
        toastElement.style.cssText = `
            position: fixed;
            right: 18px;
            bottom: 18px;
            z-index: 9999;
            padding: 12px 16px;
            border-radius: 999px;
            color: #fff;
            background: rgba(15, 23, 42, 0.94);
            box-shadow: 0 14px 34px rgba(0,0,0,.28);
            font-weight: 900;
        `;
        document.body.appendChild(toastElement);
        window.setTimeout(() => toastElement.remove(), 1800);
    }

    async function copyText(value) {
        try {
            await navigator.clipboard.writeText(value);
            toast("Kopiert");
        } catch {
            toast("Kopieren nicht möglich");
        }
    }

    function updateColor(hex, options = {}) {
        const normalized = normalizeHex(hex);
        if (!normalized) return;

        state.color = normalized;
        const rgb = hexToRgb(normalized);
        const hsl = rgbToHsl(rgb);
        const rgbString = `rgb(${rgb.r}, ${rgb.g}, ${rgb.b})`;
        const hslString = `hsl(${hsl.h}, ${hsl.s}%, ${hsl.l}%)`;
        const readableText = getReadableText(rgb);

        els.nativePicker.value = normalized.toLowerCase();
        els.hexInput.value = normalized;
        els.rgbInput.value = rgbString;
        els.hslInput.value = hslString;
        els.currentHex.textContent = normalized;
        els.currentRgb.textContent = rgbString;
        els.mainSwatch.style.background = normalized;
        els.mainSwatch.style.boxShadow = `inset 0 0 0 1px rgba(255,255,255,.34), 0 18px 36px ${normalized}55`;

        els.contrastPreview.style.background = normalized;
        els.contrastPreview.style.color = readableText;

        const whiteRatio = contrastRatio(rgb, { r: 255, g: 255, b: 255 });
        const blackRatio = contrastRatio(rgb, { r: 0, g: 0, b: 0 });
        els.contrastWhite.textContent = `${whiteRatio.toFixed(2)} · ${gradeContrast(whiteRatio)}`;
        els.contrastBlack.textContent = `${blackRatio.toFixed(2)} · ${gradeContrast(blackRatio)}`;
        els.contrastRecommendation.textContent = whiteRatio >= blackRatio ? "Weißer Text" : "Dunkler Text";

        const secondColor = options.secondColor || suggestSecondColor(rgb);
        state.gradient = `linear-gradient(135deg, ${normalized}, ${secondColor})`;
        els.gradientPreview.style.background = state.gradient;
    }

    function suggestSecondColor(rgb) {
        const hsl = rgbToHsl(rgb);
        const hue = (hsl.h + 155) % 360;
        return hslToHex(hue, Math.max(54, hsl.s), Math.max(48, Math.min(72, hsl.l + 8)));
    }

    function hslToHex(h, s, l) {
        s /= 100;
        l /= 100;
        const c = (1 - Math.abs(2 * l - 1)) * s;
        const x = c * (1 - Math.abs((h / 60) % 2 - 1));
        const m = l - c / 2;
        let r = 0, g = 0, b = 0;

        if (h < 60) [r, g, b] = [c, x, 0];
        else if (h < 120) [r, g, b] = [x, c, 0];
        else if (h < 180) [r, g, b] = [0, c, x];
        else if (h < 240) [r, g, b] = [0, x, c];
        else if (h < 300) [r, g, b] = [x, 0, c];
        else [r, g, b] = [c, 0, x];

        return rgbToHex(
            Math.round((r + m) * 255),
            Math.round((g + m) * 255),
            Math.round((b + m) * 255)
        );
    }

    function loadPalette() {
        try {
            const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
            state.palette = Array.isArray(parsed) ? parsed.filter(normalizeHex).map(normalizeHex) : [];
        } catch {
            state.palette = [];
        }
    }

    function savePalette() {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(state.palette));
    }

    function renderPalette() {
        els.paletteList.innerHTML = "";
        if (!state.palette.length) {
            const empty = document.createElement("div");
            empty.className = "palette-empty";
            empty.textContent = "Noch keine Farben gespeichert.";
            els.paletteList.appendChild(empty);
            return;
        }

        state.palette.forEach((hex, index) => {
            const item = document.createElement("article");
            item.className = "palette-item";
            item.innerHTML = `
                <div class="palette-swatch" style="background:${hex}" title="${hex}"></div>
                <div class="palette-item-footer">
                    <strong>${hex}</strong>
                    <button type="button" aria-label="Farbe entfernen">
                        <i class="fa-solid fa-xmark"></i>
                    </button>
                </div>
            `;

            item.querySelector(".palette-swatch").addEventListener("click", () => updateColor(hex));
            item.querySelector("strong").addEventListener("click", () => copyText(hex));
            item.querySelector("button").addEventListener("click", () => {
                state.palette.splice(index, 1);
                savePalette();
                renderPalette();
            });

            els.paletteList.appendChild(item);
        });
    }

    function addCurrentToPalette() {
        if (!state.palette.includes(state.color)) {
            state.palette.unshift(state.color);
            state.palette = state.palette.slice(0, 36);
            savePalette();
            renderPalette();
        }
        toast("Farbe gespeichert");
    }

    function initEyeDropper() {
        if (!els.screenPickerButton) return;

        if (!("EyeDropper" in window)) {
            els.screenPickerButton.disabled = true;
            els.screenPickerButton.classList.remove("color-btn-primary");
            els.screenPickerButton.classList.add("color-btn-soft");
            els.supportNote.textContent = "Dein Browser unterstützt den Bildschirm-Eyedropper nicht. Nutze den Bild-Upload oder Chrome/Edge.";
            return;
        }

        els.supportNote.textContent = "Der Bildschirm-Eyedropper wird von deinem Browser unterstützt.";

        els.screenPickerButton.addEventListener("click", async () => {
            try {
                const eyeDropper = new window.EyeDropper();
                const result = await eyeDropper.open();
                updateColor(result.sRGBHex);
                addCurrentToPalette();
            } catch {
                toast("Farbaufnahme abgebrochen");
            }
        });
    }

    function initImagePicker() {
        if (!els.upload || !els.canvas || !ctx) return;

        els.upload.addEventListener("change", () => {
            const file = els.upload.files && els.upload.files[0];
            if (!file) return;

            const reader = new FileReader();
            reader.onload = () => {
                const image = new Image();
                image.onload = () => {
                    const maxWidth = 980;
                    const scale = Math.min(1, maxWidth / image.width);
                    els.canvas.width = Math.round(image.width * scale);
                    els.canvas.height = Math.round(image.height * scale);
                    ctx.clearRect(0, 0, els.canvas.width, els.canvas.height);
                    ctx.drawImage(image, 0, 0, els.canvas.width, els.canvas.height);
                    els.canvas.style.display = "block";
                    els.imageEmpty.style.display = "none";
                };
                image.src = reader.result;
            };
            reader.readAsDataURL(file);
        });

        els.canvas.addEventListener("click", (event) => {
            const rect = els.canvas.getBoundingClientRect();
            const x = Math.floor((event.clientX - rect.left) * (els.canvas.width / rect.width));
            const y = Math.floor((event.clientY - rect.top) * (els.canvas.height / rect.height));
            const data = ctx.getImageData(x, y, 1, 1).data;
            const hex = rgbToHex(data[0], data[1], data[2]);
            updateColor(hex);
            addCurrentToPalette();
        });
    }

    function bindEvents() {
        els.nativePicker.addEventListener("input", (event) => updateColor(event.target.value));
        els.hexInput.addEventListener("input", (event) => {
            const normalized = normalizeHex(event.target.value);
            if (normalized) updateColor(normalized);
        });

        document.querySelectorAll("[data-copy-target]").forEach((button) => {
            button.addEventListener("click", () => {
                const target = document.getElementById(button.dataset.copyTarget);
                if (target) copyText(target.value);
            });
        });

        els.saveButton.addEventListener("click", addCurrentToPalette);
        els.randomButton.addEventListener("click", () => {
            const hex = rgbToHex(
                Math.floor(Math.random() * 256),
                Math.floor(Math.random() * 256),
                Math.floor(Math.random() * 256)
            );
            updateColor(hex);
        });

        els.clearPalette.addEventListener("click", () => {
            if (!state.palette.length) return;
            if (!window.confirm("Palette wirklich leeren?")) return;
            state.palette = [];
            savePalette();
            renderPalette();
        });

        els.copyGradient.addEventListener("click", () => copyText(state.gradient));
    }

    loadPalette();
    renderPalette();
    updateColor(state.color);
    bindEvents();
    initEyeDropper();
    initImagePicker();
})();
