(() => {
    const form = document.getElementById("qr-code-form");
    if (!form) return;

    const typeInputs = Array.from(form.querySelectorAll('input[name="qr_type"]'));
    const panels = Array.from(form.querySelectorAll("[data-qr-panel]"));

    function syncPanels() {
        const activeType = typeInputs.find((input) => input.checked)?.value || "text";
        panels.forEach((panel) => {
            panel.hidden = panel.dataset.qrPanel !== activeType;
        });
    }

    typeInputs.forEach((input) => input.addEventListener("change", syncPanels));
    syncPanels();

    const copyButton = document.getElementById("copy-qr-payload");
    if (copyButton) {
        copyButton.addEventListener("click", async () => {
            const payload = copyButton.dataset.payload || "";
            try {
                await navigator.clipboard.writeText(payload);
                const originalText = copyButton.innerHTML;
                copyButton.innerHTML = '<i class="fa-solid fa-check"></i> Kopiert';
                setTimeout(() => {
                    copyButton.innerHTML = originalText;
                }, 1400);
            } catch (error) {
                console.warn("QR-Inhalt konnte nicht kopiert werden", error);
            }
        });
    }
})();
