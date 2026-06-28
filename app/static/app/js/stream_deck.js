const OBS_WEBSOCKET_MODULE_URL = "https://cdn.jsdelivr.net/npm/obs-websocket-js@5.0.6/+esm";
let obsWebSocketClassPromise = null;

function loadObsWebSocketClass() {
    if (!obsWebSocketClassPromise) {
        obsWebSocketClassPromise = import(OBS_WEBSOCKET_MODULE_URL)
            .then((module) => module.default || module.OBSWebSocket || module);
    }

    return obsWebSocketClassPromise;
}

function warmObsWebSocketModule() {
    loadObsWebSocketClass().catch((error) => {
        console.warn("OBS WebSocket Modul konnte nicht vorgeladen werden.", error);
        obsWebSocketClassPromise = null;
    });
}

const streamDeckPage = document.querySelector(".stream-deck-page");
const USER_STORAGE_SUFFIX = streamDeckPage?.dataset.userId ? `_user_${streamDeckPage.dataset.userId}` : "";
const scopedStorageKey = (key) => `${key}${USER_STORAGE_SUFFIX}`;

const STORAGE_KEYS = {
    buttons: "obs_streamdeck_buttons_v2",
    obsAddress: "obs_streamdeck_address_v2",
    obsPassword: "obs_streamdeck_password_v2",
    spotifyToken: "obs_streamdeck_spotify_token_v2",
    voicemodApiKey: "obs_streamdeck_voicemod_api_key_v1",
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
const VOICEMOD_ACTION_URL = streamDeckPage?.dataset.voicemodActionUrl || "";
const VOICEMOD_DEFAULT_RANDOM_MODE = "FreeVoices";
const STREAM_DECK_LANGUAGE = (streamDeckPage?.dataset.language || document.documentElement.lang || "de").toLowerCase();
const STREAM_DECK_I18N = {
    en: {
        on: "On",
        off: "Off",
        connected: "Connected",
        disconnected: "Not connected",
        ready: "Ready",
        missingApiKey: "API key missing",
        saveApiKeyHint: "Enter and save an API key",
        apiKeySavedLocal: "API key saved locally",
        missing: "Missing",
        sending: "Sending...",
        active: "Active",
        localPort: "Local port {port}",
        voicemodReachable: "Voicemod reachable",
        error: "Error",
        noActivePlayback: "No active playback",
        playing: "Playing",
        paused: "Paused",
        unknown: "Unknown",
        spotifyUnavailable: "Spotify unavailable",
        noTitle: "No title",
        noArtist: "No artist",
        savedValue: "Saved: {value}",
        tokenInvalid: "Spotify token invalid or expired.",
        accessDenied: "Spotify access denied.",
        noActiveDevice: "No active Spotify device found.",
        rateLimited: "Spotify rate limit reached.",
        unknownError: "Unknown error",
        editModeEnabled: "Edit mode enabled",
        editModeDisabled: "Edit mode disabled",
        fullscreenFallback: "Browser fullscreen unavailable. Deck view enabled.",
        resetButtonsConfirm: "Do you really want to reset all buttons?",
        buttonsReset: "Buttons were reset",
        buttonSaved: "Button saved",
        deleteButtonConfirm: "Really delete this button?",
        buttonDeleted: "Button deleted",
        obsConnectionFailed: "OBS connection failed",
        obsNotConnected: "OBS is not connected.",
        obsRequestExecuted: "OBS request executed: {title}",
        actionExecuted: "Action executed: {title}",
        urlOpened: "URL opened: {url}",
        opened: "Opened: {title}",
        noAction: "No action assigned: {title}",
        actionFailed: "Action failed.",
        buttonError: "Error for \"{title}\": {error}",
        noObsRequest: "No OBS request selected.",
        noAudioDevice: "No audio device entered.",
        sourceNotFound: "Source \"{source}\" not found.",
        noUrl: "No URL assigned.",
        noVoiceId: "No Voicemod voice ID entered.",
        voicemodActionDone: "Voicemod action executed.",
        voicemodActionFailed: "Voicemod action failed.",
        voicemodActionLog: "Voicemod action: {action}",
        voicemodVoicesLoaded: "Voicemod voices loaded: {count}",
        noVoicemodVoices: "No Voicemod voices found.",
        voicemodVoicesLoadFailed: "Voicemod voices could not be loaded.",
        voicemodError: "Voicemod error: {error}",
        voicemodStatusChecked: "Voicemod status checked",
        voicemodReachableToast: "Voicemod is reachable.",
        voicemodNotReachable: "Voicemod is not reachable.",
        voicemodVoiceLoaded: "Voicemod voice loaded.",
        voicemodVoiceLoadedLog: "Voicemod voice loaded: {voice}",
        voicemodVoiceLoadFailed: "Voicemod voice could not be loaded.",
        voicemodApiKeySaved: "Voicemod API key saved",
        spotifyActionFailed: "Spotify action failed.",
        spotifyTokenMissing: "Please paste a Spotify token.",
        spotifyTokenSaved: "Spotify token saved",
        spotifyGenericError: "Spotify error.",
        noLogEntries: "No entries yet.",
        spotifyClientIdMissing: "Spotify Client ID is missing in .env.",
        spotifyLoginClientIdMissing: "Spotify login cancelled: Client ID missing",
        spotifyRedirectHttpsRequired: "Spotify login needs HTTPS. HTTP is only allowed with 127.0.0.1 or ::1.",
        spotifyLoginInvalidRedirect: "Spotify login cancelled: invalid redirect URI {uri}",
        spotifyLoginStartFailed: "Spotify login could not be started.",
        spotifyLoginFailed: "Spotify login failed: {error}",
        spotifyCodeVerifierMissing: "Spotify login failed: code verifier missing.",
        spotifyLoginError: "Spotify login error: {error}",
        spotifyAccessTokenFailed: "Spotify access token could not be fetched. See console.",
        spotifyRedirectProcessingFailed: "Spotify login processing failed."
    }
};

function sdText(key, fallback, values = {}) {
    const dictionary = STREAM_DECK_LANGUAGE.startsWith("en") ? STREAM_DECK_I18N.en : {};
    return String(dictionary[key] || fallback).replace(/\{(\w+)\}/g, (_match, name) => values[name] ?? "");
}

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
let voicemodVoices = [];
let voicemodVoicesLoaded = false;
let voicemodVoicesLoading = false;

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
    voicemodStatusDot: $("voicemod-status-dot"),
    voicemodStatusText: $("voicemod-status-text"),
    voicemodStatusDetail: $("voicemod-status-detail"),
    voicemodSystemStatus: $("voicemod-system-status"),
    voicemodApiKeyInput: $("voicemod-api-key-input"),
    toggleVoicemodApiKeyBtn: $("toggle-voicemod-api-key-btn"),
    saveVoicemodApiKeyBtn: $("save-voicemod-api-key-btn"),
    clearVoicemodApiKeyBtn: $("clear-voicemod-api-key-btn"),
    voicemodVoicesSelect: $("voicemod-voices-select"),
    loadVoicemodVoicesBtn: $("load-voicemod-voices-btn"),
    refreshVoicemodStatusBtn: $("refresh-voicemod-status-btn"),
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
    editVoicemodAction: $("edit-voicemod-action"),
    editVoicemodVoiceId: $("edit-voicemod-voice-id"),
    editVoicemodRandomMode: $("edit-voicemod-random-mode"),
    loadEditorVoicemodVoicesBtn: $("load-editor-voicemod-voices-btn"),
    editUrl: $("edit-url"),
    obsRequestFields: $("obs-request-fields"),
    obsSceneFields: $("obs-scene-fields"),
    obsSourceFields: $("obs-source-fields"),
    obsAudioFields: $("obs-audio-fields"),
    spotifyFields: $("spotify-fields"),
    voicemodFields: $("voicemod-fields"),
    voicemodVoiceIdField: $("voicemod-voice-id-field"),
    voicemodRandomModeField: $("voicemod-random-mode-field"),
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
    updateVoicemodConfiguredState();
    refreshSpotifyState();
    startSpotifyAutoRefresh();
    startSpotifyProgressTicker();
});

