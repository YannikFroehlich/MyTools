document.addEventListener("DOMContentLoaded", () => {
    const homeRoot = document.querySelector(".hm-home-page");
    if (homeRoot) {
        initHomePage(homeRoot);
    }

    const root = document.querySelector(".hm-lobby-page");
    if (!root) return;

    const urls = {
        state: root.dataset.stateUrl,
        start: root.dataset.startUrl,
        guess: root.dataset.guessUrl,
        reset: root.dataset.resetUrl,
    };

    const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÜ".split("");
    const csrfToken = getCookie("csrftoken");
    const keyboard = document.getElementById("hm-keyboard");
    const guessForm = document.getElementById("hm-guess-form");
    const guessInput = document.getElementById("hm-guess-input");
    let game = null;
    let isPosting = false;

    bindEvents();
    renderKeyboard();
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

        document.getElementById("hm-copy-link")?.addEventListener("click", async () => {
            await navigator.clipboard?.writeText(window.location.href);
            showToast("Link kopiert");
        });

        document.getElementById("hm-start")?.addEventListener("click", async () => {
            if (isPosting || !game?.isOwner) return;
            await post(urls.start);
        });

        document.getElementById("hm-reset")?.addEventListener("click", async () => {
            if (isPosting || !game?.isOwner) return;
            await post(urls.reset);
        });

        document.getElementById("hm-result-reset")?.addEventListener("click", async () => {
            if (isPosting || !game?.isOwner) return;
            await post(urls.reset);
        });

        guessForm?.addEventListener("submit", async (event) => {
            event.preventDefault();
            if (!game?.canGuess || isPosting) return;
            const guess = guessInput.value.trim();
            if (!guess) return;
            await post(urls.guess, {guess});
            guessInput.value = "";
            guessInput.focus();
        });

        keyboard?.addEventListener("click", async (event) => {
            const button = event.target.closest(".hm-key");
            if (!button || button.disabled || !game?.canGuess || isPosting) return;
            await post(urls.guess, {guess: button.dataset.letter});
            guessInput?.focus();
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
            console.warn("Hangman state failed", error);
        }
    }

    async function post(url, data = {}) {
        isPosting = true;
        syncControls();
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
            syncControls();
        }
    }

    function render() {
        if (!game) return;

        setText("hm-status", game.statusLabel || "-");
        setText("hm-message", game.message || "-");
        setText("hm-round", game.roundNumber ?? "-");
        setText("hm-mistakes", `${game.mistakes ?? 0}/${game.maxMistakes ?? 8}`);
        setText("hm-hint", game.hint || "Kein Hinweis");
        setText("hm-guessed", formatLetters(game.guessedLetters));
        setText("hm-wrong", formatLetters(game.wrongLetters));
        setText("hm-player-count", String((game.players || []).length));

        renderPlayers();
        renderWord();
        renderDrawing();
        renderKeyboard();
        renderLastGuess();
        renderResultOverlay();
        syncControls();
    }

    function renderPlayers() {
        const list = document.getElementById("hm-player-list");
        if (!list) return;

        const players = game.players || [];
        if (!players.length) {
            list.innerHTML = `<p class="hm-muted">Keine Spieler im Raum.</p>`;
            return;
        }

        list.innerHTML = players.map((player) => `
            <div class="hm-player-row ${player.isOwner ? "is-owner" : ""}">
                <div>
                    <strong class="hm-player-name">${escapeHtml(player.name)}</strong>
                    <small>${player.isOwner ? "Host" : "Spieler"}</small>
                </div>
                <span class="hm-player-score">${Number(player.score || 0)} P</span>
            </div>
        `).join("");
    }

    function renderWord() {
        const wordElement = document.getElementById("hm-word");
        if (!wordElement) return;

        const masked = game.maskedWord || [];
        if (!masked.length) {
            wordElement.innerHTML = `<span class="hm-letter-tile is-empty">?</span>`;
            return;
        }

        wordElement.innerHTML = masked.map((char) => {
            if (char === " ") return `<span class="hm-letter-tile is-space"></span>`;
            if (char === "-") return `<span class="hm-letter-tile">-</span>`;
            if (char === "_") return `<span class="hm-letter-tile is-empty">_</span>`;
            return `<span class="hm-letter-tile">${escapeHtml(char)}</span>`;
        }).join("");
    }

    function renderDrawing() {
        const mistakes = Number(game.mistakes || 0);
        document.querySelectorAll(".hm-body-part").forEach((part) => {
            const index = Number(part.dataset.part || 0);
            part.classList.toggle("is-visible", index < mistakes);
        });
    }

    function renderKeyboard() {
        if (!keyboard) return;
        const guessed = new Set((game?.guessedLetters || []).map((letter) => String(letter).toUpperCase()));
        const wrong = new Set((game?.wrongLetters || []).map((letter) => String(letter).toUpperCase()).filter((letter) => letter.length === 1));
        const disabled = isPosting || !game?.canGuess;

        keyboard.innerHTML = alphabet.map((letter) => {
            const isCorrect = guessed.has(letter);
            const isWrong = wrong.has(letter);
            const classes = ["hm-key", isCorrect ? "is-correct" : "", isWrong ? "is-wrong" : ""].filter(Boolean).join(" ");
            return `<button class="${classes}" type="button" data-letter="${letter}" ${(disabled || isCorrect || isWrong) ? "disabled" : ""}>${letter}</button>`;
        }).join("");
    }

    function renderLastGuess() {
        const element = document.getElementById("hm-last-guess");
        if (!element) return;

        const last = game.lastGuess || {};
        element.classList.remove("is-correct", "is-wrong");
        if (!last.player) {
            element.textContent = "";
            return;
        }

        element.classList.add(last.correct ? "is-correct" : "is-wrong");
        if (last.correct) {
            element.textContent = `${last.player}: ${last.guess} war richtig (+${last.points || 0} Punkte)`;
        } else {
            element.textContent = `${last.player}: ${last.guess} war falsch`;
        }
    }

    function renderResultOverlay() {
        const overlay = document.getElementById("hm-result-overlay");
        const title = document.getElementById("hm-result-title");
        const text = document.getElementById("hm-result-text");
        if (!overlay || !title || !text) return;

        const finished = game.status === "finished";
        overlay.classList.toggle("hidden", !finished);
        if (!finished) return;

        if (game.winnerName) {
            title.textContent = `${game.winnerName} hat gewonnen`;
            text.textContent = `Das Wort war: ${game.word || "-"}`;
        } else {
            title.textContent = "Nicht geschafft";
            text.textContent = `Das gesuchte Wort war: ${game.word || "-"}`;
        }
    }

    function syncControls() {
        const ownerDisabled = isPosting || !game?.isOwner;
        document.getElementById("hm-start")?.toggleAttribute("disabled", ownerDisabled || game?.status === "playing");
        document.getElementById("hm-reset")?.toggleAttribute("disabled", ownerDisabled);
        document.getElementById("hm-result-reset")?.toggleAttribute("disabled", ownerDisabled);

        const guessDisabled = isPosting || !game?.canGuess;
        if (guessInput) guessInput.disabled = guessDisabled;
        guessForm?.querySelector("button[type='submit']")?.toggleAttribute("disabled", guessDisabled);
        renderKeyboard();
    }

    function formatLetters(values) {
        const letters = values || [];
        return letters.length ? letters.join(", ") : "-";
    }

    function setText(id, value) {
        const element = document.getElementById(id);
        if (element) element.textContent = value;
    }

    function handleDeletedGame(payload) {
        showToast(payload.error || "Dieser Raum wurde gelöscht.");
        window.setTimeout(() => {
            window.location.href = payload.redirectUrl || "/hangman/";
        }, 900);
    }
});

