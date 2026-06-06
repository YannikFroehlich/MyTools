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
    let liveStroke = null;
    let liveStrokeFlushTimer = null;
    let drawSendTimer = null;
    let drawSendInFlight = false;
    let drawSendPromise = Promise.resolve();
    let segmentSequence = 0;
    let pendingSegments = [];
    let localCanvasSegments = [];
    let localCanvasDirty = false;
    let lastDrawingSignature = "";
    let drawingRevision = 0;
    let drawingSession = 0;
    let currentTurnKey = "";
    let stateRefreshTimer = null;
    let stateRefreshInFlight = false;
    let stateRequestSequence = 0;
    let latestRenderedStateRequest = 0;

    initCanvas();
    bindEvents();
    refreshState(true).finally(() => scheduleStateRefresh(80));

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
            if (!state?.lobby?.isOwner) return;
            await post(urls.start);
            await refreshState(true);
        });

        document.getElementById("restart-game-btn")?.addEventListener("click", async () => {
            if (!state?.lobby?.isOwner) return;
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
            await drainSegmentQueue();
            resetLocalDrawingState();
            clearCanvas();
            drawingRevision = 0;
            const result = await post(urls.draw, {action: "clear"});
            const revision = Number(result.drawingRevision);
            if (Number.isFinite(revision)) {
                drawingRevision = revision;
            }
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
            if (canDraw() && localCanvasDirty) {
                redrawLocalCanvas();
            } else {
                drawAll(state?.drawing || []);
            }
        };

        scaleCanvas();
        window.addEventListener("resize", scaleCanvas);

        canvas.addEventListener("pointerdown", (event) => {
            if (!canDraw()) return;
            event.preventDefault();
            const point = pointFromEvent(event);
            isDrawing = true;
            liveStroke = {
                id: `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`,
                points: [point],
                color: brushColor.value,
                size: Number(brushSize.value),
                lastSentIndex: 0,
                chunkIndex: 0,
            };
            currentPoints = liveStroke.points;
            localCanvasDirty = true;
            canvas.setPointerCapture(event.pointerId);
        });

        canvas.addEventListener("pointermove", (event) => {
            if (!isDrawing || !canDraw()) return;
            event.preventDefault();
            const events = typeof event.getCoalescedEvents === "function" ? event.getCoalescedEvents() : [event];
            events.forEach((moveEvent) => appendLivePoint(pointFromEvent(moveEvent)));
            scheduleLiveStrokeFlush();
            if (liveStroke && liveStroke.points.length - liveStroke.lastSentIndex >= 6) {
                flushLiveStroke(false);
            }
        });

        canvas.addEventListener("pointerup", finishStroke);
        canvas.addEventListener("pointercancel", finishStroke);
        canvas.addEventListener("lostpointercapture", finishStroke);
        window.addEventListener("pointerup", finishStroke);
        window.addEventListener("blur", () => {
            if (isDrawing) finishStroke();
        });
    }

    function scheduleLiveStrokeFlush(delay = 35) {
        if (liveStrokeFlushTimer) return;
        liveStrokeFlushTimer = window.setTimeout(() => {
            liveStrokeFlushTimer = null;
            flushLiveStroke(false);
        }, delay);
    }

    function scheduleDrawUpload(delay = 10) {
        if (drawSendTimer) return;
        drawSendTimer = window.setTimeout(() => {
            drawSendTimer = null;
            drainSegmentQueue();
        }, delay);
    }

    function appendLivePoint(point) {
        if (!liveStroke) return;
        const previous = liveStroke.points[liveStroke.points.length - 1];
        if (!previous || distanceBetween(previous, point) < 0.25) return;
        liveStroke.points.push(point);
        currentPoints = liveStroke.points;
        drawSegment(previous, point, liveStroke.color, liveStroke.size);
    }

    function flushLiveStroke(force = false) {
        if (!liveStroke) return;
        if (force && liveStroke.points.length < 2) {
            const dotPoint = liveStroke.points[0];
            if (dotPoint) {
                appendLivePoint({x: dotPoint.x + 0.6, y: dotPoint.y + 0.6});
            }
        }

        const startIndex = Math.max(0, liveStroke.lastSentIndex - 1);
        const points = liveStroke.points.slice(startIndex);
        if (points.length < 2) return;

        const chunk = {
            id: `${liveStroke.id}-${String(liveStroke.chunkIndex).padStart(4, "0")}`,
            order: ++segmentSequence,
            points: serializePoints(points),
            color: liveStroke.color,
            size: liveStroke.size,
        };
        liveStroke.chunkIndex += 1;
        liveStroke.lastSentIndex = liveStroke.points.length;
        pendingSegments.push(chunk);
        localCanvasSegments.push(chunk);
        localCanvasDirty = true;

        if (pendingSegments.length >= 8) {
            drainSegmentQueue();
        } else {
            scheduleDrawUpload();
        }
    }

    async function drainSegmentQueue() {
        window.clearTimeout(drawSendTimer);
        drawSendTimer = null;
        if (drawSendInFlight) return drawSendPromise;

        drawSendInFlight = true;
        const session = drawingSession;
        drawSendPromise = (async () => {
            try {
                while (pendingSegments.length > 0) {
                    const batch = pendingSegments.splice(0, 24);
                    let result;
                    try {
                        result = await post(urls.draw, {
                            action: "segments",
                            segments: JSON.stringify(batch),
                        });
                    } catch (error) {
                        console.warn("Skribble draw upload failed", error);
                        pendingSegments = batch.concat(pendingSegments);
                        break;
                    }
                    if (session !== drawingSession) {
                        break;
                    }
                    if (!result.ok) {
                        pendingSegments = batch.concat(pendingSegments);
                        break;
                    }
                    const revision = Number(result.drawingRevision);
                    if (Number.isFinite(revision)) {
                        drawingRevision = Math.max(drawingRevision, revision);
                    }
                }
            } finally {
                drawSendInFlight = false;
                if (pendingSegments.length > 0 && canDraw()) {
                    scheduleDrawUpload(session === drawingSession ? 120 : 0);
                }
            }
        })();
        return drawSendPromise;
    }

    async function finishStroke(event) {
        if (!isDrawing) {
            return;
        }

        if (canDraw() && event?.clientX != null) {
            appendLivePoint(pointFromEvent(event));
        }

        if (!liveStroke || liveStroke.points.length < 1) {
            isDrawing = false;
            currentPoints = [];
            liveStroke = null;
            return;
        }

        isDrawing = false;
        window.clearTimeout(liveStrokeFlushTimer);
        liveStrokeFlushTimer = null;
        flushLiveStroke(true);
        liveStroke = null;
        window.clearTimeout(drawSendTimer);
        drawSendTimer = null;
        currentPoints = [];
        await drainSegmentQueue();
        // Drawer already has the stroke on canvas locally — no need for a full redraw.
        // Viewers will pick it up via the delta mechanism on their next poll.
        await refreshState(false);
    }

    function resetLocalDrawingState() {
        drawingSession += 1;
        isDrawing = false;
        currentPoints = [];
        liveStroke = null;
        pendingSegments = [];
        localCanvasSegments = [];
        localCanvasDirty = false;
        segmentSequence = 0;
        window.clearTimeout(liveStrokeFlushTimer);
        liveStrokeFlushTimer = null;
        window.clearTimeout(drawSendTimer);
        drawSendTimer = null;
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

    function currentDrawingTurnKey(nextState = state) {
        const lobby = nextState?.lobby || {};
        return [
            lobby.round || 0,
            lobby.currentDrawerId || "",
            lobby.hasWord ? (lobby.word || lobby.maskedWord || "word") : "no-word",
        ].join(":");
    }

    function statePollDelay() {
        if (state?.lobby?.status !== "playing") return 500;
        if (canDraw()) return localCanvasDirty || drawSendInFlight || pendingSegments.length > 0 ? 260 : 180;
        return 120;
    }

    function scheduleStateRefresh(delay = statePollDelay()) {
        window.clearTimeout(stateRefreshTimer);
        stateRefreshTimer = window.setTimeout(async () => {
            await refreshState(false);
            scheduleStateRefresh();
        }, delay);
    }

    async function refreshState(forceDraw = false) {
        if (stateRefreshInFlight && !forceDraw) return;
        stateRefreshInFlight = true;
        const requestId = ++stateRequestSequence;
        try {
            const after = forceDraw ? 0 : drawingRevision;
            const separator = urls.state.includes("?") ? "&" : "?";
            const response = await fetch(`${urls.state}${separator}after=${encodeURIComponent(after)}`, {
                cache: "no-store",
                headers: {"X-Requested-With": "XMLHttpRequest"},
            });
            const json = await response.json();
            if (json.lobbyDeleted) {
                handleDeletedLobby(json);
                return;
            }
            if (!json.ok) return;
            if (requestId < latestRenderedStateRequest) return;
            latestRenderedStateRequest = requestId;
            state = json.state;
            renderState(forceDraw);
        } catch (error) {
            console.warn("Skribble state failed", error);
        } finally {
            stateRefreshInFlight = false;
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
        syncHostControls();

        const drawing = state.drawing || [];
        const delta = state.drawingDelta || [];
        const nextRevision = Number(state.drawingRevision || 0);
        const nextTurnKey = currentDrawingTurnKey(state);
        if (nextTurnKey !== currentTurnKey) {
            resetLocalDrawingState();
            currentTurnKey = nextTurnKey;
            drawingRevision = nextRevision;
            drawAll(drawing);
            segmentSequence = maxSegmentOrder(drawing);
            if (canDraw()) {
                localCanvasSegments = drawing.slice();
                localCanvasDirty = false;
            }
            lastDrawingSignature = `${nextRevision}:turn`;
            return;
        }

        if (canDraw() && localCanvasDirty && !forceDraw && nextRevision >= drawingRevision) {
            drawingRevision = Math.max(drawingRevision, nextRevision);
            return;
        }

        if (!isDrawing) {
            if (forceDraw || nextRevision < drawingRevision || (drawing.length > 0 && drawingRevision === 0)) {
                // Full redraw: forced, revision went backwards (clear), or initial load
                drawAll(drawing);
                segmentSequence = maxSegmentOrder(drawing);
                if (canDraw()) {
                    localCanvasSegments = drawing.slice();
                    localCanvasDirty = false;
                }
                drawingRevision = nextRevision;
                lastDrawingSignature = `${nextRevision}:full`;
            } else if (delta.length > 0 && nextRevision > drawingRevision) {
                // Incremental: only paint new strokes
                drawStrokes(delta);
                if (canDraw()) {
                    localCanvasSegments = localCanvasSegments.concat(delta);
                    segmentSequence = Math.max(segmentSequence, maxSegmentOrder(delta));
                }
                drawingRevision = nextRevision;
                lastDrawingSignature = `${nextRevision}:delta`;
            } else if (nextRevision !== drawingRevision) {
                drawingRevision = nextRevision;
            }
        }
    }

    function syncHostControls() {
        const isOwner = Boolean(state?.lobby?.isOwner);
        document.getElementById("start-game-btn")?.toggleAttribute("disabled", !isOwner || state?.lobby?.status !== "waiting");
        document.getElementById("restart-game-btn")?.toggleAttribute("disabled", !isOwner);
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

    function redrawLocalCanvas() {
        drawAll(localCanvasSegments);
        if (liveStroke?.points?.length > 1) {
            drawStrokes([{
                points: serializePoints(liveStroke.points),
                color: liveStroke.color,
                size: liveStroke.size,
            }]);
        }
    }

    function maxSegmentOrder(strokes) {
        return strokes.reduce((maxOrder, stroke) => {
            const order = Number(stroke.order || 0);
            return Number.isFinite(order) ? Math.max(maxOrder, order) : maxOrder;
        }, 0);
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
