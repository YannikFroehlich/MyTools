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
    hydrateSnakeProfileCardFromLocalStorage();

    function hydrateSnakeProfileCardFromLocalStorage() {
        const card = document.querySelector("[data-snake-profile-card]");
        if (!card) return;

        const records = loadSnakeHighscores();
        const best = records.sort(compareSnakeHighscores)[0];
        if (!best) return;

        renderSnakeProfileCard(card, best);
        syncSnakeHighscores(card.dataset.snakeScoreApi || "", records);
    }

    function loadSnakeHighscores() {
        try {
            const parsed = JSON.parse(localStorage.getItem("mytools-snake-simple-highscores-v1") || "[]");
            return Array.isArray(parsed) ? parsed.filter((record) => record && Number(record.score || 0) > 0) : [];
        } catch (_error) {
            return [];
        }
    }

    function compareSnakeHighscores(a, b) {
        return Number(b.score || 0) - Number(a.score || 0)
            || Number(b.length || 0) - Number(a.length || 0)
            || String(b.achievedAt || "").localeCompare(String(a.achievedAt || ""));
    }

    function renderSnakeProfileCard(card, record) {
        card.classList.remove("is-empty");
        card.querySelector(".profile-game-empty")?.remove();

        let scoreWrap = card.querySelector(".profile-game-score");
        if (!scoreWrap) {
            scoreWrap = document.createElement("div");
            scoreWrap.className = "profile-game-score";
            card.appendChild(scoreWrap);
        }
        scoreWrap.innerHTML = "";

        const main = document.createElement("div");
        main.className = "profile-game-score-main";

        const label = document.createElement("span");
        const icon = document.createElement("i");
        icon.className = "fa-solid fa-trophy";
        label.append(icon, document.createTextNode(` ${snakeText("Bester Score", "Best score")}`));

        const value = document.createElement("strong");
        value.textContent = formatSnakeNumber(record.score);

        const detail = document.createElement("small");
        detail.textContent = formatSnakeDate(record.achievedAt);

        main.append(label, value, detail);

        const grid = document.createElement("div");
        grid.className = "profile-game-grid";
        grid.append(
            snakeMetric("Länge", "Length", formatSnakeNumber(record.length || 0), "fa-solid fa-staff-snake"),
            snakeMetric("Früchte", "Fruits", formatSnakeNumber(record.fruits || 0), "fa-solid fa-apple-whole"),
            snakeMetric("Spiele", "Games", formatSnakeNumber(record.runs || 1), "fa-solid fa-gamepad"),
            snakeMetric("Einstellung", "Setting", snakeSettingsLabel(record), "fa-solid fa-sliders")
        );

        scoreWrap.append(main, grid);
    }

    function snakeMetric(labelDe, labelEn, valueText, iconClass) {
        const item = document.createElement("div");
        const icon = document.createElement("i");
        icon.className = iconClass;
        const label = document.createElement("span");
        label.textContent = snakeText(labelDe, labelEn);
        const value = document.createElement("strong");
        value.textContent = valueText;
        item.append(icon, label, value);
        return item;
    }

    function snakeSettingsLabel(record) {
        const settings = record.settings || parseSnakeSettingsKey(record.key);
        const boardSize = clampSnakeNumber(Number(settings.boardSize || 19), 11, 31);
        const fruitLimit = clampSnakeNumber(Number(settings.fruitLimit || 1), 1, 7);
        const speedLabels = { relaxed: snakeText("Entspannt", "Relaxed"), normal: snakeText("Normal", "Normal"), fast: snakeText("Schnell", "Fast"), turbo: snakeText("Turbo", "Turbo") };
        const spawnLabels = { slow: snakeText("Ruhig", "Calm"), normal: snakeText("Standard", "Default"), high: snakeText("Hoch", "High"), instant: snakeText("Sofort", "Instant") };
        const wallLabels = { wrap: snakeText("Durchlaufen", "Wrap"), wall: snakeText("Wände", "Walls") };
        const fruitWord = fruitLimit === 1 ? snakeText("Frucht", "fruit") : snakeText("Früchte", "fruits");
        return `${boardSize} × ${boardSize} · ${speedLabels[settings.speedKey] || speedLabels.normal} · ${fruitLimit} ${fruitWord} · ${spawnLabels[settings.spawnKey] || spawnLabels.normal} · ${wallLabels[settings.wallMode] || wallLabels.wrap}`;
    }

    function parseSnakeSettingsKey(key) {
        const [boardSize, speedKey, fruitLimit, spawnKey, wallMode] = String(key || "").split("|");
        return {
            boardSize: clampSnakeNumber(Number(boardSize || 19), 11, 31),
            speedKey: speedKey || "normal",
            fruitLimit: clampSnakeNumber(Number(fruitLimit || 1), 1, 7),
            spawnKey: spawnKey || "normal",
            wallMode: wallMode || "wrap"
        };
    }

    function syncSnakeHighscores(apiUrl, records) {
        if (!apiUrl) return;
        records.slice(0, 60).forEach((record, index) => {
            window.setTimeout(() => {
                fetch(apiUrl, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": getCsrfToken(),
                        "X-Requested-With": "XMLHttpRequest"
                    },
                    body: JSON.stringify(record)
                }).catch(() => {});
            }, index * 80);
        });
    }

    function getCsrfToken() {
        const cookieValue = document.cookie
            .split(";")
            .map((item) => item.trim())
            .find((item) => item.startsWith("csrftoken="))
            ?.slice("csrftoken=".length);
        return cookieValue || document.querySelector("[name=csrfmiddlewaretoken]")?.value || "";
    }

    function formatSnakeNumber(value) {
        return Number(value || 0).toLocaleString(document.documentElement.lang || navigator.language || "de-DE");
    }

    function formatSnakeDate(value) {
        if (!value) return "";
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return "";
        return date.toLocaleDateString(document.documentElement.lang || navigator.language || "de-DE", { day: "2-digit", month: "2-digit", year: "2-digit" });
    }

    function clampSnakeNumber(value, min, max) {
        if (!Number.isFinite(value)) return min;
        return Math.max(min, Math.min(max, Math.round(value)));
    }

    function snakeText(de, en) {
        return (document.documentElement.lang || "de").toLowerCase().startsWith("en") ? en : de;
    }
});
