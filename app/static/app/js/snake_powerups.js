(function () {
    "use strict";

    const root = document.querySelector(".snake-page");
    const canvas = document.getElementById("snakeCanvas");
    if (!root || !canvas) {
        return;
    }

    const ctx = canvas.getContext("2d");
    const bestKey = root.dataset.bestKey || "mytools-snake-powerups-best-v1";

    const ui = {
        score: document.getElementById("snakeScore"),
        best: document.getElementById("snakeBest"),
        length: document.getElementById("snakeLength"),
        combo: document.getElementById("snakeCombo"),
        apples: document.getElementById("snakeApples"),
        powerCount: document.getElementById("snakePowerCount"),
        shieldCount: document.getElementById("snakeShieldCount"),
        runState: document.getElementById("snakeRunState"),
        activeSummary: document.getElementById("snakeActiveSummary"),
        powerGrid: document.getElementById("snakePowerGrid"),
        overlay: document.getElementById("snakeOverlay"),
        overlayKicker: document.getElementById("snakeOverlayKicker"),
        overlayTitle: document.getElementById("snakeOverlayTitle"),
        overlayText: document.getElementById("snakeOverlayText"),
        startButton: document.getElementById("snakeStartButton"),
        menuResetButton: document.getElementById("snakeMenuResetButton"),
        resetButton: document.getElementById("snakeResetButton"),
        pauseButton: document.getElementById("snakePauseButton"),
        soundButton: document.getElementById("snakeSoundButton"),
        modeSelect: document.getElementById("snakeModeSelect"),
        speedSelect: document.getElementById("snakeSpeedSelect"),
        toast: document.getElementById("snakeToast")
    };

    const modes = {
        neon: {
            label: "Neon Run",
            board: 24,
            tick: 108,
            walls: false,
            obstacles: 6,
            powerChance: 0.34
        },
        classic: {
            label: "Classic Walls",
            board: 22,
            tick: 124,
            walls: true,
            obstacles: 0,
            powerChance: 0.25
        },
        chaos: {
            label: "Power Chaos",
            board: 26,
            tick: 96,
            walls: true,
            obstacles: 18,
            powerChance: 0.52
        }
    };

    const speeds = {
        normal: { label: "Normal", multiplier: 1 },
        fast: { label: "Schnell", multiplier: 0.86 },
        wild: { label: "Wild", multiplier: 0.72 }
    };

    const powerups = [
        {
            id: "double",
            name: "Doppelpunkte",
            tag: "2x",
            icon: "fa-solid fa-star",
            color: "#ffd166",
            duration: 10000
        },
        {
            id: "magnet",
            name: "Magnet",
            tag: "MAG",
            icon: "fa-solid fa-magnet",
            color: "#38bdf8",
            duration: 9000
        },
        {
            id: "slow",
            name: "Slow-Motion",
            tag: "SLO",
            icon: "fa-solid fa-hourglass-half",
            color: "#a78bfa",
            duration: 8000
        },
        {
            id: "turbo",
            name: "Turbo",
            tag: "GO",
            icon: "fa-solid fa-bolt",
            color: "#fb7185",
            duration: 7000
        },
        {
            id: "ghost",
            name: "Phantom",
            tag: "GHO",
            icon: "fa-solid fa-wand-magic-sparkles",
            color: "#42f2a1",
            duration: 6500
        },
        {
            id: "shield",
            name: "Schild",
            tag: "SH",
            icon: "fa-solid fa-shield-halved",
            color: "#f97316",
            duration: 0
        },
        {
            id: "shrink",
            name: "Kuerzen",
            tag: "-5",
            icon: "fa-solid fa-compress",
            color: "#f8fafc",
            duration: 0
        }
    ];

    const powerById = Object.fromEntries(powerups.map((power) => [power.id, power]));
    const directions = {
        up: { x: 0, y: -1 },
        down: { x: 0, y: 1 },
        left: { x: -1, y: 0 },
        right: { x: 1, y: 0 }
    };

    let bestScore = loadBestScore();
    let state = createState();
    let lastFrame = performance.now();
    let accumulator = 0;
    let audioContext = null;
    let soundEnabled = true;
    let toastTimeout = null;
    let lastPowerGridSignature = "";

    function loadBestScore() {
        try {
            return Math.max(0, Number(localStorage.getItem(bestKey) || 0));
        } catch (_error) {
            return 0;
        }
    }

    function saveBestScore(score) {
        bestScore = Math.max(bestScore, score);
        try {
            localStorage.setItem(bestKey, String(bestScore));
        } catch (_error) {
            return;
        }
    }

    function selectedMode() {
        return modes[ui.modeSelect?.value] || modes.neon;
    }

    function selectedSpeed() {
        return speeds[ui.speedSelect?.value] || speeds.normal;
    }

    function createState() {
        const mode = selectedMode();
        const center = Math.floor(mode.board / 2);
        const snake = [
            { x: center + 1, y: center },
            { x: center, y: center },
            { x: center - 1, y: center }
        ];
        const created = {
            phase: "idle",
            mode,
            speed: selectedSpeed(),
            board: mode.board,
            snake,
            direction: directions.right,
            nextDirection: directions.right,
            food: null,
            powerup: null,
            obstacles: [],
            particles: [],
            score: 0,
            apples: 0,
            powers: 0,
            combo: 1,
            lastAppleAt: 0,
            shield: 0,
            effects: {},
            nextPowerAt: performance.now() + 4600
        };
        created.obstacles = buildObstacles(created);
        created.food = randomFreeCell(created);
        return created;
    }

    function buildObstacles(game) {
        const obstacles = [];
        const blockedRadius = 4;
        let guard = 0;
        while (obstacles.length < game.mode.obstacles && guard < 900) {
            guard += 1;
            const cell = {
                x: randomInt(1, game.board - 2),
                y: randomInt(1, game.board - 2)
            };
            const nearStart = Math.abs(cell.x - game.snake[0].x) + Math.abs(cell.y - game.snake[0].y) < blockedRadius;
            if (!nearStart && !occupies(game.snake, cell) && !occupies(obstacles, cell)) {
                obstacles.push(cell);
            }
        }
        return obstacles;
    }

    function randomInt(min, max) {
        return Math.floor(Math.random() * (max - min + 1)) + min;
    }

    function sameCell(a, b) {
        return a && b && a.x === b.x && a.y === b.y;
    }

    function occupies(list, cell) {
        return list.some((item) => sameCell(item, cell));
    }

    function isBlocked(game, cell, includePowerup) {
        return (
            occupies(game.snake, cell)
            || occupies(game.obstacles, cell)
            || sameCell(game.food, cell)
            || (includePowerup && game.powerup && sameCell(game.powerup, cell))
        );
    }

    function randomFreeCell(game) {
        let guard = 0;
        while (guard < 1600) {
            guard += 1;
            const cell = {
                x: randomInt(0, game.board - 1),
                y: randomInt(0, game.board - 1)
            };
            if (!isBlocked(game, cell, true)) {
                return cell;
            }
        }
        return { x: 0, y: 0 };
    }

    function setPhase(phase) {
        state.phase = phase;
        updateOverlay();
        updatePauseIcon();
        updateUi();
    }

    function startGame() {
        if (state.phase === "paused") {
            setPhase("playing");
            beep(660, 0.06, "triangle");
            return;
        }
        state = createState();
        state.phase = "playing";
        accumulator = 0;
        ui.overlay.hidden = true;
        showToast("Run gestartet", "start");
        beep(620, 0.08, "square");
        updatePauseIcon();
        updateUi();
    }

    function resetToMenu() {
        state = createState();
        accumulator = 0;
        updateOverlay("idle");
        updatePauseIcon();
        updateUi();
    }

    function pauseGame() {
        if (state.phase === "playing") {
            setPhase("paused");
            beep(280, 0.05, "sine");
        } else if (state.phase === "paused") {
            startGame();
        } else if (state.phase === "idle" || state.phase === "over") {
            startGame();
        }
    }

    function gameOver(reason) {
        state.phase = "over";
        saveBestScore(state.score);
        burst(state.snake[0], "#fb7185", 28);
        showToast("Run beendet", "danger");
        beep(130, 0.16, "sawtooth");
        updateOverlay(reason || "crash");
        updateUi();
        updatePauseIcon();
    }

    function updateOverlay(reason) {
        if (!ui.overlay) {
            return;
        }
        if (state.phase === "playing") {
            ui.overlay.hidden = true;
            return;
        }

        ui.overlay.hidden = false;
        if (state.phase === "paused") {
            ui.overlayKicker.textContent = "Pause";
            ui.overlayTitle.textContent = "Pausiert";
            ui.overlayText.textContent = "Dein Run bleibt eingefroren.";
            ui.startButton.innerHTML = '<i class="fa-solid fa-play"></i> Weiter';
            return;
        }
        if (state.phase === "over") {
            ui.overlayKicker.textContent = "Game Over";
            ui.overlayTitle.textContent = `${state.score} Punkte`;
            ui.overlayText.textContent = reason === "wall"
                ? "Die Wand war schneller."
                : reason === "self"
                    ? "Die Snake hat sich selbst erwischt."
                    : "Das Board hat dich gestoppt.";
            ui.startButton.innerHTML = '<i class="fa-solid fa-rotate-right"></i> Nochmal';
            return;
        }
        ui.overlayKicker.textContent = "Bereit";
        ui.overlayTitle.textContent = "Snake Powerups";
        ui.overlayText.textContent = "Sammle Energie, stapel Combos und nutze Powerups, bevor das Board zu eng wird.";
        ui.startButton.innerHTML = '<i class="fa-solid fa-play"></i> Start';
    }

    function updatePauseIcon() {
        if (!ui.pauseButton) {
            return;
        }
        const icon = ui.pauseButton.querySelector("i");
        if (!icon) {
            return;
        }
        icon.className = state.phase === "playing" ? "fa-solid fa-pause" : "fa-solid fa-play";
    }

    function queueDirection(directionName) {
        const direction = directions[directionName];
        if (!direction) {
            return;
        }
        const opposite = direction.x + state.direction.x === 0 && direction.y + state.direction.y === 0;
        if (!opposite) {
            state.nextDirection = direction;
        }
        if (state.phase === "idle" || state.phase === "over") {
            startGame();
        }
    }

    function currentTickInterval() {
        let tick = state.mode.tick * state.speed.multiplier;
        if (isEffectActive("slow")) {
            tick += 58;
        }
        if (isEffectActive("turbo")) {
            tick *= 0.64;
        }
        return Math.max(42, tick);
    }

    function tick(now) {
        if (state.phase !== "playing") {
            return;
        }

        cleanEffects(now);
        state.direction = state.nextDirection;

        let head = {
            x: state.snake[0].x + state.direction.x,
            y: state.snake[0].y + state.direction.y
        };

        if (!state.mode.walls) {
            head = wrapCell(head, state.board);
        }

        const collision = collisionType(head);
        if (collision) {
            head = resolveCollision(head, collision);
            if (!head) {
                gameOver(collision);
                return;
            }
        }

        state.snake.unshift(head);

        const ateFood = sameCell(head, state.food) || (isEffectActive("magnet") && manhattan(head, state.food) <= 2);
        if (ateFood) {
            collectFood(now);
        } else {
            state.snake.pop();
        }

        if (state.powerup && sameCell(head, state.powerup.cell)) {
            collectPowerup(state.powerup.type, now);
            state.powerup = null;
        }

        if (state.powerup && state.powerup.expiresAt < now) {
            state.powerup = null;
        }

        if (!state.powerup && now >= state.nextPowerAt) {
            spawnPowerup(now);
        }
    }

    function wrapCell(cell, board) {
        return {
            x: (cell.x + board) % board,
            y: (cell.y + board) % board
        };
    }

    function collisionType(cell) {
        const outside = cell.x < 0 || cell.y < 0 || cell.x >= state.board || cell.y >= state.board;
        if (outside) {
            return "wall";
        }
        if (occupies(state.obstacles, cell)) {
            return "obstacle";
        }
        if (!isEffectActive("ghost") && occupies(state.snake, cell)) {
            return "self";
        }
        return "";
    }

    function resolveCollision(cell, type) {
        if (state.shield <= 0) {
            return null;
        }

        state.shield -= 1;
        state.effects.ghost = performance.now() + 2200;
        showToast("Schild verbraucht", "shield");
        beep(420, 0.08, "triangle");

        if (type === "wall") {
            return wrapCell(cell, state.board);
        }

        const safe = safeNeighbor();
        return safe || randomFreeCell(state);
    }

    function safeNeighbor() {
        const head = state.snake[0];
        const candidates = Object.values(directions).map((direction) => ({
            x: head.x + direction.x,
            y: head.y + direction.y
        }));
        return candidates.find((cell) => !collisionType(cell));
    }

    function manhattan(a, b) {
        return Math.abs(a.x - b.x) + Math.abs(a.y - b.y);
    }

    function collectFood(now) {
        const keptCombo = now - state.lastAppleAt < 4700;
        state.combo = keptCombo ? Math.min(5, state.combo + 0.5) : 1;
        state.lastAppleAt = now;
        state.apples += 1;

        const multiplier = state.combo * (isEffectActive("double") ? 2 : 1) * (isEffectActive("turbo") ? 1.25 : 1);
        const points = Math.round(10 * multiplier);
        state.score += points;
        state.food = randomFreeCell(state);

        burst(state.snake[0], "#42f2a1", 18);
        showToast(`+${points} Punkte`, "score");
        beep(720 + Math.min(360, state.combo * 70), 0.055, "triangle");

        if (!state.powerup && (state.apples % 4 === 0 || Math.random() < state.mode.powerChance)) {
            spawnPowerup(now, true);
        }
    }

    function spawnPowerup(now, force) {
        if (!force && Math.random() > state.mode.powerChance) {
            state.nextPowerAt = now + randomInt(5200, 8800);
            return;
        }
        const pool = powerups.filter((power) => power.id !== "shrink" || state.snake.length > 7);
        const type = pool[randomInt(0, pool.length - 1)].id;
        state.powerup = {
            type,
            cell: randomFreeCell(state),
            createdAt: now,
            expiresAt: now + 9000
        };
        state.nextPowerAt = now + randomInt(7600, 11800);
    }

    function collectPowerup(type, now) {
        const power = powerById[type];
        if (!power) {
            return;
        }
        state.powers += 1;
        state.score += 18;
        burst(state.snake[0], power.color, 26);
        showToast(power.name, type);
        beep(500 + state.powers * 24, 0.07, "square");

        if (type === "shield") {
            state.shield = Math.min(3, state.shield + 1);
        } else if (type === "shrink") {
            const target = Math.max(3, state.snake.length - 5);
            state.snake = state.snake.slice(0, target);
            state.score += 25;
        } else {
            state.effects[type] = now + power.duration;
        }
    }

    function cleanEffects(now) {
        Object.entries(state.effects).forEach(([key, expiresAt]) => {
            if (expiresAt <= now) {
                delete state.effects[key];
            }
        });
        if (state.lastAppleAt && now - state.lastAppleAt > 5200) {
            state.combo = 1;
        }
    }

    function isEffectActive(key) {
        return Number(state.effects[key] || 0) > performance.now();
    }

    function burst(cell, color, count) {
        const size = canvas.width / state.board;
        const center = {
            x: (cell.x + 0.5) * size,
            y: (cell.y + 0.5) * size
        };
        for (let index = 0; index < count; index += 1) {
            const angle = Math.random() * Math.PI * 2;
            const speed = 50 + Math.random() * 130;
            state.particles.push({
                x: center.x,
                y: center.y,
                vx: Math.cos(angle) * speed,
                vy: Math.sin(angle) * speed,
                life: 450 + Math.random() * 380,
                age: 0,
                size: 2 + Math.random() * 4,
                color
            });
        }
    }

    function updateParticles(delta) {
        state.particles = state.particles.filter((particle) => {
            particle.age += delta;
            particle.x += particle.vx * (delta / 1000);
            particle.y += particle.vy * (delta / 1000);
            particle.vx *= 0.985;
            particle.vy *= 0.985;
            return particle.age < particle.life;
        });
    }

    function draw(now) {
        const width = canvas.width;
        const height = canvas.height;
        const cell = width / state.board;

        ctx.clearRect(0, 0, width, height);
        drawBoard(width, height, cell, now);
        drawObstacles(cell);
        drawFood(cell, now);
        drawPowerup(cell, now);
        drawSnake(cell);
        drawParticles();
    }

    function drawBoard(width, height, cell, now) {
        const pulse = (Math.sin(now / 700) + 1) / 2;
        const background = ctx.createLinearGradient(0, 0, width, height);
        background.addColorStop(0, "#07111f");
        background.addColorStop(0.52, "#0b1727");
        background.addColorStop(1, "#10101f");
        ctx.fillStyle = background;
        ctx.fillRect(0, 0, width, height);

        ctx.save();
        ctx.globalAlpha = 0.11 + pulse * 0.03;
        ctx.strokeStyle = "#7dd3fc";
        ctx.lineWidth = 1;
        for (let index = 0; index <= state.board; index += 1) {
            const position = index * cell;
            ctx.beginPath();
            ctx.moveTo(position, 0);
            ctx.lineTo(position, height);
            ctx.stroke();
            ctx.beginPath();
            ctx.moveTo(0, position);
            ctx.lineTo(width, position);
            ctx.stroke();
        }
        ctx.restore();

        if (state.mode.walls) {
            ctx.save();
            ctx.lineWidth = Math.max(5, cell * 0.15);
            ctx.strokeStyle = "#fb7185";
            ctx.shadowColor = "#fb7185";
            ctx.shadowBlur = 18;
            ctx.strokeRect(2, 2, width - 4, height - 4);
            ctx.restore();
        }
    }

    function drawObstacles(cell) {
        state.obstacles.forEach((obstacle, index) => {
            const x = obstacle.x * cell + cell * 0.13;
            const y = obstacle.y * cell + cell * 0.13;
            drawRoundRect(x, y, cell * 0.74, cell * 0.74, cell * 0.18, "#334155", "#64748b");
            ctx.save();
            ctx.globalAlpha = 0.22;
            ctx.fillStyle = index % 2 ? "#38bdf8" : "#fb7185";
            ctx.fillRect(x + cell * 0.18, y + cell * 0.2, cell * 0.38, cell * 0.08);
            ctx.restore();
        });
    }

    function drawFood(cell, now) {
        if (!state.food) {
            return;
        }
        const x = (state.food.x + 0.5) * cell;
        const y = (state.food.y + 0.5) * cell;
        const radius = cell * (0.26 + Math.sin(now / 180) * 0.035);
        ctx.save();
        ctx.shadowColor = "#42f2a1";
        ctx.shadowBlur = 18;
        ctx.fillStyle = "#42f2a1";
        ctx.beginPath();
        ctx.arc(x, y, radius, 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowBlur = 0;
        ctx.fillStyle = "#052e1d";
        ctx.beginPath();
        ctx.arc(x + radius * 0.22, y - radius * 0.2, radius * 0.18, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
    }

    function drawPowerup(cell, now) {
        if (!state.powerup) {
            return;
        }
        const power = powerById[state.powerup.type];
        const x = (state.powerup.cell.x + 0.5) * cell;
        const y = (state.powerup.cell.y + 0.5) * cell;
        const pulse = 1 + Math.sin(now / 150) * 0.08;

        ctx.save();
        ctx.translate(x, y);
        ctx.scale(pulse, pulse);
        ctx.shadowColor = power.color;
        ctx.shadowBlur = 22;
        ctx.fillStyle = power.color;
        ctx.beginPath();
        ctx.arc(0, 0, cell * 0.34, 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowBlur = 0;
        ctx.fillStyle = "#06111d";
        ctx.font = `900 ${Math.max(9, cell * 0.23)}px Arial, sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(power.tag, 0, 1);
        ctx.restore();
    }

    function drawSnake(cell) {
        const ghost = isEffectActive("ghost");
        state.snake.forEach((segment, index) => {
            const progress = index / Math.max(1, state.snake.length - 1);
            const x = segment.x * cell + cell * 0.08;
            const y = segment.y * cell + cell * 0.08;
            const size = cell * 0.84;
            const color = index === 0
                ? (ghost ? "#c4b5fd" : "#42f2a1")
                : blendSnakeColor(progress, ghost);
            drawRoundRect(x, y, size, size, cell * 0.22, color, "rgba(255,255,255,0.2)");

            if (index === 0) {
                drawEyes(segment, cell);
            }
        });
    }

    function blendSnakeColor(progress, ghost) {
        if (ghost) {
            return progress < 0.5 ? "#a78bfa" : "#38bdf8";
        }
        if (progress < 0.45) {
            return "#1ddc89";
        }
        if (progress < 0.75) {
            return "#38bdf8";
        }
        return "#60a5fa";
    }

    function drawEyes(head, cell) {
        const centerX = (head.x + 0.5) * cell;
        const centerY = (head.y + 0.5) * cell;
        const dx = state.direction.x;
        const dy = state.direction.y;
        const sideX = dy * cell * 0.14;
        const sideY = -dx * cell * 0.14;
        const frontX = dx * cell * 0.18;
        const frontY = dy * cell * 0.18;
        ctx.save();
        ctx.fillStyle = "#03111f";
        [1, -1].forEach((side) => {
            ctx.beginPath();
            ctx.arc(centerX + frontX + sideX * side, centerY + frontY + sideY * side, cell * 0.07, 0, Math.PI * 2);
            ctx.fill();
        });
        ctx.restore();
    }

    function drawParticles() {
        state.particles.forEach((particle) => {
            const alpha = 1 - particle.age / particle.life;
            ctx.save();
            ctx.globalAlpha = alpha;
            ctx.fillStyle = particle.color;
            ctx.beginPath();
            ctx.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2);
            ctx.fill();
            ctx.restore();
        });
    }

    function drawRoundRect(x, y, width, height, radius, fill, stroke) {
        const safeRadius = Math.min(radius, width / 2, height / 2);
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(x + safeRadius, y);
        ctx.lineTo(x + width - safeRadius, y);
        ctx.quadraticCurveTo(x + width, y, x + width, y + safeRadius);
        ctx.lineTo(x + width, y + height - safeRadius);
        ctx.quadraticCurveTo(x + width, y + height, x + width - safeRadius, y + height);
        ctx.lineTo(x + safeRadius, y + height);
        ctx.quadraticCurveTo(x, y + height, x, y + height - safeRadius);
        ctx.lineTo(x, y + safeRadius);
        ctx.quadraticCurveTo(x, y, x + safeRadius, y);
        ctx.closePath();
        ctx.fillStyle = fill;
        ctx.shadowColor = fill;
        ctx.shadowBlur = 9;
        ctx.fill();
        if (stroke) {
            ctx.shadowBlur = 0;
            ctx.strokeStyle = stroke;
            ctx.lineWidth = Math.max(1, width * 0.04);
            ctx.stroke();
        }
        ctx.restore();
    }

    function updateUi() {
        const now = performance.now();
        const activeEffects = powerups.filter((power) => isEffectActive(power.id));
        if (ui.score) ui.score.textContent = String(state.score);
        if (ui.best) ui.best.textContent = String(Math.max(bestScore, state.score));
        if (ui.length) ui.length.textContent = String(state.snake.length);
        if (ui.combo) ui.combo.textContent = `x${state.combo.toFixed(state.combo % 1 ? 1 : 0)}`;
        if (ui.apples) ui.apples.textContent = String(state.apples);
        if (ui.powerCount) ui.powerCount.textContent = String(state.powers);
        if (ui.shieldCount) ui.shieldCount.textContent = String(state.shield);
        if (ui.runState) ui.runState.textContent = phaseLabel();
        if (ui.activeSummary) {
            const names = activeEffects.map((power) => power.name);
            if (state.shield > 0) {
                names.push(`${state.shield} Schild`);
            }
            ui.activeSummary.textContent = names.length ? names.join(" + ") : "Kein Effekt aktiv";
        }
        renderPowerGrid(now);
    }

    function phaseLabel() {
        if (state.phase === "playing") return `${state.mode.label} · ${state.speed.label}`;
        if (state.phase === "paused") return "Pausiert";
        if (state.phase === "over") return "Run beendet";
        return "Warte auf Start";
    }

    function renderPowerGrid(now) {
        if (!ui.powerGrid) {
            return;
        }
        const signature = powerups.map((power) => {
            const remaining = Math.max(0, Math.ceil(((state.effects[power.id] || 0) - now) / 1000));
            return `${power.id}:${remaining}:${power.id === "shield" ? state.shield : 0}`;
        }).join("|");
        if (signature === lastPowerGridSignature) {
            return;
        }
        lastPowerGridSignature = signature;

        ui.powerGrid.innerHTML = powerups.map((power) => {
            const remaining = Math.max(0, Math.ceil(((state.effects[power.id] || 0) - now) / 1000));
            const shieldActive = power.id === "shield" && state.shield > 0;
            const active = remaining > 0 || shieldActive;
            const detail = power.id === "shield"
                ? (state.shield ? `${state.shield} Ladung` : "Blockt Crash")
                : power.id === "shrink"
                    ? "Kuerzt Snake"
                    : (remaining ? `${remaining}s aktiv` : `${Math.round(power.duration / 1000)}s`);
            return `
                <div class="snake-power-card ${active ? "is-active" : ""}" style="--power-color: ${power.color}">
                    <i class="${power.icon}"></i>
                    <span>
                        <strong>${escapeHtml(power.name)}</strong>
                        <small>${escapeHtml(detail)}</small>
                    </span>
                </div>
            `;
        }).join("");
    }

    function escapeHtml(value) {
        return String(value).replace(/[&<>"']/g, (char) => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;"
        }[char]));
    }

    function showToast(message) {
        if (!ui.toast) {
            return;
        }
        ui.toast.textContent = message;
        ui.toast.classList.add("is-visible");
        clearTimeout(toastTimeout);
        toastTimeout = window.setTimeout(() => {
            ui.toast.classList.remove("is-visible");
        }, 1050);
    }

    function ensureAudioContext() {
        if (!soundEnabled) {
            return null;
        }
        if (!audioContext) {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            if (!AudioContext) {
                return null;
            }
            audioContext = new AudioContext();
        }
        if (audioContext.state === "suspended") {
            audioContext.resume();
        }
        return audioContext;
    }

    function beep(frequency, duration, type) {
        const context = ensureAudioContext();
        if (!context) {
            return;
        }
        const oscillator = context.createOscillator();
        const gain = context.createGain();
        oscillator.type = type || "sine";
        oscillator.frequency.value = frequency;
        gain.gain.setValueAtTime(0.0001, context.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.05, context.currentTime + 0.01);
        gain.gain.exponentialRampToValueAtTime(0.0001, context.currentTime + duration);
        oscillator.connect(gain);
        gain.connect(context.destination);
        oscillator.start();
        oscillator.stop(context.currentTime + duration + 0.01);
    }

    function frame(now) {
        const delta = Math.min(48, now - lastFrame);
        lastFrame = now;
        updateParticles(delta);

        if (state.phase === "playing") {
            accumulator += delta;
            const interval = currentTickInterval();
            while (accumulator >= interval) {
                tick(now);
                accumulator -= interval;
            }
        }

        draw(now);
        updateUi();
        requestAnimationFrame(frame);
    }

    function bindEvents() {
        ui.startButton?.addEventListener("click", startGame);
        ui.menuResetButton?.addEventListener("click", resetToMenu);
        ui.resetButton?.addEventListener("click", resetToMenu);
        ui.pauseButton?.addEventListener("click", pauseGame);
        ui.soundButton?.addEventListener("click", () => {
            soundEnabled = !soundEnabled;
            const icon = ui.soundButton.querySelector("i");
            if (icon) {
                icon.className = soundEnabled ? "fa-solid fa-volume-high" : "fa-solid fa-volume-xmark";
            }
        });

        ui.modeSelect?.addEventListener("change", resetToMenu);
        ui.speedSelect?.addEventListener("change", resetToMenu);

        document.querySelectorAll(".snake-touch-controls [data-direction]").forEach((button) => {
            button.addEventListener("pointerdown", (event) => {
                event.preventDefault();
                queueDirection(button.dataset.direction);
            });
        });

        window.addEventListener("keydown", (event) => {
            const key = event.key.toLowerCase();
            const keyMap = {
                arrowup: "up",
                w: "up",
                arrowdown: "down",
                s: "down",
                arrowleft: "left",
                a: "left",
                arrowright: "right",
                d: "right"
            };
            if (keyMap[key]) {
                event.preventDefault();
                queueDirection(keyMap[key]);
                return;
            }
            if (key === "p") {
                event.preventDefault();
                pauseGame();
            }
            if (key === " " || key === "enter") {
                event.preventDefault();
                if (state.phase !== "playing") {
                    startGame();
                }
            }
            if (key === "r") {
                event.preventDefault();
                resetToMenu();
            }
        });

        let touchStart = null;
        canvas.addEventListener("touchstart", (event) => {
            const firstTouch = event.changedTouches[0];
            touchStart = firstTouch ? { x: firstTouch.clientX, y: firstTouch.clientY } : null;
        }, { passive: true });

        canvas.addEventListener("touchend", (event) => {
            if (!touchStart) {
                return;
            }
            const lastTouch = event.changedTouches[0];
            if (!lastTouch) {
                return;
            }
            const dx = lastTouch.clientX - touchStart.x;
            const dy = lastTouch.clientY - touchStart.y;
            if (Math.max(Math.abs(dx), Math.abs(dy)) < 24) {
                return;
            }
            queueDirection(Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? "right" : "left") : (dy > 0 ? "down" : "up"));
            touchStart = null;
        }, { passive: true });
    }

    bindEvents();
    updateOverlay("idle");
    updateUi();
    requestAnimationFrame((now) => {
        lastFrame = now;
        requestAnimationFrame(frame);
    });
}());
