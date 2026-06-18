(() => {
    const root = document.querySelector("[data-nebula-tycoon]");
    if (!root) return;

    const SAVE_KEY = root.dataset.saveKey || "mytools-nebula-forge-tycoon-v1";
    const EXPORT_FORMAT = "mytools-nebula-forge-tycoon-save";
    const SAVE_VERSION = 2;
    const DB_SAVE_COOLDOWN_SECONDS = 60;
    const SPACE_MINE_REPEAT_INTERVAL_MS = 150;
    const SPACE_MINE_SPAM_INTERVAL_MS = 55;
    const DB_LOAD_URL = root.dataset.dbLoadUrl || "";
    const DB_SAVE_URL = root.dataset.dbSaveUrl || "";
    const USER_IS_AUTHENTICATED = root.dataset.authenticated === "true";
    const hadLocalSaveAtStartup = Boolean(localStorage.getItem(SAVE_KEY));
    const now = () => Date.now();

    const buildings = [
        {
            id: "pocketDrill",
            name: "Taschen-Bohrer",
            icon: "fa-solid fa-person-digging",
            description: "Der erste kleine AFK-Bohrer am Rand des Sternenkerns.",
            baseCost: 18,
            growth: 1.16,
            rate: 0.25,
        },
        {
            id: "solarCrawler",
            name: "Solar-Crawler",
            icon: "fa-solid fa-solar-panel",
            description: "Fährt über Asteroidenplatten und sammelt Flux-Splitter.",
            baseCost: 120,
            growth: 1.18,
            rate: 1.6,
        },
        {
            id: "droneNest",
            name: "Drohnen-Nest",
            icon: "fa-solid fa-helicopter-symbol",
            description: "Schickt Schwärme los, die auch während AFK weiterarbeiten.",
            baseCost: 760,
            growth: 1.19,
            rate: 8.5,
        },
        {
            id: "crystalGreenhouse",
            name: "Kristall-Gewächshaus",
            icon: "fa-solid fa-seedling",
            description: "Züchtet Flux-Kristalle in Schwerelosigkeit.",
            baseCost: 5200,
            growth: 1.2,
            rate: 42,
        },
        {
            id: "orbitalFoundry",
            name: "Orbitale Gießerei",
            icon: "fa-solid fa-industry",
            description: "Schmilzt Meteorstaub zu gewaltigen Flux-Barren.",
            baseCost: 42000,
            growth: 1.21,
            rate: 230,
        },
        {
            id: "singularityEngine",
            name: "Singularitäts-Engine",
            icon: "fa-solid fa-circle-nodes",
            description: "Krümmt Raumzeit, damit deine Fabrik doppelt so fleißig wirkt.",
            baseCost: 390000,
            growth: 1.22,
            rate: 1400,
        },
        {
            id: "naniteSwarm",
            name: "Naniten-Schwarm",
            icon: "fa-solid fa-bugs",
            description: "Winzige Maschinen zerlegen Sternenstaub in verwertbaren Flux.",
            baseCost: 3800000,
            growth: 1.23,
            rate: 9200,
        },
        {
            id: "lunarHarvester",
            name: "Mond-Harvester",
            icon: "fa-solid fa-moon",
            description: "Schürft komplette Mondadern leer und liefert konstant Nachschub.",
            baseCost: 37000000,
            growth: 1.235,
            rate: 57000,
        },
        {
            id: "voidRefinery",
            name: "Void-Raffinerie",
            icon: "fa-solid fa-filter-circle-dollar",
            description: "Reinigt dunkle Materie und presst sie zu hochreinem Flux.",
            baseCost: 420000000,
            growth: 1.24,
            rate: 400000,
        },
        {
            id: "chronoFactory",
            name: "Chrono-Fabrik",
            icon: "fa-solid fa-clock-rotate-left",
            description: "Produziert in kleinen Zeitschleifen mehrfach denselben Flux-Barren.",
            baseCost: 5800000000,
            growth: 1.245,
            rate: 3200000,
        },
        {
            id: "dysonLattice",
            name: "Dyson-Gitter",
            icon: "fa-solid fa-sun",
            description: "Fängt Sternenenergie in riesigen Gitternetzen ein.",
            baseCost: 84000000000,
            growth: 1.25,
            rate: 27000000,
        },
        {
            id: "galaxyPrinter",
            name: "Galaxie-Drucker",
            icon: "fa-solid fa-print",
            description: "Druckt ganze Produktionslinien aus komprimierter Raumzeit.",
            baseCost: 1300000000000,
            growth: 1.255,
            rate: 240000000,
        },
    ];

    const upgrades = [
        {
            id: "plasmaGloves",
            name: "Plasma-Handschuhe",
            icon: "fa-solid fa-hand-fist",
            description: "+0,9 aktiver Abbau pro Level.",
            baseCost: 60,
            growth: 1.95,
            max: 25,
        },
        {
            id: "afkProtocol",
            name: "AFK-Protokoll",
            icon: "fa-solid fa-moon",
            description: "+8% passive Produktion und besserer Offline-Ertrag.",
            baseCost: 260,
            growth: 2.08,
            max: 14,
        },
        {
            id: "coolingLoop",
            name: "Kryo-Kühlkreis",
            icon: "fa-solid fa-snowflake",
            description: "Mehr Hitze-Kapazität und schnellere Abkühlung.",
            baseCost: 480,
            growth: 2.15,
            max: 12,
        },
        {
            id: "comboMatrix",
            name: "Combo-Matrix",
            icon: "fa-solid fa-gauge-high",
            description: "Aktives Spielen skaliert stärker mit deiner Combo.",
            baseCost: 1250,
            growth: 2.25,
            max: 12,
        },
        {
            id: "deepStorage",
            name: "Tiefenspeicher",
            icon: "fa-solid fa-box-archive",
            description: "+2 Stunden Offline-Cap pro Level.",
            baseCost: 3200,
            growth: 2.35,
            max: 8,
        },
        {
            id: "meteorMagnet",
            name: "Meteor-Magnet",
            icon: "fa-solid fa-magnet",
            description: "Mehr Meteor-Events und bessere Event-Belohnungen.",
            baseCost: 6800,
            growth: 2.4,
            max: 8,
        },
        {
            id: "collectorArray",
            name: "Sammler-Array",
            icon: "fa-solid fa-hand-holding-droplet",
            description: "Sammelimpuls gibt einen kleinen Sofort-Schub und lädt moderat schneller nach.",
            baseCost: 1800,
            growth: 2.12,
            max: 12,
        },
        {
            id: "eventRelay",
            name: "Event-Relais",
            icon: "fa-solid fa-tower-broadcast",
            description: "Timing-Events laden schneller wieder auf.",
            baseCost: 4200,
            growth: 2.18,
            max: 10,
        },
        {
            id: "riftAmplifier",
            name: "Riss-Verstärker",
            icon: "fa-solid fa-wave-square",
            description: "Alle Timing-Events und Meteor-Funde geben mehr Flux.",
            baseCost: 9200,
            growth: 2.28,
            max: 12,
        },
        {
            id: "neuralPicks",
            name: "Neural-Picken",
            icon: "fa-solid fa-brain",
            description: "+11% aktiver Abbau pro Level.",
            baseCost: 14500,
            growth: 2.32,
            max: 15,
        },
        {
            id: "stellarLogistics",
            name: "Stellar-Logistik",
            icon: "fa-solid fa-route",
            description: "+6,5% passive Produktion pro Level.",
            baseCost: 28000,
            growth: 2.36,
            max: 14,
        },
        {
            id: "harmonicCapacitor",
            name: "Harmonischer Kondensator",
            icon: "fa-solid fa-dharmachakra",
            description: "Event-Boosts halten länger und passive Buffs werden stärker.",
            baseCost: 76000,
            growth: 2.42,
            max: 10,
        },
        {
            id: "autoCalibrator",
            name: "Auto-Kalibrator",
            icon: "fa-solid fa-sliders",
            description: "Jede freigeschaltete Anlagenart gibt einen kleinen AFK-Bonus.",
            baseCost: 180000,
            growth: 2.5,
            max: 10,
        },
        {
            id: "clickResonator",
            name: "Klick-Resonator",
            icon: "fa-solid fa-fingerprint",
            description: "Combos skalieren stärker und fallen langsamer ab.",
            baseCost: 440000,
            growth: 2.55,
            max: 8,
        },
        {
            id: "coreSynchronizer",
            name: "Kern-Synchronisator",
            icon: "fa-solid fa-link",
            description: "Klicks erhalten einen Anteil deiner aktuellen AFK-Produktion als Sofort-Flux.",
            baseCost: 950,
            growth: 2.04,
            max: 15,
        },
        {
            id: "rhythmExtractor",
            name: "Rhythmus-Extraktor",
            icon: "fa-solid fa-drum",
            description: "Hohe Combos verstärken den AFK-Anteil pro Klick deutlich.",
            baseCost: 7200,
            growth: 2.18,
            max: 12,
        },
        {
            id: "pulseCondenser",
            name: "Takt-Kondensator",
            icon: "fa-solid fa-burst",
            description: "Aktive Klickserien lösen öfter zusätzliche Takt-Bursts aus.",
            baseCost: 36000,
            growth: 2.28,
            max: 10,
        },
        {
            id: "heatRecycler",
            name: "Hitze-Recycling",
            icon: "fa-solid fa-temperature-arrow-up",
            description: "Hohe Reaktor-Hitze erhöht aktive Klickerträge und kühlt bei Takt-Bursts leicht ab.",
            baseCost: 165000,
            growth: 2.45,
            max: 10,
        },
    ];

    const achievements = [
        { id: "firstFlux", title: "Erster Funke", description: "Sammle 100 Flux.", icon: "fa-solid fa-sparkles", test: s => s.lifetimeFlux >= 100 },
        { id: "afkStart", title: "Automatisierung", description: "Besitze 10 Anlagen.", icon: "fa-solid fa-robot", test: s => totalBuildings(s) >= 10 },
        { id: "comboTen", title: "Rhythmus gefunden", description: "Erreiche eine x10 Combo.", icon: "fa-solid fa-music", test: s => s.bestCombo >= 10 },
        { id: "meteor", title: "Kosmischer Fang", description: "Sammle 5 Meteor-Events.", icon: "fa-solid fa-meteor", test: s => s.meteorsCollected >= 5 },
        { id: "overdrive", title: "Heiß gelaufen", description: "Zünde 3 Overdrives.", icon: "fa-solid fa-bolt-lightning", test: s => s.overdrives >= 3 },
        { id: "signalMaster", title: "Signal-Profi", description: "Treffe 5 perfekte Signal-Raids.", icon: "fa-solid fa-crosshairs", test: s => s.perfectSignals >= 5 },
        { id: "riftPilot", title: "Riss-Pilot", description: "Versiegle 8 Flux-Risse.", icon: "fa-solid fa-wand-sparkles", test: s => s.riftsSealed >= 8 },
        { id: "cryoTechnician", title: "Kryo-Techniker", description: "Treffe 5 perfekte Kryo-Takte.", icon: "fa-solid fa-snowflake", test: s => s.cryoPerfects >= 5 },
        { id: "collector", title: "Impuls-Sammler", description: "Nutze den Sammelimpuls 30 Mal.", icon: "fa-solid fa-hand-sparkles", test: s => s.collectImpulses >= 30 },
        { id: "activeMiner", title: "Aktiv-Schmied", description: "Führe 300 aktive Kernaktionen aus.", icon: "fa-solid fa-hand-back-fist", test: s => s.clicks >= 300 },
        { id: "pulseMachine", title: "Taktmaschine", description: "Löse 25 aktive Takt-Bursts aus.", icon: "fa-solid fa-burst", test: s => s.activeBursts >= 25 },
        { id: "engineer", title: "Großingenieur", description: "Besitze 75 Anlagen.", icon: "fa-solid fa-gears", test: s => totalBuildings(s) >= 75 },
        { id: "million", title: "Millionen-Schmiede", description: "Sammle 1.000.000 Lifetime-Flux.", icon: "fa-solid fa-vault", test: s => s.totalLifetimeFlux >= 1_000_000 },
        { id: "prestige", title: "Neue Galaxie", description: "Führe dein erstes Prestige aus.", icon: "fa-solid fa-star", test: s => s.prestigeLevel >= 2 },
    ];

    const defaultState = () => ({
        version: SAVE_VERSION,
        flux: 0,
        lifetimeFlux: 0,
        totalLifetimeFlux: 0,
        prestigeLevel: 1,
        shards: 0,
        heat: 0,
        combo: 0,
        bestCombo: 0,
        activeMode: "balanced",
        buildings: {},
        upgrades: {},
        achievements: {},
        lastSaved: now(),
        databaseSavedAt: 0,
        lastManualAt: 0,
        signalReadyAt: now() + 12000,
        riftReadyAt: now() + 18000,
        cryoReadyAt: now() + 24000,
        collectReadyAt: 0,
        overdriveUntil: 0,
        activeBoostUntil: 0,
        passiveBoostUntil: 0,
        meteorsCollected: 0,
        overdrives: 0,
        perfectSignals: 0,
        riftsSealed: 0,
        cryoPerfects: 0,
        collectImpulses: 0,
        clicks: 0,
        activePulseCharge: 0,
        activeBursts: 0,
        sessionStartedAt: now(),
    });

    const elements = {
        flux: document.getElementById("nftFlux"),
        cps: document.getElementById("nftCps"),
        manualPower: document.getElementById("nftManualPower"),
        combo: document.getElementById("nftCombo"),
        comboHint: document.getElementById("nftComboHint"),
        shards: document.getElementById("nftShards"),
        heatLabel: document.getElementById("nftHeatLabel"),
        heatFill: document.getElementById("nftHeatFill"),
        modePill: document.getElementById("nftModePill"),
        mineButton: document.getElementById("nftMineButton"),
        collectButton: document.getElementById("nftCollectButton"),
        collectHint: document.getElementById("nftCollectHint"),
        overdriveButton: document.getElementById("nftOverdriveButton"),
        overdriveHint: document.getElementById("nftOverdriveHint"),
        signalButton: document.getElementById("nftSignalButton"),
        signalHint: document.getElementById("nftSignalHint"),
        signalPanel: document.getElementById("nftSignalPanel"),
        signalMarker: document.getElementById("nftSignalMarker"),
        signalZone: document.querySelector("#nftSignalPanel .nft-signal-zone"),
        stopSignalButton: document.getElementById("nftStopSignalButton"),
        riftButton: document.getElementById("nftRiftButton"),
        riftHint: document.getElementById("nftRiftHint"),
        riftPanel: document.getElementById("nftRiftPanel"),
        riftMarker: document.getElementById("nftRiftMarker"),
        riftZone: document.querySelector("#nftRiftPanel .nft-signal-zone"),
        stopRiftButton: document.getElementById("nftStopRiftButton"),
        cryoButton: document.getElementById("nftCryoButton"),
        cryoHint: document.getElementById("nftCryoHint"),
        cryoPanel: document.getElementById("nftCryoPanel"),
        cryoMarker: document.getElementById("nftCryoMarker"),
        cryoZone: document.querySelector("#nftCryoPanel .nft-signal-zone"),
        stopCryoButton: document.getElementById("nftStopCryoButton"),
        buildings: document.getElementById("nftBuildings"),
        buildingCount: document.getElementById("nftBuildingCount"),
        upgrades: document.getElementById("nftUpgrades"),
        achievements: document.getElementById("nftAchievements"),
        achievementCount: document.getElementById("nftAchievementCount"),
        prestigeButton: document.getElementById("nftPrestigeButton"),
        prestigeHint: document.getElementById("nftPrestigeHint"),
        toastStack: document.getElementById("nftToastStack"),
        eventLayer: document.getElementById("nftEventLayer"),
        foundry: document.getElementById("nftFoundry"),
        saveButton: document.getElementById("nftSaveButton"),
        saveButtonText: document.getElementById("nftSaveButtonText"),
        resetHeaderButton: document.getElementById("nftResetHeaderButton"),
        exportButton: document.getElementById("nftExportButton"),
        importInput: document.getElementById("nftImportInput"),
        resetButton: document.getElementById("nftResetButton"),
        offlineInfo: document.getElementById("nftOfflineInfo"),
    };

    let state = loadState();
    let lastFrame = now();
    let holdTimer = null;
    let renderQueued = false;
    let shopScrollLockUntil = 0;
    let lastBuildingsRenderKey = "";
    let lastUpgradesRenderKey = "";
    let lastAchievementsRenderKey = "";
    const SHOP_SCROLL_IDLE_MS = 650;
    let activeSignal = null;
    let activeRift = null;
    let activeCryo = null;
    let nextMeteorAt = nextMeteorTime();
    let dbSaveCooldownUntil = 0;
    let lastSpaceMineAt = 0;

    function sanitizeNumber(value, fallback = 0) {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : fallback;
    }

    function clamp(value, min, max) {
        return Math.min(max, Math.max(min, value));
    }

    function format(value) {
        value = Math.max(0, Number(value) || 0);
        const suffixes = ["", "K", "M", "B", "T", "Qa", "Qi", "Sx", "Sp"];
        if (value < 1000) return Math.floor(value).toString();
        let tier = 0;
        while (value >= 1000 && tier < suffixes.length - 1) {
            value /= 1000;
            tier += 1;
        }
        const digits = value >= 100 ? 0 : value >= 10 ? 1 : 2;
        return `${value.toFixed(digits)}${suffixes[tier]}`;
    }

    function formatRate(value) {
        value = Math.max(0, Number(value) || 0);
        if (value > 0 && value < 10) {
            const digits = value < 1 ? 2 : 1;
            return value.toFixed(digits).replace(/\.?0+$/, "");
        }
        return format(value);
    }

    function formatSeconds(seconds) {
        seconds = Math.max(0, Math.floor(seconds));
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = seconds % 60;
        if (hours > 0) return `${hours}h ${minutes}m`;
        if (minutes > 0) return `${minutes}m ${secs}s`;
        return `${secs}s`;
    }

    function mergeState(raw) {
        const base = defaultState();
        const merged = { ...base, ...(raw || {}) };
        merged.flux = Math.max(0, sanitizeNumber(merged.flux));
        merged.lifetimeFlux = Math.max(0, sanitizeNumber(merged.lifetimeFlux));
        merged.totalLifetimeFlux = Math.max(merged.lifetimeFlux, sanitizeNumber(merged.totalLifetimeFlux));
        merged.prestigeLevel = Math.max(1, Math.floor(sanitizeNumber(merged.prestigeLevel, 1)));
        merged.shards = Math.max(0, Math.floor(sanitizeNumber(merged.shards)));
        merged.heat = Math.max(0, sanitizeNumber(merged.heat));
        merged.combo = Math.max(0, sanitizeNumber(merged.combo));
        merged.bestCombo = Math.max(0, sanitizeNumber(merged.bestCombo));
        merged.activeMode = ["balanced", "active", "afk"].includes(merged.activeMode) ? merged.activeMode : "balanced";
        merged.buildings = typeof merged.buildings === "object" && merged.buildings ? merged.buildings : {};
        merged.upgrades = typeof merged.upgrades === "object" && merged.upgrades ? merged.upgrades : {};
        merged.heat = clamp(merged.heat, 0, maxHeat(merged));
        merged.achievements = typeof merged.achievements === "object" && merged.achievements ? merged.achievements : {};
        merged.lastSaved = Math.max(0, sanitizeNumber(merged.lastSaved, now()));
        merged.databaseSavedAt = Math.max(0, sanitizeNumber(merged.databaseSavedAt));
        merged.signalReadyAt = Math.max(0, sanitizeNumber(merged.signalReadyAt, now() + 12000));
        merged.riftReadyAt = Math.max(0, sanitizeNumber(merged.riftReadyAt, now() + 18000));
        merged.cryoReadyAt = Math.max(0, sanitizeNumber(merged.cryoReadyAt, now() + 24000));
        merged.collectReadyAt = Math.max(0, sanitizeNumber(merged.collectReadyAt));
        merged.overdriveUntil = Math.max(0, sanitizeNumber(merged.overdriveUntil));
        merged.activeBoostUntil = Math.max(0, sanitizeNumber(merged.activeBoostUntil));
        merged.passiveBoostUntil = Math.max(0, sanitizeNumber(merged.passiveBoostUntil));
        merged.meteorsCollected = Math.max(0, Math.floor(sanitizeNumber(merged.meteorsCollected)));
        merged.overdrives = Math.max(0, Math.floor(sanitizeNumber(merged.overdrives)));
        merged.perfectSignals = Math.max(0, Math.floor(sanitizeNumber(merged.perfectSignals)));
        merged.riftsSealed = Math.max(0, Math.floor(sanitizeNumber(merged.riftsSealed)));
        merged.cryoPerfects = Math.max(0, Math.floor(sanitizeNumber(merged.cryoPerfects)));
        merged.collectImpulses = Math.max(0, Math.floor(sanitizeNumber(merged.collectImpulses)));
        merged.clicks = Math.max(0, Math.floor(sanitizeNumber(merged.clicks)));
        merged.activePulseCharge = Math.max(0, sanitizeNumber(merged.activePulseCharge));
        merged.activeBursts = Math.max(0, Math.floor(sanitizeNumber(merged.activeBursts)));
        return merged;
    }

    function loadState() {
        try {
            const raw = JSON.parse(localStorage.getItem(SAVE_KEY) || "null");
            const loaded = mergeState(raw);
            applyOfflineProgress(loaded);
            return loaded;
        } catch (error) {
            console.warn("Nebula Forge Save konnte nicht gelesen werden.", error);
            return defaultState();
        }
    }

    function saveState(showToast = false) {
        state.lastSaved = now();
        try {
            localStorage.setItem(SAVE_KEY, JSON.stringify(state));
            if (showToast) showMessage("Gespeichert", "Nebula Forge wurde lokal gespeichert.");
        } catch (error) {
            console.warn("Nebula Forge Save konnte nicht geschrieben werden.", error);
            showMessage("Speichern fehlgeschlagen", "Der Browser hat den lokalen Spielstand blockiert.");
        }
    }


    function getCookie(name) {
        const cookieValue = document.cookie
            .split(";")
            .map(part => part.trim())
            .find(part => part.startsWith(`${name}=`));
        return cookieValue ? decodeURIComponent(cookieValue.slice(name.length + 1)) : "";
    }

    function countAchievementUnlocks(source = state) {
        return Object.values(source.achievements || {}).filter(Boolean).length;
    }

    function totalUpgradeLevels(source = state) {
        return upgrades.reduce((sum, item) => sum + upgradeLevel(item.id, source), 0);
    }

    function updateDatabaseSaveButton() {
        if (!elements.saveButton || !elements.saveButtonText) return;

        if (!USER_IS_AUTHENTICATED) {
            elements.saveButton.disabled = false;
            elements.saveButtonText.textContent = "Login nötig";
            return;
        }

        const remaining = Math.ceil(Math.max(0, dbSaveCooldownUntil - now()) / 1000);
        if (remaining > 0) {
            elements.saveButton.disabled = true;
            elements.saveButtonText.textContent = `Speichern ${remaining}s`;
            return;
        }

        elements.saveButton.disabled = false;
        elements.saveButtonText.textContent = "Speichern";
    }

    function setDatabaseSaveCooldown(seconds) {
        const cooldownSeconds = Math.max(0, Math.ceil(Number(seconds) || 0));
        dbSaveCooldownUntil = cooldownSeconds > 0 ? now() + cooldownSeconds * 1000 : 0;
        updateDatabaseSaveButton();
    }

    function buildDatabaseSavePayload() {
        const saveData = JSON.parse(JSON.stringify({ ...state, lastSaved: now() }));
        return {
            save_data: saveData,
            flux: state.flux,
            lifetime_flux: state.lifetimeFlux,
            total_lifetime_flux: state.totalLifetimeFlux,
            cps: calculateCps(),
            manual_power: manualPower(),
            prestige_level: state.prestigeLevel,
            shards: state.shards,
            achievements_count: countAchievementUnlocks(),
            upgrades_count: totalUpgradeLevels(),
            buildings_count: totalBuildings(),
        };
    }

    async function loadDatabaseSave() {
        if (!USER_IS_AUTHENTICATED || !DB_LOAD_URL) {
            updateDatabaseSaveButton();
            return;
        }

        try {
            const response = await fetch(DB_LOAD_URL, {
                headers: { "X-Requested-With": "XMLHttpRequest" },
                credentials: "same-origin",
            });
            if (!response.ok) {
                updateDatabaseSaveButton();
                return;
            }

            const data = await response.json();
            const saveData = data && typeof data.save_data === "object" ? data.save_data : null;
            setDatabaseSaveCooldown(data.next_save_in_seconds || 0);

            if (!saveData) return;

            const remoteSavedAt = sanitizeNumber(
                saveData.databaseSavedAt,
                data.save && data.save.last_manual_save ? Date.parse(data.save.last_manual_save) : 0
            );
            const localDbSavedAt = sanitizeNumber(state.databaseSavedAt);
            const localHasProgress = hadLocalSaveAtStartup && (state.totalLifetimeFlux > 0 || totalBuildings(state) > 0 || state.shards > 0 || state.prestigeLevel > 1);
            const shouldLoadRemote = !hadLocalSaveAtStartup || !localHasProgress || remoteSavedAt > localDbSavedAt + 2000;

            if (!shouldLoadRemote) return;

            const loaded = mergeState(saveData);
            applyOfflineProgress(loaded);
            state = loaded;
            saveState(false);
            renderAll(true);
            showMessage("Datenbank-Spielstand geladen", "Dein gespeicherter Nebula-Forge-Stand wurde geladen.");
        } catch (error) {
            console.warn("Nebula Forge Datenbank-Spielstand konnte nicht geladen werden.", error);
            updateDatabaseSaveButton();
        }
    }

    async function saveDatabaseState() {
        if (!USER_IS_AUTHENTICATED) {
            showMessage("Login nötig", "Melde dich an, um in der Datenbank zu speichern.");
            return;
        }

        if (!DB_SAVE_URL) {
            showMessage("Speichern nicht verfügbar", "Die Datenbank-Speicherroute fehlt.");
            return;
        }

        const remaining = Math.ceil(Math.max(0, dbSaveCooldownUntil - now()) / 1000);
        if (remaining > 0) {
            showMessage("Speichern lädt", `Du kannst in ${remaining}s wieder in der Datenbank speichern.`);
            updateDatabaseSaveButton();
            return;
        }

        saveState(false);
        if (elements.saveButton) elements.saveButton.disabled = true;
        if (elements.saveButtonText) elements.saveButtonText.textContent = "Speichert...";

        try {
            const response = await fetch(DB_SAVE_URL, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCookie("csrftoken"),
                    "X-Requested-With": "XMLHttpRequest",
                },
                body: JSON.stringify(buildDatabaseSavePayload()),
            });
            const data = await response.json().catch(() => ({}));

            if (!response.ok || data.status !== "ok") {
                setDatabaseSaveCooldown(data.next_save_in_seconds || 0);
                showMessage("Speichern fehlgeschlagen", data.message || "Der Datenbank-Save wurde abgelehnt.");
                return;
            }

            const savedAt = data.save && data.save.last_manual_save ? Date.parse(data.save.last_manual_save) : now();
            state.databaseSavedAt = Number.isFinite(savedAt) ? savedAt : now();
            saveState(false);
            setDatabaseSaveCooldown(data.next_save_in_seconds || DB_SAVE_COOLDOWN_SECONDS);
            showMessage("Datenbank gespeichert", "Dein Spielstand wurde gespeichert. Nächster DB-Save in 60s.");
        } catch (error) {
            console.warn("Nebula Forge Datenbank-Speichern fehlgeschlagen.", error);
            showMessage("Speichern fehlgeschlagen", "Der Datenbank-Save konnte nicht gesendet werden.");
            updateDatabaseSaveButton();
        }
    }

    function applyOfflineProgress(loaded) {
        const elapsed = Math.floor((now() - sanitizeNumber(loaded.lastSaved, now())) / 1000);
        if (elapsed < 15) return;

        const cap = offlineCapHours(loaded) * 3600;
        const usedSeconds = Math.min(elapsed, cap);
        const rate = calculateCps(loaded);
        const gain = rate * usedSeconds * offlineEfficiency(loaded);
        if (gain <= 0) return;

        loaded.flux += gain;
        loaded.lifetimeFlux += gain;
        loaded.totalLifetimeFlux += gain;
        loaded.lastSaved = now();
        window.setTimeout(() => {
            showMessage("AFK-Ertrag eingesammelt", `${format(gain)} Flux für ${formatSeconds(usedSeconds)} Offline-Zeit.`);
            if (elements.offlineInfo) {
                elements.offlineInfo.dataset.touched = "true";
                elements.offlineInfo.textContent = `Letzter AFK-Ertrag: ${format(gain)} Flux für ${formatSeconds(usedSeconds)}. Offline-Cap: ${offlineCapHours(loaded)}h.`;
            }
        }, 250);
    }

    function buildingCount(id, source = state) {
        return Math.max(0, Math.floor(sanitizeNumber(source.buildings[id])));
    }

    function upgradeLevel(id, source = state) {
        return Math.max(0, Math.floor(sanitizeNumber(source.upgrades[id])));
    }

    function totalBuildings(source = state) {
        return buildings.reduce((sum, item) => sum + buildingCount(item.id, source), 0);
    }

    function uniqueBuildings(source = state) {
        return buildings.reduce((sum, item) => sum + (buildingCount(item.id, source) > 0 ? 1 : 0), 0);
    }

    function costFor(item, owned) {
        return Math.floor(item.baseCost * Math.pow(item.growth, owned));
    }

    function prestigeMultiplier(source = state) {
        return 1 + (source.prestigeLevel - 1) * 0.12 + source.shards * 0.045;
    }

    function focusPassive(source = state) {
        if (source.activeMode === "afk") return 1.2;
        if (source.activeMode === "active") return 0.9;
        return 1;
    }

    function focusManual(source = state) {
        if (source.activeMode === "active") return 1.25;
        if (source.activeMode === "afk") return 0.85;
        return 1;
    }

    function passiveMultiplier(source = state) {
        const afk = upgradeLevel("afkProtocol", source);
        const overdrive = source.overdriveUntil > now() ? 2.4 : 1;
        const passiveBoost = source.passiveBoostUntil > now() ? 1.65 + upgradeLevel("harmonicCapacitor", source) * 0.08 : 1;
        const logistics = 1 + upgradeLevel("stellarLogistics", source) * 0.065 + uniqueBuildings(source) * upgradeLevel("autoCalibrator", source) * 0.012;
        return (1 + afk * 0.08) * logistics * prestigeMultiplier(source) * focusPassive(source) * overdrive * passiveBoost;
    }

    function calculateCps(source = state) {
        const base = buildings.reduce((sum, item) => sum + buildingCount(item.id, source) * item.rate, 0);
        return base * passiveMultiplier(source);
    }

    function maxHeat(source = state) {
        return 100 + upgradeLevel("coolingLoop", source) * 12;
    }

    function heatDecay(source = state) {
        return 4.5 + upgradeLevel("coolingLoop", source) * 0.8;
    }

    function comboMultiplier(source = state) {
        const comboBonus = 0.035 + upgradeLevel("comboMatrix", source) * 0.011 + upgradeLevel("clickResonator", source) * 0.006;
        return 1 + Math.min(source.combo, maxCombo(source)) * comboBonus;
    }

    function maxCombo(source = state) {
        return 25 + upgradeLevel("comboMatrix", source) * 8 + upgradeLevel("clickResonator", source) * 10;
    }

    function activeTapSeconds(source = state) {
        const sync = upgradeLevel("coreSynchronizer", source);
        const rhythm = upgradeLevel("rhythmExtractor", source);
        const heatRecycler = upgradeLevel("heatRecycler", source);
        const comboRatio = clamp(Math.min(source.combo, maxCombo(source)) / Math.max(1, maxCombo(source)), 0, 1);
        const modeBonus = source.activeMode === "active" ? 1.35 : source.activeMode === "afk" ? 0.72 : 1;
        const heatRatio = clamp(source.heat / Math.max(1, maxHeat(source)), 0, 1);
        const heatBonus = 1 + heatRatio * heatRecycler * 0.026;
        const seconds = (0.13 + sync * 0.018 + rhythm * comboRatio * 0.018) * modeBonus * heatBonus;
        return clamp(seconds, 0.08, 0.9);
    }

    function activePulseRequirement(source = state) {
        return Math.max(7.5, 14 - upgradeLevel("pulseCondenser", source) * 0.55 - upgradeLevel("clickResonator", source) * 0.18);
    }

    function activePulseSeconds(source = state) {
        return 1.2 + upgradeLevel("pulseCondenser", source) * 0.18 + upgradeLevel("rhythmExtractor", source) * 0.055;
    }

    function manualPower(source = state) {
        const gloves = upgradeLevel("plasmaGloves", source);
        const neural = 1 + upgradeLevel("neuralPicks", source) * 0.11;
        const activeBoost = source.activeBoostUntil > now() ? 1.85 + upgradeLevel("harmonicCapacitor", source) * 0.05 : 1;
        const heatRatio = clamp(source.heat / Math.max(1, maxHeat(source)), 0, 1);
        const hotPenalty = source.heat >= maxHeat(source) ? 0.62 : 1;
        const heatRecycler = 1 + heatRatio * upgradeLevel("heatRecycler", source) * 0.025;
        const basePower = (1 + gloves * 0.9) * neural * comboMultiplier(source) * prestigeMultiplier(source) * focusManual(source) * activeBoost * hotPenalty * heatRecycler;
        const afkEcho = calculateCps(source) * activeTapSeconds(source) * activeBoost;
        return Math.max(1, basePower + afkEcho);
    }

    function offlineEfficiency(source = state) {
        return clamp(0.55 + upgradeLevel("afkProtocol", source) * 0.025, 0.55, 0.92);
    }

    function offlineCapHours(source = state) {
        return 4 + upgradeLevel("deepStorage", source) * 2;
    }

    function eventRewardMultiplier(source = state) {
        return 1 + upgradeLevel("riftAmplifier", source) * 0.12 + upgradeLevel("meteorMagnet", source) * 0.025;
    }

    function eventCooldownMs(base, min = 6000) {
        const reduction = upgradeLevel("eventRelay") * 1200 + upgradeLevel("harmonicCapacitor") * 450;
        return Math.max(min, base - reduction);
    }

    function eventBoostDuration(base) {
        return base + upgradeLevel("harmonicCapacitor") * 1600;
    }

    function prestigeRequirement() {
        return 250000 * Math.pow(state.prestigeLevel, 2.1);
    }

    function prestigeReward() {
        if (state.lifetimeFlux < prestigeRequirement()) return 0;
        return Math.max(1, Math.floor(Math.sqrt(state.lifetimeFlux / prestigeRequirement())));
    }

    function addFlux(amount, reason = "") {
        amount = Math.max(0, sanitizeNumber(amount));
        if (amount <= 0) return;
        state.flux += amount;
        state.lifetimeFlux += amount;
        state.totalLifetimeFlux += amount;
        if (reason) floatingGain(amount, reason);
        queueRender();
    }

    function spendFlux(amount) {
        amount = Math.max(0, sanitizeNumber(amount));
        if (state.flux < amount) return false;
        state.flux -= amount;
        queueRender();
        return true;
    }

    function activePulseBurst() {
        const reward = Math.max(manualPower() * 5.5, calculateCps() * activePulseSeconds()) * eventRewardMultiplier();
        addFlux(reward, `Takt-Burst +${format(reward)}`);
        state.activeBursts += 1;
        const heatRecycler = upgradeLevel("heatRecycler");
        if (heatRecycler > 0) {
            state.heat = Math.max(0, state.heat - (1.5 + heatRecycler * 0.35));
        }
    }

    function manualMine(multiplier = 1, heatGain = 2.8) {
        const gain = manualPower() * multiplier;
        addFlux(gain, `+${format(gain)}`);
        state.clicks += 1;
        state.combo = Math.min(maxCombo(), state.combo + 1);
        state.bestCombo = Math.max(state.bestCombo, state.combo);
        state.lastManualAt = now();
        state.activePulseCharge += multiplier;
        const pulseRequirement = activePulseRequirement();
        if (state.activePulseCharge >= pulseRequirement) {
            const pulses = Math.floor(state.activePulseCharge / pulseRequirement);
            state.activePulseCharge %= pulseRequirement;
            for (let index = 0; index < Math.min(pulses, 3); index += 1) {
                activePulseBurst();
            }
        }
        state.heat = Math.min(maxHeat(), state.heat + heatGain);
        checkAchievements();
    }

    function floatingGain(amount, text) {
        const foundryRect = elements.foundry.getBoundingClientRect();
        const rootRect = root.getBoundingClientRect();
        const gain = document.createElement("span");
        gain.className = "nft-floating-gain";
        gain.textContent = text || `+${format(amount)}`;
        gain.style.left = `${foundryRect.left - rootRect.left + foundryRect.width / 2 + (Math.random() - 0.5) * 120}px`;
        gain.style.top = `${foundryRect.top - rootRect.top + foundryRect.height / 2 + (Math.random() - 0.5) * 90}px`;
        root.appendChild(gain);
        window.setTimeout(() => gain.remove(), 950);
    }

    function buyBuilding(id) {
        const item = buildings.find(entry => entry.id === id);
        if (!item) return;
        const owned = buildingCount(id);
        const cost = costFor(item, owned);
        if (!spendFlux(cost)) {
            showMessage("Nicht genug Flux", `${item.name} kostet ${format(cost)} Flux.`);
            return;
        }
        state.buildings[id] = owned + 1;
        renderStats();
        renderShopLists(true);
        checkAchievements();
        saveState();
    }

    function buyUpgrade(id) {
        const item = upgrades.find(entry => entry.id === id);
        if (!item) return;
        const level = upgradeLevel(id);
        if (level >= item.max) return;
        const cost = costFor(item, level);
        if (!spendFlux(cost)) {
            showMessage("Nicht genug Flux", `${item.name} kostet ${format(cost)} Flux.`);
            return;
        }
        state.upgrades[id] = level + 1;
        state.heat = clamp(state.heat, 0, maxHeat());
        renderStats();
        renderShopLists(true);
        checkAchievements();
        saveState();
    }

    function collectImpulseRewardPreview(source = state) {
        const collector = upgradeLevel("collectorArray", source);
        const secondsOfAfk = 2.2 + collector * 0.28;
        const passivePart = calculateCps(source) * secondsOfAfk;
        const activePart = manualPower(source) * (0.65 + collector * 0.06);
        const coolBonus = source.heat <= maxHeat(source) * 0.45 ? 1.06 : 1;
        const eventBonus = 1 + (eventRewardMultiplier(source) - 1) * 0.35;
        return {
            secondsOfAfk,
            reward: Math.max(3, (passivePart + activePart) * coolBonus * eventBonus),
        };
    }

    function collectImpulseCooldownMs(source = state) {
        const collector = upgradeLevel("collectorArray", source);
        const relay = upgradeLevel("eventRelay", source);
        return Math.max(8500, 18000 - collector * 600 - relay * 250);
    }

    function collectImpulse() {
        const currentTime = now();
        if (currentTime < state.collectReadyAt) {
            showMessage("Sammelimpuls lädt", `Wieder bereit in ${formatSeconds((state.collectReadyAt - currentTime) / 1000)}.`);
            return;
        }
        const collector = upgradeLevel("collectorArray");
        const preview = collectImpulseRewardPreview();
        const reward = preview.reward;
        addFlux(reward, `Impuls +${format(reward)}`);
        state.combo = Math.min(maxCombo(), state.combo + 1 + Math.floor(collector / 6));
        state.bestCombo = Math.max(state.bestCombo, state.combo);
        state.lastManualAt = currentTime;
        state.heat = Math.min(maxHeat(), state.heat + 1.15);
        state.collectImpulses += 1;
        state.collectReadyAt = currentTime + collectImpulseCooldownMs();
        showMessage("Sammelimpuls", `Kleiner Sofort-Schub: ${formatSeconds(preview.secondsOfAfk)} AFK-Produktion gesammelt.`);
        checkAchievements();
        saveState();
    }

    function startOverdrive() {
        const readyHeat = maxHeat() * 0.92;
        if (state.heat < readyHeat) {
            showMessage("Overdrive lädt", `Du brauchst mindestens ${Math.ceil(readyHeat)} Hitze.`);
            return;
        }
        const duration = 9000 + upgradeLevel("coolingLoop") * 750;
        const burst = Math.max(manualPower() * 25, calculateCps() * 18);
        state.heat = 0;
        state.overdriveUntil = now() + duration;
        state.overdrives += 1;
        addFlux(burst, `Overdrive +${format(burst)}`);
        showMessage("Overdrive gezündet", `Passive Produktion x2,4 für ${formatSeconds(duration / 1000)}.`);
        checkAchievements();
        saveState();
    }

    function randomRange(min, max) {
        return min + Math.random() * (max - min);
    }

    function createTimingWindow(perfectWidth, closePadding) {
        const safeMargin = 6;
        const minStart = safeMargin + closePadding;
        const maxStart = 100 - safeMargin - closePadding - perfectWidth;
        const perfectStart = randomRange(minStart, Math.max(minStart, maxStart));
        const perfectEnd = perfectStart + perfectWidth;
        return {
            perfectStart,
            perfectEnd,
            closeStart: Math.max(0, perfectStart - closePadding),
            closeEnd: Math.min(100, perfectEnd + closePadding),
        };
    }

    function applyTimingZone(zoneElement, timingWindow) {
        if (!zoneElement || !timingWindow) return;
        zoneElement.style.left = `${timingWindow.perfectStart}%`;
        zoneElement.style.width = `${timingWindow.perfectEnd - timingWindow.perfectStart}%`;
    }

    function isInsideTimingWindow(position, timingWindow, mode) {
        if (!timingWindow) return false;
        if (mode === "perfect") {
            return position >= timingWindow.perfectStart && position <= timingWindow.perfectEnd;
        }
        return position >= timingWindow.closeStart && position <= timingWindow.closeEnd;
    }

    function startSignalRaid() {
        if (activeSignal) {
            stopSignalRaid();
            return;
        }
        const currentTime = now();
        if (currentTime < state.signalReadyAt) {
            showMessage("Signal lädt", `Bereit in ${formatSeconds((state.signalReadyAt - currentTime) / 1000)}.`);
            return;
        }
        const timingWindow = createTimingWindow(20, 10);
        activeSignal = {
            startedAt: currentTime,
            position: 0,
            direction: 1,
            speed: 42 + Math.min(40, state.prestigeLevel * 2 + upgradeLevel("comboMatrix") * 2),
            timingWindow,
        };
        applyTimingZone(elements.signalZone, timingWindow);
        elements.signalPanel.hidden = false;
        elements.signalButton.querySelector("strong").textContent = "Signal stoppen";
        elements.signalHint.textContent = "Marker treffen";
    }

    function stopSignalRaid() {
        if (!activeSignal) return;
        const position = activeSignal.position;
        const perfect = isInsideTimingWindow(position, activeSignal.timingWindow, "perfect");
        const close = isInsideTimingWindow(position, activeSignal.timingWindow, "close");
        let rewardMultiplier = close ? 35 : 12;
        let boostDuration = eventBoostDuration(close ? 14000 : 7000);
        if (perfect) {
            rewardMultiplier = 65;
            boostDuration = eventBoostDuration(24000);
            state.perfectSignals += 1;
        }
        const reward = (manualPower() * rewardMultiplier + calculateCps() * (perfect ? 22 : close ? 10 : 4)) * eventRewardMultiplier();
        addFlux(reward, `${perfect ? "Perfekt" : close ? "Treffer" : "Signal"} +${format(reward)}`);
        state.activeBoostUntil = now() + boostDuration;
        state.signalReadyAt = now() + eventCooldownMs(36000 - upgradeLevel("meteorMagnet") * 900, 12000);
        showMessage(
            perfect ? "Perfekter Signal-Raid" : close ? "Signal getroffen" : "Signal verfehlt",
            `${format(reward)} Flux und aktiver Boost für ${formatSeconds(boostDuration / 1000)}.`
        );
        activeSignal = null;
        elements.signalPanel.hidden = true;
        elements.signalButton.querySelector("strong").textContent = "Signal-Raid";
        checkAchievements();
        saveState();
    }

    function startRiftEvent() {
        if (activeRift) {
            stopRiftEvent();
            return;
        }
        const currentTime = now();
        if (currentTime < state.riftReadyAt) {
            showMessage("Flux-Riss lädt", `Bereit in ${formatSeconds((state.riftReadyAt - currentTime) / 1000)}.`);
            return;
        }
        const timingWindow = createTimingWindow(16, 9);
        activeRift = {
            startedAt: currentTime,
            position: 100,
            direction: -1,
            speed: 58 + upgradeLevel("eventRelay") * 2.5 + Math.min(18, state.prestigeLevel * 1.5),
            timingWindow,
        };
        applyTimingZone(elements.riftZone, timingWindow);
        elements.riftPanel.hidden = false;
        elements.riftButton.querySelector("strong").textContent = "Riss versiegeln";
        elements.riftHint.textContent = "Marker treffen";
    }

    function stopRiftEvent() {
        if (!activeRift) return;
        const position = activeRift.position;
        const perfect = isInsideTimingWindow(position, activeRift.timingWindow, "perfect");
        const close = isInsideTimingWindow(position, activeRift.timingWindow, "close");
        const boostDuration = eventBoostDuration(perfect ? 26000 : close ? 15000 : 6500);
        const reward = (manualPower() * (perfect ? 95 : close ? 48 : 15) + calculateCps() * (perfect ? 34 : close ? 16 : 5)) * eventRewardMultiplier();
        addFlux(reward, `${perfect ? "Riss perfekt" : close ? "Riss" : "Streifschuss"} +${format(reward)}`);
        if (close) {
            state.passiveBoostUntil = now() + boostDuration;
            state.riftsSealed += 1;
        }
        state.heat = Math.min(maxHeat(), state.heat + (perfect ? 8 : close ? 13 : 19));
        state.riftReadyAt = now() + eventCooldownMs(42000, 15000);
        showMessage(
            perfect ? "Flux-Riss perfekt versiegelt" : close ? "Flux-Riss stabilisiert" : "Flux-Riss instabil",
            close ? `${format(reward)} Flux und AFK-Boost für ${formatSeconds(boostDuration / 1000)}.` : `${format(reward)} Flux, aber kein AFK-Boost.`
        );
        activeRift = null;
        elements.riftPanel.hidden = true;
        elements.riftButton.querySelector("strong").textContent = "Flux-Riss";
        checkAchievements();
        saveState();
    }

    function startCryoEvent() {
        if (activeCryo) {
            stopCryoEvent();
            return;
        }
        const currentTime = now();
        if (currentTime < state.cryoReadyAt) {
            showMessage("Kryo-Takt lädt", `Bereit in ${formatSeconds((state.cryoReadyAt - currentTime) / 1000)}.`);
            return;
        }
        const timingWindow = createTimingWindow(16, 7);
        activeCryo = {
            startedAt: currentTime,
            position: 0,
            direction: 1,
            speed: 72 + upgradeLevel("eventRelay") * 2,
            timingWindow,
        };
        applyTimingZone(elements.cryoZone, timingWindow);
        elements.cryoPanel.hidden = false;
        elements.cryoButton.querySelector("strong").textContent = "Kryo stoppen";
        elements.cryoHint.textContent = "kaltes Fenster treffen";
    }

    function stopCryoEvent() {
        if (!activeCryo) return;
        const position = activeCryo.position;
        const perfect = isInsideTimingWindow(position, activeCryo.timingWindow, "perfect");
        const close = isInsideTimingWindow(position, activeCryo.timingWindow, "close");
        const beforeHeat = state.heat;
        const heatDrop = close ? maxHeat() * (perfect ? 0.58 : 0.34) : maxHeat() * 0.12;
        state.heat = Math.max(0, state.heat - heatDrop);
        const boostDuration = eventBoostDuration(perfect ? 22000 : close ? 12000 : 5000);
        const reward = (manualPower() * (perfect ? 55 : close ? 24 : 8) + calculateCps() * (perfect ? 13 : close ? 6 : 2)) * eventRewardMultiplier();
        addFlux(reward, `${perfect ? "Kryo perfekt" : close ? "Kryo" : "Kühlung"} +${format(reward)}`);
        if (close) state.activeBoostUntil = now() + boostDuration;
        if (perfect) state.cryoPerfects += 1;
        state.cryoReadyAt = now() + eventCooldownMs(34000, 12000);
        showMessage(
            perfect ? "Perfekter Kryo-Takt" : close ? "Kryo-Takt getroffen" : "Kryo-Takt verpasst",
            `${format(reward)} Flux, -${Math.round(Math.min(beforeHeat, heatDrop))} Hitze${close ? ` und aktiver Boost für ${formatSeconds(boostDuration / 1000)}` : ""}.`
        );
        activeCryo = null;
        elements.cryoPanel.hidden = true;
        elements.cryoButton.querySelector("strong").textContent = "Kryo-Takt";
        checkAchievements();
        saveState();
    }

    function nextMeteorTime() {
        const magnet = upgradeLevel("meteorMagnet");
        const min = Math.max(9000, 23000 - magnet * 1300);
        const max = Math.max(16000, 44000 - magnet * 2200);
        return now() + min + Math.random() * (max - min);
    }

    function rectanglesOverlap(a, b) {
        return a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
    }

    function getSafeMeteorPosition() {
        const layerRect = elements.eventLayer?.getBoundingClientRect();
        const coreRect = elements.mineButton?.getBoundingClientRect();
        if (!layerRect || !coreRect || layerRect.width <= 0 || layerRect.height <= 0) {
            return { left: "12%", top: "12%" };
        }

        const meteorSize = Math.max(44, Math.min(66, layerRect.width * 0.12));
        const padding = 14;
        const coreSafeRect = {
            left: coreRect.left - layerRect.left - meteorSize * 0.85,
            right: coreRect.right - layerRect.left + meteorSize * 0.85,
            top: coreRect.top - layerRect.top - meteorSize * 0.85,
            bottom: coreRect.bottom - layerRect.top + meteorSize * 0.85,
        };

        const maxLeft = Math.max(padding, layerRect.width - meteorSize - padding);
        const maxTop = Math.max(padding, layerRect.height - meteorSize - padding);

        for (let attempt = 0; attempt < 28; attempt += 1) {
            const left = padding + Math.random() * Math.max(1, maxLeft - padding);
            const top = padding + Math.random() * Math.max(1, maxTop - padding);
            const meteorRect = {
                left,
                right: left + meteorSize,
                top,
                bottom: top + meteorSize,
            };
            if (!rectanglesOverlap(meteorRect, coreSafeRect)) {
                return { left: `${left}px`, top: `${top}px` };
            }
        }

        const fallbackSpots = [
            { left: padding, top: padding },
            { left: maxLeft, top: padding },
            { left: padding, top: maxTop },
            { left: maxLeft, top: maxTop },
        ];
        const spot = fallbackSpots[Math.floor(Math.random() * fallbackSpots.length)];
        return { left: `${spot.left}px`, top: `${spot.top}px` };
    }

    function spawnMeteor() {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "nft-meteor";
        button.innerHTML = '<i class="fa-solid fa-meteor"></i>';
        const position = getSafeMeteorPosition();
        button.style.left = position.left;
        button.style.top = position.top;
        const timeout = window.setTimeout(() => button.remove(), 7600);
        let collected = false;
        const collectMeteor = (event) => {
            if (event) {
                event.preventDefault();
                event.stopPropagation();
            }
            if (collected) return;
            collected = true;
            window.clearTimeout(timeout);
            const reward = Math.max(80, (manualPower() * (35 + upgradeLevel("meteorMagnet") * 7) + calculateCps() * 12) * eventRewardMultiplier());
            state.meteorsCollected += 1;
            state.combo = Math.min(maxCombo(), state.combo + 4);
            addFlux(reward, `Meteor +${format(reward)}`);
            showMessage("Meteor eingesammelt", `+${format(reward)} Flux und +4 Combo.`);
            button.remove();
            checkAchievements();
            saveState();
        };
        button.addEventListener("pointerdown", collectMeteor);
        button.addEventListener("click", collectMeteor);
        elements.eventLayer.appendChild(button);
        nextMeteorAt = nextMeteorTime();
    }

    function checkAchievements() {
        let changed = false;
        achievements.forEach(item => {
            if (!state.achievements[item.id] && item.test(state)) {
                state.achievements[item.id] = now();
                changed = true;
                showMessage("Erfolg freigeschaltet", item.title);
            }
        });
        if (changed) {
            saveState();
            renderShopLists(true);
        }
        return changed;
    }

    function performPrestige() {
        updateDatabaseSaveButton();

        const reward = prestigeReward();
        if (reward <= 0) {
            showMessage("Prestige noch nicht bereit", `Du brauchst ${format(prestigeRequirement())} Lifetime-Flux.`);
            return;
        }
        const confirmed = window.confirm(`Neue Galaxie starten und ${reward} Splitter erhalten? Flux, Anlagen und Upgrades werden zurückgesetzt.`);
        if (!confirmed) return;
        const keepTotal = state.totalLifetimeFlux;
        const newLevel = state.prestigeLevel + 1;
        const newShards = state.shards + reward;
        state = defaultState();
        state.prestigeLevel = newLevel;
        state.shards = newShards;
        state.totalLifetimeFlux = keepTotal;
        state.lastSaved = now();
        showMessage("Prestige abgeschlossen", `Galaxie Level ${newLevel}. Dauerhafter Bonus: +${Math.round((prestigeMultiplier() - 1) * 100)}%.`);
        checkAchievements();
        saveState();
        renderAll(true);
    }

    function renderAll(forceShops = false) {
        renderStats();
        updateNebulaAppearance();
        renderShopLists(forceShops);
        renderModes();
    }

    function updateNebulaAppearance() {
        if (!elements.mineButton || !elements.foundry) return;

        const prestigeLevel = Math.max(1, Math.floor(state.prestigeLevel || 1));
        const intensity = Math.max(0, prestigeLevel - 1);
        const shardIntensity = Math.min(20, state.shards || 0);

        const coreScale = 1 + Math.min(0.14, intensity * 0.012);
        const hueRotate = Math.min(165, intensity * 11 + shardIntensity * 1.8);
        const saturation = 1 + Math.min(0.95, intensity * 0.055 + shardIntensity * 0.014);
        const coreHaloOpacity = clamp(0.30 + intensity * 0.055 + shardIntensity * 0.008, 0.30, 0.98);
        const coreShadowSize = 55 + Math.min(90, intensity * 6 + shardIntensity * 2.2);
        const coreShadowDepth = 70 + Math.min(80, intensity * 5 + shardIntensity * 1.8);
        const ringWidth = Math.min(20, intensity * 1.6 + shardIntensity * 0.35);
        const ringOpacity = clamp(0.05 + intensity * 0.018 + shardIntensity * 0.004, 0.05, 0.28);
        const ringScale = 1.08 + Math.min(0.16, intensity * 0.012);
        const glowBlur = 8 + Math.min(16, intensity * 1.15 + shardIntensity * 0.25);

        const starOpacity = clamp(0.32 + intensity * 0.018 + shardIntensity * 0.004, 0.32, 0.72);
        const starScale = 1 + Math.min(0.12, intensity * 0.01);
        const orbitScale = 1 + Math.min(0.18, intensity * 0.014);
        const orbitSpeed = 1 + Math.min(0.85, intensity * 0.055 + shardIntensity * 0.01);
        const nebulaCenter = clamp(0.20 + intensity * 0.022, 0.20, 0.58);
        const nebulaSide = clamp(0.15 + intensity * 0.018, 0.15, 0.46);
        const nebulaDeep = clamp(0.11 + intensity * 0.014, 0.11, 0.38);

        elements.mineButton.style.setProperty("--nft-core-scale", coreScale.toFixed(3));
        elements.mineButton.style.setProperty("--nft-core-hue", `${hueRotate.toFixed(0)}deg`);
        elements.mineButton.style.setProperty("--nft-core-sat", saturation.toFixed(3));
        elements.mineButton.style.setProperty("--nft-core-halo", `rgba(124, 244, 255, ${coreHaloOpacity.toFixed(3)})`);
        elements.mineButton.style.setProperty("--nft-core-shadow-size", `${Math.round(coreShadowSize)}px`);
        elements.mineButton.style.setProperty("--nft-core-shadow-depth", `${Math.round(coreShadowDepth)}px`);
        elements.mineButton.style.setProperty("--nft-core-ring-width", `${ringWidth.toFixed(2)}px`);
        elements.mineButton.style.setProperty("--nft-core-ring-opacity", ringOpacity.toFixed(3));
        elements.mineButton.style.setProperty("--nft-core-ring-scale", ringScale.toFixed(3));
        elements.mineButton.style.setProperty("--nft-core-glow-blur", `${Math.round(glowBlur)}px`);
        elements.mineButton.dataset.prestigeLevel = String(prestigeLevel);

        elements.foundry.style.setProperty("--nft-stars-opacity", starOpacity.toFixed(3));
        elements.foundry.style.setProperty("--nft-star-scale", starScale.toFixed(3));
        elements.foundry.style.setProperty("--nft-orbit-scale", orbitScale.toFixed(3));
        elements.foundry.style.setProperty("--nft-orbit-speed", orbitSpeed.toFixed(3));
        elements.foundry.style.setProperty("--nft-nebula-center", `rgba(124, 244, 255, ${nebulaCenter.toFixed(3)})`);
        elements.foundry.style.setProperty("--nft-nebula-side", `rgba(250, 204, 21, ${nebulaSide.toFixed(3)})`);
        elements.foundry.style.setProperty("--nft-nebula-deep", `rgba(236, 72, 153, ${nebulaDeep.toFixed(3)})`);
        elements.foundry.dataset.prestigeLevel = String(prestigeLevel);
    }

    function renderStats() {
        const cps = calculateCps();
        const manual = manualPower();
        const heatPercent = clamp((state.heat / maxHeat()) * 100, 0, 100);
        elements.flux.textContent = format(state.flux);
        elements.cps.textContent = `${formatRate(cps)}/s`;
        elements.manualPower.textContent = formatRate(manual);
        elements.combo.textContent = `x${comboMultiplier().toFixed(2)}`;
        elements.comboHint.textContent = state.combo > 0
            ? `${Math.floor(state.combo)} Treffer · Takt ${Math.floor(state.activePulseCharge)}/${Math.ceil(activePulseRequirement())}`
            : "halte Rhythmus";
        elements.shards.textContent = format(state.shards);
        elements.heatLabel.textContent = `${Math.round(heatPercent)}%`;
        elements.heatFill.style.width = `${heatPercent}%`;

        const readyHeat = maxHeat() * 0.92;
        const overdriveActive = state.overdriveUntil > now();
        elements.overdriveButton.disabled = overdriveActive || state.heat < readyHeat;
        elements.overdriveHint.textContent = overdriveActive
            ? `aktiv: ${formatSeconds((state.overdriveUntil - now()) / 1000)}`
            : state.heat >= readyHeat
                ? "bereit zum Zünden"
                : `bereit ab ${Math.ceil((readyHeat / maxHeat()) * 100)}% Hitze`;

        const currentTime = now();
        const collectRemaining = Math.max(0, state.collectReadyAt - currentTime);
        elements.collectButton.disabled = collectRemaining > 0;
        elements.collectHint.textContent = collectRemaining > 0
            ? `bereit in ${formatSeconds(collectRemaining / 1000)}`
            : `kleiner Schub ca. ${format(collectImpulseRewardPreview().reward)} Flux`;

        const signalRemaining = Math.max(0, state.signalReadyAt - currentTime);
        elements.signalButton.disabled = signalRemaining > 0 && !activeSignal;
        if (!activeSignal) {
            elements.signalHint.textContent = signalRemaining > 0 ? `bereit in ${formatSeconds(signalRemaining / 1000)}` : "Timing-Bonus bereit";
        }

        const riftRemaining = Math.max(0, state.riftReadyAt - currentTime);
        elements.riftButton.disabled = riftRemaining > 0 && !activeRift;
        if (!activeRift) {
            elements.riftHint.textContent = riftRemaining > 0 ? `bereit in ${formatSeconds(riftRemaining / 1000)}` : "AFK-Boost erspielen";
        }

        const cryoRemaining = Math.max(0, state.cryoReadyAt - currentTime);
        elements.cryoButton.disabled = cryoRemaining > 0 && !activeCryo;
        if (!activeCryo) {
            elements.cryoHint.textContent = cryoRemaining > 0 ? `bereit in ${formatSeconds(cryoRemaining / 1000)}` : "Hitze senken + Boost";
        }

        updateDatabaseSaveButton();

        const reward = prestigeReward();
        const requirement = prestigeRequirement();
        elements.prestigeButton.disabled = reward <= 0;
        elements.prestigeHint.textContent = reward > 0
            ? `Bereit: ${reward} Splitter beim Neustart. Aktueller Bonus danach ca. +${Math.round(((prestigeMultiplier() + reward * 0.045 + 0.12) - 1) * 100)}%.`
            : `${format(state.lifetimeFlux)} / ${format(requirement)} Lifetime-Flux bis zum nächsten Prestige.`;

        if (elements.offlineInfo && !elements.offlineInfo.dataset.touched) {
            elements.offlineInfo.textContent = `Offline-Effizienz: ${Math.round(offlineEfficiency() * 100)}%, Offline-Cap: ${offlineCapHours()}h.`;
        }
    }

    function markShopScrollActive() {
        shopScrollLockUntil = now() + SHOP_SCROLL_IDLE_MS;
    }

    function missingBucket(cost) {
        const missing = Math.max(0, cost - state.flux);
        if (missing <= 0) return 0;
        return Math.ceil(missing / Math.max(1, cost * 0.04));
    }

    function buildingsRenderKey() {
        return buildings.map(item => {
            const owned = buildingCount(item.id);
            const cost = costFor(item, owned);
            const affordable = state.flux >= cost ? 1 : 0;
            return `${item.id}:${owned}:${affordable}:${missingBucket(cost)}`;
        }).join("|");
    }

    function upgradesRenderKey() {
        return upgrades.map(item => {
            const level = upgradeLevel(item.id);
            const maxed = level >= item.max ? 1 : 0;
            const cost = costFor(item, level);
            const affordable = state.flux >= cost && !maxed ? 1 : 0;
            return `${item.id}:${level}:${maxed}:${affordable}:${missingBucket(cost)}`;
        }).join("|");
    }

    function achievementsRenderKey() {
        return achievements.map(item => `${item.id}:${state.achievements[item.id] ? 1 : 0}`).join("|");
    }

    function preserveListScroll(element, renderCallback) {
        if (!element) {
            renderCallback();
            return;
        }

        const previousScrollTop = element.scrollTop;
        const previousMaxScrollTop = Math.max(0, element.scrollHeight - element.clientHeight);
        const distanceFromBottom = previousMaxScrollTop - previousScrollTop;
        renderCallback();

        window.requestAnimationFrame(() => {
            const nextMaxScrollTop = Math.max(0, element.scrollHeight - element.clientHeight);
            const shouldStayAtBottom = previousMaxScrollTop > 0 && distanceFromBottom <= 2;
            element.scrollTop = shouldStayAtBottom
                ? nextMaxScrollTop
                : Math.min(previousScrollTop, nextMaxScrollTop);
        });
    }

    function renderShopLists(force = false) {
        const isUserScrollingShop = now() < shopScrollLockUntil;
        const buildingKey = buildingsRenderKey();
        const upgradeKey = upgradesRenderKey();
        const achievementKey = achievementsRenderKey();

        if ((force || buildingKey !== lastBuildingsRenderKey) && (!isUserScrollingShop || force)) {
            preserveListScroll(elements.buildings, () => {
                renderBuildings();
                lastBuildingsRenderKey = buildingKey;
            });
        }

        if ((force || upgradeKey !== lastUpgradesRenderKey) && (!isUserScrollingShop || force)) {
            preserveListScroll(elements.upgrades, () => {
                renderUpgrades();
                lastUpgradesRenderKey = upgradeKey;
            });
        }

        if ((force || achievementKey !== lastAchievementsRenderKey) && (!isUserScrollingShop || force)) {
            preserveListScroll(elements.achievements, () => {
                renderAchievements();
                lastAchievementsRenderKey = achievementKey;
            });
        }
    }

    function renderBuildings() {
        elements.buildingCount.textContent = totalBuildings();
        elements.buildings.innerHTML = buildings.map(item => {
            const owned = buildingCount(item.id);
            const cost = costFor(item, owned);
            const affordable = state.flux >= cost;
            return `
                <article class="nft-shop-card ${affordable ? "is-affordable" : "is-unaffordable"}">
                    <span class="nft-shop-icon"><i class="${item.icon}"></i></span>
                    <div class="nft-shop-copy">
                        <strong>${item.name}</strong>
                        <p>${item.description}</p>
                        <div class="nft-shop-meta">
                            <span>Besitz: ${owned}</span>
                            <span>+${formatRate(item.rate * passiveMultiplier())}/s je Anlage</span>
                        </div>
                    </div>
                    <button type="button" class="nft-shop-buy ${affordable ? "is-affordable" : "is-unaffordable"}" data-buy-building="${item.id}" aria-disabled="${affordable ? "false" : "true"}" title="${affordable ? "Kaufen" : `Es fehlen ${format(Math.max(0, cost - state.flux))} Flux`}">
                        ${format(cost)} Flux
                        <small>${affordable ? "Kaufen" : `fehlen ${format(Math.max(0, cost - state.flux))}`}</small>
                    </button>
                </article>
            `;
        }).join("");
    }

    function renderUpgrades() {
        elements.upgrades.innerHTML = upgrades.map(item => {
            const level = upgradeLevel(item.id);
            const maxed = level >= item.max;
            const cost = costFor(item, level);
            const affordable = state.flux >= cost && !maxed;
            return `
                <article class="nft-shop-card ${maxed ? "is-locked" : affordable ? "is-affordable" : "is-unaffordable"}">
                    <span class="nft-shop-icon"><i class="${item.icon}"></i></span>
                    <div class="nft-shop-copy">
                        <strong>${item.name}</strong>
                        <p>${item.description}</p>
                        <div class="nft-shop-meta">
                            <span>Level: ${level}/${item.max}</span>
                            <span>${maxed ? "Maximal" : "Nächster Ausbau"}</span>
                        </div>
                    </div>
                    <button type="button" class="nft-shop-buy ${maxed ? "is-maxed" : affordable ? "is-affordable" : "is-unaffordable"}" data-buy-upgrade="${item.id}" ${maxed ? "disabled" : ""} aria-disabled="${affordable ? "false" : "true"}" title="${maxed ? "Maximal ausgebaut" : affordable ? "Kaufen" : `Es fehlen ${format(Math.max(0, cost - state.flux))} Flux`}">
                        ${maxed ? "Max" : `${format(cost)} Flux`}
                        <small>${maxed ? "Fertig" : affordable ? "Kaufen" : `fehlen ${format(Math.max(0, cost - state.flux))}`}</small>
                    </button>
                </article>
            `;
        }).join("");
    }

    function renderAchievements() {
        const done = achievements.filter(item => state.achievements[item.id]).length;
        elements.achievementCount.textContent = `${done}/${achievements.length}`;
        elements.achievements.innerHTML = achievements.map(item => {
            const unlocked = Boolean(state.achievements[item.id]);
            return `
                <article class="nft-achievement-card ${unlocked ? "is-done" : ""}">
                    <span class="nft-achievement-icon"><i class="${unlocked ? item.icon : "fa-solid fa-lock"}"></i></span>
                    <div class="nft-achievement-copy">
                        <strong>${item.title}</strong>
                        <p>${item.description}</p>
                    </div>
                    <span class="nft-shop-meta"><span>${unlocked ? "Erledigt" : "Offen"}</span></span>
                </article>
            `;
        }).join("");
    }

    function renderModes() {
        document.querySelectorAll(".nft-focus-buttons button").forEach(button => {
            button.classList.toggle("is-active", button.dataset.mode === state.activeMode);
        });
        elements.modePill.textContent = state.activeMode === "afk" ? "AFK-Shift" : state.activeMode === "active" ? "Aktiv-Shift" : "Balanced";
    }

    function queueRender() {
        if (renderQueued) return;
        renderQueued = true;
        window.requestAnimationFrame(() => {
            renderQueued = false;
            renderAll();
        });
    }

    function showMessage(title, message = "") {
        const toast = document.createElement("div");
        toast.className = "nft-toast";
        toast.innerHTML = `<strong>${title}</strong>${message ? `<p>${message}</p>` : ""}`;
        elements.toastStack.appendChild(toast);
        window.setTimeout(() => {
            toast.style.opacity = "0";
            toast.style.transform = "translateY(8px)";
        }, 3200);
        window.setTimeout(() => toast.remove(), 3700);
    }

    function exportSave() {
        saveState();
        const payload = {
            format: EXPORT_FORMAT,
            version: SAVE_VERSION,
            exportedAt: new Date().toISOString(),
            state,
        };
        const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `nebula-forge-tycoon-${new Date().toISOString().slice(0, 10)}.json`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
        showMessage("Export erstellt", "Dein Nebula Forge Save wurde heruntergeladen.");
    }

    function importSave(file) {
        if (!file) return;
        const reader = new FileReader();
        reader.onload = () => {
            try {
                const payload = JSON.parse(String(reader.result || ""));
                if (payload.format !== EXPORT_FORMAT || !payload.state) {
                    showMessage("Import fehlgeschlagen", "Die Datei ist kein gültiger Nebula Forge Save.");
                    return;
                }
                const confirmed = window.confirm("Aktuellen Nebula Forge Spielstand durch diesen Import ersetzen?");
                if (!confirmed) return;
                state = mergeState(payload.state);
                state.lastSaved = now();
                saveState();
                renderAll(true);
                showMessage("Import abgeschlossen", "Dein Spielstand wurde geladen.");
            } catch (error) {
                console.warn("Nebula Forge Import fehlgeschlagen.", error);
                showMessage("Import fehlgeschlagen", "Die Datei konnte nicht gelesen werden.");
            } finally {
                elements.importInput.value = "";
            }
        };
        reader.readAsText(file);
    }

    function resetSave() {
        const confirmed = window.confirm("Nebula Forge Tycoon wirklich komplett zurücksetzen?");
        if (!confirmed) return;
        localStorage.removeItem(SAVE_KEY);
        state = defaultState();
        activeSignal = null;
        activeRift = null;
        activeCryo = null;
        elements.signalPanel.hidden = true;
        elements.riftPanel.hidden = true;
        elements.cryoPanel.hidden = true;
        elements.eventLayer.innerHTML = "";
        nextMeteorAt = nextMeteorTime();
        renderAll(true);
        saveState();
        showMessage("Zurückgesetzt", "Du startest wieder mit einer frischen Schmiede.");
    }

    function gameLoop() {
        const currentTime = now();
        const dt = Math.min(1, (currentTime - lastFrame) / 1000);
        lastFrame = currentTime;

        const passive = calculateCps() * dt;
        if (passive > 0) addFlux(passive);

        if (state.heat > 0) {
            state.heat = Math.max(0, state.heat - heatDecay() * dt);
        }

        if (state.combo > 0 && currentTime - state.lastManualAt > 1700 + upgradeLevel("clickResonator") * 170) {
            state.combo = Math.max(0, state.combo - dt * Math.max(1.15, 2.8 - upgradeLevel("clickResonator") * 0.14));
        }

        if (activeSignal) {
            activeSignal.position += activeSignal.direction * activeSignal.speed * dt;
            if (activeSignal.position >= 100) {
                activeSignal.position = 100;
                activeSignal.direction = -1;
            }
            if (activeSignal.position <= 0) {
                activeSignal.position = 0;
                activeSignal.direction = 1;
            }
            elements.signalMarker.style.left = `${activeSignal.position}%`;
            if (currentTime - activeSignal.startedAt > 7000) {
                stopSignalRaid();
            }
        }

        if (activeRift) {
            activeRift.position += activeRift.direction * activeRift.speed * dt;
            if (activeRift.position >= 100) {
                activeRift.position = 100;
                activeRift.direction = -1;
            }
            if (activeRift.position <= 0) {
                activeRift.position = 0;
                activeRift.direction = 1;
            }
            elements.riftMarker.style.left = `${activeRift.position}%`;
            if (currentTime - activeRift.startedAt > 6500) {
                stopRiftEvent();
            }
        }

        if (activeCryo) {
            activeCryo.position += activeCryo.direction * activeCryo.speed * dt;
            if (activeCryo.position >= 100) {
                activeCryo.position = 100;
                activeCryo.direction = -1;
            }
            if (activeCryo.position <= 0) {
                activeCryo.position = 0;
                activeCryo.direction = 1;
            }
            elements.cryoMarker.style.left = `${activeCryo.position}%`;
            if (currentTime - activeCryo.startedAt > 5200) {
                stopCryoEvent();
            }
        }

        if (currentTime >= nextMeteorAt && elements.eventLayer.childElementCount < 2) {
            spawnMeteor();
        }

        checkAchievements();
        queueRender();
        window.requestAnimationFrame(gameLoop);
    }

    function attachEvents() {
        elements.mineButton.addEventListener("pointerdown", event => {
            event.preventDefault();
            elements.mineButton.classList.add("is-pressed");
            manualMine();
            if (holdTimer) window.clearInterval(holdTimer);
            holdTimer = window.setInterval(() => manualMine(0.58, 1.35), 150);
        });

        const stopHolding = () => {
            elements.mineButton.classList.remove("is-pressed");
            if (holdTimer) {
                window.clearInterval(holdTimer);
                holdTimer = null;
            }
        };
        ["pointerup", "pointercancel", "pointerleave"].forEach(name => elements.mineButton.addEventListener(name, stopHolding));

        elements.collectButton.addEventListener("pointerdown", event => {
            event.preventDefault();
            collectImpulse();
        });
        elements.overdriveButton.addEventListener("click", startOverdrive);
        elements.signalButton.addEventListener("click", startSignalRaid);
        elements.stopSignalButton.addEventListener("click", stopSignalRaid);
        elements.riftButton.addEventListener("click", startRiftEvent);
        elements.stopRiftButton.addEventListener("click", stopRiftEvent);
        elements.cryoButton.addEventListener("click", startCryoEvent);
        elements.stopCryoButton.addEventListener("click", stopCryoEvent);
        elements.prestigeButton.addEventListener("click", performPrestige);

        const isTypingTarget = target => {
            if (!target) return false;
            const tagName = target.tagName;
            return target.isContentEditable || tagName === "INPUT" || tagName === "TEXTAREA" || tagName === "SELECT";
        };

        const pulseShortcutButton = button => {
            if (!button) return;
            button.classList.add("is-key-pressed");
            window.setTimeout(() => button.classList.remove("is-key-pressed"), 130);
        };

        const shortcutActions = {
            "1": { button: elements.overdriveButton, run: startOverdrive },
            "Numpad1": { button: elements.overdriveButton, run: startOverdrive },
            "2": { button: elements.signalButton, run: startSignalRaid },
            "Numpad2": { button: elements.signalButton, run: startSignalRaid },
            "3": { button: elements.collectButton, run: collectImpulse },
            "Numpad3": { button: elements.collectButton, run: collectImpulse },
            "4": { button: elements.riftButton, run: startRiftEvent },
            "Numpad4": { button: elements.riftButton, run: startRiftEvent },
            "5": { button: elements.cryoButton, run: startCryoEvent },
            "Numpad5": { button: elements.cryoButton, run: startCryoEvent },
        };

        const pulseCoreButton = () => {
            elements.mineButton.classList.add("is-pressed");
            window.setTimeout(() => elements.mineButton.classList.remove("is-pressed"), 95);
        };

        const mineWithSpace = event => {
            const currentTime = now();
            const minimumInterval = event.repeat ? SPACE_MINE_REPEAT_INTERVAL_MS : SPACE_MINE_SPAM_INTERVAL_MS;
            if (currentTime - lastSpaceMineAt < minimumInterval) return;
            lastSpaceMineAt = currentTime;
            pulseCoreButton();
            manualMine(event.repeat ? 0.58 : 1, event.repeat ? 1.35 : 2.8);
        };

        document.addEventListener("keydown", event => {
            if (isTypingTarget(event.target)) return;

            if ((event.code === "Space" || event.key === " ") && !event.ctrlKey && !event.altKey && !event.metaKey) {
                event.preventDefault();
                event.stopPropagation();
                mineWithSpace(event);
                return;
            }

            if (event.repeat) return;
            const action = shortcutActions[event.key] || shortcutActions[event.code];
            if (!action) return;
            event.preventDefault();
            pulseShortcutButton(action.button);
            action.run();
        }, true);

        const handleShopBuy = (event, selector, callback) => {
            const button = event.target.closest(selector);
            if (!button) return;
            if (!button.closest("#nftBuildings, #nftUpgrades")) return;
            event.preventDefault();
            event.stopPropagation();
            if (button.disabled) return;
            callback(button);
        };

        elements.buildings.addEventListener("pointerdown", event => {
            handleShopBuy(event, "[data-buy-building]", button => buyBuilding(button.dataset.buyBuilding));
        });

        elements.upgrades.addEventListener("pointerdown", event => {
            handleShopBuy(event, "[data-buy-upgrade]", button => buyUpgrade(button.dataset.buyUpgrade));
        });

        elements.buildings.addEventListener("keydown", event => {
            if (event.key !== "Enter" && event.key !== " ") return;
            handleShopBuy(event, "[data-buy-building]", button => buyBuilding(button.dataset.buyBuilding));
        });

        elements.upgrades.addEventListener("keydown", event => {
            if (event.key !== "Enter" && event.key !== " ") return;
            handleShopBuy(event, "[data-buy-upgrade]", button => buyUpgrade(button.dataset.buyUpgrade));
        });

        [elements.buildings, elements.upgrades, elements.achievements].forEach(list => {
            if (!list) return;
            list.addEventListener("scroll", markShopScrollActive, { passive: true });
            list.addEventListener("wheel", markShopScrollActive, { passive: true });
            list.addEventListener("touchmove", markShopScrollActive, { passive: true });
        });

        document.querySelectorAll(".nft-tabs button").forEach(button => {
            button.addEventListener("click", () => {
                document.querySelectorAll(".nft-tabs button").forEach(item => item.classList.toggle("is-active", item === button));
                document.querySelectorAll(".nft-tab-panel").forEach(panel => panel.classList.toggle("is-active", panel.dataset.panel === button.dataset.tab));
            });
        });

        document.querySelectorAll(".nft-focus-buttons button").forEach(button => {
            button.addEventListener("click", () => {
                state.activeMode = button.dataset.mode;
                renderModes();
                showMessage("Schichtmodus geändert", elements.modePill.textContent);
                saveState();
            });
        });

        elements.saveButton?.addEventListener("click", saveDatabaseState);
        elements.exportButton?.addEventListener("click", exportSave);
        elements.importInput?.addEventListener("change", () => importSave(elements.importInput.files[0]));
        elements.resetButton?.addEventListener("click", resetSave);
        elements.resetHeaderButton?.addEventListener("click", resetSave);
        window.addEventListener("beforeunload", () => saveState(false));
        window.setInterval(() => saveState(false), 5000);
    }

    attachEvents();
    renderAll(true);
    loadDatabaseSave();
    showMessage("Nebula Forge bereit", "Aktives Klicken skaliert jetzt mit deiner AFK-Produktion: Combos halten und Takt-Bursts auslösen.");
    window.requestAnimationFrame(gameLoop);
})();
