document.addEventListener("DOMContentLoaded", () => {
    const homeRoot = document.querySelector(".ttt-home-page");
    if (homeRoot) {
        initHomePage(homeRoot);
    }

    const root = document.querySelector(".ttt-lobby-page");
    if (!root) return;

    const urls = {
        state: root.dataset.stateUrl,
        move: root.dataset.moveUrl,
        reset: root.dataset.resetUrl,
    };
    const csrfToken = getCookie("csrftoken");
    const board = document.getElementById("ttt-board");
    const cells = Array.from(document.querySelectorAll(".ttt-cell"));
    let game = null;
    let isPosting = false;

    bindEvents();
    refreshState();
    setInterval(refreshState, 900);

    function bindEvents() {
        document.querySelectorAll("form[data-confirm]").forEach((form) => {
            form.addEventListener("submit", (event) => {
                if (!window.confirm(form.dataset.confirm || "Wirklich löschen?")) {
                    event.preventDefault();
                }
            });
        });

        cells.forEach((cell) => {
            cell.addEventListener("click", async () => {
                if (!game?.canMove || isPosting) return;
                const index = Number(cell.dataset.index);
                if (game.board[index]) return;
                await post(urls.move, {index});
            });
        });

        document.getElementById("ttt-reset")?.addEventListener("click", async () => {
            if (isPosting) return;
            await post(urls.reset);
        });

        document.getElementById("ttt-copy-link")?.addEventListener("click", async () => {
            await navigator.clipboard?.writeText(window.location.href);
            showToast("Link kopiert");
        });
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
                render();
            }
        } catch (error) {
            console.warn("Tic Tac Toe state failed", error);
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
            if (!response.ok || !json.ok) {
                showToast(json.error || "Aktion fehlgeschlagen");
                return;
            }
            game = json.game;
            render();
        } finally {
            isPosting = false;
        }
    }

    function render() {
        document.getElementById("ttt-player-x").textContent = game.players.X || "Wartet...";
        document.getElementById("ttt-player-o").textContent = game.players.O || "Wartet...";
        document.getElementById("ttt-status").textContent = game.statusLabel;
        document.getElementById("ttt-message").textContent = game.message;
        document.getElementById("ttt-round").textContent = game.roundNumber;
        document.getElementById("ttt-symbol").textContent = game.playerSymbol || "Zuschauer";
        document.getElementById("ttt-current").textContent = game.currentSymbol;

        const winningLine = new Set(game.winningLine || []);
        cells.forEach((cell, index) => {
            const value = game.board[index] || "";
            cell.textContent = value;
            cell.disabled = isPosting || !game.canMove || Boolean(value);
            cell.classList.toggle("is-x", value === "X");
            cell.classList.toggle("is-o", value === "O");
            cell.classList.toggle("is-winning", winningLine.has(index));
        });

        board.classList.toggle("is-your-turn", Boolean(game.canMove));
    }

    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(";").shift();
        return "";
    }

    function showToast(message) {
        let toast = document.querySelector(".ttt-toast");
        if (!toast) {
            toast = document.createElement("div");
            toast.className = "ttt-toast";
            document.body.appendChild(toast);
        }
        toast.textContent = message;
        clearTimeout(toast.timer);
        toast.timer = setTimeout(() => toast.remove(), 2200);
    }

    function handleDeletedGame(payload) {
        showToast(payload.error || "Dieser Raum wurde gelöscht.");
        window.setTimeout(() => {
            window.location.href = payload.redirectUrl || "/tic-tac-toe/";
        }, 900);
    }

    function initHomePage(rootElement) {
        const stateUrl = rootElement.dataset.homeStateUrl;
        if (!stateUrl) return;

        const csrfToken = getCookie("csrftoken");
        const labels = {
            emptyInvites: rootElement.dataset.emptyInvitesLabel || "No pending invitations.",
            emptyGames: rootElement.dataset.emptyGamesLabel || "You do not have a room yet.",
            from: rootElement.dataset.fromLabel || "from",
            accept: rootElement.dataset.acceptLabel || "Accept",
            decline: rootElement.dataset.declineLabel || "Decline",
            round: rootElement.dataset.roundLabel || "Round",
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

                const signature = JSON.stringify({
                    games: json.games,
                    invites: json.invites,
                });
                if (signature === lastSignature) return;
                lastSignature = signature;

                renderHomeInvites(json.invites || []);
                renderHomeGames(json.games || []);
            } catch (error) {
                console.warn("Tic Tac Toe home state failed", error);
            }
        }

        function renderHomeInvites(invites) {
            const container = document.getElementById("ttt-invites-live");
            if (!container) return;

            if (!invites.length) {
                container.innerHTML = `<p class="ttt-muted" id="ttt-invites-empty">${escapeHtml(labels.emptyInvites)}</p>`;
                return;
            }

            container.innerHTML = `
                <div class="ttt-invite-list" id="ttt-invite-list">
                    ${invites.map(invite => `
                        <div class="ttt-invite-row">
                            <div>
                                <strong>${escapeHtml(invite.gameName)}</strong>
                                <span>${escapeHtml(labels.from)} ${escapeHtml(invite.fromUser)}</span>
                            </div>
                            <div class="ttt-inline-actions">
                                ${inviteForm(invite.acceptUrl, "accept", labels.accept, "ttt-primary")}
                                ${inviteForm(invite.declineUrl, "decline", labels.decline, "ttt-secondary")}
                            </div>
                        </div>
                    `).join("")}
                </div>
            `;
        }

        function renderHomeGames(games) {
            const container = document.getElementById("ttt-games-live");
            if (!container) return;

            if (!games.length) {
                container.innerHTML = `<p class="ttt-muted" id="ttt-games-empty">${escapeHtml(labels.emptyGames)}</p>`;
                return;
            }

            container.innerHTML = `
                <div class="ttt-room-grid" id="ttt-room-grid">
                    ${games.map(game => `
                        <a class="ttt-room-card" href="${escapeHtml(game.url)}">
                            <span class="ttt-code">${escapeHtml(game.code)}</span>
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
