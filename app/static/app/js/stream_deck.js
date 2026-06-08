import OBSWebSocket from "https://cdn.jsdelivr.net/npm/obs-websocket-js@5.0.6/+esm";

const streamDeckPage = document.querySelector(".stream-deck-page");
const USER_STORAGE_SUFFIX = streamDeckPage?.dataset.userId ? `_user_${streamDeckPage.dataset.userId}` : "";
const scopedStorageKey = (key) => `${key}${USER_STORAGE_SUFFIX}`;

const STORAGE_KEYS = {
    buttons: "obs_streamdeck_buttons_v2",
    obsAddress: "obs_streamdeck_address_v2",
    obsPassword: "obs_streamdeck_password_v2",
    spotifyToken: "obs_streamdeck_spotify_token_v2",
    logs: "obs_streamdeck_logs_v2"
};

Object.keys(STORAGE_KEYS).forEach((key) => {
    STORAGE_KEYS[key] = scopedStorageKey(STORAGE_KEYS[key]);
});

const SPOTIFY_REFRESH_TOKEN_KEY = scopedStorageKey("spotify_refresh_token");
const SPOTIFY_TOKEN_EXPIRES_AT_KEY = scopedStorageKey("spotify_token_expires_at");
const SPOTIFY_CODE_VERIFIER_KEY = scopedStorageKey("spotify_code_verifier");

const SPOTIFY_CLIENT_ID = streamDeckPage?.dataset.spotifyClientId || "";
const SPOTIFY_REDIRECT_URI = streamDeckPage?.dataset.spotifyRedirectUri || window.location.href.split("?")[0];

const SPOTIFY_SCOPES = [
    "user-read-currently-playing",
    "user-read-playback-state",
    "user-modify-playback-state"
];

const defaultButtons = [];

let obs = null;
let obsConnected = false;
let editMode = false;
let deckFullscreenActive = false;
let currentEditIndex = null;
let buttons = [];
let logs = [];
let toastTimer = null;
let spotifyRefreshInterval = null;
let spotifyProgressInterval = null;
let spotifyProgressCache = {
    isPlaying: false,
    progressMs: 0,
    durationMs: 0,
    lastUpdated: 0
};

const $ = (id) => document.getElementById(id);

const elements = {
    obsAddress: $("obs-address"),
    obsPassword: $("obs-password"),
    togglePasswordBtn: $("toggle-password-btn"),
    connectBtn: $("connect-btn"),
    disconnectBtn: $("disconnect-btn"),
    editToggleBtn: $("edit-toggle-btn"),
    deckFullscreenBtn: $("deck-fullscreen-btn"),
    exitDeckFullscreenBtn: $("exit-deck-fullscreen-btn"),
    buttonGrid: $("button-grid"),
    addButtonBtn: $("add-button-btn"),
    resetButtonsBtn: $("reset-buttons-btn"),
    obsStatusDot: $("obs-status-dot"),
    obsStatusLabel: $("obs-status-label"),
    obsAddressPreview: $("obs-address-preview"),
    obsVersionText: $("obs-version-text"),
    spotifyStatusDot: $("spotify-status-dot"),
    spotifyStatusText: $("spotify-status-text"),
    spotifySystemStatus: $("spotify-system-status"),
    editModeStatus: $("edit-mode-status"),
    buttonCountText: $("button-count-text"),
    lastActionText: $("last-action-text"),
    spotifyTokenBtn: $("spotify-token-btn"),
    spotifyTrackTitle: $("spotify-track-title"),
    spotifyTrackArtist: $("spotify-track-artist"),
    spotifyCover: $("spotify-cover"),
    spotifyProgressFill: $("spotify-progress-fill"),
    spotifyCurrentTime: $("spotify-current-time"),
    spotifyTotalTime: $("spotify-total-time"),
    spotifyToggleBtn: document.querySelector('[data-spotify-control="toggle"]'),
    showLogBtn: $("show-log-btn"),
    toast: $("toast"),

    editorModal: $("editor-modal"),
    closeEditorBtn: $("close-editor-btn"),
    cancelEditorBtn: $("cancel-editor-btn"),
    saveEditorBtn: $("save-editor-btn"),
    deleteButtonBtn: $("delete-button-btn"),
    editTitle: $("edit-title"),
    editIcon: $("edit-icon"),
    editColor: $("edit-color"),
    editActionType: $("edit-action-type"),
    editObsRequest: $("edit-obs-request"),
    editSceneName: $("edit-scene-name"),
    editSourceScene: $("edit-source-scene"),
    editSourceName: $("edit-source-name"),
    editAudioInput: $("edit-audio-input"),
    editAudioAction: $("edit-audio-action"),
    editAudioStep: $("edit-audio-step"),
    editSpotifyAction: $("edit-spotify-action"),
    editUrl: $("edit-url"),
    obsRequestFields: $("obs-request-fields"),
    obsSceneFields: $("obs-scene-fields"),
    obsSourceFields: $("obs-source-fields"),
    obsAudioFields: $("obs-audio-fields"),
    spotifyFields: $("spotify-fields"),
    urlFields: $("url-fields"),

    spotifyModal: $("spotify-modal"),
    closeSpotifyBtn: $("close-spotify-btn"),
    saveSpotifyTokenBtn: $("save-spotify-token-btn"),
    clearSpotifyTokenBtn: $("clear-spotify-token-btn"),
    spotifyTokenInput: $("spotify-token-input"),

    logModal: $("log-modal"),
    closeLogBtn: $("close-log-btn"),
    logList: $("log-list")
};