function loadState() {
    const savedButtons = localStorage.getItem(STORAGE_KEYS.buttons);
    const savedAddress = localStorage.getItem(STORAGE_KEYS.obsAddress);
    const savedPassword = localStorage.getItem(STORAGE_KEYS.obsPassword);
    const savedVoicemodApiKey = localStorage.getItem(STORAGE_KEYS.voicemodApiKey);
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
    elements.voicemodApiKeyInput.value = savedVoicemodApiKey || "";
    elements.obsAddressPreview.textContent = elements.obsAddress.value || "-";
}

function bindEvents() {
    elements.togglePasswordBtn.addEventListener("click", togglePasswordVisibility);
    elements.connectBtn.addEventListener("click", connectOrDisconnectObs);
    elements.connectBtn.addEventListener("pointerenter", warmObsWebSocketModule, { once: true });
    elements.connectBtn.addEventListener("focus", warmObsWebSocketModule, { once: true });
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
    elements.editVoicemodAction.addEventListener("change", updateVoicemodEditorFields);

    elements.spotifyTokenBtn.addEventListener("click", spotifyLogin);
    elements.closeSpotifyBtn.addEventListener("click", closeSpotifyModal);
    elements.saveSpotifyTokenBtn.addEventListener("click", saveSpotifyToken);
    elements.clearSpotifyTokenBtn.addEventListener("click", clearSpotifyToken);
    elements.toggleVoicemodApiKeyBtn.addEventListener("click", toggleVoicemodApiKeyVisibility);
    elements.saveVoicemodApiKeyBtn.addEventListener("click", saveVoicemodApiKey);
    elements.clearVoicemodApiKeyBtn.addEventListener("click", clearVoicemodApiKey);
    elements.loadVoicemodVoicesBtn.addEventListener("click", loadVoicemodVoices);
    elements.loadEditorVoicemodVoicesBtn.addEventListener("click", loadVoicemodVoices);
    elements.refreshVoicemodStatusBtn.addEventListener("click", refreshVoicemodStatus);
    elements.voicemodVoicesSelect.addEventListener("change", loadSelectedVoicemodVoice);

    elements.showLogBtn.addEventListener("click", openLogModal);
    elements.closeLogBtn.addEventListener("click", closeLogModal);

    document.querySelectorAll("[data-spotify-control]").forEach((btn) => {
        btn.addEventListener("click", async () => {
            const action = btn.dataset.spotifyControl;
            try {
                await executeSpotifyAction(action);
                await refreshSpotifyState();
            } catch (error) {
                showToast(error.message || sdText("spotifyActionFailed", "Spotify Aktion fehlgeschlagen."));
                addLog(sdText("spotifyLoginError", "Spotify Fehler: {error}", { error: error.message || sdText("unknownError", "Unbekannter Fehler") }));
            }
        });
    });

    document.querySelectorAll("[data-voicemod-quick]").forEach((btn) => {
        btn.addEventListener("click", async () => {
            const action = btn.dataset.voicemodQuick;

            try {
                const payload = buildVoicemodPayload(action);
                await executeVoicemodAction(action, payload);
                addLog(sdText("voicemodActionLog", "Voicemod Aktion: {action}", { action }));
                showToast(sdText("voicemodActionDone", "Voicemod Aktion ausgeführt."));
            } catch (error) {
                setVoicemodErrorState(error.message || sdText("voicemodActionFailed", "Voicemod Aktion fehlgeschlagen."));
                addLog(sdText("voicemodError", "Voicemod Fehler: {error}", { error: error.message || sdText("unknownError", "Unbekannter Fehler") }));
                showToast(error.message || sdText("voicemodActionFailed", "Voicemod Aktion fehlgeschlagen."));
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
    elements.editModeStatus.textContent = editMode ? sdText("on", "An") : sdText("off", "Aus");
}

function toggleEditMode() {
    editMode = !editMode;
    updateEditModeUI();

    renderButtons();
    addLog(editMode ? sdText("editModeEnabled", "Bearbeiten-Modus aktiviert") : sdText("editModeDisabled", "Bearbeiten-Modus deaktiviert"));
    showToast(editMode ? `${sdText("editModeEnabled", "Bearbeiten-Modus aktiviert")}.` : `${sdText("editModeDisabled", "Bearbeiten-Modus deaktiviert")}.`);
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
        showToast(sdText("fullscreenFallback", "Browser-Vollbild nicht verfügbar. Deck-Ansicht aktiviert."));
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
    if (!confirm(sdText("resetButtonsConfirm", "Willst du wirklich alle Buttons zurücksetzen?"))) return;

    buttons = [...defaultButtons];
    saveButtonsToStorage();
    renderButtons();
    addLog(sdText("buttonsReset", "Buttons wurden zurückgesetzt"));
    showToast(`${sdText("buttonsReset", "Buttons wurden zurückgesetzt")}.`);
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
    ensureVoicemodVoiceOption(button.voicemodVoiceId);
    elements.editVoicemodAction.value = button.voicemodAction || "toggleVoiceChanger";
    elements.editVoicemodVoiceId.value = button.voicemodVoiceId || "";
    elements.editVoicemodRandomMode.value = button.voicemodRandomMode || VOICEMOD_DEFAULT_RANDOM_MODE;
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
    if (type === "voicemod") {
        elements.voicemodFields.classList.remove("hidden");
        updateVoicemodEditorFields();
    }
    if (type === "open-url") elements.urlFields.classList.remove("hidden");
}

function hideAllDynamicSections() {
    elements.obsRequestFields.classList.add("hidden");
    elements.obsSceneFields.classList.add("hidden");
    elements.obsSourceFields.classList.add("hidden");
    elements.obsAudioFields.classList.add("hidden");
    elements.spotifyFields.classList.add("hidden");
    elements.voicemodFields.classList.add("hidden");
    elements.urlFields.classList.add("hidden");
}

function updateVoicemodEditorFields() {
    const action = elements.editVoicemodAction.value;
    elements.voicemodVoiceIdField.classList.toggle("hidden", action !== "loadVoice");
    elements.voicemodRandomModeField.classList.toggle("hidden", action !== "selectRandomVoice");

    if (action === "loadVoice" && !elements.editVoicemodVoiceId.value && elements.voicemodVoicesSelect.value) {
        ensureVoicemodVoiceOption(elements.voicemodVoicesSelect.value);
        elements.editVoicemodVoiceId.value = elements.voicemodVoicesSelect.value;
    }

    if (action === "loadVoice" && hasVoicemodApiKey() && !voicemodVoicesLoaded && !voicemodVoicesLoading) {
        loadVoicemodVoices({ silent: true });
    }
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
    } else if (actionType === "voicemod") {
        updated.voicemodAction = elements.editVoicemodAction.value;

        if (updated.voicemodAction === "loadVoice") {
            updated.voicemodVoiceId = elements.editVoicemodVoiceId.value.trim();
        } else if (updated.voicemodAction === "selectRandomVoice") {
            updated.voicemodRandomMode = elements.editVoicemodRandomMode.value || VOICEMOD_DEFAULT_RANDOM_MODE;
        }
    } else if (actionType === "open-url") {
        updated.url = elements.editUrl.value.trim();
    }

    buttons[currentEditIndex] = updated;
    saveButtonsToStorage();
    renderButtons();
    closeEditorModal();

    addLog(`${sdText("buttonSaved", "Button gespeichert")}: ${updated.title}`);
    showToast(`${sdText("buttonSaved", "Button gespeichert")}.`);
}

function deleteCurrentButton() {
    if (currentEditIndex === null) return;
    if (!confirm(sdText("deleteButtonConfirm", "Diesen Button wirklich löschen?"))) return;

    const removed = buttons[currentEditIndex];
    buttons.splice(currentEditIndex, 1);
    saveButtonsToStorage();
    renderButtons();
    closeEditorModal();

    addLog(`${sdText("buttonDeleted", "Button gelöscht")}: ${removed?.title || sdText("unknown", "Unbekannt")}`);
    showToast(`${sdText("buttonDeleted", "Button gelöscht")}.`);
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

    const previousConnectButtonHtml = elements.connectBtn.innerHTML;
    elements.connectBtn.disabled = true;
    elements.connectBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i><span>Verbinden...</span>';

    try {
        const OBSWebSocket = await loadObsWebSocketClass();
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
        obsWebSocketClassPromise = null;
        updateObsUI();
        addLog(sdText("obsConnectionFailed", "OBS Verbindung fehlgeschlagen"));
        showToast(`${sdText("obsConnectionFailed", "OBS Verbindung fehlgeschlagen")}.`);
        console.error(error);
    } finally {
        elements.connectBtn.disabled = false;
        if (obsConnected) {
            updateObsUI();
        } else {
            elements.connectBtn.innerHTML = previousConnectButtonHtml;
        }
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
        elements.obsStatusLabel.textContent = sdText("connected", "Verbunden");
        elements.connectBtn.innerHTML = '<i class="fa-solid fa-link-slash"></i><span>Trennen</span>';
    } else {
        elements.obsStatusDot.classList.remove("online");
        elements.obsStatusLabel.textContent = sdText("disconnected", "Nicht verbunden");
        elements.connectBtn.innerHTML = '<i class="fa-solid fa-link"></i><span>Verbinden</span>';
        elements.obsVersionText.textContent = "-";
    }
}

function requireObsConnection() {
    if (!obsConnected || !obs) {
        throw new Error(sdText("obsNotConnected", "OBS ist nicht verbunden."));
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
                addLog(sdText("obsRequestExecuted", "OBS Request ausgeführt: {title}", { title: button.title }));
                showToast(sdText("actionExecuted", "Aktion ausgeführt: {title}", { title: button.title }));
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

            case "voicemod":
                await executeVoicemodButton(button);
                addLog(`Voicemod Aktion: ${button.voicemodAction || button.title}`);
                showToast(`Voicemod Aktion: ${button.title}`);
                break;

            case "open-url":
                openUrl(button.url);
                addLog(sdText("urlOpened", "URL geöffnet: {url}", { url: button.url }));
                showToast(sdText("opened", "Geöffnet: {title}", { title: button.title }));
                break;

            default:
                addLog(sdText("noAction", "Keine Aktion hinterlegt: {title}", { title: button.title }));
                showToast("Dieser Button hat noch keine Aktion.");
                break;
        }
    } catch (error) {
        addLog(sdText("buttonError", "Fehler bei \"{title}\": {error}", { title: button.title, error: error.message || sdText("unknownError", "Unbekannter Fehler") }));
        showToast(error.message || sdText("actionFailed", "Aktion fehlgeschlagen."));
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
    if (!requestName) throw new Error(sdText("noObsRequest", "Kein OBS Request gewählt."));
    await obs.call(requestName);
}

function normalizeAudioStep(value) {
    const parsed = Number.parseFloat(value);
    if (!Number.isFinite(parsed) || parsed <= 0) return 5;
    return Math.min(parsed, 30);
}

async function executeObsAudioAction(inputName, action, stepDb = 5) {
    requireObsConnection();
    if (!inputName) throw new Error(sdText("noAudioDevice", "Kein Audiogerät eingetragen."));

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

    const sourceItem = await findObsSceneItem(sceneName, sourceName);

    if (!sourceItem) {
        throw new Error(sdText("sourceNotFound", "Quelle \"{source}\" nicht gefunden.", { source: sourceName }));
    }

    const enabledData = await obs.call("GetSceneItemEnabled", {
        sceneName: sourceItem.sceneName,
        sceneItemId: sourceItem.item.sceneItemId
    });

    await obs.call("SetSceneItemEnabled", {
        sceneName: sourceItem.sceneName,
        sceneItemId: sourceItem.item.sceneItemId,
        sceneItemEnabled: !enabledData.sceneItemEnabled
    });
}

async function findObsSceneItem(sceneName, sourceName, visitedScenes = new Set()) {
    if (visitedScenes.has(sceneName)) {
        return null;
    }

    visitedScenes.add(sceneName);
    const sceneItems = await obs.call("GetSceneItemList", { sceneName });

    for (const item of sceneItems.sceneItems || []) {
        if (item.sourceName === sourceName) {
            return { sceneName, item };
        }

        if (item.isGroup) {
            const nestedItem = await findObsSceneItem(item.sourceName, sourceName, visitedScenes);
            if (nestedItem) {
                return nestedItem;
            }
        }
    }

    return null;
}

function openUrl(url) {
    if (!url) throw new Error(sdText("noUrl", "Keine URL hinterlegt."));

    const normalized = /^https?:\/\//i.test(url) ? url : `https://${url}`;
    window.open(normalized, "_blank", "noopener,noreferrer");
}

async function executeVoicemodButton(button) {
    const action = button.voicemodAction || "toggleVoiceChanger";
    const payload = buildVoicemodPayload(action, button);
    await executeVoicemodAction(action, payload);
}

function buildVoicemodPayload(action, source = {}) {
    if (action === "loadVoice") {
        const voiceID = (source.voicemodVoiceId || source.voiceID || "").trim();

        if (!voiceID) {
            throw new Error(sdText("noVoiceId", "Keine Voicemod Voice-ID eingetragen."));
        }

        return { voiceID };
    }

    if (action === "selectRandomVoice") {
        return {
            mode: source.voicemodRandomMode || source.mode || VOICEMOD_DEFAULT_RANDOM_MODE
        };
    }

    return {};
}

async function executeVoicemodAction(action, payload = {}) {
    const apiKey = getVoicemodApiKey();

    if (!hasVoicemodApiKey()) {
        throw new Error("Kein Voicemod API-Key verbunden.");
    }

    if (!VOICEMOD_ACTION_URL) {
        throw new Error("Voicemod API-Endpunkt fehlt.");
    }

    setVoicemodBusyState();

    const response = await fetch(VOICEMOD_ACTION_URL, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie("csrftoken")
        },
        body: JSON.stringify({ action, payload, apiKey })
    });

    const data = await response.json().catch(() => null);

    if (!response.ok || data?.status !== "ok") {
        const message = data?.message || sdText("voicemodActionFailed", "Voicemod Aktion fehlgeschlagen.");
        throw new Error(message);
    }

    setVoicemodConnectedState(data);
    return data;
}

async function loadVoicemodVoices(options = {}) {
    const { silent = false } = options;

    if (voicemodVoicesLoading) return;

    voicemodVoicesLoading = true;

    try {
        const data = await executeVoicemodAction("getVoices");
        const voices = extractVoicemodVoices(data);
        renderVoicemodVoices(voices);

        if (!silent) {
            addLog(sdText("voicemodVoicesLoaded", "Voicemod Voices geladen: {count}", { count: voices.length }));
            showToast(voices.length ? `${sdText("voicemodVoicesLoaded", "Voicemod Voices geladen: {count}", { count: voices.length })}.` : sdText("noVoicemodVoices", "Keine Voicemod Voices gefunden."));
        }
    } catch (error) {
        setVoicemodErrorState(error.message || sdText("voicemodVoicesLoadFailed", "Voicemod Voices konnten nicht geladen werden."));

        if (silent) {
            console.warn("Voicemod Voices konnten nicht geladen werden.", error);
        } else {
            addLog(sdText("voicemodError", "Voicemod Fehler: {error}", { error: error.message || sdText("unknownError", "Unbekannter Fehler") }));
            showToast(error.message || sdText("voicemodVoicesLoadFailed", "Voicemod Voices konnten nicht geladen werden."));
        }
    } finally {
        voicemodVoicesLoading = false;
    }
}

async function refreshVoicemodStatus() {
    try {
        await executeVoicemodAction("getVoiceChangerStatus");
        addLog(sdText("voicemodStatusChecked", "Voicemod Status geprüft"));
        showToast(sdText("voicemodReachableToast", "Voicemod ist erreichbar."));
    } catch (error) {
        setVoicemodErrorState(error.message || sdText("voicemodNotReachable", "Voicemod ist nicht erreichbar."));
        addLog(sdText("voicemodError", "Voicemod Fehler: {error}", { error: error.message || sdText("unknownError", "Unbekannter Fehler") }));
        showToast(error.message || sdText("voicemodNotReachable", "Voicemod ist nicht erreichbar."));
    }
}

async function loadSelectedVoicemodVoice() {
    const voiceID = elements.voicemodVoicesSelect.value;

    if (!voiceID) return;

    try {
        await executeVoicemodAction("loadVoice", { voiceID });
        addLog(sdText("voicemodVoiceLoadedLog", "Voicemod Voice geladen: {voice}", { voice: voiceID }));
        showToast(sdText("voicemodVoiceLoaded", "Voicemod Voice geladen."));
    } catch (error) {
        setVoicemodErrorState(error.message || sdText("voicemodVoiceLoadFailed", "Voicemod Voice konnte nicht geladen werden."));
        addLog(sdText("voicemodError", "Voicemod Fehler: {error}", { error: error.message || sdText("unknownError", "Unbekannter Fehler") }));
        showToast(error.message || sdText("voicemodVoiceLoadFailed", "Voicemod Voice konnte nicht geladen werden."));
    }
}

function extractVoicemodVoices(data) {
    const messages = data?.response?.messages || [];

    for (const message of messages) {
        const voices = message?.actionObject?.voices || message?.payload?.voices;

        if (Array.isArray(voices)) {
            return voices;
        }
    }

    return [];
}

function renderVoicemodVoices(voices) {
    const selectedSidebarVoice = elements.voicemodVoicesSelect.value;
    const selectedEditorVoice = elements.editVoicemodVoiceId.value;

    voicemodVoices = voices
        .filter((voice) => voice?.enabled !== false)
        .map((voice) => ({
            id: String(voice.id || "").trim(),
            name: String(voice.friendlyName || voice.name || voice.id || "").trim()
        }))
        .filter((voice) => voice.id)
        .sort((a, b) => a.name.localeCompare(b.name));

    voicemodVoicesLoaded = true;

    renderVoicemodVoiceSelect(elements.voicemodVoicesSelect, selectedSidebarVoice, "Voice auswaehlen...");
    renderVoicemodVoiceSelect(elements.editVoicemodVoiceId, selectedEditorVoice, "Voice auswaehlen...");
}

function renderVoicemodVoiceSelect(select, selectedValue, placeholder) {
    const value = selectedValue || "";
    select.innerHTML = "";

    const placeholderOption = document.createElement("option");
    placeholderOption.value = "";
    placeholderOption.textContent = placeholder;
    select.appendChild(placeholderOption);

    if (value && !voicemodVoices.some((voice) => voice.id === value)) {
        const savedOption = document.createElement("option");
        savedOption.value = value;
        savedOption.textContent = sdText("savedValue", "Gespeichert: {value}", { value });
        select.appendChild(savedOption);
    }

    voicemodVoices.forEach((voice) => {
        const option = document.createElement("option");
        option.value = voice.id;
        option.textContent = voice.name || voice.id;
        select.appendChild(option);
    });

    select.value = value;
}

function ensureVoicemodVoiceOption(voiceId) {
    const value = String(voiceId || "").trim();

    if (!value) return;

    [elements.voicemodVoicesSelect, elements.editVoicemodVoiceId].forEach((select) => {
        if ([...select.options].some((option) => option.value === value)) {
            return;
        }

        const option = document.createElement("option");
        option.value = value;
        option.textContent = sdText("savedValue", "Gespeichert: {value}", { value });
        select.appendChild(option);
    });
}

function getVoicemodApiKey() {
    return elements.voicemodApiKeyInput.value.trim();
}

function hasVoicemodApiKey() {
    return Boolean(getVoicemodApiKey());
}

function saveVoicemodApiKey() {
    const apiKey = getVoicemodApiKey();

    if (!apiKey) {
        showToast("Bitte Voicemod API-Key eintragen.");
        return;
    }

    localStorage.setItem(STORAGE_KEYS.voicemodApiKey, apiKey);
    updateVoicemodConfiguredState();
    addLog(sdText("voicemodApiKeySaved", "Voicemod API-Key gespeichert"));
    showToast(`${sdText("voicemodApiKeySaved", "Voicemod API-Key gespeichert")}.`);
}

function clearVoicemodApiKey() {
    localStorage.removeItem(STORAGE_KEYS.voicemodApiKey);
    elements.voicemodApiKeyInput.value = "";
    updateVoicemodConfiguredState();
    addLog("Voicemod API-Key entfernt");
    showToast("Voicemod API-Key entfernt.");
}

function toggleVoicemodApiKeyVisibility() {
    if (elements.voicemodApiKeyInput.type === "password") {
        elements.voicemodApiKeyInput.type = "text";
        elements.toggleVoicemodApiKeyBtn.innerHTML = '<i class="fa-regular fa-eye-slash"></i>';
    } else {
        elements.voicemodApiKeyInput.type = "password";
        elements.toggleVoicemodApiKeyBtn.innerHTML = '<i class="fa-regular fa-eye"></i>';
    }
}

function updateVoicemodConfiguredState() {
    if (getVoicemodApiKey()) {
        elements.voicemodStatusDot.classList.remove("online");
        elements.voicemodStatusText.textContent = sdText("ready", "Bereit");
        elements.voicemodStatusDetail.textContent = sdText("apiKeySavedLocal", "API-Key lokal gespeichert");
        elements.voicemodSystemStatus.textContent = sdText("ready", "Bereit");
        setVoicemodControlsDisabled(false);
    } else {
        elements.voicemodStatusDot.classList.remove("online");
        elements.voicemodStatusText.textContent = sdText("missingApiKey", "API-Key fehlt");
        elements.voicemodStatusDetail.textContent = sdText("saveApiKeyHint", "API-Key eintragen und speichern");
        elements.voicemodSystemStatus.textContent = sdText("missing", "Fehlt");
        setVoicemodControlsDisabled(false);
    }
}

function setVoicemodBusyState() {
    elements.voicemodStatusDot.classList.remove("online");
    elements.voicemodStatusText.textContent = sdText("sending", "Sende...");
    elements.voicemodSystemStatus.textContent = sdText("active", "Aktiv");
}

function setVoicemodConnectedState(data) {
    const port = data?.response?.port;
    elements.voicemodStatusDot.classList.add("online");
    elements.voicemodStatusText.textContent = sdText("connected", "Verbunden");
    elements.voicemodStatusDetail.textContent = port ? sdText("localPort", "Lokaler Port {port}", { port }) : sdText("voicemodReachable", "Voicemod erreichbar");
    elements.voicemodSystemStatus.textContent = "OK";
}

function setVoicemodErrorState(message) {
    elements.voicemodStatusDot.classList.remove("online");
    elements.voicemodStatusText.textContent = sdText("error", "Fehler");
    elements.voicemodStatusDetail.textContent = message;
    elements.voicemodSystemStatus.textContent = sdText("error", "Fehler");
}

function setVoicemodControlsDisabled(disabled) {
    elements.loadVoicemodVoicesBtn.disabled = disabled;
    elements.loadEditorVoicemodVoicesBtn.disabled = disabled;
    elements.refreshVoicemodStatusBtn.disabled = disabled;
    elements.voicemodVoicesSelect.disabled = disabled;

    document.querySelectorAll("[data-voicemod-quick]").forEach((button) => {
        button.disabled = disabled;
    });
}

function getCookie(name) {
    const cookie = document.cookie
        .split(";")
        .map((item) => item.trim())
        .find((item) => item.startsWith(`${name}=`));

    return cookie ? decodeURIComponent(cookie.split("=").slice(1).join("=")) : "";
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
        showToast(sdText("spotifyTokenMissing", "Bitte einen Spotify Token einfügen."));
        return;
    }

    localStorage.setItem(STORAGE_KEYS.spotifyToken, token);
    closeSpotifyModal();
    addLog(sdText("spotifyTokenSaved", "Spotify Token gespeichert"));
    showToast(`${sdText("spotifyTokenSaved", "Spotify Token gespeichert")}.`);
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
    if (response.status === 401) return sdText("tokenInvalid", "Spotify Token ungültig oder abgelaufen.");
    if (response.status === 403) return sdText("accessDenied", "Spotify Zugriff verweigert.");
    if (response.status === 404) return sdText("noActiveDevice", "Kein aktives Spotify Gerät gefunden.");
    if (response.status === 429) return sdText("rateLimited", "Spotify Rate Limit erreicht.");

    try {
        const data = await response.json();
        return data?.error?.message || sdText("spotifyGenericError", "Spotify Fehler.");
    } catch {
        return sdText("spotifyGenericError", "Spotify Fehler.");
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
            elements.spotifyStatusText.textContent = sdText("connected", "Verbunden");
            elements.spotifySystemStatus.textContent = "OK";
            elements.spotifyTrackTitle.textContent = sdText("noActivePlayback", "Keine aktive Wiedergabe");
            elements.spotifyTrackArtist.textContent = "-";
            elements.spotifyCurrentTime.textContent = "0:00";
            elements.spotifyTotalTime.textContent = "0:00";
            elements.spotifyProgressFill.style.width = "0%";
            elements.spotifyCover.innerHTML = '<i class="fa-brands fa-spotify"></i>';
            updateSpotifyToggleButton(false, true);
            return;
        }

        elements.spotifyStatusDot.classList.add("online");
        elements.spotifyStatusText.textContent = state.is_playing ? sdText("playing", "Wird abgespielt") : sdText("paused", "Pausiert");
        elements.spotifySystemStatus.textContent = "OK";

        elements.spotifyTrackTitle.textContent = state.item.name || sdText("unknown", "Unbekannt");
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
        elements.spotifyStatusText.textContent = sdText("error", "Fehler");
        elements.spotifySystemStatus.textContent = sdText("error", "Fehler");
        elements.spotifyTrackTitle.textContent = sdText("spotifyUnavailable", "Spotify nicht verfügbar");
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
    elements.spotifyStatusText.textContent = sdText("disconnected", "Nicht verbunden");
    elements.spotifySystemStatus.textContent = "-";
    elements.spotifyTrackTitle.textContent = sdText("noTitle", "Kein Titel");
    elements.spotifyTrackArtist.textContent = sdText("noArtist", "Kein Künstler");
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
        elements.logList.innerHTML = `<div class="log-entry"><span class="log-time">-</span>${sdText("noLogEntries", "Noch keine Einträge vorhanden.")}</div>`;
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
        showToast(sdText("spotifyClientIdMissing", "Spotify Client-ID fehlt in der .env."));
        addLog(sdText("spotifyLoginClientIdMissing", "Spotify Login abgebrochen: Client-ID fehlt"));
        return;
    }

    if (!isSpotifyRedirectUriAllowed(SPOTIFY_REDIRECT_URI)) {
        const message = sdText("spotifyRedirectHttpsRequired", "Spotify Login braucht HTTPS. HTTP ist nur mit 127.0.0.1 oder ::1 erlaubt.");
        console.warn(message, SPOTIFY_REDIRECT_URI);
        showToast(message);
        addLog(sdText("spotifyLoginInvalidRedirect", "Spotify Login abgebrochen: ungültige Redirect URI {uri}", { uri: SPOTIFY_REDIRECT_URI }));
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
        showToast(error.message || sdText("spotifyLoginStartFailed", "Spotify Login konnte nicht gestartet werden."));
        addLog(sdText("spotifyLoginError", "Spotify Login Fehler: {error}", { error: error.message || sdText("unknownError", "Unbekannter Fehler") }));
    }
}

async function handleSpotifyRedirect() {
    const urlParams = new URLSearchParams(window.location.search);
    const code = urlParams.get("code");
    const error = urlParams.get("error");

    if (error) {
        console.error("Spotify Login Fehler:", error);
        showToast(sdText("spotifyLoginFailed", "Spotify Login fehlgeschlagen: {error}", { error }));
        return;
    }

    if (!code) return;

    const codeVerifier = localStorage.getItem(SPOTIFY_CODE_VERIFIER_KEY);

    if (!codeVerifier) {
        showToast(sdText("spotifyCodeVerifierMissing", "Spotify Login fehlgeschlagen: Code Verifier fehlt."));
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
            showToast(sdText("spotifyAccessTokenFailed", "Spotify Access Token konnte nicht geholt werden. Siehe Konsole."));
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
        showToast(sdText("spotifyRedirectProcessingFailed", "Spotify Login-Verarbeitung fehlgeschlagen."));
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
