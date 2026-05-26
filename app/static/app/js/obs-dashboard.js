import OBSWebSocket from "https://cdn.jsdelivr.net/npm/obs-websocket-js@5.0.6/+esm";

console.log("script.js wurde geladen");

const obs = new OBSWebSocket();
const obsDashboardPage = document.querySelector(".obs-dashboard-page");
const USER_STORAGE_SUFFIX = obsDashboardPage?.dataset.userId ? `_user_${obsDashboardPage.dataset.userId}` : "";
const storageKey = (key) => `${key}${USER_STORAGE_SUFFIX}`;

const urlInput = document.getElementById("url");
const passwordInput = document.getElementById("password");
const connectBtn = document.getElementById("connectBtn");

const statusText = document.getElementById("status");
const connectionDot = document.getElementById("connectionDot");

const sceneButtons = document.getElementById("sceneButtons");
const sceneCount = document.getElementById("sceneCount");

const sourceButtons = document.getElementById("sourceButtons");
const sourceCount = document.getElementById("sourceCount");
const currentSceneTitle = document.getElementById("currentSceneTitle");

const audioMixer = document.getElementById("audioMixer");
const audioCount = document.getElementById("audioCount");

const toggleRecordBtn = document.getElementById("toggleRecordBtn");
const toggleStreamBtn = document.getElementById("toggleStreamBtn");
const refreshBtn = document.getElementById("refreshBtn");
const fullscreenBtn = document.getElementById("fullscreenBtn");
const rememberConnection = document.getElementById("rememberConnection");

let connected = false;
let currentSceneName = null;
let audioRefreshTimer = null;

function updateControlButtons() {
    toggleRecordBtn.disabled = !connected;
    toggleStreamBtn.disabled = !connected;
    refreshBtn.disabled = !connected;

    const recordSmall = toggleRecordBtn.querySelector("small");
    const streamSmall = toggleStreamBtn.querySelector("small");
    const refreshSmall = refreshBtn.querySelector("small");

    if (connected) {
        if (recordSmall) recordSmall.textContent = "Start / Stop";
        if (streamSmall) streamSmall.textContent = "Start / Stop";
        if (refreshSmall) refreshSmall.textContent = "Szenen aktualisieren";
    } else {
        if (recordSmall) recordSmall.textContent = "Erst mit OBS verbinden";
        if (streamSmall) streamSmall.textContent = "Erst mit OBS verbinden";
        if (refreshSmall) refreshSmall.textContent = "Erst mit OBS verbinden";
    }
}

updateControlButtons();

function setStatus(text, mode = "offline") {
    statusText.textContent = text;

    connectionDot.classList.remove("online", "offline", "loading");
    connectionDot.classList.add(mode);
}

connectBtn.addEventListener("click", async () => {
    await connectToObs(true);
});

async function connectToObs(showAlerts = false) {
    const url = urlInput.value.trim();
    const password = passwordInput.value;

    if (!url) {
        setStatus("Keine URL eingetragen", "offline");
        return;
    }

    try {
        setStatus("Verbinde...", "loading");

        await obs.connect(url, password, {
            rpcVersion: 1
        });

        connected = true;
        setStatus("Verbunden", "online");

        updateControlButtons();

        if (rememberConnection.checked) {
            localStorage.setItem(storageKey("obsDashboardRemember"), "true");
            localStorage.setItem(storageKey("obsDashboardUrl"), url);
            localStorage.setItem(storageKey("obsDashboardPassword"), password);
        } else {
            localStorage.removeItem(storageKey("obsDashboardRemember"));
            localStorage.removeItem(storageKey("obsDashboardUrl"));
            localStorage.removeItem(storageKey("obsDashboardPassword"));
        }

        await loadScenes();

    } catch (error) {
        console.error("OBS Verbindung fehlgeschlagen:", error);

        connected = false;
        setStatus("Verbindung fehlgeschlagen", "offline");

        updateControlButtons();

        if (showAlerts) {
            alert(error.message || "OBS Verbindung fehlgeschlagen");
        }
    }
}

async function loadDashboard() {
    await loadScenes();
    await loadAudioMixer();
}

async function loadScenes() {
    if (!connected) return;

    try {
        const response = await obs.call("GetSceneList");

        currentSceneName = response.currentProgramSceneName;

        sceneButtons.innerHTML = "";
        sceneCount.textContent = `${response.scenes.length} Szenen`;

        response.scenes.forEach(scene => {
            const button = document.createElement("button");
            button.className = "scene-card";

            if (scene.sceneName === currentSceneName) {
                button.classList.add("active");
            }

            button.innerHTML = `
                <span class="scene-name">${escapeHtml(scene.sceneName)}</span>
                <span class="scene-label">
                    ${scene.sceneName === currentSceneName ? "Aktiv" : "Szene wechseln"}
                </span>
            `;

            button.addEventListener("click", async () => {
                await changeScene(scene.sceneName);
            });

            sceneButtons.appendChild(button);
        });

        await loadSourcesForCurrentScene();

    } catch (error) {
        console.error("Szenen konnten nicht geladen werden:", error);
        setStatus("Szenenfehler", "offline");
    }
}