document.addEventListener("DOMContentLoaded", async () => {
    loadState();
    bindEvents();

    await handleSpotifyRedirect();

    renderButtons();
    updateObsUI();
    updateSidebarMeta();
    refreshSpotifyState();
    startSpotifyAutoRefresh();
    startSpotifyProgressTicker();
});

function loadState() {
    const savedButtons = localStorage.getItem(STORAGE_KEYS.buttons);
    const savedAddress = localStorage.getItem(STORAGE_KEYS.obsAddress);
    const savedPassword = localStorage.getItem(STORAGE_KEYS.obsPassword);
    const savedLogs = localStorage.getItem(STORAGE_KEYS.logs);

    try {
        buttons = savedButtons ? JSON.parse(savedButtons) : [...defaultButtons];
    } catch {
        buttons = [...defaultButtons];
    }

    try {
        logs = savedLogs ? JSON.parse(savedLogs) : [];
    } catch {
        logs = [];
    }

    elements.obsAddress.value = savedAddress || "ws://127.0.0.1:4455";
    elements.obsPassword.value = savedPassword || "";
    elements.obsAddressPreview.textContent = elements.obsAddress.value || "-";
}

function bindEvents() {
    elements.togglePasswordBtn.addEventListener("click", togglePasswordVisibility);
    elements.connectBtn.addEventListener("click", connectOrDisconnectObs);
    elements.disconnectBtn.addEventListener("click", disconnectObs);
    elements.editToggleBtn.addEventListener("click", toggleEditMode);
    elements.deckFullscreenBtn.addEventListener("click", enterDeckFullscreen);
    elements.exitDeckFullscreenBtn.addEventListener("click", exitDeckFullscreen);

    elements.addButtonBtn.addEventListener("click", addButton);
    elements.resetButtonsBtn.addEventListener("click", resetButtons);

    elements.obsAddress.addEventListener("change", persistConnectionFields);
    elements.obsPassword.addEventListener("change", persistConnectionFields);

    elements.closeEditorBtn.addEventListener("click", closeEditorModal);
    elements.cancelEditorBtn.addEventListener("click", closeEditorModal);
    elements.saveEditorBtn.addEventListener("click", saveEditor);
    elements.deleteButtonBtn.addEventListener("click", deleteCurrentButton);
    elements.editActionType.addEventListener("change", updateDynamicEditorFields);

    elements.spotifyTokenBtn.addEventListener("click", spotifyLogin);
    elements.closeSpotifyBtn.addEventListener("click", closeSpotifyModal);
    elements.saveSpotifyTokenBtn.addEventListener("click", saveSpotifyToken);
    elements.clearSpotifyTokenBtn.addEventListener("click", clearSpotifyToken);

    elements.showLogBtn.addEventListener("click", openLogModal);
    elements.closeLogBtn.addEventListener("click", closeLogModal);

    document.querySelectorAll("[data-spotify-control]").forEach((btn) => {
        btn.addEventListener("click", async () => {
            const action = btn.dataset.spotifyControl;
            try {
                await executeSpotifyAction(action);
                await refreshSpotifyState();
            } catch (error) {
                showToast(error.message || "Spotify Aktion fehlgeschlagen.");
                addLog(`Spotify Fehler: ${error.message || "Unbekannter Fehler"}`);
            }
        });
    });

    document.querySelectorAll(".modal-backdrop").forEach((backdrop) => {
        backdrop.addEventListener("click", (event) => {
            const modal = event.target.parentElement;
            modal.classList.add("hidden");
        });
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            if (deckFullscreenActive) {
                exitDeckFullscreen();
            }

            closeEditorModal();
            closeSpotifyModal();
            closeLogModal();
        }
    });

    document.addEventListener("fullscreenchange", syncDeckFullscreenState);
}

function persistConnectionFields() {
    localStorage.setItem(STORAGE_KEYS.obsAddress, elements.obsAddress.value.trim());
    localStorage.setItem(STORAGE_KEYS.obsPassword, elements.obsPassword.value);
    elements.obsAddressPreview.textContent = elements.obsAddress.value.trim() || "-";
}

function togglePasswordVisibility() {
    if (elements.obsPassword.type === "password") {
        elements.obsPassword.type = "text";
        elements.togglePasswordBtn.innerHTML = '<i class="fa-regular fa-eye-slash"></i>';
    } else {
        elements.obsPassword.type = "password";
        elements.togglePasswordBtn.innerHTML = '<i class="fa-regular fa-eye"></i>';
    }
}

function saveButtonsToStorage() {
    localStorage.setItem(STORAGE_KEYS.buttons, JSON.stringify(buttons));
}

function renderButtons() {
    elements.buttonGrid.innerHTML = "";

    buttons.forEach((button, index) => {
        const wrapper = document.createElement("button");
        wrapper.className = `stream-btn ${editMode ? "edit-mode" : ""}`;
        wrapper.type = "button";

        wrapper.innerHTML = `
            <div class="stream-btn-inner">
                <div class="stream-btn-face" style="--btn-color: ${button.color || "#4e63ff"};">
                    <i class="${button.icon || "fa-solid fa-plus"}"></i>
                </div>
            </div>
            <div class="stream-btn-label">${escapeHtml(button.title || "Leer")}</div>
        `;

        wrapper.addEventListener("click", () => {
            if (editMode) {
                openEditorModal(index);
            } else {
                executeButton(index);
            }
        });

        elements.buttonGrid.appendChild(wrapper);
    });

    updateSidebarMeta();
}