function initHomePage(rootElement) {
    const stateUrl = rootElement.dataset.homeStateUrl;
    if (!stateUrl) return;

    const csrfToken = getCookie("csrftoken");
    const labels = {
        emptyInvites: rootElement.dataset.emptyInvitesLabel || "Du hast aktuell keine offenen Hangman-Einladungen.",
        emptyGames: rootElement.dataset.emptyGamesLabel || "Du hast noch keinen Hangman-Raum.",
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
            console.warn("Hangman home state failed", error);
        }
    }

    function renderHomeInvites(invites) {
        const container = document.getElementById("hm-invites-live");
        if (!container) return;

        if (!invites.length) {
            container.innerHTML = `<p class="hm-muted" id="hm-invites-empty">${escapeHtml(labels.emptyInvites)}</p>`;
            return;
        }

        container.innerHTML = `
            <div class="hm-invite-list" id="hm-invite-list">
                ${invites.map(invite => `
                    <div class="hm-invite-row">
                        <div>
                            <strong>${escapeHtml(invite.gameName)}</strong>
                            <span>${escapeHtml(labels.from)} ${escapeHtml(invite.fromUser)}</span>
                        </div>
                        <div class="hm-inline-actions">
                            <form method="post" action="${escapeAttr(invite.acceptUrl)}">
                                <input type="hidden" name="csrfmiddlewaretoken" value="${escapeAttr(csrfToken)}">
                                <input type="hidden" name="action" value="accept">
                                <button class="hm-primary" type="submit">${escapeHtml(labels.accept)}</button>
                            </form>
                            <form method="post" action="${escapeAttr(invite.declineUrl)}">
                                <input type="hidden" name="csrfmiddlewaretoken" value="${escapeAttr(csrfToken)}">
                                <input type="hidden" name="action" value="decline">
                                <button class="hm-secondary" type="submit">${escapeHtml(labels.decline)}</button>
                            </form>
                        </div>
                    </div>
                `).join("")}
            </div>
        `;
    }

    function renderHomeGames(games) {
        const container = document.getElementById("hm-games-live");
        if (!container) return;

        if (!games.length) {
            container.innerHTML = `<p class="hm-muted" id="hm-games-empty">${escapeHtml(labels.emptyGames)}</p>`;
            return;
        }

        container.innerHTML = `
            <div class="hm-room-grid" id="hm-room-grid">
                ${games.map(game => `
                    <a class="hm-room-card" href="${escapeAttr(game.url)}">
                        <span class="hm-code">${escapeHtml(game.code)}</span>
                        <strong>${escapeHtml(game.name)}</strong>
                        <span>${escapeHtml(game.statusLabel)} · ${escapeHtml(labels.round)} ${escapeHtml(String(game.roundNumber))}</span>
                    </a>
                `).join("")}
            </div>
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
    let toast = document.querySelector(".hm-toast");
    if (!toast) {
        toast = document.createElement("div");
        toast.className = "hm-toast";
        document.body.appendChild(toast);
    }
    toast.textContent = message;
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => toast.remove(), 2200);
}

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function escapeAttr(value) {
    return escapeHtml(value);
}
