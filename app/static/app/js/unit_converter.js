document.addEventListener("DOMContentLoaded", () => {
    const tabs = document.querySelectorAll(".converter-tab");
    const valueInput = document.getElementById("converter-value");
    const fromSelect = document.getElementById("converter-from");
    const toSelect = document.getElementById("converter-to");
    const swapButton = document.getElementById("converter-swap");
    const resultElement = document.getElementById("converter-result");
    const formulaElement = document.getElementById("converter-formula");
    const examples = document.querySelectorAll(".converter-example");
    const labelsElement = document.getElementById("converter-labels");
    const labels = labelsElement ? JSON.parse(labelsElement.textContent) : {};

    const categories = {
        storage: {
            units: {
                kb: { label: labels.storage?.kb || "Kilobyte (KB)", factor: 1 },
                mb: { label: labels.storage?.mb || "Megabyte (MB)", factor: 1024 },
                gb: { label: labels.storage?.gb || "Gigabyte (GB)", factor: 1024 * 1024 },
                tb: { label: labels.storage?.tb || "Terabyte (TB)", factor: 1024 * 1024 * 1024 },
            },
            defaultFrom: "mb",
            defaultTo: "gb",
        },
        time: {
            units: {
                seconds: { label: labels.time?.seconds || "Sekunden", factor: 1 },
                minutes: { label: labels.time?.minutes || "Minuten", factor: 60 },
                hours: { label: labels.time?.hours || "Stunden", factor: 3600 },
                days: { label: labels.time?.days || "Tage", factor: 86400 },
            },
            defaultFrom: "seconds",
            defaultTo: "minutes",
        },
        distance: {
            units: {
                mm: { label: labels.distance?.mm || "Millimeter", factor: 0.001 },
                cm: { label: labels.distance?.cm || "Zentimeter", factor: 0.01 },
                m: { label: labels.distance?.m || "Meter", factor: 1 },
                km: { label: labels.distance?.km || "Kilometer", factor: 1000 },
                mi: { label: labels.distance?.mi || "Meilen", factor: 1609.344 },
            },
            defaultFrom: "km",
            defaultTo: "mi",
        },
        money: {
            units: {
                daily: { label: labels.money?.daily || "Euro pro Tag", factor: 1 },
                weekly: { label: labels.money?.weekly || "Euro pro Woche", factor: 7 },
                monthly: { label: labels.money?.monthly || "Euro pro Monat", factor: 30.4375 },
                yearly: { label: labels.money?.yearly || "Euro pro Jahr", factor: 365.25 },
            },
            defaultFrom: "monthly",
            defaultTo: "yearly",
        },
    };

    let currentCategory = "storage";

    const formatNumber = (number) => {
        if (!Number.isFinite(number)) {
            return "-";
        }

        return new Intl.NumberFormat("de-DE", {
            maximumFractionDigits: 6,
        }).format(number);
    };

    const getCurrentUnits = () => {
        return categories[currentCategory].units;
    };

    const fillSelects = () => {
        const category = categories[currentCategory];
        const units = category.units;

        fromSelect.innerHTML = "";
        toSelect.innerHTML = "";

        Object.entries(units).forEach(([key, unit]) => {
            const fromOption = document.createElement("option");
            fromOption.value = key;
            fromOption.textContent = unit.label;

            const toOption = document.createElement("option");
            toOption.value = key;
            toOption.textContent = unit.label;

            fromSelect.appendChild(fromOption);
            toSelect.appendChild(toOption);
        });

        fromSelect.value = category.defaultFrom;
        toSelect.value = category.defaultTo;
    };

    const calculate = () => {
        const rawValue = valueInput.value.replace(",", ".");
        const value = Number.parseFloat(rawValue);

        if (!rawValue || Number.isNaN(value)) {
            resultElement.textContent = "-";
            formulaElement.textContent = labels.messages?.empty || "Gib einen Wert ein, um die Umrechnung zu starten.";
            return;
        }

        const units = getCurrentUnits();
        const fromUnit = units[fromSelect.value];
        const toUnit = units[toSelect.value];

        const baseValue = value * fromUnit.factor;
        const result = baseValue / toUnit.factor;

        const suffix = currentCategory === "money" ? "€" : "";
        resultElement.textContent = `${formatNumber(result)} ${suffix}`.trim();

        formulaElement.textContent =
            `${formatNumber(value)} ${fromUnit.label} = ${formatNumber(result)} ${toUnit.label}`;
    };

    const setCategory = (categoryKey) => {
        currentCategory = categoryKey;

        tabs.forEach((tab) => {
            tab.classList.toggle("active", tab.dataset.category === categoryKey);
        });

        fillSelects();
        calculate();
    };

    tabs.forEach((tab) => {
        tab.addEventListener("click", () => {
            setCategory(tab.dataset.category);
        });
    });

    valueInput.addEventListener("input", calculate);
    fromSelect.addEventListener("change", calculate);
    toSelect.addEventListener("change", calculate);

    swapButton.addEventListener("click", () => {
        const oldFrom = fromSelect.value;
        fromSelect.value = toSelect.value;
        toSelect.value = oldFrom;
        calculate();
    });

    examples.forEach((example) => {
        example.addEventListener("click", () => {
            setCategory(example.dataset.category);

            valueInput.value = example.dataset.value;
            fromSelect.value = example.dataset.from;
            toSelect.value = example.dataset.to;

            calculate();
            valueInput.focus();
        });
    });

    fillSelects();
    calculate();
});