function updateSidebarMeta() {
    elements.buttonCountText.textContent = String(buttons.length);
    elements.editModeStatus.textContent = editMode ? "An" : "Aus";
}

function toggleEditMode() {
    editMode = !editMode;
    updateEditModeUI();

    renderButtons();
    addLog(editMode ? "Bearbeiten-Modus aktiviert" : "Bearbeiten-Modus deaktiviert");
    showToast(editMode ? "Bearbeiten-Modus aktiviert." : "Bearbeiten-Modus deaktiviert.");
}

function updateEditModeUI() {
    elements.editToggleBtn.innerHTML = editMode
        ? '<i class="fa-solid fa-check"></i><span>Fertig</span>'
        : '<i class="fa-solid fa-pen"></i><span>Bearbeiten</span>';

    updateSidebarMeta();
}

async function enterDeckFullscreen() {
    closeEditorModal();
    closeSpotifyModal();
    closeLogModal();

    if (editMode) {
        editMode = false;
        updateEditModeUI();
        renderButtons();
    }

    setDeckFullscreenState(true);

    try {
        if (streamDeckPage.requestFullscreen && document.fullscreenElement !== streamDeckPage) {
            await streamDeckPage.requestFullscreen({ navigationUI: "hide" });
        }
    } catch (error) {
        showToast("Browser-Vollbild nicht verfügbar. Deck-Ansicht aktiviert.");
    }

    lockLandscapeOrientation();
}

async function exitDeckFullscreen() {
    setDeckFullscreenState(false);
    unlockScreenOrientation();

    try {
        if (document.fullscreenElement === streamDeckPage && document.exitFullscreen) {
            await document.exitFullscreen();
        }
    } catch (error) {
        console.warn(error);
    }
}

function setDeckFullscreenState(active) {
    deckFullscreenActive = active;
    streamDeckPage.classList.toggle("is-deck-fullscreen", active);
    document.body.classList.toggle("stream-deck-fullscreen-active", active);

    elements.deckFullscreenBtn.setAttribute("aria-pressed", String(active));
    elements.exitDeckFullscreenBtn.hidden = !active;
    elements.deckFullscreenBtn.innerHTML = active
        ? '<i class="fa-solid fa-compress"></i><span>Vollbild</span>'
        : '<i class="fa-solid fa-expand"></i><span>Vollbild</span>';
}

function syncDeckFullscreenState() {
    const isBrowserFullscreen = document.fullscreenElement === streamDeckPage;

    if (!isBrowserFullscreen && deckFullscreenActive) {
        setDeckFullscreenState(false);
        unlockScreenOrientation();
    }
}

async function lockLandscapeOrientation() {
    try {
        if (screen.orientation?.lock) {
            await screen.orientation.lock("landscape");
        }
    } catch {
        // Some mobile browsers only allow orientation lock in installed apps.
    }
}

function unlockScreenOrientation() {
    try {
        if (screen.orientation?.unlock) {
            screen.orientation.unlock();
        }
    } catch {
        // Ignore unsupported orientation APIs.
    }
}

function addButton() {
    buttons.push({
        title: "Neuer Button",
        icon: "fa-solid fa-plus",
        color: "#4e63ff",
        actionType: "none"
    });

    saveButtonsToStorage();
    renderButtons();

    if (!editMode) {
        toggleEditMode();
    }

    openEditorModal(buttons.length - 1);
}

function resetButtons() {
    if (!confirm("Willst du wirklich alle Buttons zurücksetzen?")) return;

    buttons = [...defaultButtons];
    saveButtonsToStorage();
    renderButtons();
    addLog("Buttons wurden zurückgesetzt");
    showToast("Buttons wurden zurückgesetzt.");
}

function openEditorModal(index) {
    currentEditIndex = index;
    const button = buttons[index];
    if (!button) return;

    elements.editTitle.value = button.title || "";
    elements.editIcon.value = button.icon || "fa-solid fa-plus";
    elements.editColor.value = button.color || "#4e63ff";
    elements.editActionType.value = button.actionType || "none";
    elements.editObsRequest.value = button.obsRequest || "ToggleStream";
    elements.editSceneName.value = button.sceneName || "";
    elements.editSourceScene.value = button.sourceScene || "";
    elements.editSourceName.value = button.sourceName || "";
    elements.editAudioInput.value = button.audioInputName || "";
    elements.editAudioAction.value = button.audioAction || "toggle-mute";
    elements.editAudioStep.value = button.audioStepDb ?? 5;
    elements.editSpotifyAction.value = button.spotifyAction || "toggle";
    elements.editUrl.value = button.url || "";

    updateDynamicEditorFields();
    elements.editorModal.classList.remove("hidden");
}

function closeEditorModal() {
    elements.editorModal.classList.add("hidden");
    currentEditIndex = null;
}

function updateDynamicEditorFields() {
    const type = elements.editActionType.value;

    hideAllDynamicSections();

    if (type === "obs-request") elements.obsRequestFields.classList.remove("hidden");
    if (type === "obs-scene") elements.obsSceneFields.classList.remove("hidden");
    if (type === "obs-source-toggle") elements.obsSourceFields.classList.remove("hidden");
    if (type === "obs-audio") elements.obsAudioFields.classList.remove("hidden");
    if (type === "spotify") elements.spotifyFields.classList.remove("hidden");
    if (type === "open-url") elements.urlFields.classList.remove("hidden");
}

