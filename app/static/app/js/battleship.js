document.addEventListener("DOMContentLoaded", () => {
    const homeRoot = document.querySelector(".bs-home-page");
    if (homeRoot) initHomePage(homeRoot);

    const root = document.querySelector(".bs-lobby-page");
    if (!root) return;

    const urls = {
        state: root.dataset.stateUrl,
        place: root.dataset.placeUrl,
        attack: root.dataset.attackUrl,
        reset: root.dataset.resetUrl,
    };
    const csrfToken = getCookie("csrftoken");
    const ownBoard = document.getElementById("bs-own-board");
    const enemyBoard = document.getElementById("bs-enemy-board");
    const placementTools = document.getElementById("bs-placement-tools");
    const shipPicker = document.getElementById("bs-ship-picker");
    let game = null;
    let isPosting = false;
    let orientation = "horizontal";
    let selectedShipId = "";
    let placedShips = {};
    let lastEnemyShots = new Set();
    let lastOwnShotsReceived = new Set();
    let hasRenderedBattleState = false;
    let lastRoundNumber = null;

    buildBoards();
    bindLobbyEvents();
    refreshState();
    setInterval(refreshState, 900);

    function bindLobbyEvents() {
        document.querySelectorAll("form[data-confirm]").forEach((form) => {
            form.addEventListener("submit", (event) => {
                if (!window.confirm(form.dataset.confirm || "Wirklich löschen?")) {
                    event.preventDefault();
                }
            });
        });

        document.getElementById("bs-place")?.addEventListener("click", async () => {
            if (isPosting || !game?.canPlace) return;
            const fleet = serializePlacedFleet();
            if (!fleet) {
                showToast("Platziere erst alle Schiffe.");
                playSound("error");
                return;
            }
            await post(urls.place, {fleet: JSON.stringify(fleet)});
        });

        document.getElementById("bs-rotate")?.addEventListener("click", () => {
            orientation = orientation === "horizontal" ? "vertical" : "horizontal";
            const rotateButton = document.getElementById("bs-rotate");
            if (rotateButton) {
                const label = orientation === "horizontal" ? "Horizontal platzieren" : "Vertikal platzieren";
                rotateButton.title = label;
                rotateButton.setAttribute("aria-label", label);
                rotateButton.classList.toggle("is-vertical", orientation === "vertical");
            }
            playSound("click");
        });

        document.getElementById("bs-random-fleet")?.addEventListener("click", () => {
            if (!game?.canPlace) return;
            randomizePlacement();
            renderPlacement();
            playSound("place");
        });

        document.getElementById("bs-clear-fleet")?.addEventListener("click", () => {
            if (!game?.canPlace) return;
            placedShips = {};
            selectedShipId = game.fleetConfig?.[0]?.id || "";
            renderPlacement();
            playSound("click");
        });

        document.getElementById("bs-reset")?.addEventListener("click", async () => {
            if (isPosting) return;
            await post(urls.reset);
        });

        document.getElementById("bs-copy-link")?.addEventListener("click", async () => {
            await navigator.clipboard?.writeText(window.location.href);
            showToast("Link kopiert");
        });
    }

    function buildBoards() {
        ownBoard.innerHTML = "";
        enemyBoard.innerHTML = "";
        for (let index = 0; index < 64; index += 1) {
            const ownCell = document.createElement("button");
            ownCell.type = "button";
            ownCell.className = "bs-cell";
            ownCell.dataset.index = index;
            ownCell.addEventListener("click", () => placeSelectedShip(index));
            ownCell.addEventListener("mouseenter", () => renderPlacement(index));
            ownCell.addEventListener("mouseleave", () => renderPlacement());
            ownBoard.appendChild(ownCell);

            const enemyCell = document.createElement("button");
            enemyCell.type = "button";
            enemyCell.className = "bs-cell";
            enemyCell.dataset.index = index;
            enemyCell.addEventListener("click", async () => {
                if (!game?.canAttack || isPosting) return;
                if ((game.enemy.shots || []).includes(index)) return;
                await post(urls.attack, {index});
            });
            enemyBoard.appendChild(enemyCell);
        }
    }

    async function refreshState() {
        try {
            const response = await fetch(urls.state, {
                headers: {"X-Requested-With": "XMLHttpRequest"},
            });
            const json = await response.json();
            if (json.gameDeleted) {
                handleDeletedGame(json);
                return;
            }
            if (json.ok) {
                game = json.game;
                renderLobby();
            }
        } catch (error) {
            console.warn("Battleship state failed", error);
        }
    }

    async function post(url, data = {}) {
        isPosting = true;
        const formData = new FormData();
        Object.entries(data).forEach(([key, value]) => formData.append(key, value));

        try {
            const response = await fetch(url, {
                method: "POST",
                headers: {"X-CSRFToken": csrfToken},
                body: formData,
            });
            const json = await response.json().catch(() => ({ok: false}));
            if (json.gameDeleted) {
                handleDeletedGame(json);
                return;
            }
            if (!response.ok || !json.ok) {
                showToast(json.error || "Aktion fehlgeschlagen");
                return;
            }
            game = json.game;
            renderLobby();
        } finally {
            isPosting = false;
        }
    }

    function renderLobby() {
        document.getElementById("bs-player-a").textContent = game.players.A || "Wartet...";
        document.getElementById("bs-player-b").textContent = game.players.B || "Wartet...";
        document.getElementById("bs-status").textContent = game.statusLabel;
        document.getElementById("bs-message").textContent = game.message;
        document.getElementById("bs-turn").textContent = game.currentTurn ? `Zug ${game.currentTurn}` : "-";
        document.getElementById("bs-own-ready").textContent = game.readiness[game.side] ? "Bereit" : "Nicht bereit";
        syncPlacementState();
        renderShipPicker();

        const placeButton = document.getElementById("bs-place");
        placeButton.disabled = !game.canPlace || isPosting;
        placeButton.style.display = game.canPlace || game.status === "setup" ? "inline-flex" : "none";
        const resetButton = document.getElementById("bs-reset");
        if (resetButton) {
            resetButton.hidden = !game.isOwner;
            resetButton.disabled = !game.isOwner || isPosting;
        }
        placementTools?.classList.toggle("is-hidden", !game.canPlace);
        renderVictoryOverlay();

        const ownShips = new Set(game.own.ships || []);
        const shotsReceived = new Set(game.own.shotsReceived || []);
        const hitsReceived = new Set(game.own.hitsReceived || []);
        const ownSunk = new Set(game.own.sunk || []);
        if (game.canPlace) {
            renderPlacement();
        } else {
            ownBoard.querySelectorAll(".bs-cell").forEach((cell) => {
                const index = Number(cell.dataset.index);
                setCellState(cell, {
                    ship: ownShips.has(index),
                    miss: shotsReceived.has(index) && !hitsReceived.has(index),
                    hit: hitsReceived.has(index),
                    sunk: ownSunk.has(index),
                });
                cell.disabled = true;
            });
        }

        const enemyShots = new Set(game.enemy.shots || []);
        const enemyHits = new Set(game.enemy.hits || []);
        const enemySunk = new Set(game.enemy.sunk || []);
        const changedEnemyShots = [...enemyShots].filter(index => !lastEnemyShots.has(index));
        const changedOwnShots = [...shotsReceived].filter(index => !lastOwnShotsReceived.has(index));
        enemyBoard.querySelectorAll(".bs-cell").forEach((cell) => {
            const index = Number(cell.dataset.index);
            const shot = enemyShots.has(index);
            setCellState(cell, {
                miss: shot && !enemyHits.has(index),
                hit: enemyHits.has(index),
                sunk: enemySunk.has(index),
            });
            cell.disabled = isPosting || !game.canAttack || shot;
            cell.classList.toggle("is-new-shot", changedEnemyShots.includes(index));
        });

        if (hasRenderedBattleState) {
            changedEnemyShots.forEach(index => playSound(enemyHits.has(index) ? "hit" : "miss"));
            if (changedOwnShots.length) {
                root.classList.remove("is-impact");
                void root.offsetWidth;
                root.classList.add("is-impact");
                changedOwnShots.forEach(index => playSound(hitsReceived.has(index) ? "hit" : "miss"));
            }
        }
        hasRenderedBattleState = true;
        lastEnemyShots = enemyShots;
        lastOwnShotsReceived = shotsReceived;
    }

    function renderVictoryOverlay() {
        const overlay = document.getElementById("bs-victory-overlay");
        if (!overlay) return;

        const title = document.getElementById("bs-victory-title");
        const text = document.getElementById("bs-victory-text");
        const isFinished = game.status === "finished" && game.winnerSide;
        overlay.hidden = !isFinished;
        if (!isFinished) return;

        const won = game.winnerSide === game.side;
        const winnerName = game.players[game.winnerSide] || `Spieler ${game.winnerSide}`;
        title.textContent = won ? "Sieg!" : "Flotte verloren";
        text.textContent = won
            ? "Du hast alle gegnerischen Schiffe versenkt."
            : `${winnerName} hat alle deine Schiffe versenkt.`;

        if (won) {
            playSound("victory");
        }
    }

    function setCellState(cell, state) {
        cell.classList.toggle("is-ship", Boolean(state.ship));
        cell.classList.toggle("is-miss", Boolean(state.miss));
        cell.classList.toggle("is-hit", Boolean(state.hit));
        cell.classList.toggle("is-sunk", Boolean(state.sunk));
        cell.classList.toggle("is-placement-preview", Boolean(state.preview));
        cell.classList.toggle("is-placement-invalid", Boolean(state.invalid));
    }

    function syncPlacementState() {
        if (!game?.canPlace) return;
        if (lastRoundNumber !== game.roundNumber) {
            placedShips = {};
            selectedShipId = "";
            lastEnemyShots = new Set();
            lastOwnShotsReceived = new Set();
            hasRenderedBattleState = false;
        }
        lastRoundNumber = game.roundNumber;
        if (!selectedShipId) selectedShipId = game.fleetConfig?.[0]?.id || "";
    }

    function renderShipPicker() {
        if (!shipPicker || !game?.fleetConfig) return;
        shipPicker.innerHTML = game.fleetConfig.map(ship => {
            const placed = Boolean(placedShips[ship.id]);
            const active = selectedShipId === ship.id;
            return `
                <button type="button" class="bs-ship-choice${active ? " is-active" : ""}${placed ? " is-placed" : ""}" data-ship-id="${escapeHtml(ship.id)}">
                    <span>${escapeHtml(ship.name)}</span>
                    <span>${"■".repeat(ship.length)}</span>
                </button>
            `;
        }).join("");

        shipPicker.querySelectorAll("[data-ship-id]").forEach(button => {
            button.addEventListener("click", () => {
                selectedShipId = button.dataset.shipId;
                renderShipPicker();
                renderPlacement();
                playSound("click");
            });
        });
    }

    function placeSelectedShip(startIndex) {
        if (!game?.canPlace || !selectedShipId) return;
        const ship = game.fleetConfig.find(item => item.id === selectedShipId);
        const cells = cellsForPlacement(startIndex, ship?.length || 0, orientation);
        if (!canPlaceCells(cells, selectedShipId)) {
            playSound("error");
            renderPlacement(startIndex);
            return;
        }
        placedShips[selectedShipId] = cells;
        const nextOpen = game.fleetConfig.find(item => !placedShips[item.id]);
        if (nextOpen) selectedShipId = nextOpen.id;
        renderShipPicker();
        renderPlacement();
        playSound("place");
    }

    function renderPlacement(previewStart = null) {
        const placed = placedCellMap();
        const ship = game?.fleetConfig?.find(item => item.id === selectedShipId);
        const previewCells = previewStart !== null && ship ? cellsForPlacement(previewStart, ship.length, orientation) : [];
        const previewValid = previewCells.length > 0 && canPlaceCells(previewCells, selectedShipId);
        const previewSet = new Set(previewCells);

        ownBoard.querySelectorAll(".bs-cell").forEach(cell => {
            const index = Number(cell.dataset.index);
            setCellState(cell, {
                ship: placed.has(index),
                preview: previewSet.has(index) && previewValid,
                invalid: previewSet.has(index) && !previewValid,
            });
            cell.disabled = !game?.canPlace;
        });
    }

    function cellsForPlacement(startIndex, length, direction) {
        const row = Math.floor(startIndex / 8);
        const col = startIndex % 8;
        if (direction === "horizontal" && col + length > 8) return [];
        if (direction === "vertical" && row + length > 8) return [];
        return Array.from({length}, (_, offset) => (
            direction === "horizontal" ? startIndex + offset : startIndex + (offset * 8)
        ));
    }

    function canPlaceCells(cells, shipId) {
        if (!cells.length) return false;
        const occupied = placedCellMap(shipId);
        return cells.every(cell => cell >= 0 && cell < 64 && !occupied.has(cell));
    }

    function placedCellMap(exceptShipId = "") {
        const cells = new Set();
        Object.entries(placedShips).forEach(([shipId, shipCells]) => {
            if (shipId === exceptShipId) return;
            shipCells.forEach(cell => cells.add(cell));
        });
        return cells;
    }

    function serializePlacedFleet() {
        if (!game?.fleetConfig?.every(ship => placedShips[ship.id]?.length === ship.length)) return null;
        return game.fleetConfig.map(ship => ({
            id: ship.id,
            length: ship.length,
            cells: placedShips[ship.id],
        }));
    }

    function randomizePlacement() {
        placedShips = {};
        game.fleetConfig.forEach(ship => {
            for (let attempt = 0; attempt < 300; attempt += 1) {
                const direction = Math.random() > 0.5 ? "horizontal" : "vertical";
                const start = Math.floor(Math.random() * 64);
                const cells = cellsForPlacement(start, ship.length, direction);
                if (canPlaceCells(cells, ship.id)) {
                    placedShips[ship.id] = cells;
                    break;
                }
            }
        });
        selectedShipId = game.fleetConfig.find(ship => !placedShips[ship.id])?.id || game.fleetConfig[0]?.id || "";
        renderShipPicker();
    }

    function initHomePage(rootElement) {
        const stateUrl = rootElement.dataset.homeStateUrl;
        if (!stateUrl) return;
        const csrfToken = getCookie("csrftoken");
        let lastSignature = "";

        refreshHomeState();
        setInterval(refreshHomeState, 1200);

        async function refreshHomeState() {
            try {
                const response = await fetch(stateUrl, {
                    headers: {"X-Requested-With": "XMLHttpRequest"},
                });
                const json = await response.json();
                if (!json.ok) return;
                const signature = JSON.stringify({games: json.games, invites: json.invites});
                if (signature === lastSignature) return;
                lastSignature = signature;
                renderHomeInvites(json.invites || []);
                renderHomeGames(json.games || []);
            } catch (error) {
                console.warn("Battleship home state failed", error);
            }
        }

        function renderHomeInvites(invites) {
            const container = document.getElementById("bs-invites-live");
            if (!container) return;
            if (!invites.length) {
                container.innerHTML = '<p class="bs-muted">Du hast aktuell keine offenen Schiffe-versenken-Einladungen.</p>';
                return;
            }
            container.innerHTML = `
                <div class="bs-invite-list">
                    ${invites.map(invite => `
                        <div class="bs-invite-row">
                            <div>
                                <strong>${escapeHtml(invite.gameName)}</strong>
                                <span>von ${escapeHtml(invite.fromUser)}</span>
                            </div>
                            <div class="bs-inline-actions">
                                ${inviteForm(invite.acceptUrl, "accept", "Annehmen", "bs-primary")}
                                ${inviteForm(invite.declineUrl, "decline", "Ablehnen", "bs-secondary")}
                            </div>
                        </div>
                    `).join("")}
                </div>
            `;
        }

        function renderHomeGames(games) {
            const container = document.getElementById("bs-games-live");
            if (!container) return;
            if (!games.length) {
                container.innerHTML = '<p class="bs-muted">Du hast noch keinen Schiffe-versenken-Raum.</p>';
                return;
            }
            container.innerHTML = `
                <div class="bs-room-grid">
                    ${games.map(item => `
                        <a class="bs-room-card" href="${escapeHtml(item.url)}">
                            <span class="bs-code">${escapeHtml(item.code)}</span>
                            <strong>${escapeHtml(item.name)}</strong>
                            <span>${escapeHtml(item.statusLabel)} · Runde ${escapeHtml(item.roundNumber)}</span>
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

    function escapeHtml(value) {
        return String(value ?? "").replace(/[&<>'"]/g, char => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            "'": "&#39;",
            '"': "&quot;",
        }[char]));
    }

    function showToast(message) {
        let toast = document.querySelector(".bs-toast");
        if (!toast) {
            toast = document.createElement("div");
            toast.className = "bs-toast";
            document.body.appendChild(toast);
        }
        toast.textContent = message;
        clearTimeout(toast.timer);
        toast.timer = setTimeout(() => toast.remove(), 2200);
    }

    function playSound(type) {
        try {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            if (!AudioContext) return;
            const context = playSound.context || new AudioContext();
            playSound.context = context;
            const now = context.currentTime;

            if (type === "hit") {
                playTone(context, 110, 44, 0.28, "sawtooth", 0.14);
                playNoise(context, 0.24, 520, 0.16);
                window.setTimeout(() => playTone(context, 68, 52, 0.16, "triangle", 0.08), 70);
                return;
            }

            if (type === "miss") {
                playNoise(context, 0.22, 1300, 0.075);
                playTone(context, 360, 180, 0.20, "sine", 0.045);
                return;
            }

            if (type === "place") {
                playTone(context, 220, 330, 0.09, "triangle", 0.055);
                window.setTimeout(() => playTone(context, 330, 520, 0.10, "triangle", 0.05), 55);
                return;
            }

            if (type === "error") {
                playTone(context, 170, 95, 0.16, "square", 0.06);
                return;
            }

            if (type === "victory") {
                playTone(context, 330, 440, 0.12, "triangle", 0.06);
                window.setTimeout(() => playTone(context, 440, 660, 0.14, "triangle", 0.06), 95);
                window.setTimeout(() => playTone(context, 660, 880, 0.18, "triangle", 0.055), 210);
                return;
            }

            playTone(context, 260, 320, 0.07, "sine", 0.04);
        } catch (error) {
            // Browsers can block audio before user interaction.
        }
    }

    function playTone(context, start, end, duration, type, volume) {
        const now = context.currentTime;
        const oscillator = context.createOscillator();
        const gain = context.createGain();
        oscillator.type = type;
        oscillator.frequency.setValueAtTime(start, now);
        oscillator.frequency.exponentialRampToValueAtTime(Math.max(end, 1), now + duration);
        gain.gain.setValueAtTime(0.0001, now);
        gain.gain.exponentialRampToValueAtTime(volume, now + 0.012);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + duration);
        oscillator.connect(gain);
        gain.connect(context.destination);
        oscillator.start(now);
        oscillator.stop(now + duration + 0.03);
    }

    function playNoise(context, duration, frequency, volume) {
        const now = context.currentTime;
        const buffer = context.createBuffer(1, Math.floor(context.sampleRate * duration), context.sampleRate);
        const data = buffer.getChannelData(0);
        for (let index = 0; index < data.length; index += 1) {
            data[index] = (Math.random() * 2 - 1) * (1 - index / data.length);
        }
        const source = context.createBufferSource();
        const filter = context.createBiquadFilter();
        const gain = context.createGain();
        source.buffer = buffer;
        filter.type = "lowpass";
        filter.frequency.setValueAtTime(frequency, now);
        gain.gain.setValueAtTime(volume, now);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + duration);
        source.connect(filter);
        filter.connect(gain);
        gain.connect(context.destination);
        source.start(now);
        source.stop(now + duration);
    }

    function handleDeletedGame(payload) {
        showToast(payload.error || "Dieser Raum wurde gelöscht.");
        window.setTimeout(() => {
            window.location.href = payload.redirectUrl || "/schiffe-versenken/";
        }, 900);
    }
});
