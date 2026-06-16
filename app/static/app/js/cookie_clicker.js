(() => {
    const root = document.querySelector(".cookie-page");

    if (!root) {
        return;
    }

    const STORAGE_KEY = root.dataset.saveKey || "mytools-cookie-cosmos-v1";
    const SCORE_URL = root.dataset.scoreUrl || "";
    const VERSION = 1;
    const EXPORT_FORMAT = "mytools-cookie-cosmos-save";
    const EXPORT_VERSION = 2;
    const ASCENSION_BASE = 50000000;
    const BUILDING_COST_GROWTH = 1.18;
    const SCORE_SYNC_INTERVAL = 15000;
    const language = (document.documentElement.lang || "de").toLowerCase().startsWith("en") ? "en" : "de";
    const numberFormatter = new Intl.NumberFormat(language === "en" ? "en-US" : "de-DE");
    const suffixes = ["", "K", "M", "B", "T", "Qa", "Qi", "Sx", "Sp", "Oc", "No", "Dc"];

    const ui = {
        cookieCount: document.getElementById("cookieCount"),
        cpsCount: document.getElementById("cpsCount"),
        clickPower: document.getElementById("clickPower"),
        stardustCount: document.getElementById("stardustCount"),
        cookieButton: document.getElementById("cookieButton"),
        goldenCookie: document.getElementById("goldenCookie"),
        bakeryScene: document.getElementById("bakeryScene"),
        floatingLayer: document.getElementById("floatingLayer"),
        eventBanner: document.getElementById("eventBanner"),
        buildingList: document.getElementById("buildingList"),
        upgradeList: document.getElementById("upgradeList"),
        achievementList: document.getElementById("achievementList"),
        ownedSummary: document.getElementById("ownedSummary"),
        upgradeSummary: document.getElementById("upgradeSummary"),
        achievementSummary: document.getElementById("achievementSummary"),
        comboLabel: document.getElementById("comboLabel"),
        comboBar: document.getElementById("comboBar"),
        nextStarLabel: document.getElementById("nextStarLabel"),
        overdriveButton: document.getElementById("overdriveButton"),
        overdriveStatus: document.getElementById("overdriveStatus"),
        ascendButton: document.getElementById("ascendButton"),
        ascendStatus: document.getElementById("ascendStatus"),
        saveState: document.getElementById("saveState"),
        soundToggle: document.getElementById("soundToggle"),
        exportButton: document.getElementById("exportButton"),
        importButton: document.getElementById("importButton"),
        resetButton: document.getElementById("resetButton"),
        canvas: document.getElementById("bakeryCanvas")
    };

    const ctx = ui.canvas.getContext("2d", { alpha: false });

    const copy = {
        de: {
            status: {
                saved: "Gespeichert",
                highscoreSynced: "Highscore synchronisiert",
                bought: "Gekauft",
                upgrade: "Upgrade",
                golden: "Golden",
                transcended: "Transzendiert",
                imported: "Importiert",
                reset: "Zurückgesetzt",
                soundOn: "Sound an",
                soundOff: "Sound aus",
                ready: "Bereit"
            },
            ui: {
                notEnoughCookies: "zu wenig Cookies",
                boughtBuilding: "{amount}x {name} gekauft",
                unlocked: "{name} freigeschaltet",
                luckyBatch: "Lucky Batch: +{amount} Cookies",
                timeJump: "Zeitsprung: +{amount} Cookies",
                overdriveActive: "Overdrive aktiv: Klicks x4, CPS x2",
                ascendConfirm: "Transzendieren und {amount} Stardust erhalten? Deine Anlagen und Upgrades starten neu.",
                activeSeconds: "{seconds}s aktiv",
                cooldownSeconds: "{seconds}s Cooldown",
                untilStar: "{amount} bis Stern",
                ownedSummary: "{amount} Anlagen aktiv",
                buyAmount: "{amount} kaufen",
                buy: "Kaufen",
                cost: "Kosten",
                output: "Output",
                upgradeSummary: "{bought} gekauft, {ready} bereit",
                emptyResearch: "Noch keine Forschung sichtbar.",
                new: "Neu",
                unlock: "Freischalten",
                achievementSummary: "{complete} von {total} erledigt",
                offlineGain: "Offline gebacken: +{amount} Cookies",
                exportedFile: "Spielstand-Datei exportiert",
                copiedExport: "Export-Code kopiert",
                markedExport: "Export-Code markiert",
                exportDialogLabel: "Spielstand exportieren",
                exportTitle: "Spielstand exportieren",
                exportDescription: "Speichere die JSON-Datei oder kopiere den Code. Beides kannst du später wieder importieren.",
                exportCode: "Export-Code",
                downloadFile: "Datei herunterladen",
                copyCode: "Code kopieren",
                close: "Schließen",
                importDialogLabel: "Spielstand importieren",
                importTitle: "Spielstand importieren",
                importDescription: "Füge deinen Export-Code ein oder wähle die exportierte JSON-Datei aus. Dein aktueller Spielstand wird dabei ersetzt.",
                importCode: "Import-Code",
                importPlaceholder: "Export-Code oder JSON hier einfügen",
                chooseJson: "JSON-Datei auswählen",
                fileLoaded: "{name} geladen",
                fileReadError: "Datei konnte nicht gelesen werden.",
                importInvalid: "Der Import-Code oder die Datei ist ungültig.",
                importFailed: "Import fehlgeschlagen",
                replaceSaveConfirm: "Aktuellen Cookie-Cosmos-Spielstand ersetzen?",
                importedSave: "Spielstand importiert",
                resetConfirm: "Spielstand wirklich zurücksetzen?",
                resetAria: "Spielstand zur\u00fccksetzen",
                nextStar: "N\u00e4chster Stern"
            }
        },
        en: {
            status: {
                saved: "Saved",
                highscoreSynced: "High score synced",
                bought: "Bought",
                upgrade: "Upgrade",
                golden: "Golden",
                transcended: "Transcended",
                imported: "Imported",
                reset: "Reset",
                soundOn: "Sound on",
                soundOff: "Sound off",
                ready: "Ready"
            },
            ui: {
                notEnoughCookies: "not enough cookies",
                boughtBuilding: "Bought {amount}x {name}",
                unlocked: "{name} unlocked",
                luckyBatch: "Lucky batch: +{amount} cookies",
                timeJump: "Time jump: +{amount} cookies",
                overdriveActive: "Overdrive active: clicks x4, CPS x2",
                ascendConfirm: "Transcend and gain {amount} Stardust? Your buildings and upgrades will restart.",
                activeSeconds: "{seconds}s active",
                cooldownSeconds: "{seconds}s cooldown",
                untilStar: "{amount} to next star",
                ownedSummary: "{amount} buildings active",
                buyAmount: "Buy {amount}",
                buy: "Buy",
                cost: "Cost",
                output: "Output",
                upgradeSummary: "{bought} bought, {ready} ready",
                emptyResearch: "No research visible yet.",
                new: "New",
                unlock: "Unlock",
                achievementSummary: "{complete} of {total} completed",
                offlineGain: "Baked offline: +{amount} cookies",
                exportedFile: "Save file exported",
                copiedExport: "Export code copied",
                markedExport: "Export code selected",
                exportDialogLabel: "Export save",
                exportTitle: "Export save",
                exportDescription: "Save the JSON file or copy the code. You can import either one later.",
                exportCode: "Export code",
                downloadFile: "Download file",
                copyCode: "Copy code",
                close: "Close",
                importDialogLabel: "Import save",
                importTitle: "Import save",
                importDescription: "Paste your export code or choose the exported JSON file. Your current save will be replaced.",
                importCode: "Import code",
                importPlaceholder: "Paste export code or JSON here",
                chooseJson: "Choose JSON file",
                fileLoaded: "{name} loaded",
                fileReadError: "File could not be read.",
                importInvalid: "The import code or file is invalid.",
                importFailed: "Import failed",
                replaceSaveConfirm: "Replace the current Cookie Cosmos save?",
                importedSave: "Save imported",
                resetConfirm: "Really reset your save?",
                resetAria: "Reset save",
                nextStar: "Next star"
            },
            buildings: {
                clicker: { name: "Click bots", note: "Tiny arms for steady base production" },
                apprentice: { name: "Doughlings", note: "Knead, roll, sort" },
                oven: { name: "Turbo ovens", note: "Hot cores, short bake time" },
                farm: { name: "Sugar fields", note: "Crystal sugar straight from the field" },
                factory: { name: "Cookie factory", note: "Conveyor belt, icing, packaging" },
                lab: { name: "Aroma lab", note: "Vanilla formulas with side effects" },
                portal: { name: "Crumb portal", note: "Cookies from very practical dimensions" },
                forge: { name: "Star forge", note: "Bakes with compressed starlight" },
                timeline: { name: "Time mill", note: "Tomorrow was already baked yesterday" },
                moon: { name: "Moon bakery", note: "Low gravity, high lift" },
                nebula: { name: "Nebula refinery", note: "Sugar dust from glowing clouds" },
                quantum: { name: "Quantum mixer", note: "Stirs every dough in several states" },
                blackhole: { name: "Black-hole storage", note: "Stores everything, loses almost nothing" },
                multiverse: { name: "Multiverse branch", note: "One bakery per reality" },
                singularity: { name: "Singularity kitchen", note: "One point, infinite trays" }
            },
            upgrades: {
                double_dough: { name: "Dense dough", effect: "Clicks x1.8" },
                butter_logic: { name: "Butter logic", effect: "Click bots x2" },
                caramel_cache: { name: "Caramel cache", effect: "CPS x1.15" },
                oven_matrix: { name: "Oven matrix", effect: "Turbo ovens x2" },
                lucky_glove: { name: "Lucky glove", effect: "Crit chance +4%" },
                sugar_radar: { name: "Golden radar", effect: "Golden cookies faster, value x1.15" },
                farm_weather: { name: "Sugar weather", effect: "Sugar fields x2" },
                factory_flow: { name: "Conveyor sync", effect: "Cookie factory x2" },
                critical_cocoa: { name: "Critical cocoa", effect: "Crits x7 instead of x5" },
                lab_serum: { name: "Vanilla serum", effect: "Aroma lab x2" },
                portal_treaty: { name: "Portal treaty", effect: "Crumb portal x2" },
                comet_sugar: { name: "Comet sugar", effect: "Clicks x2.2" },
                cosmic_butter: { name: "Cosmic butter", effect: "CPS x1.6" },
                forge_chorus: { name: "Forge chorus", effect: "Star forge x2" },
                timeline_anchor: { name: "Time anchor", effect: "Time mill x2 and longer events" },
                stardust_lens: { name: "Stardust lens", effect: "Stronger Stardust bonus" },
                overdrive_engine: { name: "Overdrive turbine", effect: "Longer Overdrive, shorter cooldown" },
                combo_silo: { name: "Combo silo", effect: "Combo limit +40" },
                moon_delivery: { name: "Moon delivery", effect: "CPS x1.25" },
                nebula_contract: { name: "Nebula contract", effect: "Golden value x1.45" },
                quantum_recipe: { name: "Quantum recipe", effect: "CPS and clicks x1.35" },
                blackhole_vault: { name: "Black-hole vault", effect: "CPS x1.5" },
                multiverse_brand: { name: "Multiverse brand", effect: "CPS x1.6" },
                singularity_whisk: { name: "Singularity whisk", effect: "Clicks x3, CPS x1.4" },
                prestige_matrix: { name: "Prestige matrix", effect: "Much stronger Stardust bonus" },
                achievement_council: { name: "Achievement council", effect: "CPS and clicks x1.3" }
            },
            tiers: {
                tuning: "Fine tuning",
                automation: "Automation",
                quality: "Quality batch",
                logistics: "Logistics network",
                mastery: "Master line"
            },
            achievements: {
                first_click: { name: "First bite", note: "1 click" },
                hundred: { name: "Cookie jar", note: "100 cookies" },
                thousand: { name: "Tray ready", note: "1K cookies" },
                click_runner: { name: "Finger festival", note: "250 clicks" },
                click_marathon: { name: "Crunch marathon", note: "2,500 clicks" },
                ten_buildings: { name: "Bake team", note: "10 buildings" },
                fifty_buildings: { name: "Production hall", note: "50 buildings" },
                two_hundred_buildings: { name: "Industrial complex", note: "200 buildings" },
                combo_40: { name: "Combo crown", note: "40 combo" },
                combo_100: { name: "Finger orbit", note: "100 combo" },
                golden: { name: "Golden find", note: "Golden cookie" },
                golden_25: { name: "Star hunter", note: "25 golden cookies" },
                million: { name: "Million tray", note: "1M cookies" },
                fifty_million: { name: "Star-ready", note: "50M cookies" },
                hundred_million: { name: "Galactic delivery", note: "100M cookies" },
                billion: { name: "Billion mix", note: "1B cookies" },
                trillion: { name: "Trillion tray", note: "1T cookies" },
                cps_1000: { name: "Constant fire", note: "1K CPS" },
                cps_1m: { name: "Orbit oven", note: "1M CPS" },
                cps_1b: { name: "Cosmic autobake", note: "1B CPS" },
                upgrades_10: { name: "Research urge", note: "10 upgrades" },
                upgrades_30: { name: "Lab lead", note: "30 upgrades" },
                upgrades_60: { name: "Upgrade archive", note: "60 upgrades" },
                stardust: { name: "Star crumb", note: "1 Stardust" },
                stardust_25: { name: "Star stash", note: "25 Stardust" },
                ascended: { name: "New oven, new luck", note: "Transcended" },
                ascended_5: { name: "Prestige routine", note: "5 transcensions" },
                moon: { name: "Moon flour", note: "Moon bakery built" },
                quantum: { name: "Probably tasty", note: "Quantum mixer built" },
                singularity: { name: "Point landing", note: "Singularity kitchen built" }
            },
            events: {
                frenzy: { name: "Oven fever", text: "CPS x4" },
                clickstorm: { name: "Click storm", text: "Clicks x8" },
                balanced: { name: "Golden batch", text: "CPS x2.4 and clicks x2.4" }
            }
        }
    };

    function translate(section, key) {
        return copy[language]?.[section]?.[key] || copy.de[section]?.[key] || key;
    }

    function interpolate(template, values = {}) {
        return template.replace(/\{([a-zA-Z0-9_]+)\}/g, (_, key) => values[key] ?? "");
    }

    function label(key, values) {
        return interpolate(translate("ui", key), values);
    }

    function statusLabel(key) {
        return translate("status", key);
    }

    function localizeItems(section, items) {
        if (language === "de") {
            return;
        }

        const translations = copy.en[section] || {};
        items.forEach(item => {
            Object.assign(item, translations[item.id] || {});
        });
    }

    function repairTextValue(value) {
        if (typeof value !== "string" || !/[ÃÂ]/.test(value)) {
            return value;
        }

        try {
            return decodeURIComponent(escape(value));
        } catch (error) {
            return value;
        }
    }

    function repairTextObject(target) {
        if (!target || typeof target !== "object") {
            return;
        }

        Object.keys(target).forEach(key => {
            const value = target[key];

            if (typeof value === "string") {
                target[key] = repairTextValue(value);
            } else if (value && typeof value === "object") {
                repairTextObject(value);
            }
        });
    }

    function applyStaticLabels() {
        ui.resetButton?.setAttribute("aria-label", label("resetAria"));
        document.querySelector(".progress-strip > div:last-child span").textContent = label("nextStar");
    }

    repairTextObject(copy.de);

    const buildings = [
        {
            id: "clicker",
            name: "Click-Bots",
            icon: "fa-solid fa-hand-pointer",
            baseCost: 25,
            cps: 0.08,
            note: "Mini-Arme für konstante Grundproduktion"
        },
        {
            id: "apprentice",
            name: "Teiglinge",
            icon: "fa-solid fa-user-gear",
            baseCost: 180,
            cps: 0.75,
            note: "Kneten, rollen, sortieren"
        },
        {
            id: "oven",
            name: "Turbo-Öfen",
            icon: "fa-solid fa-fire-burner",
            baseCost: 1200,
            cps: 4.5,
            note: "Heiße Kerne, kurze Backzeit"
        },
        {
            id: "farm",
            name: "Zuckerfelder",
            icon: "fa-solid fa-seedling",
            baseCost: 8500,
            cps: 22,
            note: "Kristallzucker direkt vom Feld"
        },
        {
            id: "factory",
            name: "Keksfabrik",
            icon: "fa-solid fa-industry",
            baseCost: 54000,
            cps: 110,
            note: "Förderband, Glasur, Verpackung"
        },
        {
            id: "lab",
            name: "Aroma-Labor",
            icon: "fa-solid fa-flask-vial",
            baseCost: 310000,
            cps: 560,
            note: "Vanilleformeln mit Nebenwirkung"
        },
        {
            id: "portal",
            name: "Krumenportal",
            icon: "fa-solid fa-circle-nodes",
            baseCost: 2000000,
            cps: 3100,
            note: "Kekse aus sehr praktischen Dimensionen"
        },
        {
            id: "forge",
            name: "Sternenforge",
            icon: "fa-solid fa-meteor",
            baseCost: 13500000,
            cps: 18000,
            note: "Backt mit komprimiertem Sternenlicht"
        },
        {
            id: "timeline",
            name: "Zeitmühle",
            icon: "fa-solid fa-hourglass-half",
            baseCost: 95000000,
            cps: 98000,
            note: "Morgen schon gestern gebacken"
        },
        {
            id: "moon",
            name: "Mondbäckerei",
            icon: "fa-solid fa-moon",
            baseCost: 720000000,
            cps: 540000,
            note: "Niedrige Schwerkraft, hoher Auftrieb"
        },
        {
            id: "nebula",
            name: "Nebula-Raffinerie",
            icon: "fa-solid fa-cloud",
            baseCost: 5800000000,
            cps: 3200000,
            note: "Zuckerstaub aus leuchtenden Wolken"
        },
        {
            id: "quantum",
            name: "Quantenmixer",
            icon: "fa-solid fa-atom",
            baseCost: 48000000000,
            cps: 19000000,
            note: "Rührt jeden Teig in mehreren Zuständen"
        },
        {
            id: "blackhole",
            name: "Schwarzloch-Vorrat",
            icon: "fa-solid fa-circle-dot",
            baseCost: 420000000000,
            cps: 115000000,
            note: "Lagert alles, verliert fast nichts"
        },
        {
            id: "multiverse",
            name: "Multiversum-Filiale",
            icon: "fa-solid fa-network-wired",
            baseCost: 3900000000000,
            cps: 720000000,
            note: "Eine Backstube pro Realität"
        },
        {
            id: "singularity",
            name: "Singularitäts-Küche",
            icon: "fa-solid fa-infinity",
            baseCost: 39000000000000,
            cps: 4800000000,
            note: "Ein Punkt, unendlich viele Bleche"
        }
    ];

    localizeItems("buildings", buildings);
    buildings.forEach(repairTextObject);

    const buildingMap = Object.fromEntries(buildings.map(building => [building.id, building]));

    const specialUpgrades = [
        {
            id: "double_dough",
            name: "Dichter Teig",
            icon: "fa-solid fa-layer-group",
            cost: 280,
            effect: "Klicks x1.8",
            requires: state => state.totalBaked >= 180,
            apply: mods => { mods.clickMultiplier *= 1.8; }
        },
        {
            id: "butter_logic",
            name: "Butterlogik",
            icon: "fa-solid fa-brain",
            cost: 3500,
            effect: "Click-Bots x2",
            requires: state => getOwned(state, "clicker") >= 12,
            apply: mods => { mods.buildingMultipliers.clicker *= 2; }
        },
        {
            id: "caramel_cache",
            name: "Karamell-Cache",
            icon: "fa-solid fa-box-archive",
            cost: 9000,
            effect: "CPS x1.15",
            requires: state => state.totalBaked >= 6500,
            apply: mods => { mods.cpsMultiplier *= 1.15; }
        },
        {
            id: "oven_matrix",
            name: "Ofenmatrix",
            icon: "fa-solid fa-table-cells-large",
            cost: 22000,
            effect: "Turbo-Öfen x2",
            requires: state => getOwned(state, "oven") >= 8,
            apply: mods => { mods.buildingMultipliers.oven *= 2; }
        },
        {
            id: "lucky_glove",
            name: "Glückshandschuh",
            icon: "fa-solid fa-hand-sparkles",
            cost: 45000,
            effect: "Kritchance +4%",
            requires: state => state.totalClicks >= 220,
            apply: mods => { mods.critChance += 0.04; }
        },
        {
            id: "sugar_radar",
            name: "Golden Radar",
            icon: "fa-solid fa-satellite-dish",
            cost: 140000,
            effect: "Golden Cookies schneller, Wert x1.15",
            requires: state => state.stats.goldenClicks >= 1 || state.totalBaked >= 90000,
            apply: mods => {
                mods.goldenDelay *= 0.82;
                mods.goldenRewardMultiplier *= 1.15;
            }
        },
        {
            id: "farm_weather",
            name: "Zuckerwetter",
            icon: "fa-solid fa-cloud-sun-rain",
            cost: 280000,
            effect: "Zuckerfelder x2",
            requires: state => getOwned(state, "farm") >= 10,
            apply: mods => { mods.buildingMultipliers.farm *= 2; }
        },
        {
            id: "factory_flow",
            name: "Förderband-Sync",
            icon: "fa-solid fa-arrows-spin",
            cost: 900000,
            effect: "Keksfabrik x2",
            requires: state => getOwned(state, "factory") >= 10,
            apply: mods => { mods.buildingMultipliers.factory *= 2; }
        },
        {
            id: "critical_cocoa",
            name: "Kakao-Krit",
            icon: "fa-solid fa-burst",
            cost: 2200000,
            effect: "Krits x7 statt x5",
            requires: state => state.manualCookies >= 400000,
            apply: mods => { mods.critMultiplier = Math.max(mods.critMultiplier, 7); }
        },
        {
            id: "lab_serum",
            name: "Vanilleserum",
            icon: "fa-solid fa-vial-circle-check",
            cost: 5200000,
            effect: "Aroma-Labor x2",
            requires: state => getOwned(state, "lab") >= 8,
            apply: mods => { mods.buildingMultipliers.lab *= 2; }
        },
        {
            id: "portal_treaty",
            name: "Portalvertrag",
            icon: "fa-solid fa-file-signature",
            cost: 28000000,
            effect: "Krumenportal x2",
            requires: state => getOwned(state, "portal") >= 6,
            apply: mods => { mods.buildingMultipliers.portal *= 2; }
        },
        {
            id: "comet_sugar",
            name: "Kometenzucker",
            icon: "fa-solid fa-meteor",
            cost: 62000000,
            effect: "Klicks x2.2",
            requires: state => state.totalBaked >= 25000000,
            apply: mods => { mods.clickMultiplier *= 2.2; }
        },
        {
            id: "cosmic_butter",
            name: "Kosmische Butter",
            icon: "fa-solid fa-star-half-stroke",
            cost: 160000000,
            effect: "CPS x1.6",
            requires: state => state.totalBaked >= 70000000,
            apply: mods => { mods.cpsMultiplier *= 1.6; }
        },
        {
            id: "forge_chorus",
            name: "Forge-Chor",
            icon: "fa-solid fa-music",
            cost: 520000000,
            effect: "Sternenforge x2",
            requires: state => getOwned(state, "forge") >= 5,
            apply: mods => { mods.buildingMultipliers.forge *= 2; }
        },
        {
            id: "timeline_anchor",
            name: "Zeitanker",
            icon: "fa-solid fa-clock-rotate-left",
            cost: 1800000000,
            effect: "Zeitmühle x2 und Events länger",
            requires: state => getOwned(state, "timeline") >= 4,
            apply: mods => {
                mods.buildingMultipliers.timeline *= 2;
                mods.eventDurationMultiplier *= 1.25;
            }
        },
        {
            id: "stardust_lens",
            name: "Stardust-Linse",
            icon: "fa-solid fa-gem",
            cost: 4200000000,
            effect: "Stardust-Bonus stärker",
            requires: state => state.stardust >= 3,
            apply: mods => { mods.stardustBonus += 0.03; }
        },
        {
            id: "overdrive_engine",
            name: "Overdrive-Turbine",
            icon: "fa-solid fa-gauge-high",
            cost: 9500000000,
            effect: "Overdrive länger, Cooldown kürzer",
            requires: state => state.totalBaked >= 3000000000,
            apply: mods => {
                mods.overdriveDurationMultiplier *= 1.35;
                mods.overdriveCooldownMultiplier *= 0.82;
            }
        },
        {
            id: "combo_silo",
            name: "Combo-Silo",
            icon: "fa-solid fa-arrow-up-wide-short",
            cost: 22000000000,
            effect: "Combo-Limit +40",
            requires: state => state.stats.maxCombo >= 60,
            apply: mods => { mods.comboCap += 40; }
        },
        {
            id: "moon_delivery",
            name: "Mondlieferdienst",
            icon: "fa-solid fa-rocket",
            cost: 85000000000,
            effect: "CPS x1.25",
            requires: state => getOwned(state, "moon") >= 2,
            apply: mods => { mods.cpsMultiplier *= 1.25; }
        },
        {
            id: "nebula_contract",
            name: "Nebula-Kontrakt",
            icon: "fa-solid fa-file-contract",
            cost: 620000000000,
            effect: "Golden-Wert x1.45",
            requires: state => getOwned(state, "nebula") >= 2,
            apply: mods => { mods.goldenRewardMultiplier *= 1.45; }
        },
        {
            id: "quantum_recipe",
            name: "Quantenrezept",
            icon: "fa-solid fa-atom",
            cost: 4800000000000,
            effect: "CPS und Klicks x1.35",
            requires: state => getOwned(state, "quantum") >= 1,
            apply: mods => {
                mods.cpsMultiplier *= 1.35;
                mods.clickMultiplier *= 1.35;
            }
        },
        {
            id: "blackhole_vault",
            name: "Schwarzloch-Tresor",
            icon: "fa-solid fa-vault",
            cost: 36000000000000,
            effect: "CPS x1.5",
            requires: state => getOwned(state, "blackhole") >= 1,
            apply: mods => { mods.cpsMultiplier *= 1.5; }
        },
        {
            id: "multiverse_brand",
            name: "Multiversum-Marke",
            icon: "fa-solid fa-store",
            cost: 280000000000000,
            effect: "CPS x1.6",
            requires: state => getOwned(state, "multiverse") >= 1,
            apply: mods => { mods.cpsMultiplier *= 1.6; }
        },
        {
            id: "singularity_whisk",
            name: "Singularitäts-Schneebesen",
            icon: "fa-solid fa-wand-magic-sparkles",
            cost: 2400000000000000,
            effect: "Klicks x3, CPS x1.4",
            requires: state => getOwned(state, "singularity") >= 1,
            apply: mods => {
                mods.clickMultiplier *= 3;
                mods.cpsMultiplier *= 1.4;
            }
        },
        {
            id: "prestige_matrix",
            name: "Prestige-Matrix",
            icon: "fa-solid fa-diagram-project",
            cost: 12000000000000000,
            effect: "Stardust-Bonus massiv stärker",
            requires: state => state.stardust >= 10,
            apply: mods => { mods.stardustBonus += 0.05; }
        },
        {
            id: "achievement_council",
            name: "Erfolgsgremium",
            icon: "fa-solid fa-award",
            cost: 85000000000000000,
            effect: "CPS und Klicks x1.3",
            requires: state => state.achievements.length >= 20,
            apply: mods => {
                mods.cpsMultiplier *= 1.3;
                mods.clickMultiplier *= 1.3;
            }
        }
    ];

    localizeItems("upgrades", specialUpgrades);
    specialUpgrades.forEach(repairTextObject);

    const buildingTierDefinitions = [
        { id: "tuning", label: "Feinjustierung", icon: "fa-solid fa-screwdriver-wrench", count: 5, costMultiplier: 12, productionMultiplier: 1.6 },
        { id: "automation", label: "Automatisierung", icon: "fa-solid fa-robot", count: 15, costMultiplier: 70, productionMultiplier: 1.8 },
        { id: "quality", label: "Qualitäts-Charge", icon: "fa-solid fa-medal", count: 30, costMultiplier: 390, productionMultiplier: 2 },
        { id: "logistics", label: "Logistiknetz", icon: "fa-solid fa-route", count: 55, costMultiplier: 2400, productionMultiplier: 2.25 },
        { id: "mastery", label: "Meisterlinie", icon: "fa-solid fa-crown", count: 85, costMultiplier: 15500, productionMultiplier: 2.5 }
    ];

    if (language === "en") {
        buildingTierDefinitions.forEach(tier => {
            tier.label = copy.en.tiers[tier.id] || tier.label;
        });
    }
    buildingTierDefinitions.forEach(repairTextObject);

    const upgrades = [
        ...specialUpgrades,
        ...buildings.flatMap(building => buildingTierDefinitions.map(tier => ({
            id: `${building.id}_${tier.id}`,
            name: `${building.name}: ${tier.label}`,
            icon: tier.icon,
            cost: Math.ceil(building.baseCost * tier.costMultiplier),
            effect: `${building.name} x${tier.productionMultiplier}`,
            requires: state => getOwned(state, building.id) >= tier.count,
            apply: mods => { mods.buildingMultipliers[building.id] *= tier.productionMultiplier; }
        })))
    ];

    const achievements = [
        { id: "first_click", name: "Erster Biss", icon: "fa-solid fa-cookie-bite", note: "1 Klick", test: state => state.totalClicks >= 1 },
        { id: "hundred", name: "Keksdose", icon: "fa-solid fa-box", note: "100 Cookies", test: state => state.lifetimeBaked >= 100 },
        { id: "thousand", name: "Blechbereit", icon: "fa-solid fa-cookie", note: "1K Cookies", test: state => state.lifetimeBaked >= 1000 },
        { id: "click_runner", name: "Finger-Festival", icon: "fa-solid fa-hand", note: "250 Klicks", test: state => state.totalClicks >= 250 },
        { id: "click_marathon", name: "Knusper-Marathon", icon: "fa-solid fa-person-running", note: "2.500 Klicks", test: state => state.totalClicks >= 2500 },
        { id: "ten_buildings", name: "Backteam", icon: "fa-solid fa-users-gear", note: "10 Anlagen", test: state => getTotalBuildings(state) >= 10 },
        { id: "fifty_buildings", name: "Produktionshalle", icon: "fa-solid fa-warehouse", note: "50 Anlagen", test: state => getTotalBuildings(state) >= 50 },
        { id: "two_hundred_buildings", name: "Industriekomplex", icon: "fa-solid fa-city", note: "200 Anlagen", test: state => getTotalBuildings(state) >= 200 },
        { id: "combo_40", name: "Combo-Krone", icon: "fa-solid fa-crown", note: "40er Combo", test: state => state.stats.maxCombo >= 40 },
        { id: "combo_100", name: "Fingerorbit", icon: "fa-solid fa-arrows-spin", note: "100er Combo", test: state => state.stats.maxCombo >= 100 },
        { id: "golden", name: "Goldfund", icon: "fa-solid fa-star", note: "Golden Cookie", test: state => state.stats.goldenClicks >= 1 },
        { id: "golden_25", name: "Sternjäger", icon: "fa-solid fa-wand-magic-sparkles", note: "25 Golden Cookies", test: state => state.stats.goldenClicks >= 25 },
        { id: "million", name: "Millionen-Blech", icon: "fa-solid fa-certificate", note: "1M Cookies", test: state => state.lifetimeBaked >= 1000000 },
        { id: "fifty_million", name: "Sternenreif", icon: "fa-solid fa-meteor", note: "50M Cookies", test: state => state.lifetimeBaked >= 50000000 },
        { id: "hundred_million", name: "Galaktische Lieferung", icon: "fa-solid fa-truck-fast", note: "100M Cookies", test: state => state.lifetimeBaked >= 100000000 },
        { id: "billion", name: "Milliarden-Mischung", icon: "fa-solid fa-scale-balanced", note: "1B Cookies", test: state => state.lifetimeBaked >= 1000000000 },
        { id: "trillion", name: "Trillionen-Tablett", icon: "fa-solid fa-layer-group", note: "1T Cookies", test: state => state.lifetimeBaked >= 1000000000000 },
        { id: "cps_1000", name: "Dauerfeuer", icon: "fa-solid fa-gauge-high", note: "1K CPS", test: () => computeCps() >= 1000 },
        { id: "cps_1m", name: "Orbitofen", icon: "fa-solid fa-satellite", note: "1M CPS", test: () => computeCps() >= 1000000 },
        { id: "cps_1b", name: "Kosmisches Dauerbacken", icon: "fa-solid fa-sun", note: "1B CPS", test: () => computeCps() >= 1000000000 },
        { id: "upgrades_10", name: "Forschungsdrang", icon: "fa-solid fa-flask", note: "10 Upgrades", test: state => state.upgrades.length >= 10 },
        { id: "upgrades_30", name: "Laborleitung", icon: "fa-solid fa-microscope", note: "30 Upgrades", test: state => state.upgrades.length >= 30 },
        { id: "upgrades_60", name: "Upgrade-Archiv", icon: "fa-solid fa-folder-tree", note: "60 Upgrades", test: state => state.upgrades.length >= 60 },
        { id: "stardust", name: "Sternenkrume", icon: "fa-solid fa-meteor", note: "1 Stardust", test: state => state.stardust >= 1 },
        { id: "stardust_25", name: "Sternenlager", icon: "fa-solid fa-gem", note: "25 Stardust", test: state => state.stardust >= 25 },
        { id: "ascended", name: "Neuer Ofen, neues Glück", icon: "fa-solid fa-arrow-up-right-dots", note: "Transzendiert", test: state => state.ascensions >= 1 },
        { id: "ascended_5", name: "Prestige-Routine", icon: "fa-solid fa-repeat", note: "5 Transzendenzen", test: state => state.ascensions >= 5 },
        { id: "moon", name: "Mondmehl", icon: "fa-solid fa-moon", note: "Mondbäckerei gebaut", test: state => getOwned(state, "moon") >= 1 },
        { id: "quantum", name: "Wahrscheinlich lecker", icon: "fa-solid fa-atom", note: "Quantenmixer gebaut", test: state => getOwned(state, "quantum") >= 1 },
        { id: "singularity", name: "Punktlandung", icon: "fa-solid fa-infinity", note: "Singularitäts-Küche gebaut", test: state => getOwned(state, "singularity") >= 1 }
    ];

    localizeItems("achievements", achievements);
    achievements.forEach(repairTextObject);

    const eventTypes = [
        {
            id: "frenzy",
            name: "Ofenfieber",
            text: "CPS x4",
            duration: 18000,
            cpsMultiplier: 4,
            clickMultiplier: 1
        },
        {
            id: "clickstorm",
            name: "Klicksturm",
            text: "Klicks x8",
            duration: 11000,
            cpsMultiplier: 1,
            clickMultiplier: 8
        },
        {
            id: "balanced",
            name: "Goldene Charge",
            text: "CPS x2.4 und Klicks x2.4",
            duration: 15000,
            cpsMultiplier: 2.4,
            clickMultiplier: 2.4
        }
    ];

    localizeItems("events", eventTypes);
    eventTypes.forEach(repairTextObject);

    let state = loadState();
    let buyMode = "one";
    let lastFrame = performance.now();
    let lastRender = 0;
    let lastListRender = 0;
    let lastSave = 0;
    let nextGoldenAt = Date.now() + 14000;
    let goldenVisibleUntil = 0;
    let notice = { text: "", until: 0 };
    let audioContext = null;
    let canvasSize = { width: 960, height: 560, dpr: 1 };
    let lastScoreSync = 0;
    let lastSubmittedScore = 0;
    let scoreSyncFailedUntil = 0;

    function defaultState() {
        return {
            version: VERSION,
            cookies: 0,
            totalBaked: 0,
            lifetimeBaked: 0,
            totalClicks: 0,
            manualCookies: 0,
            stardust: 0,
            ascensions: 0,
            buildings: {},
            upgrades: [],
            achievements: [],
            stats: {
                goldenClicks: 0,
                maxCombo: 0,
                buildingsBought: 0,
                upgradesBought: 0
            },
            combo: 0,
            comboUntil: 0,
            event: null,
            eventUntil: 0,
            overdriveUntil: 0,
            overdriveCooldownUntil: 0,
            sound: true,
            lastSaved: Date.now()
        };
    }

    function loadState() {
        try {
            const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY));
            return normalizeState(parsed || defaultState());
        } catch (error) {
            return defaultState();
        }
    }

    function normalizeState(raw = {}) {
        if (!raw || typeof raw !== "object") {
            raw = {};
        }

        const base = defaultState();
        const normalized = { ...base, ...raw };
        const rawBuildings = raw.buildings && typeof raw.buildings === "object" ? raw.buildings : {};
        const rawStats = raw.stats && typeof raw.stats === "object" ? raw.stats : {};
        const upgradeIds = new Set(upgrades.map(upgrade => upgrade.id));
        const achievementIds = new Set(achievements.map(achievement => achievement.id));
        const now = Date.now();

        normalized.buildings = {};
        for (const building of buildings) {
            const owned = Math.floor(getSafeNumber(rawBuildings[building.id], 0));

            if (owned > 0) {
                normalized.buildings[building.id] = Math.min(999999, owned);
            }
        }

        normalized.stats = { ...base.stats, ...rawStats };
        normalized.stats.goldenClicks = Math.floor(getSafeNumber(normalized.stats.goldenClicks, 0));
        normalized.stats.maxCombo = Math.floor(getSafeNumber(normalized.stats.maxCombo, 0));
        normalized.stats.buildingsBought = Math.floor(getSafeNumber(normalized.stats.buildingsBought, 0));
        normalized.stats.upgradesBought = Math.floor(getSafeNumber(normalized.stats.upgradesBought, 0));

        normalized.upgrades = uniqueKnownIds(raw.upgrades, upgradeIds);
        normalized.achievements = uniqueKnownIds(raw.achievements, achievementIds);
        normalized.cookies = getSafeNumber(raw.cookies, 0);
        normalized.totalBaked = getSafeNumber(raw.totalBaked, 0);
        normalized.lifetimeBaked = Math.max(normalized.totalBaked, getSafeNumber(raw.lifetimeBaked, normalized.totalBaked));
        normalized.totalClicks = Math.floor(getSafeNumber(raw.totalClicks, 0));
        normalized.manualCookies = getSafeNumber(raw.manualCookies, 0);
        normalized.stardust = Math.floor(getSafeNumber(raw.stardust, 0));
        normalized.ascensions = Math.floor(getSafeNumber(raw.ascensions, 0));
        normalized.combo = getSafeNumber(raw.combo, 0);
        normalized.comboUntil = getSafeNumber(raw.comboUntil, 0);
        normalized.eventUntil = getSafeNumber(raw.eventUntil, 0);
        normalized.overdriveUntil = getSafeNumber(raw.overdriveUntil, 0);
        normalized.overdriveCooldownUntil = getSafeNumber(raw.overdriveCooldownUntil, 0);
        normalized.sound = raw.sound !== false;
        normalized.lastSaved = getSafeNumber(raw.lastSaved, now);
        normalized.version = VERSION;

        const eventId = raw.event && typeof raw.event === "object" ? raw.event.id : null;
        const knownEvent = eventTypes.find(event => event.id === eventId);
        normalized.event = knownEvent && normalized.eventUntil > now ? { ...knownEvent } : null;

        return normalized;
    }

    function getSafeNumber(value, fallback = 0) {
        const number = Number(value);

        if (!Number.isFinite(number) || number < 0) {
            return fallback;
        }

        return number;
    }

    function uniqueKnownIds(value, allowedIds) {
        if (!Array.isArray(value)) {
            return [];
        }

        return [...new Set(value.filter(id => allowedIds.has(id)))];
    }

    function saveState(label = statusLabel("saved")) {
        state.lastSaved = Date.now();
        localStorage.setItem(STORAGE_KEY, JSON.stringify(state));

        if (ui.saveState) {
            ui.saveState.textContent = label;
        }
    }

    function getCookie(name) {
        return document.cookie
            .split(";")
            .map(part => part.trim())
            .find(part => part.startsWith(`${name}=`))
            ?.slice(name.length + 1) || "";
    }

    function getHighscorePayload() {
        return {
            score: state.lifetimeBaked,
            display_score: format(state.lifetimeBaked),
            cps: computeCps(),
            click_power: computeClickPower(),
            stardust: state.stardust,
            ascensions: state.ascensions,
            achievements_count: state.achievements.length,
            upgrades_count: state.upgrades.length,
            buildings_count: getTotalBuildings(state),
            details: {
                total_baked: state.totalBaked,
                manual_cookies: state.manualCookies,
                total_clicks: state.totalClicks,
                golden_clicks: state.stats.goldenClicks,
                max_combo: state.stats.maxCombo,
                buildings_bought: state.stats.buildingsBought,
                upgrades_bought: state.stats.upgradesBought
            }
        };
    }

    async function submitHighscore(force = false) {
        if (!SCORE_URL || scoreSyncFailedUntil > Date.now()) {
            return;
        }

        const now = Date.now();
        const score = state.lifetimeBaked;
        const meaningfulGain = score - lastSubmittedScore >= 1000 || score > lastSubmittedScore * 1.01;

        if (!force && (now - lastScoreSync < SCORE_SYNC_INTERVAL || !meaningfulGain)) {
            return;
        }

        lastScoreSync = now;

        try {
            const response = await fetch(SCORE_URL, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": decodeURIComponent(getCookie("csrftoken"))
                },
                body: JSON.stringify(getHighscorePayload())
            });
            const contentType = response.headers.get("content-type") || "";

            if (!response.ok || !contentType.includes("application/json")) {
                scoreSyncFailedUntil = Date.now() + 60000;
                return;
            }

            const data = await response.json();

            if (data.status === "ok") {
                lastSubmittedScore = Math.max(lastSubmittedScore, score);

                if (data.new_highscore && ui.saveState) {
                    ui.saveState.textContent = statusLabel("highscoreSynced");
                }
            }
        } catch (error) {
            scoreSyncFailedUntil = Date.now() + 30000;
        }
    }

    function getOwned(targetState, id) {
        return Number(targetState.buildings[id]) || 0;
    }

    function getTotalBuildings(targetState = state) {
        return Object.values(targetState.buildings).reduce((sum, value) => sum + (Number(value) || 0), 0);
    }

    function createModifiers() {
        const baseStardustBonus = 0.06;
        const mods = {
            clickMultiplier: 1 + state.stardust * 0.08,
            cpsMultiplier: 1 + state.stardust * baseStardustBonus,
            stardustBonus: baseStardustBonus,
            critChance: 0.04,
            critMultiplier: 5,
            goldenDelay: 1,
            goldenRewardMultiplier: 1,
            eventDurationMultiplier: 1,
            overdriveDurationMultiplier: 1,
            overdriveCooldownMultiplier: 1,
            comboCap: 90,
            buildingMultipliers: Object.fromEntries(buildings.map(building => [building.id, 1]))
        };

        for (const upgrade of upgrades) {
            if (state.upgrades.includes(upgrade.id)) {
                upgrade.apply(mods, state);
            }
        }

        mods.cpsMultiplier += state.stardust * Math.max(0, mods.stardustBonus - baseStardustBonus);
        return mods;
    }

    function getTimedMultipliers() {
        const now = Date.now();
        const multipliers = { cps: 1, click: 1 };

        if (state.event && state.eventUntil > now) {
            multipliers.cps *= state.event.cpsMultiplier || 1;
            multipliers.click *= state.event.clickMultiplier || 1;
        }

        if (state.overdriveUntil > now) {
            multipliers.cps *= 2;
            multipliers.click *= 4;
        }

        return multipliers;
    }

    function computeCps() {
        const mods = createModifiers();
        let cps = 0;

        for (const building of buildings) {
            cps += getOwned(state, building.id) * building.cps * mods.buildingMultipliers[building.id];
        }

        return cps * mods.cpsMultiplier * getTimedMultipliers().cps;
    }

    function computeClickPower() {
        const mods = createModifiers();
        const ownedClickers = getOwned(state, "clicker");
        const forgeBonus = Math.sqrt(getOwned(state, "forge")) * 0.4;
        return (1 + ownedClickers * 0.035 + forgeBonus) * mods.clickMultiplier * getTimedMultipliers().click;
    }

    function getBuildingCost(building, count = getOwned(state, building.id)) {
        return Math.ceil(building.baseCost * Math.pow(BUILDING_COST_GROWTH, count));
    }

    function getBuyInfo(building) {
        if (buyMode === "one") {
            return { amount: 1, cost: getBuildingCost(building) };
        }

        let amount = 0;
        let cost = 0;
        let nextCount = getOwned(state, building.id);

        while (amount < 5000) {
            const nextCost = getBuildingCost(building, nextCount);

            if (cost + nextCost > state.cookies) {
                break;
            }

            cost += nextCost;
            nextCount += 1;
            amount += 1;
        }

        return { amount, cost };
    }

    function buyBuilding(id) {
        const building = buildingMap[id];

        if (!building) {
            return;
        }

        const info = getBuyInfo(building);

        if (!info.amount || state.cookies < info.cost) {
            pulseUnavailable();
            return;
        }

        state.cookies -= info.cost;
        state.buildings[id] = getOwned(state, id) + info.amount;
        state.stats.buildingsBought += info.amount;
        beep(220 + Math.min(700, building.cps * 2), 0.045, 0.04);
        showNotice(label("boughtBuilding", { amount: info.amount, name: building.name }));
        checkAchievements();
        renderLists();
        renderDynamic();
        saveState(statusLabel("bought"));
    }

    function buyUpgrade(id) {
        const upgrade = upgrades.find(item => item.id === id);

        if (!upgrade || state.upgrades.includes(id) || !upgrade.requires(state)) {
            return;
        }

        if (state.cookies < upgrade.cost) {
            pulseUnavailable();
            return;
        }

        state.cookies -= upgrade.cost;
        state.upgrades.push(id);
        state.stats.upgradesBought += 1;
        beep(620, 0.08, 0.06);
        showNotice(label("unlocked", { name: upgrade.name }));
        scheduleGolden();
        checkAchievements();
        renderLists();
        renderDynamic();
        saveState(statusLabel("upgrade"));
    }

    function addCookies(amount) {
        if (!Number.isFinite(amount) || amount <= 0) {
            return;
        }

        state.cookies += amount;
        state.totalBaked += amount;
        state.lifetimeBaked += amount;
    }

    function handleCookieClick(event) {
        const rect = ui.bakeryScene.getBoundingClientRect();
        const x = event.clientX ? event.clientX - rect.left : rect.width / 2;
        const y = event.clientY ? event.clientY - rect.top : rect.height / 2;
        const mods = createModifiers();
        const comboMultiplier = 1 + Math.min(state.combo, mods.comboCap) / 100;
        let amount = computeClickPower() * comboMultiplier;
        let color = "#fff3bf";
        let labelPrefix = "+";

        if (Math.random() < mods.critChance) {
            amount *= mods.critMultiplier;
            color = "#fb7185";
            labelPrefix = language === "en" ? "CRIT +" : "KRIT +";
            beep(900, 0.05, 0.06);
        } else {
            beep(300 + Math.random() * 70, 0.035, 0.03);
        }

        addCookies(amount);
        state.totalClicks += 1;
        state.manualCookies += amount;
        state.combo = Math.min(mods.comboCap, state.combo + 1);
        state.comboUntil = Date.now() + 1450;
        state.stats.maxCombo = Math.max(state.stats.maxCombo, Math.floor(state.combo));

        ui.cookieButton.classList.add("is-pressed");
        window.setTimeout(() => ui.cookieButton.classList.remove("is-pressed"), 90);

        spawnFloat(x, y, `${labelPrefix}${format(amount)}`, color);
        spawnCrumbs(x, y, 10);
        checkAchievements();
        renderDynamic();
    }

    function pulseUnavailable() {
        spawnFloat(ui.bakeryScene.clientWidth / 2, ui.bakeryScene.clientHeight * 0.35, label("notEnoughCookies"), "#fca5a5");
        beep(120, 0.05, 0.035);
    }

    function scheduleGolden() {
        const mods = createModifiers();
        const delay = random(40000, 95000) * mods.goldenDelay;
        nextGoldenAt = Date.now() + delay;
    }

    function showGoldenCookie() {
        const scene = ui.bakeryScene.getBoundingClientRect();
        const size = 72;
        const x = random(22, Math.max(24, scene.width - size - 22));
        const y = random(74, Math.max(96, scene.height - size - 72));
        ui.goldenCookie.style.left = `${x}px`;
        ui.goldenCookie.style.top = `${y}px`;
        ui.goldenCookie.classList.remove("hidden");
        goldenVisibleUntil = Date.now() + 9000;
    }

    function hideGoldenCookie() {
        ui.goldenCookie.classList.add("hidden");
        goldenVisibleUntil = 0;
        scheduleGolden();
    }

    function claimGoldenCookie() {
        if (ui.goldenCookie.classList.contains("hidden")) {
            return;
        }

        const rect = ui.goldenCookie.getBoundingClientRect();
        const sceneRect = ui.bakeryScene.getBoundingClientRect();
        const x = rect.left - sceneRect.left + rect.width / 2;
        const y = rect.top - sceneRect.top + rect.height / 2;
        const roll = Math.random();
        const mods = createModifiers();

        state.stats.goldenClicks += 1;

        if (roll < 0.22) {
            const gain = Math.max(77, state.cookies * 0.08 + computeCps() * 120) * mods.goldenRewardMultiplier;
            addCookies(gain);
            showNotice(label("luckyBatch", { amount: format(gain) }));
            spawnFloat(x, y, `+${format(gain)}`, "#facc15");
        } else if (roll < 0.34) {
            const gain = Math.max(777, computeCps() * 240) * mods.goldenRewardMultiplier;
            addCookies(gain);
            showNotice(label("timeJump", { amount: format(gain) }));
            spawnFloat(x, y, `+${format(gain)}`, "#38bdf8");
        } else {
            const event = eventTypes[Math.floor(Math.random() * eventTypes.length)];
            state.event = { ...event };
            state.eventUntil = Date.now() + event.duration * mods.eventDurationMultiplier;
            showNotice(`${event.name}: ${event.text}`);
            spawnFloat(x, y, event.name, "#fff3bf");
        }

        spawnCrumbs(x, y, 28);
        beep(740, 0.09, 0.07);
        hideGoldenCookie();
        checkAchievements();
        renderLists();
        renderDynamic();
        saveState(statusLabel("golden"));
    }

    function activateOverdrive() {
        const now = Date.now();
        const mods = createModifiers();

        if (state.overdriveCooldownUntil > now) {
            return;
        }

        state.overdriveUntil = now + 12000 * mods.overdriveDurationMultiplier;
        state.overdriveCooldownUntil = now + 120000 * mods.overdriveCooldownMultiplier;
        showNotice(label("overdriveActive"));
        beep(520, 0.12, 0.06);
        saveState("Overdrive");
    }

    function getAscendGain() {
        return Math.floor(Math.sqrt(state.totalBaked / ASCENSION_BASE));
    }

    function ascend() {
        const gain = getAscendGain();

        if (gain <= 0) {
            return;
        }

        const message = label("ascendConfirm", { amount: gain });

        if (!window.confirm(message)) {
            return;
        }

        state.stardust += gain;
        state.ascensions += 1;
        state.cookies = 0;
        state.totalBaked = 0;
        state.buildings = {};
        state.upgrades = [];
        state.combo = 0;
        state.event = null;
        state.eventUntil = 0;
        state.overdriveUntil = 0;
        state.overdriveCooldownUntil = Date.now() + 20000;
        hideGoldenCookie();
        showNotice(`+${gain} Stardust`);
        checkAchievements();
        renderLists();
        renderDynamic();
        saveState(statusLabel("transcended"));
    }

    function checkAchievements() {
        let unlocked = false;

        for (const achievement of achievements) {
            if (!state.achievements.includes(achievement.id) && achievement.test(state)) {
                state.achievements.push(achievement.id);
                showNotice(label("unlocked", { name: achievement.name }));
                unlocked = true;
            }
        }

        if (unlocked) {
            beep(820, 0.08, 0.045);
        }
    }

    function showNotice(text, duration = 3200) {
        notice = { text, until: Date.now() + duration };
    }

    function renderDynamic() {
        const cps = computeCps();
        const clickPower = computeClickPower();
        const now = Date.now();
        const mods = createModifiers();
        const comboMultiplier = 1 + Math.min(state.combo, mods.comboCap) / 100;
        const nextStar = Math.pow(getAscendGain() + 1, 2) * ASCENSION_BASE;
        const nextStarProgress = Math.max(0, Math.min(1, state.totalBaked / nextStar));

        ui.cookieCount.textContent = format(state.cookies);
        ui.cpsCount.textContent = format(cps);
        ui.clickPower.textContent = format(clickPower * comboMultiplier);
        ui.stardustCount.textContent = format(state.stardust);
        ui.comboLabel.textContent = `x${comboMultiplier.toFixed(2)}`;
        ui.comboBar.style.transform = `scaleX(${Math.min(1, state.combo / mods.comboCap)})`;
        ui.nextStarLabel.textContent = format(nextStar);
        ui.comboBar.parentElement.title = `${Math.round(nextStarProgress * 100)}%`;

        const ascendGain = getAscendGain();
        ui.ascendButton.disabled = ascendGain <= 0;
        ui.ascendStatus.textContent = ascendGain > 0
            ? `+${ascendGain} Stardust`
            : label("untilStar", { amount: format(Math.max(0, nextStar - state.totalBaked)) });

        if (state.overdriveUntil > now) {
            ui.overdriveButton.disabled = true;
            ui.overdriveStatus.textContent = label("activeSeconds", { seconds: Math.ceil((state.overdriveUntil - now) / 1000) });
        } else if (state.overdriveCooldownUntil > now) {
            ui.overdriveButton.disabled = true;
            ui.overdriveStatus.textContent = label("cooldownSeconds", { seconds: Math.ceil((state.overdriveCooldownUntil - now) / 1000) });
        } else {
            ui.overdriveButton.disabled = false;
            ui.overdriveStatus.textContent = statusLabel("ready");
        }

        renderBanner();
        updateSoundIcon();
    }

    function renderBanner() {
        const now = Date.now();
        let text = "";

        if (notice.until > now) {
            text = notice.text;
        } else if (state.event && state.eventUntil > now) {
            text = `${state.event.name}: ${state.event.text} (${Math.ceil((state.eventUntil - now) / 1000)}s)`;
        } else if (state.overdriveUntil > now) {
            text = `Overdrive (${Math.ceil((state.overdriveUntil - now) / 1000)}s)`;
        }

        ui.eventBanner.textContent = text;
        ui.eventBanner.classList.toggle("is-visible", Boolean(text));
    }

    function renderLists() {
        renderBuildings();
        renderUpgrades();
        renderAchievements();
    }

    function renderBuildings() {
        const totalOwned = getTotalBuildings();
        ui.ownedSummary.textContent = label("ownedSummary", { amount: totalOwned });
        const mods = createModifiers();

        ui.buildingList.innerHTML = buildings.map(building => {
            const owned = getOwned(state, building.id);
            const info = getBuyInfo(building);
            const canBuy = info.amount > 0 && state.cookies >= info.cost;
            const production = building.cps * owned * mods.buildingMultipliers[building.id] * mods.cpsMultiplier;
            const buyLabel = buyMode === "max" && info.amount > 0 ? label("buyAmount", { amount: info.amount }) : label("buy");

            return `
                <article class="building-card ${canBuy ? "can-buy" : ""}">
                    <div class="building-head">
                        <span class="item-icon"><i class="${building.icon}"></i></span>
                        <div class="building-title">
                            <strong>${building.name}</strong>
                            <small>${building.note}</small>
                        </div>
                        <span class="owned-pill">${owned}</span>
                    </div>
                    <div class="building-meta">
                        <span>${label("cost")}: <strong>${format(info.cost || getBuildingCost(building))}</strong></span>
                        <span>${label("output")}: <strong>${format(production)}/s</strong></span>
                    </div>
                    <button type="button" data-buy-building="${building.id}" ${canBuy ? "" : "disabled"}>${buyLabel}</button>
                </article>
            `;
        }).join("");

        ui.buildingList.querySelectorAll("[data-buy-building]").forEach(button => {
            button.addEventListener("click", () => buyBuilding(button.dataset.buyBuilding));
        });
    }

    function renderUpgrades() {
        const available = upgrades.filter(upgrade => upgrade.requires(state));
        const buyableCount = available.filter(upgrade => !state.upgrades.includes(upgrade.id) && state.cookies >= upgrade.cost).length;
        ui.upgradeSummary.textContent = label("upgradeSummary", { bought: state.upgrades.length, ready: buyableCount });

        const visible = upgrades.filter(upgrade => upgrade.requires(state) || state.upgrades.includes(upgrade.id));

        if (!visible.length) {
            ui.upgradeList.innerHTML = `<div class="empty-note">${label("emptyResearch")}</div>`;
            return;
        }

        ui.upgradeList.innerHTML = visible.map(upgrade => {
            const bought = state.upgrades.includes(upgrade.id);
            const canBuy = !bought && state.cookies >= upgrade.cost && upgrade.requires(state);

            return `
                <article class="upgrade-card ${bought ? "is-bought" : ""} ${canBuy ? "can-buy" : ""}">
                    <div class="upgrade-head">
                        <span class="item-icon"><i class="${upgrade.icon}"></i></span>
                        <div class="upgrade-title">
                            <strong>${upgrade.name}</strong>
                            <small>${label("cost")}: ${format(upgrade.cost)}</small>
                        </div>
                        <span class="owned-pill">${bought ? "OK" : label("new")}</span>
                    </div>
                    <div class="upgrade-effect">${upgrade.effect}</div>
                    <button type="button" data-buy-upgrade="${upgrade.id}" ${canBuy ? "" : "disabled"}>${bought ? statusLabel("bought") : label("unlock")}</button>
                </article>
            `;
        }).join("");

        ui.upgradeList.querySelectorAll("[data-buy-upgrade]").forEach(button => {
            button.addEventListener("click", () => buyUpgrade(button.dataset.buyUpgrade));
        });
    }

    function renderAchievements() {
        const completeCount = state.achievements.length;
        ui.achievementSummary.textContent = label("achievementSummary", { complete: completeCount, total: achievements.length });

        ui.achievementList.innerHTML = achievements.map(achievement => {
            const complete = state.achievements.includes(achievement.id);

            return `
                <article class="achievement-card ${complete ? "is-complete" : ""}">
                    <div class="achievement-head">
                        <span class="item-icon"><i class="${achievement.icon}"></i></span>
                        <div class="achievement-title">
                            <strong>${achievement.name}</strong>
                            <small>${achievement.note}</small>
                        </div>
                    </div>
                </article>
            `;
        }).join("");
    }

    function setActiveTab(tab) {
        document.querySelectorAll(".tab-button").forEach(button => {
            const active = button.dataset.tab === tab;
            button.classList.toggle("is-active", active);
            button.setAttribute("aria-selected", String(active));
        });

        document.querySelectorAll("[data-panel]").forEach(panel => {
            panel.classList.toggle("is-active", panel.dataset.panel === tab);
        });
    }

    function setBuyMode(mode) {
        buyMode = mode === "max" ? "max" : "one";

        document.querySelectorAll("[data-buy-mode]").forEach(button => {
            button.classList.toggle("is-active", button.dataset.buyMode === buyMode);
        });

        renderBuildings();
    }

    function applyOfflineProgress() {
        const elapsedSeconds = Math.min(8 * 60 * 60, Math.max(0, (Date.now() - state.lastSaved) / 1000));

        if (elapsedSeconds < 15) {
            return;
        }

        const gain = computeCps() * elapsedSeconds * 0.35;

        if (gain > 1) {
            addCookies(gain);
            showNotice(label("offlineGain", { amount: format(gain) }), 5200);
        }
    }

    function updateGame(deltaSeconds) {
        const now = Date.now();

        if (state.event && state.eventUntil <= now) {
            state.event = null;
            state.eventUntil = 0;
        }

        if (state.combo > 0 && state.comboUntil < now) {
            state.combo = Math.max(0, state.combo - 36 * deltaSeconds);
        }

        const passive = computeCps() * deltaSeconds;
        addCookies(passive);

        if (ui.goldenCookie.classList.contains("hidden") && now >= nextGoldenAt) {
            showGoldenCookie();
        }

        if (!ui.goldenCookie.classList.contains("hidden") && now >= goldenVisibleUntil) {
            hideGoldenCookie();
        }
    }

    function spawnFloat(x, y, text, color = "#f8fafc") {
        const element = document.createElement("span");
        element.className = "float-text";
        element.textContent = text;
        element.style.setProperty("--x", `${x}px`);
        element.style.setProperty("--y", `${y}px`);
        element.style.setProperty("--color", color);
        ui.floatingLayer.appendChild(element);
        element.addEventListener("animationend", () => element.remove(), { once: true });
    }

    function spawnCrumbs(x, y, amount) {
        const colors = ["#f0bc68", "#c97c32", "#3f2418", "#fff3bf"];

        for (let index = 0; index < amount; index++) {
            const crumb = document.createElement("span");
            const size = random(4, 10);
            crumb.className = "crumb";
            crumb.style.setProperty("--x", `${x}px`);
            crumb.style.setProperty("--y", `${y}px`);
            crumb.style.setProperty("--s", `${size}px`);
            crumb.style.setProperty("--dx", `${random(-110, 110)}px`);
            crumb.style.setProperty("--dy", `${random(-120, 75)}px`);
            crumb.style.setProperty("--c", colors[Math.floor(Math.random() * colors.length)]);
            ui.floatingLayer.appendChild(crumb);
            crumb.addEventListener("animationend", () => crumb.remove(), { once: true });
        }
    }

    function resizeCanvas() {
        const rect = ui.canvas.getBoundingClientRect();
        const dpr = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
        canvasSize = {
            width: Math.max(1, rect.width),
            height: Math.max(1, rect.height),
            dpr
        };
        ui.canvas.width = Math.round(canvasSize.width * dpr);
        ui.canvas.height = Math.round(canvasSize.height * dpr);
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    function drawBakery(time) {
        const width = canvasSize.width;
        const height = canvasSize.height;
        const t = time / 1000;
        const totalOwned = getTotalBuildings();
        const ovenCount = getOwned(state, "oven") + getOwned(state, "factory") * 2;
        const labCount = getOwned(state, "lab");
        const portalCount = getOwned(state, "portal");
        const forgeCount = getOwned(state, "forge");

        ctx.clearRect(0, 0, width, height);

        const wall = ctx.createLinearGradient(0, 0, width, height);
        wall.addColorStop(0, "#111827");
        wall.addColorStop(0.5, "#182235");
        wall.addColorStop(1, "#0b1120");
        ctx.fillStyle = wall;
        ctx.fillRect(0, 0, width, height);

        drawWallTiles(width, height, t);
        drawShelves(width, height, totalOwned);
        drawConveyor(width, height, t, totalOwned);
        drawOvens(width, height, ovenCount, t);
        drawLabs(width, height, labCount, t);
        drawPortals(width, height, portalCount, t);
        drawForge(width, height, forgeCount, t);
        drawAmbientCookies(width, height, t, totalOwned);
        drawStatusGlow(width, height);
    }

    function drawWallTiles(width, height, t) {
        ctx.save();
        ctx.globalAlpha = 0.32;
        ctx.strokeStyle = "rgba(255,255,255,0.06)";
        ctx.lineWidth = 1;

        for (let x = ((t * 8) % 44) - 44; x < width + 44; x += 44) {
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, height);
            ctx.stroke();
        }

        for (let y = 0; y < height; y += 44) {
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(width, y);
            ctx.stroke();
        }

        ctx.restore();

        const floorY = height * 0.72;
        const floor = ctx.createLinearGradient(0, floorY, 0, height);
        floor.addColorStop(0, "#1f2937");
        floor.addColorStop(1, "#0f172a");
        ctx.fillStyle = floor;
        ctx.fillRect(0, floorY, width, height - floorY);
    }

    function drawShelves(width, height, totalOwned) {
        const shelfY = height * 0.18;
        ctx.save();
        ctx.fillStyle = "rgba(8, 12, 20, 0.7)";
        ctx.fillRect(width * 0.05, shelfY, width * 0.9, 12);

        const jars = Math.min(18, Math.floor(totalOwned / 3) + 3);

        for (let i = 0; i < jars; i++) {
            const x = width * 0.08 + i * (width * 0.84 / Math.max(1, jars - 1));
            const hue = i % 4;
            ctx.fillStyle = ["#facc15", "#38bdf8", "#58d68d", "#fb7185"][hue];
            ctx.globalAlpha = 0.74;
            ctx.beginPath();
            ctx.roundRect(x - 12, shelfY - 42, 24, 36, 5);
            ctx.fill();
            ctx.fillStyle = "rgba(255,255,255,0.7)";
            ctx.fillRect(x - 9, shelfY - 37, 18, 5);
        }

        ctx.restore();
    }

    function drawConveyor(width, height, t, totalOwned) {
        const y = height * 0.78;
        ctx.save();
        ctx.fillStyle = "rgba(5, 8, 14, 0.82)";
        ctx.beginPath();
        ctx.roundRect(width * 0.08, y, width * 0.84, 72, 8);
        ctx.fill();

        ctx.strokeStyle = "rgba(255,255,255,0.12)";
        ctx.lineWidth = 3;
        for (let x = width * 0.08 - ((t * 74) % 44); x < width * 0.94; x += 44) {
            ctx.beginPath();
            ctx.moveTo(x, y + 8);
            ctx.lineTo(x + 24, y + 64);
            ctx.stroke();
        }

        const cookieCount = Math.min(11, Math.floor(totalOwned / 8) + 3);
        for (let i = 0; i < cookieCount; i++) {
            const x = width * 0.12 + ((i / cookieCount) * width * 0.74 + t * 42) % (width * 0.74);
            drawSmallCookie(x, y + 36 + Math.sin(t * 2 + i) * 4, 16 + (i % 3) * 2);
        }

        ctx.restore();
    }

    function drawOvens(width, height, count, t) {
        const visible = Math.min(5, Math.ceil(count / 3));

        for (let i = 0; i < visible; i++) {
            const x = width * 0.13 + i * 82;
            const y = height * 0.45;
            const heat = 0.5 + Math.sin(t * 5 + i) * 0.2;

            ctx.save();
            ctx.fillStyle = "#334155";
            ctx.beginPath();
            ctx.roundRect(x, y, 62, 78, 8);
            ctx.fill();
            ctx.fillStyle = `rgba(250, 204, 21, ${0.38 + heat * 0.36})`;
            ctx.beginPath();
            ctx.roundRect(x + 10, y + 18, 42, 32, 6);
            ctx.fill();
            ctx.fillStyle = "rgba(255,255,255,0.18)";
            ctx.fillRect(x + 9, y + 60, 44, 4);
            ctx.restore();
        }
    }

    function drawLabs(width, height, count, t) {
        const visible = Math.min(4, Math.ceil(count / 2));

        for (let i = 0; i < visible; i++) {
            const x = width * 0.58 + i * 58;
            const y = height * 0.38;
            const bubble = 0.5 + Math.sin(t * 3 + i) * 0.5;

            ctx.save();
            ctx.strokeStyle = "rgba(255,255,255,0.55)";
            ctx.lineWidth = 4;
            ctx.beginPath();
            ctx.moveTo(x, y);
            ctx.lineTo(x, y + 74);
            ctx.stroke();

            ctx.fillStyle = "rgba(88,214,141,0.28)";
            ctx.beginPath();
            ctx.roundRect(x - 18, y + 38, 36, 54, 8);
            ctx.fill();
            ctx.fillStyle = `rgba(56,189,248,${0.34 + bubble * 0.34})`;
            ctx.beginPath();
            ctx.arc(x, y + 58, 8 + bubble * 7, 0, Math.PI * 2);
            ctx.fill();
            ctx.restore();
        }
    }

    function drawPortals(width, height, count, t) {
        const visible = Math.min(3, Math.ceil(count / 2));

        for (let i = 0; i < visible; i++) {
            const x = width * 0.72 + i * 72;
            const y = height * 0.55;
            const radius = 24 + Math.sin(t * 2 + i) * 3;

            ctx.save();
            ctx.translate(x, y);
            ctx.rotate(t * 0.9 + i);
            const gradient = ctx.createRadialGradient(0, 0, 4, 0, 0, radius);
            gradient.addColorStop(0, "rgba(250,204,21,0.9)");
            gradient.addColorStop(0.45, "rgba(167,139,250,0.55)");
            gradient.addColorStop(1, "rgba(56,189,248,0.05)");
            ctx.fillStyle = gradient;
            ctx.beginPath();
            ctx.ellipse(0, 0, radius * 0.75, radius, 0, 0, Math.PI * 2);
            ctx.fill();
            ctx.restore();
        }
    }

    function drawForge(width, height, count, t) {
        if (count <= 0) {
            return;
        }

        const power = Math.min(1, count / 8);
        const x = width * 0.5;
        const y = height * 0.32;

        ctx.save();
        ctx.globalAlpha = 0.45 + power * 0.35;
        ctx.strokeStyle = "#facc15";
        ctx.lineWidth = 2 + power * 3;

        for (let i = 0; i < 8; i++) {
            const angle = t * 0.7 + i * Math.PI / 4;
            ctx.beginPath();
            ctx.moveTo(x, y);
            ctx.lineTo(x + Math.cos(angle) * (52 + power * 44), y + Math.sin(angle) * (30 + power * 28));
            ctx.stroke();
        }

        ctx.fillStyle = "#fff7ad";
        ctx.beginPath();
        ctx.arc(x, y, 12 + power * 12, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
    }

    function drawAmbientCookies(width, height, t, totalOwned) {
        const amount = Math.min(32, Math.floor(totalOwned / 5));

        for (let i = 0; i < amount; i++) {
            const x = (i * 91 + t * (16 + i % 4) * 6) % width;
            const y = height * 0.26 + ((i * 47 + t * 13) % (height * 0.35));
            drawSmallCookie(x, y, 5 + (i % 4), 0.24);
        }
    }

    function drawSmallCookie(x, y, radius, alpha = 1) {
        ctx.save();
        ctx.globalAlpha = alpha;
        ctx.fillStyle = "#c97c32";
        ctx.beginPath();
        ctx.arc(x, y, radius, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = "#3f2418";
        ctx.beginPath();
        ctx.arc(x - radius * 0.35, y - radius * 0.2, radius * 0.18, 0, Math.PI * 2);
        ctx.arc(x + radius * 0.22, y + radius * 0.26, radius * 0.16, 0, Math.PI * 2);
        ctx.arc(x + radius * 0.36, y - radius * 0.18, radius * 0.13, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
    }

    function drawStatusGlow(width, height) {
        const now = Date.now();

        if (state.eventUntil <= now && state.overdriveUntil <= now) {
            return;
        }

        ctx.save();
        const color = state.overdriveUntil > now ? "rgba(56,189,248,0.18)" : "rgba(250,204,21,0.16)";
        ctx.fillStyle = color;
        ctx.fillRect(0, 0, width, height);
        ctx.restore();
    }

    function updateSoundIcon() {
        const icon = ui.soundToggle.querySelector("i");
        icon.className = state.sound ? "fa-solid fa-volume-high" : "fa-solid fa-volume-xmark";
    }

    function toggleSound() {
        state.sound = !state.sound;
        updateSoundIcon();
        saveState(state.sound ? statusLabel("soundOn") : statusLabel("soundOff"));
    }

    function beep(frequency, duration, gain) {
        if (!state.sound) {
            return;
        }

        try {
            audioContext = audioContext || new (window.AudioContext || window.webkitAudioContext)();
            const oscillator = audioContext.createOscillator();
            const volume = audioContext.createGain();
            oscillator.type = "triangle";
            oscillator.frequency.value = frequency;
            volume.gain.value = gain;
            oscillator.connect(volume);
            volume.connect(audioContext.destination);
            oscillator.start();
            volume.gain.exponentialRampToValueAtTime(0.0001, audioContext.currentTime + duration);
            oscillator.stop(audioContext.currentTime + duration);
        } catch (error) {
            state.sound = false;
            updateSoundIcon();
        }
    }

    function createExportPayload() {
        return {
            type: EXPORT_FORMAT,
            exportVersion: EXPORT_VERSION,
            gameVersion: VERSION,
            app: "MyTools Cookie Cosmos",
            exportedAt: new Date().toISOString(),
            state: normalizeState(state)
        };
    }

    function encodeExportPayload(payload) {
        const json = JSON.stringify(payload);
        const bytes = new TextEncoder().encode(json);
        let binary = "";

        bytes.forEach(byte => {
            binary += String.fromCharCode(byte);
        });

        return btoa(binary);
    }

    function decodeExportPayload(input) {
        const text = String(input || "").trim();

        if (!text) {
            throw new Error("empty");
        }

        let parsed = tryParseJson(text);

        if (!parsed) {
            const base64 = text.replace(/\s+/g, "").replace(/-/g, "+").replace(/_/g, "/");
            const paddedBase64 = base64.padEnd(base64.length + ((4 - base64.length % 4) % 4), "=");
            const binary = atob(paddedBase64);
            const bytes = Uint8Array.from(binary, character => character.charCodeAt(0));
            parsed = JSON.parse(new TextDecoder().decode(bytes));
        }

        const importedState = unwrapImportPayload(parsed);

        if (!isSaveLikeObject(importedState)) {
            throw new Error("invalid-save");
        }

        return normalizeState(importedState);
    }

    function tryParseJson(text) {
        try {
            return JSON.parse(text);
        } catch (error) {
            return null;
        }
    }

    function unwrapImportPayload(payload) {
        if (payload && typeof payload === "object" && payload.state && typeof payload.state === "object") {
            return payload.state;
        }

        return payload;
    }

    function isSaveLikeObject(value) {
        if (!value || typeof value !== "object") {
            return false;
        }

        return [
            "cookies",
            "totalBaked",
            "lifetimeBaked",
            "buildings",
            "upgrades",
            "achievements",
            "stardust",
            "ascensions",
            "version"
        ].some(key => Object.prototype.hasOwnProperty.call(value, key));
    }

    function getExportFilename() {
        const stamp = new Date().toISOString().slice(0, 19).replace(/[T:]/g, "-");
        return `cookie-cosmos-save-${stamp}.json`;
    }

    function downloadExportFile(payload) {
        const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");

        link.href = url;
        link.download = getExportFilename();
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
        showNotice(label("exportedFile"));
    }

    function closeOverlayOnBackdrop(overlay) {
        overlay.querySelector("[data-close]").addEventListener("click", () => overlay.remove());
        overlay.addEventListener("click", event => {
            if (event.target === overlay) {
                overlay.remove();
            }
        });
        overlay.addEventListener("keydown", event => {
            if (event.key === "Escape") {
                overlay.remove();
            }
        });
    }

    function showExportDialog() {
        const payload = createExportPayload();
        const exportCode = encodeExportPayload(payload);
        const overlay = document.createElement("div");

        overlay.className = "export-box";
        overlay.innerHTML = `
            <div class="export-dialog" role="dialog" aria-modal="true" aria-label="${label("exportDialogLabel")}" tabindex="-1">
                <h2>${label("exportTitle")}</h2>
                <p>${label("exportDescription")}</p>
                <textarea readonly aria-label="${label("exportCode")}"></textarea>
                <div class="export-actions">
                    <button type="button" data-download>${label("downloadFile")}</button>
                    <button type="button" data-copy>${label("copyCode")}</button>
                    <button type="button" data-close>${label("close")}</button>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);

        const dialog = overlay.querySelector(".export-dialog");
        const textarea = overlay.querySelector("textarea");
        textarea.value = exportCode;
        dialog.focus();
        textarea.select();

        overlay.querySelector("[data-download]").addEventListener("click", () => downloadExportFile(payload));
        overlay.querySelector("[data-copy]").addEventListener("click", async () => {
            textarea.select();
            try {
                await navigator.clipboard.writeText(textarea.value);
                showNotice(label("copiedExport"));
            } catch (error) {
                document.execCommand("copy");
                showNotice(label("markedExport"));
            }
        });

        closeOverlayOnBackdrop(overlay);
    }

    function showImportDialog() {
        const overlay = document.createElement("div");

        overlay.className = "export-box";
        overlay.innerHTML = `
            <div class="export-dialog" role="dialog" aria-modal="true" aria-label="${label("importDialogLabel")}" tabindex="-1">
                <h2>${label("importTitle")}</h2>
                <p>${label("importDescription")}</p>
                <textarea aria-label="${label("importCode")}" placeholder="${label("importPlaceholder")}"></textarea>
                <label class="import-file-picker">
                    <span>${label("chooseJson")}</span>
                    <input type="file" accept=".json,.txt,application/json,text/plain" data-file>
                </label>
                <p class="import-status" data-status></p>
                <div class="export-actions">
                    <button type="button" data-import>${label("importTitle")}</button>
                    <button type="button" data-close>${language === "en" ? "Cancel" : "Abbrechen"}</button>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);

        const dialog = overlay.querySelector(".export-dialog");
        const textarea = overlay.querySelector("textarea");
        const status = overlay.querySelector("[data-status]");
        const fileInput = overlay.querySelector("[data-file]");

        dialog.focus();
        textarea.focus();

        fileInput.addEventListener("change", () => {
            const file = fileInput.files?.[0];

            if (!file) {
                return;
            }

            const reader = new FileReader();
            reader.addEventListener("load", () => {
                textarea.value = String(reader.result || "");
                status.textContent = label("fileLoaded", { name: file.name });
            });
            reader.addEventListener("error", () => {
                status.textContent = label("fileReadError");
            });
            reader.readAsText(file);
        });

        overlay.querySelector("[data-import]").addEventListener("click", () => {
            let importedState;

            try {
                importedState = decodeExportPayload(textarea.value);
            } catch (error) {
                status.textContent = label("importInvalid");
                showNotice(label("importFailed"));
                return;
            }

            if (!window.confirm(label("replaceSaveConfirm"))) {
                return;
            }

            applyImportedState(importedState);
            overlay.remove();
        });

        closeOverlayOnBackdrop(overlay);
    }

    function applyImportedState(importedState) {
        state = normalizeState(importedState);
        lastScoreSync = 0;
        lastSubmittedScore = 0;
        scoreSyncFailedUntil = 0;
        hideGoldenCookie();
        updateSoundIcon();
        renderLists();
        renderDynamic();
        saveState(statusLabel("imported"));
        submitHighscore(true);
        showNotice(label("importedSave"));
    }

    function resetGame() {
        if (!window.confirm(label("resetConfirm"))) {
            return;
        }

        state = defaultState();
        localStorage.removeItem(STORAGE_KEY);
        hideGoldenCookie();
        scheduleGolden();
        renderLists();
        renderDynamic();
        saveState(statusLabel("reset"));
    }

    function format(value) {
        const number = Math.max(0, Number(value) || 0);

        if (number < 1000) {
            if (number < 10 && number % 1 !== 0) {
                return number.toFixed(1);
            }
            return numberFormatter.format(Math.floor(number));
        }

        const tier = Math.min(suffixes.length - 1, Math.floor(Math.log10(number) / 3));
        const scaled = number / Math.pow(1000, tier);
        const digits = scaled >= 100 ? 0 : scaled >= 10 ? 1 : 2;
        return `${scaled.toFixed(digits)}${suffixes[tier]}`;
    }

    function random(min, max) {
        return min + Math.random() * (max - min);
    }

    function setupEvents() {
        ui.cookieButton.addEventListener("click", handleCookieClick);
        ui.goldenCookie.addEventListener("click", claimGoldenCookie);
        ui.overdriveButton.addEventListener("click", activateOverdrive);
        ui.ascendButton.addEventListener("click", ascend);
        ui.soundToggle.addEventListener("click", toggleSound);
        ui.exportButton.addEventListener("click", showExportDialog);
        ui.importButton.addEventListener("click", showImportDialog);
        ui.resetButton.addEventListener("click", resetGame);

        document.querySelectorAll(".tab-button").forEach(button => {
            button.addEventListener("click", () => setActiveTab(button.dataset.tab));
        });

        document.querySelectorAll("[data-buy-mode]").forEach(button => {
            button.addEventListener("click", () => setBuyMode(button.dataset.buyMode));
        });

        window.addEventListener("resize", resizeCanvas);
        window.addEventListener("beforeunload", () => {
            saveState();
            submitHighscore(true);
        });
    }

    function loop(frameTime) {
        const deltaSeconds = Math.min(0.25, Math.max(0, (frameTime - lastFrame) / 1000));
        lastFrame = frameTime;
        updateGame(deltaSeconds);
        drawBakery(frameTime);

        if (frameTime - lastRender > 120) {
            renderDynamic();
            lastRender = frameTime;
        }

        if (frameTime - lastListRender > 650) {
            renderLists();
            lastListRender = frameTime;
        }

        if (frameTime - lastSave > 4500) {
            saveState();
            submitHighscore();
            lastSave = frameTime;
        }

        requestAnimationFrame(loop);
    }

    resizeCanvas();
    applyStaticLabels();
    setupEvents();
    applyOfflineProgress();
    checkAchievements();
    scheduleGolden();
    renderLists();
    renderDynamic();
    requestAnimationFrame(loop);
})();