function hideAllDynamicSections() {
    elements.obsRequestFields.classList.add("hidden");
    elements.obsSceneFields.classList.add("hidden");
    elements.obsSourceFields.classList.add("hidden");
    elements.obsAudioFields.classList.add("hidden");
    elements.spotifyFields.classList.add("hidden");
    elements.urlFields.classList.add("hidden");
}

function saveEditor() {
    if (currentEditIndex === null) return;

    const actionType = elements.editActionType.value;
    const updated = {
        title: elements.editTitle.value.trim() || "Ohne Titel",
        icon: elements.editIcon.value,
        color: elements.editColor.value,
        actionType
    };

    if (actionType === "obs-request") {
        updated.obsRequest = elements.editObsRequest.value;
    } else if (actionType === "obs-scene") {
        updated.sceneName = elements.editSceneName.value.trim();
    } else if (actionType === "obs-source-toggle") {
        updated.sourceScene = elements.editSourceScene.value.trim();
        updated.sourceName = elements.editSourceName.value.trim();
    } else if (actionType === "obs-audio") {
        updated.audioInputName = elements.editAudioInput.value.trim();
        updated.audioAction = elements.editAudioAction.value;
        updated.audioStepDb = normalizeAudioStep(elements.editAudioStep.value);
    } else if (actionType === "spotify") {
        updated.spotifyAction = elements.editSpotifyAction.value;
    } else if (actionType === "open-url") {
        updated.url = elements.editUrl.value.trim();
    }

    buttons[currentEditIndex] = updated;
    saveButtonsToStorage();
    renderButtons();
    closeEditorModal();

    addLog(`Button gespeichert: ${updated.title}`);
    showToast("Button gespeichert.");
}

function deleteCurrentButton() {
    if (currentEditIndex === null) return;
    if (!confirm("Diesen Button wirklich löschen?")) return;

    const removed = buttons[currentEditIndex];
    buttons.splice(currentEditIndex, 1);
    saveButtonsToStorage();
    renderButtons();
    closeEditorModal();

    addLog(`Button gelöscht: ${removed?.title || "Unbekannt"}`);
    showToast("Button gelöscht.");
}

async function connectOrDisconnectObs() {
    if (obsConnected) {
        await disconnectObs();
    } else {
        await connectObs();
    }
}

async function connectObs() {
    const address = elements.obsAddress.value.trim();
    const password = elements.obsPassword.value;

    if (!address) {
        showToast("Bitte OBS WebSocket Adresse eingeben.");
        return;
    }

    persistConnectionFields();

    try {
        obs = new OBSWebSocket();

        obs.on("ConnectionClosed", () => {
            obsConnected = false;
            updateObsUI();
            addLog("OBS Verbindung wurde geschlossen");
        });

        await obs.connect(address, password || undefined, {
            rpcVersion: 1
        });
        obsConnected = true;
        updateObsUI();

        try {
            const versionData = await obs.call("GetVersion");
            elements.obsVersionText.textContent = versionData.obsVersion || "-";
        } catch {
            elements.obsVersionText.textContent = "-";
        }

        addLog(`OBS verbunden mit ${address}`);
        showToast("OBS erfolgreich verbunden.");
    } catch (error) {
        obsConnected = false;
        obs = null;
        updateObsUI();
        addLog("OBS Verbindung fehlgeschlagen");
        showToast("OBS Verbindung fehlgeschlagen.");
        console.error(error);
    }
}

async function disconnectObs() {
    try {
        if (obs) {
            await obs.disconnect();
        }
    } catch (error) {
        console.warn(error);
    }

    obs = null;
    obsConnected = false;
    updateObsUI();
    addLog("OBS getrennt");
    showToast("OBS getrennt.");
}

function updateObsUI() {
    if (obsConnected) {
        elements.obsStatusDot.classList.add("online");
        elements.obsStatusLabel.textContent = "Verbunden";
        elements.connectBtn.innerHTML = '<i class="fa-solid fa-link-slash"></i><span>Trennen</span>';
    } else {
        elements.obsStatusDot.classList.remove("online");
        elements.obsStatusLabel.textContent = "Nicht verbunden";
        elements.connectBtn.innerHTML = '<i class="fa-solid fa-link"></i><span>Verbinden</span>';
        elements.obsVersionText.textContent = "-";
    }
}

function requireObsConnection() {
    if (!obsConnected || !obs) {
        throw new Error("OBS ist nicht verbunden.");
    }
}

async function executeButton(index) {
    const button = buttons[index];
    if (!button) return;

    animateButton(index);

    try {
        switch (button.actionType) {
            case "obs-request":
                await executeObsRequest(button.obsRequest);
                addLog(`OBS Request ausgeführt: ${button.title}`);
                showToast(`Aktion ausgeführt: ${button.title}`);
                break;

            case "obs-scene":
                await changeObsScene(button.sceneName);
                addLog(`OBS Szene gewechselt: ${button.sceneName}`);
                showToast(`Szene gewechselt: ${button.sceneName}`);
                break;

            case "obs-source-toggle":
                await toggleObsSource(button.sourceScene, button.sourceName);
                addLog(`OBS Quelle getoggelt: ${button.sourceName}`);
                showToast(`Quelle getoggelt: ${button.sourceName}`);
                break;

            case "obs-audio":
                await executeObsAudioAction(button.audioInputName, button.audioAction, button.audioStepDb);
                addLog(`OBS Audio Aktion: ${button.audioInputName}`);
                showToast(`Audio Aktion: ${button.title}`);
                break;

            case "spotify":
                await executeSpotifyAction(button.spotifyAction);
                await refreshSpotifyState();
                addLog(`Spotify Aktion: ${button.spotifyAction}`);
                showToast(`Spotify Aktion: ${button.title}`);
                break;

            case "open-url":
                openUrl(button.url);
                addLog(`URL geöffnet: ${button.url}`);
                showToast(`Geöffnet: ${button.title}`);
                break;

            default:
                addLog(`Keine Aktion hinterlegt: ${button.title}`);
                showToast("Dieser Button hat noch keine Aktion.");
                break;
        }
    } catch (error) {
        addLog(`Fehler bei "${button.title}": ${error.message || "Unbekannter Fehler"}`);
        showToast(error.message || "Aktion fehlgeschlagen.");
    }
}

