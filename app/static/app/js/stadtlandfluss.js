document.addEventListener("DOMContentLoaded", () => {
    initHomePage();
    initLobbyPage();
});

function initHomePage() {
    const root = document.querySelector(".slf-home-page");
    if (!root) return;

    const stateUrl = root.dataset.homeStateUrl;
    const csrfToken = getCookie("csrftoken");

    refreshHomeState();
    setInterval(refreshHomeState, 3000);
    window.addEventListener("focus", refreshHomeState);

    async function refreshHomeState() {
        if (!stateUrl || document.hidden) return;
        try {
            const response = await fetch(stateUrl, {
                headers: {"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
                cache: "no-store",
            });
            const json = await response.json();
            if (!json.ok) return;
            renderInviteList(json.invites || []);
            renderLobbyList("slf-discover-list", "slf-discover-empty", json.discoverLobbies || [], true);
            renderLobbyList("slf-my-lobbies-list", "slf-my-lobbies-empty", json.myLobbies || [], false);
        } catch (error) {
            console.warn("Stadt Land Fluss home state failed", error);
        }
    }

    function renderInviteList(invites) {
        const list = document.getElementById("slf-invite-list");
        const empty = document.getElementById("slf-invite-empty");
        if (!list || !empty) return;
        list.classList.toggle("hidden", invites.length === 0);
        empty.classList.toggle("hidden", invites.length > 0);
        list.innerHTML = invites.map((invite) => `
            <div class="slf-list-item">
                <div>
                    <strong>${escapeHtml(invite.lobbyName)}</strong>
                    <span>von ${escapeHtml(invite.fromUser)}</span>
                </div>
                <div class="slf-actions-inline">
                    <form method="post" action="${escapeHtml(invite.acceptUrl)}">
                        <input type="hidden" name="csrfmiddlewaretoken" value="${escapeHtml(csrfToken)}">
                        <input type="hidden" name="action" value="accept">
                        <button class="slf-small slf-accept" type="submit">Annehmen</button>
                    </form>
                    <form method="post" action="${escapeHtml(invite.declineUrl)}">
                        <input type="hidden" name="csrfmiddlewaretoken" value="${escapeHtml(csrfToken)}">
                        <input type="hidden" name="action" value="decline">
                        <button class="slf-small" type="submit">Ablehnen</button>
                    </form>
                </div>
            </div>
        `).join("");
    }

    function renderLobbyList(listId, emptyId, lobbies, showOwner) {
        const list = document.getElementById(listId);
        const empty = document.getElementById(emptyId);
        if (!list || !empty) return;
        list.classList.toggle("hidden", lobbies.length === 0);
        empty.classList.toggle("hidden", lobbies.length > 0);
        list.innerHTML = lobbies.map((lobby) => `
            <a href="${escapeHtml(lobby.url)}" class="slf-lobby-card">
                <span class="slf-status">${escapeHtml(lobby.statusLabel)}</span>
                <strong>${escapeHtml(lobby.name)}</strong>
                <span>${showOwner ? `@${escapeHtml(lobby.owner)}` : `${escapeHtml(lobby.code)} · ${escapeHtml(lobby.statusLabel)}`}</span>
                <div>
                    <small><i class="fa-solid fa-users"></i> ${lobby.playersCount} / ${lobby.maxPlayers}</small>
                    <small><i class="fa-solid fa-rotate"></i> ${lobby.rounds}</small>
                    <small><i class="fa-solid fa-clock"></i> ${lobby.seconds}s</small>
                </div>
            </a>
        `).join("");
    }

    function escapeHtml(value) {
        return escapeHtmlGlobal(value);
    }
}

function initLobbyPage() {
    const root = document.querySelector(".slf-lobby-page");
    if (!root) return;

    const urls = {
        state: root.dataset.stateUrl,
        start: root.dataset.startUrl,
        draft: root.dataset.draftUrl,
        submit: root.dataset.submitUrl,
        vote: root.dataset.voteUrl,
        continueRound: root.dataset.continueUrl,
        restart: root.dataset.restartUrl,
        invite: root.dataset.inviteUrl,
    };
    const csrfToken = getCookie("csrftoken");
    let state = null;
    let lastAnswerRound = null;
    let draftTimer = null;

    bindEvents();
    refreshState(true);
    setInterval(refreshState, 1000);

    function bindEvents() {
        document.querySelectorAll(".slf-inline-form[data-confirm]").forEach((form) => {
            form.addEventListener("submit", (event) => {
                if (!window.confirm(form.dataset.confirm || "Wirklich ausführen?")) {
                    event.preventDefault();
                }
            });
        });

        document.getElementById("copy-lobby-link")?.addEventListener("click", async () => {
            await navigator.clipboard?.writeText(window.location.href);
            showToast("Lobby-Link kopiert");
        });

        document.getElementById("start-game-btn")?.addEventListener("click", async () => {
            await post(urls.start);
            await refreshState(true);
        });

        document.getElementById("restart-game-btn")?.addEventListener("click", async () => {
            await post(urls.restart);
            lastAnswerRound = null;
            await refreshState(true);
        });

        document.getElementById("continue-round-btn")?.addEventListener("click", async () => {
            await post(urls.continueRound);
            await refreshState(true);
        });

        document.getElementById("summary-table")?.addEventListener("click", async (event) => {
            const button = event.target.closest("[data-vote]");
            if (!button || !state || state.status !== "round_summary") return;
            await post(urls.vote, {
                category: button.dataset.category,
                player_id: button.dataset.playerId,
                accepted: button.dataset.vote,
            });
            await refreshState(true);
        });

        document.getElementById("answers-form")?.addEventListener("submit", async (event) => {
            event.preventDefault();
            if (!state || state.status !== "playing" || state.me.isSubmitted) return;
            clearTimeout(draftTimer);
            await post(urls.submit, collectAnswers());
            await refreshState(true);
        });

        document.getElementById("answers-grid")?.addEventListener("input", () => {
            if (!state || state.status !== "playing" || state.me.isSubmitted) return;
            clearTimeout(draftTimer);
            draftTimer = setTimeout(async () => {
                await post(urls.draft, collectAnswers());
            }, 450);
        });

        document.getElementById("friend-invite-list")?.addEventListener("submit", async (event) => {
            const form = event.target.closest("form");
            if (!form) return;
            event.preventDefault();
            await post(form.action, Object.fromEntries(new FormData(form).entries()));
            await refreshState(true);
            showToast("Einladung wurde gesendet");
        });
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
            showToast(json.error || "Aktion fehlgeschlagen");
        }
        return json;
    }

    function collectAnswers() {
        const formData = {};
        (state?.categories || []).forEach((category, index) => {
            formData[`answer_${index}`] = document.getElementById(`answer-${index}`)?.value || "";
        });
        return formData;
    }

    async function refreshState(force = false) {
        try {
            const response = await fetch(urls.state, {headers: {"X-Requested-With": "XMLHttpRequest"}});
            const json = await response.json();
            if (json.lobbyDeleted) {
                handleDeletedLobby(json);
                return;
            }
            if (!json.ok) return;
            state = json.state;
            renderState(force);
        } catch (error) {
            console.warn("Stadt Land Fluss state failed", error);
        }
    }

    function renderState(force = false) {
        document.getElementById("game-status").textContent = labelStatus(state.status);
        document.getElementById("round-info").textContent = `${state.round || 0} / ${state.rounds}`;
        document.getElementById("letter-display").textContent = state.letter || "-";
        document.getElementById("timer-display").textContent = state.secondsLeft ?? "--";

        renderPlayers();
        renderFriendInvites();
        renderAnswers(force);
        renderPanels();
        renderSummary();

        document.getElementById("start-game-btn")?.toggleAttribute("disabled", state.status !== "waiting" && state.status !== "finished");
    }

    function labelStatus(status) {
        if (status === "waiting") return "Wartet";
        if (status === "playing") return "Läuft";
        if (status === "round_summary") return "Auswertung";
        if (status === "finished") return "Beendet";
        return status || "-";
    }

    function renderPlayers() {
        const list = document.getElementById("players-list");
        list.innerHTML = "";
        state.players.forEach((player, index) => {
            const item = document.createElement("div");
            item.className = `slf-player ${player.submitted ? "is-submitted" : ""}`;
            item.innerHTML = `
                <div class="slf-player-rank">#${index + 1}</div>
                <div>
                    <strong>${escapeHtml(player.name)}${player.isOwner ? ' <i class="fa-solid fa-crown"></i>' : ""}</strong>
                    <small>${player.submitted ? "abgegeben" : (state.status === "playing" ? "schreibt" : "bereit")}</small>
                </div>
                <span>${player.score}</span>
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
            item.className = "slf-friend-row";
            item.innerHTML = `
                <div class="slf-friend-mini">
                    <span>${escapeHtml(friend.initial || "?")}</span>
                    <div>
                        <strong>${escapeHtml(friend.name)}</strong>
                        <small>${friend.isInvited ? "Einladung offen" : (friend.wasInvited ? "War schon eingeladen" : "Freund")}</small>
                    </div>
                </div>
                <form method="post" action="${escapeHtml(urls.invite)}">
                    <input type="hidden" name="csrfmiddlewaretoken" value="${escapeHtml(csrfToken)}">
                    <input type="hidden" name="friend_id" value="${escapeHtml(friend.id)}">
                    <button class="slf-icon-btn" type="submit" ${friend.isInvited ? "disabled" : ""} aria-label="Einladen">
                        <i class="fa-solid ${friend.isInvited ? "fa-check" : "fa-plus"}"></i>
                    </button>
                </form>
            `;
            list.appendChild(item);
        });
    }

    function renderAnswers(force = false) {
        const grid = document.getElementById("answers-grid");
        const form = document.getElementById("answers-form");
        const button = document.getElementById("submit-answers-btn");
        const isPlaying = state.status === "playing";
        form.classList.toggle("hidden", !isPlaying);
        button.disabled = !isPlaying || state.me.isSubmitted;
        button.innerHTML = state.me.isSubmitted
            ? '<i class="fa-solid fa-check"></i> Runde gestoppt'
            : '<i class="fa-solid fa-hand"></i> Stopp rufen';

        if (!isPlaying) {
            lastAnswerRound = null;
            return;
        }
        if (!force && lastAnswerRound === state.round && grid.children.length === state.categories.length) {
            return;
        }

        lastAnswerRound = state.round;
        grid.innerHTML = "";
        state.categories.forEach((category, index) => {
            const label = document.createElement("label");
            label.className = "slf-answer-field";
            label.innerHTML = `
                <span>${escapeHtml(category)}</span>
                <input id="answer-${index}" type="text" maxlength="80" autocomplete="off" ${state.me.isSubmitted ? "disabled" : ""} value="${escapeHtml((state.me.answers || {})[category] || "")}">
            `;
            grid.appendChild(label);
        });
        grid.querySelector("input:not([disabled])")?.focus();
    }

    function renderPanels() {
        const waiting = document.getElementById("waiting-panel");
        const summary = document.getElementById("summary-panel");
        waiting.classList.toggle("hidden", state.status !== "waiting");
        summary.classList.toggle("hidden", state.status !== "round_summary" && state.status !== "finished");
        const continueBtn = document.getElementById("continue-round-btn");
        continueBtn.classList.toggle("hidden", !state.isOwner || state.status === "finished");
    }

    function renderSummary() {
        const summary = state.summary || {};
        const table = document.getElementById("summary-table");
        if (state.status === "finished") {
            renderFinalRanking(summary.finalRanking || state.finalRanking || []);
            return;
        }

        if (state.status !== "round_summary" || !Array.isArray(summary.rows)) {
            table.innerHTML = "";
            return;
        }

        document.getElementById("summary-title").textContent = `Runde ${summary.round} - Buchstabe ${summary.letter}`;
        document.querySelector("#continue-round-btn span").textContent = summary.isGameOver ? "Spiel beenden" : "Nächste Runde";

        const scoreRows = (summary.rows || []).map((row) => `
            <div class="slf-score-row">
                <strong>${escapeHtml(row.name)}</strong>
                <span>+${Number(row.roundPoints || 0)} P</span>
                <small>${Number(row.score || 0)} gesamt</small>
            </div>
        `).join("");

        const categoryRows = (summary.categoryResults || []).map((category) => `
            <section class="slf-summary-category">
                <h3>${escapeHtml(category.name)}</h3>
                <div class="slf-vote-list">
                    ${(category.entries || []).map((entry) => `
                        <div class="slf-vote-row ${entry.accepted ? "is-accepted" : "is-rejected"}">
                            <strong>${escapeHtml(entry.name)}</strong>
                            <span class="slf-vote-answer">${escapeHtml(entry.answer || "-")}</span>
                            <div class="slf-vote-actions">
                                <button type="button" data-vote="true" data-category="${escapeHtml(category.name)}" data-player-id="${escapeHtml(entry.playerId)}" class="${entry.accepted ? "is-active" : ""}" ${entry.answer ? "" : "disabled"}>
                                    <i class="fa-solid fa-check"></i>
                                    Zählt
                                </button>
                                <button type="button" data-vote="false" data-category="${escapeHtml(category.name)}" data-player-id="${escapeHtml(entry.playerId)}" class="${!entry.accepted ? "is-active" : ""}">
                                    <i class="fa-solid fa-xmark"></i>
                                    Zählt nicht
                                </button>
                            </div>
                            <em>${Number(entry.points || 0)} P</em>
                        </div>
                    `).join("")}
                </div>
            </section>
        `).join("");

        table.innerHTML = `
            <div class="slf-score-list">${scoreRows}</div>
            ${categoryRows}
        `;
    }

    function renderFinalRanking(ranking) {
        const table = document.getElementById("summary-table");
        document.getElementById("summary-title").textContent = "Endstand";
        const podium = ranking.slice(0, 3);
        const remaining = ranking.slice(3);
        table.innerHTML = `
            <div class="slf-final-podium">
                ${podium.map((player) => `
                    <div class="slf-final-card place-${Math.min(Number(player.place || 0), 3)}">
                        <span>#${Number(player.place || 0)}</span>
                        <strong>${escapeHtml(player.name)}</strong>
                        <em>${Number(player.score || 0)} Punkte</em>
                    </div>
                `).join("")}
            </div>
            ${remaining.length ? `
                <div class="slf-final-ranking">
                    ${remaining.map((player) => `
                        <div class="slf-final-row">
                            <span>#${Number(player.place || 0)}</span>
                            <strong>${escapeHtml(player.name)}</strong>
                            <em>${Number(player.score || 0)} Punkte</em>
                        </div>
                    `).join("")}
                </div>
            ` : ""}
        `;
    }

    function escapeHtml(value) {
        return escapeHtmlGlobal(value);
    }

    function showToast(message) {
        let toast = document.querySelector(".slf-toast");
        if (!toast) {
            toast = document.createElement("div");
            toast.className = "slf-toast";
            document.body.appendChild(toast);
        }
        toast.textContent = message;
        clearTimeout(toast.timer);
        toast.timer = setTimeout(() => toast.remove(), 2200);
    }

    function handleDeletedLobby(payload) {
        showToast(payload.error || "Diese Lobby wurde gelöscht.");
        window.setTimeout(() => {
            window.location.href = payload.redirectUrl || "/stadt-land-fluss/";
        }, 900);
    }
}

function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(";").shift();
    return "";
}

function escapeHtmlGlobal(value) {
    return String(value ?? "").replace(/[&<>'"]/g, char => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        "'": "&#39;",
        '"': "&quot;",
    }[char]));
}
