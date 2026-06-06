document.addEventListener("DOMContentLoaded", () => {
    const list = document.querySelector("[data-profile-game-cards-list]");
    if (!list) return;

    function updateButtons() {
        const rows = Array.from(list.querySelectorAll("[data-profile-game-card-row]"));
        rows.forEach((row, index) => {
            row.querySelector("[data-profile-game-card-up]")?.toggleAttribute("disabled", index === 0);
            row.querySelector("[data-profile-game-card-down]")?.toggleAttribute("disabled", index === rows.length - 1);
        });
    }

    list.addEventListener("click", (event) => {
        const upButton = event.target.closest("[data-profile-game-card-up]");
        const downButton = event.target.closest("[data-profile-game-card-down]");
        if (!upButton && !downButton) return;

        const row = event.target.closest("[data-profile-game-card-row]");
        if (!row) return;

        if (upButton && row.previousElementSibling) {
            list.insertBefore(row, row.previousElementSibling);
        }

        if (downButton && row.nextElementSibling) {
            list.insertBefore(row.nextElementSibling, row);
        }

        updateButtons();
    });

    updateButtons();
});