function animateButton(index) {
    const btn = elements.buttonGrid.children[index];
    if (!btn) return;

    btn.animate(
        [
            { transform: "translateY(0px) scale(1)" },
            { transform: "translateY(3px) scale(0.97)" },
            { transform: "translateY(0px) scale(1)" }
        ],
        { duration: 170, easing: "ease-out" }
    );
}

async function executeObsRequest(requestName) {
    requireObsConnection();
    if (!requestName) throw new Error("Kein OBS Request gewählt.");
    await obs.call(requestName);
}

function normalizeAudioStep(value) {
    const parsed = Number.parseFloat(value);
    if (!Number.isFinite(parsed) || parsed <= 0) return 5;
    return Math.min(parsed, 30);
}

async function executeObsAudioAction(inputName, action, stepDb = 5) {
    requireObsConnection();
    if (!inputName) throw new Error("Kein Audiogerät eingetragen.");

    if (action === "mute" || action === "unmute") {
        await obs.call("SetInputMute", {
            inputName,
            inputMuted: action === "mute"
        });
        return;
    }

    if (action === "toggle-mute") {
        const muteData = await obs.call("GetInputMute", { inputName });
        await obs.call("SetInputMute", {
            inputName,
            inputMuted: !muteData.inputMuted
        });
        return;
    }

    if (action === "volume-up" || action === "volume-down") {
        const volumeData = await obs.call("GetInputVolume", { inputName });
        const currentDb = Number.isFinite(volumeData.inputVolumeDb) ? volumeData.inputVolumeDb : 0;
        const direction = action === "volume-up" ? 1 : -1;
        const nextDb = clamp(currentDb + (normalizeAudioStep(stepDb) * direction), -100, 26);

        await obs.call("SetInputVolume", {
            inputName,
            inputVolumeDb: nextDb
        });
        return;
    }

    throw new Error("Unbekannte Audio Aktion.");
}

function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
}

async function changeObsScene(sceneName) {
    requireObsConnection();
    if (!sceneName) throw new Error("Kein Szenenname eingetragen.");

    await obs.call("SetCurrentProgramScene", { sceneName });
}

async function toggleObsSource(sceneName, sourceName) {
    requireObsConnection();
    if (!sceneName || !sourceName) throw new Error("Szene oder Quelle fehlt.");

    const sceneItems = await obs.call("GetSceneItemList", { sceneName });
    const sourceItem = sceneItems.sceneItems.find(item => item.sourceName === sourceName);

    if (!sourceItem) {
        throw new Error(`Quelle "${sourceName}" nicht gefunden.`);
    }

    const enabledData = await obs.call("GetSceneItemEnabled", {
        sceneName,
        sceneItemId: sourceItem.sceneItemId
    });

    await obs.call("SetSceneItemEnabled", {
        sceneName,
        sceneItemId: sourceItem.sceneItemId,
        sceneItemEnabled: !enabledData.sceneItemEnabled
    });
}

function openUrl(url) {
    if (!url) throw new Error("Keine URL hinterlegt.");

    const normalized = /^https?:\/\//i.test(url) ? url : `https://${url}`;
    window.open(normalized, "_blank", "noopener,noreferrer");
}

function openSpotifyModal() {
    elements.spotifyTokenInput.value = localStorage.getItem(STORAGE_KEYS.spotifyToken) || "";
    elements.spotifyModal.classList.remove("hidden");
}

function closeSpotifyModal() {
    elements.spotifyModal.classList.add("hidden");
}

function saveSpotifyToken() {
    const token = elements.spotifyTokenInput.value.trim();
    if (!token) {
        showToast("Bitte einen Spotify Token einfügen.");
        return;
    }

    localStorage.setItem(STORAGE_KEYS.spotifyToken, token);
    closeSpotifyModal();
    addLog("Spotify Token gespeichert");
    showToast("Spotify Token gespeichert.");
    refreshSpotifyState();
}

function clearSpotifyToken() {
    localStorage.removeItem(STORAGE_KEYS.spotifyToken);
    localStorage.removeItem(SPOTIFY_REFRESH_TOKEN_KEY);
    localStorage.removeItem(SPOTIFY_TOKEN_EXPIRES_AT_KEY);
    localStorage.removeItem(SPOTIFY_CODE_VERIFIER_KEY);

    elements.spotifyTokenInput.value = "";

    addLog("Spotify Token entfernt");
    showToast("Spotify Verbindung entfernt.");
    refreshSpotifyState(true);
}

