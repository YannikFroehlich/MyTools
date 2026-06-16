document.addEventListener("DOMContentLoaded", () => {
    const homeRoot = document.querySelector(".kniffel-home-page");
    if (homeRoot) initHomePage(homeRoot);

    const root = document.querySelector(".kniffel-lobby-page");
    if (!root) return;

    const urls = {
        state: root.dataset.stateUrl,
        start: root.dataset.startUrl,
        roll: root.dataset.rollUrl,
        score: root.dataset.scoreUrl,
        reset: root.dataset.resetUrl,
    };
    const csrfToken = getCookie("csrftoken");
    let game = null;
    let isPosting = false;
    let isRefreshing = false;
    let keptIndices = new Set();
    let lastDiceSignature = "";
    let lastPlayersSignature = "";
    let lastCurrentPlayerId = "";
    let lastWinnerSoundKey = "";
    let dismissedWinnerKey = "";
    let audioContext = null;
    let soundEnabled = window.localStorage.getItem("kniffelSound") !== "off";
    let audioUnlocked = false;

    bindEvents();
    updateSoundButton();
    refreshState(true);
    window.setInterval(() => refreshState(false), 1500);

    function bindEvents() {
        document.querySelectorAll("form[data-confirm]").forEach((form) => {
            form.addEventListener("submit", (event) => {
                if (!window.confirm(form.dataset.confirm || "Wirklich?")) {
                    event.preventDefault();
                }
            });
        });

        document.getElementById("kniffel-copy-link")?.addEventListener("click", async () => {
            unlockAudio();
            await navigator.clipboard?.writeText(window.location.href);
            playSound("click");
            showToast("Link kopiert");
        });
        document.getElementById("kniffel-sound-toggle")?.addEventListener("click", () => {
            if (soundEnabled) {
                unlockAudio();
                playSound("toggleOff");
                soundEnabled = false;
                window.localStorage.setItem("kniffelSound", "off");
            } else {
                soundEnabled = true;
                window.localStorage.setItem("kniffelSound", "on");
                unlockAudio();
                playSound("toggleOn");
            }
            updateSoundButton();
        });
        document.getElementById("kniffel-start")?.addEventListener("click", () => post(urls.start, {}, "start"));
        document.getElementById("kniffel-reset")?.addEventListener("click", () => post(urls.reset, {}, "start"));
        document.getElementById("kniffel-roll")?.addEventListener("click", () => {
            unlockAudio();
            animateDiceRoll();
            post(urls.roll, {kept_indices: Array.from(keptIndices).join(",")}, "roll");
        });
        document.getElementById("kniffel-winner-close")?.addEventListener("click", () => {
            playSound("click");
            dismissedWinnerKey = winnerKey();
            hideWinnerModal();
        });
    }

    async function refreshState(force = false) {
        if (isPosting || isRefreshing) return;
        isRefreshing = true;
        try {
            const response = await fetch(urls.state, {headers: {"X-Requested-With": "XMLHttpRequest"}});
            const json = await response.json();
            if (json.gameDeleted) {
                handleDeletedGame(json);
                return;
            }
            if (!json.ok) return;

            const signature = JSON.stringify(json.game);
            if (!force && game && signature === JSON.stringify(game)) return;
            game = json.game;
            syncKeptDice();
            render();
        } catch (error) {
            console.warn("Kniffel state failed", error);
        } finally {
            isRefreshing = false;
        }
    }

    async function post(url, data = null, soundType = "") {
        if (isPosting || !url) return;
        unlockAudio();
        isPosting = true;
        let nextGame = null;
        const hasData = data && Object.keys(data).length > 0;
        const requestOptions = {
            method: "POST",
            headers: {
                "X-CSRFToken": csrfToken,
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json",
            },
        };

        if (hasData) {
            requestOptions.headers["Content-Type"] = "application/x-www-form-urlencoded;charset=UTF-8";
            requestOptions.body = new URLSearchParams(data).toString();
        }

        try {
            const response = await fetch(url, requestOptions);
            const rawBody = await response.text();
            let json = {ok: false};

            try {
                json = rawBody ? JSON.parse(rawBody) : json;
            } catch (error) {
                console.warn("Kniffel action returned non-JSON", response.status, rawBody.slice(0, 200));
            }

            if (!response.ok || !json.ok) {
                playSound("error");
                showToast(json.error || `Aktion fehlgeschlagen (${response.status})`);
                return;
            }
            nextGame = json.game;
            if (soundType) playSound(soundType);
        } finally {
            isPosting = false;
            if (nextGame) {
                game = nextGame;
                syncKeptDice(true);
                render();
            }
        }
    }

    function syncKeptDice(force = false) {
        const diceSignature = `${(game.dice || []).join("-")}:${game.rollCount}`;
        if (force || diceSignature !== lastDiceSignature) {
            keptIndices = new Set(game.keptIndices || []);
            lastDiceSignature = diceSignature;
        }
    }

    function render() {
        document.getElementById("kniffel-status").textContent = game.statusLabel;
        document.getElementById("kniffel-message").textContent = game.message;
        document.getElementById("kniffel-round").textContent = game.roundNumber;
        document.getElementById("kniffel-roll-count").textContent = game.rollCount;
        document.getElementById("kniffel-current-player").textContent = game.currentPlayerName || "-";
        document.getElementById("kniffel-own-total").textContent = game.ownSummary.total;

        document.getElementById("kniffel-start").disabled = isPosting || !game.canStart;
        document.getElementById("kniffel-reset").disabled = isPosting || !game.isOwner || game.players.length < 2;
        document.getElementById("kniffel-roll").disabled = isPosting || !game.canRoll;

        const arena = document.getElementById("kniffel-dice-arena");
        arena?.classList.toggle("is-your-turn", Boolean(game.canRoll || game.canScore));
        arena?.classList.toggle("is-finished", game.status === "finished");
        arena?.classList.toggle("is-waiting", game.status === "waiting");

        renderPlayers();
        renderDice();
        renderScoreTable();
        renderLog();
        renderWinnerModal();
        noticePlayerChanges();
        noticeTurnChange();
    }

    function renderPlayers() {
        const list = document.getElementById("kniffel-player-list");
        list.innerHTML = game.players.map((player) => `
            <div class="kniffel-player-row ${player.isCurrent ? "is-current" : ""} ${player.isYou ? "is-you" : ""}">
                ${avatarMarkup(player, "kniffel-player-avatar")}
                <div>
                    <strong>${escapeHtml(player.name)}${player.isYou ? " - Du" : ""}</strong>
                    <small>${player.filled}/13 Felder - ${player.total} Punkte</small>
                </div>
                <b>${player.total}</b>
            </div>
        `).join("");
    }

    function renderDice() {
        const row = document.getElementById("kniffel-dice-row");
        const dice = game.dice && game.dice.length === 5 ? game.dice : [0, 0, 0, 0, 0];
        row.innerHTML = dice.map((value, index) => {
            const isKept = keptIndices.has(index);
            const canKeep = game.rollCount > 0 && game.status === "playing" && (game.canRoll || game.canScore);
            return `
                <button type="button"
                        class="kniffel-die ${isKept ? "is-kept" : ""} ${value ? "" : "is-empty"}"
                        data-index="${index}"
                        ${canKeep && value ? "" : "disabled"}
                        aria-label="Würfel ${index + 1}${isKept ? " gehalten" : ""}">
                    ${dieFaceMarkup(value)}
                    <span class="kniffel-die-label">${value || "-"}</span>
                </button>
            `;
        }).join("");

        row.querySelectorAll(".kniffel-die").forEach((button) => {
            button.addEventListener("click", () => {
                const index = Number(button.dataset.index);
                if (keptIndices.has(index)) {
                    keptIndices.delete(index);
                } else {
                    keptIndices.add(index);
                }
                playSound("hold");
                renderDice();
            });
        });

        const hint = document.getElementById("kniffel-roll-hint");
        if (game.rollCount <= 0) {
            hint.textContent = "Erster Wurf: alle Würfel rollen.";
        } else if (game.rollCount >= game.maxRolls) {
            hint.textContent = "Drei Würfe gespielt. Trage jetzt eine Kategorie ein.";
        } else {
            hint.textContent = "Klicke Würfel an, um sie zu halten.";
        }
    }

    function renderScoreTable() {
        const table = document.getElementById("kniffel-score-table");
        const playerHeaders = game.players.map((player) => `<th>${escapeHtml(player.isYou ? "Du" : player.name)}</th>`).join("");
        let currentSection = "";
        const bodyRows = game.categories.map((category) => {
            const sectionRow = category.section !== currentSection
                ? `<tr class="kniffel-score-section"><th colspan="${game.players.length + 1}">${category.section === "upper" ? "Oberer Block" : "Unterer Block"}</th></tr>`
                : "";
            currentSection = category.section;
            const scoreCells = game.players.map((player) => {
                const value = category.scoresByPlayer[String(player.id)];
                const isYou = player.isYou;
                const canChoose = isYou && game.canScore && !category.used;
                if (canChoose) {
                    return `<td><button type="button" class="kniffel-score-button" data-category="${escapeHtml(category.key)}">${category.preview ?? 0}</button></td>`;
                }
                return `<td class="${value === null || value === undefined ? "is-empty" : ""}">${value === null || value === undefined ? "-" : value}</td>`;
            }).join("");
            return `
                ${sectionRow}
                <tr class="${category.used ? "is-used" : ""}">
                    <th>
                        <strong>${escapeHtml(category.label)}</strong>
                        <small>${escapeHtml(category.description)}</small>
                    </th>
                    ${scoreCells}
                </tr>
            `;
        }).join("");

        const totalRows = `
            <tr class="kniffel-total-row">
                <th>Oberer Block</th>
                ${game.players.map((player) => `<td>${player.upper}</td>`).join("")}
            </tr>
            <tr class="kniffel-total-row">
                <th>Bonus</th>
                ${game.players.map((player) => `<td>${player.bonus}</td>`).join("")}
            </tr>
            <tr class="kniffel-grand-row">
                <th>Gesamt</th>
                ${game.players.map((player) => `<td>${player.total}</td>`).join("")}
            </tr>
        `;

        table.innerHTML = `
            <thead>
                <tr>
                    <th>Kategorie</th>
                    ${playerHeaders}
                </tr>
            </thead>
            <tbody>${bodyRows}${totalRows}</tbody>
        `;

        table.querySelectorAll(".kniffel-score-button").forEach((button) => {
            button.addEventListener("click", () => {
                post(urls.score, {category: button.dataset.category}, "score");
            });
        });
    }

    function renderLog() {
        document.getElementById("kniffel-log").innerHTML = (game.actionLog || [])
            .slice()
            .reverse()
            .map((entry) => `<span>${escapeHtml(entry)}</span>`)
            .join("");
    }

    function renderWinnerModal() {
        const modal = document.getElementById("kniffel-winner-modal");
        const name = document.getElementById("kniffel-winner-name");
        if (!modal || !name) return;
        const key = winnerKey();
        const shouldShow = game.status === "finished" && game.winnerName && key !== dismissedWinnerKey;
        name.textContent = game.winnerName || "-";
        modal.classList.toggle("hidden", !shouldShow);
        if (shouldShow && key !== lastWinnerSoundKey) {
            playSound("winner");
            lastWinnerSoundKey = key;
        }
    }

    function hideWinnerModal() {
        document.getElementById("kniffel-winner-modal")?.classList.add("hidden");
    }

    function winnerKey() {
        if (!game) return "";
        return `${game.id || ""}:${game.winnerUserId || ""}:${game.updatedAt || ""}`;
    }

    function noticePlayerChanges() {
        const signature = game.players.map((player) => player.id).join(",");
        if (lastPlayersSignature && lastPlayersSignature !== signature) {
            playSound("player");
            showToast("Spielerliste aktualisiert");
        }
        lastPlayersSignature = signature;
    }

    function noticeTurnChange() {
        const currentId = game.currentPlayerId ? String(game.currentPlayerId) : "";
        if (!lastCurrentPlayerId) {
            lastCurrentPlayerId = currentId;
            return;
        }
        if (game.status === "playing" && currentId && currentId !== lastCurrentPlayerId) {
            const currentIsYou = game.players.some((player) => String(player.id) === currentId && player.isYou);
            playSound(currentIsYou ? "turn" : "pass");
        }
        lastCurrentPlayerId = currentId;
    }

    function animateDiceRoll() {
        const row = document.getElementById("kniffel-dice-row");
        row?.classList.remove("is-rolling");
        void row?.offsetWidth;
        row?.classList.add("is-rolling");
        window.setTimeout(() => row?.classList.remove("is-rolling"), 700);
    }

    function dieFaceMarkup(value) {
        const active = {
            1: [4],
            2: [0, 8],
            3: [0, 4, 8],
            4: [0, 2, 6, 8],
            5: [0, 2, 4, 6, 8],
            6: [0, 2, 3, 5, 6, 8],
        }[Number(value)] || [];
        return `
            <span class="kniffel-pip-grid" aria-hidden="true">
                ${Array.from({length: 9}, (_item, index) => `<span class="${active.includes(index) ? "is-active" : ""}"></span>`).join("")}
            </span>
        `;
    }

    function avatarMarkup(player, className) {
        const initials = player.initials || (player.name || "?").slice(0, 2).toUpperCase();
        if (player.avatarUrl) {
            return `<span class="${className} has-image"><img src="${escapeHtml(player.avatarUrl)}" alt="${escapeHtml(player.name)}"></span>`;
        }
        return `<span class="${className}">${escapeHtml(initials)}</span>`;
    }

    function updateSoundButton() {
        const button = document.getElementById("kniffel-sound-toggle");
        if (!button) return;
        button.setAttribute("aria-pressed", soundEnabled ? "true" : "false");
        button.classList.toggle("is-muted", !soundEnabled);
        button.innerHTML = `
            <i class="fa-solid ${soundEnabled ? "fa-volume-high" : "fa-volume-xmark"}"></i>
            Sound
        `;
    }

    function unlockAudio() {
        if (!soundEnabled) return;
        if (!audioContext) {
            const AudioContextConstructor = window.AudioContext || window.webkitAudioContext;
            if (!AudioContextConstructor) return;
            audioContext = new AudioContextConstructor();
        }
        if (audioContext.state === "suspended") {
            audioContext.resume();
        }
        audioUnlocked = true;
    }

    function playSound(type) {
        if (!soundEnabled || !audioUnlocked) return;
        unlockAudio();
        if (!audioContext) return;

        const presets = {
            click: [[420, 0.025, "triangle", 0], [640, 0.035, "triangle", 0.025]],
            hold: [[520, 0.03, "triangle", 0], [320, 0.035, "sine", 0.03]],
            roll: [[120, 0.045, "sawtooth", 0], [185, 0.035, "triangle", 0.045], [145, 0.04, "sawtooth", 0.085], [230, 0.05, "triangle", 0.13], [165, 0.04, "sawtooth", 0.18]],
            score: [[392, 0.05, "triangle", 0], [523, 0.06, "triangle", 0.05], [659, 0.08, "square", 0.12]],
            start: [[196, 0.05, "triangle", 0], [392, 0.06, "triangle", 0.05], [784, 0.08, "triangle", 0.11]],
            turn: [[660, 0.05, "triangle", 0], [880, 0.08, "triangle", 0.06]],
            pass: [[280, 0.04, "sine", 0], [210, 0.05, "sine", 0.04]],
            player: [[320, 0.04, "triangle", 0], [480, 0.05, "triangle", 0.045]],
            winner: [[330, 0.08, "triangle", 0], [494, 0.10, "triangle", 0.08], [659, 0.12, "triangle", 0.17], [988, 0.16, "square", 0.28]],
            error: [[170, 0.08, "sawtooth", 0], [110, 0.10, "sawtooth", 0.08]],
            toggleOn: [[520, 0.04, "triangle", 0], [760, 0.06, "triangle", 0.04]],
            toggleOff: [[360, 0.04, "triangle", 0], [220, 0.06, "triangle", 0.04]],
        };

        (presets[type] || presets.click).forEach(([frequency, duration, wave, delay]) => {
            tone(frequency, duration, wave, delay);
        });
    }

    function tone(frequency, duration, wave = "sine", delay = 0) {
        const start = audioContext.currentTime + delay;
        const oscillator = audioContext.createOscillator();
        const gain = audioContext.createGain();
        oscillator.type = wave;
        oscillator.frequency.setValueAtTime(frequency, start);
        oscillator.frequency.exponentialRampToValueAtTime(Math.max(40, frequency * 0.82), start + duration);
        gain.gain.setValueAtTime(0.0001, start);
        gain.gain.exponentialRampToValueAtTime(0.1, start + 0.01);
        gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);
        oscillator.connect(gain);
        gain.connect(audioContext.destination);
        oscillator.start(start);
        oscillator.stop(start + duration + 0.03);
    }

    function handleDeletedGame(payload) {
        showToast(payload.error || "Dieser Raum wurde gelöscht.");
        window.setTimeout(() => {
            window.location.href = payload.redirectUrl || "/kniffel/";
        }, 900);
    }

    function initHomePage(rootElement) {
        const stateUrl = rootElement.dataset.homeStateUrl;
        if (!stateUrl) return;
        const csrfToken = getCookie("csrftoken");
        const labels = {
            emptyInvites: rootElement.dataset.emptyInvitesLabel || "Keine Einladungen.",
            emptyGames: rootElement.dataset.emptyGamesLabel || "Keine Räume.",
            from: rootElement.dataset.fromLabel || "von",
            accept: rootElement.dataset.acceptLabel || "Annehmen",
            decline: rootElement.dataset.declineLabel || "Ablehnen",
            round: rootElement.dataset.roundLabel || "Runde",
        };
        let lastSignature = "";
        refreshHomeState();
        window.setInterval(refreshHomeState, 1200);

        async function refreshHomeState() {
            try {
                const response = await fetch(stateUrl, {headers: {"X-Requested-With": "XMLHttpRequest"}});
                const json = await response.json();
                if (!json.ok) return;
                const signature = JSON.stringify({games: json.games, invites: json.invites});
                if (signature === lastSignature) return;
                lastSignature = signature;
                renderHomeInvites(json.invites || []);
                renderHomeGames(json.games || []);
            } catch (error) {
                console.warn("Kniffel home state failed", error);
            }
        }

        function renderHomeInvites(invites) {
            const container = document.getElementById("kniffel-invites-live");
            if (!container) return;
            if (!invites.length) {
                container.innerHTML = `<p class="kniffel-muted" id="kniffel-invites-empty">${escapeHtml(labels.emptyInvites)}</p>`;
                return;
            }
            container.innerHTML = `
                <div class="kniffel-invite-list" id="kniffel-invite-list">
                    ${invites.map(invite => `
                        <div class="kniffel-invite-row">
                            <div>
                                <strong>${escapeHtml(invite.gameName)}</strong>
                                <span>${escapeHtml(labels.from)} ${escapeHtml(invite.fromUser)}</span>
                            </div>
                            <div class="kniffel-inline-actions">
                                ${inviteForm(invite.acceptUrl, "accept", labels.accept, "kniffel-primary")}
                                ${inviteForm(invite.declineUrl, "decline", labels.decline, "kniffel-secondary")}
                            </div>
                        </div>
                    `).join("")}
                </div>
            `;
        }

        function renderHomeGames(games) {
            const container = document.getElementById("kniffel-games-live");
            if (!container) return;
            if (!games.length) {
                container.innerHTML = `<p class="kniffel-muted" id="kniffel-games-empty">${escapeHtml(labels.emptyGames)}</p>`;
                return;
            }
            container.innerHTML = `
                <div class="kniffel-room-grid" id="kniffel-room-grid">
                    ${games.map(game => `
                        <a class="kniffel-room-card" href="${escapeHtml(game.url)}">
                            <span class="kniffel-code">${escapeHtml(game.code)}</span>
                            <strong>${escapeHtml(game.name)}</strong>
                            <span>${escapeHtml(game.statusLabel)} - ${game.playerCount}/${game.maxPlayers} - ${escapeHtml(labels.round)} ${game.roundNumber}</span>
                        </a>
                    `).join("")}
                </div>
            `;
        }

        function inviteForm(url, action, label, className) {
            return `
                <form method="post" action="${escapeHtml(url)}">
                    <input type="hidden" name="csrfmiddlewaretoken" value="${escapeHtml(csrfToken)}">
                    <input type="hidden" name="action" value="${escapeHtml(action)}">
                    <button class="${escapeHtml(className)}" type="submit">${escapeHtml(label)}</button>
                </form>
            `;
        }
    }

    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(";").shift();
        return "";
    }

    function showToast(message) {
        let toast = document.querySelector(".kniffel-toast");
        if (!toast) {
            toast = document.createElement("div");
            toast.className = "kniffel-toast";
            document.body.appendChild(toast);
        }
        toast.textContent = message;
        clearTimeout(toast.timer);
        toast.timer = window.setTimeout(() => toast.remove(), 2200);
    }

    function escapeHtml(value) {
        return String(value ?? "").replace(/[&<>'"]/g, char => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            "'": "&#39;",
            '"': "&quot;",
        }[char]));
    }
});
