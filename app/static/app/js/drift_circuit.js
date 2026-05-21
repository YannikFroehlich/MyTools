(() => {
    const canvas = document.getElementById("gameCanvas");

    if (!canvas) {
        return;
    }

const ctx = canvas.getContext("2d", { alpha: false });

const ui = {
    map: document.getElementById("mapDisplay"),
    lap: document.getElementById("lapDisplay"),
    time: document.getElementById("timeDisplay"),
    best: document.getElementById("bestDisplay"),
    speed: document.getElementById("speedDisplay"),
    drift: document.getElementById("driftDisplay"),
    nitro: document.getElementById("nitroFill"),
    grip: document.getElementById("gripFill"),
    modeLabel: document.getElementById("modeLabel"),
    toast: document.getElementById("toast"),
    countdown: document.getElementById("countdown"),
    finalTime: document.getElementById("finalTime"),
    finalStats: document.getElementById("finalStats"),
    finishTitle: document.getElementById("finishTitle"),
    finishText: document.getElementById("finishText"),
    overlays: {
        menu: document.getElementById("menuOverlay"),
        pause: document.getElementById("pauseOverlay"),
        finish: document.getElementById("finishOverlay")
    },
    buttons: {
        start: document.getElementById("startButton"),
        restart: document.getElementById("restartButton"),
        resume: document.getElementById("resumeButton"),
        menu: document.getElementById("menuButton"),
        finishMenu: document.getElementById("finishMenuButton")
    },
    selects: {
        map: document.getElementById("mapSelect"),
        mode: document.getElementById("modeSelect"),
        difficulty: document.getElementById("difficultySelect"),
        color: document.getElementById("colorSelect")
    }
};

const keys = Object.create(null);
const blockedKeys = new Set(["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", " ", "Spacebar"]);

const modes = {
    timeTrial: { label: "Time Trial · 3 Runden", laps: 3, countdown: 0, finishByLaps: true },
    checkpointRush: { label: "Checkpoint Rush · 90 Sekunden", laps: 99, countdown: 90000, finishByLaps: false },
    zen: { label: "Zen Drive · Freies Fahren", laps: 999, countdown: 0, finishByLaps: false }
};

const difficultyProfiles = {
    normal: { grip: 0.096, grassGrip: 0.029, maxSpeed: 11.7, steer: 0.0062, driftGrip: 0.020, drag: 0.993 },
    arcade: { grip: 0.132, grassGrip: 0.044, maxSpeed: 12.2, steer: 0.0070, driftGrip: 0.038, drag: 0.994 },
    drift: { grip: 0.074, grassGrip: 0.023, maxSpeed: 12.5, steer: 0.0066, driftGrip: 0.012, drag: 0.992 }
};

const maps = {
    neonBay: {
        id: "neonBay",
        name: "Neon Bay",
        layoutName: "City Flow",
        world: { width: 3300, height: 2100 },
        trackWidth: 250,
        checkpointRadius: 155,
        startIndex: 0,
        theme: {
            groundA: "#123426",
            groundB: "#09251c",
            roadA: "#4a505c",
            roadB: "#2f3642",
            shoulder: "#121722",
            curbA: "#f8fafc",
            curbB: "#ff4d6d",
            glow: "#38bdf8",
            dust: "rgba(170, 205, 220, .38)",
            line: "rgba(255,255,255,.34)"
        },
        path: [
            [1640, 1700],
            [1050, 1650],
            [620, 1360],
            [520, 910],
            [840, 520],
            [1380, 390],
            [2000, 450],
            [2580, 720],
            [2690, 1180],
            [2390, 1540],
            [1970, 1685]
        ],
        checkpointsAt: [0, 3, 5, 7, 9],
        barriers: [
            [815, 1470, 120, 48], [575, 1060, 115, 48], [960, 410, 120, 48],
            [2030, 315, 130, 50], [2580, 585, 120, 48], [2560, 1370, 130, 50],
            [2020, 1810, 120, 48], [1390, 1815, 110, 46]
        ],
        cones: [
            [1320, 1580], [840, 1300], [725, 820], [1120, 530], [1760, 505],
            [2360, 720], [2485, 1160], [2220, 1450], [1830, 1555], [1540, 1565],
            [1180, 690], [2240, 540]
        ],
        decorations: { trees: 44, lights: 12, boards: ["NEON", "APEX", "DRIFT", "TURBO", "NIGHT"] }
    },
    desertRush: {
        id: "desertRush",
        name: "Desert Rush",
        layoutName: "Snake Rally",
        world: { width: 3900, height: 2300 },
        trackWidth: 240,
        checkpointRadius: 150,
        startIndex: 0,
        theme: {
            groundA: "#4b311f",
            groundB: "#2d1b10",
            roadA: "#5a575e",
            roadB: "#3b3b43",
            shoulder: "#19161a",
            curbA: "#fef3c7",
            curbB: "#f97316",
            glow: "#ffd166",
            dust: "rgba(219, 150, 70, .42)",
            line: "rgba(255,245,220,.32)"
        },
        path: [
            [540, 1800],
            [980, 1510],
            [640, 1180],
            [1010, 830],
            [1580, 760],
            [2100, 1010],
            [2620, 760],
            [3260, 860],
            [3430, 1320],
            [3070, 1710],
            [2450, 1790],
            [1900, 1540],
            [1350, 1820]
        ],
        checkpointsAt: [0, 2, 4, 6, 8, 10, 12],
        barriers: [
            [740, 1600, 130, 52], [520, 1280, 120, 50], [885, 920, 130, 52],
            [1530, 610, 140, 54], [2070, 860, 135, 52], [2580, 610, 135, 52],
            [3340, 965, 130, 52], [3170, 1540, 135, 52], [2490, 1930, 140, 54],
            [1820, 1700, 130, 52], [1280, 1970, 135, 52]
        ],
        cones: [
            [820, 1480], [710, 1160], [970, 980], [1390, 860], [1810, 830],
            [2260, 1040], [2580, 900], [3090, 900], [3280, 1270], [3030, 1590],
            [2500, 1650], [1980, 1510], [1500, 1690], [1040, 1740]
        ],
        decorations: { trees: 24, lights: 8, boards: ["DUST", "BOOST", "RALLY", "HEAT", "SNAKE"] }
    },
    snowPeak: {
        id: "snowPeak",
        name: "Snow Peak",
        layoutName: "Hairpin Mountain",
        world: { width: 3500, height: 2450 },
        trackWidth: 225,
        checkpointRadius: 145,
        startIndex: 0,
        ice: true,
        theme: {
            groundA: "#dbeafe",
            groundB: "#9fb6cf",
            roadA: "#657180",
            roadB: "#3f4a58",
            shoulder: "#1d2733",
            curbA: "#e0f2fe",
            curbB: "#38bdf8",
            glow: "#a78bfa",
            dust: "rgba(230, 245, 255, .46)",
            line: "rgba(245,250,255,.34)"
        },
        path: [
            [1750, 2020],
            [980, 1960],
            [650, 1640],
            [1050, 1360],
            [1720, 1440],
            [2350, 1320],
            [2780, 980],
            [2500, 640],
            [1830, 570],
            [1180, 690],
            [850, 1010],
            [1260, 1160],
            [2000, 1110],
            [2760, 1400],
            [2470, 1830]
        ],
        checkpointsAt: [0, 2, 4, 6, 8, 10, 12, 14],
        barriers: [
            [1100, 2080, 130, 50], [610, 1780, 120, 48], [900, 1275, 125, 50],
            [1660, 1560, 135, 52], [2310, 1460, 130, 50], [2760, 1110, 130, 50],
            [2460, 520, 130, 50], [1750, 440, 130, 50], [1100, 560, 130, 50],
            [760, 905, 120, 48], [1340, 1030, 125, 50], [2070, 980, 130, 50],
            [2700, 1550, 130, 50], [2480, 1970, 130, 50]
        ],
        cones: [
            [1280, 1890], [790, 1650], [980, 1420], [1390, 1450], [1970, 1360],
            [2440, 1210], [2600, 840], [2230, 650], [1640, 650], [1080, 780],
            [900, 1030], [1340, 1190], [1970, 1150], [2460, 1330], [2610, 1710],
            [2130, 1900]
        ],
        decorations: { trees: 62, lights: 14, boards: ["ICE", "PEAK", "GLIDE", "SNOW", "FROST"] }
    }
};

const game = {
    state: "menu",
    mapId: localStorage.getItem("dcp-map") || "neonBay",
    mode: localStorage.getItem("dcp-mode") || "timeTrial",
    difficulty: localStorage.getItem("dcp-difficulty") || "normal",
    startedAt: 0,
    elapsed: 0,
    pausedAt: 0,
    pauseOffset: 0,
    countdownStart: 0,
    currentLap: 1,
    totalLaps: 3,
    nextCheckpoint: 0,
    checkpointHits: 0,
    score: 0,
    driftScore: 0,
    driftCombo: 0,
    bestDrift: 0,
    lapTimes: [],
    lastLapStart: 0,
    shake: 0,
    flash: 0,
    toastTimer: 0,
    frame: 0,
    camera: { x: 0, y: 0, tx: 0, ty: 0 }
};

const car = {
    x: 0,
    y: 0,
    vx: 0,
    vy: 0,
    angle: -Math.PI / 2,
    angularVelocity: 0,
    width: 38,
    height: 64,
    color: localStorage.getItem("dcp-color") || "#ff4d6d",
    enginePower: 0.265,
    reversePower: 0.135,
    brakePower: 0.958,
    nitro: 100,
    maxNitro: 100,
    heat: 0,
    damaged: 0,
    lastOnRoad: true
};

let activeMap = maps[game.mapId] || maps.neonBay;
let pathSegments = [];
let checkpointGates = [];
let barriers = [];
let cones = [];
let decorations = [];
let grassBlades = [];
let asphaltSpeckles = [];
let tireMarks = [];
let particles = [];
let floatingTexts = [];

const rand = (min, max) => min + Math.random() * (max - min);

function syncSelects() {
    ui.selects.map.value = game.mapId;
    ui.selects.mode.value = game.mode;
    ui.selects.difficulty.value = game.difficulty;
    ui.selects.color.value = car.color;
    updateLabels();
    updateBestDisplay();
}

function applyOptions() {
    game.mapId = ui.selects.map.value;
    game.mode = ui.selects.mode.value;
    game.difficulty = ui.selects.difficulty.value;
    car.color = ui.selects.color.value;
    activeMap = maps[game.mapId] || maps.neonBay;

    localStorage.setItem("dcp-map", game.mapId);
    localStorage.setItem("dcp-mode", game.mode);
    localStorage.setItem("dcp-difficulty", game.difficulty);
    localStorage.setItem("dcp-color", car.color);

    updateLabels();
    updateBestDisplay();
}

function updateLabels() {
    activeMap = maps[game.mapId] || maps.neonBay;
    ui.map.textContent = activeMap.name;
    ui.modeLabel.textContent = `${modes[game.mode].label} · ${activeMap.name} · ${activeMap.layoutName}`;
}

window.addEventListener("keydown", event => {
    if (blockedKeys.has(event.key)) event.preventDefault();
    const key = normalizeKey(event.key);
    keys[key] = true;

    if (key === "r") restartRace();
    if (key === "p") togglePause();
    if (key === "m") switchMapInGame();
    if ((key === "enter" || key === " ") && game.state === "menu") startRace();
}, { passive: false });

window.addEventListener("keyup", event => {
    if (blockedKeys.has(event.key)) event.preventDefault();
    keys[normalizeKey(event.key)] = false;
}, { passive: false });

for (const button of document.querySelectorAll(".touch-btn")) {
    const key = button.dataset.key;
    const press = event => { event.preventDefault(); keys[key] = true; };
    const release = event => { event.preventDefault(); keys[key] = false; };
    button.addEventListener("pointerdown", press);
    button.addEventListener("pointerup", release);
    button.addEventListener("pointercancel", release);
    button.addEventListener("pointerleave", release);
}

ui.buttons.start.addEventListener("click", startRace);
ui.buttons.restart.addEventListener("click", restartRace);
ui.buttons.resume.addEventListener("click", togglePause);
ui.buttons.menu.addEventListener("click", goToMenu);
ui.buttons.finishMenu.addEventListener("click", goToMenu);
Object.values(ui.selects).forEach(select => select.addEventListener("change", applyOptions));

function normalizeKey(key) {
    if (key === " ") return " ";
    if (key === "Shift") return "shift";
    return key.toLowerCase();
}

function startRace() {
    applyOptions();
    resetGame();
    ui.overlays.menu.classList.add("hidden");
    ui.overlays.finish.classList.add("hidden");
    ui.overlays.pause.classList.add("hidden");
    game.state = "countdown";
    game.countdownStart = performance.now();
    ui.countdown.classList.remove("hidden");
    ui.countdown.textContent = "3";
}

function restartRace() {
    if (game.state === "menu") return;
    startRace();
}

function goToMenu() {
    game.state = "menu";
    ui.overlays.pause.classList.add("hidden");
    ui.overlays.finish.classList.add("hidden");
    ui.overlays.menu.classList.remove("hidden");
    ui.countdown.classList.add("hidden");
}

function togglePause() {
    if (game.state === "running") {
        game.state = "paused";
        game.pausedAt = performance.now();
        ui.overlays.pause.classList.remove("hidden");
    } else if (game.state === "paused") {
        game.state = "running";
        game.pauseOffset += performance.now() - game.pausedAt;
        ui.overlays.pause.classList.add("hidden");
    }
}

function switchMapInGame() {
    const ids = Object.keys(maps);
    const index = ids.indexOf(game.mapId);
    game.mapId = ids[(index + 1) % ids.length];
    ui.selects.map.value = game.mapId;
    applyOptions();
    resetGame();
    showToast(`${activeMap.name}: ${activeMap.layoutName}`);
}

function resetGame() {
    activeMap = maps[game.mapId] || maps.neonBay;
    buildTrackData();

    barriers = activeMap.barriers.map(([x, y, width, height]) => ({ x, y, width, height }));
    cones = activeMap.cones.map(([x, y]) => ({ x, y, baseX: x, baseY: y, hit: false, vx: 0, vy: 0, spin: 0 }));
    seedMapDecorations();

    const start = getPointOnPath(activeMap.startIndex || 0);
    const next = getPointOnPath((activeMap.startIndex || 0) + 1);
    car.x = start.x;
    car.y = start.y;
    car.vx = 0;
    car.vy = 0;
    car.angle = Math.atan2(next.y - start.y, next.x - start.x);
    car.angularVelocity = 0;
    car.nitro = car.maxNitro;
    car.heat = 0;
    car.damaged = 0;
    car.lastOnRoad = true;

    game.currentLap = 1;
    game.totalLaps = modes[game.mode].laps;
    game.nextCheckpoint = 0;
    game.checkpointHits = 0;
    game.score = 0;
    game.driftScore = 0;
    game.driftCombo = 0;
    game.bestDrift = 0;
    game.lapTimes = [];
    game.elapsed = 0;
    game.pauseOffset = 0;
    game.shake = 0;
    game.flash = 0;
    game.toastTimer = 0;

    tireMarks = [];
    particles = [];
    floatingTexts = [];

    centerCameraInstant();
    updateUI();
}

function buildTrackData() {
    const path = activeMap.path.map(([x, y]) => ({ x, y }));
    pathSegments = [];

    for (let i = 0; i < path.length; i++) {
        const a = path[i];
        const b = path[(i + 1) % path.length];
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        pathSegments.push({
            a,
            b,
            dx,
            dy,
            lengthSq: dx * dx + dy * dy,
            length: Math.hypot(dx, dy)
        });
    }

    checkpointGates = activeMap.checkpointsAt.map((pathIndex, order) => {
        const p = getPointOnPath(pathIndex);
        const n = getPointOnPath(pathIndex + 1);
        const angle = Math.atan2(n.y - p.y, n.x - p.x);
        return {
            x: p.x,
            y: p.y,
            radius: activeMap.checkpointRadius,
            angle,
            name: order === 0 ? "Start/Ziel" : `Checkpoint ${order}`,
            bonus: 650 + order * 90
        };
    });
}

function getPointOnPath(index) {
    const path = activeMap.path;
    const i = ((index % path.length) + path.length) % path.length;
    return { x: path[i][0], y: path[i][1] };
}

function seedMapDecorations() {
    decorations = [];
    grassBlades = [];
    asphaltSpeckles = [];

    let r = activeMap.id.split("").reduce((sum, char) => sum + char.charCodeAt(0), 0) * 999;
    const sr = () => {
        r = (r * 1664525 + 1013904223) % 4294967296;
        return r / 4294967296;
    };

    for (let i = 0; i < activeMap.decorations.trees; i++) {
        let x, y, tries = 0;
        do {
            x = sr() * activeMap.world.width;
            y = sr() * activeMap.world.height;
            tries++;
        } while (distanceToTrack(x, y).distance < activeMap.trackWidth * 0.85 && tries < 80);

        decorations.push({ type: "tree", x, y, s: 0.65 + sr() * 0.8, wobble: sr() * Math.PI * 2 });
    }

    for (let i = 0; i < activeMap.decorations.lights; i++) {
        const pathIndex = Math.floor(i / activeMap.decorations.lights * activeMap.path.length);
        const p = getPointOnPath(pathIndex);
        const n = getPointOnPath(pathIndex + 1);
        const angle = Math.atan2(n.y - p.y, n.x - p.x);
        const side = i % 2 === 0 ? 1 : -1;
        decorations.push({
            type: "light",
            x: p.x + Math.cos(angle + Math.PI / 2) * activeMap.trackWidth * 0.82 * side,
            y: p.y + Math.sin(angle + Math.PI / 2) * activeMap.trackWidth * 0.82 * side,
            angle: angle + side * 1.1
        });
    }

    activeMap.decorations.boards.forEach((text, i) => {
        const p = getPointOnPath(i * 2 + 1);
        const n = getPointOnPath(i * 2 + 2);
        const angle = Math.atan2(n.y - p.y, n.x - p.x);
        const side = i % 2 === 0 ? 1 : -1;
        decorations.push({
            type: "board",
            text,
            x: p.x + Math.cos(angle + Math.PI / 2) * activeMap.trackWidth * 0.95 * side - 65,
            y: p.y + Math.sin(angle + Math.PI / 2) * activeMap.trackWidth * 0.95 * side - 18
        });
    });

    for (let i = 0; i < 520; i++) {
        grassBlades.push({
            x: sr() * activeMap.world.width,
            y: sr() * activeMap.world.height,
            h: 5 + sr() * 12,
            a: -0.45 + sr() * 0.9,
            alpha: 0.07 + sr() * 0.20
        });
    }

    for (let i = 0; i < 1300; i++) {
        const segment = pathSegments[Math.floor(sr() * pathSegments.length)];
        const t = sr();
        const side = (sr() - 0.5) * activeMap.trackWidth * 0.82;
        const len = segment.length || 1;
        const nx = -segment.dy / len;
        const ny = segment.dx / len;
        asphaltSpeckles.push({
            x: segment.a.x + segment.dx * t + nx * side,
            y: segment.a.y + segment.dy * t + ny * side,
            w: 1 + sr() * 4,
            a: 0.03 + sr() * 0.12,
            light: sr() > .5
        });
    }
}

function beginRunning() {
    game.state = "running";
    game.startedAt = performance.now();
    game.lastLapStart = game.startedAt;
    ui.countdown.classList.add("hidden");
    showToast(`${activeMap.name}: ${activeMap.layoutName}`);
}

let lastTime = performance.now();
function loop(now) {
    const dt = Math.min(32, now - lastTime) / 16.6667;
    lastTime = now;
    update(now, dt);
    draw();
    requestAnimationFrame(loop);
}

function update(now, dt) {
    game.frame++;

    if (game.state === "countdown") updateCountdown(now);
    updateParticles(dt);
    updateFloatingTexts(dt);
    updateCamera(dt);

    if (game.toastTimer > 0) {
        game.toastTimer -= dt;
        if (game.toastTimer <= 0) ui.toast.classList.add("hidden");
    }

    if (game.shake > 0) game.shake = Math.max(0, game.shake * Math.pow(0.88, dt) - 0.02);
    if (game.flash > 0) game.flash = Math.max(0, game.flash - 0.035 * dt);

    if (game.state !== "running") {
        updateUI();
        return;
    }

    game.elapsed = now - game.startedAt - game.pauseOffset;

    const mode = modes[game.mode];
    if (mode.countdown && game.elapsed >= mode.countdown) {
        finishRace("Zeit abgelaufen", "Checkpoint Rush beendet:");
        return;
    }

    updateCarPhysics(dt);
    handleWorldBounds();
    handleBarrierCollisions();
    handleConeCollisions(dt);
    handleCheckpoints();
    updateUI();
}

function updateCountdown(now) {
    const passed = now - game.countdownStart;
    const left = 3 - Math.floor(passed / 800);
    const shown = left > 0 ? String(left) : "GO!";

    if (shown !== ui.countdown.textContent) {
        ui.countdown.textContent = shown;
        ui.countdown.style.animation = "none";
        void ui.countdown.offsetHeight;
        ui.countdown.style.animation = "";
    }

    if (passed >= 3200) beginRunning();
}

function updateCarPhysics(dt) {
    const profile = getProfile();
    const forward = keys["w"] || keys["arrowup"];
    const backward = keys["s"] || keys["arrowdown"];
    const left = keys["a"] || keys["arrowleft"];
    const right = keys["d"] || keys["arrowright"];
    const handbrake = keys[" "] || keys["spacebar"];
    const nitroKey = keys["shift"];

    const forwardX = Math.cos(car.angle);
    const forwardY = Math.sin(car.angle);
    const rightX = Math.cos(car.angle + Math.PI / 2);
    const rightY = Math.sin(car.angle + Math.PI / 2);

    let forwardSpeed = car.vx * forwardX + car.vy * forwardY;
    let sideSpeed = car.vx * rightX + car.vy * rightY;
    const speed = Math.hypot(car.vx, car.vy);
    const trackDistance = distanceToTrack(car.x, car.y);
    const onRoad = trackDistance.distance <= activeMap.trackWidth / 2;
    const onShoulder = trackDistance.distance <= activeMap.trackWidth / 2 + 46;
    const usingNitro = nitroKey && car.nitro > 0 && forward && speed > 2;

    let grip = handbrake ? profile.driftGrip : onRoad ? profile.grip : onShoulder ? profile.grassGrip * 1.25 : profile.grassGrip;
    let drag = onRoad ? profile.drag : onShoulder ? 0.972 : 0.954;
    let maxSpeed = profile.maxSpeed;

    if (activeMap.ice) {
        grip *= 0.76;
        drag += 0.001;
        maxSpeed *= 0.98;
    }

    if (usingNitro) {
        maxSpeed *= 1.34;
        car.nitro = Math.max(0, car.nitro - 0.72 * dt);
        car.heat = Math.min(1, car.heat + 0.018 * dt);
        spawnFlame();
    } else {
        const recharge = onRoad ? 0.10 : 0.045;
        car.nitro = Math.min(car.maxNitro, car.nitro + recharge * dt + Math.min(game.driftCombo, 3) * 0.012 * dt);
        car.heat = Math.max(0, car.heat - 0.010 * dt);
    }

    if (forward) {
        const boost = usingNitro ? 1.58 : 1;
        car.vx += forwardX * car.enginePower * boost * dt;
        car.vy += forwardY * car.enginePower * boost * dt;
    }

    if (backward) {
        if (forwardSpeed > 1.15) {
            car.vx *= Math.pow(car.brakePower, dt);
            car.vy *= Math.pow(car.brakePower, dt);
        } else {
            car.vx -= forwardX * car.reversePower * dt;
            car.vy -= forwardY * car.reversePower * dt;
        }
    }

    forwardSpeed = car.vx * forwardX + car.vy * forwardY;
    sideSpeed = car.vx * rightX + car.vy * rightY;

    car.vx -= rightX * sideSpeed * grip * dt;
    car.vy -= rightY * sideSpeed * grip * dt;

    const newSpeed = Math.hypot(car.vx, car.vy);
    const steerInput = (right ? 1 : 0) - (left ? 1 : 0);
    const speedSteerFactor = clamp(newSpeed / maxSpeed, 0, 1);

    car.angularVelocity += steerInput * profile.steer * speedSteerFactor * Math.sign(forwardSpeed || 1) * dt;
    if (handbrake && newSpeed > 2.2) car.angularVelocity += steerInput * 0.0038 * dt;

    car.angularVelocity *= Math.pow(0.88, dt);
    car.angle += car.angularVelocity * dt;

    car.vx *= Math.pow(drag, dt);
    car.vy *= Math.pow(drag, dt);

    const limitedSpeed = Math.hypot(car.vx, car.vy);
    if (limitedSpeed > maxSpeed) {
        const scale = maxSpeed / limitedSpeed;
        car.vx *= scale;
        car.vy *= scale;
    }

    car.x += car.vx * dt;
    car.y += car.vy * dt;

    const driftAmount = Math.abs(sideSpeed);
    const isDrifting = driftAmount > 1.0 && newSpeed > 2.6;
    if (isDrifting) {
        addTireMarks();
        const gained = Math.floor((driftAmount * newSpeed) * 0.18 * dt);
        game.driftCombo += 0.045 * dt;
        game.driftScore += gained;
        game.bestDrift = Math.max(game.bestDrift, Math.floor(game.driftCombo * 100));
        if (game.frame % 2 === 0) spawnSmoke(2, onRoad ? activeMap.theme.dust : "rgba(120,90,55,.36)");
    } else {
        if (game.driftCombo > 1.1) {
            addFloatingText(car.x, car.y - 40, `+${Math.floor(game.driftCombo * 75)} Drift`, "#65f29a");
            game.score += Math.floor(game.driftCombo * 75);
        }
        game.driftCombo = Math.max(0, game.driftCombo - 0.10 * dt);
    }

    if (!onRoad && newSpeed > 1.2 && game.frame % 3 === 0) {
        spawnSmoke(1, activeMap.theme.dust);
    }

    car.lastOnRoad = onRoad;
}

function getProfile() {
    const p = { ...difficultyProfiles[game.difficulty] };
    if (activeMap.ice) {
        p.grip *= 0.86;
        p.driftGrip *= 0.78;
        p.grassGrip *= 0.82;
    }
    return p;
}

function handleWorldBounds() {
    const padding = 42;
    let hit = false;
    if (car.x < padding) { car.x = padding; car.vx *= -0.38; hit = true; }
    if (car.x > activeMap.world.width - padding) { car.x = activeMap.world.width - padding; car.vx *= -0.38; hit = true; }
    if (car.y < padding) { car.y = padding; car.vy *= -0.38; hit = true; }
    if (car.y > activeMap.world.height - padding) { car.y = activeMap.world.height - padding; car.vy *= -0.38; hit = true; }
    if (hit) crashEffect();
}

function handleBarrierCollisions() {
    const box = getCarBox();
    for (const barrier of barriers) {
        if (!rectsCollide(box, barrier)) continue;
        const centerX = barrier.x + barrier.width / 2;
        const centerY = barrier.y + barrier.height / 2;
        const dx = car.x - centerX;
        const dy = car.y - centerY;
        const len = Math.hypot(dx, dy) || 1;
        const nx = dx / len;
        const ny = dy / len;
        car.x += nx * 16;
        car.y += ny * 16;
        const dot = car.vx * nx + car.vy * ny;
        car.vx -= 1.85 * dot * nx;
        car.vy -= 1.85 * dot * ny;
        car.vx *= 0.55;
        car.vy *= 0.55;
        car.angularVelocity += (Math.random() - 0.5) * 0.09;
        car.damaged = Math.min(1, car.damaged + 0.12);
        crashEffect();
    }
}

function handleConeCollisions(dt) {
    for (const cone of cones) {
        const distance = Math.hypot(car.x - cone.x, car.y - cone.y);
        if (distance < 30 && !cone.hit) {
            cone.hit = true;
            cone.vx = (cone.x - car.x) * 0.15 + car.vx * 0.86;
            cone.vy = (cone.y - car.y) * 0.15 + car.vy * 0.86;
            cone.spin = rand(-0.2, 0.2);
            car.vx *= 0.94;
            car.vy *= 0.94;
            spawnSparks(cone.x, cone.y, 12, "#ffd166");
            addFloatingText(cone.x, cone.y - 20, "Bonk!", "#ffd166");
        }
        if (cone.hit) {
            cone.x += cone.vx * dt;
            cone.y += cone.vy * dt;
            cone.vx *= Math.pow(0.94, dt);
            cone.vy *= Math.pow(0.94, dt);
            cone.spin *= Math.pow(0.97, dt);
        }
    }
}

function handleCheckpoints() {
    const checkpoint = checkpointGates[game.nextCheckpoint];
    if (!checkpoint) return;

    if (Math.hypot(car.x - checkpoint.x, car.y - checkpoint.y) < checkpoint.radius) {
        spawnSparks(checkpoint.x, checkpoint.y, 24, "#65f29a");
        game.score += checkpoint.bonus + Math.floor(game.driftCombo * 40);
        game.checkpointHits++;
        addFloatingText(checkpoint.x, checkpoint.y - 25, checkpoint.name, "#65f29a");
        showToast(checkpoint.name);

        game.nextCheckpoint++;
        if (game.nextCheckpoint >= checkpointGates.length) {
            game.nextCheckpoint = 0;
            game.currentLap++;
            game.lapTimes.push(performance.now() - game.lastLapStart);
            game.lastLapStart = performance.now();
            showToast(`Runde ${Math.min(game.currentLap, game.totalLaps)} / ${game.totalLaps}`);

            if (modes[game.mode].finishByLaps && game.currentLap > game.totalLaps) finishRace("Rennen beendet", "Deine Zeit:");
        }
    }
}

function finishRace(title = "Rennen beendet", text = "Deine Zeit:") {
    game.state = "finished";
    ui.finishTitle.textContent = title;
    ui.finishText.textContent = text;
    ui.finalTime.textContent = game.mode === "checkpointRush" ? `${game.checkpointHits} Checkpoints` : formatTime(game.elapsed);

    const bestKey = getBestKey();
    if (game.mode !== "zen") {
        const previous = localStorage.getItem(bestKey);
        const result = game.mode === "checkpointRush" ? game.checkpointHits : game.elapsed;
        const isBetter = game.mode === "checkpointRush" ? (!previous || result > Number(previous)) : (!previous || result < Number(previous));
        if (isBetter) localStorage.setItem(bestKey, String(result));
    }

    ui.finalStats.innerHTML = `
        <div><span>Map</span><strong>${activeMap.name}</strong></div>
        <div><span>Layout</span><strong>${activeMap.layoutName}</strong></div>
        <div><span>Score</span><strong>${game.score.toLocaleString("de-DE")}</strong></div>
        <div><span>Driftpunkte</span><strong>${Math.floor(game.driftScore).toLocaleString("de-DE")}</strong></div>
        <div><span>Checkpoints</span><strong>${game.checkpointHits}</strong></div>
    `;
    updateBestDisplay();
    ui.overlays.finish.classList.remove("hidden");
}

function showToast(text) {
    ui.toast.textContent = text;
    ui.toast.classList.remove("hidden");
    game.toastTimer = 120;
}

function centerCameraInstant() {
    game.camera.x = clamp(car.x - canvas.width / 2, 0, Math.max(0, activeMap.world.width - canvas.width));
    game.camera.y = clamp(car.y - canvas.height / 2, 0, Math.max(0, activeMap.world.height - canvas.height));
}

function updateCamera(dt) {
    const lookAhead = clamp(Math.hypot(car.vx, car.vy) * 18, 0, 170);
    const targetX = car.x + Math.cos(car.angle) * lookAhead - canvas.width / 2;
    const targetY = car.y + Math.sin(car.angle) * lookAhead - canvas.height / 2;
    const maxX = Math.max(0, activeMap.world.width - canvas.width);
    const maxY = Math.max(0, activeMap.world.height - canvas.height);

    game.camera.tx = clamp(targetX, 0, maxX);
    game.camera.ty = clamp(targetY, 0, maxY);

    const lerpAmount = 1 - Math.pow(0.90, dt);
    game.camera.x += (game.camera.tx - game.camera.x) * lerpAmount;
    game.camera.y += (game.camera.ty - game.camera.y) * lerpAmount;
}

function addTireMarks() {
    const backDistance = 23;
    const sideDistance = 15;
    const backX = car.x - Math.cos(car.angle) * backDistance;
    const backY = car.y - Math.sin(car.angle) * backDistance;
    const sideX = Math.cos(car.angle + Math.PI / 2);
    const sideY = Math.sin(car.angle + Math.PI / 2);

    tireMarks.push({
        x1: backX + sideX * sideDistance,
        y1: backY + sideY * sideDistance,
        x2: backX - sideX * sideDistance,
        y2: backY - sideY * sideDistance,
        life: 360,
        maxLife: 360
    });

    if (tireMarks.length > 1000) tireMarks.shift();
}

function spawnSmoke(amount, color) {
    for (let i = 0; i < amount; i++) {
        const backX = car.x - Math.cos(car.angle) * 30;
        const backY = car.y - Math.sin(car.angle) * 30;
        particles.push({
            type: "smoke",
            x: backX + rand(-16, 16),
            y: backY + rand(-16, 16),
            vx: rand(-0.9, 0.9) - car.vx * 0.04,
            vy: rand(-0.9, 0.9) - car.vy * 0.04,
            radius: rand(7, 13),
            life: 48,
            maxLife: 48,
            color
        });
    }
}

function spawnFlame() {
    if (game.frame % 2 !== 0) return;
    const backX = car.x - Math.cos(car.angle) * 36;
    const backY = car.y - Math.sin(car.angle) * 36;
    particles.push({
        type: "flame",
        x: backX + rand(-5, 5),
        y: backY + rand(-5, 5),
        vx: -Math.cos(car.angle) * rand(1.2, 2.4) + rand(-0.4, 0.4),
        vy: -Math.sin(car.angle) * rand(1.2, 2.4) + rand(-0.4, 0.4),
        radius: rand(4, 8),
        life: 18,
        maxLife: 18,
        color: Math.random() > .5 ? "#38bdf8" : "#ffd166"
    });
}

function spawnSparks(x, y, amount, color) {
    for (let i = 0; i < amount; i++) {
        particles.push({
            type: "spark",
            x,
            y,
            vx: rand(-7, 7),
            vy: rand(-7, 7),
            radius: rand(2, 4),
            life: 30,
            maxLife: 30,
            color
        });
    }
}

function crashEffect() {
    game.shake = Math.max(game.shake, 9);
    game.flash = 0.22;
    spawnSparks(car.x, car.y, 15, "#ff4d6d");
}

function updateParticles(dt) {
    for (const p of particles) {
        p.x += p.vx * dt;
        p.y += p.vy * dt;
        const damp = p.type === "smoke" ? 0.972 : 0.91;
        p.vx *= Math.pow(damp, dt);
        p.vy *= Math.pow(damp, dt);
        if (p.type === "smoke") p.radius += 0.22 * dt;
        p.life -= dt;
    }
    particles = particles.filter(p => p.life > 0);

    for (const mark of tireMarks) mark.life -= dt;
    tireMarks = tireMarks.filter(mark => mark.life > 0);
}

function addFloatingText(x, y, text, color) {
    floatingTexts.push({ x, y, text, color, life: 72, maxLife: 72 });
}

function updateFloatingTexts(dt) {
    for (const t of floatingTexts) {
        t.y -= 0.42 * dt;
        t.life -= dt;
    }
    floatingTexts = floatingTexts.filter(t => t.life > 0);
}

function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const shakeX = game.shake ? rand(-game.shake, game.shake) : 0;
    const shakeY = game.shake ? rand(-game.shake, game.shake) : 0;

    ctx.save();
    ctx.translate(shakeX, shakeY);
    ctx.translate(-game.camera.x, -game.camera.y);

    drawBackground();
    drawDecorations();
    drawTrack();
    drawTrackDetails();
    drawCheckpoints();
    drawTireMarks();
    drawBarriers();
    drawCones();
    drawParticles();
    drawCar();
    drawFloatingTexts();

    ctx.restore();

    drawScreenVignette();
    drawMinimap();
    drawCompassArrow();

    if (game.flash > 0) {
        ctx.save();
        ctx.globalAlpha = game.flash;
        ctx.fillStyle = "#ff4d6d";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.restore();
    }
}

function drawBackground() {
    const theme = activeMap.theme;
    const gradient = ctx.createLinearGradient(0, 0, activeMap.world.width, activeMap.world.height);
    gradient.addColorStop(0, theme.groundA);
    gradient.addColorStop(1, theme.groundB);
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, activeMap.world.width, activeMap.world.height);

    ctx.save();
    for (let x = 0; x < activeMap.world.width; x += 48) {
        for (let y = 0; y < activeMap.world.height; y += 48) {
            const shade = (x * 13 + y * 7) % 96;
            ctx.fillStyle = shade > 48 ? "rgba(255,255,255,0.025)" : "rgba(0,0,0,0.025)";
            ctx.fillRect(x, y, 48, 48);
        }
    }

    for (const blade of grassBlades) {
        if (!isVisible(blade.x, blade.y, 80)) continue;
        if (distanceToTrack(blade.x, blade.y).distance < activeMap.trackWidth * .62) continue;
        ctx.globalAlpha = blade.alpha;
        ctx.strokeStyle = activeMap.ice ? "#f8fafc" : "#d9ffd9";
        ctx.beginPath();
        ctx.moveTo(blade.x, blade.y);
        ctx.lineTo(blade.x + Math.sin(blade.a) * 5, blade.y - blade.h);
        ctx.stroke();
    }
    ctx.restore();
}