async function executeSpotifyAction(action) {
    const token = await getValidSpotifyAccessToken();

    if (!token) {
        throw new Error("Bitte zuerst mit Spotify verbinden.");
    }

    if (action === "toggle") {
        const playerState = await getSpotifyPlayerState(token);

        if (playerState?.is_playing) {
            await spotifyRequest("https://api.spotify.com/v1/me/player/pause", "PUT", token);
        } else {
            await spotifyRequest("https://api.spotify.com/v1/me/player/play", "PUT", token);
        }

        return;
    }

    const actionMap = {
        play: { url: "https://api.spotify.com/v1/me/player/play", method: "PUT" },
        pause: { url: "https://api.spotify.com/v1/me/player/pause", method: "PUT" },
        next: { url: "https://api.spotify.com/v1/me/player/next", method: "POST" },
        previous: { url: "https://api.spotify.com/v1/me/player/previous", method: "POST" }
    };

    const config = actionMap[action];

    if (!config) {
        throw new Error("Unbekannte Spotify Aktion.");
    }

    await spotifyRequest(config.url, config.method, token);
}

async function spotifyRequest(url, method, token) {
    const response = await fetch(url, {
        method,
        headers: {
            Authorization: `Bearer ${token}`
        }
    });

    if (!response.ok && response.status !== 204) {
        throw new Error(await getSpotifyError(response));
    }
}

async function getSpotifyPlayerState(token) {
    const response = await fetch("https://api.spotify.com/v1/me/player", {
        headers: {
            Authorization: `Bearer ${token}`
        }
    });

    if (response.status === 204) {
        return null;
    }

    if (!response.ok) {
        throw new Error(await getSpotifyError(response));
    }

    return await response.json();
}

async function getSpotifyError(response) {
    if (response.status === 401) return "Spotify Token ungültig oder abgelaufen.";
    if (response.status === 403) return "Spotify Zugriff verweigert.";
    if (response.status === 404) return "Kein aktives Spotify Gerät gefunden.";
    if (response.status === 429) return "Spotify Rate Limit erreicht.";

    try {
        const data = await response.json();
        return data?.error?.message || "Spotify Fehler.";
    } catch {
        return "Spotify Fehler.";
    }
}

async function refreshSpotifyState(forceReset = false) {
    if (forceReset) {
        setSpotifyDisconnectedState();
        return;
    }

    const token = await getValidSpotifyAccessToken();

    if (!token) {
        setSpotifyDisconnectedState();
        return;
    }

    try {
        const state = await getSpotifyPlayerState(token);

        if (!state || !state.item) {
            spotifyProgressCache = {
                isPlaying: false,
                progressMs: 0,
                durationMs: 0,
                lastUpdated: Date.now()
            };

            elements.spotifyStatusDot.classList.add("online");
            elements.spotifyStatusText.textContent = "Verbunden";
            elements.spotifySystemStatus.textContent = "OK";
            elements.spotifyTrackTitle.textContent = "Keine aktive Wiedergabe";
            elements.spotifyTrackArtist.textContent = "-";
            elements.spotifyCurrentTime.textContent = "0:00";
            elements.spotifyTotalTime.textContent = "0:00";
            elements.spotifyProgressFill.style.width = "0%";
            elements.spotifyCover.innerHTML = '<i class="fa-brands fa-spotify"></i>';
            updateSpotifyToggleButton(false, true);
            return;
        }

        elements.spotifyStatusDot.classList.add("online");
        elements.spotifyStatusText.textContent = state.is_playing ? "Wird abgespielt" : "Pausiert";
        elements.spotifySystemStatus.textContent = "OK";

        elements.spotifyTrackTitle.textContent = state.item.name || "Unbekannt";
        elements.spotifyTrackArtist.textContent = (state.item.artists || [])
            .map(artist => artist.name)
            .join(", ") || "Unbekannt";

        spotifyProgressCache = {
            isPlaying: Boolean(state.is_playing),
            progressMs: state.progress_ms || 0,
            durationMs: state.item.duration_ms || 0,
            lastUpdated: Date.now()
        };

        updateSpotifyToggleButton(Boolean(state.is_playing), true);
        updateSpotifyProgressUI();

        const imageUrl = state.item.album?.images?.[0]?.url;

        if (imageUrl) {
            elements.spotifyCover.innerHTML = `<img src="${imageUrl}" alt="Cover">`;
        } else {
            elements.spotifyCover.innerHTML = '<i class="fa-brands fa-spotify"></i>';
        }
    } catch (error) {
        console.error("Spotify State Fehler:", error);

        elements.spotifyStatusDot.classList.remove("online");
        elements.spotifyStatusText.textContent = "Fehler";
        elements.spotifySystemStatus.textContent = "Fehler";
        elements.spotifyTrackTitle.textContent = "Spotify nicht verfügbar";
        elements.spotifyTrackArtist.textContent = error.message || "-";
        elements.spotifyProgressFill.style.width = "0%";
        elements.spotifyCurrentTime.textContent = "0:00";
        elements.spotifyTotalTime.textContent = "0:00";
        elements.spotifyCover.innerHTML = '<i class="fa-brands fa-spotify"></i>';
        updateSpotifyToggleButton(false, false);
    }
}

