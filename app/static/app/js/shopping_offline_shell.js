document.addEventListener("DOMContentLoaded", async () => {
    const api = window.MyToolsShoppingOffline;
    const content = document.getElementById("shopping-offline-content");
    const emptyState = document.getElementById("shopping-offline-empty");
    const addCard = document.getElementById("shopping-offline-add-card");
    const addForm = document.getElementById("shopping-offline-add-form");
    const csrfInput = document.getElementById("shopping-offline-csrf");
    const status = document.getElementById("shopping-sync-status");
    const summary = document.getElementById("shopping-offline-summary");
    const syncLink = document.getElementById("shopping-offline-sync");

    if (!api) return;
    const snapshot = await api.latestSnapshot().catch(() => null);
    if (!snapshot) {
        if (emptyState) emptyState.hidden = false;
        if (status) status.textContent = "Keine lokal gespeicherte Liste gefunden.";
        return;
    }

    const store = api.create({userId: snapshot.userId, listId: snapshot.listId, statusElement: status});
    if (content) content.innerHTML = snapshot.listHtml;
    if (csrfInput) csrfInput.value = snapshot.csrfToken || "";
    if (addCard) addCard.hidden = false;
    if (summary) {
        const data = snapshot.summary || {};
        summary.textContent = `${data.active || 0} offen · ${data.planned || 0} geplant · ${data.estimated_total || "0.00"} €`;
    }

    const queueForm = async (form, kind) => {
        await store.enqueue({url: form.action, body: store.serializeForm(form), kind});
    };

    addForm?.addEventListener("submit", async (event) => {
        event.preventDefault();
        await queueForm(addForm, "add");
        addForm.reset();
        if (csrfInput) csrfInput.value = snapshot.csrfToken || "";
    });

    content?.addEventListener("submit", async (event) => {
        const form = event.target.closest("form");
        if (!form) return;
        event.preventDefault();
        const article = form.closest(".shopping-item");
        let kind = "update";
        if (form.classList.contains("shopping-toggle-form")) {
            kind = article?.dataset.shoppingState === "planned" ? "activate" : "toggle";
        } else if (form.classList.contains("shopping-delete-form")) {
            kind = "delete";
        } else if (form.classList.contains("shopping-confirm-form")) {
            kind = "clear-completed";
        }
        await queueForm(form, kind);
        if (["toggle", "activate", "delete"].includes(kind)) article?.remove();
        if (kind === "clear-completed") form.closest("[data-shopping-card-state]")?.setAttribute("hidden", "");
    });

    content?.addEventListener("click", (event) => {
        const editButton = event.target.closest(".shopping-edit-toggle");
        if (editButton) {
            const panel = document.getElementById(editButton.dataset.editTarget);
            if (panel) panel.hidden = !panel.hidden;
        }
        const cancelButton = event.target.closest(".shopping-edit-cancel");
        if (cancelButton) {
            const panel = document.getElementById(cancelButton.dataset.editTarget);
            if (panel) panel.hidden = true;
        }
    });

    const syncAvailability = () => {
        if (!syncLink) return;
        syncLink.classList.toggle("is-disabled", !navigator.onLine);
        syncLink.setAttribute("aria-disabled", navigator.onLine ? "false" : "true");
    };
    syncLink?.addEventListener("click", (event) => {
        if (!navigator.onLine) event.preventDefault();
    });
    window.addEventListener("online", syncAvailability);
    window.addEventListener("offline", syncAvailability);
    syncAvailability();
    await store.updateStatus();
});
