(() => {
    const root = document.querySelector('.game2048-page');
    if (!root) return;

    const boardEl = document.getElementById('board2048');
    const scoreEl = document.getElementById('score2048');
    const bestEl = document.getElementById('best2048');
    const statusEl = document.getElementById('game2048Status');
    const overlay = document.getElementById('overlay2048');
    const overlayTitle = document.getElementById('overlay2048Title');
    const overlayText = document.getElementById('overlay2048Text');
    const restartBtn = document.getElementById('restart2048');
    const continueBtn = document.getElementById('continue2048');
    const againBtn = document.getElementById('again2048');
    const scoreUrl = root.dataset.scoreUrl;
    const activityUrl = root.dataset.activityUrl;
    const localBestKey = 'mytools-2048-local-best-v1';

    const size = 4;
    const slideDuration = 205;
    const popDuration = 170;
    const animationBuffer = 18;
    const maxQueuedMoves = 2;

    let cellLayer = null;
    let tileLayer = null;
    let tileId = 0;
    let isAnimating = false;
    let queuedMoves = [];
    let animationToken = 0;
    let boardMetrics = { gap: 12, tileSize: 0, step: 0 };

    const state = {
        tiles: [],
        score: 0,
        moves: 0,
        startedAt: Date.now(),
        wonNotified: false,
        finished: false,
        savedFinal: false,
    };

    const getCookie = name => {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        return parts.length === 2 ? parts.pop().split(';').shift() : '';
    };

    const formatNumber = value => Number(value || 0).toLocaleString('de-DE');
    const durationSeconds = () => Math.max(0, Math.round((Date.now() - state.startedAt) / 1000));
    const activeTiles = () => state.tiles.filter(tile => !tile.remove);
    const bestTileFrom = tiles => Math.max(2, ...tiles.map(tile => Number(tile.value || 0)));
    const bestTile = () => bestTileFrom(activeTiles());
    const overlayIsOpen = () => overlay && !overlay.classList.contains('is-hidden');

    const buildBoard = () => {
        boardEl.innerHTML = '';

        cellLayer = document.createElement('div');
        cellLayer.className = 'game2048-cell-layer';

        tileLayer = document.createElement('div');
        tileLayer.className = 'game2048-tile-layer';
        tileLayer.setAttribute('aria-hidden', 'true');

        for (let i = 0; i < size * size; i += 1) {
            const cell = document.createElement('div');
            cell.className = 'game2048-cell';
            cellLayer.appendChild(cell);
        }

        boardEl.append(cellLayer, tileLayer);
    };

    const updateBoardMetrics = () => {
        if (!cellLayer || !tileLayer) return boardMetrics;

        const styles = window.getComputedStyle(cellLayer);
        const gap = parseFloat(styles.columnGap || styles.gap || '12') || 12;
        const layerWidth = tileLayer.getBoundingClientRect().width;
        const tileSize = Math.max(0, (layerWidth - gap * (size - 1)) / size);
        const step = tileSize + gap;

        boardMetrics = { gap, tileSize, step };
        boardEl.style.setProperty('--game2048-tile-size', `${tileSize}px`);
        boardEl.style.setProperty('--game2048-tile-gap', `${gap}px`);
        boardEl.style.setProperty('--game2048-slide-duration', `${slideDuration}ms`);
        return boardMetrics;
    };

    const transformFor = (row, col) => {
        const { step } = boardMetrics;
        return `translate3d(${col * step}px, ${row * step}px, 0)`;
    };

    const createLogicalTile = (value, row, col, options = {}) => ({
        id: options.id ?? (tileId += 1),
        value,
        row,
        col,
        isNew: Boolean(options.isNew),
        isMerged: Boolean(options.isMerged),
    });

    const createTileElement = tile => {
        const el = document.createElement('div');
        el.className = 'game2048-tile';
        const inner = document.createElement('span');
        inner.className = 'game2048-tile-inner';
        inner.textContent = tile.value;
        el.appendChild(inner);
        el.dataset.value = String(tile.value);
        el.dataset.tileId = String(tile.id);
        el.style.transform = transformFor(tile.row, tile.col);

        if (tile.isNew) el.classList.add('is-new');
        if (tile.isMerged) el.classList.add('is-merged');
        if (tile.isGhost) el.classList.add('is-ghost');

        return el;
    };

    const gridFromTiles = tiles => {
        const grid = Array.from({ length: size }, () => Array(size).fill(null));
        tiles.forEach(tile => {
            if (tile.row >= 0 && tile.row < size && tile.col >= 0 && tile.col < size) {
                grid[tile.row][tile.col] = tile;
            }
        });
        return grid;
    };

    const emptyCells = tiles => {
        const grid = gridFromTiles(tiles ?? activeTiles());
        const cells = [];
        for (let row = 0; row < size; row += 1) {
            for (let col = 0; col < size; col += 1) {
                if (!grid[row][col]) cells.push([row, col]);
            }
        }
        return cells;
    };

    const addRandomTile = (withAnimation = true) => {
        const cells = emptyCells(state.tiles);
        if (!cells.length) return null;

        const [row, col] = cells[Math.floor(Math.random() * cells.length)];
        const tile = createLogicalTile(Math.random() < 0.9 ? 2 : 4, row, col, { isNew: withAnimation });
        state.tiles.push(tile);
        return tile;
    };

    const updateScoreDisplays = (visibleBest = bestTile()) => {
        scoreEl.textContent = formatNumber(state.score);
        const storedBest = Number(localStorage.getItem(localBestKey) || 0);
        bestEl.textContent = formatNumber(Math.max(storedBest, state.score));
        statusEl.textContent = state.moves
            ? `${state.moves} Züge · beste Kachel ${visibleBest}`
            : 'Nutze Pfeiltasten, WASD oder Wischgesten.';
    };


    const pulseScoreCard = gained => {
        if (!gained) return;
        const card = scoreEl.closest('.game2048-score-card');
        if (!card) return;
        card.classList.remove('is-bumped');
        void card.offsetWidth;
        card.classList.add('is-bumped');

        const floatingScore = document.createElement('span');
        floatingScore.className = 'game2048-score-pop';
        floatingScore.textContent = `+${formatNumber(gained)}`;
        card.appendChild(floatingScore);

        window.setTimeout(() => card.classList.remove('is-bumped'), 240);
        window.setTimeout(() => floatingScore.remove(), 760);
    };

    const clearTransientTileClasses = () => {
        window.setTimeout(() => {
            state.tiles.forEach(tile => {
                tile.isNew = false;
                tile.isMerged = false;
            });
            tileLayer?.querySelectorAll('.is-new, .is-merged').forEach(el => {
                el.classList.remove('is-new', 'is-merged');
            });
        }, popDuration + 80);
    };

    const renderStaticBoard = () => {
        updateBoardMetrics();
        tileLayer.innerHTML = '';
        state.tiles.forEach(tile => tileLayer.appendChild(createTileElement(tile)));
        updateScoreDisplays();
        clearTransientTileClasses();
    };

    const linesForDirection = direction => {
        const lines = [];
        if (direction === 'left' || direction === 'right') {
            for (let row = 0; row < size; row += 1) {
                const cols = direction === 'right' ? [3, 2, 1, 0] : [0, 1, 2, 3];
                lines.push(cols.map(col => [row, col]));
            }
            return lines;
        }

        for (let col = 0; col < size; col += 1) {
            const rows = direction === 'down' ? [3, 2, 1, 0] : [0, 1, 2, 3];
            lines.push(rows.map(row => [row, col]));
        }
        return lines;
    };

    const calculateMove = direction => {
        const grid = gridFromTiles(activeTiles());
        const finalTiles = [];
        const animationTiles = [];
        let gained = 0;
        let moved = false;

        linesForDirection(direction).forEach(coords => {
            const sourceTiles = coords.map(([row, col]) => grid[row][col]).filter(Boolean);
            let targetIndex = 0;

            for (let i = 0; i < sourceTiles.length; i += 1) {
                const current = sourceTiles[i];
                const next = sourceTiles[i + 1];
                const [targetRow, targetCol] = coords[targetIndex];

                if (next && current.value === next.value) {
                    const mergedValue = current.value * 2;

                    animationTiles.push({
                        ...current,
                        fromRow: current.row,
                        fromCol: current.col,
                        toRow: targetRow,
                        toCol: targetCol,
                        mergeLead: true,
                    });
                    animationTiles.push({
                        ...next,
                        fromRow: next.row,
                        fromCol: next.col,
                        toRow: targetRow,
                        toCol: targetCol,
                        isGhost: true,
                    });

                    finalTiles.push(createLogicalTile(mergedValue, targetRow, targetCol, {
                        id: current.id,
                        isMerged: true,
                    }));

                    gained += mergedValue;
                    moved = true;
                    i += 1;
                    targetIndex += 1;
                    continue;
                }

                if (current.row !== targetRow || current.col !== targetCol) moved = true;

                animationTiles.push({
                    ...current,
                    fromRow: current.row,
                    fromCol: current.col,
                    toRow: targetRow,
                    toCol: targetCol,
                });
                finalTiles.push(createLogicalTile(current.value, targetRow, targetCol, { id: current.id }));
                targetIndex += 1;
            }
        });

        return { moved, gained, finalTiles, animationTiles };
    };

    const movementOvershootFor = (fromRow, fromCol, toRow, toCol) => {
        const dx = toCol - fromCol;
        const dy = toRow - fromRow;
        if (!dx && !dy) return transformFor(toRow, toCol);

        const travel = Math.abs(dx) + Math.abs(dy);
        const overshoot = Math.min(7, Math.max(3, boardMetrics.step * (travel > 1 ? 0.025 : 0.018)));
        const x = toCol * boardMetrics.step + Math.sign(dx) * overshoot;
        const y = toRow * boardMetrics.step + Math.sign(dy) * overshoot;
        return `translate3d(${x}px, ${y}px, 0)`;
    };

    const transformWithScale = (transform, scale = 1) => scale === 1 ? transform : `${transform} scale(${scale})`;

    const runElementSlide = (el, tile) => {
        const fromTransform = transformFor(tile.fromRow, tile.fromCol);
        const toTransform = transformFor(tile.toRow, tile.toCol);
        const overshootTransform = movementOvershootFor(tile.fromRow, tile.fromCol, tile.toRow, tile.toCol);

        el.style.transform = fromTransform;
        el.classList.remove('is-preparing-move');
        el.classList.add('is-moving');

        if (typeof el.animate === 'function') {
            const hasMovement = fromTransform !== toTransform;
            const animation = el.animate(
                hasMovement
                    ? [
                        { transform: transformWithScale(fromTransform, 1), offset: 0 },
                        { transform: transformWithScale(overshootTransform, 1.018), offset: 0.84 },
                        { transform: transformWithScale(toTransform, 1), offset: 1 },
                    ]
                    : [{ transform: toTransform }, { transform: toTransform }],
                {
                    duration: slideDuration,
                    easing: 'cubic-bezier(.2,.82,.2,1)',
                    fill: 'forwards',
                },
            );
            animation.finished.catch(() => null);
            return animation;
        }

        el.style.transition = `transform ${slideDuration}ms cubic-bezier(.2,.82,.2,1)`;
        void el.offsetWidth;
        requestAnimationFrame(() => {
            el.style.transform = toTransform;
        });
        return null;
    };

    const animateTiles = (animationTiles, finalTiles, onComplete) => {
        const token = animationToken;
        updateBoardMetrics();
        tileLayer.innerHTML = '';
        boardEl.classList.add('is-sliding');

        const animatedElements = animationTiles.map(tile => {
            const el = createTileElement({
                id: tile.id,
                value: tile.value,
                row: tile.fromRow,
                col: tile.fromCol,
                isGhost: tile.isGhost,
            });
            el.classList.add('is-preparing-move');
            el.style.transform = transformFor(tile.fromRow, tile.fromCol);
            tileLayer.appendChild(el);
            return { el, tile };
        });

        // Wichtig: Erst Startpositionen in den DOM schreiben und Layout erzwingen.
        // Danach starten die Tiles per Web Animations API wirklich von Feld A nach Feld B.
        void tileLayer.offsetWidth;

        const animations = animatedElements
            .map(({ el, tile }) => runElementSlide(el, tile))
            .filter(Boolean);

        const finish = () => {
            if (animationToken !== token) return;
            boardEl.classList.remove('is-sliding');
            state.tiles = finalTiles;
            onComplete();
        };

        if (animations.length) {
            Promise.allSettled(animations.map(animation => animation.finished))
                .then(finish);
            window.setTimeout(finish, slideDuration + animationBuffer + 45);
            return;
        }

        window.setTimeout(finish, slideDuration + animationBuffer);
    };

    const flushQueuedMove = () => {
        const direction = queuedMoves.shift();
        if (!direction || state.finished || overlayIsOpen()) return;
        window.setTimeout(() => requestMove(direction), 8);
    };

    const move = direction => {
        if (state.finished) return;

        const result = calculateMove(direction);
        if (!result.moved) return;

        isAnimating = true;
        animationToken += 1;
        const token = animationToken;

        state.score += result.gained;
        state.moves += 1;
        const visibleBest = bestTileFrom(result.finalTiles);
        localStorage.setItem(localBestKey, String(Math.max(Number(localStorage.getItem(localBestKey) || 0), state.score)));
        updateScoreDisplays(visibleBest);
        pulseScoreCard(result.gained);
        pingActivity();
        if (result.gained && navigator.vibrate) navigator.vibrate(8);

        animateTiles(result.animationTiles, result.finalTiles, () => {
            if (animationToken !== token) return;

            addRandomTile(true);
            renderStaticBoard();
            isAnimating = false;
            checkState();
            flushQueuedMove();
        });
    };

    const requestMove = direction => {
        if (isAnimating) {
            if (queuedMoves[queuedMoves.length - 1] !== direction) {
                queuedMoves = [...queuedMoves.slice(-(maxQueuedMoves - 1)), direction];
            }
            return;
        }
        move(direction);
    };

    const canMove = () => {
        if (emptyCells(state.tiles).length) return true;
        const grid = gridFromTiles(activeTiles());
        for (let row = 0; row < size; row += 1) {
            for (let col = 0; col < size; col += 1) {
                const tile = grid[row][col];
                if (!tile) return true;
                if (grid[row]?.[col + 1]?.value === tile.value || grid[row + 1]?.[col]?.value === tile.value) return true;
            }
        }
        return false;
    };

    const postJson = async (url, payload = {}) => {
        if (!url) return null;
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'),
            },
            body: JSON.stringify(payload),
            credentials: 'same-origin',
        });
        if (!response.ok) return null;
        return response.json();
    };

    const saveScore = async (final = false) => {
        if (final && state.savedFinal) return;
        if (final) state.savedFinal = true;

        const data = await postJson(scoreUrl, {
            score: state.score,
            best_tile: bestTile(),
            moves: state.moves,
            duration_seconds: durationSeconds(),
            won: bestTile() >= 2048,
            details: { final },
        });

        if (data?.highscore) {
            bestEl.textContent = data.highscore.display_score;
            statusEl.textContent = data.new_highscore ? 'Neuer Highscore gespeichert!' : 'Score gespeichert.';
        }
    };

    const pingActivity = () => postJson(activityUrl).catch(() => null);

    const showOverlay = (title, text, showContinue = false) => {
        overlayTitle.textContent = title;
        overlayText.textContent = text;
        continueBtn.hidden = !showContinue;
        overlay.classList.remove('is-hidden');
    };

    const hideOverlay = () => overlay.classList.add('is-hidden');

    const checkState = () => {
        if (!state.wonNotified && bestTile() >= 2048) {
            state.wonNotified = true;
            saveScore(false);
            showOverlay('2048!', 'Stark, du hast die 2048-Kachel erreicht. Du kannst weiterspielen oder neu starten.', true);
            return;
        }

        if (!canMove()) {
            state.finished = true;
            saveScore(true);
            showOverlay('Game Over', `Finaler Score: ${formatNumber(state.score)} · Beste Kachel: ${bestTile()}`, false);
        }
    };

    const newGame = () => {
        animationToken += 1;
        isAnimating = false;
        queuedMoves = [];
        tileId = 0;

        state.tiles = [];
        state.score = 0;
        state.moves = 0;
        state.startedAt = Date.now();
        state.wonNotified = false;
        state.finished = false;
        state.savedFinal = false;

        addRandomTile(true);
        addRandomTile(true);
        hideOverlay();
        renderStaticBoard();
        pingActivity();
    };

    const keyMap = {
        ArrowLeft: 'left', a: 'left', A: 'left',
        ArrowRight: 'right', d: 'right', D: 'right',
        ArrowUp: 'up', w: 'up', W: 'up',
        ArrowDown: 'down', s: 'down', S: 'down',
    };

    document.addEventListener('keydown', event => {
        const direction = keyMap[event.key];
        if (!direction) return;
        event.preventDefault();
        requestMove(direction);
    });

    let touchStart = null;
    boardEl.addEventListener('touchstart', event => {
        const touch = event.changedTouches[0];
        touchStart = { x: touch.clientX, y: touch.clientY };
    }, { passive: true });

    boardEl.addEventListener('touchend', event => {
        if (!touchStart) return;
        const touch = event.changedTouches[0];
        const dx = touch.clientX - touchStart.x;
        const dy = touch.clientY - touchStart.y;
        touchStart = null;

        if (Math.max(Math.abs(dx), Math.abs(dy)) < 24) return;
        requestMove(Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? 'right' : 'left') : (dy > 0 ? 'down' : 'up'));
    }, { passive: true });

    restartBtn.addEventListener('click', newGame);
    againBtn.addEventListener('click', newGame);
    continueBtn.addEventListener('click', () => {
        hideOverlay();
        flushQueuedMove();
    });

    window.addEventListener('resize', () => {
        if (!isAnimating) renderStaticBoard();
    });

    setInterval(pingActivity, 60000);
    window.addEventListener('beforeunload', () => {
        if (state.moves > 0 && !state.savedFinal) saveScore(false);
    });

    buildBoard();
    newGame();
})();