function setSpotifyDisconnectedState() {
    spotifyProgressCache = {
        isPlaying: false,
        progressMs: 0,
        durationMs: 0,
        lastUpdated: Date.now()
    };

    elements.spotifyStatusDot.classList.remove("online");
    elements.spotifyStatusText.textContent = "Nicht verbunden";
    elements.spotifySystemStatus.textContent = "-";
    elements.spotifyTrackTitle.textContent = "Kein Titel";
    elements.spotifyTrackArtist.textContent = "Kein Künstler";
    elements.spotifyProgressFill.style.width = "0%";
    elements.spotifyCurrentTime.textContent = "0:00";
    elements.spotifyTotalTime.textContent = "0:00";
    elements.spotifyCover.innerHTML = '<i class="fa-brands fa-spotify"></i>';
    updateSpotifyToggleButton(false, false);
}

function updateSpotifyToggleButton(isPlaying, isConnected) {
    if (!elements.spotifyToggleBtn) return;

    const icon = elements.spotifyToggleBtn.querySelector("i");

    if (icon) {
        icon.className = isPlaying ? "fa-solid fa-pause" : "fa-solid fa-play";
    }

    elements.spotifyToggleBtn.classList.toggle("is-playing", Boolean(isPlaying));
    elements.spotifyToggleBtn.disabled = !isConnected;
    elements.spotifyToggleBtn.setAttribute(
        "aria-label",
        isPlaying ? "Spotify pausieren" : "Spotify abspielen"
    );
    elements.spotifyToggleBtn.title = isPlaying ? "Pause" : "Play";
}

function startSpotifyAutoRefresh() {
    if (spotifyRefreshInterval) clearInterval(spotifyRefreshInterval);

    spotifyRefreshInterval = setInterval(() => {
        refreshSpotifyState();
    }, 1000);
}

