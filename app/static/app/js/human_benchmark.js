document.addEventListener('DOMContentLoaded', () => {
    const page = document.querySelector('.benchmark-page');

    if (!page) {
        return;
    }

    const labelsElement = document.getElementById('benchmark-labels');
    const labels = labelsElement ? JSON.parse(labelsElement.textContent) : {};

    const scoreDataElement = document.getElementById('benchmark-score-data');
    let scoreData = scoreDataElement ? JSON.parse(scoreDataElement.textContent) : { games: {} };

    const scoreUrl = page.dataset.scoreUrl;
    let activeGame = page.querySelector('.benchmark-tab.active')?.dataset.game || 'typing';

    const currentLanguage = (page.dataset.language || '').toLowerCase();
    const shouldTranslateQuotes = currentLanguage.startsWith('de');

    let audioCtx;

    function getAudioContext() {
        if (!audioCtx) {
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        }

        if (audioCtx.state === 'suspended') {
            audioCtx.resume();
        }

        return audioCtx;
    }

    function playSound(type) {
        if (!window.AudioContext && !window.webkitAudioContext) {
            return;
        }

        const context = getAudioContext();
        const osc = context.createOscillator();
        const gain = context.createGain();
        const now = context.currentTime;

        osc.connect(gain);
        gain.connect(context.destination);

        switch (type) {
            case 'type': {
                const freq = 150 + Math.random() * 50;
                osc.type = 'sine';
                osc.frequency.setValueAtTime(freq, now);
                gain.gain.setValueAtTime(0.05, now);
                gain.gain.exponentialRampToValueAtTime(0.01, now + 0.05);
                osc.start();
                osc.stop(now + 0.05);
                break;
            }
            case 'success':
                osc.type = 'triangle';
                osc.frequency.setValueAtTime(500, now);
                osc.frequency.exponentialRampToValueAtTime(1000, now + 0.2);
                gain.gain.setValueAtTime(0.1, now);
                gain.gain.exponentialRampToValueAtTime(0.01, now + 0.3);
                osc.start();
                osc.stop(now + 0.3);
                break;
            case 'finish': {
                [523.25, 659.25, 783.99, 1046.5].forEach((freq, index) => {
                    const note = context.createOscillator();
                    const noteGain = context.createGain();

                    note.type = 'square';
                    note.connect(noteGain);
                    noteGain.connect(context.destination);
                    note.frequency.setValueAtTime(freq, now + index * 0.1);
                    noteGain.gain.setValueAtTime(0.05, now + index * 0.1);
                    noteGain.gain.exponentialRampToValueAtTime(0.01, now + index * 0.1 + 0.3);
                    note.start(now + index * 0.1);
                    note.stop(now + index * 0.1 + 0.3);
                });
                break;
            }
            case 'error':
                osc.type = 'sawtooth';
                osc.frequency.setValueAtTime(120, now);
                gain.gain.setValueAtTime(0.1, now);
                gain.gain.linearRampToValueAtTime(0, now + 0.4);
                osc.start();
                osc.stop(now + 0.4);
                break;
            case 'go':
                osc.type = 'sine';
                osc.frequency.setValueAtTime(1000, now);
                gain.gain.setValueAtTime(0.1, now);
                gain.gain.exponentialRampToValueAtTime(0.01, now + 0.2);
                osc.start();
                osc.stop(now + 0.2);
                break;
            default:
                osc.type = 'sine';
                osc.frequency.setValueAtTime(800, now);
                gain.gain.setValueAtTime(0.1, now);
                gain.gain.exponentialRampToValueAtTime(0.01, now + 0.1);
                osc.start();
                osc.stop(now + 0.1);
        }
    }

    function escapeHtml(value) {
        return String(value ?? '')
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#039;');
    }

    function getCookie(name) {
        const cookieValue = document.cookie
            .split('; ')
            .find((row) => row.startsWith(`${name}=`));

        return cookieValue ? decodeURIComponent(cookieValue.split('=')[1]) : '';
    }

    function formatScoreDetails(game, details = {}) {
        switch (game) {
            case 'reaction':
                return details.seconds
                    ? `${details.seconds}s Reaktionszeit`
                    : '';

            case 'aim': {
                const parts = [];

                if (details.accuracy !== null && details.accuracy !== undefined) {
                    parts.push(`${details.accuracy}% Genauigkeit`);
                }

                if (details.misses !== null && details.misses !== undefined) {
                    parts.push(`${details.misses} Fehlschüsse`);
                }

                if (details.total_clicks !== null && details.total_clicks !== undefined) {
                    parts.push(`${details.total_clicks} Klicks`);
                }

                return parts.join(' · ');
            }

            case 'typing': {
                const parts = [];

                if (details.seconds !== null && details.seconds !== undefined) {
                    parts.push(`${details.seconds}s`);
                }

                if (details.words !== null && details.words !== undefined) {
                    parts.push(`${details.words} Wörter`);
                }

                if (details.characters !== null && details.characters !== undefined) {
                    parts.push(`${details.characters} Zeichen`);
                }

                return parts.join(' · ');
            }

            case 'visual': {
                const parts = [];

                if (details.sequence_length !== null && details.sequence_length !== undefined) {
                    parts.push(`${details.sequence_length} Felder`);
                }

                if (details.grid_size !== null && details.grid_size !== undefined) {
                    parts.push(`${details.grid_size}x${details.grid_size}`);
                }

                return parts.join(' · ');
            }

            default:
                return '';
        }
    }

    function updateScoreboard(game) {
        const gameData = scoreData.games?.[game] || {};
        const highscoreElement = document.getElementById('current-highscore');
        const highscoreHint = document.getElementById('current-highscore-hint');
        const recentList = document.getElementById('recent-scores-list');
        const leaderboardList = document.getElementById('leaderboard-list');
        const currentGameElement = document.getElementById('scoreboard-current-game');

        if (!highscoreElement || !highscoreHint || !recentList || !leaderboardList) {
            return;
        }

        const activeTab = page.querySelector(`.benchmark-tab[data-game="${CSS.escape(game)}"]`);

        if (currentGameElement) {
            currentGameElement.textContent = activeTab?.textContent?.trim() || game;
        }

        if (gameData.highscore) {
            highscoreElement.textContent = gameData.highscore.display_score;
            highscoreHint.textContent = gameData.highscore.created_at || gameData.highscore.achieved_at || '';
        } else {
            highscoreElement.textContent = '--';
            highscoreHint.textContent = labels.noResults || 'Noch keine Ergebnisse.';
        }

        const recentScores = gameData.recent || [];

        if (recentScores.length === 0) {
            recentList.classList.add('empty');
            recentList.innerHTML = labels.noResults || 'Noch keine Ergebnisse.';
        } else {
            recentList.classList.remove('empty');
            recentList.innerHTML = recentScores.map((entry) => `
            <div class="score-row score-row-detailed">
                <div>
                    <strong>${escapeHtml(entry.display_score)}</strong>
                    <small>${escapeHtml(formatScoreDetails(game, entry.details || {}))}</small>
                </div>
                <time>${escapeHtml(entry.created_at || '')}</time>
            </div>
        `).join('');
        }

        const leaderboard = gameData.leaderboard || [];

        if (leaderboard.length === 0) {
            leaderboardList.classList.add('empty');
            leaderboardList.innerHTML = labels.noResults || 'Noch keine Ergebnisse.';
        } else {
            leaderboardList.classList.remove('empty');
            leaderboardList.innerHTML = leaderboard.map((entry) => `
                <div class="leaderboard-row">
                    <span class="leaderboard-rank">#${escapeHtml(entry.rank)}</span>
                    <span class="leaderboard-user">
                        <i class="fa-solid fa-user"></i>
                        ${escapeHtml(entry.username)}
                    </span>
                    <strong>${escapeHtml(entry.display_score)}</strong>
                </div>
            `).join('');
        }
    }

    async function saveBenchmarkScore(game, score, displayScore, details = {}) {
        if (!scoreUrl) {
            return;
        }

        const statusElement = document.getElementById('score-save-status');

        try {
            const response = await fetch(scoreUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken'),
                },
                body: JSON.stringify({
                    game,
                    score,
                    display_score: displayScore,
                    details,
                }),
            });

            const data = await response.json();

            if (!response.ok || data.status !== 'ok') {
                throw new Error(data.message || 'Score konnte nicht gespeichert werden.');
            }

            scoreData = data.score_data || scoreData;
            updateScoreboard(game);

            if (statusElement) {
                statusElement.textContent = data.new_highscore
                    ? (labels.newHighscore || 'Neuer Highscore!')
                    : (labels.saved || 'Ergebnis gespeichert.');

                window.clearTimeout(Number(statusElement.dataset.timeoutId || 0));

                const timeoutId = window.setTimeout(() => {
                    statusElement.textContent = '';
                }, 3000);

                statusElement.dataset.timeoutId = String(timeoutId);
            }
        } catch (error) {
            if (statusElement) {
                statusElement.textContent = error.message || 'Score konnte nicht gespeichert werden.';
            }
        }
    }

    function buildScoreDetails(game, data = {}) {
        switch (game) {
            case 'reaction':
                return {
                    milliseconds: data.milliseconds ?? null,
                    seconds: data.milliseconds ? Number((data.milliseconds / 1000).toFixed(3)) : null,
                };

            case 'aim':
                return {
                    seconds: data.seconds ?? null,
                    accuracy: data.accuracy ?? null,
                    misses: data.misses ?? null,
                    hits: data.hits ?? null,
                    total_clicks: data.total_clicks ?? null,
                    targets: data.targets ?? 30,
                };

            case 'typing':
                return {
                    wpm: data.wpm ?? null,
                    seconds: data.seconds ?? null,
                    words: data.words ?? null,
                    characters: data.characters ?? null,
                    quote_length: data.quote_length ?? data.characters ?? null,
                };

            case 'visual':
                return {
                    level: data.level ?? null,
                    sequence_length: data.sequence_length ?? null,
                    grid_size: data.grid_size ?? null,
                };

            default:
                return data;
        }
    }

    function switchGame(gameId, button) {
        playSound('click');

        activeGame = gameId;

        page.querySelectorAll('.benchmark-tab').forEach((tab) => tab.classList.remove('active'));
        button?.classList.add('active');

        page.querySelectorAll('.game-screen').forEach((screen) => screen.classList.remove('active'));
        document.getElementById(`${gameId}-game`)?.classList.add('active');

        updateScoreboard(gameId);
    }

    page.querySelectorAll('.benchmark-tab').forEach((button) => {
        button.addEventListener('click', () => switchGame(button.dataset.game, button));
    });

    const logo = page.querySelector('.benchmark-logo');

    if (logo) {
        logo.addEventListener('click', () => switchGame('reaction', page.querySelector('[data-game="reaction"]')));
        logo.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                switchGame('reaction', page.querySelector('[data-game="reaction"]'));
            }
        });
    }

    const rBox = document.getElementById('reaction-box');
    const rTitle = document.getElementById('r-title');
    const rDesc = document.getElementById('r-desc');

    let rState = 'waiting';
    let rTimer;
    let rStart;

    if (rBox && rTitle && rDesc) {
        rBox.addEventListener('mousedown', () => {
            if (rState === 'waiting' || rState === 'result') {
                playSound('click');
                rState = 'ready';
                rBox.className = 'benchmark-card box-ready';
                rTitle.textContent = 'Warten...';
                rDesc.textContent = 'Klicke bei GRÜN!';

                rTimer = window.setTimeout(() => {
                    playSound('go');
                    rState = 'go';
                    rBox.className = 'benchmark-card box-go';
                    rTitle.textContent = 'JETZT!';
                    rDesc.textContent = '';
                    rStart = Date.now();
                }, Math.random() * 3000 + 2000);
            } else if (rState === 'ready') {
                playSound('error');
                window.clearTimeout(rTimer);
                rState = 'result';
                rBox.className = 'benchmark-card box-waiting';
                rTitle.textContent = 'Zu früh!';
                rDesc.textContent = 'Versuche es noch einmal.';
            } else if (rState === 'go') {
                playSound('success');

                const ms = Date.now() - rStart;

                rState = 'result';
                rBox.className = 'benchmark-card box-waiting';
                rTitle.textContent = `${ms} ms`;
                rDesc.textContent = 'Klicke für einen neuen Versuch.';

                saveBenchmarkScore('reaction', ms, `${ms} ms`, buildScoreDetails('reaction', {
                    milliseconds: ms,
                }));
            }
        });
    }

    const target = document.getElementById('target');
    const aimBtn = document.getElementById('aim-start-btn');
    const aimStopBtn = document.getElementById('aim-stop-btn');
    const aimRetryBtn = document.getElementById('aim-retry-btn');
    const aimArea = document.getElementById('aim-area');
    const aimResultScreen = document.getElementById('aim-result-screen');

    let aimCount = 30;
    let aimStart;
    let aimMisses = 0;
    let aimInterval;
    let totalClicks = 0;
    let aimRunning = false;

    function updateAimUI() {
        const aimCountElement = document.getElementById('aim-count');

        if (aimCountElement) {
            aimCountElement.textContent = aimCount;
        }
    }

    function updateAccuracy() {
        const hits = 30 - aimCount;
        const acc = totalClicks > 0 ? Math.round((hits / totalClicks) * 100) : 100;
        const accuracyElement = document.getElementById('aim-accuracy-live');

        if (accuracyElement) {
            accuracyElement.textContent = acc;
        }

        return acc;
    }

    function finishAimTrainer() {
        if (!aimRunning) {
            return;
        }

        aimRunning = false;
        window.clearInterval(aimInterval);

        if (target) {
            target.style.display = 'none';
        }

        playSound('finish');

        aimStopBtn?.classList.add('hidden');

        const finalTime = Number(((Date.now() - aimStart) / 1000).toFixed(2));
        const finalAccuracy = updateAccuracy();

        const aimTimerElement = document.getElementById('aim-timer');
        const aimFinalTimeElement = document.getElementById('aim-final-time');
        const aimFinalAccuracyElement = document.getElementById('aim-final-accuracy');
        const aimFinalMissesElement = document.getElementById('aim-final-misses');

        if (aimTimerElement) {
            aimTimerElement.textContent = finalTime.toFixed(2);
        }

        if (aimFinalTimeElement) {
            aimFinalTimeElement.textContent = `${finalTime.toFixed(2)}s`;
        }

        if (aimFinalAccuracyElement) {
            aimFinalAccuracyElement.textContent = `${finalAccuracy}%`;
        }

        if (aimFinalMissesElement) {
            aimFinalMissesElement.textContent = aimMisses;
        }

        aimResultScreen?.classList.remove('hidden');

        const aimHits = 30 - aimCount;

        saveBenchmarkScore('aim', finalTime, `${finalTime.toFixed(2)}s`, buildScoreDetails('aim', {
            seconds: finalTime,
            accuracy: finalAccuracy,
            misses: aimMisses,
            hits: aimHits,
            total_clicks: totalClicks,
            targets: 30,
        }));
    }

    function moveTarget() {
        if (!target || !aimArea) {
            return;
        }

        if (aimCount <= 0) {
            playSound('success');
            finishAimTrainer();
            return;
        }

        target.style.display = 'block';

        const maxX = Math.max(0, aimArea.clientWidth - 60);
        const maxY = Math.max(0, aimArea.clientHeight - 60);

        const x = Math.random() * maxX;
        const y = Math.random() * maxY;

        target.style.left = `${x}px`;
        target.style.top = `${y}px`;
    }

    function startAimTrainer() {
        aimBtn?.classList.add('hidden');
        aimResultScreen?.classList.add('hidden');
        aimStopBtn?.classList.remove('hidden');

        aimRunning = true;
        aimCount = 30;
        aimMisses = 0;
        totalClicks = 0;

        const accuracyElement = document.getElementById('aim-accuracy-live');
        const timerElement = document.getElementById('aim-timer');

        if (accuracyElement) {
            accuracyElement.textContent = '100';
        }

        if (timerElement) {
            timerElement.textContent = '0.00';
        }

        aimStart = Date.now();

        window.clearInterval(aimInterval);
        aimInterval = window.setInterval(() => {
            const timer = document.getElementById('aim-timer');

            if (timer) {
                timer.textContent = ((Date.now() - aimStart) / 1000).toFixed(2);
            }
        }, 10);

        updateAimUI();
        moveTarget();
    }

    function resetAimTrainer() {
        window.clearInterval(aimInterval);

        aimRunning = false;
        aimResultScreen?.classList.add('hidden');
        aimBtn?.classList.remove('hidden');
        aimStopBtn?.classList.add('hidden');

        if (target) {
            target.style.display = 'none';
        }

        aimCount = 30;
        aimMisses = 0;
        totalClicks = 0;

        const timerElement = document.getElementById('aim-timer');
        const accuracyElement = document.getElementById('aim-accuracy-live');

        if (timerElement) {
            timerElement.textContent = '0.00';
        }

        if (accuracyElement) {
            accuracyElement.textContent = '100';
        }

        updateAimUI();
    }

    if (aimBtn) {
        aimBtn.addEventListener('click', (event) => {
            event.stopPropagation();
            playSound('click');
            startAimTrainer();
        });
    }

    if (aimRetryBtn) {
        aimRetryBtn.addEventListener('click', () => {
            playSound('click');
            resetAimTrainer();
        });
    }

    if (aimStopBtn) {
        aimStopBtn.addEventListener('click', () => {
            finishAimTrainer();
        });
    }

    if (aimArea) {
        aimArea.addEventListener('mousedown', (event) => {
            if (aimRunning && aimResultScreen?.classList.contains('hidden')) {
                if (target?.style.display === 'block' && event.target !== target) {
                    playSound('error');
                    aimMisses++;
                    totalClicks++;
                    updateAccuracy();
                }
            }
        });
    }

    if (target) {
        target.addEventListener('mousedown', (event) => {
            event.stopPropagation();

            if (!aimRunning) {
                return;
            }

            playSound('click');
            aimCount--;
            totalClicks++;
            updateAccuracy();
            updateAimUI();
            moveTarget();
        });
    }

    const tInput = document.getElementById('typing-input');
    const tDisplay = document.getElementById('quote-display');
    const tBtn = document.getElementById('typing-start-btn');
    const tStopBtn = document.getElementById('typing-stop-btn');
    const wpmLabel = document.getElementById('wpm-display');
    const timeLabel = document.getElementById('typing-timer-display');

    const fallbackQuotes = [
        'Es ist nicht von Bedeutung, wie langsam du gehst, solange du nicht stehen bleibst.',
        'Der einzige Weg, großartige Arbeit zu leisten, ist zu lieben, was man tut.',
        'Probleme sind keine Stoppschilder, sie sind Wegweiser.',
    ];

    const fallbackEnglishQuotes = [
        'It does not matter how slowly you go as long as you do not stop.',
        'The only way to do great work is to love what you do.',
        'Problems are not stop signs, they are guidelines.',
    ];

    let tStart;
    let tInterval;
    let currentQuote = '';
    let typingRunning = false;

    async function getRandomQuote() {
        try {
            const controller = new AbortController();
            const timeoutId = window.setTimeout(() => controller.abort(), 3000);

            if (tDisplay) {
                tDisplay.textContent = labels.loading || 'Lade Text...';
            }

            const response = await fetch('https://dummyjson.com/quotes/random', { signal: controller.signal });
            const data = await response.json();
            const englishQuote = data.quote;

            if (!shouldTranslateQuotes) {
                window.clearTimeout(timeoutId);
                return englishQuote;
            }

            if (tDisplay) {
                tDisplay.textContent = labels.translating || 'Übersetze...';
            }

            const transRes = await fetch(
                `https://api.mymemory.translated.net/get?q=${encodeURIComponent(englishQuote)}&langpair=en|de`,
                { signal: controller.signal }
            );
            const transData = await transRes.json();

            window.clearTimeout(timeoutId);

            return transData.responseData.translatedText || englishQuote;
        } catch (error) {
            const quotes = shouldTranslateQuotes ? fallbackQuotes : fallbackEnglishQuotes;
            return quotes[Math.floor(Math.random() * quotes.length)];
        }
    }

    function finishTypingTest() {
        if (!typingRunning || !tStart) {
            return;
        }

        typingRunning = false;
        window.clearInterval(tInterval);

        const finalTime = Math.max((Date.now() - tStart) / 1000, 1);
        const words = currentQuote.trim().split(/\s+/).filter(Boolean).length;
        const finalWpm = Math.round((words / finalTime) * 60);

        if (wpmLabel) {
            wpmLabel.textContent = finalWpm;
        }

        if (tInput) {
            tInput.disabled = true;
        }

        tStopBtn?.classList.add('hidden');
        tBtn?.classList.remove('hidden');

        if (tBtn) {
            tBtn.textContent = labels.nextTest || 'Nächster Test';
        }

        saveBenchmarkScore('typing', finalWpm, `${finalWpm} WPM`, buildScoreDetails('typing', {
            wpm: finalWpm,
            seconds: Number(finalTime.toFixed(2)),
            words,
            characters: currentQuote.length,
            quote_length: currentQuote.length,
        }));
    }

    if (tBtn) {
        tBtn.addEventListener('click', async () => {
            playSound('click');

            tBtn.disabled = true;
            tBtn.textContent = labels.loadingButton || 'Lädt...';

            currentQuote = await getRandomQuote();

            tBtn.disabled = false;
            tBtn.textContent = labels.startTest || 'Test starten';

            if (tDisplay) {
                tDisplay.textContent = currentQuote;
            }

            if (tInput) {
                tInput.disabled = false;
                tInput.value = '';
                tInput.focus();
            }

            tBtn.classList.add('hidden');
            tStopBtn?.classList.remove('hidden');

            window.clearInterval(tInterval);

            typingRunning = true;
            tStart = Date.now();

            if (wpmLabel) {
                wpmLabel.textContent = '0';
            }

            if (timeLabel) {
                timeLabel.textContent = '0.0s';
            }

            tInterval = window.setInterval(() => {
                const seconds = Math.max((Date.now() - tStart) / 1000, 0.1);

                if (timeLabel) {
                    timeLabel.textContent = `${seconds.toFixed(1)}s`;
                }

                const wordCount = tInput?.value.trim().split(/\s+/).filter(Boolean).length || 0;

                if (tInput && tInput.value.length > 2 && wpmLabel) {
                    wpmLabel.textContent = Math.round((wordCount / seconds) * 60);
                }
            }, 100);
        });
    }

    if (tInput) {
        tInput.addEventListener('input', () => {
            if (!typingRunning) {
                return;
            }

            playSound('type');

            const value = tInput.value;
            let highlightedText = '';

            for (let i = 0; i < currentQuote.length; i++) {
                const char = currentQuote[i];
                const escapedChar = escapeHtml(char);

                if (i < value.length) {
                    const color = value[i] === char ? 'var(--benchmark-green)' : 'var(--benchmark-red)';
                    highlightedText += `<span style="color: ${color}">${escapedChar}</span>`;
                } else {
                    highlightedText += `<span>${escapedChar}</span>`;
                }
            }

            if (tDisplay) {
                tDisplay.innerHTML = highlightedText;
            }

            if (value.trim() === currentQuote.trim()) {
                playSound('success');
                finishTypingTest();
            }
        });
    }

    if (tStopBtn) {
        tStopBtn.addEventListener('click', () => {
            playSound('click');
            finishTypingTest();
        });
    }

    let vLevel = 1;
    let vSequence = [];
    let vUserSequence = [];
    let vCanClick = false;
    let visualRunning = false;

    const vGrid = document.getElementById('visual-grid');
    const vLevelLabel = document.getElementById('visual-level');
    const vStartScreen = document.getElementById('visual-start-screen');
    const vStartBtn = document.getElementById('visual-start-btn');
    const vStopBtn = document.getElementById('visual-stop-btn');

    function stopVisualMemory() {
        playSound('click');

        visualRunning = false;
        vCanClick = false;

        if (vGrid) {
            vGrid.innerHTML = '';
        }

        vStartScreen?.classList.remove('hidden');

        const startTitle = vStartScreen?.querySelector('h3');

        if (startTitle) {
            startTitle.textContent = 'Visual Memory';
        }

        vStopBtn?.classList.add('hidden');

        if (vLevelLabel) {
            vLevelLabel.textContent = '1';
        }

        vLevel = 1;
        vSequence = [];
        vUserSequence = [];
    }

    function finishVisualMemory() {
        playSound('error');

        visualRunning = false;
        vCanClick = false;
        vStopBtn?.classList.add('hidden');

        vSequence.forEach((correctIndex) => {
            vGrid?.children[correctIndex]?.classList.add('correct');
        });

        const visualGridSize = vGrid ? Math.sqrt(vGrid.children.length) : null;

        saveBenchmarkScore('visual', vLevel, `Level ${vLevel}`, buildScoreDetails('visual', {
            level: vLevel,
            sequence_length: vSequence.length,
            grid_size: visualGridSize,
        }));

        window.setTimeout(() => {
            vStartScreen?.classList.remove('hidden');

            const startTitle = vStartScreen?.querySelector('h3');

            if (startTitle) {
                startTitle.textContent = `Game Over! Level ${vLevel}`;
            }
        }, 1200);
    }

    function handleTileClick(index, tile) {
        if (!vCanClick || vUserSequence.includes(index)) {
            return;
        }

        if (index === vSequence[vUserSequence.length]) {
            playSound('type');
            vUserSequence.push(index);
            tile.classList.add('correct');

            if (vUserSequence.length === vSequence.length) {
                playSound('success');
                vCanClick = false;
                vLevel++;
                window.setTimeout(nextLevel, 1000);
            }
        } else {
            tile.classList.add('wrong');
            finishVisualMemory();
        }
    }

    function nextLevel() {
        if (!visualRunning || !vGrid || !vStartScreen || !vStartScreen.classList.contains('hidden')) {
            return;
        }

        vCanClick = false;
        vUserSequence = [];
        vSequence = [];

        if (vLevelLabel) {
            vLevelLabel.textContent = vLevel;
        }

        const size = Math.min(vLevel + 2, 8);

        vGrid.style.gridTemplateColumns = `repeat(${size}, 1fr)`;
        vGrid.innerHTML = '';

        for (let i = 0; i < size * size; i++) {
            const tile = document.createElement('div');
            tile.className = 'visual-tile';
            tile.addEventListener('click', () => handleTileClick(i, tile));
            vGrid.appendChild(tile);
        }

        const count = vLevel + 2;

        while (vSequence.length < count) {
            const randomIndex = Math.floor(Math.random() * vGrid.children.length);

            if (!vSequence.includes(randomIndex)) {
                vSequence.push(randomIndex);
            }
        }

        vSequence.forEach((index, order) => {
            window.setTimeout(() => {
                if (visualRunning && vGrid.children[index] && vStartScreen.classList.contains('hidden')) {
                    playSound('go');
                    vGrid.children[index].classList.add('active');
                }
            }, order * 600 + 500);

            window.setTimeout(() => {
                vGrid.children[index]?.classList.remove('active');
            }, order * 600 + 1000);
        });

        window.setTimeout(() => {
            if (visualRunning && vGrid.innerHTML !== '') {
                vCanClick = true;
            }
        }, vSequence.length * 600 + 500);
    }

    function startVisualMemory() {
        playSound('click');

        visualRunning = true;
        vStartScreen?.classList.add('hidden');
        vStopBtn?.classList.remove('hidden');

        vLevel = 1;
        vSequence = [];
        vUserSequence = [];

        nextLevel();
    }

    if (vStartBtn) {
        vStartBtn.addEventListener('click', startVisualMemory);
    }

    if (vStopBtn) {
        vStopBtn.addEventListener('click', stopVisualMemory);
    }

    updateScoreboard(activeGame);
});
