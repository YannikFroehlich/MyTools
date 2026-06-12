(() => {
    const form = document.getElementById("budget-entry-form");
    const categorySelect = document.getElementById("budget-category-select");

    function syncCategoryOptions() {
        if (!form || !categorySelect) return;
        const checkedType = form.querySelector("input[name='entry_type']:checked")?.value || "expense";
        let firstVisible = null;

        Array.from(categorySelect.options).forEach((option) => {
            const isVisible = option.dataset.kind === checkedType;
            option.hidden = !isVisible;
            option.disabled = !isVisible;
            if (isVisible && !firstVisible) firstVisible = option;
        });

        if (!categorySelect.selectedOptions.length || categorySelect.selectedOptions[0].hidden) {
            categorySelect.value = firstVisible ? firstVisible.value : "";
        }
    }

    form?.querySelectorAll("input[name='entry_type']").forEach((radio) => {
        radio.addEventListener("change", syncCategoryOptions);
    });
    syncCategoryOptions();

    document.querySelectorAll(".budget-delete-form").forEach((deleteForm) => {
        deleteForm.addEventListener("submit", (event) => {
            const message = deleteForm.dataset.confirm || "Wirklich löschen?";
            if (!window.confirm(message)) {
                event.preventDefault();
            }
        });
    });

    const chart = document.getElementById("budget-trend-chart");
    const dataScript = document.getElementById("budget-trend-data");
    if (chart && dataScript) {
        let data = null;
        try {
            data = JSON.parse(dataScript.textContent || "{}");
        } catch (_error) {
            data = null;
        }

        if (data?.labels?.length) {
            const maxValue = Math.max(1, ...data.income, ...data.expenses);
            chart.innerHTML = data.labels.map((label, index) => {
                const incomeHeight = Math.max(4, Math.round((Number(data.income[index] || 0) / maxValue) * 120));
                const expenseHeight = Math.max(4, Math.round((Number(data.expenses[index] || 0) / maxValue) * 120));
                return `
                    <div class="budget-chart-month" title="${label}">
                        <div class="budget-chart-bars">
                            <span class="budget-chart-bar is-income" style="height:${incomeHeight}px" aria-label="Einnahmen"></span>
                            <span class="budget-chart-bar is-expense" style="height:${expenseHeight}px" aria-label="Ausgaben"></span>
                        </div>
                        <span class="budget-chart-label">${label}</span>
                    </div>
                `;
            }).join("");
        } else {
            chart.innerHTML = "<p class='budget-muted'>Noch keine Verlaufsdaten.</p>";
        }
    }
})();
