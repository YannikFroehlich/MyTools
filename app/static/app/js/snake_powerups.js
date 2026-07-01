(() => {
    'use strict';

    const root = document.querySelector('.snake-page');
    const canvas = document.getElementById('snakeCanvas');
    if (!root || !canvas) return;

    const ctx = canvas.getContext('2d', { alpha: false, desynchronized: true });
    const text = readText();
    const highscoreKey = root.dataset.highscoresKey || 'mytools-snake-simple-highscores-v1';
    const scoreApiUrl = root.dataset.scoreApi || '';
    const serverHighscores = readServerHighscores();
    const locale = document.documentElement.lang || navigator.language || 'de-DE';

    const ui = {
        score: document.getElementById('snakeScore'),
        bestCurrent: document.getElementById('snakeBestCurrent'),
        length: document.getElementById('snakeLength'),
        fruits: document.getElementById('snakeFruits'),
        currentBestLabel: document.getElementById('snakeCurrentBestLabel'),
        currentBestSettings: document.getElementById('snakeCurrentBestSettings'),
        highscoreList: document.getElementById('snakeHighscoreList'),
        overlay: document.getElementById('snakeOverlay'),
        overlayKicker: document.getElementById('snakeOverlayKicker'),
        overlayTitle: document.getElementById('snakeOverlayTitle'),
        overlayText: document.getElementById('snakeOverlayText'),
        overlayStartButton: document.getElementById('snakeOverlayStartButton'),
        restartButton: document.getElementById('snakeRestartButton'),
        pauseButton: document.getElementById('snakePauseButton'),
        boardSelect: document.getElementById('snakeBoardSelect'),
        speedSelect: document.getElementById('snakeSpeedSelect'),
        fruitCountSelect: document.getElementById('snakeFruitCountSelect'),
        spawnRateSelect: document.getElementById('snakeSpawnRateSelect'),
        wallsSelect: document.getElementById('snakeWallsSelect'),
        settingsHint: document.getElementById('snakeSettingsHint')
    };

    const directionVectors = {
        up: { x: 0, y: -1 },
        down: { x: 0, y: 1 },
        left: { x: -1, y: 0 },
        right: { x: 1, y: 0 }
    };

    const keyDirections = {
        ArrowUp: 'up',
        KeyW: 'up',
        ArrowDown: 'down',
        KeyS: 'down',
        ArrowLeft: 'left',
        KeyA: 'left',
        ArrowRight: 'right',
        KeyD: 'right'
    };

    const inputConfig = {
        maxQueuedTurns: 2,
        turnBoostProgress: 0.82,
        minTurnBoostElapsed: 18
    };

    const speedConfig = {
        relaxed: 150,
        normal: 112,
        fast: 88,
        turbo: 66
    };

    const spawnConfig = {
        slow: 22,
        normal: 12,
        high: 6,
        instant: 0
    };

    let state = createGameState(readSettings(), 'idle');
    let animationFrameId = null;
    let resizeFrameId = null;
    let lastStepAt = 0;
    let lastRenderProgress = 1;
    let touchStart = null;

    function readText() {
        const script = document.getElementById('snakeText');
        if (!script) return {};
        try {
            return JSON.parse(script.textContent || '{}');
        } catch (_error) {
            return {};
        }
    }

    function readServerHighscores() {
        const script = document.getElementById('snakeServerHighscores');
        if (!script) return [];
        try {
            const parsed = JSON.parse(script.textContent || '[]');
            return Array.isArray(parsed) ? parsed.filter(Boolean) : [];
        } catch (_error) {
            return [];
        }
    }

    function t(key, fallback) {
        return text[key] || fallback;
    }

    function optionText(select) {
        const option = select?.selectedOptions?.[0];
        return option ? option.textContent.trim() : '';
    }

    function readSettings() {
        const boardSize = clampNumber(Number(ui.boardSelect?.value || 19), 11, 31);
        const speedKey = ui.speedSelect?.value || 'normal';
        const fruitLimit = clampNumber(Number(ui.fruitCountSelect?.value || 1), 1, 7);
        const spawnKey = ui.spawnRateSelect?.value || 'normal';
        const wallMode = ui.wallsSelect?.value || 'wrap';

        return {
            boardSize,
            speedKey,
            interval: speedConfig[speedKey] || speedConfig.normal,
            fruitLimit,
            spawnKey,
            spawnEvery: spawnConfig[spawnKey] ?? spawnConfig.normal,
            wallMode
        };
    }

    function clampNumber(value, min, max) {
        if (!Number.isFinite(value)) return min;
        return Math.max(min, Math.min(max, Math.round(value)));
    }

    function clampFloat(value, min, max) {
        if (!Number.isFinite(value)) return min;
        return Math.max(min, Math.min(max, value));
    }

    function createGameState(settings, phase = 'running') {
        const middle = Math.floor(settings.boardSize / 2);
        const game = {
            phase,
            settings,
            snake: [
                { x: middle + 1, y: middle },
                { x: middle, y: middle },
                { x: middle - 1, y: middle }
            ],
            previousSnake: [],
            direction: directionVectors.right,
            nextDirection: directionVectors.right,
            turnQueue: [],
            food: [],
            score: 0,
            fruits: 0,
            moves: 0,
            spawnCounter: 0,
            startedAt: Date.now(),
            saved: false,
            gameOverReason: ''
        };

        game.previousSnake = cloneSnake(game.snake);
        spawnFood(game, 1);
        if (settings.spawnEvery === 0) {
            fillFood(game);
        }
        return game;
    }

    function cloneSnake(snake) {
        return snake.map((part) => ({ x: part.x, y: part.y }));
    }

    function settingsKey(settings) {
        return [settings.boardSize, settings.speedKey, settings.fruitLimit, settings.spawnKey, settings.wallMode].join('|');
    }

    function settingsLabel(settings) {
        const sizeLabel = `${settings.boardSize} × ${settings.boardSize}`;
        const speedLabel = optionLabel(ui.speedSelect, settings.speedKey, text.speedLabels);
        const spawnLabel = optionLabel(ui.spawnRateSelect, settings.spawnKey, text.spawnLabels);
        const wallLabel = optionLabel(ui.wallsSelect, settings.wallMode, text.wallLabels);
        const fruitWord = settings.fruitLimit === 1 ? t('fruitSingle', 'Frucht') : t('fruitPlural', 'Früchte');
        return `${sizeLabel} · ${speedLabel} · ${settings.fruitLimit} ${fruitWord} · ${spawnLabel} · ${wallLabel}`;
    }

    function optionLabel(select, key, labels = {}) {
        if (select?.value === key) return optionText(select);
        return labels[key] || key;
    }

    function startGame() {
        clearTimer();
        state = createGameState(readSettings(), 'running');
        hideOverlay();
        updateSettingsDisabled(true);
        updatePauseButton();
        updateUi();
        syncBoardSize();
        render(1);
        scheduleNextTick(true);
    }

    function restartToMenu() {
        clearTimer();
        state = createGameState(readSettings(), 'idle');
        updateSettingsDisabled(false);
        updatePauseButton();
        updateUi();
        syncBoardSize();
        render(1);
        showOverlay(
            t('readyKicker', 'Bereit'),
            'Snake',
            t('readyText', 'Starte ein schlichtes Snake ohne Effekte. Die Lüfter sollten dabei deutlich ruhiger bleiben.')
        );
    }

    function togglePause() {
        if (state.phase === 'idle' || state.phase === 'gameover') {
            startGame();
            return;
        }

        if (state.phase === 'paused') {
            state.phase = 'running';
            state.previousSnake = cloneSnake(state.snake);
            hideOverlay();
            updatePauseButton();
            scheduleNextTick(true);
            return;
        }

        if (state.phase === 'running') {
            state.phase = 'paused';
            clearTimer();
            updatePauseButton();
            render(1);
            showOverlay(
                t('pausedKicker', 'Pausiert'),
                t('pausedTitle', 'Pause'),
                t('pausedText', 'Drücke Fortsetzen oder die Leertaste.')
            );
        }
    }

    function updatePauseButton() {
        const icon = ui.pauseButton?.querySelector('i');
        const label = ui.pauseButton?.querySelector('span');
        if (!icon || !label) return;

        if (state.phase === 'paused') {
            icon.className = 'fa-solid fa-play';
            label.textContent = t('resume', 'Fortsetzen');
            return;
        }

        if (state.phase === 'idle' || state.phase === 'gameover') {
            icon.className = 'fa-solid fa-play';
            label.textContent = t('start', 'Start');
            return;
        }

        icon.className = 'fa-solid fa-pause';
        label.textContent = t('pause', 'Pausieren');
    }

    function updateSettingsDisabled(disabled) {
        [ui.boardSelect, ui.speedSelect, ui.fruitCountSelect, ui.spawnRateSelect, ui.wallsSelect].forEach((select) => {
            if (select) select.disabled = disabled;
        });
        if (ui.settingsHint) {
            ui.settingsHint.textContent = disabled
                ? t('settingsLocked', 'Einstellungen sind während des Runs gesperrt.')
                : t('settingsHint', 'Änderungen gelten ab dem nächsten Start.');
        }
    }

    function scheduleNextTick(resetClock = false) {
        if (state.phase !== 'running') return;
        if (resetClock || !lastStepAt) lastStepAt = performance.now();
        if (!animationFrameId) animationFrameId = window.requestAnimationFrame(animationLoop);
    }

    function animationLoop(now) {
        animationFrameId = null;
        if (state.phase !== 'running') return;

        const elapsed = now - lastStepAt;
        if (elapsed >= state.settings.interval) {
            const steps = Math.min(4, Math.floor(elapsed / state.settings.interval));
            for (let index = 0; index < steps; index += 1) {
                step();
                if (state.phase !== 'running') return;
            }
            lastStepAt += steps * state.settings.interval;
            if (now - lastStepAt > state.settings.interval) lastStepAt = now;
        }

        lastRenderProgress = clampFloat((now - lastStepAt) / state.settings.interval, 0, 1);
        render(lastRenderProgress);
        animationFrameId = window.requestAnimationFrame(animationLoop);
    }

    function clearTimer() {
        if (animationFrameId) {
            window.cancelAnimationFrame(animationFrameId);
            animationFrameId = null;
        }
        lastStepAt = 0;
        lastRenderProgress = 1;
    }

    function step() {
        const previousSnake = cloneSnake(state.snake);
        const queuedDirection = state.turnQueue.shift();
        if (queuedDirection && !isOppositeDirection(queuedDirection, state.direction)) {
            state.direction = queuedDirection;
        }
        state.nextDirection = state.turnQueue[0] || state.direction;

        const head = state.snake[0];
        const next = {
            x: head.x + state.direction.x,
            y: head.y + state.direction.y
        };

        if (state.settings.wallMode === 'wrap') {
            next.x = wrap(next.x, state.settings.boardSize);
            next.y = wrap(next.y, state.settings.boardSize);
        } else if (isOutside(next, state.settings.boardSize)) {
            endGame(t('hitWall', 'Die Snake ist gegen die Wand gelaufen.'));
            return;
        }

        const foodIndex = state.food.findIndex((item) => sameCell(item, next));
        const grows = foodIndex >= 0;
        const bodyForCollision = grows ? state.snake : state.snake.slice(0, -1);
        if (bodyForCollision.some((part) => sameCell(part, next))) {
            endGame(t('hitSnake', 'Die Snake hat sich selbst erwischt.'));
            return;
        }

        state.snake.unshift(next);
        state.previousSnake = previousSnake;
        state.moves += 1;

        if (grows) {
            state.food.splice(foodIndex, 1);
            state.fruits += 1;
            state.score += 10;
        } else {
            state.snake.pop();
        }

        updateFoodSpawns();

        if (freeCells(state).length === 0) {
            endGame(t('boardFull', 'Das Spielfeld ist voll. Stark gespielt!'));
            return;
        }

        updateUi(false);
    }

    function wrap(value, size) {
        if (value < 0) return size - 1;
        if (value >= size) return 0;
        return value;
    }

    function isOutside(cell, size) {
        return cell.x < 0 || cell.y < 0 || cell.x >= size || cell.y >= size;
    }

    function sameCell(a, b) {
        return a.x === b.x && a.y === b.y;
    }

    function updateFoodSpawns() {
        if (state.food.length === 0) {
            spawnFood(state, 1);
        }

        if (state.settings.spawnEvery === 0) {
            fillFood(state);
            return;
        }

        if (state.food.length >= state.settings.fruitLimit) return;
        state.spawnCounter += 1;
        if (state.spawnCounter >= state.settings.spawnEvery) {
            state.spawnCounter = 0;
            spawnFood(state, 1);
        }
    }

    function fillFood(game) {
        while (game.food.length < game.settings.fruitLimit) {
            if (!spawnFood(game, 1)) break;
        }
    }

    function spawnFood(game, amount = 1) {
        let spawned = 0;
        for (let index = 0; index < amount && game.food.length < game.settings.fruitLimit; index += 1) {
            const cell = randomFreeCell(game);
            if (!cell) break;
            game.food.push(cell);
            spawned += 1;
        }
        return spawned > 0;
    }

    function randomFreeCell(game) {
        const cells = freeCells(game);
        if (!cells.length) return null;
        return cells[Math.floor(Math.random() * cells.length)];
    }

    function freeCells(game) {
        const occupied = new Set([
            ...game.snake.map(cellKey),
            ...game.food.map(cellKey)
        ]);
        const cells = [];
        for (let y = 0; y < game.settings.boardSize; y += 1) {
            for (let x = 0; x < game.settings.boardSize; x += 1) {
                const key = `${x}:${y}`;
                if (!occupied.has(key)) cells.push({ x, y });
            }
        }
        return cells;
    }

    function cellKey(cell) {
        return `${cell.x}:${cell.y}`;
    }

    function endGame(reason) {
        state.phase = 'gameover';
        state.gameOverReason = reason;
        clearTimer();
        const saved = saveHighscore();
        updateSettingsDisabled(false);
        updatePauseButton();
        updateUi();
        render(1);
        showOverlay(
            saved ? t('newHighscore', 'Neuer Highscore!') : t('gameOverKicker', 'Game Over'),
            t('gameOverTitle', 'Game Over'),
            `${reason} ${t('scoreSaved', 'Dein Score wurde gespeichert.')}`
        );
    }

    function saveHighscore() {
        if (state.saved || state.score <= 0) return false;
        state.saved = true;

        const records = loadHighscores();
        const key = settingsKey(state.settings);
        const existingIndex = records.findIndex((item) => item.key === key);
        const record = {
            key,
            settings: {
                boardSize: state.settings.boardSize,
                speedKey: state.settings.speedKey,
                fruitLimit: state.settings.fruitLimit,
                spawnKey: state.settings.spawnKey,
                wallMode: state.settings.wallMode
            },
            score: state.score,
            length: state.snake.length,
            fruits: state.fruits,
            moves: state.moves,
            durationSeconds: Math.max(0, Math.round((Date.now() - state.startedAt) / 1000)),
            achievedAt: new Date().toISOString(),
            runs: 1
        };

        let isNewHighscore = false;
        if (existingIndex >= 0) {
            const existing = records[existingIndex];
            record.runs = Number(existing.runs || 0) + 1;
            if (record.score > Number(existing.score || 0) || (record.score === Number(existing.score || 0) && record.length > Number(existing.length || 0))) {
                records[existingIndex] = record;
                isNewHighscore = true;
            } else {
                existing.runs = record.runs;
                records[existingIndex] = existing;
            }
        } else {
            records.push(record);
            isNewHighscore = true;
        }

        saveHighscores(records);
        const savedRecord = records.find((item) => item.key === key) || record;
        void syncHighscoreRecord(savedRecord);
        renderHighscores();
        requestFitSync();
        return isNewHighscore;
    }

    function loadHighscores() {
        try {
            const parsed = JSON.parse(localStorage.getItem(highscoreKey) || '[]');
            return Array.isArray(parsed) ? parsed.filter(Boolean) : [];
        } catch (_error) {
            return [];
        }
    }

    function saveHighscores(records) {
        const cleaned = records
            .map(normalizeHighscoreRecord)
            .filter((record) => record && record.key && Number(record.score) >= 0)
            .sort(compareHighscores)
            .slice(0, 60);
        try {
            localStorage.setItem(highscoreKey, JSON.stringify(cleaned));
        } catch (_error) {
            return;
        }
    }

    function normalizeHighscoreRecord(record) {
        if (!record) return null;
        const settings = normalizeSettings(record.settings || parseSettingsKey(record.key));
        const key = record.key || settingsKey(settings);
        return {
            key,
            settings,
            score: clampNumber(Number(record.score || 0), 0, 999999999),
            length: clampNumber(Number(record.length || 3), 1, 999999),
            fruits: clampNumber(Number(record.fruits || 0), 0, 999999),
            moves: clampNumber(Number(record.moves || 0), 0, 999999),
            durationSeconds: clampNumber(Number(record.durationSeconds || 0), 0, 86400),
            achievedAt: record.achievedAt || new Date().toISOString(),
            runs: clampNumber(Number(record.runs || 1), 1, 999999)
        };
    }

    function normalizeSettings(settings) {
        const parsed = settings || {};
        const speedKey = speedConfig[parsed.speedKey] ? parsed.speedKey : 'normal';
        const spawnKey = Object.prototype.hasOwnProperty.call(spawnConfig, parsed.spawnKey) ? parsed.spawnKey : 'normal';
        const wallMode = parsed.wallMode === 'wall' ? 'wall' : 'wrap';

        return {
            boardSize: clampNumber(Number(parsed.boardSize || 19), 11, 31),
            speedKey,
            interval: speedConfig[speedKey] || speedConfig.normal,
            fruitLimit: clampNumber(Number(parsed.fruitLimit || 1), 1, 7),
            spawnKey,
            spawnEvery: spawnConfig[spawnKey] ?? spawnConfig.normal,
            wallMode
        };
    }

    function mergeHighscores(records) {
        if (!Array.isArray(records) || !records.length) return;
        const merged = loadHighscores();
        records.map(normalizeHighscoreRecord).filter(Boolean).forEach((incoming) => {
            const existingIndex = merged.findIndex((item) => item.key === incoming.key);
            if (existingIndex < 0) {
                merged.push(incoming);
                return;
            }

            const existing = normalizeHighscoreRecord(merged[existingIndex]);
            if (compareHighscores(incoming, existing) < 0) {
                merged[existingIndex] = incoming;
                return;
            }

            existing.runs = Math.max(Number(existing.runs || 1), Number(incoming.runs || 1));
            merged[existingIndex] = existing;
        });
        saveHighscores(merged);
    }

    async function syncHighscoreRecord(record) {
        if (!scoreApiUrl || !record || Number(record.score || 0) <= 0) return;
        try {
            const response = await fetch(scoreApiUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken'),
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify(record)
            });
            if (!response.ok) return;
            const data = await response.json();
            if (data?.highscore) {
                mergeHighscores([data.highscore]);
                renderHighscores();
            }
        } catch (_error) {
            // Local highscores are still kept when the profile sync is unavailable.
        }
    }

    function syncStoredHighscores() {
        if (!scoreApiUrl) return;
        loadHighscores()
            .slice(0, 60)
            .forEach((record, index) => {
                window.setTimeout(() => syncHighscoreRecord(record), index * 80);
            });
    }

    function getCookie(name) {
        const prefix = `${name}=`;
        return document.cookie
            .split(';')
            .map((item) => item.trim())
            .find((item) => item.startsWith(prefix))
            ?.slice(prefix.length) || '';
    }

    function compareHighscores(a, b) {
        return Number(b.score || 0) - Number(a.score || 0)
            || Number(b.length || 0) - Number(a.length || 0)
            || String(b.achievedAt || '').localeCompare(String(a.achievedAt || ''));
    }

    function bestForSettings(settings) {
        const key = settingsKey(settings);
        return loadHighscores()
            .filter((record) => record.key === key)
            .sort(compareHighscores)[0] || null;
    }

    function renderHighscores() {
        const currentSettings = readSettings();
        const currentBest = bestForSettings(currentSettings);
        const currentBestText = currentBest ? formatNumber(currentBest.score) : t('noHighscore', 'Noch kein Highscore');

        if (ui.bestCurrent) ui.bestCurrent.textContent = currentBest ? formatNumber(currentBest.score) : '0';
        if (ui.currentBestLabel) ui.currentBestLabel.textContent = currentBestText;
        if (ui.currentBestSettings) ui.currentBestSettings.textContent = settingsLabel(currentSettings);

        if (!ui.highscoreList) return;
        ui.highscoreList.innerHTML = '';

        const records = loadHighscores().sort(compareHighscores).slice(0, 5);
        if (!records.length) {
            const empty = document.createElement('div');
            empty.className = 'snake-empty-state';
            empty.textContent = t('emptyHighscores', 'Noch keine Highscores gespielt.');
            ui.highscoreList.appendChild(empty);
            return;
        }

        records.forEach((record, index) => {
            const row = document.createElement('article');
            row.className = 'snake-highscore-row';

            const rank = document.createElement('span');
            rank.className = 'snake-highscore-rank';
            rank.textContent = `#${index + 1}`;

            const copy = document.createElement('div');
            copy.className = 'snake-highscore-copy';

            const settings = document.createElement('div');
            settings.className = 'snake-highscore-settings';
            settings.textContent = settingsLabelFromRecord(record);

            const meta = document.createElement('div');
            meta.className = 'snake-highscore-meta';
            meta.textContent = `${record.fruits || 0} ${t('fruitPlural', 'Früchte')} · ${t('lengthShort', 'Länge')} ${record.length || 0} · ${formatDate(record.achievedAt)}`;

            const score = document.createElement('strong');
            score.className = 'snake-highscore-score';
            score.textContent = formatNumber(record.score);

            copy.append(settings, meta);
            row.append(rank, copy, score);
            ui.highscoreList.appendChild(row);
        });
    }

    function settingsLabelFromRecord(record) {
        const settings = record.settings || parseSettingsKey(record.key);
        return settingsLabel(settings);
    }

    function parseSettingsKey(key) {
        const [boardSize, speedKey, fruitLimit, spawnKey, wallMode] = String(key || '').split('|');
        return {
            boardSize: clampNumber(Number(boardSize || 19), 11, 31),
            speedKey: speedKey || 'normal',
            interval: speedConfig[speedKey] || speedConfig.normal,
            fruitLimit: clampNumber(Number(fruitLimit || 1), 1, 7),
            spawnKey: spawnKey || 'normal',
            spawnEvery: spawnConfig[spawnKey] ?? spawnConfig.normal,
            wallMode: wallMode || 'wrap'
        };
    }

    function formatNumber(value) {
        return Number(value || 0).toLocaleString(locale);
    }

    function formatDate(value) {
        if (!value) return '';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return '';
        return date.toLocaleDateString(locale, { day: '2-digit', month: '2-digit', year: '2-digit' });
    }

    function updateUi(includeHighscores = true) {
        if (ui.score) ui.score.textContent = formatNumber(state.score);
        if (ui.length) ui.length.textContent = formatNumber(state.snake.length);
        if (ui.fruits) ui.fruits.textContent = formatNumber(state.fruits);
        if (includeHighscores) renderHighscores();
    }

    function showOverlay(kicker, title, message) {
        if (ui.overlayKicker) ui.overlayKicker.textContent = kicker;
        if (ui.overlayTitle) ui.overlayTitle.textContent = title;
        if (ui.overlayText) ui.overlayText.textContent = message;
        ui.overlay?.classList.remove('is-hidden');
    }

    function hideOverlay() {
        ui.overlay?.classList.add('is-hidden');
    }

    function setDirection(directionName) {
        if (!directionVectors[directionName]) return;
        if (state.phase === 'idle') startGame();
        if (state.phase !== 'running') return;

        const next = directionVectors[directionName];
        const lastQueuedDirection = state.turnQueue[state.turnQueue.length - 1];
        const base = lastQueuedDirection || state.direction;
        if (isSameDirection(next, base) || isOppositeDirection(next, base)) return;

        if (state.turnQueue.length >= inputConfig.maxQueuedTurns) {
            state.turnQueue[state.turnQueue.length - 1] = next;
        } else {
            state.turnQueue.push(next);
        }

        state.nextDirection = state.turnQueue[0] || state.direction;
        boostPendingTurn();
        renderCurrentFrame();
    }

    function isSameDirection(a, b) {
        return Boolean(a && b && a.x === b.x && a.y === b.y);
    }

    function isOppositeDirection(a, b) {
        return Boolean(a && b && a.x + b.x === 0 && a.y + b.y === 0);
    }

    function boostPendingTurn() {
        if (!lastStepAt || state.phase !== 'running') return;

        const now = performance.now();
        const interval = state.settings.interval;
        const elapsed = now - lastStepAt;
        if (elapsed < inputConfig.minTurnBoostElapsed) return;

        const targetElapsed = interval * inputConfig.turnBoostProgress;
        if (elapsed < targetElapsed) {
            lastStepAt = now - targetElapsed;
        }

        if (!animationFrameId) {
            animationFrameId = window.requestAnimationFrame(animationLoop);
        }
    }

    function renderCurrentFrame() {
        if (!lastStepAt || state.phase !== 'running') return;
        lastRenderProgress = clampFloat((performance.now() - lastStepAt) / state.settings.interval, 0, 1);
        render(lastRenderProgress);
    }

    function syncBoardSize() {
        const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 720;
        const pageTop = Math.max(0, root.getBoundingClientRect().top);
        const shell = root.querySelector('.snake-shell');
        const header = root.querySelector('.snake-header');
        const scorebar = root.querySelector('.snake-scorebar');
        const gameCard = root.querySelector('.snake-game-card');
        const sidePanel = root.querySelector('.snake-side-panel');
        const shellStyles = shell ? getComputedStyle(shell) : null;
        const gameStyles = gameCard ? getComputedStyle(gameCard) : null;
        const verticalGap = parseFloat(shellStyles?.rowGap || shellStyles?.gap || 10) || 10;
        const gamePadding = (parseFloat(gameStyles?.paddingTop || 0) || 0) + (parseFloat(gameStyles?.paddingBottom || 0) || 0);
        const bottomGap = 12;
        const availableHeight = viewportHeight
            - pageTop
            - (header?.offsetHeight || 0)
            - verticalGap
            - (scorebar?.offsetHeight || 0)
            - gamePadding
            - bottomGap;
        const sideHeight = sidePanel?.offsetHeight || 0;
        const pageHeaderSpace = (header?.offsetHeight || 0) + verticalGap + bottomGap;
        const sideFitHeight = viewportHeight - pageTop - pageHeaderSpace;
        const sideOverflowPenalty = Math.max(0, sideHeight - sideFitHeight);
        const maxBoardSize = window.innerWidth <= 980 ? 620 : 540;
        const nextBoardSize = clampNumber(availableHeight - sideOverflowPenalty, 300, maxBoardSize);

        root.style.setProperty('--snake-board-fit-size', `${nextBoardSize}px`);

        const displaySize = Math.round(canvas.getBoundingClientRect().width || nextBoardSize);
        const dpr = clampFloat(window.devicePixelRatio || 1, 1, 2);
        const pixelSize = clampNumber(displaySize * dpr, 300, 1200);
        if (canvas.width !== pixelSize || canvas.height !== pixelSize) {
            canvas.width = pixelSize;
            canvas.height = pixelSize;
        }
        ctx.imageSmoothingEnabled = true;
    }

    function requestFitSync() {
        if (resizeFrameId) window.cancelAnimationFrame(resizeFrameId);
        resizeFrameId = window.requestAnimationFrame(() => {
            resizeFrameId = null;
            syncBoardSize();
            render(state.phase === 'running' ? lastRenderProgress : 1);
        });
    }

    function render(progress = 1) {
        const styles = getComputedStyle(root);
        const boardSize = state.settings.boardSize;
        const canvasSize = canvas.width;
        const cellSize = canvasSize / boardSize;

        ctx.fillStyle = styles.getPropertyValue('--snake-board-bg').trim() || '#f7fafc';
        ctx.fillRect(0, 0, canvasSize, canvasSize);

        drawGrid(styles, canvasSize, cellSize, boardSize);
        drawFood(styles, cellSize);
        drawSnake(styles, cellSize, progress);
    }

    function drawGrid(styles, canvasSize, cellSize, boardSize) {
        ctx.strokeStyle = styles.getPropertyValue('--snake-board-line').trim() || 'rgba(15, 23, 42, 0.08)';
        ctx.lineWidth = Math.max(1, canvasSize / 600);
        ctx.beginPath();
        for (let index = 1; index < boardSize; index += 1) {
            const position = Math.round(index * cellSize) + 0.5;
            ctx.moveTo(position, 0);
            ctx.lineTo(position, canvasSize);
            ctx.moveTo(0, position);
            ctx.lineTo(canvasSize, position);
        }
        ctx.stroke();
    }

    function drawFood(styles, cellSize) {
        const color = styles.getPropertyValue('--snake-food').trim() || '#ea4335';
        ctx.fillStyle = color;
        state.food.forEach((food) => {
            const centerX = food.x * cellSize + cellSize / 2;
            const centerY = food.y * cellSize + cellSize / 2;
            const radius = Math.max(4, cellSize * 0.32);
            ctx.beginPath();
            ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
            ctx.fill();
        });
    }

    function drawSnake(styles, cellSize, progress = 1) {
        const bodyColor = styles.getPropertyValue('--snake-snake').trim() || '#34a853';
        const headColor = styles.getPropertyValue('--snake-snake-head').trim() || '#1e8e3e';
        const bellyColor = styles.getPropertyValue('--snake-snake-belly').trim() || 'rgba(255, 255, 255, 0.24)';
        const eyeColor = styles.getPropertyValue('--snake-snake-eye').trim() || '#111827';
        const tongueColor = styles.getPropertyValue('--snake-snake-tongue').trim() || '#e11d48';
        const easedProgress = easeInOut(progress);
        const bodyDiameter = Math.max(7, cellSize * 0.72);
        const headDiameter = Math.max(9, cellSize * 0.86);
        const tailDiameter = Math.max(5, cellSize * 0.46);
        const positions = state.snake.map((part, index) => {
            const previous = state.previousSnake[index] || state.previousSnake[state.previousSnake.length - 1] || part;
            return interpolateCell(previous, part, easedProgress, state.settings.boardSize);
        });

        drawSnakeBody(positions, cellSize, bodyColor, bellyColor, bodyDiameter, tailDiameter);
        drawSnakeHead(positions[0], cellSize, headColor, eyeColor, tongueColor, headDiameter);
    }

    function drawSnakeBody(positions, cellSize, bodyColor, bellyColor, bodyDiameter, tailDiameter) {
        if (positions.length <= 1) return;

        ctx.save();
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        ctx.strokeStyle = bodyColor;
        ctx.fillStyle = bodyColor;

        for (let index = 0; index < positions.length - 1; index += 1) {
            const current = positions[index];
            const next = positions[index + 1];
            if (!canConnectSnakeParts(current, next)) continue;

            const currentCenter = cellCenter(current, cellSize);
            const nextCenter = cellCenter(next, cellSize);
            ctx.lineWidth = Math.min(
                snakeBodyDiameter(index, positions.length, bodyDiameter, tailDiameter),
                snakeBodyDiameter(index + 1, positions.length, bodyDiameter, tailDiameter)
            );
            ctx.beginPath();
            ctx.moveTo(currentCenter.x, currentCenter.y);
            ctx.lineTo(nextCenter.x, nextCenter.y);
            ctx.stroke();
        }

        for (let index = positions.length - 1; index >= 1; index -= 1) {
            const center = cellCenter(positions[index], cellSize);
            const diameter = snakeBodyDiameter(index, positions.length, bodyDiameter, tailDiameter);
            ctx.fillStyle = bodyColor;
            ctx.beginPath();
            ctx.arc(center.x, center.y, diameter / 2, 0, Math.PI * 2);
            ctx.fill();

            if (index % 2 === 0 && positions.length > 5) {
                ctx.fillStyle = bellyColor;
                ctx.beginPath();
                ctx.arc(center.x, center.y, Math.max(1.2, diameter * 0.13), 0, Math.PI * 2);
                ctx.fill();
            }
        }

        ctx.restore();
    }

    function drawSnakeHead(position, cellSize, headColor, eyeColor, tongueColor, headDiameter) {
        if (!position) return;

        const center = cellCenter(position, cellSize);
        const angle = directionAngle(getVisualDirection());
        const radiusX = headDiameter * 0.5;
        const radiusY = headDiameter * 0.44;

        ctx.save();
        ctx.translate(center.x, center.y);
        ctx.rotate(angle);

        ctx.fillStyle = headColor;
        ctx.beginPath();
        ctx.ellipse(0, 0, radiusX, radiusY, 0, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = 'rgba(255, 255, 255, 0.18)';
        ctx.beginPath();
        ctx.ellipse(-headDiameter * 0.08, -headDiameter * 0.1, radiusX * 0.52, radiusY * 0.34, -0.22, 0, Math.PI * 2);
        ctx.fill();

        const eyeRadius = Math.max(1.8, headDiameter * 0.075);
        const pupilRadius = Math.max(0.9, eyeRadius * 0.48);
        const eyeX = headDiameter * 0.16;
        const eyeY = headDiameter * 0.2;
        drawSnakeEye(eyeX, -eyeY, eyeRadius, pupilRadius, eyeColor);
        drawSnakeEye(eyeX, eyeY, eyeRadius, pupilRadius, eyeColor);

        ctx.fillStyle = eyeColor;
        const nostrilRadius = Math.max(0.75, headDiameter * 0.025);
        ctx.beginPath();
        ctx.arc(headDiameter * 0.34, -headDiameter * 0.075, nostrilRadius, 0, Math.PI * 2);
        ctx.arc(headDiameter * 0.34, headDiameter * 0.075, nostrilRadius, 0, Math.PI * 2);
        ctx.fill();

        drawTongue(headDiameter, tongueColor);
        ctx.restore();
    }

    function drawSnakeEye(x, y, eyeRadius, pupilRadius, eyeColor) {
        ctx.fillStyle = '#ffffff';
        ctx.beginPath();
        ctx.arc(x, y, eyeRadius, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = eyeColor;
        ctx.beginPath();
        ctx.arc(x + eyeRadius * 0.2, y, pupilRadius, 0, Math.PI * 2);
        ctx.fill();
    }

    function drawTongue(headDiameter, tongueColor) {
        const tongueStart = headDiameter * 0.45;
        const tongueEnd = headDiameter * 0.68;
        const fork = headDiameter * 0.11;

        ctx.strokeStyle = tongueColor;
        ctx.lineWidth = Math.max(1.2, headDiameter * 0.035);
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        ctx.beginPath();
        ctx.moveTo(tongueStart, 0);
        ctx.lineTo(tongueEnd, 0);
        ctx.lineTo(tongueEnd + fork, -fork * 0.55);
        ctx.moveTo(tongueEnd, 0);
        ctx.lineTo(tongueEnd + fork, fork * 0.55);
        ctx.stroke();
    }

    function snakeBodyDiameter(index, total, bodyDiameter, tailDiameter) {
        if (total <= 4) return bodyDiameter;
        const taperStart = Math.max(1, Math.floor(total * 0.72));
        if (index < taperStart) return bodyDiameter;

        const taperProgress = (index - taperStart) / Math.max(1, total - 1 - taperStart);
        return bodyDiameter - (bodyDiameter - tailDiameter) * clampFloat(taperProgress, 0, 1);
    }

    function canConnectSnakeParts(a, b) {
        if (!a || !b) return false;
        return Math.abs(a.x - b.x) <= 1.05 && Math.abs(a.y - b.y) <= 1.05;
    }

    function cellCenter(cell, cellSize) {
        return {
            x: cell.x * cellSize + cellSize / 2,
            y: cell.y * cellSize + cellSize / 2
        };
    }

    function getVisualDirection() {
        return state.turnQueue?.[0] || state.nextDirection || state.direction || directionVectors.right;
    }

    function directionAngle(vector) {
        if (!vector) return 0;
        if (vector.x < 0) return Math.PI;
        if (vector.y > 0) return Math.PI / 2;
        if (vector.y < 0) return -Math.PI / 2;
        return 0;
    }

    function easeInOut(value) {
        const progress = clampFloat(value, 0, 1);
        return progress * progress * (3 - 2 * progress);
    }

    function interpolateCell(from, to, progress, boardSize) {
        if (!from || !to) return to || from || { x: 0, y: 0 };
        if (Math.abs(to.x - from.x) > 1 || Math.abs(to.y - from.y) > 1) return to;
        if (from.x < 0 || from.y < 0 || from.x >= boardSize || from.y >= boardSize) return to;
        return {
            x: from.x + (to.x - from.x) * progress,
            y: from.y + (to.y - from.y) * progress
        };
    }

    function roundedRect(x, y, width, height, radius) {
        if (typeof ctx.roundRect === 'function') {
            ctx.beginPath();
            ctx.roundRect(x, y, width, height, radius);
            ctx.fill();
            return;
        }

        const r = Math.min(radius, width / 2, height / 2);
        ctx.beginPath();
        ctx.moveTo(x + r, y);
        ctx.lineTo(x + width - r, y);
        ctx.quadraticCurveTo(x + width, y, x + width, y + r);
        ctx.lineTo(x + width, y + height - r);
        ctx.quadraticCurveTo(x + width, y + height, x + width - r, y + height);
        ctx.lineTo(x + r, y + height);
        ctx.quadraticCurveTo(x, y + height, x, y + height - r);
        ctx.lineTo(x, y + r);
        ctx.quadraticCurveTo(x, y, x + r, y);
        ctx.fill();
    }

    function handleSettingChange() {
        if (state.phase === 'running' || state.phase === 'paused') return;
        state = createGameState(readSettings(), 'idle');
        updateUi();
        requestFitSync();
    }

    function bindEvents() {
        ui.overlayStartButton?.addEventListener('click', startGame);
        ui.restartButton?.addEventListener('click', restartToMenu);
        ui.pauseButton?.addEventListener('click', togglePause);

        [ui.boardSelect, ui.speedSelect, ui.fruitCountSelect, ui.spawnRateSelect, ui.wallsSelect].forEach((select) => {
            select?.addEventListener('change', handleSettingChange);
        });

        document.addEventListener('keydown', (event) => {
            const direction = keyDirections[event.code];
            if (direction) {
                event.preventDefault();
                setDirection(direction);
                return;
            }
            if (event.code === 'Space') {
                event.preventDefault();
                togglePause();
            }
        });

        document.querySelectorAll('.snake-touch-controls [data-direction]').forEach((button) => {
            button.addEventListener('click', () => setDirection(button.dataset.direction));
        });

        canvas.addEventListener('pointerdown', (event) => {
            touchStart = { x: event.clientX, y: event.clientY };
        });

        canvas.addEventListener('pointerup', (event) => {
            if (!touchStart) return;
            const deltaX = event.clientX - touchStart.x;
            const deltaY = event.clientY - touchStart.y;
            touchStart = null;
            if (Math.max(Math.abs(deltaX), Math.abs(deltaY)) < 24) return;
            if (Math.abs(deltaX) > Math.abs(deltaY)) {
                setDirection(deltaX > 0 ? 'right' : 'left');
            } else {
                setDirection(deltaY > 0 ? 'down' : 'up');
            }
        });

        window.addEventListener('resize', requestFitSync, { passive: true });
        window.addEventListener('orientationchange', requestFitSync, { passive: true });

        const observer = new MutationObserver(requestFitSync);
        observer.observe(document.body, { attributes: true, attributeFilter: ['class'] });
    }

    mergeHighscores(serverHighscores);
    bindEvents();
    updateSettingsDisabled(false);
    updatePauseButton();
    updateUi();
    requestFitSync();
    syncStoredHighscores();
})();