async function changeScene(sceneName) {
    if (!connected) return;

    try {
        await obs.call("SetCurrentProgramScene", {
            sceneName: sceneName
        });

        currentSceneName = sceneName;
        updateActiveSceneButtons();

        await loadSourcesForCurrentScene();
        await loadAudioMixer();

    } catch (error) {
        console.error("Fehler beim Szenenwechsel:", error);
        alert("Szene konnte nicht gewechselt werden.");
    }
}

function updateActiveSceneButtons() {
    const buttons = sceneButtons.querySelectorAll(".scene-card");

    buttons.forEach(button => {
        const sceneName = button.querySelector(".scene-name")?.textContent;
        const label = button.querySelector(".scene-label");

        if (sceneName === currentSceneName) {
            button.classList.add("active");
            if (label) label.textContent = "Aktiv";
        } else {
            button.classList.remove("active");
            if (label) label.textContent = "Szene wechseln";
        }
    });
}

async function loadSourcesForCurrentScene() {
    if (!connected || !currentSceneName) {
        sourceButtons.innerHTML = `
            <div class="empty-state">
                Keine aktive Szene gefunden.
            </div>
        `;
        sourceCount.textContent = "0 Quellen";
        currentSceneTitle.textContent = "Keine Szene ausgewählt";
        return;
    }

    try {
        currentSceneTitle.textContent = `Aktuelle Szene: ${currentSceneName}`;

        const response = await obs.call("GetSceneItemList", {
            sceneName: currentSceneName
        });

        sourceButtons.innerHTML = "";
        sourceCount.textContent = `${response.sceneItems.length} Quellen`;

        if (response.sceneItems.length === 0) {
            sourceButtons.innerHTML = `
                <div class="empty-state">
                    Diese Szene hat keine Quellen.
                </div>
            `;
            return;
        }

        response.sceneItems.forEach(item => {
            const button = document.createElement("button");
            const isEnabled = item.sceneItemEnabled;

            button.className = `source-toggle-card ${isEnabled ? "enabled" : "disabled"}`;

            button.innerHTML = `
                <span class="source-toggle-name">${escapeHtml(item.sourceName)}</span>
                <span class="source-toggle-status">
                    ${isEnabled ? "Sichtbar" : "Ausgeblendet"}
                </span>
            `;

            button.addEventListener("click", async () => {
                await toggleSceneSource(item.sceneItemId, item.sourceName, !isEnabled);
            });

            sourceButtons.appendChild(button);
        });

    } catch (error) {
        console.error("Quellen konnten nicht geladen werden:", error);

        sourceButtons.innerHTML = `
            <div class="empty-state">
                Quellen konnten nicht geladen werden.
            </div>
        `;

        sourceCount.textContent = "Fehler";
    }
}

async function toggleSceneSource(sceneItemId, sourceName, enabled) {
    if (!connected || !currentSceneName) return;

    try {
        await obs.call("SetSceneItemEnabled", {
            sceneName: currentSceneName,
            sceneItemId: sceneItemId,
            sceneItemEnabled: enabled
        });

        await loadSourcesForCurrentScene();

    } catch (error) {
        console.error("Quelle konnte nicht umgeschaltet werden:", error);
        alert(`Quelle "${sourceName}" konnte nicht umgeschaltet werden.`);
    }
}

async function loadAudioMixer() {
    if (!connected) return;

    try {
        const inputResponse = await obs.call("GetInputList");

        const audioInputs = [];

        for (const input of inputResponse.inputs) {
            try {
                const volume = await obs.call("GetInputVolume", {
                    inputName: input.inputName
                });

                const mute = await obs.call("GetInputMute", {
                    inputName: input.inputName
                });

                audioInputs.push({
                    name: input.inputName,
                    volumeDb: volume.inputVolumeDb,
                    volumeMul: volume.inputVolumeMul,
                    muted: mute.inputMuted
                });

            } catch {
                // Kein Audio-Input, ignorieren
            }
        }

        renderAudioMixer(audioInputs);

    } catch (error) {
        console.error("Audio-Mixer konnte nicht geladen werden:", error);

        audioMixer.innerHTML = `
            <div class="empty-state">
                Audio-Mixer konnte nicht geladen werden.
            </div>
        `;

        audioCount.textContent = "Fehler";
    }
}

