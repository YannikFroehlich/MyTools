document.addEventListener("DOMContentLoaded", () => {
    const root = document.querySelector("[data-vacation-root]");
    if (!root) {
        return;
    }

    const holidaysElement = document.getElementById("vacation-holidays-data");
    const labelsElement = document.getElementById("vacation-planner-labels");
    const holidays = holidaysElement ? JSON.parse(holidaysElement.textContent || "[]") : [];
    const labels = labelsElement ? JSON.parse(labelsElement.textContent || "{}") : {};
    const locale = document.documentElement.lang || navigator.language || "de-DE";
    const numberFormatter = new Intl.NumberFormat(locale, { maximumFractionDigits: 1 });

    const holidayMap = new Map();
    holidays.forEach((holiday) => {
        if (!holiday.date) {
            return;
        }
        if (!holidayMap.has(holiday.date)) {
            holidayMap.set(holiday.date, []);
        }
        holidayMap.get(holiday.date).push({
            name: holiday.name || "Feiertag",
            deduction: Number(holiday.deduction || (holiday.is_half_day ? 0.5 : 1)),
        });
    });

    function parseDate(value) {
        const parts = String(value || "").split("-").map(Number);
        if (parts.length !== 3 || parts.some((part) => Number.isNaN(part))) {
            return null;
        }
        return new Date(Date.UTC(parts[0], parts[1] - 1, parts[2]));
    }

    function dateKey(date) {
        const year = date.getUTCFullYear();
        const month = String(date.getUTCMonth() + 1).padStart(2, "0");
        const day = String(date.getUTCDate()).padStart(2, "0");
        return `${year}-${month}-${day}`;
    }

    function addDays(date, days) {
        const next = new Date(date.getTime());
        next.setUTCDate(next.getUTCDate() + days);
        return next;
    }

    function vacationStats(startDate, endDate) {
        const totalDays = Math.floor((endDate - startDate) / 86400000) + 1;
        let vacationDays = 0;
        let weekends = 0;
        let holidayDays = 0;

        for (let offset = 0; offset < totalDays; offset += 1) {
            const current = addDays(startDate, offset);
            const weekday = current.getUTCDay();
            const isWeekend = weekday === 0 || weekday === 6;
            const holidayEntries = holidayMap.get(dateKey(current)) || [];
            const holidayDeduction = Math.min(1, holidayEntries.reduce((sum, holiday) => {
                const deduction = Number.isFinite(holiday.deduction) ? holiday.deduction : 1;
                return sum + Math.max(0, deduction);
            }, 0));

            if (isWeekend) {
                weekends += 1;
            } else if (holidayDeduction > 0) {
                holidayDays += holidayDeduction;
                vacationDays += Math.max(0, 1 - holidayDeduction);
            } else {
                vacationDays += 1;
            }
        }

        return { totalDays, vacationDays, weekends, holidayDays };
    }

    function formatCount(value) {
        return numberFormatter.format(value);
    }

    function updatePreview(form) {
        const output = form.querySelector("[data-vacation-preview]");
        const startInput = form.querySelector("[data-vacation-start]");
        const endInput = form.querySelector("[data-vacation-end]");
        if (!output || !startInput || !endInput) {
            return;
        }

        const startDate = parseDate(startInput.value);
        const endDate = parseDate(endInput.value);

        output.classList.remove("is-error");
        if (!startDate || !endDate) {
            output.textContent = labels.ready || "Zeitraum auswählen, um die Urlaubstage zu prüfen.";
            return;
        }

        if (endDate < startDate) {
            output.textContent = labels.invalidRange || "Das Enddatum darf nicht vor dem Startdatum liegen.";
            output.classList.add("is-error");
            return;
        }

        const stats = vacationStats(startDate, endDate);
        output.textContent = `${formatCount(stats.vacationDays)} ${labels.vacationDays || "Urlaubstage"} | ${formatCount(stats.totalDays)} ${labels.calendarDays || "Kalendertage"} | ${formatCount(stats.weekends)} ${labels.weekends || "Wochenenden"} | ${formatCount(stats.holidayDays)} ${labels.holidays || "Feiertage"}`;
    }

    root.querySelectorAll("[data-vacation-range-form]").forEach((form) => {
        form.querySelectorAll("input").forEach((input) => {
            input.addEventListener("input", () => updatePreview(form));
            input.addEventListener("change", () => updatePreview(form));
        });
        updatePreview(form);
    });

    root.querySelectorAll("[data-edit-toggle]").forEach((button) => {
        button.addEventListener("click", () => {
            const container = button.closest("[data-edit-container]");
            const form = container?.querySelector(".vacation-edit-form");
            if (!form) {
                return;
            }
            const isOpening = form.hidden;
            form.hidden = !isOpening;
            button.setAttribute("aria-expanded", String(isOpening));
            if (isOpening) {
                updatePreview(form);
                form.querySelector("input:not([type='hidden'])")?.focus();
            }
        });
    });

    root.querySelectorAll("[data-edit-cancel]").forEach((button) => {
        button.addEventListener("click", () => {
            const form = button.closest(".vacation-edit-form");
            if (form) {
                form.hidden = true;
            }
        });
    });

    root.querySelectorAll("form[data-confirm]").forEach((form) => {
        form.addEventListener("submit", (event) => {
            const message = form.dataset.confirm || "";
            if (message && !window.confirm(message)) {
                event.preventDefault();
            }
        });
    });
});

