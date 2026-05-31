document.addEventListener("DOMContentLoaded", () => {
    const homeRoot = document.querySelector(".c4-home-page");
    if (homeRoot) initHomePage(homeRoot);

    const root = document.querySelector(".c4-lobby-page");
    if (!root) return;

    const urls = {
        state: root.dataset.stateUrl,
        move: root.dataset.moveUrl,
        reset: root.dataset.resetUrl,
    };
    const csrfToken = getCookie("csrftoken");
    const board = document.getElementById("c4-board");
    const dropZone = document.getElementById("c4-drop-zone");
    const columnButtons = Array.from(document.querySelectorAll(".c4-column-button"));
    const fallingDisc = document.getElementById("c4-falling-disc");
    const cells = [];
    let game = null;
    let isPosting = false;
    let lastMoveKey = "";

    buildBoard();
    bindEvents();
    refreshState(true);
    setInterval(() => refreshState(false), 800);

    function buildBoard() {
        board.innerHTML = "";
        for (let row = 0; row < 6; row += 1) {
            for (let column = 0; column < 7; column += 1) {
                const index = (row * 7) + column;
                const cell = document.createElement("button");
                cell.type = "button";
                cell.className = "c4-cell";
                cell.dataset.index = String(index);
                cell.dataset.row = String(row);
                cell.dataset.column = String(column);
                cell.setAttribute("aria-label", `Feld ${row + 1}, ${column + 1}`);
                board.appendChild(cell);
                cells.push(cell);
            }
        }
    }

    function bindEvents() {
        document.querySelectorAll("form[data-confirm]").forEach((form) => {
            form.addEventListener("submit", (event) => {
                if (!window.confirm(form.dataset.confirm || "Wirklich löschen?")) {
                    event.preventDefault();
                }
            });
        });

        columnButtons.forEach((button) => {
            button.addEventListener("click", async () => {
                if (!game?.canMove || isPosting) return;
                await post(urls.move, {column: button.dataset.column});
            });
        });

        cells.forEach((cell) => {
            cell.addEventListener("click", async () => {
                if (!game?.canMove || isPosting) return;
                await post(urls.move, {column: cell.dataset.column});
            });
        });

        document.getElementById("c4-reset")?.addEventListener("click", async () => {
            if (isPosting) return;
            lastMoveKey = "";
            await post(urls.reset, {}, true);
        });

        document.getElementById("c4-result-reset")?.addEventListener("click", async () => {
            if (isPosting) return;
            lastMoveKey = "";
            await post(urls.reset, {}, true);
        });

        document.getElementById("c4-copy-link")?.addEventListener("click", async () => {
            await navigator.clipboard?.writeText(window.location.href);
            showToast("Link kopiert");
        });
    }

    async function refreshState(force = false) {
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
                render(force);
            }
        } catch (error) {
            console.warn("Vier gewinnt state failed", error);
        }
    }

    async function post(url, data = {}, forceRender = false) {
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
            if (!response.ok || !json.ok) {
                showToast(json.error || "Aktion fehlgeschlagen");
                return;
            }
            game = json.game;
            render(forceRender);
        } finally {
            isPosting = false;
        }
    }

    function render(force = false) {
        document.getElementById("c4-player-red").textContent = game.players.R || "Wartet...";
        document.getElementById("c4-player-yellow").textContent = game.players.Y || "Wartet...";
        document.getElementById("c4-status").textContent = game.statusLabel;
        document.getElementById("c4-message").textContent = game.message;
        document.getElementById("c4-round").textContent = game.roundNumber;
        document.getElementById("c4-disc").textContent = discLabel(game.playerDisc) || "Zuschauer";
        document.getElementById("c4-current").textContent = discLabel(game.currentDisc);

        const winningLine = new Set(game.winningLine || []);
        cells.forEach((cell, index) => {
            const value = game.board[index] || "";
            const previous = cell.dataset.value || "";
            cell.dataset.value = value;
            cell.disabled = isPosting || !game.canMove || game.status !== "playing";
            cell.classList.toggle("is-red", value === "R");
            cell.classList.toggle("is-yellow", value === "Y");
            cell.classList.toggle("is-empty", !value);
            cell.classList.toggle("is-winning", winningLine.has(index));
            if (force || previous !== value) {
                cell.classList.remove("just-dropped");
                if (value && previous !== value) {
                    window.requestAnimationFrame(() => cell.classList.add("just-dropped"));
                }
            }
        });

        columnButtons.forEach((button) => {
            const column = Number(button.dataset.column);
            const isFull = Boolean(game.board[column]);
            button.disabled = isPosting || !game.canMove || isFull || game.status !== "playing";
        });

        board.classList.toggle("is-your-turn", Boolean(game.canMove));
        dropZone.classList.toggle("is-your-turn", Boolean(game.canMove));
        renderResultOverlay();
        animateLastMove();
    }

    function renderResultOverlay() {
        const overlay = document.getElementById("c4-result-overlay");
        const title = document.getElementById("c4-result-title");
        const text = document.getElementById("c4-result-text");
        const kicker = document.getElementById("c4-result-kicker");
        if (!overlay || !title || !text || !kicker) return;

        const isFinished = game.status === "finished";
        overlay.classList.toggle("hidden", !isFinished);
        if (!isFinished) return;

        overlay.classList.toggle("is-red", game.winnerDisc === "R");
        overlay.classList.toggle("is-yellow", game.winnerDisc === "Y");
        overlay.classList.toggle("is-draw", !game.winnerDisc);

        if (!game.winnerDisc) {
            kicker.textContent = "Unentschieden";
            title.textContent = "Keiner gewinnt diese Runde";
            text.textContent = "Das Board ist voll. Startet eine neue Runde und klärt das.";
            return;
        }

        const winnerName = game.players[game.winnerDisc] || discLabel(game.winnerDisc);
        const playerWon = game.playerDisc && game.playerDisc === game.winnerDisc;
        kicker.textContent = playerWon ? "Gewonnen" : "Spiel beendet";
        title.textContent = playerWon ? "Du hast gewonnen!" : `${winnerName} hat gewonnen`;
        text.textContent = `${discLabel(game.winnerDisc)} verbindet vier Steine.`;
    }

    function animateLastMove() {
        const move = game.lastMove || {};
        if (!Number.isInteger(move.index)) return;
        const key = `${game.roundNumber}:${move.index}:${move.disc}`;
        if (key === lastMoveKey) return;
        lastMoveKey = key;

        const target = cells[move.index];
        if (!target) return;
        const boardRect = board.getBoundingClientRect();
        const targetRect = target.getBoundingClientRect();
        const size = Math.min(targetRect.width, targetRect.height) * 0.78;
        fallingDisc.className = `c4-falling-disc is-${move.disc === "R" ? "red" : "yellow"}`;
        fallingDisc.style.width = `${size}px`;
        fallingDisc.style.height = `${size}px`;
        fallingDisc.style.left = `${targetRect.left - boardRect.left + (targetRect.width - size) / 2}px`;
        fallingDisc.style.top = `${-size - 18}px`;
        fallingDisc.classList.remove("hidden");

        window.requestAnimationFrame(() => {
            fallingDisc.style.transform = `translateY(${targetRect.top - boardRect.top + (targetRect.height - size) / 2 + size + 18}px)`;
        });
        window.setTimeout(() => {
            fallingDisc.classList.add("hidden");
            fallingDisc.style.transform = "";
        }, 430);
    }

    function discLabel(disc) {
        if (disc === "R") return "Rot";
        if (disc === "Y") return "Gelb";
        return "";
    }

    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(";").shift();
        return "";
    }

    function showToast(message) {
        let toast = document.querySelector(".c4-toast");
        if (!toast) {
            toast = document.createElement("div");
            toast.className = "c4-toast";
            document.body.appendChild(toast);
        }
        toast.textContent = message;
        clearTimeout(toast.timer);
        toast.timer = setTimeout(() => toast.remove(), 2200);
    }

    function handleDeletedGame(payload) {
        showToast(payload.error || "Dieser Raum wurde gelöscht.");
        window.setTimeout(() => {
            window.location.href = payload.redirectUrl || "/vier-gewinnt/";
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
                console.warn("Vier gewinnt home state failed", error);
            }
        }

        function renderHomeInvites(invites) {
            const container = document.getElementById("c4-invites-live");
            if (!container) return;
            if (!invites.length) {
                container.innerHTML = `<p class="c4-muted" id="c4-invites-empty">${escapeHtml(labels.emptyInvites)}</p>`;
                return;
            }
            container.innerHTML = `
                <div class="c4-invite-list" id="c4-invite-list">
                    ${invites.map(invite => `
                        <div class="c4-invite-row">
                            <div>
                                <strong>${escapeHtml(invite.gameName)}</strong>
                                <span>${escapeHtml(labels.from)} ${escapeHtml(invite.fromUser)}</span>
                            </div>
                            <div class="c4-inline-actions">
                                ${inviteForm(invite.acceptUrl, "accept", labels.accept, "c4-primary")}
                                ${inviteForm(invite.declineUrl, "decline", labels.decline, "c4-secondary")}
                            </div>
                        </div>
                    `).join("")}
                </div>
            `;
        }

        function renderHomeGames(games) {
            const container = document.getElementById("c4-games-live");
            if (!container) return;
            if (!games.length) {
                container.innerHTML = `<p class="c4-muted" id="c4-games-empty">${escapeHtml(labels.emptyGames)}</p>`;
                return;
            }
            container.innerHTML = `
                <div class="c4-room-grid" id="c4-room-grid">
                    ${games.map(game => `
                        <a class="c4-room-card" href="${escapeHtml(game.url)}">
                            <span class="c4-code">${escapeHtml(game.code)}</span>
                            <strong>${escapeHtml(game.name)}</strong>
                            <span>${escapeHtml(game.statusLabel)} · ${escapeHtml(labels.round)} ${escapeHtml(game.roundNumber)}</span>
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
