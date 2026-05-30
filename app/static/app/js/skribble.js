document.addEventListener("DOMContentLoaded", () => {
    const root = document.querySelector(".draw-lobby-page");
    if (!root) return;

    const urls = {
        state: root.dataset.stateUrl,
        start: root.dataset.startUrl,
        restart: root.dataset.restartUrl,
        continueRound: root.dataset.continueUrl,
        choose: root.dataset.chooseUrl,
        draw: root.dataset.drawUrl,
        guess: root.dataset.guessUrl,
        invite: root.dataset.inviteUrl,
    };

    const csrfToken = getCookie("csrftoken");
    const canvas = document.getElementById("drawing-canvas");
    const ctx = canvas.getContext("2d");
    const blocker = document.getElementById("canvas-blocker");
    const brushColor = document.getElementById("brush-color");
    const brushSize = document.getElementById("brush-size");
    const clearBtn = document.getElementById("clear-canvas-btn");
    const guessForm = document.getElementById("guess-form");
    const guessInput = document.getElementById("guess-input");
    const roundSummary = document.getElementById("round-summary");
    const continueRoundBtn = document.getElementById("continue-round-btn");
    const logicalCanvasSize = {width: 1280, height: 760};

    let state = null;
    let isDrawing = false;
    let currentPoints = [];
    let drawSendTimer = null;
    let drawSendInFlight = false;
    let drawSendPromise = Promise.resolve();
    let segmentSequence = 0;
    let pendingSegments = [];
    let lastDrawingSignature = "";
    let drawingRevision = 0;

    initCanvas();
    bindEvents();
    refreshState();
    setInterval(refreshState, 100);

    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(";").shift();
        return "";
    }

    async function post(url, data = {}) {
        const formData = new FormData();
        Object.entries(data).forEach(([key, value]) => formData.append(key, value));
        const response = await fetch(url, {
            method: "POST",
            headers: {"X-CSRFToken": csrfToken},
            body: formData,
        });
        const json = await response.json().catch(() => ({ok: false}));
        if (json.lobbyDeleted) {
            handleDeletedLobby(json);
            return json;
        }
        if (!response.ok || !json.ok) {
            if (json.error) showToast(json.error);
            return json;
        }
        return json;
    }

    function bindEvents() {
        document.querySelectorAll(".draw-inline-form[data-confirm]").forEach((form) => {
            form.addEventListener("submit", (event) => {
                const message = form.dataset.confirm || "Wirklich ausführen?";
                if (!window.confirm(message)) {
                    event.preventDefault();
                }
            });
        });

        document.getElementById("start-game-btn")?.addEventListener("click", async () => {
            await post(urls.start);
            await refreshState(true);
        });

        document.getElementById("restart-game-btn")?.addEventListener("click", async () => {
            await post(urls.restart);
            await refreshState(true);
        });

        continueRoundBtn?.addEventListener("click", async () => {
            await post(urls.continueRound);
            await refreshState(true);
        });

        document.getElementById("copy-lobby-link")?.addEventListener("click", async () => {
            await navigator.clipboard?.writeText(window.location.href);
            showToast("Lobby-Link kopiert");
        });

        document.querySelectorAll("#brush-palette [data-color]").forEach((button) => {
            button.addEventListener("click", () => {
                brushColor.value = button.dataset.color;
                setActiveBrushButton(button.dataset.color);
            });
        });

        brushColor?.addEventListener("input", () => setActiveBrushButton(brushColor.value));

        clearBtn?.addEventListener("click", async () => {
            if (!canDraw()) return;
            clearCanvas();
            currentPoints = [];
            pendingSegments = [];
            window.clearTimeout(drawSendTimer);
            drawSendTimer = null;
            drawingRevision = 0;
            await post(urls.draw, {action: "clear"});
            await refreshState(true);
        });

        guessForm?.addEventListener("submit", async (event) => {
            event.preventDefault();
            const message = guessInput.value.trim();
            if (!message) return;
            guessInput.value = "";
            await post(urls.guess, {message});
            await refreshState(true);
        });
    }

    function initCanvas() {
        const scaleCanvas = () => {
            const rect = canvas.getBoundingClientRect();
            const ratio = window.devicePixelRatio || 1;
            canvas.width = Math.round(rect.width * ratio);
            canvas.height = Math.round(rect.height * ratio);
            ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
            drawAll(state?.drawing || []);
        };

        scaleCanvas();
        window.addEventListener("resize", scaleCanvas);

        canvas.addEventListener("pointerdown", (event) => {
            if (!canDraw()) return;
            isDrawing = true;
            currentPoints = [pointFromEvent(event)];
            canvas.setPointerCapture(event.pointerId);
        });

        canvas.addEventListener("pointermove", (event) => {
            if (!isDrawing || !canDraw()) return;
            const point = pointFromEvent(event);
            const previous = currentPoints[currentPoints.length - 1];
            currentPoints.push(point);
            drawSegment(previous, point, brushColor.value, Number(brushSize.value));
            queueSegment(previous, point);
        });

        canvas.addEventListener("pointerup", finishStroke);
        canvas.addEventListener("pointercancel", finishStroke);
    }

    function scheduleStrokeFlush(delay = 16) {
        if (drawSendTimer) return;
        drawSendTimer = window.setTimeout(() => {
            drawSendTimer = null;
            drainSegmentQueue();
        }, delay);
    }

    function queueSegment(from, to) {
        pendingSegments.push({
            id: `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`,
            order: ++segmentSequence,
            points: serializePoints([from, to]),
            color: brushColor.value,
            size: brushSize.value,
        });

        if (pendingSegments.length >= 6) {
            drainSegmentQueue();
        } else {
            scheduleStrokeFlush();
        }
    }

    async function drainSegmentQueue() {
        window.clearTimeout(drawSendTimer);
        drawSendTimer = null;
        if (drawSendInFlight) return drawSendPromise;

        drawSendInFlight = true;
        drawSendPromise = (async () => {
            try {
                while (pendingSegments.length > 0) {
                    const batch = pendingSegments.splice(0, 24);
                    const result = await post(urls.draw, {
                        action: "segments",
                        segments: JSON.stringify(batch),
                    });
                    if (!result.ok) {
                        pendingSegments = batch.concat(pendingSegments);
                        break;
                    }
                }
            } finally {
                drawSendInFlight = false;
            }
        })();
        return drawSendPromise;
    }

    async function finishStroke(event) {
        if (!isDrawing) {
            return;
        }

        if (canDraw() && event?.clientX != null) {
            const releasePoint = pointFromEvent(event);
            const previous = currentPoints[currentPoints.length - 1];
            if (!previous || distanceBetween(previous, releasePoint) > 0.4) {
                currentPoints.push(releasePoint);
                if (previous) {
                    drawSegment(previous, releasePoint, brushColor.value, Number(brushSize.value));
                    queueSegment(previous, releasePoint);
                }
            }
        }

        if (currentPoints.length < 2) {
            const dotPoint = currentPoints[0];
            if (dotPoint) {
                currentPoints = [dotPoint, {x: dotPoint.x + 0.6, y: dotPoint.y + 0.6}];
                drawSegment(currentPoints[0], currentPoints[1], brushColor.value, Number(brushSize.value));
                queueSegment(currentPoints[0], currentPoints[1]);
            }
        }

        if (currentPoints.length < 2) {
            isDrawing = false;
            currentPoints = [];
            return;
        }

        isDrawing = false;
        window.clearTimeout(drawSendTimer);
        drawSendTimer = null;
        currentPoints = [];
        await drainSegmentQueue();
        await refreshState(true);
    }

    function serializePoints(points) {
        return points.map(point => `${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(";");
    }

    function distanceBetween(a, b) {
        return Math.hypot((a?.x || 0) - (b?.x || 0), (a?.y || 0) - (b?.y || 0));
    }

    function pointFromEvent(event) {
        const rect = canvas.getBoundingClientRect();
        return {
            x: ((event.clientX - rect.left) / rect.width) * logicalCanvasSize.width,
            y: ((event.clientY - rect.top) / rect.height) * logicalCanvasSize.height,
        };
    }

    function canDraw() {
        return state?.me?.isDrawer && state?.lobby?.status === "playing" && Boolean(state?.lobby?.word);
    }

    async function refreshState(forceDraw = false) {
        try {
            const after = forceDraw ? 0 : drawingRevision;
            const separator = urls.state.includes("?") ? "&" : "?";
            const response = await fetch(`${urls.state}${separator}after=${encodeURIComponent(after)}`, {
                headers: {"X-Requested-With": "XMLHttpRequest"},
            });
            const json = await response.json();
            if (json.lobbyDeleted) {
                handleDeletedLobby(json);
                return;
            }
            if (!json.ok) return;
            state = json.state;
            renderState(forceDraw);
        } catch (error) {
            console.warn("Skribble state failed", error);
        }
    }

    function renderState(forceDraw = false) {
        document.getElementById("game-status").textContent = labelStatus(state.lobby.status);
        document.getElementById("round-info").textContent = `Runde ${state.lobby.round} / ${state.lobby.rounds}`;
        document.getElementById("drawer-name").textContent = state.lobby.currentDrawerName || "-";
        document.getElementById("timer-display").textContent = state.lobby.secondsLeft ?? "--";

        const wordDisplay = document.getElementById("word-display");
        wordDisplay.textContent = state.lobby.word || state.lobby.maskedWord || "-";
        wordDisplay.classList.toggle("is-mask", !state.lobby.word && Boolean(state.lobby.maskedWord));
        renderWordChoices();
        renderPlayers();
        renderFriendInvites();
        renderGuesses();
        renderRoundSummary();
        renderCanvasBlocker();

        const drawing = state.drawing || [];
        const delta = state.drawingDelta || [];
        const nextRevision = Number(state.drawingRevision || 0);

        if (!isDrawing && (forceDraw || drawing.length > 0 || nextRevision < drawingRevision)) {
            drawAll(drawing);
            drawingRevision = nextRevision;
            lastDrawingSignature = `${nextRevision}:full`;
        } else if (!isDrawing && delta.length > 0) {
            drawStrokes(delta);
            drawingRevision = nextRevision;
            lastDrawingSignature = `${nextRevision}:delta`;
        } else if (nextRevision !== drawingRevision && !isDrawing) {
            drawingRevision = nextRevision;
        }
    }

    function labelStatus(status) {
        if (status === "waiting") return "Wartet";
        if (status === "playing") return "Läuft";
        if (status === "round_summary") return "Rundenuebersicht";
        if (status === "finished") return "Beendet";
        return status;
    }

    function renderWordChoices() {
        const container = document.getElementById("word-choices");
        container.innerHTML = "";
        (state.lobby.wordChoices || []).forEach((word) => {
            const button = document.createElement("button");
            button.className = "draw-word-choice";
            button.type = "button";
            button.textContent = word;
            button.addEventListener("click", async () => {
                await post(urls.choose, {word});
                await refreshState(true);
            });
            container.appendChild(button);
        });
    }

    function renderPlayers() {
        const list = document.getElementById("players-list");
        list.innerHTML = "";
        state.players.forEach((player) => {
            const item = document.createElement("div");
            item.className = "draw-player";
            const initials = player.name.split(/\s+/).map(part => part[0]).join("").slice(0, 2).toUpperCase();
            item.innerHTML = `
                <div class="draw-player-avatar" data-base="${escapeHtml(player.avatarBase)}" data-initials="${escapeHtml(initials)}" style="--avatar-color: ${escapeHtml(player.avatarColor)}; --accent-color: ${escapeHtml(player.accentColor)}"></div>
                <div class="draw-player-info">
                    <strong>${escapeHtml(player.name)} ${player.isDrawer ? "✏️" : ""}</strong>
                    <small>${player.hasGuessed ? "Wort erraten" : "im Spiel"}</small>
                </div>
                <div class="draw-player-score">${player.score}</div>
            `;
            list.appendChild(item);
        });
    }

    function renderFriendInvites() {
        const list = document.getElementById("friend-invite-list");
        const empty = document.getElementById("friend-invite-empty");
        if (!list) return;

        const rows = state.friendInvites || [];
        list.innerHTML = "";
        empty?.classList.toggle("hidden", rows.length > 0);

        rows.forEach((friend) => {
            const item = document.createElement("div");
            item.className = "draw-friend-invite-row";
            const status = friend.isInvited ? "Einladung offen" : (friend.wasInvited ? "War schon eingeladen" : "Freund");
            const disabled = friend.isInvited ? "disabled" : "";
            const label = friend.isInvited ? "Eingeladen" : "Einladen";
            const buttonContent = friend.isInvited ? '<i class="fa-solid fa-check"></i>' : '<span aria-hidden="true">+</span>';
            item.innerHTML = `
                <div class="draw-friend-mini">
                    <div class="draw-friend-avatar">${escapeHtml(friend.initial || "?")}</div>
                    <div>
                        <strong>${escapeHtml(friend.name)}</strong>
                        <span>${escapeHtml(status)}</span>
                    </div>
                </div>
                <form method="post" action="${escapeHtml(urls.invite)}">
                    <input type="hidden" name="csrfmiddlewaretoken" value="${escapeHtml(csrfToken)}">
                    <input type="hidden" name="friend_id" value="${escapeHtml(friend.id)}">
                    <button class="draw-primary draw-invite-one" type="submit" aria-label="${escapeHtml(label)}" ${disabled}>${buttonContent}</button>
                </form>
            `;
            list.appendChild(item);
        });
    }

    function renderGuesses() {
        const list = document.getElementById("guess-list");
        const shouldStick = list.scrollTop + list.clientHeight >= list.scrollHeight - 32;
        list.innerHTML = "";
        state.guesses.forEach((guess) => {
            const item = document.createElement("div");
            item.className = `draw-guess ${guess.isCorrect ? "correct" : ""}`;
            item.innerHTML = `<strong>${escapeHtml(guess.user)}:</strong> ${escapeHtml(guess.message)}`;
            list.appendChild(item);
        });
        if (shouldStick) list.scrollTop = list.scrollHeight;
    }

    function renderRoundSummary() {
        if (!roundSummary) return;
        const summary = state.lobby.roundSummary || {};
        const isVisible = state.lobby.status === "round_summary" && Array.isArray(summary.rows);
        roundSummary.classList.toggle("hidden", !isVisible);
        if (!isVisible) return;

        const title = document.getElementById("round-summary-title");
        const word = document.getElementById("round-summary-word");
        const list = document.getElementById("round-summary-list");
        const wait = document.getElementById("round-summary-wait");
        title.textContent = summary.isGameOver ? "Spielauswertung" : `Runde ${summary.round} / ${summary.rounds}`;
        word.textContent = summary.word ? `Wort: ${summary.word}` : "";
        list.innerHTML = "";

        summary.rows.forEach((row, index) => {
            const delta = Number(row.points || 0);
            const item = document.createElement("div");
            item.className = "draw-round-summary-row";
            item.innerHTML = `
                <span class="draw-round-summary-rank">#${index + 1}</span>
                <strong>${escapeHtml(row.name)}${row.isDrawer ? " · Zeichner" : ""}</strong>
                <span class="draw-round-summary-points">${delta > 0 ? "+" : ""}${delta}</span>
                <span class="draw-round-summary-total">${escapeHtml(row.score)} gesamt</span>
            `;
            list.appendChild(item);
        });

        continueRoundBtn.hidden = !state.lobby.isOwner;
        continueRoundBtn.querySelector("span").textContent = summary.isGameOver ? "Spiel beenden" : "Naechste Runde";
        wait.hidden = state.lobby.isOwner;
    }

    function renderCanvasBlocker() {
        if (state.lobby.status === "round_summary") {
            blocker.classList.add("hidden");
            return;
        }
        if (canDraw() || (state.lobby.status === "playing" && (state.lobby.hasWord || state.lobby.maskedWord))) {
            blocker.classList.add("hidden");
        } else {
            blocker.classList.remove("hidden");
            const title = blocker.querySelector("strong");
            const text = blocker.querySelector("span");
            if (state.lobby.status === "finished") {
                title.textContent = "Spiel beendet";
                text.textContent = "Der Host kann die Lobby zurücksetzen und eine neue Runde starten.";
            } else if (state.lobby.status === "waiting") {
                title.textContent = "Warte auf den Start";
                text.textContent = "Der Host startet das Spiel, sobald genug Spieler da sind.";
            } else if (state.me.isDrawer) {
                title.textContent = "Wähle ein Wort";
                text.textContent = "Danach kannst du direkt zeichnen.";
            } else {
                title.textContent = "Der Zeichner wählt ein Wort";
                text.textContent = "Gleich geht es los.";
            }
        }
    }

    function setActiveBrushButton(color) {
        const normalized = String(color || "").toLowerCase();
        document.querySelectorAll("#brush-palette [data-color]").forEach((button) => {
            button.classList.toggle("active", button.dataset.color.toLowerCase() === normalized);
        });
    }

    function drawAll(strokes) {
        clearCanvas();
        drawStrokes(strokes);
    }

    function drawStrokes(strokes) {
        strokes.forEach((stroke) => {
            const points = parsePoints(stroke.points);
            for (let i = 1; i < points.length; i++) {
                drawSegment(points[i - 1], points[i], stroke.color, Number(stroke.size));
            }
        });
    }

    function clearCanvas() {
        const rect = canvas.getBoundingClientRect();
        ctx.clearRect(0, 0, rect.width, rect.height);
        ctx.fillStyle = "#ffffff";
        ctx.fillRect(0, 0, rect.width, rect.height);
    }

    function drawSegment(from, to, color, size) {
        const fromPoint = logicalToCanvasPoint(from);
        const toPoint = logicalToCanvasPoint(to);
        const scale = brushScale();

        ctx.lineCap = "round";
        ctx.lineJoin = "round";
        ctx.strokeStyle = color || "#111827";
        ctx.lineWidth = (size || 6) * scale;
        ctx.beginPath();
        ctx.moveTo(fromPoint.x, fromPoint.y);
        ctx.lineTo(toPoint.x, toPoint.y);
        ctx.stroke();
    }

    function logicalToCanvasPoint(point) {
        const rect = canvas.getBoundingClientRect();
        return {
            x: (point.x / logicalCanvasSize.width) * rect.width,
            y: (point.y / logicalCanvasSize.height) * rect.height,
        };
    }

    function brushScale() {
        const rect = canvas.getBoundingClientRect();
        return ((rect.width / logicalCanvasSize.width) + (rect.height / logicalCanvasSize.height)) / 2;
    }

    function parsePoints(value) {
        return String(value || "").split(";").map(pair => {
            const [x, y] = pair.split(",").map(Number);
            return {x, y};
        }).filter(point => Number.isFinite(point.x) && Number.isFinite(point.y));
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
        let toast = document.querySelector(".draw-toast");
        if (!toast) {
            toast = document.createElement("div");
            toast.className = "draw-toast";
            Object.assign(toast.style, {
                position: "fixed",
                right: "18px",
                bottom: "18px",
                zIndex: "9999",
                background: "rgba(15,23,42,.94)",
                color: "white",
                border: "1px solid rgba(255,255,255,.14)",
                borderRadius: "16px",
                padding: "12px 16px",
                boxShadow: "0 18px 45px rgba(0,0,0,.28)",
                fontWeight: "800",
            });
            document.body.appendChild(toast);
        }
        toast.textContent = message;
        clearTimeout(toast.timer);
        toast.timer = setTimeout(() => toast.remove(), 2200);
    }

    function handleDeletedLobby(payload) {
        showToast(payload.error || "Diese Lobby wurde geloescht.");
        window.setTimeout(() => {
            window.location.href = payload.redirectUrl || "/skribble/";
        }, 900);
    }
});
