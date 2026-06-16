document.addEventListener("DOMContentLoaded", () => {
    const homeRoot = document.querySelector(".uno-home-page");
    if (homeRoot) initHomePage(homeRoot);

    const root = document.querySelector(".uno-lobby-page");
    if (!root) return;

    const urls = {
        state: root.dataset.stateUrl,
        start: root.dataset.startUrl,
        play: root.dataset.playUrl,
        draw: root.dataset.drawUrl,
        pass: root.dataset.passUrl,
        call: root.dataset.callUrl,
        catch: root.dataset.catchUrl,
        reset: root.dataset.resetUrl,
    };
    const csrfToken = getCookie("csrftoken");
    let game = null;
    let isPosting = false;
    let isRefreshing = false;
    let pendingCard = null;
    let chosenColor = "";
    let targetUserId = "";
    let lastTopCardId = "";
    let dismissedWinnerKey = "";
    let previousCardCounts = new Map();
    let audioContext = null;
    let soundEnabled = window.localStorage.getItem("unoSound") !== "off";
    let audioUnlocked = false;

    bindEvents();
    bindSoundEvents();
    refreshState(true);
    setInterval(() => refreshState(false), 1500);

    function bindEvents() {
        document.querySelectorAll("form[data-confirm]").forEach((form) => {
            form.addEventListener("submit", (event) => {
                if (!window.confirm(form.dataset.confirm || "Wirklich löschen?")) {
                    event.preventDefault();
                }
            });
        });
        document.getElementById("uno-copy-link")?.addEventListener("click", async () => {
            await navigator.clipboard?.writeText(window.location.href);
            showToast("Link kopiert");
        });
        document.getElementById("uno-start")?.addEventListener("click", () => post(urls.start));
        document.getElementById("uno-reset")?.addEventListener("click", () => post(urls.reset));
        document.getElementById("uno-draw-pile")?.addEventListener("click", () => post(urls.draw));
        document.getElementById("uno-call")?.addEventListener("click", () => post(urls.call));
        document.getElementById("uno-winner-close")?.addEventListener("click", () => {
            dismissedWinnerKey = winnerKey();
            hideWinnerModal();
        });

        document.querySelectorAll("#uno-color-picker button").forEach((button) => {
            button.addEventListener("click", () => {
                chosenColor = button.dataset.color;
                document.querySelectorAll("#uno-color-picker button").forEach((item) => item.classList.toggle("is-selected", item === button));
                maybeSubmitPendingCard();
            });
        });
    }

    function bindSoundEvents() {
        updateSoundButton();

        const bindAction = (selector, handler) => {
            document.getElementById(selector)?.addEventListener("click", (event) => {
                event.stopImmediatePropagation();
                unlockAudio();
                handler();
            }, true);
        };

        bindAction("uno-sound-toggle", () => {
            soundEnabled = !soundEnabled;
            window.localStorage.setItem("unoSound", soundEnabled ? "on" : "off");
            playSound(soundEnabled ? "toggleOn" : "toggleOff");
            updateSoundButton();
        });
        bindAction("uno-copy-link", async () => {
            await navigator.clipboard?.writeText(window.location.href);
            playSound("click");
            showToast("Link kopiert");
        });
        bindAction("uno-start", () => post(urls.start, {}, "start"));
        bindAction("uno-reset", () => post(urls.reset, {}, "start"));
        bindAction("uno-draw-pile", () => post(urls.draw, {}, "draw"));
        bindAction("uno-call", () => post(urls.call, {}, "uno"));

        document.querySelectorAll("#uno-color-picker button").forEach((button) => {
            button.addEventListener("click", (event) => {
                event.stopImmediatePropagation();
                unlockAudio();
                chosenColor = button.dataset.color;
                document.querySelectorAll("#uno-color-picker button").forEach((item) => item.classList.toggle("is-selected", item === button));
                playSound("click");
                maybeSubmitPendingCard();
            }, true);
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
            if (json.ok) {
                const signatureChanged = JSON.stringify(game) !== JSON.stringify(json.game);
                game = json.game;
                if (force || signatureChanged) render();
            }
        } catch (error) {
            console.warn("Uno state failed", error);
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
                console.warn("Uno action returned non-JSON", response.status, rawBody.slice(0, 200));
            }

            if (!response.ok || !json.ok) {
                playSound("error");
                showToast(json.error || `Aktion fehlgeschlagen (${response.status})`);
                return;
            }
            nextGame = json.game;
            if (soundType) playSound(soundType);
            pendingCard = null;
            chosenColor = "";
            targetUserId = "";
        } finally {
            isPosting = false;
            if (nextGame) {
                game = nextGame;
                render();
            }
        }
    }

    function render() {
        document.getElementById("uno-status").textContent = game.statusLabel;
        document.getElementById("uno-message").textContent = game.message;
        document.getElementById("uno-round").textContent = game.roundNumber;
        document.getElementById("uno-direction").textContent = game.direction === 1 ? "\u21bb" : "\u21ba";
        document.getElementById("uno-deck-count").textContent = game.deckCount;
        document.getElementById("uno-deck-count-large").textContent = game.deckCount;

        const arena = document.getElementById("uno-arena");
        if (arena) {
            arena.dataset.color = game.currentColor || "";
            arena.classList.toggle("is-your-turn", Boolean(game.canAct));
            arena.classList.toggle("is-waiting", game.status === "waiting");
            arena.classList.toggle("is-finished", game.status === "finished");
        }

        const colorBadge = document.getElementById("uno-current-color");
        colorBadge.textContent = game.pendingDraw ? `${game.currentColorLabel} - +${game.pendingDraw}` : game.currentColorLabel;
        colorBadge.dataset.color = game.currentColor || "";

        document.getElementById("uno-start").disabled = isPosting || !game.canStart;
        document.getElementById("uno-reset").disabled = isPosting || !game.isOwner || game.players.length < 2;
        const drawPile = document.getElementById("uno-draw-pile");
        if (drawPile) {
            drawPile.disabled = isPosting || !game.canAct || game.status !== "playing";
            drawPile.classList.toggle("is-clickable", !drawPile.disabled);
        }
        document.getElementById("uno-call").disabled = isPosting || !game.canCallUno;

        renderPlayers();
        renderTablePlayers();
        renderRules();
        renderTopCard();
        renderHand();
        renderLog();
        renderPickers();
        renderWinnerModal();
    }

    function renderWinnerModal() {
        const modal = document.getElementById("uno-winner-modal");
        const name = document.getElementById("uno-winner-name");
        if (!modal || !name) return;

        const key = winnerKey();
        const shouldShow = game.status === "finished" && game.winnerName && key !== dismissedWinnerKey;
        name.textContent = game.winnerName || "-";
        modal.classList.toggle("hidden", !shouldShow);
        if (shouldShow) playSound("winner");
    }

    function hideWinnerModal() {
        document.getElementById("uno-winner-modal")?.classList.add("hidden");
    }

    function winnerKey() {
        if (!game) return "";
        return `${game.id || ""}:${game.roundNumber || ""}:${game.winnerUserId || ""}`;
    }

    function renderPlayers() {
        const list = document.getElementById("uno-player-list");
        list.innerHTML = game.players.map((player) => `
            <div class="uno-player-row ${player.isCurrent ? "is-current" : ""}">
                ${avatarMarkup(player, "uno-player-avatar")}
                <div>
                    <strong>${escapeHtml(player.name)}${player.isYou ? " - Du" : ""}</strong>
                    <small>${player.cardCount} Karten${player.saidUno ? " - Uno" : ""}</small>
                </div>
                ${player.cardCount === 1 && !player.saidUno && !player.isYou ? `<button type="button" class="uno-catch-button" data-user-id="${player.id}">+2</button>` : ""}
            </div>
        `).join("");
        list.querySelectorAll(".uno-catch-button").forEach((button) => {
            button.addEventListener("click", () => post(urls.catch, {target_user_id: button.dataset.userId}, "draw"));
        });
    }

    function renderTablePlayers() {
        const tablePlayers = document.getElementById("uno-table-players");
        if (!tablePlayers) return;

        const players = orderedForTable(game.players || []);
        const count = Math.max(players.length, 1);
        tablePlayers.innerHTML = players.map((player, index) => {
            const previousCount = previousCardCounts.get(player.id);
            const countChanged = previousCount !== undefined && previousCount !== player.cardCount;
            const countWentUp = countChanged && player.cardCount > previousCount;
            return `
                <div class="uno-seat uno-seat-${count}-${index} ${player.isCurrent ? "is-current" : ""} ${player.isYou ? "is-you" : ""} ${countChanged ? "is-count-changed" : ""} ${countWentUp ? "is-drawing" : "is-playing"}" data-user-id="${player.id}">
                    <div class="uno-seat-label">
                        ${avatarMarkup(player, "uno-seat-avatar")}
                        <div>
                            <strong>${escapeHtml(player.isYou ? "Du" : player.name)}</strong>
                            <small>${player.cardCount} Karten${player.saidUno ? " - Uno" : ""}</small>
                        </div>
                        ${player.cardCount === 1 && !player.saidUno && !player.isYou ? `<button type="button" class="uno-catch-button" data-user-id="${player.id}">+2</button>` : ""}
                    </div>
                    ${player.isYou ? "" : `<div class="uno-seat-hand" aria-hidden="true">${cardBacksForCount(player.cardCount)}</div>`}
                </div>
            `;
        }).join("");
        tablePlayers.querySelectorAll(".uno-catch-button").forEach((button) => {
            button.addEventListener("click", () => post(urls.catch, {target_user_id: button.dataset.userId}, "draw"));
        });

        previousCardCounts = new Map((game.players || []).map((player) => [player.id, player.cardCount]));
    }

    function avatarMarkup(player, className) {
        const initials = player.initials || (player.name || "?").slice(0, 2).toUpperCase();
        if (player.avatarUrl) {
            return `<span class="${className} has-image"><img src="${escapeHtml(player.avatarUrl)}" alt="${escapeHtml(player.name)}"></span>`;
        }
        return `<span class="${className}">${escapeHtml(initials)}</span>`;
    }

    function orderedForTable(players) {
        if (!players.length) return [];
        const youIndex = players.findIndex((player) => player.isYou);
        if (youIndex < 0) return players.slice();
        return players.slice(youIndex).concat(players.slice(0, youIndex));
    }

    function cardBacksForCount(count) {
        const visible = Math.min(Math.max(count, 0), 7);
        return Array.from({length: visible}, (_unused, index) => {
            const offset = index - ((visible - 1) / 2);
            return `<span class="uno-card-back" style="--card-shift:${offset * 11}px;--card-rotate:${offset * 6}deg;"></span>`;
        }).join("");
    }

    function renderRules() {
        const rules = [
            ["+2/+4 automatisch", true],
            ["Jump-In", game.rules.jumpIn],
            ["7-0", game.rules.sevenZero],
            ["Ziehen bis spielbar", game.rules.drawUntilPlayable],
            ["Gezogene Karte muss raus", game.rules.forcePlayDrawnCard],
            ["+4 Challenge", game.rules.keepBluffChallenge],
        ];
        document.getElementById("uno-rule-pills").innerHTML = rules
            .filter(([, enabled]) => enabled)
            .map(([label]) => `<span>${escapeHtml(label)}</span>`)
            .join("") || `<span>Standardregeln</span>`;
    }

    function renderTopCard() {
        const slot = document.getElementById("uno-top-card-slot");
        const topCardId = game.topCard?.id || "";
        const didChange = lastTopCardId && topCardId && topCardId !== lastTopCardId;
        slot.innerHTML = game.topCard?.id ? cardMarkup(game.topCard, `uno-card is-large ${didChange ? "is-just-played" : ""}`) : "";
        if (didChange) {
            const arena = document.getElementById("uno-arena");
            const pile = document.getElementById("uno-draw-pile");
            arena?.classList.remove("is-card-played");
            pile?.classList.remove("is-pulse");
            window.requestAnimationFrame(() => {
                arena?.classList.add("is-card-played");
                pile?.classList.add("is-pulse");
            });
            playSound("card");
        }
        lastTopCardId = topCardId;
    }

    function renderHand() {
        const hand = document.getElementById("uno-hand");
        if (!game.hand.length) {
            hand.innerHTML = `<p class="uno-muted">Keine Karten auf der Hand.</p>`;
            return;
        }
        const total = game.hand.length;
        hand.innerHTML = game.hand.map((card, index) => {
            const playable = game.playableIds.includes(card.id);
            const spread = index - ((total - 1) / 2);
            const tilt = Math.max(-18, Math.min(18, spread * 2.8));
            return `
                <button type="button"
                        class="uno-hand-card ${playable ? "is-playable" : ""}"
                        data-card-id="${escapeHtml(card.id)}"
                        style="--hand-index:${index};--hand-total:${total};--hand-tilt:${tilt}deg;"
                        aria-label="${escapeHtml(card.label)}${playable ? " spielen" : ""}">
                    ${cardMarkup(card, "uno-card")}
                </button>
            `;
        }).join("");
        hand.querySelectorAll(".uno-hand-card").forEach((button) => {
            button.addEventListener("click", () => {
                const card = game.hand.find((item) => item.id === button.dataset.cardId);
                if (!card || !game.playableIds.includes(card.id)) return;
                pendingCard = card;
                chosenColor = "";
                targetUserId = "";
                renderPickers();
                maybeSubmitPendingCard();
            });
        });
    }

    function renderPickers() {
        const colorPicker = document.getElementById("uno-color-picker");
        const targetPicker = document.getElementById("uno-target-picker");
        const needsColor = pendingCard && pendingCard.color === "wild";
        const needsTarget = pendingCard && pendingCard.value === "7" && game.rules.sevenZero && game.players.length > 1;
        colorPicker.classList.toggle("hidden", !needsColor);
        targetPicker.classList.toggle("hidden", !needsTarget);
        document.querySelectorAll("#uno-color-picker button").forEach((button) => button.classList.toggle("is-selected", button.dataset.color === chosenColor));

        const targetList = document.getElementById("uno-target-list");
        targetList.innerHTML = game.players
            .filter((player) => !player.isYou)
            .map((player) => `<button type="button" data-user-id="${player.id}" class="${String(player.id) === String(targetUserId) ? "is-selected" : ""}">${escapeHtml(player.name)}</button>`)
            .join("");
        targetList.querySelectorAll("button").forEach((button) => {
            button.addEventListener("click", () => {
                targetUserId = button.dataset.userId;
                renderPickers();
                maybeSubmitPendingCard();
            });
        });
    }

    function maybeSubmitPendingCard() {
        if (!pendingCard) return;
        if (pendingCard.color === "wild" && !chosenColor) return;
        if (pendingCard.value === "7" && game.rules.sevenZero && game.players.length > 1 && !targetUserId) return;
        post(urls.play, {card_id: pendingCard.id, color: chosenColor, target_user_id: targetUserId}, "card");
    }

    function renderLog() {
        document.getElementById("uno-log").innerHTML = (game.actionLog || [])
            .slice()
            .reverse()
            .map((entry) => `<span>${escapeHtml(entry)}</span>`)
            .join("");
    }

    function cardMarkup(card, className) {
        const value = cardValueMarkup(card);
        const cornerValue = cardCornerValue(card);
        return `
            <span class="${className}" data-color="${escapeHtml(card.color)}" data-value="${escapeHtml(card.value)}" data-type="${escapeHtml(card.type || "")}">
                <span class="uno-card-corner uno-card-corner-top">${cornerValue}</span>
                <strong class="uno-card-face">${value}</strong>
                <span class="uno-card-corner uno-card-corner-bottom">${cornerValue}</span>
            </span>
        `;
    }

    function cardCornerValue(card) {
        if (card.value === "skip") return "\u2298";
        if (card.value === "reverse") return "\u21ba";
        if (card.value === "draw2") return "+2";
        if (card.value === "wild4") return "+4";
        if (card.value === "wild") return "W";
        return escapeHtml(card.label);
    }

    function cardValueMarkup(card) {
        if (card.value === "skip") return `<span class="uno-action-symbol" aria-label="Aussetzen">\u2298</span>`;
        if (card.value === "reverse") return `<span class="uno-action-symbol" aria-label="Richtungswechsel">\u21bb</span>`;
        if (card.value === "draw2") return `<span class="uno-action-symbol" aria-label="Zieh zwei">+2</span>`;
        if (card.value === "wild4") return `<span class="uno-action-symbol" aria-label="Zieh vier">+4</span>`;
        if (card.value === "wild") return `<span class="uno-action-symbol" aria-label="Farbwahl">Wunsch</span>`;
        return escapeHtml(card.label);
    }

    function updateSoundButton() {
        const button = document.getElementById("uno-sound-toggle");
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
            click: [[420, 0.025, "triangle", 0], [620, 0.035, "triangle", 0.025]],
            card: [[260, 0.035, "triangle", 0], [520, 0.055, "square", 0.025], [780, 0.04, "triangle", 0.065]],
            draw: [[150, 0.04, "sawtooth", 0], [210, 0.05, "triangle", 0.045]],
            pass: [[240, 0.03, "sine", 0], [180, 0.04, "sine", 0.035]],
            start: [[196, 0.05, "triangle", 0], [392, 0.06, "triangle", 0.045], [784, 0.08, "triangle", 0.095]],
            uno: [[440, 0.08, "square", 0], [660, 0.10, "square", 0.08], [880, 0.12, "triangle", 0.17]],
            winner: [[330, 0.08, "triangle", 0], [494, 0.10, "triangle", 0.08], [659, 0.12, "triangle", 0.17], [988, 0.16, "square", 0.28]],
            error: [[180, 0.08, "sawtooth", 0], [120, 0.10, "sawtooth", 0.08]],
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
        gain.gain.exponentialRampToValueAtTime(0.12, start + 0.01);
        gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);
        oscillator.connect(gain);
        gain.connect(audioContext.destination);
        oscillator.start(start);
        oscillator.stop(start + duration + 0.025);
    }

    function handleDeletedGame(payload) {
        showToast(payload.error || "Dieser Raum wurde gelöscht.");
        window.setTimeout(() => {
            window.location.href = payload.redirectUrl || "/uno/";
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
                const response = await fetch(stateUrl, {headers: {"X-Requested-With": "XMLHttpRequest"}});
                const json = await response.json();
                if (!json.ok) return;
                const signature = JSON.stringify({games: json.games, invites: json.invites});
                if (signature === lastSignature) return;
                lastSignature = signature;
                renderHomeInvites(json.invites || []);
                renderHomeGames(json.games || []);
            } catch (error) {
                console.warn("Uno home state failed", error);
            }
        }

        function renderHomeInvites(invites) {
            const container = document.getElementById("uno-invites-live");
            if (!container) return;
            if (!invites.length) {
                container.innerHTML = `<p class="uno-muted" id="uno-invites-empty">${escapeHtml(labels.emptyInvites)}</p>`;
                return;
            }
            container.innerHTML = `
                <div class="uno-invite-list" id="uno-invite-list">
                    ${invites.map(invite => `
                        <div class="uno-invite-row">
                            <div>
                                <strong>${escapeHtml(invite.gameName)}</strong>
                                <span>${escapeHtml(labels.from)} ${escapeHtml(invite.fromUser)}</span>
                            </div>
                            <div class="uno-inline-actions">
                                ${inviteForm(invite.acceptUrl, "accept", labels.accept, "uno-primary")}
                                ${inviteForm(invite.declineUrl, "decline", labels.decline, "uno-secondary")}
                            </div>
                        </div>
                    `).join("")}
                </div>
            `;
        }

        function renderHomeGames(games) {
            const container = document.getElementById("uno-games-live");
            if (!container) return;
            if (!games.length) {
                container.innerHTML = `<p class="uno-muted" id="uno-games-empty">${escapeHtml(labels.emptyGames)}</p>`;
                return;
            }
            container.innerHTML = `
                <div class="uno-room-grid" id="uno-room-grid">
                    ${games.map(game => `
                        <a class="uno-room-card" href="${escapeHtml(game.url)}">
                            <span class="uno-code">${escapeHtml(game.code)}</span>
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
        let toast = document.querySelector(".uno-toast");
        if (!toast) {
            toast = document.createElement("div");
            toast.className = "uno-toast";
            document.body.appendChild(toast);
        }
        toast.textContent = message;
        clearTimeout(toast.timer);
        toast.timer = setTimeout(() => toast.remove(), 2200);
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
