(function () {
    "use strict";

    function readI18n() {
        const script = document.getElementById("ww-i18n");
        if (!script) return {};
        try {
            return JSON.parse(script.textContent || "{}");
        } catch (_error) {
            return {};
        }
    }

    const i18n = readI18n();
    function text(key, replacements) {
        const template = i18n[key] || key;
        return String(template).replace(/\{([a-zA-Z0-9_]+)\}/g, (_match, name) => {
            if (!replacements || replacements[name] == null) return "";
            return String(replacements[name]);
        });
    }

    const visibility = document.getElementById("ww-visibility");
    const passwordField = document.getElementById("ww-password-field");
    if (visibility && passwordField) {
        const syncPassword = () => {
            const isPassword = visibility.value === "password";
            passwordField.hidden = !isPassword;
            const input = passwordField.querySelector("input");
            if (input) input.required = isPassword;
        };
        visibility.addEventListener("change", syncPassword);
        syncPassword();
    }

    document.querySelectorAll("[data-confirm]").forEach((form) => {
        form.addEventListener("submit", (event) => {
            if (!window.confirm(form.dataset.confirm)) event.preventDefault();
        });
    });

    const game = document.getElementById("ww-game");
    if (!game) return;

    const $ = (selector) => game.querySelector(selector);
    const els = {
        phase: $("#ww-phase-banner"), phaseKicker: $("#ww-phase-kicker"), phaseTitle: $("#ww-phase-title"), phaseText: $("#ww-phase-text"), day: $("#ww-day-badge"),
        roleCard: $("#ww-role-card"), roleIcon: $("#ww-role-icon"), roleName: $("#ww-role-name"), roleDescription: $("#ww-role-description"), roleToggle: $("#ww-toggle-role"),
        playerList: $("#ww-player-list"), playerCount: $("#ww-player-count"), rules: $("#ww-rules-list"),
        actionKicker: $("#ww-action-kicker"), actionTitle: $("#ww-action-title"), actionHelp: $("#ww-action-help"), targets: $("#ww-target-grid"), specials: $("#ww-special-actions"), actionResult: $("#ww-action-result"),
        hostPanel: $("#ww-host-panel"), hostHelp: $("#ww-host-help"), start: $("#ww-start"), advance: $("#ww-advance"), reset: $("#ww-reset"),
        messages: $("#ww-message-list"), chatForm: $("#ww-chat-form"), chatInput: $("#ww-chat-input"), wolfTab: $("#ww-wolf-chat-tab"), toast: $("#ww-toast")
    };
    let state = null;
    let activeChannel = "village";
    let loading = false;
    let toastTimer = null;
    const roleMeta = {
        villager: ["fa-solid fa-house", "roleVillager"],
        werewolf: ["fa-solid fa-paw", "roleWerewolf"],
        seer: ["fa-solid fa-eye", "roleSeer"],
        witch: ["fa-solid fa-flask", "roleWitch"],
        guard: ["fa-solid fa-shield-halved", "roleGuard"]
    };

    function escapeHtml(value) {
        const div = document.createElement("div");
        div.textContent = value == null ? "" : String(value);
        return div.innerHTML;
    }
    function csrf() {
        return document.querySelector("input[name=csrfmiddlewaretoken]")?.value || document.cookie.split("; ").find((row) => row.startsWith("csrftoken="))?.split("=")[1] || "";
    }
    function showToast(message, error) {
        els.toast.textContent = message;
        els.toast.hidden = false;
        els.toast.classList.toggle("is-error", Boolean(error));
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => { els.toast.hidden = true; }, 3600);
    }
    async function post(url, data) {
        const body = new URLSearchParams(data || {});
        const response = await fetch(url, { method: "POST", headers: { "X-CSRFToken": csrf(), "X-Requested-With": "XMLHttpRequest" }, body });
        let json;
        try { json = await response.json(); } catch (_error) { json = { ok: false, error: text("invalidServerResponse") }; }
        if (!response.ok || json.ok === false) throw new Error(json.error || text("actionFailed"));
        return json;
    }

    function renderPhase() {
        const status = state.status;
        els.phase.className = `ww-phase-banner is-${status}`;
        if (status === "waiting") {
            els.phaseKicker.textContent = text("waitingPhaseKicker");
            els.phaseTitle.textContent = text("waitingPhaseTitle");
            els.phaseText.textContent = text("waitingPhaseText", { count: state.players.length, max: state.rules.maxPlayers, min: state.rules.minPlayers });
            els.day.textContent = text("dash");
        } else if (status === "night") {
            els.phaseKicker.textContent = text("nightPhaseKicker");
            els.phaseTitle.textContent = text("nightPhaseTitle", { day: state.day });
            els.phaseText.textContent = text("nightPhaseText");
            els.day.textContent = text("nightBadge", { day: state.day });
        } else if (status === "day") {
            els.phaseKicker.textContent = text("dayPhaseKicker");
            els.phaseTitle.textContent = text("dayPhaseTitle", { day: state.day });
            els.phaseText.textContent = text("dayPhaseText");
            els.day.textContent = text("dayBadge", { day: state.day });
        } else {
            const villageWon = state.winner === "village";
            els.phaseKicker.textContent = text("finishedPhaseKicker");
            els.phaseTitle.textContent = villageWon ? text("villageWonTitle") : text("wolvesWonTitle");
            els.phaseText.textContent = villageWon ? text("villageWonText") : text("wolvesWonText");
            els.day.textContent = text("endBadge");
        }
    }

    function renderRole() {
        const role = state.viewer.role;
        const meta = roleMeta[role] || ["fa-solid fa-question", "unknownRoleDescription"];
        els.roleName.textContent = state.viewer.roleLabel;
        els.roleDescription.textContent = text(meta[1]);
        els.roleIcon.className = meta[0];
        els.roleCard.classList.toggle("is-werewolf", role === "werewolf");
        if (!role) els.roleCard.classList.add("is-hidden");
        els.wolfTab.hidden = role !== "werewolf";
        if (role !== "werewolf" && activeChannel === "wolves") setChannel("village");
    }

    function renderPlayers() {
        els.playerCount.textContent = `${state.players.filter((player) => player.isAlive).length}/${state.players.length}`;
        els.playerList.innerHTML = state.players.map((player) => {
            const badges = `${player.isHost ? `<i class="fa-solid fa-crown" title="${escapeHtml(text("hostTitle"))}"></i>` : ""}${player.hasVoted ? `<i class="fa-solid fa-check" title="${escapeHtml(text("votedTitle"))}"></i>` : ""}`;
            const status = player.roleLabel || (player.isAlive ? text("alive") : text("eliminated"));
            const ownLabel = player.isMe ? ` &middot; ${escapeHtml(text("you"))}` : "";
            return `<div class="ww-player-row ${player.isAlive ? "" : "is-dead"} ${player.isMe ? "is-me" : ""}"><span class="ww-player-avatar">${escapeHtml(player.name.slice(0, 1).toUpperCase())}</span><span class="ww-player-copy"><strong>${escapeHtml(player.name)}${ownLabel}</strong><small>${escapeHtml(status)}</small></span><span class="ww-player-badges">${player.voteCount ? `<span class="ww-vote-count">${player.voteCount}</span>` : ""}${badges}</span></div>`;
        }).join("");
    }

    function yesNo(value) { return value ? text("active") : text("inactive"); }
    function renderRules() {
        els.rules.innerHTML = [
            [text("playerLimit"), state.rules.maxPlayers],
            [text("werewolves"), state.rules.werewolfCount],
            [text("seer"), yesNo(state.rules.seer)],
            [text("witch"), yesNo(state.rules.witch)],
            [text("guard"), yesNo(state.rules.guard)],
            [text("revealRoles"), yesNo(state.rules.revealRoles)],
            [text("anonymousVotes"), yesNo(state.rules.anonymousVotes)]
        ].map(([label, value]) => `<div class="ww-rule-row"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("");
    }

    function targetButton(player, label, selected, action, extra) {
        return `<button type="button" class="ww-target ${selected ? "is-selected" : ""}" data-game-action="${action}" data-target-id="${player.id}" ${extra || ""}><strong>${escapeHtml(player.name)}</strong><small>${escapeHtml(label)}</small></button>`;
    }
    function renderAction() {
        els.targets.innerHTML = ""; els.specials.innerHTML = ""; els.actionResult.hidden = true;
        const viewer = state.viewer;
        if (state.status === "waiting") {
            els.actionKicker.textContent = text("actionWaitingKicker"); els.actionTitle.textContent = text("actionWaitingTitle"); els.actionHelp.textContent = text("actionWaitingHelp"); return;
        }
        if (state.status === "finished") {
            els.actionKicker.textContent = text("actionFinishedKicker"); els.actionTitle.textContent = text("actionFinishedTitle"); els.actionHelp.textContent = text("actionFinishedHelp"); return;
        }
        if (!viewer.isAlive) {
            els.actionKicker.textContent = text("spectatorKicker"); els.actionTitle.textContent = text("spectatorTitle"); els.actionHelp.textContent = text("spectatorHelp"); return;
        }
        const alive = state.players.filter((player) => player.isAlive && !player.isMe);
        if (state.status === "day") {
            els.actionKicker.textContent = text("dayActionKicker"); els.actionTitle.textContent = text("dayActionTitle"); els.actionHelp.textContent = text("dayActionHelp");
            els.targets.innerHTML = alive.map((player) => targetButton(player, player.voteCount ? text("voteCountLabel", { count: player.voteCount }) : text("suspectLabel"), viewer.voteTargetId === player.id, "day_vote")).join(""); return;
        }
        if (viewer.role === "werewolf") {
            els.actionKicker.textContent = text("werewolfActionKicker"); els.actionTitle.textContent = text("werewolfActionTitle"); els.actionHelp.textContent = text("werewolfActionHelp");
            els.targets.innerHTML = alive.filter((player) => player.role !== "werewolf").map((player) => targetButton(player, text("victimLabel"), viewer.nightTargetId === player.id, "wolf_vote")).join("");
        } else if (viewer.role === "seer") {
            const roleState = viewer.roleState || {}; els.actionKicker.textContent = text("seerActionKicker"); els.actionTitle.textContent = text("seerActionTitle"); els.actionHelp.textContent = text("seerActionHelp");
            if (roleState.inspected_day === state.day) {
                els.actionResult.hidden = false;
                els.actionResult.textContent = text("inspectionResult", { name: roleState.inspection_name, result: roleState.inspection_is_wolf ? text("isWerewolf") : text("isNotWerewolf") });
            } else {
                els.targets.innerHTML = alive.map((player) => targetButton(player, text("inspectLabel"), false, "seer_inspect")).join("");
            }
        } else if (viewer.role === "guard") {
            els.actionKicker.textContent = text("guardActionKicker"); els.actionTitle.textContent = text("guardActionTitle"); els.actionHelp.textContent = text("guardActionHelp");
            const candidates = state.players.filter((player) => player.isAlive && player.id !== viewer.roleState.last_protected_id);
            els.targets.innerHTML = candidates.map((player) => targetButton(player, text("protectLabel"), viewer.nightTargetId === player.id, "guard_protect")).join("");
        } else if (viewer.role === "witch") {
            const roleState = viewer.roleState || {}; const victim = viewer.wolfVictim;
            els.actionKicker.textContent = text("witchActionKicker"); els.actionTitle.textContent = text("witchActionTitle"); els.actionHelp.textContent = victim ? text("witchHelpWithVictim", { name: victim.name }) : text("witchHelpNoVictim");
            els.targets.innerHTML = roleState.poison_available ? alive.map((player) => targetButton(player, text("poisonLabel"), viewer.nightTargetId === player.id && roleState.night_action === "poison", "witch_action", 'data-choice="poison"')).join("") : "";
            const healLabel = victim ? text("healVictimLabel", { name: victim.name }) : text("noVictimToHeal");
            els.specials.innerHTML = `${roleState.heal_available ? `<button class="ww-primary" data-witch-choice="heal" ${victim ? "" : "disabled"}><i class="fa-solid fa-heart"></i> ${escapeHtml(healLabel)}</button>` : ""}<button class="ww-secondary" data-witch-choice="skip"><i class="fa-solid fa-bed"></i> ${escapeHtml(text("doNothing"))}</button>`;
        } else {
            els.actionKicker.textContent = text("villagerActionKicker"); els.actionTitle.textContent = text("villagerActionTitle"); els.actionHelp.textContent = text("villagerActionHelp");
        }
    }

    function renderHost() {
        els.hostPanel.hidden = !state.isHost; if (!state.isHost) return;
        els.start.hidden = state.status !== "waiting"; els.advance.hidden = !["night", "day"].includes(state.status); els.reset.hidden = state.status !== "finished";
        els.start.disabled = state.players.length < state.rules.minPlayers;
        if (state.status === "waiting") els.hostHelp.textContent = state.players.length < state.rules.minPlayers ? text("playersNeeded", { count: state.rules.minPlayers - state.players.length }) : text("hostReady");
        else if (state.status === "night") { els.hostHelp.textContent = text("hostNightHelp"); els.advance.querySelector("span").textContent = text("resolveNight"); }
        else if (state.status === "day") { els.hostHelp.textContent = text("hostDayHelp"); els.advance.querySelector("span").textContent = text("resolveVote"); }
        else els.hostHelp.textContent = text("hostResetHelp");
    }

    function setChannel(channel) {
        activeChannel = channel;
        game.querySelectorAll(".ww-chat-tabs button").forEach((button) => button.classList.toggle("active", button.dataset.channel === channel));
        renderMessages();
    }
    function renderMessages() {
        if (!state) return;
        const rows = state.messages.filter((message) => message.channel === "system" || message.channel === activeChannel);
        els.messages.innerHTML = rows.map((message) => message.channel === "system" ? `<div class="ww-message is-system"><p>${escapeHtml(message.text)}</p></div>` : `<div class="ww-message ${message.channel === "wolves" ? "is-wolves" : ""}"><strong>${escapeHtml(message.sender)}</strong><time>${escapeHtml(message.time)}</time><p>${escapeHtml(message.text)}</p></div>`).join("") || `<p class="ww-muted">${escapeHtml(text("noMessages"))}</p>`;
        els.messages.scrollTop = els.messages.scrollHeight;
        els.chatInput.disabled = !state.viewer.isAlive && state.status !== "finished";
    }
    function render() { renderPhase(); renderRole(); renderPlayers(); renderRules(); renderAction(); renderHost(); renderMessages(); }

    async function loadState(silent) {
        if (loading) return; loading = true;
        try {
            const response = await fetch(game.dataset.stateUrl, { headers: { "X-Requested-With": "XMLHttpRequest" } });
            const json = await response.json();
            if (response.status === 410 || json.gameDeleted) { window.location.href = json.redirectUrl || "/werwolf/"; return; }
            if (!response.ok) throw new Error(json.error || text("stateLoadFailed"));
            state = json; render();
        } catch (error) { if (!silent) showToast(error.message, true); }
        finally { loading = false; }
    }
    async function run(url, data) {
        try { state = await post(url, data); render(); }
        catch (error) { showToast(error.message, true); }
    }

    els.roleToggle.addEventListener("click", () => els.roleCard.classList.toggle("is-hidden"));
    els.start.addEventListener("click", () => run(game.dataset.startUrl));
    els.advance.addEventListener("click", () => run(game.dataset.advanceUrl));
    els.reset.addEventListener("click", () => run(game.dataset.resetUrl));
    els.targets.addEventListener("click", (event) => {
        const button = event.target.closest("[data-game-action]"); if (!button) return;
        const data = { action: button.dataset.gameAction, target_id: button.dataset.targetId };
        if (button.dataset.choice) data.choice = button.dataset.choice;
        run(game.dataset.actionUrl, data);
    });
    els.specials.addEventListener("click", (event) => {
        const button = event.target.closest("[data-witch-choice]"); if (!button) return;
        run(game.dataset.actionUrl, { action: "witch_action", choice: button.dataset.witchChoice });
    });
    game.querySelectorAll(".ww-chat-tabs button").forEach((button) => button.addEventListener("click", () => setChannel(button.dataset.channel)));
    els.chatForm.addEventListener("submit", async (event) => {
        event.preventDefault(); const message = els.chatInput.value.trim(); if (!message) return;
        try { await post(game.dataset.messageUrl, { text: message, channel: activeChannel }); els.chatInput.value = ""; await loadState(); }
        catch (error) { showToast(error.message, true); }
    });
    $(".ww-copy-code")?.addEventListener("click", async (event) => {
        const code = event.currentTarget.dataset.code;
        try { await navigator.clipboard.writeText(`${window.location.origin}/werwolf/?code=${code}`); showToast(text("lobbyLinkCopied")); }
        catch (_error) { showToast(text("lobbyCode", { code })); }
    });

    loadState();
    window.setInterval(() => loadState(true), 2500);
})();
