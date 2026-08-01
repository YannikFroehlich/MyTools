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
    const toolbar = document.querySelector(".notes-editor-toolbar");

    if (!editor || !hiddenInput || !form) {
        return;
    }

    if (!editor.innerHTML.trim()) {
        editor.style.textAlign = "left";
    }

    const syncEditorToInput = () => {
        hiddenInput.value = editor.innerHTML.trim();
    };

    const serializeFormState = () => {
        syncEditorToInput();

        const entries = Array.from(new FormData(form).entries())
            .filter(([name]) => name !== "csrfmiddlewaretoken")
            .map(([name, value]) => [
                name,
                typeof value === "string"
                    ? value
                    : `${value.name}:${value.size}:${value.lastModified}`,
            ]);

        return JSON.stringify(entries);
    };

    const focusEditor = () => {
        editor.focus({ preventScroll: true });
    };

    let savedEditorRange = null;

    const isInsideEditor = (node) => node === editor || editor.contains(node);

    const saveEditorSelection = () => {
        const selection = window.getSelection();

        if (!selection || selection.rangeCount === 0) {
            return;
        }

        const range = selection.getRangeAt(0);

        if (!isInsideEditor(range.startContainer) || !isInsideEditor(range.endContainer)) {
            return;
        }

        savedEditorRange = range.cloneRange();
    };

    const restoreEditorSelection = () => {
        if (
            !savedEditorRange
            || !isInsideEditor(savedEditorRange.startContainer)
            || !isInsideEditor(savedEditorRange.endContainer)
        ) {
            return false;
        }

        const selection = window.getSelection();

        if (!selection) {
            return false;
        }

        const rangeToRestore = savedEditorRange.cloneRange();

        try {
            focusEditor();
            selection.removeAllRanges();
            selection.addRange(rangeToRestore);
            return true;
        } catch (error) {
            savedEditorRange = null;
            return false;
        }
    };

    document.addEventListener("selectionchange", saveEditorSelection);

    if (toolbar) {
        toolbar.addEventListener("pointerdown", saveEditorSelection, true);
    }

    const executeEditorCommand = (command) => {
        if (command === "insertChecklist") {
            document.execCommand(
                "insertHTML",
                false,
                '<ul class="note-checklist"><li data-checked="false">Aufgabe</li></ul>'
            );
        } else {
            document.execCommand(command, false, null);
        }

        saveEditorSelection();
        syncEditorToInput();
    };

    document.querySelectorAll("[data-command]").forEach((button) => {
        button.addEventListener("click", () => {
            const command = button.dataset.command;

            if (!restoreEditorSelection()) {
                focusEditor();
            }

            executeEditorCommand(command);
        });
    });

    const shortcutCommands = {
        b: "bold",
        i: "italic",
        u: "underline",
    };

    const shiftedShortcutCommands = {
        x: "strikeThrough",
    };

    editor.addEventListener("keydown", (event) => {
        if (!(event.ctrlKey || event.metaKey) || event.altKey || event.isComposing) {
            return;
        }

        const key = event.key.toLowerCase();
        const command = event.shiftKey
            ? shiftedShortcutCommands[key]
            : shortcutCommands[key];

        if (!command) {
            return;
        }

        event.preventDefault();
        executeEditorCommand(command);
    });

    const headingSelect = document.getElementById("editor-heading");

    if (headingSelect) {
        headingSelect.addEventListener("change", () => {
            if (!restoreEditorSelection()) {
                focusEditor();
            }

            const value = headingSelect.value || "p";
            document.execCommand("formatBlock", false, value);

            headingSelect.value = "p";
            saveEditorSelection();
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

            if (!restoreEditorSelection()) {
                focusEditor();
            }

            applyFontSize(size);
            fontSizeSelect.value = "";
            saveEditorSelection();
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

    let initialFormState = "";
    let isSubmitting = false;

    const hasUnsavedChanges = () => serializeFormState() !== initialFormState;

    window.addEventListener("beforeunload", (event) => {
        if (isSubmitting || !hasUnsavedChanges()) {
            return;
        }

        event.preventDefault();
        event.returnValue = "";
    });

    form.addEventListener("submit", () => {
        syncEditorToInput();
        isSubmitting = true;
    });

    syncEditorToInput();
    initialFormState = serializeFormState();
});
