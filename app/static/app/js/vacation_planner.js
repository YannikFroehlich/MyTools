document.addEventListener("DOMContentLoaded", () => {
    const holidaysElement = document.getElementById("vacation-holidays-data");
    const labelsElement = document.getElementById("vacation-planner-labels");
    const holidays = holidaysElement ? JSON.parse(holidaysElement.textContent) : [];
    const labels = labelsElement ? JSON.parse(labelsElement.textContent) : {};

    const startInput = document.getElementById("vacation-start-date");
    const endInput = document.getElementById("vacation-end-date");
    const calculateButton = document.getElementById("vacation-calculate");
    const daysNeeded = document.getElementById("vacation-days-needed");
    const calendarDays = document.getElementById("vacation-calendar-days");
    const weekendDays = document.getElementById("vacation-weekend-days");
    const holidayDays = document.getElementById("vacation-holiday-days");
    const message = document.getElementById("vacation-message");
    const timeline = document.getElementById("vacation-timeline");
    const hitList = document.getElementById("vacation-holiday-hit-list");
    const coverage = document.getElementById("vacation-year-coverage");
    const clearForm = document.querySelector("[data-vacation-clear-form]");
    const saveStartInput = document.getElementById("vacation-save-start");
    const saveEndInput = document.getElementById("vacation-save-end");
    const locale = document.documentElement.lang || "de";

    const holidayMap = new Map();
    const savedYears = new Set();

    holidays.forEach((holiday) => {
        if (!holiday.date) {
            return;
        }

        if (!holidayMap.has(holiday.date)) {
            holidayMap.set(holiday.date, []);
        }
        holidayMap.get(holiday.date).push(holiday.name || "Feiertag");
        savedYears.add(Number(holiday.year || holiday.date.slice(0, 4)));
    });

    const dateFormatter = new Intl.DateTimeFormat(locale, {
        timeZone: "UTC",
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
    });

    const weekdayFormatter = new Intl.DateTimeFormat(locale, {
        timeZone: "UTC",
        weekday: "short",
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

    function setMessage(text, state = "") {
        message.textContent = text;
        message.classList.toggle("is-error", state === "error");
        message.classList.toggle("is-warning", state === "warning");
    }

    function resetResults() {
        daysNeeded.textContent = "0";
        calendarDays.textContent = "0";
        weekendDays.textContent = "0";
        holidayDays.textContent = "0";
        timeline.innerHTML = "";
        renderHolidayHits([]);
    }

    function renderHolidayHits(records) {
        const holidayRecords = records.filter((record) => record.isHolidayWeekday);
        hitList.innerHTML = "";

        if (!holidayRecords.length) {
            const empty = document.createElement("div");
            empty.className = "vacation-empty-state";
            empty.innerHTML = `<i class="fa-regular fa-calendar"></i><span>${labels.noHolidays || "Keine gespeicherten Feiertage im Zeitraum."}</span>`;
            hitList.appendChild(empty);
            return;
        }

        holidayRecords.forEach((record) => {
            const item = document.createElement("article");
            item.className = "vacation-holiday-hit";

            const copy = document.createElement("div");
            const title = document.createElement("strong");
            title.textContent = record.holidayNames.join(", ");
            const date = document.createElement("span");
            date.textContent = `${dateFormatter.format(record.date)} · ${weekdayFormatter.format(record.date)}`;
            copy.append(title, date);

            const icon = document.createElement("i");
            icon.className = "fa-solid fa-calendar-check";
            icon.setAttribute("aria-hidden", "true");

            item.append(copy, icon);
            hitList.appendChild(item);
        });
    }

    function renderTimeline(records) {
        timeline.innerHTML = "";
        const visibleRecords = records.slice(0, 180);

        visibleRecords.forEach((record) => {
            const chip = document.createElement("div");
            chip.className = "vacation-day-chip";

            if (record.isWeekend) {
                chip.classList.add("is-weekend");
                chip.title = labels.weekend || "Wochenende";
            } else if (record.isHolidayWeekday) {
                chip.classList.add("is-holiday");
                chip.title = `${labels.savedHoliday || "Gespeicherter Feiertag"}: ${record.holidayNames.join(", ")}`;
            } else {
                chip.classList.add("is-vacation");
                chip.title = labels.vacation || "Urlaubstag";
            }

            const day = document.createElement("span");
            day.textContent = String(record.date.getUTCDate()).padStart(2, "0");
            const meta = document.createElement("small");
            meta.textContent = weekdayFormatter.format(record.date);
            chip.append(day, meta);
            timeline.appendChild(chip);
        });

        if (records.length > visibleRecords.length) {
            const more = document.createElement("div");
            more.className = "vacation-day-chip";
            more.textContent = `+${records.length - visibleRecords.length}`;
            timeline.appendChild(more);
        }
    }

    function updateCoverage(yearsInRange) {
        const missingYears = Array.from(yearsInRange)
            .filter((year) => !savedYears.has(year))
            .sort((a, b) => a - b);

        if (missingYears.length) {
            coverage.classList.add("is-warning");
            coverage.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> ${labels.missingYearPrefix || "Noch keine Feiertage gespeichert fuer"} ${missingYears.join(", ")}`;
            return missingYears;
        }

        coverage.classList.remove("is-warning");
        coverage.innerHTML = `<i class="fa-solid fa-calendar-days"></i> ${Array.from(yearsInRange).sort((a, b) => a - b).join(", ")}`;
        return [];
    }

    function calculateVacation() {
        const startDate = parseDate(startInput.value);
        const endDate = parseDate(endInput.value);

        if (!startDate || !endDate) {
            resetResults();
            setMessage(labels.missingDates || "Bitte Start- und Enddatum ausfuellen.", "error");
            return;
        }

        if (endDate < startDate) {
            resetResults();
            setMessage(labels.invalidRange || "Das Enddatum muss nach dem Startdatum liegen.", "error");
            return;
        }

        const totalDays = Math.floor((endDate - startDate) / 86400000) + 1;
        let weekends = 0;
        let holidaysOnWeekdays = 0;
        let requiredVacationDays = 0;
        const records = [];
        const yearsInRange = new Set();

        for (let offset = 0; offset < totalDays; offset += 1) {
            const current = addDays(startDate, offset);
            const key = dateKey(current);
            const day = current.getUTCDay();
            const isWeekend = day === 0 || day === 6;
            const holidayNames = holidayMap.get(key) || [];
            const isHolidayWeekday = !isWeekend && holidayNames.length > 0;
            yearsInRange.add(current.getUTCFullYear());

            if (isWeekend) {
                weekends += 1;
            } else if (isHolidayWeekday) {
                holidaysOnWeekdays += 1;
            } else {
                requiredVacationDays += 1;
            }

            records.push({
                date: current,
                isWeekend,
                holidayNames,
                isHolidayWeekday,
            });
        }

        daysNeeded.textContent = requiredVacationDays;
        calendarDays.textContent = totalDays;
        weekendDays.textContent = weekends;
        holidayDays.textContent = holidaysOnWeekdays;

        const missingYears = updateCoverage(yearsInRange);
        if (missingYears.length) {
            setMessage(`${labels.missingYearPrefix || "Noch keine Feiertage gespeichert fuer"} ${missingYears.join(", ")}.`, "warning");
        } else {
            setMessage(`${requiredVacationDays} ${labels.vacationDays || "benoetigte Urlaubstage"} · ${totalDays} ${labels.calendarDays || "Kalendertage"} · ${weekends} ${labels.weekends || "Wochenendtage"} · ${holidaysOnWeekdays} ${labels.holidays || "Feiertage auf Werktagen"}`);
        }

        renderHolidayHits(records);
        renderTimeline(records);
    }

    function syncSaveRange() {
        if (saveStartInput && startInput?.value) {
            saveStartInput.value = startInput.value;
        }
        if (saveEndInput && endInput?.value) {
            saveEndInput.value = endInput.value;
        }
    }

    calculateButton?.addEventListener("click", calculateVacation);
    startInput?.addEventListener("change", () => {
        syncSaveRange();
        calculateVacation();
    });
    endInput?.addEventListener("change", () => {
        syncSaveRange();
        calculateVacation();
    });

    clearForm?.addEventListener("submit", (event) => {
        const confirmed = window.confirm(labels.clearConfirm || "Alle Feiertage fuer dieses Jahr loeschen?");
        if (!confirmed) {
            event.preventDefault();
        }
    });

    syncSaveRange();
    calculateVacation();
});
