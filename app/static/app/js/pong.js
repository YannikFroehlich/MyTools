document.addEventListener("DOMContentLoaded", () => {
    const homeRoot = document.querySelector(".pong-home-page");
    if (homeRoot) initHomePage(homeRoot);

    const root = document.querySelector(".pong-lobby-page");
    if (!root) return;

    const urls = {
        state: root.dataset.stateUrl,
        paddle: root.dataset.paddleUrl,
        reset: root.dataset.resetUrl,
        ws: root.dataset.wsUrl,
    };

    const csrfToken = getCookie("csrftoken");
    const canvas = document.getElementById("pong-canvas");
    const ctx = canvas.getContext("2d");

    let socket = null;
    let socketReady = false;
    let socketRetry = 0;
    let fallbackTimer = null;
    let game = null;
    let renderState = null;
    let targetBall = null;
    let isPosting = false;
    let desiredY = 50;
    let lastSentY = 50;
    let keys = new Set();
    let lastFrame = performance.now();
    let lastServerStateAt = performance.now();
    let lastPaddleSendAt = 0;

    bindEvents();
    resizeCanvas();
    connectRealtime();
    requestAnimationFrame(loop);

    function bindEvents() {
        window.addEventListener("resize", resizeCanvas);

        document.querySelectorAll("form[data-confirm]").forEach((form) => {
            form.addEventListener("submit", (event) => {
                if (!window.confirm(form.dataset.confirm || "Wirklich löschen?")) {
                    event.preventDefault();
                }
            });
        });

        document.addEventListener("keydown", (event) => {
            if (["KeyW", "KeyS", "ArrowUp", "ArrowDown"].includes(event.code)) {
                keys.add(event.code);
                event.preventDefault();
            }
        });

        document.addEventListener("keyup", (event) => keys.delete(event.code));

        ["pointermove", "pointerdown"].forEach((eventName) => {
            canvas.addEventListener(eventName, (event) => {
                const rect = canvas.getBoundingClientRect();
                desiredY = clamp(((event.clientY - rect.top) / rect.height) * 100, 10, 90);
                applyLocalPaddle();
                sendPaddleRealtime();
            });
        });

        document.getElementById("pong-reset")?.addEventListener("click", () => resetRound());
        document.getElementById("pong-result-reset")?.addEventListener("click", () => resetRound());
        document.getElementById("pong-copy-link")?.addEventListener("click", async () => {
            await navigator.clipboard?.writeText(window.location.href);
            showToast("Link kopiert");
        });
    }

    function connectRealtime() {
        if (!urls.ws || !window.WebSocket) {
            startHttpFallback();
            return;
        }

        const protocol = window.location.protocol === "https:" ? "wss" : "ws";
        const wsUrl = `${protocol}://${window.location.host}${urls.ws}`;
        socket = new WebSocket(wsUrl);

        socket.addEventListener("open", () => {
            socketReady = true;
            socketRetry = 0;
            stopHttpFallback();
            socket.send(JSON.stringify({action: "ping"}));
        });

        socket.addEventListener("message", (event) => {
            let payload;
            try {
                payload = JSON.parse(event.data);
            } catch (error) {
                return;
            }

            if (payload.type === "deleted") {
                handleDeletedGame(payload);
                return;
            }

            if (payload.type === "state" && payload.game) {
                receiveServerState(payload.game);
                return;
            }

            if (payload.type === "error") {
                showToast(payload.error || "Aktion fehlgeschlagen");
            }
        });

        socket.addEventListener("close", () => {
            socketReady = false;
            socket = null;
            startHttpFallback();
            const retryDelay = Math.min(4000, 350 + socketRetry * 400);
            socketRetry += 1;
            window.setTimeout(connectRealtime, retryDelay);
        });

        socket.addEventListener("error", () => {
            socketReady = false;
        });
    }

    function receiveServerState(nextGame) {
        const now = performance.now();
        const previous = renderState;
        game = nextGame;
        lastServerStateAt = now;
        targetBall = {...nextGame.ball};

        const scoreChanged = previous && (
            previous.score?.left !== nextGame.score.left ||
            previous.score?.right !== nextGame.score.right ||
            previous.roundNumber !== nextGame.roundNumber
        );
        const statusChanged = previous && previous.status !== nextGame.status;
        const ballError = previous ? distance(previous.ball?.x, previous.ball?.y, nextGame.ball.x, nextGame.ball.y) : 0;
        const hardSync = !previous || scoreChanged || statusChanged || ballError > 12 || nextGame.status !== "playing";

        if (!previous || hardSync) {
            renderState = cloneGame(nextGame);
            desiredY = nextGame.playerSide ? nextGame.paddles[nextGame.playerSide] : 50;
            lastSentY = desiredY;
        } else {
            const ownSide = nextGame.playerSide;
            const nextPaddles = {...nextGame.paddles};
            if (ownSide) nextPaddles[ownSide] = desiredY;

            renderState = {
                ...previous,
                ...nextGame,
                ball: {...previous.ball},
                paddles: {
                    left: smooth(previous.paddles.left, nextPaddles.left, 0.35),
                    right: smooth(previous.paddles.right, nextPaddles.right, 0.35),
                },
                score: {...nextGame.score},
                players: {...nextGame.players},
            };
        }

        syncUi();
    }

    function startHttpFallback() {
        if (fallbackTimer) return;
        refreshStateHttp();
        fallbackTimer = window.setInterval(refreshStateHttp, 120);
    }

    function stopHttpFallback() {
        if (!fallbackTimer) return;
        window.clearInterval(fallbackTimer);
        fallbackTimer = null;
    }

    async function refreshStateHttp() {
        if (socketReady) return;
        try {
            const response = await fetch(urls.state, {headers: {"X-Requested-With": "XMLHttpRequest"}});
            const json = await response.json();
            if (json.gameDeleted) return handleDeletedGame(json);
            if (json.ok) receiveServerState(json.game);
        } catch (error) {
            console.warn("Pong state failed", error);
        }
    }

    async function post(url, data = {}) {
        isPosting = true;
        const formData = new FormData();
        Object.entries(data).forEach(([key, value]) => formData.append(key, value));
        try {
            const response = await fetch(url, {method: "POST", headers: {"X-CSRFToken": csrfToken}, body: formData});
            const json = await response.json().catch(() => ({ok: false}));
            if (!response.ok || !json.ok) {
                showToast(json.error || "Aktion fehlgeschlagen");
                return;
            }
            receiveServerState(json.game);
        } finally {
            isPosting = false;
        }
    }

    function sendPaddleRealtime() {
        if (!game?.playerSide || game.status === "finished") return;
        if (Math.abs(desiredY - lastSentY) < 0.18) return;

        const now = performance.now();
        if (now - lastPaddleSendAt < 16) return;

        lastPaddleSendAt = now;
        lastSentY = desiredY;

        if (socketReady && socket?.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({action: "paddle", y: desiredY.toFixed(2)}));
        } else {
            post(urls.paddle, {y: desiredY.toFixed(2)});
        }
    }

    function resetRound() {
        if (!game?.isOwner || isPosting) return;

        const topButton = document.getElementById("pong-reset");
        const overlayButton = document.getElementById("pong-result-reset");
        topButton?.setAttribute("disabled", "disabled");
        overlayButton?.setAttribute("disabled", "disabled");

        if (socketReady && socket?.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({action: "reset"}));
            window.setTimeout(() => {
                if (game?.isOwner) {
                    topButton?.removeAttribute("disabled");
                    overlayButton?.removeAttribute("disabled");
                }
            }, 450);
            return;
        }
        post(urls.reset);
    }

    function syncUi() {
        const left = document.getElementById("pong-player-left");
        const right = document.getElementById("pong-player-right");
        if (!left || !game) return;

        left.textContent = game.players.left || "Wartet...";
        right.textContent = game.players.right || "Wartet...";
        document.getElementById("pong-score-left").textContent = game.score.left;
        document.getElementById("pong-score-right").textContent = game.score.right;
        document.getElementById("pong-status").textContent = game.statusLabel;
        document.getElementById("pong-message").textContent = game.message;
        document.getElementById("pong-side").textContent = game.playerSide === "left" ? "Links" : game.playerSide === "right" ? "Rechts" : "Zuschauer";
        document.getElementById("pong-rally").textContent = game.rallyHits || 0;
        document.getElementById("pong-best-rally").textContent = game.bestRally || 0;
        document.getElementById("pong-target").textContent = game.targetScore;
        document.getElementById("pong-round").textContent = game.roundNumber;
        document.getElementById("pong-reset")?.toggleAttribute("disabled", isPosting || !game.isOwner);
        document.getElementById("pong-result-reset")?.toggleAttribute("disabled", isPosting || !game.isOwner);
        renderResultOverlay();
    }

    function renderResultOverlay() {
        const overlay = document.getElementById("pong-result-overlay");
        if (!overlay || !game) return;

        const isFinished = game.status === "finished";
        overlay.classList.toggle("hidden", !isFinished);
        if (!isFinished) return;

        const playerWon = game.playerSide && game.playerSide === game.winnerSide;
        document.getElementById("pong-result-kicker").textContent = playerWon ? "Gewonnen" : "Spiel beendet";
        document.getElementById("pong-result-title").textContent = playerWon ? "Du hast gewonnen!" : `${game.winnerName || "Ein Spieler"} hat gewonnen`;
        document.getElementById("pong-result-text").textContent = `${game.score.left}:${game.score.right} · Beste Rally: ${game.bestRally || 0}`;
    }

    function loop(now) {
        const dt = Math.min((now - lastFrame) / 1000, 0.05);
        lastFrame = now;
        handleKeyboard(dt);
        simulateClient(dt);
        draw();
        requestAnimationFrame(loop);
    }

    function handleKeyboard(dt) {
        if (!game?.playerSide) return;

        const speed = 82;
        if (keys.has("KeyW") || keys.has("ArrowUp")) desiredY -= speed * dt;
        if (keys.has("KeyS") || keys.has("ArrowDown")) desiredY += speed * dt;
        desiredY = clamp(desiredY, 10, 90);

        if (keys.size) {
            applyLocalPaddle();
            sendPaddleRealtime();
        }
    }

    function applyLocalPaddle() {
        if (renderState?.paddles && game?.playerSide) {
            renderState.paddles[game.playerSide] = desiredY;
        }
    }

    function simulateClient(dt) {
        if (!renderState || renderState.status !== "playing") return;

        const age = performance.now() - lastServerStateAt;
        if (age > 300) return;

        renderState.ball.x += renderState.ball.vx * dt;
        renderState.ball.y += renderState.ball.vy * dt;

        if (renderState.ball.y <= 1.7 || renderState.ball.y >= 98.3) {
            renderState.ball.vy *= -1;
        }

        if (targetBall) {
            const correction = age < 90 ? 0.10 : 0.18;
            renderState.ball.x = smooth(renderState.ball.x, targetBall.x, correction);
            renderState.ball.y = smooth(renderState.ball.y, targetBall.y, correction);
            renderState.ball.vx = smooth(renderState.ball.vx, targetBall.vx, 0.16);
            renderState.ball.vy = smooth(renderState.ball.vy, targetBall.vy, 0.16);
        }

        renderState.ball.x = clamp(renderState.ball.x, -3, 103);
        renderState.ball.y = clamp(renderState.ball.y, 1.7, 98.3);
    }

    function draw() {
        if (!ctx) return;

        const w = canvas.width;
        const h = canvas.height;
        ctx.clearRect(0, 0, w, h);

        const grd = ctx.createLinearGradient(0, 0, w, h);
        grd.addColorStop(0, "#020617");
        grd.addColorStop(0.55, "#0f172a");
        grd.addColorStop(1, "#082f49");
        ctx.fillStyle = grd;
        ctx.fillRect(0, 0, w, h);

        ctx.strokeStyle = "rgba(255,255,255,.18)";
        ctx.lineWidth = 2;
        ctx.strokeRect(10, 10, w - 20, h - 20);

        ctx.setLineDash([12, 14]);
        ctx.beginPath();
        ctx.moveTo(w / 2, 16);
        ctx.lineTo(w / 2, h - 16);
        ctx.stroke();
        ctx.setLineDash([]);

        ctx.fillStyle = "rgba(255,255,255,.06)";
        ctx.font = `900 ${Math.max(42, w * 0.11)}px system-ui`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";

        if (renderState?.score) {
            ctx.fillText(renderState.score.left, w * 0.36, h * 0.18);
            ctx.fillText(renderState.score.right, w * 0.64, h * 0.18);
        }

        const state = renderState || game;
        if (!state) {
            drawCentered("Verbinde mit Pong...");
            return;
        }

        drawPaddle(5, state.paddles.left, "#22d3ee");
        drawPaddle(95, state.paddles.right, "#a78bfa");
        drawBall(state.ball.x, state.ball.y);

        if (state.status === "waiting") {
            drawCentered("Warte auf zweiten Spieler");
        }
    }

    function drawPaddle(xPct, yPct, color) {
        const x = pctX(xPct);
        const y = pctY(yPct);
        const pw = Math.max(10, canvas.width * 0.012);
        const ph = canvas.height * 0.20;
        ctx.fillStyle = color;
        ctx.shadowColor = color;
        ctx.shadowBlur = 18;
        roundRect(x - pw / 2, y - ph / 2, pw, ph, 999);
        ctx.shadowBlur = 0;
    }

    function drawBall(xPct, yPct) {
        const r = Math.max(8, canvas.width * 0.012);
        ctx.fillStyle = "#fef3c7";
        ctx.shadowColor = "#fef3c7";
        ctx.shadowBlur = 24;
        ctx.beginPath();
        ctx.arc(pctX(xPct), pctY(yPct), r, 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowBlur = 0;
    }

    function drawCentered(text) {
        ctx.fillStyle = "rgba(255,255,255,.82)";
        ctx.font = `800 ${Math.max(18, canvas.width * 0.032)}px system-ui`;
        ctx.textAlign = "center";
        ctx.fillText(text, canvas.width / 2, canvas.height / 2);
    }

    function pctX(v) { return (v / 100) * canvas.width; }
    function pctY(v) { return (v / 100) * canvas.height; }

    function roundRect(x, y, w, h, r) {
        ctx.beginPath();
        ctx.roundRect(x, y, w, h, r);
        ctx.fill();
    }

    function resizeCanvas() {
        const ratio = window.devicePixelRatio || 1;
        const rect = canvas.getBoundingClientRect();
        canvas.width = Math.max(360, Math.floor(rect.width * ratio));
        canvas.height = Math.max(260, Math.floor(rect.height * ratio));
    }


    function cloneGame(value) {
        if (typeof structuredClone === "function") return structuredClone(value);
        return JSON.parse(JSON.stringify(value));
    }

    function smooth(current, target, factor) {
        return current + (target - current) * factor;
    }

    function distance(x1 = 0, y1 = 0, x2 = 0, y2 = 0) {
        return Math.hypot(x2 - x1, y2 - y1);
    }

    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(";").shift();
        return "";
    }

    function clamp(value, min, max) {
        return Math.max(min, Math.min(max, value));
    }

    function showToast(message) {
        let toast = document.querySelector(".pong-toast");
        if (!toast) {
            toast = document.createElement("div");
            toast.className = "pong-toast";
            document.body.appendChild(toast);
        }
        toast.textContent = message;
        clearTimeout(toast.timer);
        toast.timer = setTimeout(() => toast.remove(), 2200);
    }

    function handleDeletedGame(payload) {
        showToast(payload.error || "Dieser Raum wurde gelöscht.");
        window.setTimeout(() => {
            window.location.href = payload.redirectUrl || "/pong/";
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
                const response = await fetch(stateUrl, {headers: {"X-Requested-With": "XMLHttpRequest"}});
                const json = await response.json();
                if (!json.ok) return;

                const signature = JSON.stringify({games: json.games, invites: json.invites});
                if (signature === lastSignature) return;

                lastSignature = signature;
                renderHomeInvites(json.invites || []);
                renderHomeGames(json.games || []);
            } catch (error) {
                console.warn("Pong home state failed", error);
            }
        }

        function renderHomeInvites(invites) {
            const container = document.getElementById("pong-invites-live");
            if (!container) return;

            if (!invites.length) {
                container.innerHTML = `<p class="pong-muted" id="pong-invites-empty">${escapeHtml(labels.emptyInvites)}</p>`;
                return;
            }

            container.innerHTML = `<div class="pong-invite-list" id="pong-invite-list">${invites.map((invite) => `
                <div class="pong-invite-row">
                    <div>
                        <strong>${escapeHtml(invite.gameName)}</strong>
                        <span>${escapeHtml(labels.from)} ${escapeHtml(invite.fromUser)}</span>
                    </div>
                    <div class="pong-inline-actions">
                        ${inviteForm(invite.acceptUrl, "accept", labels.accept, "pong-primary")}
                        ${inviteForm(invite.declineUrl, "decline", labels.decline, "pong-secondary")}
                    </div>
                </div>`).join("")}</div>`;
        }

        function renderHomeGames(games) {
            const container = document.getElementById("pong-games-live");
            if (!container) return;

            if (!games.length) {
                container.innerHTML = `<p class="pong-muted" id="pong-games-empty">${escapeHtml(labels.emptyGames)}</p>`;
                return;
            }

            container.innerHTML = `<div class="pong-room-grid" id="pong-room-grid">${games.map((game) => `
                <a class="pong-room-card" href="${escapeHtml(game.url)}">
                    <span class="pong-code">${escapeHtml(game.code)}</span>
                    <strong>${escapeHtml(game.name)}</strong>
                    <span>${escapeHtml(game.statusLabel)} · ${escapeHtml(labels.round)} ${escapeHtml(String(game.roundNumber))}</span>
                </a>`).join("")}</div>`;
        }

        function inviteForm(url, action, label, className) {
            return `<form method="post" action="${escapeHtml(url)}">
                <input type="hidden" name="csrfmiddlewaretoken" value="${escapeHtml(csrfToken)}">
                <input type="hidden" name="action" value="${escapeHtml(action)}">
                <button class="${className}" type="submit">${escapeHtml(label)}</button>
            </form>`;
        }

        function escapeHtml(value) {
            const div = document.createElement("div");
            div.textContent = value ?? "";
            return div.innerHTML;
        }
    }
});