function drawDecorations() {
    for (const d of decorations) {
        if (!isVisible(d.x, d.y, 180)) continue;
        if (d.type === "tree") drawTree(d);
        if (d.type === "light") drawLightPole(d);
        if (d.type === "board") drawSponsorBoard(d);
    }
}

function drawTree(tree) {
    ctx.save();
    ctx.translate(tree.x, tree.y);
    ctx.scale(tree.s, tree.s);
    ctx.fillStyle = "rgba(0,0,0,.22)";
    ctx.beginPath();
    ctx.ellipse(5, 12, 24, 11, 0, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = activeMap.ice ? "#5b4638" : "#5b3a22";
    ctx.fillRect(-4, 2, 8, 24);

    const colors = activeMap.ice ? ["#eef6ff", "#dbeafe", "#bfdbfe"] : ["#2ecc71", "#27ae60", "#1f8f4d"];
    for (let i = 0; i < 4; i++) {
        ctx.fillStyle = colors[i % colors.length];
        ctx.beginPath();
        ctx.arc((i - 1.5) * 9, -8 + (i % 2) * 5, 17, 0, Math.PI * 2);
        ctx.fill();
    }
    ctx.restore();
}

function drawLightPole(pole) {
    ctx.save();
    ctx.translate(pole.x, pole.y);
    ctx.rotate(pole.angle);
    ctx.strokeStyle = "rgba(220,230,240,.55)";
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(0, 70);
    ctx.stroke();

    ctx.fillStyle = "#d8dee9";
    ctx.beginPath();
    ctx.roundRect(-14, -12, 28, 13, 5);
    ctx.fill();

    ctx.globalAlpha = 0.12;
    ctx.fillStyle = activeMap.theme.glow;
    ctx.beginPath();
    ctx.moveTo(-42, -2);
    ctx.lineTo(42, -2);
    ctx.lineTo(110, 135);
    ctx.lineTo(-110, 135);
    ctx.closePath();
    ctx.fill();
    ctx.restore();
}

function drawSponsorBoard(board) {
    ctx.save();
    ctx.fillStyle = "rgba(8,12,20,.84)";
    ctx.strokeStyle = "rgba(255,255,255,.18)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.roundRect(board.x, board.y, 132, 38, 10);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = activeMap.theme.glow;
    ctx.font = "900 18px Arial";
    ctx.textAlign = "center";
    ctx.fillText(board.text, board.x + 66, board.y + 25);
    ctx.restore();
}

function drawTrack() {
    const theme = activeMap.theme;
    ctx.save();

    ctx.lineJoin = "round";
    ctx.lineCap = "round";

    drawPathStroke(activeMap.trackWidth + 38, theme.shoulder, 1);
    drawPathStroke(activeMap.trackWidth, makeRoadGradient(), 1);

    ctx.shadowColor = "rgba(0,0,0,.42)";
    ctx.shadowBlur = 14;
    drawPathStroke(activeMap.trackWidth + 8, "rgba(0,0,0,.18)", 0.16);
    ctx.shadowBlur = 0;

    ctx.restore();
}

function makeRoadGradient() {
    const theme = activeMap.theme;
    const gradient = ctx.createLinearGradient(0, 0, activeMap.world.width, activeMap.world.height);
    gradient.addColorStop(0, theme.roadA);
    gradient.addColorStop(.5, theme.roadB);
    gradient.addColorStop(1, theme.roadA);
    return gradient;
}

function drawPathStroke(width, stroke, alpha = 1) {
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.strokeStyle = stroke;
    ctx.lineWidth = width;
    ctx.beginPath();
    activeMap.path.forEach(([x, y], index) => {
        if (index === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    });
    ctx.closePath();
    ctx.stroke();
    ctx.restore();
}

function drawTrackDetails() {
    ctx.save();
    ctx.lineJoin = "round";
    ctx.lineCap = "round";

    drawPathStroke(6, activeMap.theme.line, 1);

    ctx.setLineDash([36, 30]);
    ctx.lineDashOffset = -game.frame * 0.65;
    drawPathStroke(5, "rgba(255,255,255,.32)", 1);
    ctx.setLineDash([]);

    drawCurbsAlongPath();
    drawStartLine();
    drawRoadArrows();
    drawAsphaltNoise();

    ctx.restore();
}

function drawCurbsAlongPath() {
    const theme = activeMap.theme;
    const step = 52;
    ctx.save();

    let count = 0;
    for (const seg of pathSegments) {
        const pieces = Math.max(2, Math.floor(seg.length / step));
        const nx = -seg.dy / (seg.length || 1);
        const ny = seg.dx / (seg.length || 1);

        for (let i = 0; i <= pieces; i++) {
            const t = i / pieces;
            const cx = seg.a.x + seg.dx * t;
            const cy = seg.a.y + seg.dy * t;

            for (const side of [-1, 1]) {
                const x = cx + nx * side * (activeMap.trackWidth / 2 + 3);
                const y = cy + ny * side * (activeMap.trackWidth / 2 + 3);
                if (!isVisible(x, y, 80)) continue;

                ctx.fillStyle = count % 2 === 0 ? theme.curbA : theme.curbB;
                ctx.globalAlpha = .85;
                ctx.beginPath();
                ctx.arc(x, y, 5.4, 0, Math.PI * 2);
                ctx.fill();
            }
            count++;
        }
    }
    ctx.restore();
}

function drawStartLine() {
    const gate = checkpointGates[0];
    if (!gate || !isVisible(gate.x, gate.y, 220)) return;

    const tile = 16;
    ctx.save();
    ctx.translate(gate.x, gate.y);
    ctx.rotate(gate.angle + Math.PI / 2);
    ctx.shadowColor = "rgba(255,255,255,.3)";
    ctx.shadowBlur = 9;

    for (let row = -4; row < 4; row++) {
        for (let col = -3; col < 3; col++) {
            ctx.fillStyle = (row + col) % 2 === 0 ? "#f8fafc" : "#050505";
            ctx.fillRect(col * tile, row * tile, tile, tile);
        }
    }
    ctx.restore();
}

function drawRoadArrows() {
    for (let i = 1; i < activeMap.path.length; i += 2) {
        const p = getPointOnPath(i);
        const n = getPointOnPath(i + 1);
        if (!isVisible(p.x, p.y, 120)) continue;
        drawRoadArrow(p.x, p.y, Math.atan2(n.y - p.y, n.x - p.x));
    }
}

function drawRoadArrow(x, y, angle) {
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(angle);
    ctx.globalAlpha = 0.20;
    ctx.fillStyle = "#ffffff";
    ctx.beginPath();
    ctx.moveTo(40, 0);
    ctx.lineTo(-12, -25);
    ctx.lineTo(-3, -7);
    ctx.lineTo(-43, -7);
    ctx.lineTo(-43, 7);
    ctx.lineTo(-3, 7);
    ctx.lineTo(-12, 25);
    ctx.closePath();
    ctx.fill();
    ctx.restore();
}

function drawAsphaltNoise() {
    ctx.save();
    for (const s of asphaltSpeckles) {
        if (!isVisible(s.x, s.y, 10)) continue;
        ctx.globalAlpha = s.a;
        ctx.fillStyle = s.light ? "#ffffff" : "#000000";
        ctx.fillRect(s.x, s.y, s.w, 1);
    }
    ctx.restore();
}

function drawCheckpoints() {
    checkpointGates.forEach((checkpoint, index) => {
        if (!isVisible(checkpoint.x, checkpoint.y, 260)) return;
        const active = index === game.nextCheckpoint;

        ctx.save();
        ctx.translate(checkpoint.x, checkpoint.y);
        ctx.rotate(checkpoint.angle);

        if (active) {
            const pulse = 0.52 + Math.sin(game.frame * 0.08) * 0.18;
            ctx.shadowColor = activeMap.theme.glow;
            ctx.shadowBlur = 28;
            ctx.fillStyle = `rgba(101, 242, 154, ${0.14 + pulse * 0.08})`;
            ctx.strokeStyle = "rgba(101, 242, 154, 0.96)";
        } else {
            ctx.fillStyle = "rgba(255,255,255,.025)";
            ctx.strokeStyle = "rgba(255,255,255,.10)";
        }

        ctx.lineWidth = active ? 3 : 1.5;
        ctx.beginPath();
        ctx.roundRect(-activeMap.trackWidth / 2, -checkpoint.radius / 2, activeMap.trackWidth, checkpoint.radius, 20);
        ctx.fill();
        ctx.stroke();

        if (active) {
            ctx.fillStyle = "#65f29a";
            ctx.font = "900 15px Arial";
            ctx.textAlign = "center";
            ctx.fillText("CHECKPOINT", 0, -checkpoint.radius / 2 - 16);

            ctx.beginPath();
            ctx.moveTo(0, -checkpoint.radius / 2 - 35 + Math.sin(game.frame * .12) * 5);
            ctx.lineTo(-15, -checkpoint.radius / 2 - 58);
            ctx.lineTo(15, -checkpoint.radius / 2 - 58);
            ctx.closePath();
            ctx.fill();
        }
        ctx.restore();
    });
}

function drawTireMarks() {
    ctx.save();
    for (const mark of tireMarks) {
        if (!isVisible((mark.x1 + mark.x2) / 2, (mark.y1 + mark.y2) / 2, 80)) continue;
        const alpha = mark.life / mark.maxLife;
        ctx.strokeStyle = `rgba(4,5,7,${alpha * 0.38})`;
        ctx.lineWidth = 4;
        ctx.lineCap = "round";
        ctx.beginPath();
        ctx.moveTo(mark.x1, mark.y1);
        ctx.lineTo(mark.x2, mark.y2);
        ctx.stroke();
    }
    ctx.restore();
}

function drawBarriers() {
    for (const b of barriers) {
        if (!isVisible(b.x + b.width / 2, b.y + b.height / 2, 160)) continue;
        const gradient = ctx.createLinearGradient(b.x, b.y, b.x + b.width, b.y + b.height);
        gradient.addColorStop(0, "#ffd166");
        gradient.addColorStop(.5, "#f97316");
        gradient.addColorStop(1, "#dc2626");

        ctx.save();
        ctx.shadowColor = "rgba(0,0,0,.32)";
        ctx.shadowBlur = 13;
        ctx.shadowOffsetY = 7;
        ctx.fillStyle = gradient;
        ctx.strokeStyle = "rgba(0,0,0,.45)";
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.roundRect(b.x, b.y, b.width, b.height, 11);
        ctx.fill();
        ctx.stroke();

        ctx.shadowBlur = 0;
        ctx.shadowOffsetY = 0;
        ctx.strokeStyle = "rgba(0,0,0,.35)";
        ctx.lineWidth = 6;
        ctx.beginPath();
        ctx.moveTo(b.x + 15, b.y + b.height - 9);
        ctx.lineTo(b.x + b.width - 12, b.y + 9);
        ctx.stroke();
        ctx.restore();
    }
}

function drawCones() {
    for (const cone of cones) {
        if (!isVisible(cone.x, cone.y, 90)) continue;
        ctx.save();
        ctx.translate(cone.x, cone.y);
        if (cone.hit) ctx.rotate(game.frame * cone.spin);

        ctx.shadowColor = "rgba(0,0,0,.28)";
        ctx.shadowBlur = 9;
        ctx.shadowOffsetY = 5;
        ctx.fillStyle = "#ff8c42";
        ctx.strokeStyle = "rgba(0,0,0,.35)";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(0, -14);
        ctx.lineTo(13, 13);
        ctx.lineTo(-13, 13);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();

        ctx.shadowBlur = 0;
        ctx.fillStyle = "#f7f7f7";
        ctx.fillRect(-8, 3, 16, 4);
        ctx.restore();
    }
}

function drawParticles() {
    ctx.save();
    for (const p of particles) {
        if (!isVisible(p.x, p.y, 100)) continue;
        const alpha = p.life / p.maxLife;
        ctx.globalAlpha = alpha;
        if (p.type === "smoke") {
            ctx.fillStyle = p.color;
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
            ctx.fill();
        } else {
            ctx.fillStyle = p.color;
            ctx.shadowColor = p.color;
            ctx.shadowBlur = p.type === "flame" ? 16 : 10;
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
            ctx.fill();
            ctx.shadowBlur = 0;
        }
    }
    ctx.restore();
}

function drawCar() {
    ctx.save();
    ctx.translate(car.x, car.y);
    ctx.rotate(car.angle + Math.PI / 2);

    drawHeadlights();

    ctx.shadowColor = "rgba(0,0,0,.62)";
    ctx.shadowBlur = 17;
    ctx.shadowOffsetY = 9;

    const body = ctx.createLinearGradient(0, -car.height / 2, 0, car.height / 2);
    body.addColorStop(0, lighten(car.color, 0.22));
    body.addColorStop(.42, car.color);
    body.addColorStop(1, darken(car.color, 0.28));

    ctx.fillStyle = body;
    ctx.beginPath();
    ctx.roundRect(-car.width / 2, -car.height / 2, car.width, car.height, 12);
    ctx.fill();

    ctx.shadowBlur = 0;
    ctx.shadowOffsetY = 0;

    ctx.fillStyle = "#111827";
    ctx.beginPath();
    ctx.roundRect(-car.width / 2 + 5, -car.height / 2 + 13, car.width - 10, 16, 5);
    ctx.fill();

    ctx.fillStyle = "rgba(255,255,255,.28)";
    ctx.beginPath();
    ctx.roundRect(-car.width / 2 + 6, car.height / 2 - 23, car.width - 12, 13, 5);
    ctx.fill();

    ctx.fillStyle = "rgba(255,255,255,.48)";
    ctx.fillRect(-2, -car.height / 2 + 4, 4, car.height - 8);

    ctx.fillStyle = "#ffd166";
    ctx.beginPath();
    ctx.moveTo(0, -car.height / 2 - 8);
    ctx.lineTo(-8, -car.height / 2 + 8);
    ctx.lineTo(8, -car.height / 2 + 8);
    ctx.closePath();
    ctx.fill();

    drawWheels();
    drawTailLights();
    ctx.restore();
}

function drawHeadlights() {
    const speed = Math.hypot(car.vx, car.vy);
    ctx.save();
    ctx.globalAlpha = 0.10 + clamp(speed / 12, 0, 1) * 0.15;
    ctx.fillStyle = "#fff2b0";
    ctx.beginPath();
    ctx.moveTo(-12, -car.height / 2);
    ctx.lineTo(-82, -car.height / 2 - 112);
    ctx.lineTo(-4, -car.height / 2 - 22);
    ctx.closePath();
    ctx.fill();

    ctx.beginPath();
    ctx.moveTo(12, -car.height / 2);
    ctx.lineTo(82, -car.height / 2 - 112);
    ctx.lineTo(4, -car.height / 2 - 22);
    ctx.closePath();
    ctx.fill();
    ctx.restore();
}

function drawTailLights() {
    ctx.save();
    ctx.fillStyle = "#ff2f45";
    ctx.shadowColor = "#ff2f45";
    ctx.shadowBlur = 10;
    ctx.fillRect(-13, car.height / 2 - 7, 7, 4);
    ctx.fillRect(6, car.height / 2 - 7, 7, 4);
    ctx.restore();
}

function drawWheels() {
    ctx.fillStyle = "#05070d";
    ctx.beginPath(); ctx.roundRect(-car.width / 2 - 6, -car.height / 2 + 8, 8, 17, 4); ctx.fill();
    ctx.beginPath(); ctx.roundRect(car.width / 2 - 2, -car.height / 2 + 8, 8, 17, 4); ctx.fill();
    ctx.beginPath(); ctx.roundRect(-car.width / 2 - 6, car.height / 2 - 25, 8, 17, 4); ctx.fill();
    ctx.beginPath(); ctx.roundRect(car.width / 2 - 2, car.height / 2 - 25, 8, 17, 4); ctx.fill();
}

function drawFloatingTexts() {
    ctx.save();
    ctx.textAlign = "center";
    ctx.font = "900 22px Arial";
    for (const t of floatingTexts) {
        const alpha = t.life / t.maxLife;
        ctx.globalAlpha = alpha;
        ctx.fillStyle = t.color;
        ctx.shadowColor = t.color;
        ctx.shadowBlur = 14;
        ctx.fillText(t.text, t.x, t.y);
    }
    ctx.restore();
}

function drawScreenVignette() {
    const gradient = ctx.createRadialGradient(canvas.width / 2, canvas.height / 2, 160, canvas.width / 2, canvas.height / 2, 720);
    gradient.addColorStop(0, "rgba(0,0,0,0)");
    gradient.addColorStop(1, "rgba(0,0,0,.34)");
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
}

function drawMinimap() {
    const w = 210, h = 130;
    const x = canvas.width - w - 22;
    const y = canvas.height - h - 22;
    const scale = Math.min((w - 20) / activeMap.world.width, (h - 20) / activeMap.world.height);
    const ox = x + 10;
    const oy = y + 10;

    ctx.save();
    ctx.fillStyle = "rgba(5,9,17,.72)";
    ctx.strokeStyle = "rgba(255,255,255,.16)";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.roundRect(x, y, w, h, 18);
    ctx.fill();
    ctx.stroke();

    ctx.save();
    ctx.translate(ox, oy);
    ctx.scale(scale, scale);

    ctx.fillStyle = "rgba(255,255,255,.055)";
    ctx.fillRect(0, 0, activeMap.world.width, activeMap.world.height);

    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    ctx.strokeStyle = "rgba(255,255,255,.30)";
    ctx.lineWidth = activeMap.trackWidth;
    ctx.beginPath();
    activeMap.path.forEach(([px, py], index) => index === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py));
    ctx.closePath();
    ctx.stroke();

    ctx.fillStyle = "#65f29a";
    const cp = checkpointGates[game.nextCheckpoint];
    if (cp) {
        ctx.beginPath();
        ctx.arc(cp.x, cp.y, 55, 0, Math.PI * 2);
        ctx.fill();
    }

    ctx.fillStyle = car.color;
    ctx.beginPath();
    ctx.arc(car.x, car.y, 38, 0, Math.PI * 2);
    ctx.fill();

    ctx.strokeStyle = "rgba(56,189,248,.9)";
    ctx.lineWidth = 10;
    ctx.strokeRect(game.camera.x, game.camera.y, canvas.width, canvas.height);

    ctx.restore();

    ctx.fillStyle = "#dbeafe";
    ctx.font = "900 11px Arial";
    ctx.textAlign = "left";
    ctx.fillText(activeMap.layoutName, x + 13, y + h - 10);
    ctx.restore();
}

function drawCompassArrow() {
    const cp = checkpointGates[game.nextCheckpoint];
    if (!cp || game.state !== "running") return;

    const screenX = cp.x - game.camera.x;
    const screenY = cp.y - game.camera.y;

    if (screenX > 80 && screenX < canvas.width - 80 && screenY > 80 && screenY < canvas.height - 80) return;

    const dx = cp.x - car.x;
    const dy = cp.y - car.y;
    const angle = Math.atan2(dy, dx);
    const cx = canvas.width / 2 + Math.cos(angle) * 235;
    const cy = canvas.height / 2 + Math.sin(angle) * 150;

    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(angle);
    ctx.fillStyle = "#65f29a";
    ctx.shadowColor = "#65f29a";
    ctx.shadowBlur = 20;
    ctx.beginPath();
    ctx.moveTo(22, 0);
    ctx.lineTo(-15, -13);
    ctx.lineTo(-9, 0);
    ctx.lineTo(-15, 13);
    ctx.closePath();
    ctx.fill();
    ctx.restore();
}

function updateUI() {
    const speed = Math.round(Math.hypot(car.vx, car.vy) * 18);
    ui.map.textContent = activeMap.name;
    ui.lap.textContent = game.mode === "zen" ? "∞" : `${Math.min(game.currentLap, game.totalLaps)} / ${game.totalLaps}`;

    if (game.mode === "checkpointRush" && game.state === "running") {
        const left = Math.max(0, modes.checkpointRush.countdown - game.elapsed);
        ui.time.textContent = formatTime(left);
    } else {
        ui.time.textContent = formatTime(game.elapsed);
    }

    ui.speed.textContent = `${speed} km/h`;
    ui.drift.textContent = Math.floor(game.driftScore).toLocaleString("de-DE");
    ui.nitro.style.transform = `scaleX(${clamp(car.nitro / car.maxNitro, 0, 1)})`;

    const profile = getProfile();
    const currentGrip = car.lastOnRoad ? profile.grip : profile.grassGrip;
    ui.grip.style.transform = `scaleX(${clamp(currentGrip / 0.13, 0.05, 1)})`;
}

function updateBestDisplay() {
    const key = getBestKey();
    const value = localStorage.getItem(key);
    if (!value || game.mode === "zen") {
        ui.best.textContent = game.mode === "zen" ? "Free" : "--:--.---";
        return;
    }
    ui.best.textContent = game.mode === "checkpointRush" ? `${value} CP` : formatTime(Number(value));
}

function getBestKey() {
    return `dcp-best-v2-${game.mapId}-${game.mode}-${game.difficulty}`;
}

function isOnRoad(x, y) {
    return distanceToTrack(x, y).distance <= activeMap.trackWidth / 2;
}

function distanceToTrack(x, y) {
    let best = { distance: Infinity, t: 0, segment: null, x: 0, y: 0 };

    for (const seg of pathSegments) {
        const rawT = ((x - seg.a.x) * seg.dx + (y - seg.a.y) * seg.dy) / (seg.lengthSq || 1);
        const t = clamp(rawT, 0, 1);
        const px = seg.a.x + seg.dx * t;
        const py = seg.a.y + seg.dy * t;
        const distance = Math.hypot(x - px, y - py);

        if (distance < best.distance) {
            best = { distance, t, segment: seg, x: px, y: py };
        }
    }

    return best;
}

function isVisible(x, y, margin = 0) {
    return (
        x > game.camera.x - margin &&
        x < game.camera.x + canvas.width + margin &&
        y > game.camera.y - margin &&
        y < game.camera.y + canvas.height + margin
    );
}

function getCarBox() {
    return {
        x: car.x - car.width / 2,
        y: car.y - car.height / 2,
        width: car.width,
        height: car.height
    };
}

function rectsCollide(a, b) {
    return a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y;
}

function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
}