function renderAudioMixer(audioInputs) {
    audioMixer.innerHTML = "";
    audioCount.textContent = `${audioInputs.length} Audioquellen`;

    if (audioInputs.length === 0) {
        audioMixer.innerHTML = `
            <div class="empty-state">
                Keine Audioquellen gefunden.
            </div>
        `;
        return;
    }

    audioInputs.forEach(input => {
        const dbValue = Math.round(input.volumeDb * 10) / 10;

        const card = document.createElement("div");
        card.className = `audio-card ${input.muted ? "muted" : ""}`;

        card.innerHTML = `
            <div class="audio-top">
                <div class="audio-name">${escapeHtml(input.name)}</div>
                <div class="audio-volume-label">${dbValue} dB</div>
            </div>

            <input 
                class="volume-slider"
                type="range"
                min="-60"
                max="0"
                value="${dbValue}"
                step="0.5"
            >

            <div class="audio-actions">
                <button class="mute-btn ${input.muted ? "muted" : ""}">
                    ${input.muted ? "Stumm" : "Mute"}
                </button>
            </div>
        `;

        const slider = card.querySelector(".volume-slider");
        const label = card.querySelector(".audio-volume-label");
        const muteBtn = card.querySelector(".mute-btn");

        slider.addEventListener("input", () => {
            label.textContent = `${slider.value} dB`;
        });

        slider.addEventListener("change", async () => {
            await setInputVolumeDb(input.name, Number(slider.value));
            await loadAudioMixer();
        });

        slider.addEventListener("pointerup", async () => {
            await setInputVolumeDb(input.name, Number(slider.value));
        });

        muteBtn.addEventListener("click", async () => {
            await toggleInputMute(input.name);
            await loadAudioMixer();
        });

        audioMixer.appendChild(card);
    });
}

async function setInputVolumeDb(inputName, dbValue) {
    try {
        console.log("Setze Lautstärke:", inputName, dbValue, "dB");

        await obs.call("SetInputVolume", {
            inputName: inputName,
            inputVolumeDb: dbValue
        });

        console.log("Lautstärke gesetzt");

    } catch (error) {
        console.error("Lautstärke konnte nicht gesetzt werden:", inputName, error);
        alert(`Lautstärke von "${inputName}" konnte nicht geändert werden.`);
    }
}

async function toggleInputMute(inputName) {
    try {
        await obs.call("ToggleInputMute", {
            inputName: inputName
        });
    } catch (error) {
        console.error("Mute konnte nicht umgeschaltet werden:", inputName, error);
        alert(`Mute von "${inputName}" konnte nicht geändert werden.`);
    }
}

toggleRecordBtn.addEventListener("click", async () => {
    if (!connected) {
        alert("Erst mit OBS verbinden.");
        return;
    }

    try {
        await obs.call("ToggleRecord");
    } catch (error) {
        console.error("Fehler bei Aufnahme:", error);
        alert("Aufnahme konnte nicht gestartet/gestoppt werden.");
    }
});

toggleStreamBtn.addEventListener("click", async () => {
    if (!connected) {
        alert("Erst mit OBS verbinden.");
        return;
    }

    try {
        await obs.call("ToggleStream");
    } catch (error) {
        console.error("Fehler beim Stream:", error);
        alert("Stream konnte nicht gestartet/gestoppt werden.");
    }
});

refreshBtn.addEventListener("click", async () => {
    if (!connected) {
        alert("Erst mit OBS verbinden.");
        return;
    }

    await loadDashboard();
});

fullscreenBtn.addEventListener("click", async () => {
    try {
        if (!document.fullscreenElement) {
            await document.documentElement.requestFullscreen();
        } else {
            await document.exitFullscreen();
        }
    } catch (error) {
        console.error("Vollbild nicht möglich:", error);
    }
});

obs.on("CurrentProgramSceneChanged", async event => {
    currentSceneName = event.sceneName;
    updateActiveSceneButtons();
    await loadSourcesForCurrentScene();
    await loadAudioMixer();
});

obs.on("SceneItemEnableStateChanged", async event => {
    if (event.sceneName === currentSceneName) {
        await loadSourcesForCurrentScene();
    }
});

obs.on("InputVolumeChanged", async () => {
    await loadAudioMixer();
});

obs.on("InputMuteStateChanged", async () => {
    await loadAudioMixer();
});

obs.on("ConnectionClosed", () => {
    connected = false;
    setStatus("Verbindung getrennt", "offline");
    updateControlButtons();

    sceneCount.textContent = "0 Szenen";
    sourceCount.textContent = "0 Quellen";
    audioCount.textContent = "0 Audioquellen";
    currentSceneTitle.textContent = "Keine Szene ausgewählt";

    sceneButtons.innerHTML = `
        <div class="empty-state">
            Verbindung getrennt.
        </div>
    `;

    sourceButtons.innerHTML = `
        <div class="empty-state">
            Verbindung getrennt.
        </div>
    `;

    audioMixer.innerHTML = `
        <div class="empty-state">
            Verbindung getrennt.
        </div>
    `;
});

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

document.addEventListener("DOMContentLoaded", async () => {
    const savedRemember = localStorage.getItem(storageKey("obsDashboardRemember")) === "true";
    const savedUrl = localStorage.getItem(storageKey("obsDashboardUrl"));
    const savedPassword = localStorage.getItem(storageKey("obsDashboardPassword"));

    if (savedUrl) {
        urlInput.value = savedUrl;
    }

    if (savedPassword) {
        passwordInput.value = savedPassword;
    }

    rememberConnection.checked = savedRemember;

    if (savedRemember && savedUrl) {
        setTimeout(async () => {
            await connectToObs(false);
        }, 300);
    }
});
