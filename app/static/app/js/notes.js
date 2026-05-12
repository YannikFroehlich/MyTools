document.addEventListener("DOMContentLoaded", () => {
    const deleteForms = document.querySelectorAll(".note-delete-form");

    deleteForms.forEach((form) => {
        form.addEventListener("submit", (event) => {
            const confirmed = confirm("Möchtest du diese Notiz wirklich endgültig löschen?");

            if (!confirmed) {
                event.preventDefault();
            }
        });
    });

    const editor = document.getElementById("note-editor");
    const hiddenInput = document.getElementById("id_content");
    const form = editor ? editor.closest("form") : null;

    if (!editor || !hiddenInput || !form) {
        return;
    }

    if (!editor.innerHTML.trim()) {
        editor.style.textAlign = "left";
    }

    const syncEditorToInput = () => {
        hiddenInput.value = editor.innerHTML.trim();
    };

    const focusEditor = () => {
        editor.focus();
    };

    document.querySelectorAll("[data-command]").forEach((button) => {
        button.addEventListener("click", () => {
            const command = button.dataset.command;

            focusEditor();
            document.execCommand(command, false, null);
            syncEditorToInput();
        });
    });

    const headingSelect = document.getElementById("editor-heading");

    if (headingSelect) {
        headingSelect.addEventListener("change", () => {
            focusEditor();

            const value = headingSelect.value || "p";
            document.execCommand("formatBlock", false, value);

            headingSelect.value = "p";
            syncEditorToInput();
        });
    }

    const fontSizeSelect = document.getElementById("editor-font-size");

    if (fontSizeSelect) {
        fontSizeSelect.addEventListener("change", () => {
            const size = fontSizeSelect.value;

            if (!size) {
                return;
            }

            focusEditor();
            applyFontSize(size);
            fontSizeSelect.value = "";
            syncEditorToInput();
        });
    }

    const applyFontSize = (size) => {
        const selection = window.getSelection();

        if (!selection || selection.rangeCount === 0) {
            return;
        }

        const range = selection.getRangeAt(0);

        if (range.collapsed) {
            return;
        }

        const span = document.createElement("span");
        span.style.fontSize = size;

        try {
            span.appendChild(range.extractContents());
            range.insertNode(span);

            selection.removeAllRanges();

            const newRange = document.createRange();
            newRange.selectNodeContents(span);
            selection.addRange(newRange);
        } catch (error) {
            console.error("Schriftgröße konnte nicht angewendet werden:", error);
        }
    };

    editor.addEventListener("input", syncEditorToInput);
    editor.addEventListener("blur", syncEditorToInput);

    editor.addEventListener("paste", (event) => {
        event.preventDefault();

        const text = event.clipboardData.getData("text/plain");
        document.execCommand("insertText", false, text);

        syncEditorToInput();
    });

    form.addEventListener("submit", () => {
        syncEditorToInput();
    });

    syncEditorToInput();
});