function formatTime(milliseconds) {
    const totalMs = Math.max(0, Math.floor(milliseconds));
    const minutes = Math.floor(totalMs / 60000);
    const seconds = Math.floor((totalMs % 60000) / 1000);
    const ms = totalMs % 1000;
    return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}.${String(ms).padStart(3, "0")}`;
}

function hexToRgb(hex) {
    const normalized = hex.replace("#", "");
    const bigint = parseInt(normalized.length === 3 ? normalized.split("").map(c => c + c).join("") : normalized, 16);
    return { r: (bigint >> 16) & 255, g: (bigint >> 8) & 255, b: bigint & 255 };
}

function rgbToHex(r, g, b) {
    return "#" + [r, g, b].map(v => Math.round(clamp(v, 0, 255)).toString(16).padStart(2, "0")).join("");
}

function lighten(hex, amount) {
    const c = hexToRgb(hex);
    return rgbToHex(c.r + (255 - c.r) * amount, c.g + (255 - c.g) * amount, c.b + (255 - c.b) * amount);
}

function darken(hex, amount) {
    const c = hexToRgb(hex);
    return rgbToHex(c.r * (1 - amount), c.g * (1 - amount), c.b * (1 - amount));
}

syncSelects();
resetGame();
requestAnimationFrame(loop);

})();
