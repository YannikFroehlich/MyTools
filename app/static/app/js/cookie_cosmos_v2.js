(function () {
    const root = document.querySelector(".cc2-page");
    if (!root) return;

    const ui = {
        loader: document.getElementById("cc2Loader"),
        loaderBar: document.getElementById("cc2LoaderBar"),
        loaderText: document.getElementById("cc2LoaderText"),
        shell: document.getElementById("cc2Shell"),
        saveHint: document.getElementById("cc2SaveHint"),
        brandCookie: document.getElementById("cc2BrandCookie"),
        cloudSaveButton: document.getElementById("cc2CloudSaveButton"),
        cloudLoadButton: document.getElementById("cc2CloudLoadButton"),
        exportButton: document.getElementById("cc2ExportButton"),
        importButton: document.getElementById("cc2ImportButton"),
        importInput: document.getElementById("cc2ImportInput"),
        resetButton: document.getElementById("cc2ResetButton"),
        cookieCount: document.getElementById("cc2CookieCount"),
        cpsCount: document.getElementById("cc2CpsCount"),
        clickPower: document.getElementById("cc2ClickPower"),
        prestigeLevel: document.getElementById("cc2PrestigeLevel"),
        stage: document.getElementById("cc2Stage"),
        stageBg: document.getElementById("cc2StageBg"),
        factoryLanes: document.getElementById("cc2FactoryLanes"),
        eventLayer: document.getElementById("cc2EventLayer"),
        cookieButton: document.getElementById("cc2CookieButton"),
        mainCookie: document.getElementById("cc2MainCookie"),
        floatingLayer: document.getElementById("cc2FloatingLayer"),
        toastLayer: document.getElementById("cc2ToastLayer"),
        buffRow: document.getElementById("cc2BuffRow"),
        prestigeName: document.getElementById("cc2PrestigeName"),
        prestigeTitle: document.getElementById("cc2PrestigeTitle"),
        prestigeDescription: document.getElementById("cc2PrestigeDescription"),
        nextCookie: document.getElementById("cc2NextCookie"),
        nextPrestigeName: document.getElementById("cc2NextPrestigeName"),
        prestigeNeed: document.getElementById("cc2PrestigeNeed"),
        prestigeProgressLabel: document.getElementById("cc2PrestigeProgressLabel"),
        prestigeProgress: document.getElementById("cc2PrestigeProgress"),
        prestigeButton: document.getElementById("cc2PrestigeButton"),
        ownedSummary: document.getElementById("cc2OwnedSummary"),
        buildingList: document.getElementById("cc2BuildingList"),
        upgradeList: document.getElementById("cc2UpgradeList"),
        eventLog: document.getElementById("cc2EventLog"),
        achievementSummary: document.getElementById("cc2AchievementSummary"),
        achievementList: document.getElementById("cc2AchievementList"),
    };

    const STORAGE_KEY = root.dataset.saveKey || "mytools-cookie-cosmos-v2";
    const LOAD_URL = root.dataset.loadUrl || "";
    const SAVE_URL = root.dataset.saveUrl || "";
    const IS_AUTHENTICATED = root.dataset.authenticated === "true";
    const EXPORT_FORMAT = "mytools-cookie-cosmos-v2-save";
    const SAVE_VERSION = 2;
    const LOCAL_SAVE_INTERVAL = 5000;
    const RENDER_INTERVAL = 180;

    const manifest = readManifest();

    const BUILDINGS = [
        { id: "hand_mixer", name: "Handmixer", desc: "Kleine Startlinie für die ersten Kekse.", icon: "fa-solid fa-hand-sparkles", baseCost: 15, baseCps: 0.12 },
        { id: "cookie_drone", name: "Cookie-Drohne", desc: "Sammelt Krümel direkt aus der Umlaufbahn.", icon: "fa-solid fa-helicopter", baseCost: 110, baseCps: 0.85 },
        { id: "dough_robot", name: "Teigroboter", desc: "Knetet ohne Pause und trifft fast jede Rezeptur.", icon: "fa-solid fa-robot", baseCost: 640, baseCps: 4.4 },
        { id: "sugar_press", name: "Zuckerpresse", desc: "Presst Sterne zu knusprigem Cookie-Staub.", icon: "fa-solid fa-compress", baseCost: 3200, baseCps: 22 },
        { id: "choco_mine", name: "Schoko-Mine", desc: "Bohrt dunkle und weiße Schokoadern an.", icon: "fa-solid fa-mountain", baseCost: 14500, baseCps: 105 },
        { id: "cookie_factory", name: "Cookie-Fabrik", desc: "Deine erste richtige Produktionshalle.", icon: "fa-solid fa-industry", baseCost: 68000, baseCps: 520 },
        { id: "orbit_oven", name: "Orbit-Ofen", desc: "Backt Cookies auf stabiler Planetenumlaufbahn.", icon: "fa-solid fa-satellite", baseCost: 340000, baseCps: 2900 },
        { id: "milky_mill", name: "Milchstraßen-Mühle", desc: "Mahlt Galaxien zu feinem Vanillemehl.", icon: "fa-solid fa-star-and-crescent", baseCost: 1900000, baseCps: 16000 },
        { id: "quantum_bakery", name: "Quanten-Bäckerei", desc: "Backt denselben Cookie in mehreren Realitäten.", icon: "fa-solid fa-atom", baseCost: 12500000, baseCps: 115000 },
        { id: "cosmos_core", name: "Cosmos Core", desc: "Das Herzstück für absurde Prestige-Runs.", icon: "fa-solid fa-sun", baseCost: 95000000, baseCps: 820000 },
    ];

    const UPGRADES = [
        { id: "butter_gloves", name: "Butterhandschuhe", desc: "+1 Cookie pro Klick.", icon: "fa-solid fa-hand", cost: 75, kind: "clickAdd", value: 1, requires: s => s.totalClicks >= 10 },
        { id: "double_tap", name: "Doppel-Biss", desc: "Klicks sind 1.8x stärker.", icon: "fa-solid fa-computer-mouse", cost: 450, kind: "clickMult", value: 1.8, requires: s => s.totalClicks >= 75 },
        { id: "white_choco_core", name: "White-Choco-Kern", desc: "Alle Produktionen +20%.", icon: "fa-solid fa-circle", cost: 1200, kind: "cpsMult", value: 1.2, requires: s => s.lifetimeCookies >= 1000 },
        { id: "drone_ai", name: "Drohnen-KI", desc: "Cookie-Drohnen produzieren doppelt.", icon: "fa-solid fa-microchip", cost: 2500, kind: "buildingMult", target: "cookie_drone", value: 2, requires: s => getBuildingCount(s, "cookie_drone") >= 5 },
        { id: "robot_arms", name: "Roboterarme", desc: "Teigroboter produzieren doppelt.", icon: "fa-solid fa-gears", cost: 7200, kind: "buildingMult", target: "dough_robot", value: 2, requires: s => getBuildingCount(s, "dough_robot") >= 5 },
        { id: "golden_sensor", name: "Goldener Sensor", desc: "Goldene Cookies erscheinen schneller.", icon: "fa-solid fa-radar", cost: 12000, kind: "goldenFrequency", value: 0.82, requires: s => s.lifetimeCookies >= 10000 },
        { id: "event_magnet", name: "Orbit-Magnet", desc: "Kleine Event-Cookies erscheinen schneller.", icon: "fa-solid fa-magnet", cost: 21000, kind: "orbitFrequency", value: 0.78, requires: s => s.eventStats.orbitCookies >= 2 || s.lifetimeCookies >= 20000 },
        { id: "cocoa_filters", name: "Kakao-Filter", desc: "Klicks sind 2.5x stärker.", icon: "fa-solid fa-filter", cost: 45000, kind: "clickMult", value: 2.5, requires: s => s.lifetimeCookies >= 35000 },
        { id: "factory_blueprint", name: "Fabrik-Blueprints", desc: "Alle Produktionen +35%.", icon: "fa-solid fa-drafting-compass", cost: 85000, kind: "cpsMult", value: 1.35, requires: s => getTotalBuildings(s) >= 25 },
        { id: "sugar_hydraulics", name: "Zucker-Hydraulik", desc: "Zuckerpressen produzieren 2.5x.", icon: "fa-solid fa-oil-well", cost: 130000, kind: "buildingMult", target: "sugar_press", value: 2.5, requires: s => getBuildingCount(s, "sugar_press") >= 10 },
        { id: "golden_recipe", name: "Gold-Rezept", desc: "Goldene Cookies geben 1.6x Belohnung.", icon: "fa-solid fa-star", cost: 250000, kind: "goldenReward", value: 1.6, requires: s => s.eventStats.goldenCookies >= 3 },
        { id: "choco_excavator", name: "Schoko-Bagger", desc: "Schoko-Minen produzieren 3x.", icon: "fa-solid fa-truck-monster", cost: 480000, kind: "buildingMult", target: "choco_mine", value: 3, requires: s => getBuildingCount(s, "choco_mine") >= 10 },
        { id: "factory_rush", name: "Rush-Schichtplan", desc: "Zufällige Fabrik-Rush-Events dauern länger.", icon: "fa-solid fa-clock", cost: 900000, kind: "factoryDuration", value: 1.35, requires: s => s.lifetimeCookies >= 500000 },
        { id: "orbit_stabilizer", name: "Orbit-Stabilisator", desc: "Orbit-Öfen produzieren 3x.", icon: "fa-solid fa-satellite-dish", cost: 1750000, kind: "buildingMult", target: "orbit_oven", value: 3, requires: s => getBuildingCount(s, "orbit_oven") >= 8 },
        { id: "cosmic_clicks", name: "Kosmische Klicks", desc: "Klicks skalieren zusätzlich mit Prestige.", icon: "fa-solid fa-meteor", cost: 4000000, kind: "prestigeClick", value: 0.12, requires: s => s.prestigeLevel >= 2 },
        { id: "milk_reactor", name: "Milch-Reaktor", desc: "Milchstraßen-Mühlen produzieren 3.5x.", icon: "fa-solid fa-flask", cost: 10500000, kind: "buildingMult", target: "milky_mill", value: 3.5, requires: s => getBuildingCount(s, "milky_mill") >= 6 },
        { id: "black_cookie_lab", name: "Black-Cookie-Labor", desc: "Alle Produktionen +75%.", icon: "fa-solid fa-vial-circle-check", cost: 30000000, kind: "cpsMult", value: 1.75, requires: s => s.prestigeLevel >= 3 || s.lifetimeCookies >= 25000000 },
        { id: "quantum_splitter", name: "Quanten-Splitter", desc: "Quanten-Bäckereien produzieren 4x.", icon: "fa-solid fa-code-branch", cost: 85000000, kind: "buildingMult", target: "quantum_bakery", value: 4, requires: s => getBuildingCount(s, "quantum_bakery") >= 5 },
        { id: "event_overclock", name: "Event-Overclock", desc: "Alle Buffs sind 20% stärker.", icon: "fa-solid fa-gauge-high", cost: 160000000, kind: "buffPower", value: 1.2, requires: s => s.eventStats.totalEvents >= 20 },
        { id: "cosmos_resonator", name: "Cosmos-Resonator", desc: "Cosmos Cores produzieren 5x.", icon: "fa-solid fa-circle-nodes", cost: 650000000, kind: "buildingMult", target: "cosmos_core", value: 5, requires: s => getBuildingCount(s, "cosmos_core") >= 3 },
    ];

    const ACHIEVEMENTS = [
        { id: "first_click", name: "Erster Biss", note: "1 Klick", icon: "fa-solid fa-cookie-bite", test: s => s.totalClicks >= 1 },
        { id: "hundred", name: "Kleines Blech", note: "100 Cookies gesamt", icon: "fa-solid fa-bread-slice", test: s => s.lifetimeCookies >= 100 },
        { id: "ten_k", name: "Backstuben-Start", note: "10K Cookies gesamt", icon: "fa-solid fa-fire-burner", test: s => s.lifetimeCookies >= 10000 },
        { id: "million", name: "Millionen-Mix", note: "1M Cookies gesamt", icon: "fa-solid fa-vault", test: s => s.lifetimeCookies >= 1000000 },
        { id: "first_building", name: "Erste Anlage", note: "1 Produktionslinie gekauft", icon: "fa-solid fa-industry", test: s => getTotalBuildings(s) >= 1 },
        { id: "hundred_buildings", name: "Fabrikpark", note: "100 Anlagen aktiv", icon: "fa-solid fa-warehouse", test: s => getTotalBuildings(s) >= 100 },
        { id: "first_upgrade", name: "Forschung läuft", note: "1 Upgrade gekauft", icon: "fa-solid fa-flask-vial", test: s => s.upgrades.length >= 1 },
        { id: "ten_upgrades", name: "Laborleitung", note: "10 Upgrades gekauft", icon: "fa-solid fa-microscope", test: s => s.upgrades.length >= 10 },
        { id: "first_golden", name: "Goldfund", note: "1 goldener Cookie", icon: "fa-solid fa-star", test: s => s.eventStats.goldenCookies >= 1 },
        { id: "golden_ten", name: "Sternenjäger", note: "10 goldene Cookies", icon: "fa-solid fa-wand-magic-sparkles", test: s => s.eventStats.goldenCookies >= 10 },
        { id: "orbit_ten", name: "Orbit-Snacker", note: "10 kleine Event-Cookies", icon: "fa-solid fa-satellite", test: s => s.eventStats.orbitCookies >= 10 },
        { id: "events_25", name: "Event-Profi", note: "25 Events genutzt", icon: "fa-solid fa-bolt", test: s => s.eventStats.totalEvents >= 25 },
        { id: "cps_100", name: "100 CPS", note: "100 Cookies pro Sekunde", icon: "fa-solid fa-gauge", test: s => computeCps(s) >= 100 },
        { id: "cps_10k", name: "10K CPS", note: "10K Cookies pro Sekunde", icon: "fa-solid fa-gauge-high", test: s => computeCps(s) >= 10000 },
        { id: "prestige_two", name: "White-Choco-Run", note: "Prestige-Level 2", icon: "fa-solid fa-circle-up", test: s => s.prestigeLevel >= 2 },
        { id: "prestige_four", name: "Cocoa Nova", note: "Prestige-Level 4", icon: "fa-solid fa-rocket", test: s => s.prestigeLevel >= 4 },
        { id: "cloud_save", name: "Cloud-Bäcker", note: "In DB gespeichert", icon: "fa-solid fa-cloud-arrow-up", test: s => s.cloudSaves >= 1 },
        { id: "exporter", name: "Save-Backup", note: "Spielstand exportiert", icon: "fa-solid fa-file-export", test: s => s.exports >= 1 },
    ];

    let state = createDefaultState();
    let buyMode = "1";
    let lastTick = Date.now();
    let lastLocalSave = 0;
    let lastRender = 0;
    let saveCooldownUntil = 0;
    let eventTimers = createEventTimers(Date.now());
    let renderQueued = false;
    let gameStarted = false;

    preloadAssets().then(() => startGame());

    function readManifest() {
        try {
            const raw = document.getElementById("cc2AssetManifest")?.textContent || "{}";
            const parsed = JSON.parse(raw);
            return {
                background: parsed.background || "",
                prestige: Array.isArray(parsed.prestige) ? parsed.prestige : [],
                forms: Array.isArray(parsed.forms) ? parsed.forms : [],
                frames: Array.isArray(parsed.frames) ? parsed.frames : [],
            };
        } catch (error) {
            console.warn("Cookie Cosmos V2 manifest konnte nicht gelesen werden.", error);
            return { background: "", prestige: [], forms: [], frames: [] };
        }
    }

    function preloadAssets() {
        const urls = [manifest.background]
            .concat(manifest.prestige.map(item => item.src))
            .concat(manifest.forms)
            .concat(manifest.frames)
            .filter(Boolean);

        if (!urls.length) {
            updateLoader(1, 1);
            return Promise.resolve();
        }

        let loaded = 0;
        updateLoader(0, urls.length);

        return Promise.allSettled(urls.map(url => new Promise(resolve => {
            const img = new Image();
            img.onload = () => resolve({ url, ok: true });
            img.onerror = () => resolve({ url, ok: false });
            img.src = url;
        }).then(result => {
            loaded += 1;
            updateLoader(loaded, urls.length);
            return result;
        }))).then(results => {
            const failed = results.filter(result => result.value && result.value.ok === false).length;
            if (failed) {
                showToast("Assets teilweise geladen", `${failed} Bild(er) konnten nicht vorgeladen werden. Das Spiel startet trotzdem.`);
            }
        });
    }

    function updateLoader(loaded, total) {
        const progress = total <= 0 ? 100 : Math.round((loaded / total) * 100);
        if (ui.loaderBar) ui.loaderBar.style.width = `${progress}%`;
        if (ui.loaderText) ui.loaderText.textContent = `${progress}%`;
    }

    async function startGame() {
        if (gameStarted) return;
        gameStarted = true;

        applyStaticVisuals();
        bindEvents();
        renderFactoryLanes();

        const local = loadLocalState();
        state = normalizeState(local || createDefaultState());
        applyOfflineProgress();
        updateRecipeVisuals();
        render(true);

        await autoLoadCloudIfUseful();

        root.classList.remove("is-loading");
        if (ui.shell) ui.shell.setAttribute("aria-hidden", "false");
        lastTick = Date.now();
        window.setInterval(tick, 100);
        window.setInterval(updateCloudSaveButton, 500);
        showToast("Cookie Cosmos V2 bereit", "Assets geladen. Kleine und goldene Cookies erscheinen während des Spiels.");
    }

    function applyStaticVisuals() {
        const recipe = getPrestigeRecipe(1);
        if (manifest.background) {
            root.style.setProperty("--cc2-bg-image", `url("${manifest.background}")`);
        }
        if (ui.stageBg && manifest.background) {
            ui.stageBg.style.setProperty("--cc2-bg-image", `url("${manifest.background}")`);
        }
        if (ui.brandCookie) ui.brandCookie.src = recipe.src || "";
        if (ui.mainCookie) ui.mainCookie.src = recipe.src || "";
        if (ui.nextCookie) ui.nextCookie.src = getPrestigeRecipe(2).src || recipe.src || "";
    }

    function bindEvents() {
        ui.cookieButton?.addEventListener("click", handleCookieClick);
        ui.prestigeButton?.addEventListener("click", handlePrestige);
        ui.cloudSaveButton?.addEventListener("click", saveToCloud);
        ui.cloudLoadButton?.addEventListener("click", () => loadFromCloud(true));
        ui.exportButton?.addEventListener("click", exportSave);
        ui.importButton?.addEventListener("click", () => ui.importInput?.click());
        ui.importInput?.addEventListener("change", importSave);
        ui.resetButton?.addEventListener("click", resetSave);

        document.querySelectorAll("[data-cc2-tab]").forEach(button => {
            button.addEventListener("click", () => switchTab(button.dataset.cc2Tab));
        });

        document.querySelectorAll("[data-cc2-buy]").forEach(button => {
            button.addEventListener("click", () => {
                buyMode = button.dataset.cc2Buy || "1";
                document.querySelectorAll("[data-cc2-buy]").forEach(item => item.classList.toggle("is-active", item === button));
                render(true);
            });
        });
    }

    function createDefaultState() {
        return {
            version: SAVE_VERSION,
            cookies: 0,
            lifetimeCookies: 0,
            manualCookies: 0,
            totalClicks: 0,
            prestigeLevel: 1,
            prestigeCrumbs: 0,
            buildings: Object.fromEntries(BUILDINGS.map(building => [building.id, 0])),
            upgrades: [],
            achievements: [],
            activeBuffs: [],
            eventStats: {
                goldenCookies: 0,
                orbitCookies: 0,
                factoryRushes: 0,
                totalEvents: 0,
            },
            eventLog: [],
            cloudSaves: 0,
            exports: 0,
            lastSavedAt: 0,
            createdAt: Date.now(),
        };
    }

    function normalizeState(raw) {
        const fallback = createDefaultState();
        if (!raw || typeof raw !== "object") return fallback;

        const normalized = { ...fallback };
        normalized.version = SAVE_VERSION;
        normalized.cookies = safeNumber(raw.cookies, 0);
        normalized.lifetimeCookies = safeNumber(raw.lifetimeCookies, safeNumber(raw.totalCookies, 0));
        normalized.manualCookies = safeNumber(raw.manualCookies, 0);
        normalized.totalClicks = Math.max(0, Math.floor(safeNumber(raw.totalClicks, 0)));
        normalized.prestigeLevel = Math.max(1, Math.floor(safeNumber(raw.prestigeLevel, 1)));
        normalized.prestigeCrumbs = Math.max(0, Math.floor(safeNumber(raw.prestigeCrumbs, 0)));
        normalized.cloudSaves = Math.max(0, Math.floor(safeNumber(raw.cloudSaves, 0)));
        normalized.exports = Math.max(0, Math.floor(safeNumber(raw.exports, 0)));
        normalized.lastSavedAt = Math.max(0, Math.floor(safeNumber(raw.lastSavedAt, 0)));
        normalized.createdAt = Math.max(0, Math.floor(safeNumber(raw.createdAt, Date.now())));

        if (raw.buildings && typeof raw.buildings === "object") {
            normalized.buildings = Object.fromEntries(BUILDINGS.map(building => [
                building.id,
                Math.max(0, Math.floor(safeNumber(raw.buildings[building.id], 0))),
            ]));
        }

        if (Array.isArray(raw.upgrades)) {
            const validUpgradeIds = new Set(UPGRADES.map(upgrade => upgrade.id));
            normalized.upgrades = [...new Set(raw.upgrades.filter(id => validUpgradeIds.has(id)))];
        }

        if (Array.isArray(raw.achievements)) {
            const validAchievementIds = new Set(ACHIEVEMENTS.map(achievement => achievement.id));
            normalized.achievements = [...new Set(raw.achievements.filter(id => validAchievementIds.has(id)))];
        }

        if (Array.isArray(raw.activeBuffs)) {
            const now = Date.now();
            normalized.activeBuffs = raw.activeBuffs
                .filter(buff => buff && safeNumber(buff.expiresAt, 0) > now)
                .slice(0, 12)
                .map(buff => ({
                    id: String(buff.id || "buff").slice(0, 40),
                    name: String(buff.name || "Buff").slice(0, 80),
                    icon: String(buff.icon || "fa-solid fa-bolt").slice(0, 80),
                    type: ["cps", "click", "both"].includes(buff.type) ? buff.type : "both",
                    multiplier: Math.max(1, Math.min(99, safeNumber(buff.multiplier, 1))),
                    expiresAt: Math.floor(safeNumber(buff.expiresAt, now)),
                }));
        }

        if (raw.eventStats && typeof raw.eventStats === "object") {
            normalized.eventStats = {
                goldenCookies: Math.max(0, Math.floor(safeNumber(raw.eventStats.goldenCookies, 0))),
                orbitCookies: Math.max(0, Math.floor(safeNumber(raw.eventStats.orbitCookies, 0))),
                factoryRushes: Math.max(0, Math.floor(safeNumber(raw.eventStats.factoryRushes, 0))),
                totalEvents: Math.max(0, Math.floor(safeNumber(raw.eventStats.totalEvents, 0))),
            };
        }

        if (Array.isArray(raw.eventLog)) {
            normalized.eventLog = raw.eventLog.slice(-30).map(item => ({
                title: String(item.title || "Event").slice(0, 80),
                text: String(item.text || "").slice(0, 140),
                icon: String(item.icon || "fa-solid fa-bolt").slice(0, 80),
                at: Math.max(0, Math.floor(safeNumber(item.at, Date.now()))),
            }));
        }

        return normalized;
    }

    function safeNumber(value, fallback) {
        const number = Number(value);
        return Number.isFinite(number) ? number : fallback;
    }

    function loadLocalState() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            if (!raw) return null;
            return JSON.parse(raw);
        } catch (error) {
            console.warn("Cookie Cosmos V2 Local Save konnte nicht gelesen werden.", error);
            return null;
        }
    }

    function saveLocalState(force) {
        const now = Date.now();
        if (!force && now - lastLocalSave < LOCAL_SAVE_INTERVAL) return;
        lastLocalSave = now;
        state.lastSavedAt = now;
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
            ui.saveHint.textContent = `Lokal gespeichert · ${new Date(now).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}`;
        } catch (error) {
            console.warn("Cookie Cosmos V2 konnte nicht lokal speichern.", error);
            ui.saveHint.textContent = "Lokaler Speicher voll oder blockiert";
        }
    }

    function serializeForCloud() {
        const copy = normalizeState(state);
        copy.activeBuffs = [];
        copy.lastSavedAt = Date.now();
        return copy;
    }

    function applyOfflineProgress() {
        if (!state.lastSavedAt) return;
        const offlineSeconds = Math.min(60 * 60 * 6, Math.max(0, (Date.now() - state.lastSavedAt) / 1000));
        if (offlineSeconds < 15) return;
        const gain = computeCps(state, { ignoreBuffs: true }) * offlineSeconds * 0.35;
        if (gain <= 0) return;
        addCookies(gain, { manual: false });
        addEventLog("Offline-Ertrag", `+${format(gain)} Cookies aus ${formatDuration(offlineSeconds)} Offline-Zeit.`, "fa-solid fa-moon");
        showToast("Offline gebacken", `+${format(gain)} Cookies wurden nachgetragen.`);
    }

    async function autoLoadCloudIfUseful() {
        if (!IS_AUTHENTICATED || !LOAD_URL) {
            updateCloudSaveButton();
            return;
        }

        const localHasProgress = state.lifetimeCookies > 0 || state.totalClicks > 0 || getTotalBuildings(state) > 0;
        const response = await fetchCloudSave();
        if (!response || !response.save_data) {
            updateCloudSaveButton(response);
            return;
        }

        if (!localHasProgress) {
            state = normalizeState(response.save_data);
            applyOfflineProgress();
            updateRecipeVisuals();
            saveLocalState(true);
            render(true);
            showToast("Cloud-Save geladen", "Dein Datenbank-Spielstand wurde automatisch übernommen.");
        } else {
            updateCloudSaveButton(response);
            ui.saveHint.textContent = "Lokaler Spielstand aktiv · DB-Laden manuell möglich";
        }
    }

    async function fetchCloudSave() {
        try {
            const response = await fetch(LOAD_URL, {
                method: "GET",
                credentials: "same-origin",
                headers: { "Accept": "application/json" },
            });
            if (!response.ok) return null;
            return await response.json();
        } catch (error) {
            console.warn("Cookie Cosmos V2 Cloud Save konnte nicht geladen werden.", error);
            return null;
        }
    }

    async function loadFromCloud(showMessages) {
        if (!IS_AUTHENTICATED) {
            showToast("Nicht angemeldet", "Melde dich an, um den DB-Spielstand zu nutzen.");
            return;
        }
        const response = await fetchCloudSave();
        updateCloudSaveButton(response);
        if (!response || !response.save_data) {
            if (showMessages) showToast("Kein DB-Spielstand", "Es wurde noch kein Cookie Cosmos V2 Save in der Datenbank gefunden.");
            return;
        }
        state = normalizeState(response.save_data);
        applyOfflineProgress();
        updateRecipeVisuals();
        eventTimers = createEventTimers(Date.now());
        saveLocalState(true);
        render(true);
        if (showMessages) showToast("DB-Spielstand geladen", "Der Datenbank-Spielstand wurde auf dieses Gerät übernommen.");
    }

    async function saveToCloud() {
        if (!IS_AUTHENTICATED) {
            showToast("Nicht angemeldet", "Der DB-Save funktioniert nur, wenn du eingeloggt bist.");
            return;
        }
        if (!SAVE_URL) return;

        const remaining = Math.ceil((saveCooldownUntil - Date.now()) / 1000);
        if (remaining > 0) {
            showToast("Speichern im Cooldown", `Du kannst in ${remaining}s wieder in die Datenbank speichern.`);
            return;
        }

        ui.cloudSaveButton.disabled = true;
        ui.cloudSaveButton.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i><span>Speichere...</span>`;

        try {
            const payload = serializeForCloud();
            const response = await fetch(SAVE_URL, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCsrfToken(),
                },
                body: JSON.stringify({
                    save_data: payload,
                    cookies: state.cookies,
                    lifetime_cookies: state.lifetimeCookies,
                    cps: computeCps(state),
                    click_power: computeClickPower(state),
                    prestige_level: state.prestigeLevel,
                    prestige_crumbs: state.prestigeCrumbs,
                    achievements_count: state.achievements.length,
                    upgrades_count: state.upgrades.length,
                    buildings_count: getTotalBuildings(state),
                }),
            });
            const data = await response.json().catch(() => ({}));

            if (response.status === 429) {
                saveCooldownUntil = Date.now() + (Math.max(1, Number(data.next_save_in_seconds) || 60) * 1000);
                showToast("DB-Save Cooldown", `Speichern ist in ${Math.ceil((saveCooldownUntil - Date.now()) / 1000)}s wieder möglich.`);
                updateCloudSaveButton(data);
                return;
            }

            if (!response.ok || data.status !== "ok") {
                throw new Error(data.message || "Datenbank-Speichern fehlgeschlagen.");
            }

            state.cloudSaves += 1;
            saveCooldownUntil = Date.now() + (Math.max(1, Number(data.next_save_in_seconds) || 60) * 1000);
            saveLocalState(true);
            checkAchievements();
            render(true);
            showToast("In DB gespeichert", "Dein Spielstand ist jetzt geräteübergreifend gesichert.");
            updateCloudSaveButton(data);
        } catch (error) {
            console.error(error);
            showToast("DB-Save fehlgeschlagen", error.message || "Bitte später erneut versuchen.");
            updateCloudSaveButton();
        }
    }

    function updateCloudSaveButton(data) {
        if (!ui.cloudSaveButton) return;

        if (!IS_AUTHENTICATED) {
            ui.cloudSaveButton.disabled = true;
            ui.cloudSaveButton.innerHTML = `<i class="fa-solid fa-lock"></i><span>Login nötig</span>`;
            return;
        }

        if (data && Number.isFinite(Number(data.next_save_in_seconds))) {
            saveCooldownUntil = Math.max(saveCooldownUntil, Date.now() + (Number(data.next_save_in_seconds) * 1000));
        }

        const remaining = Math.ceil((saveCooldownUntil - Date.now()) / 1000);
        if (remaining > 0) {
            ui.cloudSaveButton.disabled = true;
            ui.cloudSaveButton.innerHTML = `<i class="fa-solid fa-hourglass-half"></i><span>${remaining}s</span>`;
        } else {
            ui.cloudSaveButton.disabled = false;
            ui.cloudSaveButton.innerHTML = `<i class="fa-solid fa-cloud-arrow-up"></i><span>DB speichern</span>`;
        }
    }

    function tick() {
        const now = Date.now();
        const dt = Math.min(1, Math.max(0, (now - lastTick) / 1000));
        lastTick = now;

        expireBuffs(now);
        const cps = computeCps(state);
        if (cps > 0 && dt > 0) addCookies(cps * dt, { manual: false });

        handleEventTimers(now);
        checkAchievements();
        saveLocalState(false);

        if (now - lastRender > RENDER_INTERVAL) {
            scheduleRender();
        }
    }

    function handleCookieClick(event) {
        const amount = computeClickPower(state);
        addCookies(amount, { manual: true });
        state.totalClicks += 1;
        ui.cookieButton.classList.add("is-pressed");
        window.setTimeout(() => ui.cookieButton.classList.remove("is-pressed"), 95);

        const rect = ui.stage.getBoundingClientRect();
        const x = event.clientX ? event.clientX - rect.left : rect.width / 2;
        const y = event.clientY ? event.clientY - rect.top : rect.height / 2;
        spawnFloatingText(`+${format(amount)}`, x, y);
        checkAchievements();
        scheduleRender();
    }

    function addCookies(amount, options) {
        const safeAmount = Math.max(0, safeNumber(amount, 0));
        state.cookies += safeAmount;
        state.lifetimeCookies += safeAmount;
        if (options && options.manual) state.manualCookies += safeAmount;
    }

    function expireBuffs(now) {
        const before = state.activeBuffs.length;
        state.activeBuffs = state.activeBuffs.filter(buff => buff.expiresAt > now);
        if (state.activeBuffs.length !== before) scheduleRender(true);
    }

    function createEventTimers(now) {
        return {
            nextGoldenAt: now + randomBetween(18000, 32000),
            nextOrbitAt: now + randomBetween(9000, 17000),
            nextFactoryAt: now + randomBetween(42000, 76000),
            goldenActive: false,
            orbitActive: 0,
        };
    }

    function handleEventTimers(now) {
        const mods = computeUpgradeMods(state);
        if (!eventTimers.goldenActive && now >= eventTimers.nextGoldenAt) {
            spawnGoldenCookie();
            eventTimers.goldenActive = true;
            eventTimers.nextGoldenAt = now + randomBetween(36000, 76000) * mods.goldenFrequency;
        }

        if (eventTimers.orbitActive < 4 && now >= eventTimers.nextOrbitAt) {
            spawnOrbitCookie();
            eventTimers.orbitActive += 1;
            eventTimers.nextOrbitAt = now + randomBetween(13000, 26000) * mods.orbitFrequency;
        }

        if (now >= eventTimers.nextFactoryAt && computeCps(state, { ignoreBuffs: true }) > 25) {
            triggerFactoryEvent();
            eventTimers.nextFactoryAt = now + randomBetween(70000, 135000);
        }
    }

    function spawnGoldenCookie() {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "cc2-event-cookie is-golden";
        button.setAttribute("aria-label", "Goldenen Cookie einsammeln");
        button.innerHTML = `<img alt="" src="${getPrestigeRecipe(state.prestigeLevel).src}">`;
        const position = randomStagePosition(72);
        button.style.left = `${position.x}px`;
        button.style.top = `${position.y}px`;
        button.addEventListener("click", () => {
            button.remove();
            eventTimers.goldenActive = false;
            triggerGoldenReward(position.x, position.y);
        }, { once: true });
        ui.eventLayer.appendChild(button);

        window.setTimeout(() => {
            if (button.isConnected) {
                button.remove();
                eventTimers.goldenActive = false;
            }
        }, 14500);
    }

    function triggerGoldenReward(x, y) {
        const mods = computeUpgradeMods(state);
        const rewards = ["lucky", "frenzy", "click", "cosmic"];
        const reward = rewards[Math.floor(Math.random() * rewards.length)];
        state.eventStats.goldenCookies += 1;
        state.eventStats.totalEvents += 1;

        if (reward === "lucky") {
            const gain = Math.max(777, state.cookies * 0.18 + computeCps(state) * 95) * mods.goldenReward;
            addCookies(gain, { manual: false });
            spawnFloatingText(`+${format(gain)}`, x, y);
            showToast("Goldener Cookie", `Lucky Batch: +${format(gain)} Cookies.`);
            addEventLog("Goldener Cookie", `Lucky Batch: +${format(gain)} Cookies.`, "fa-solid fa-star");
        } else if (reward === "frenzy") {
            addBuff("golden_frenzy", "Golden Frenzy", "fa-solid fa-star", "cps", 7 * mods.buffPower, 77000);
            showToast("Golden Frenzy", "CPS x7 für 77 Sekunden.");
            addEventLog("Golden Frenzy", "CPS x7 für 77 Sekunden.", "fa-solid fa-star");
        } else if (reward === "click") {
            addBuff("click_frenzy", "Click Frenzy", "fa-solid fa-computer-mouse", "click", 12 * mods.buffPower, 30000);
            showToast("Click Frenzy", "Klickpower x12 für 30 Sekunden.");
            addEventLog("Click Frenzy", "Klickpower x12 für 30 Sekunden.", "fa-solid fa-computer-mouse");
        } else {
            addBuff("cosmic_oven", "Cosmic Oven", "fa-solid fa-fire-flame-curved", "both", 3 * mods.buffPower, 45000);
            showToast("Cosmic Oven", "CPS und Klicks x3 für 45 Sekunden.");
            addEventLog("Cosmic Oven", "CPS und Klicks x3 für 45 Sekunden.", "fa-solid fa-fire-flame-curved");
        }
        checkAchievements();
        scheduleRender(true);
    }

    function spawnOrbitCookie() {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "cc2-event-cookie is-orbit";
        button.setAttribute("aria-label", "Kleinen Event-Cookie einsammeln");
        const recipe = getPrestigeRecipe(Math.max(1, state.prestigeLevel - 1));
        button.innerHTML = `<img alt="" src="${recipe.src}">`;

        const position = orbitPosition();
        button.style.left = `${position.x}px`;
        button.style.top = `${position.y}px`;
        button.addEventListener("click", () => {
            button.remove();
            eventTimers.orbitActive = Math.max(0, eventTimers.orbitActive - 1);
            triggerOrbitReward(position.x, position.y);
        }, { once: true });
        ui.eventLayer.appendChild(button);

        window.setTimeout(() => {
            if (button.isConnected) {
                button.remove();
                eventTimers.orbitActive = Math.max(0, eventTimers.orbitActive - 1);
            }
        }, 10500);
    }

    function triggerOrbitReward(x, y) {
        const mods = computeUpgradeMods(state);
        const rewards = ["click", "cps", "cookies"];
        const reward = rewards[Math.floor(Math.random() * rewards.length)];
        state.eventStats.orbitCookies += 1;
        state.eventStats.totalEvents += 1;

        if (reward === "click") {
            addBuff("orbit_click", "Orbit Click", "fa-solid fa-cookie", "click", 3 * mods.buffPower, 12000);
            showToast("Orbit-Cookie", "Klickpower x3 für 12 Sekunden.");
            addEventLog("Orbit-Cookie", "Klickpower x3 für 12 Sekunden.", "fa-solid fa-cookie");
        } else if (reward === "cps") {
            addBuff("mini_frenzy", "Mini Frenzy", "fa-solid fa-bolt", "cps", 2 * mods.buffPower, 14000);
            showToast("Mini Frenzy", "CPS x2 für 14 Sekunden.");
            addEventLog("Mini Frenzy", "CPS x2 für 14 Sekunden.", "fa-solid fa-bolt");
        } else {
            const gain = Math.max(120, computeCps(state) * 18 + state.prestigeLevel * 25);
            addCookies(gain, { manual: false });
            spawnFloatingText(`+${format(gain)}`, x, y);
            showToast("Krümelregen", `+${format(gain)} Cookies.`);
            addEventLog("Krümelregen", `+${format(gain)} Cookies.`, "fa-solid fa-cloud-meatball");
        }
        checkAchievements();
        scheduleRender(true);
    }

    function triggerFactoryEvent() {
        const mods = computeUpgradeMods(state);
        const duration = 18000 * mods.factoryDuration;
        state.eventStats.factoryRushes += 1;
        state.eventStats.totalEvents += 1;
        addBuff("factory_rush_event", "Factory Rush", "fa-solid fa-industry", "cps", 2.5 * mods.buffPower, duration);
        addEventLog("Factory Rush", `Produktionslinien laufen ${formatDuration(duration / 1000)} lang mit x2.5.`, "fa-solid fa-industry");
        showToast("Factory Rush", "Deine Fabrik geht kurz in den Overdrive.");

        for (let i = 0; i < Math.min(3, 1 + Math.floor(state.prestigeLevel / 2)); i += 1) {
            window.setTimeout(spawnOrbitCookie, i * 900);
        }
    }

    function addBuff(id, name, icon, type, multiplier, durationMs) {
        const now = Date.now();
        const existing = state.activeBuffs.find(buff => buff.id === id);
        if (existing) {
            existing.expiresAt = Math.max(existing.expiresAt, now + durationMs);
            existing.multiplier = Math.max(existing.multiplier, multiplier);
            return;
        }
        state.activeBuffs.push({ id, name, icon, type, multiplier, expiresAt: now + durationMs });
    }

    function randomStagePosition(size) {
        const rect = ui.stage.getBoundingClientRect();
        const padding = Math.max(18, size / 2);
        return {
            x: randomBetween(padding, Math.max(padding, rect.width - padding)),
            y: randomBetween(padding, Math.max(padding, rect.height - padding - 90)),
        };
    }

    function orbitPosition() {
        const rect = ui.stage.getBoundingClientRect();
        const angle = Math.random() * Math.PI * 2;
        const radius = Math.min(rect.width, rect.height) * randomBetween(0.22, 0.34);
        const centerX = rect.width / 2;
        const centerY = rect.height * 0.47;
        return {
            x: centerX + Math.cos(angle) * radius,
            y: centerY + Math.sin(angle) * radius,
        };
    }

    function handlePrestige() {
        const cost = getPrestigeCost(state.prestigeLevel);
        if (state.cookies < cost) {
            showToast("Prestige noch nicht bereit", `Du brauchst ${format(cost)} Cookies für das nächste Rezept.`);
            return;
        }

        const oldLevel = state.prestigeLevel;
        state.prestigeLevel += 1;
        const gainedCrumbs = Math.max(1, Math.floor(Math.pow(oldLevel, 1.35)));
        state.prestigeCrumbs += gainedCrumbs;
        state.cookies = 0;
        state.buildings = Object.fromEntries(BUILDINGS.map(building => [building.id, 0]));
        state.upgrades = [];
        state.activeBuffs = [];
        eventTimers = createEventTimers(Date.now());
        updateRecipeVisuals();
        saveLocalState(true);
        checkAchievements();
        render(true);

        const recipe = getPrestigeRecipe(state.prestigeLevel);
        showToast("Prestige Upgrade!", `Level ${state.prestigeLevel}: ${recipe.name}. +${gainedCrumbs} Cosmic Crumbs.`);
        addEventLog("Prestige Upgrade", `Level ${oldLevel} → ${state.prestigeLevel}: ${recipe.name}.`, "fa-solid fa-rocket");
    }

    function getPrestigeCost(level) {
        return Math.floor(100000 * Math.pow(Math.max(1, level), 2.28));
    }

    function getPrestigeRecipe(level) {
        const safeLevel = Math.max(1, Math.floor(level || 1));
        if (manifest.prestige[safeLevel - 1]) {
            return manifest.prestige[safeLevel - 1];
        }
        const cookieVariants = manifest.prestige.length ? manifest.prestige : [];
        const variant = cookieVariants[(safeLevel - 1) % Math.max(1, cookieVariants.length)] || { src: "", accent: "#ffd85c" };
        const cycle = Math.floor((safeLevel - 1) / Math.max(1, cookieVariants.length));
        const names = [
            "Klassischer Keks",
            "Weiße Schoko",
            "Dunkler Keks",
            "Dunkle Schoko Weiß",
            "Cosmic Crunch",
            "Nebula Nugget",
            "Galaxie Gebäck",
            "Quanten-Keks"
        ];
        return {
            level: safeLevel,
            name: cycle === 0 ? (variant.name || names[(safeLevel - 1) % names.length]) : `${names[(safeLevel - 1) % names.length]} +${cycle}`,
            src: variant.src || "",
            accent: variant.accent || ["#ffd85c", "#ffaf3f", "#c4b5fd", "#67e8f9", "#6ee7b7"][(safeLevel - 1) % 5],
        };
    }

    function updateRecipeVisuals() {
        const current = getPrestigeRecipe(state.prestigeLevel);
        const next = getPrestigeRecipe(state.prestigeLevel + 1);
        if (ui.mainCookie) ui.mainCookie.src = current.src || "";
        if (ui.brandCookie) ui.brandCookie.src = current.src || "";
        if (ui.nextCookie) ui.nextCookie.src = next.src || current.src || "";
        root.style.setProperty("--cc2-current-accent", current.accent || "#ffd85c");
    }

    function computePrestigeMultiplier(s) {
        const base = 1 + (Math.max(1, s.prestigeLevel) - 1) * 0.16 + Math.max(0, s.prestigeCrumbs) * 0.045;
        const prestigeClickUpgrade = hasUpgrade(s, "cosmic_clicks") ? 1 + (s.prestigeLevel - 1) * 0.12 : 1;
        return { base, prestigeClickUpgrade };
    }

    function computeUpgradeMods(s) {
        const mods = {
            clickAdd: 0,
            clickMult: 1,
            cpsMult: 1,
            buildingMult: {},
            goldenFrequency: 1,
            orbitFrequency: 1,
            goldenReward: 1,
            factoryDuration: 1,
            buffPower: 1,
        };

        for (const upgrade of UPGRADES) {
            if (!hasUpgrade(s, upgrade.id)) continue;
            if (upgrade.kind === "clickAdd") mods.clickAdd += upgrade.value;
            if (upgrade.kind === "clickMult") mods.clickMult *= upgrade.value;
            if (upgrade.kind === "cpsMult") mods.cpsMult *= upgrade.value;
            if (upgrade.kind === "buildingMult") mods.buildingMult[upgrade.target] = (mods.buildingMult[upgrade.target] || 1) * upgrade.value;
            if (upgrade.kind === "goldenFrequency") mods.goldenFrequency *= upgrade.value;
            if (upgrade.kind === "orbitFrequency") mods.orbitFrequency *= upgrade.value;
            if (upgrade.kind === "goldenReward") mods.goldenReward *= upgrade.value;
            if (upgrade.kind === "factoryDuration") mods.factoryDuration *= upgrade.value;
            if (upgrade.kind === "buffPower") mods.buffPower *= upgrade.value;
        }

        mods.goldenFrequency = Math.max(0.36, mods.goldenFrequency * (1 - Math.min(0.34, (s.prestigeLevel - 1) * 0.018)));
        mods.orbitFrequency = Math.max(0.34, mods.orbitFrequency * (1 - Math.min(0.42, (s.prestigeLevel - 1) * 0.02)));
        return mods;
    }

    function computeBuffMultiplier(s, type) {
        const now = Date.now();
        return s.activeBuffs.reduce((total, buff) => {
            if (buff.expiresAt <= now) return total;
            if (buff.type === type || buff.type === "both") return total * buff.multiplier;
            return total;
        }, 1);
    }

    function computeCps(s, options) {
        const mods = computeUpgradeMods(s);
        const prestige = computePrestigeMultiplier(s).base;
        const base = BUILDINGS.reduce((sum, building) => {
            const count = getBuildingCount(s, building.id);
            const buildingMult = mods.buildingMult[building.id] || 1;
            return sum + count * building.baseCps * buildingMult;
        }, 0);
        const buff = options && options.ignoreBuffs ? 1 : computeBuffMultiplier(s, "cps");
        return Math.max(0, base * mods.cpsMult * prestige * buff);
    }

    function computeClickPower(s) {
        const mods = computeUpgradeMods(s);
        const prestige = computePrestigeMultiplier(s);
        const buff = computeBuffMultiplier(s, "click");
        return Math.max(1, (1 + mods.clickAdd) * mods.clickMult * prestige.base * prestige.prestigeClickUpgrade * buff);
    }

    function hasUpgrade(s, id) {
        return Array.isArray(s.upgrades) && s.upgrades.includes(id);
    }

    function getBuildingCount(s, id) {
        return Math.max(0, Math.floor(s.buildings?.[id] || 0));
    }

    function getTotalBuildings(s) {
        return BUILDINGS.reduce((sum, building) => sum + getBuildingCount(s, building.id), 0);
    }

    function getBuildingCost(building, count) {
        return Math.floor(building.baseCost * Math.pow(1.15, count));
    }

    function getBuyInfo(building) {
        const owned = getBuildingCount(state, building.id);
        if (buyMode === "max") {
            let amount = 0;
            let totalCost = 0;
            let nextCount = owned;
            while (amount < 10000) {
                const nextCost = getBuildingCost(building, nextCount);
                if (totalCost + nextCost > state.cookies) break;
                totalCost += nextCost;
                nextCount += 1;
                amount += 1;
            }
            return { amount, cost: totalCost, nextCost: getBuildingCost(building, owned) };
        }

        const target = buyMode === "10" ? 10 : 1;
        let totalCost = 0;
        for (let i = 0; i < target; i += 1) {
            totalCost += getBuildingCost(building, owned + i);
        }
        return { amount: target, cost: totalCost, nextCost: getBuildingCost(building, owned) };
    }

    function buyBuilding(id) {
        const building = BUILDINGS.find(item => item.id === id);
        if (!building) return;
        const info = getBuyInfo(building);
        if (info.amount <= 0 || state.cookies < info.cost) {
            showToast("Nicht genug Cookies", `${building.name} kostet ${format(info.cost || info.nextCost)} Cookies.`);
            return;
        }
        state.cookies -= info.cost;
        state.buildings[id] = getBuildingCount(state, id) + info.amount;
        saveLocalState(true);
        checkAchievements();
        render(true);
    }

    function buyUpgrade(id) {
        const upgrade = UPGRADES.find(item => item.id === id);
        if (!upgrade || hasUpgrade(state, id) || !upgrade.requires(state)) return;
        if (state.cookies < upgrade.cost) {
            showToast("Nicht genug Cookies", `${upgrade.name} kostet ${format(upgrade.cost)} Cookies.`);
            return;
        }
        state.cookies -= upgrade.cost;
        state.upgrades.push(id);
        saveLocalState(true);
        checkAchievements();
        render(true);
        showToast("Upgrade gekauft", upgrade.name);
    }

    function render(force) {
        const now = Date.now();
        if (!force && now - lastRender < RENDER_INTERVAL) return;
        lastRender = now;
        updateRecipeVisuals();
        renderStats();
        renderPrestige();
        renderBuffs();
        renderBuildings();
        renderUpgrades();
        renderEvents();
        renderAchievements();
        updateCloudSaveButton();
    }

    function scheduleRender(force) {
        if (renderQueued && !force) return;
        renderQueued = true;
        window.requestAnimationFrame(() => {
            renderQueued = false;
            render(Boolean(force));
        });
    }

    function renderStats() {
        ui.cookieCount.textContent = format(state.cookies);
        ui.cpsCount.textContent = format(computeCps(state));
        ui.clickPower.textContent = format(computeClickPower(state));
        ui.prestigeLevel.textContent = `Level ${state.prestigeLevel}`;
        ui.ownedSummary.textContent = `${getTotalBuildings(state)} Anlagen · ${state.upgrades.length} Upgrades`;
    }

    function renderPrestige() {
        const current = getPrestigeRecipe(state.prestigeLevel);
        const next = getPrestigeRecipe(state.prestigeLevel + 1);
        const cost = getPrestigeCost(state.prestigeLevel);
        const progress = Math.min(1, state.cookies / cost);
        const multiplier = computePrestigeMultiplier(state).base;

        ui.prestigeName.textContent = current.name;
        ui.prestigeTitle.textContent = `Prestige-Level ${state.prestigeLevel}`;
        ui.prestigeDescription.textContent = `Permanenter Multiplikator: x${multiplier.toFixed(2)} · Cosmic Crumbs: ${state.prestigeCrumbs}`;
        ui.nextPrestigeName.textContent = next.name;
        ui.prestigeNeed.textContent = `${format(cost)} Cookies benötigt`;
        ui.prestigeProgressLabel.textContent = `${Math.floor(progress * 100)}%`;
        ui.prestigeProgress.style.width = `${progress * 100}%`;
        ui.prestigeButton.disabled = state.cookies < cost;
    }

    function renderBuffs() {
        const now = Date.now();
        if (!state.activeBuffs.length) {
            ui.buffRow.innerHTML = `<span class="cc2-buff-empty">Keine aktiven Buffs</span>`;
            return;
        }
        ui.buffRow.innerHTML = state.activeBuffs.map(buff => {
            const seconds = Math.max(0, Math.ceil((buff.expiresAt - now) / 1000));
            return `<span class="cc2-buff-chip"><i class="${escapeAttr(buff.icon)}"></i>${escapeHtml(buff.name)} <small>${seconds}s</small></span>`;
        }).join("");
    }

    function renderFactoryLanes() {
        if (!ui.factoryLanes) return;
        const machines = BUILDINGS.slice(0, 6);
        ui.factoryLanes.innerHTML = machines.map((machine, index) => `
            <span class="cc2-factory-lane" title="${escapeAttr(machine.name)}" style="--cc2-lane-offset: ${index % 2 ? 4 : 0}; --cc2-lane-speed: ${index * 0.11}s;">
                <i class="${escapeAttr(machine.icon)}" aria-hidden="true"></i>
                <b aria-hidden="true"></b>
            </span>
        `).join("");
    }

    function renderBuildings() {
        ui.buildingList.innerHTML = BUILDINGS.map(building => {
            const count = getBuildingCount(state, building.id);
            const info = getBuyInfo(building);
            const canBuy = info.amount > 0 && state.cookies >= info.cost;
            const mods = computeUpgradeMods(state);
            const production = building.baseCps * (mods.buildingMult[building.id] || 1) * computePrestigeMultiplier(state).base * mods.cpsMult;
            return `
                <article class="cc2-card ${canBuy ? "can-buy" : ""}">
                    <div class="cc2-card-top">
                        <span class="cc2-card-icon"><i class="${building.icon}"></i></span>
                        <div class="cc2-card-title">
                            <h3>${escapeHtml(building.name)} <span>×${count}</span></h3>
                            <p>${escapeHtml(building.desc)}</p>
                        </div>
                    </div>
                    <div class="cc2-building-meta">
                        <span>${format(production)} CPS/Stück</span>
                        <span>${format(count * production)} CPS gesamt</span>
                    </div>
                    <button type="button" class="cc2-card-button" data-building-id="${building.id}" ${canBuy ? "" : "disabled"}>
                        ${info.amount > 0 ? `${info.amount}x kaufen · ${format(info.cost)}` : `Kaufen · ${format(info.nextCost)}`}
                    </button>
                </article>
            `;
        }).join("");

        ui.buildingList.querySelectorAll("[data-building-id]").forEach(button => {
            button.addEventListener("click", () => buyBuilding(button.dataset.buildingId));
        });
    }

    function renderUpgrades() {
        const visible = UPGRADES.filter(upgrade => upgrade.requires(state) || hasUpgrade(state, upgrade.id));
        const nextLocked = UPGRADES.find(upgrade => !visible.includes(upgrade) && !hasUpgrade(state, upgrade.id));
        const cards = visible.map(upgrade => {
            const bought = hasUpgrade(state, upgrade.id);
            const canBuy = !bought && state.cookies >= upgrade.cost;
            return `
                <article class="cc2-card ${canBuy ? "can-buy" : ""}">
                    <div class="cc2-card-top">
                        <span class="cc2-card-icon"><i class="${upgrade.icon}"></i></span>
                        <div class="cc2-card-title">
                            <h3>${escapeHtml(upgrade.name)}</h3>
                            <p>${escapeHtml(upgrade.desc)}</p>
                        </div>
                    </div>
                    <div class="cc2-upgrade-meta">
                        <span class="cc2-price"><i class="fa-solid fa-cookie-bite"></i>${format(upgrade.cost)}</span>
                        <span>${bought ? "Freigeschaltet" : canBuy ? "Bereit" : "Zu teuer"}</span>
                    </div>
                    <button type="button" class="cc2-card-button" data-upgrade-id="${upgrade.id}" ${canBuy ? "" : "disabled"}>
                        ${bought ? "Gekauft" : "Upgrade kaufen"}
                    </button>
                </article>
            `;
        });

        if (nextLocked) {
            cards.push(`
                <article class="cc2-card">
                    <div class="cc2-card-top">
                        <span class="cc2-card-icon"><i class="fa-solid fa-lock"></i></span>
                        <div class="cc2-card-title">
                            <h3>Nächstes Upgrade verborgen</h3>
                            <p>Spiele weiter, kaufe Anlagen oder sammle Events, um mehr Forschung freizuschalten.</p>
                        </div>
                    </div>
                </article>
            `);
        }

        ui.upgradeList.innerHTML = cards.join("");
        ui.upgradeList.querySelectorAll("[data-upgrade-id]").forEach(button => {
            button.addEventListener("click", () => buyUpgrade(button.dataset.upgradeId));
        });
    }

    function renderEvents() {
        const intro = [
            { title: "Kleine Orbit-Cookies", text: "Schweben kurz um den Cookie und geben 12–14 Sekunden Buffs oder direkte Cookies.", icon: "fa-solid fa-cookie" },
            { title: "Goldene Cookies", text: "Seltener, aber deutlich stärker: Lucky Batch, Frenzy, Click Frenzy oder Cosmic Oven.", icon: "fa-solid fa-star" },
            { title: "Factory Rush", text: "Zufälliges Fabrik-Event, sobald deine Produktion läuft. Gibt kurz starken CPS-Boost.", icon: "fa-solid fa-industry" },
        ];
        const logRows = state.eventLog.slice().reverse().map(item => ({ ...item, isLog: true }));
        ui.eventLog.innerHTML = intro.concat(logRows).map(item => `
            <article class="cc2-event-row">
                <i class="${escapeAttr(item.icon)}"></i>
                <div>
                    <strong>${escapeHtml(item.title)}</strong>
                    <p>${escapeHtml(item.text)}${item.isLog ? ` · ${new Date(item.at).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}` : ""}</p>
                </div>
            </article>
        `).join("");
    }

    function renderAchievements() {
        ui.achievementSummary.textContent = `${state.achievements.length} von ${ACHIEVEMENTS.length} erledigt`;
        ui.achievementList.innerHTML = ACHIEVEMENTS.map(achievement => {
            const unlocked = state.achievements.includes(achievement.id);
            return `
                <article class="cc2-achievement-card ${unlocked ? "is-unlocked" : ""}">
                    <i class="${achievement.icon}"></i>
                    <div>
                        <strong>${escapeHtml(achievement.name)}</strong>
                        <small>${escapeHtml(achievement.note)}</small>
                    </div>
                </article>
            `;
        }).join("");
    }

    function checkAchievements() {
        let changed = false;
        for (const achievement of ACHIEVEMENTS) {
            if (state.achievements.includes(achievement.id)) continue;
            if (!achievement.test(state)) continue;
            state.achievements.push(achievement.id);
            changed = true;
            showToast("Erfolg freigeschaltet", achievement.name);
        }
        if (changed) saveLocalState(true);
    }

    function addEventLog(title, text, icon) {
        state.eventLog.push({ title, text, icon, at: Date.now() });
        state.eventLog = state.eventLog.slice(-30);
    }

    function showToast(title, text) {
        if (!ui.toastLayer) return;
        const toast = document.createElement("div");
        toast.className = "cc2-toast";
        toast.innerHTML = `<strong>${escapeHtml(title)}</strong><span>${escapeHtml(text || "")}</span>`;
        ui.toastLayer.prepend(toast);
        while (ui.toastLayer.children.length > 4) ui.toastLayer.lastElementChild.remove();
        window.setTimeout(() => toast.remove(), 4200);
    }

    function spawnFloatingText(text, x, y) {
        const node = document.createElement("span");
        node.className = "cc2-float-text";
        node.textContent = text;
        node.style.setProperty("--x", `${x}px`);
        node.style.setProperty("--y", `${y}px`);
        ui.floatingLayer.appendChild(node);
        window.setTimeout(() => node.remove(), 950);
    }

    function switchTab(tab) {
        document.querySelectorAll("[data-cc2-tab]").forEach(button => {
            button.classList.toggle("is-active", button.dataset.cc2Tab === tab);
        });
        document.querySelectorAll("[data-cc2-panel]").forEach(panel => {
            panel.classList.toggle("is-active", panel.dataset.cc2Panel === tab);
        });
    }

    function exportSave() {
        state.exports += 1;
        checkAchievements();
        const payload = {
            format: EXPORT_FORMAT,
            exported_at: new Date().toISOString(),
            save_data: serializeForCloud(),
        };
        const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `cookie-cosmos-v2-save-${new Date().toISOString().slice(0, 10)}.json`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
        saveLocalState(true);
        render(true);
        showToast("Export erstellt", "Dein Cookie Cosmos V2 Save wurde als JSON heruntergeladen.");
    }

    function importSave(event) {
        const file = event.target.files?.[0];
        event.target.value = "";
        if (!file) return;
        const reader = new FileReader();
        reader.onload = () => {
            try {
                const payload = JSON.parse(String(reader.result || "{}"));
                const imported = payload.format === EXPORT_FORMAT ? payload.save_data : payload;
                state = normalizeState(imported);
                updateRecipeVisuals();
                saveLocalState(true);
                eventTimers = createEventTimers(Date.now());
                render(true);
                showToast("Import erfolgreich", "Der Spielstand wurde übernommen.");
            } catch (error) {
                showToast("Import fehlgeschlagen", "Die Datei ist kein gültiger Cookie Cosmos V2 Save.");
            }
        };
        reader.readAsText(file);
    }

    function resetSave() {
        const confirmed = window.confirm("Cookie Cosmos V2 wirklich zurücksetzen? Dein DB-Save bleibt erhalten, bis du wieder manuell in die DB speicherst.");
        if (!confirmed) return;
        state = createDefaultState();
        eventTimers = createEventTimers(Date.now());
        updateRecipeVisuals();
        try { localStorage.removeItem(STORAGE_KEY); } catch (error) { console.warn(error); }
        saveLocalState(true);
        render(true);
        showToast("Spielstand zurückgesetzt", "Du startest wieder bei Prestige-Level 1.");
    }

    function getCsrfToken() {
        const cookies = document.cookie ? document.cookie.split(";") : [];
        for (const cookie of cookies) {
            const trimmed = cookie.trim();
            if (trimmed.startsWith("csrftoken=")) {
                return decodeURIComponent(trimmed.substring("csrftoken=".length));
            }
        }
        return "";
    }

    function format(value) {
        const number = Math.max(0, safeNumber(value, 0));
        if (number < 1000) {
            return number % 1 === 0 ? String(Math.floor(number)) : number.toFixed(number < 10 ? 1 : 0);
        }
        const suffixes = ["", "K", "M", "B", "T", "Qa", "Qi", "Sx", "Sp", "Oc", "No", "Dc"];
        let scaled = number;
        let tier = 0;
        while (scaled >= 1000 && tier < suffixes.length - 1) {
            scaled /= 1000;
            tier += 1;
        }
        const digits = scaled >= 100 ? 0 : scaled >= 10 ? 1 : 2;
        return `${scaled.toFixed(digits)}${suffixes[tier]}`;
    }

    function formatDuration(seconds) {
        const safe = Math.max(0, Math.floor(seconds));
        if (safe < 60) return `${safe}s`;
        const minutes = Math.floor(safe / 60);
        const rest = safe % 60;
        return rest ? `${minutes}m ${rest}s` : `${minutes}m`;
    }

    function randomBetween(min, max) {
        return min + Math.random() * (max - min);
    }

    function escapeHtml(value) {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function escapeAttr(value) {
        return escapeHtml(value).replace(/`/g, "&#096;");
    }
})();