function formatMs(ms) {
    const totalSeconds = Math.floor(ms / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = String(totalSeconds % 60).padStart(2, "0");
    return `${minutes}:${seconds}`;
}

function showToast(message) {
    clearTimeout(toastTimer);
    elements.toast.textContent = message;
    elements.toast.classList.remove("hidden");

    toastTimer = setTimeout(() => {
        elements.toast.classList.add("hidden");
    }, 3000);
}

function addLog(message) {
    const entry = {
        time: new Date().toLocaleString("de-DE"),
        message
    };

    logs.unshift(entry);
    logs = logs.slice(0, 40);
    localStorage.setItem(STORAGE_KEYS.logs, JSON.stringify(logs));

    elements.lastActionText.textContent = new Date().toLocaleTimeString("de-DE");
    renderLogs();
}

function renderLogs() {
    elements.logList.innerHTML = "";

    if (!logs.length) {
        elements.logList.innerHTML = `<div class="log-entry"><span class="log-time">-</span>Noch keine Einträge vorhanden.</div>`;
        return;
    }

    logs.forEach((entry) => {
        const div = document.createElement("div");
        div.className = "log-entry";
        div.innerHTML = `
            <span class="log-time">${escapeHtml(entry.time)}</span>
            <div>${escapeHtml(entry.message)}</div>
        `;
        elements.logList.appendChild(div);
    });
}

function openLogModal() {
    renderLogs();
    elements.logModal.classList.remove("hidden");
}

function closeLogModal() {
    elements.logModal.classList.add("hidden");
}

function escapeHtml(str) {
    return String(str)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

async function spotifyLogin() {
    if (!SPOTIFY_CLIENT_ID) {
        showToast("Spotify Client-ID fehlt in der .env.");
        addLog("Spotify Login abgebrochen: Client-ID fehlt");
        return;
    }

    if (!isSpotifyRedirectUriAllowed(SPOTIFY_REDIRECT_URI)) {
        const message = "Spotify Login braucht HTTPS. HTTP ist nur mit 127.0.0.1 oder ::1 erlaubt.";
        console.warn(message, SPOTIFY_REDIRECT_URI);
        showToast(message);
        addLog(`Spotify Login abgebrochen: ungültige Redirect URI ${SPOTIFY_REDIRECT_URI}`);
        return;
    }

    try {
        console.info("Spotify Redirect URI:", SPOTIFY_REDIRECT_URI);

        const codeVerifier = generateRandomString(64);
        const codeChallenge = await generateCodeChallenge(codeVerifier);

        localStorage.setItem(SPOTIFY_CODE_VERIFIER_KEY, codeVerifier);

        const params = new URLSearchParams({
            response_type: "code",
            client_id: SPOTIFY_CLIENT_ID,
            scope: SPOTIFY_SCOPES.join(" "),
            redirect_uri: SPOTIFY_REDIRECT_URI,
            code_challenge_method: "S256",
            code_challenge: codeChallenge
        });

        window.location.href = `https://accounts.spotify.com/authorize?${params.toString()}`;
    } catch (error) {
        console.error("Spotify Login Fehler:", error);
        showToast(error.message || "Spotify Login konnte nicht gestartet werden.");
        addLog(`Spotify Login Fehler: ${error.message || "Unbekannter Fehler"}`);
    }
}

async function handleSpotifyRedirect() {
    const urlParams = new URLSearchParams(window.location.search);
    const code = urlParams.get("code");
    const error = urlParams.get("error");

    if (error) {
        console.error("Spotify Login Fehler:", error);
        showToast(`Spotify Login fehlgeschlagen: ${error}`);
        return;
    }

    if (!code) return;

    const codeVerifier = localStorage.getItem(SPOTIFY_CODE_VERIFIER_KEY);

    if (!codeVerifier) {
        showToast("Spotify Login fehlgeschlagen: Code Verifier fehlt.");
        return;
    }

    try {
        const body = new URLSearchParams({
            client_id: SPOTIFY_CLIENT_ID,
            grant_type: "authorization_code",
            code: code,
            redirect_uri: SPOTIFY_REDIRECT_URI,
            code_verifier: codeVerifier
        });

        const response = await fetch("https://accounts.spotify.com/api/token", {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded"
            },
            body
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error("Spotify Token Fehler:", errorText);
            showToast("Spotify Access Token konnte nicht geholt werden. Siehe Konsole.");
            return;
        }

        const data = await response.json();

        localStorage.setItem(STORAGE_KEYS.spotifyToken, data.access_token);

        if (data.refresh_token) {
            localStorage.setItem(SPOTIFY_REFRESH_TOKEN_KEY, data.refresh_token);
        }

        const expiresAt = Date.now() + ((data.expires_in || 3600) * 1000);
        localStorage.setItem(SPOTIFY_TOKEN_EXPIRES_AT_KEY, String(expiresAt));

        localStorage.removeItem(SPOTIFY_CODE_VERIFIER_KEY);

        window.history.replaceState({}, document.title, SPOTIFY_REDIRECT_URI);

        showToast("Spotify erfolgreich verbunden.");
        addLog("Spotify erfolgreich verbunden");

        await refreshSpotifyState();
    } catch (error) {
        console.error("Spotify Redirect Verarbeitung Fehler:", error);
        showToast("Spotify Login-Verarbeitung fehlgeschlagen.");
    }
}

function generateRandomString(length) {
    const possible = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
    const values = crypto.getRandomValues(new Uint8Array(length));

    return Array.from(values)
        .map((x) => possible[x % possible.length])
        .join("");
}

async function generateCodeChallenge(codeVerifier) {
    if (!crypto?.subtle) {
        throw new Error("Spotify Login braucht einen sicheren Browser-Kontext. Nutze HTTPS oder lokal 127.0.0.1.");
    }

    const data = new TextEncoder().encode(codeVerifier);
    const digest = await crypto.subtle.digest("SHA-256", data);

    return btoa(String.fromCharCode(...new Uint8Array(digest)))
        .replace(/\+/g, "-")
        .replace(/\//g, "_")
        .replace(/=+$/, "");
}

function isSpotifyRedirectUriAllowed(redirectUri) {
    try {
        const url = new URL(redirectUri);
        const hostname = url.hostname.toLowerCase();

        if (url.protocol === "https:") return true;

        return url.protocol === "http:" && (
            hostname === "127.0.0.1" ||
            hostname === "::1" ||
            hostname === "[::1]"
        );
    } catch {
        return false;
    }
}

async function getValidSpotifyAccessToken() {
    const token = localStorage.getItem(STORAGE_KEYS.spotifyToken);
    const refreshToken = localStorage.getItem(SPOTIFY_REFRESH_TOKEN_KEY);
    const expiresAt = Number(localStorage.getItem(SPOTIFY_TOKEN_EXPIRES_AT_KEY) || "0");

    if (token && Date.now() < expiresAt - 60000) {
        return token;
    }

    if (refreshToken) {
        return await refreshSpotifyAccessToken(refreshToken);
    }

    return token || null;
}

async function refreshSpotifyAccessToken(refreshToken) {
    try {
        const body = new URLSearchParams({
            client_id: SPOTIFY_CLIENT_ID,
            grant_type: "refresh_token",
            refresh_token: refreshToken
        });

        const response = await fetch("https://accounts.spotify.com/api/token", {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded"
            },
            body
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error("Spotify Refresh Token Fehler:", errorText);

            localStorage.removeItem(STORAGE_KEYS.spotifyToken);
            localStorage.removeItem(SPOTIFY_REFRESH_TOKEN_KEY);
            localStorage.removeItem(SPOTIFY_TOKEN_EXPIRES_AT_KEY);

            return null;
        }

        const data = await response.json();

        localStorage.setItem(STORAGE_KEYS.spotifyToken, data.access_token);

        if (data.refresh_token) {
            localStorage.setItem(SPOTIFY_REFRESH_TOKEN_KEY, data.refresh_token);
        }

        const expiresAt = Date.now() + ((data.expires_in || 3600) * 1000);
        localStorage.setItem(SPOTIFY_TOKEN_EXPIRES_AT_KEY, String(expiresAt));

        return data.access_token;
    } catch (error) {
        console.error("Spotify Token Refresh fehlgeschlagen:", error);
        return null;
    }
}

function startSpotifyProgressTicker() {
    if (spotifyProgressInterval) {
        clearInterval(spotifyProgressInterval);
    }

    spotifyProgressInterval = setInterval(() => {
        updateSpotifyProgressUI();
    }, 1000);
}

function updateSpotifyProgressUI() {
    const durationMs = spotifyProgressCache.durationMs || 0;

    if (!durationMs) {
        elements.spotifyCurrentTime.textContent = "0:00";
        elements.spotifyTotalTime.textContent = "0:00";
        elements.spotifyProgressFill.style.width = "0%";
        return;
    }

    let currentMs = spotifyProgressCache.progressMs || 0;

    if (spotifyProgressCache.isPlaying) {
        currentMs += Date.now() - spotifyProgressCache.lastUpdated;
    }

    currentMs = Math.min(currentMs, durationMs);

    elements.spotifyCurrentTime.textContent = formatMs(currentMs);
    elements.spotifyTotalTime.textContent = formatMs(durationMs);

    const progress = (currentMs / durationMs) * 100;
    elements.spotifyProgressFill.style.width = `${Math.max(0, Math.min(progress, 100))}%`;
}
