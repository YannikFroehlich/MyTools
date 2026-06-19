(function () {
    "use strict";

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
        villager: ["fa-solid fa-house", "Finde durch Diskussion und Abstimmung alle Werwölfe."],
        werewolf: ["fa-solid fa-paw", "Wähle nachts mit deinem Rudel ein Opfer und bleibe am Tag unerkannt."],
        seer: ["fa-solid fa-eye", "Prüfe jede Nacht die Gesinnung eines Dorfbewohners."],
        witch: ["fa-solid fa-flask", "Du besitzt genau einen Heiltrank und einen Gifttrank."],
        guard: ["fa-solid fa-shield-halved", "Beschütze nachts eine Person, aber nicht zweimal nacheinander dieselbe."]
    };

    function escapeHtml(value) {
        const div = document.createElement("div");
        div.textContent = value == null ? "" : String(value);
        return div.innerHTML;
    }
    function csrf() {
        return document.querySelector("input[name=csrfmiddlewaretoken]")?.value || document.cookie.split("; ").find((row) => row.startsWith("csrftoken="))?.split("=")[1] || "";
    }
    function showToast(text, error) {
        els.toast.textContent = text;
        els.toast.hidden = false;
        els.toast.classList.toggle("is-error", Boolean(error));
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => { els.toast.hidden = true; }, 3600);
    }
    async function post(url, data) {
        const body = new URLSearchParams(data || {});
        const response = await fetch(url, { method: "POST", headers: { "X-CSRFToken": csrf(), "X-Requested-With": "XMLHttpRequest" }, body });
        let json;
        try { json = await response.json(); } catch (_error) { json = { ok: false, error: "Der Server hat keine gültige Antwort gesendet." }; }
        if (!response.ok || json.ok === false) throw new Error(json.error || "Aktion fehlgeschlagen.");
        return json;
    }

    function renderPhase() {
        const status = state.status;
        els.phase.className = `ww-phase-banner is-${status}`;
        if (status === "waiting") {
            els.phaseKicker.textContent = "Vorbereitung"; els.phaseTitle.textContent = "Warten auf Spieler"; els.phaseText.textContent = `Aktuell ${state.players.length} von ${state.rules.maxPlayers} Spielern. Mindestens 5 werden benötigt.`; els.day.textContent = "–";
        } else if (status === "night") {
            els.phaseKicker.textContent = "Das Dorf schläft"; els.phaseTitle.textContent = `Nacht ${state.day}`; els.phaseText.textContent = "Die Nachtrollen wählen im Verborgenen ihre Aktionen."; els.day.textContent = `NACHT ${state.day}`;
        } else if (status === "day") {
            els.phaseKicker.textContent = "Das Dorf erwacht"; els.phaseTitle.textContent = `Tag ${state.day}`; els.phaseText.textContent = "Diskutiert, verdächtigt und stimmt über eine Verbannung ab."; els.day.textContent = `TAG ${state.day}`;
        } else {
            const villageWon = state.winner === "village";
            els.phaseKicker.textContent = "Spiel beendet"; els.phaseTitle.textContent = villageWon ? "Das Dorf gewinnt!" : "Die Werwölfe gewinnen!"; els.phaseText.textContent = villageWon ? "Alle Werwölfe wurden entlarvt." : "Das Rudel hat die Kontrolle über das Dorf übernommen."; els.day.textContent = "ENDE";
        }
    }

    function renderRole() {
        const role = state.viewer.role;
        const meta = roleMeta[role] || ["fa-solid fa-question", "Deine Rolle wird beim Start geheim verteilt."];
        els.roleName.textContent = state.viewer.roleLabel;
        els.roleDescription.textContent = meta[1];
        els.roleIcon.className = meta[0];
        els.roleCard.classList.toggle("is-werewolf", role === "werewolf");
        if (!role) els.roleCard.classList.add("is-hidden");
        els.wolfTab.hidden = role !== "werewolf";
        if (role !== "werewolf" && activeChannel === "wolves") setChannel("village");
    }

    function renderPlayers() {
        els.playerCount.textContent = `${state.players.filter((p) => p.isAlive).length}/${state.players.length}`;
        els.playerList.innerHTML = state.players.map((player) => {
            const badges = `${player.isHost ? '<i class="fa-solid fa-crown" title="Host"></i>' : ""}${player.hasVoted ? '<i class="fa-solid fa-check" title="Hat abgestimmt"></i>' : ""}`;
            const status = player.roleLabel || (player.isAlive ? "Lebt" : "Ausgeschieden");
            return `<div class="ww-player-row ${player.isAlive ? "" : "is-dead"} ${player.isMe ? "is-me" : ""}"><span class="ww-player-avatar">${escapeHtml(player.name.slice(0, 1).toUpperCase())}</span><span class="ww-player-copy"><strong>${escapeHtml(player.name)}${player.isMe ? " · Du" : ""}</strong><small>${escapeHtml(status)}</small></span><span class="ww-player-badges">${player.voteCount ? `<span class="ww-vote-count">${player.voteCount}</span>` : ""}${badges}</span></div>`;
        }).join("");
    }

    function yesNo(value) { return value ? "Aktiv" : "Aus"; }
    function renderRules() {
        els.rules.innerHTML = [
            ["Spielerlimit", state.rules.maxPlayers], ["Werwölfe", state.rules.werewolfCount], ["Seherin", yesNo(state.rules.seer)], ["Hexe", yesNo(state.rules.witch)], ["Beschützer", yesNo(state.rules.guard)], ["Rollen aufdecken", yesNo(state.rules.revealRoles)], ["Geheime Stimmen", yesNo(state.rules.anonymousVotes)]
        ].map(([label, value]) => `<div class="ww-rule-row"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("");
    }

    function targetButton(player, label, selected, action, extra) {
        return `<button type="button" class="ww-target ${selected ? "is-selected" : ""}" data-game-action="${action}" data-target-id="${player.id}" ${extra || ""}><strong>${escapeHtml(player.name)}</strong><small>${escapeHtml(label)}</small></button>`;
    }
    function renderAction() {
        els.targets.innerHTML = ""; els.specials.innerHTML = ""; els.actionResult.hidden = true;
        const viewer = state.viewer;
        if (state.status === "waiting") { els.actionKicker.textContent = "Vorbereitung"; els.actionTitle.textContent = "Versammelt das Dorf"; els.actionHelp.textContent = "Lade Freunde ein oder teile den Lobby-Code. Ab fünf Spielern kann der Host starten."; return; }
        if (state.status === "finished") { els.actionKicker.textContent = "Auflösung"; els.actionTitle.textContent = "Alle Rollen sind sichtbar"; els.actionHelp.textContent = "Der Host kann dieselbe Lobby für eine neue Runde zurücksetzen."; return; }
        if (!viewer.isAlive) { els.actionKicker.textContent = "Zuschauer"; els.actionTitle.textContent = "Du bist ausgeschieden"; els.actionHelp.textContent = "Beobachte den weiteren Spielverlauf. Deine Informationen bleiben geheim."; return; }
        const alive = state.players.filter((p) => p.isAlive && !p.isMe);
        if (state.status === "day") {
            els.actionKicker.textContent = "Dorfabstimmung"; els.actionTitle.textContent = "Wen wollt ihr verbannen?"; els.actionHelp.textContent = "Wähle einen Verdächtigen. Du kannst deine Stimme bis zur Auswertung ändern.";
            els.targets.innerHTML = alive.map((p) => targetButton(p, p.voteCount ? `${p.voteCount} Stimme(n)` : "Verdächtigen", viewer.voteTargetId === p.id, "day_vote")).join(""); return;
        }
        if (viewer.role === "werewolf") {
            els.actionKicker.textContent = "Geheime Rudelwahl"; els.actionTitle.textContent = "Wählt euer Nachtopfer"; els.actionHelp.textContent = "Stimmt euch im Rudel-Chat ab. Bei Gleichstand stirbt niemand.";
            els.targets.innerHTML = alive.filter((p) => p.role !== "werewolf").map((p) => targetButton(p, "Als Opfer wählen", viewer.nightTargetId === p.id, "wolf_vote")).join("");
        } else if (viewer.role === "seer") {
            const rs = viewer.roleState || {}; els.actionKicker.textContent = "Seherblick"; els.actionTitle.textContent = "Prüfe eine Person"; els.actionHelp.textContent = "Du erfährst, ob diese Person ein Werwolf ist.";
            if (rs.inspected_day === state.day) { els.actionResult.hidden = false; els.actionResult.textContent = `${rs.inspection_name} ist ${rs.inspection_is_wolf ? "ein Werwolf" : "kein Werwolf"}.`; }
            else els.targets.innerHTML = alive.map((p) => targetButton(p, "Gesinnung prüfen", false, "seer_inspect")).join("");
        } else if (viewer.role === "guard") {
            els.actionKicker.textContent = "Nachtwache"; els.actionTitle.textContent = "Beschütze eine Person"; els.actionHelp.textContent = "Das gewählte Ziel überlebt den Angriff der Werwölfe. Nicht zweimal nacheinander dieselbe Person.";
            const candidates = state.players.filter((p) => p.isAlive && p.id !== viewer.roleState.last_protected_id);
            els.targets.innerHTML = candidates.map((p) => targetButton(p, "Diese Nacht schützen", viewer.nightTargetId === p.id, "guard_protect")).join("");
        } else if (viewer.role === "witch") {
            const rs = viewer.roleState || {}; const victim = viewer.wolfVictim; els.actionKicker.textContent = "Hexenküche"; els.actionTitle.textContent = "Nutze deine Tränke mit Bedacht"; els.actionHelp.textContent = victim ? `Das aktuelle Ziel des Rudels ist ${victim.name}.` : "Das Rudel hat noch kein eindeutiges Opfer gewählt.";
            els.targets.innerHTML = rs.poison_available ? alive.map((p) => targetButton(p, "Mit Gift ausschalten", viewer.nightTargetId === p.id && rs.night_action === "poison", "witch_action", 'data-choice="poison"')).join("") : "";
            els.specials.innerHTML = `${rs.heal_available ? `<button class="ww-primary" data-witch-choice="heal" ${victim ? "" : "disabled"}><i class="fa-solid fa-heart"></i> ${victim ? `${escapeHtml(victim.name)} heilen` : "Kein Opfer zu heilen"}</button>` : ""}<button class="ww-secondary" data-witch-choice="skip"><i class="fa-solid fa-bed"></i> Nichts tun</button>`;
        } else { els.actionKicker.textContent = "Dorfbewohner"; els.actionTitle.textContent = "Du schläfst"; els.actionHelp.textContent = "In der Nacht hast du keine Aktion. Am nächsten Tag zählt deine Stimme."; }
    }

    function renderHost() {
        els.hostPanel.hidden = !state.isHost; if (!state.isHost) return;
        els.start.hidden = state.status !== "waiting"; els.advance.hidden = !["night", "day"].includes(state.status); els.reset.hidden = state.status !== "finished";
        els.start.disabled = state.players.length < 5;
        if (state.status === "waiting") els.hostHelp.textContent = state.players.length < 5 ? `Noch ${5 - state.players.length} Spieler benötigt.` : "Das Dorf ist bereit. Rollen werden beim Start geheim verteilt.";
        else if (state.status === "night") { els.hostHelp.textContent = "Beende die Nacht, sobald alle Nachtrollen gewählt haben."; els.advance.querySelector("span").textContent = "Nacht auswerten"; }
        else if (state.status === "day") { els.hostHelp.textContent = "Beende den Tag nach Diskussion und Abstimmung."; els.advance.querySelector("span").textContent = "Abstimmung auswerten"; }
        else els.hostHelp.textContent = "Bereite dieselbe Lobby für eine neue Runde vor.";
    }

    function setChannel(channel) {
        activeChannel = channel;
        game.querySelectorAll(".ww-chat-tabs button").forEach((button) => button.classList.toggle("active", button.dataset.channel === channel));
        renderMessages();
    }
    function renderMessages() {
        if (!state) return;
        const rows = state.messages.filter((message) => message.channel === "system" || message.channel === activeChannel);
        els.messages.innerHTML = rows.map((message) => message.channel === "system" ? `<div class="ww-message is-system"><p>${escapeHtml(message.text)}</p></div>` : `<div class="ww-message ${message.channel === "wolves" ? "is-wolves" : ""}"><strong>${escapeHtml(message.sender)}</strong><time>${escapeHtml(message.time)}</time><p>${escapeHtml(message.text)}</p></div>`).join("") || '<p class="ww-muted">Noch keine Nachrichten.</p>';
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
            if (!response.ok) throw new Error(json.error || "Status konnte nicht geladen werden.");
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
        event.preventDefault(); const text = els.chatInput.value.trim(); if (!text) return;
        try { await post(game.dataset.messageUrl, { text, channel: activeChannel }); els.chatInput.value = ""; await loadState(); }
        catch (error) { showToast(error.message, true); }
    });
    $(".ww-copy-code")?.addEventListener("click", async (event) => {
        const code = event.currentTarget.dataset.code;
        try { await navigator.clipboard.writeText(`${window.location.origin}/werwolf/?code=${code}`); showToast("Lobby-Link kopiert."); }
        catch (_error) { showToast(`Lobby-Code: ${code}`); }
    });

    loadState();
    window.setInterval(() => loadState(true), 2500);
})();
