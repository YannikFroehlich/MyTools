document.addEventListener('DOMContentLoaded', () => {
    const page = document.querySelector('.benchmark-page');

    if (!page) {
        return;
    }

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
        return value
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#039;');
    }

    function switchGame(gameId, button) {
        playSound('click');
        page.querySelectorAll('.benchmark-tab').forEach((tab) => tab.classList.remove('active'));
        button?.classList.add('active');
        page.querySelectorAll('.game-screen').forEach((screen) => screen.classList.remove('active'));
        document.getElementById(`${gameId}-game`)?.classList.add('active');
    }

    page.querySelectorAll('.benchmark-tab').forEach((button) => {
        button.addEventListener('click', () => switchGame(button.dataset.game, button));
    });

    const logo = page.querySelector('.benchmark-logo');
    logo.addEventListener('click', () => switchGame('reaction', page.querySelector('[data-game="reaction"]')));
    logo.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            switchGame('reaction', page.querySelector('[data-game="reaction"]'));
        }
    });

    const rBox = document.getElementById('reaction-box');
    const rTitle = document.getElementById('r-title');
    const rDesc = document.getElementById('r-desc');
    let rState = 'waiting';
    let rTimer;
    let rStart;

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
        }
    });

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

    function updateAimUI() {
        document.getElementById('aim-count').textContent = aimCount;
    }

    function updateAccuracy() {
        const hits = 30 - aimCount;
        const acc = totalClicks > 0 ? Math.round((hits / totalClicks) * 100) : 100;
        document.getElementById('aim-accuracy-live').textContent = acc;
    }

    function finishAimTrainer() {
        window.clearInterval(aimInterval);
        target.style.display = 'none';
        playSound('finish');
        aimStopBtn.classList.add('hidden');
        document.getElementById('aim-final-time').textContent = `${document.getElementById('aim-timer').textContent}s`;
        document.getElementById('aim-final-accuracy').textContent = `${document.getElementById('aim-accuracy-live').textContent}%`;
        document.getElementById('aim-final-misses').textContent = aimMisses;
        aimResultScreen.classList.remove('hidden');
    }

    function moveTarget() {
        if (aimCount <= 0) {
            playSound('success');
            finishAimTrainer();
            return;
        }

        target.style.display = 'block';
        const x = Math.random() * (aimArea.clientWidth - 60);
        const y = Math.random() * (aimArea.clientHeight - 60);
        target.style.left = `${x}px`;
        target.style.top = `${y}px`;
    }

    function startAimTrainer() {
        aimBtn.classList.add('hidden');
        aimResultScreen.classList.add('hidden');
        aimStopBtn.classList.remove('hidden');
        aimCount = 30;
        aimMisses = 0;
        totalClicks = 0;
        document.getElementById('aim-accuracy-live').textContent = '100';
        document.getElementById('aim-timer').textContent = '0.00';
        aimStart = Date.now();
        aimInterval = window.setInterval(() => {
            document.getElementById('aim-timer').textContent = ((Date.now() - aimStart) / 1000).toFixed(2);
        }, 10);
        updateAimUI();
        moveTarget();
    }

    function resetAimTrainer() {
        aimResultScreen.classList.add('hidden');
        aimBtn.classList.remove('hidden');
        aimStopBtn.classList.add('hidden');
        aimCount = 30;
        aimMisses = 0;
        totalClicks = 0;
        document.getElementById('aim-timer').textContent = '0.00';
        document.getElementById('aim-accuracy-live').textContent = '100';
        updateAimUI();
    }

    aimBtn.addEventListener('click', (event) => {
        event.stopPropagation();
        playSound('click');
        startAimTrainer();
    });
    aimRetryBtn.addEventListener('click', resetAimTrainer);
    aimStopBtn.addEventListener('click', finishAimTrainer);

    aimArea.addEventListener('mousedown', (event) => {
        if (aimBtn.classList.contains('hidden') && aimResultScreen.classList.contains('hidden')) {
            if (target.style.display === 'block' && event.target !== target) {
                playSound('error');
                aimMisses++;
                totalClicks++;
                updateAccuracy();
            }
        }
    });

    target.addEventListener('mousedown', (event) => {
        event.stopPropagation();
        playSound('click');
        aimCount--;
        totalClicks++;
        updateAccuracy();
        updateAimUI();
        moveTarget();
    });

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
    let tStart;
    let tInterval;
    let currentQuote = '';

    async function getRandomQuote() {
        try {
            const controller = new AbortController();
            const timeoutId = window.setTimeout(() => controller.abort(), 3000);
            tDisplay.textContent = 'Lade Text...';
            const response = await fetch('https://dummyjson.com/quotes/random', { signal: controller.signal });
            const data = await response.json();
            const englishQuote = data.quote;
            tDisplay.textContent = 'Übersetze...';
            const transRes = await fetch(`https://api.mymemory.translated.net/get?q=${encodeURIComponent(englishQuote)}&langpair=en|de`, { signal: controller.signal });
            const transData = await transRes.json();
            window.clearTimeout(timeoutId);
            return transData.responseData.translatedText || englishQuote;
        } catch (error) {
            return fallbackQuotes[Math.floor(Math.random() * fallbackQuotes.length)];
        }
    }

    function finishTypingTest() {
        window.clearInterval(tInterval);
        const finalTime = (Date.now() - tStart) / 1000;
        const words = currentQuote.split(/\s+/).length;
        wpmLabel.textContent = Math.round((words / finalTime) * 60);
        tInput.disabled = true;
        tStopBtn.classList.add('hidden');
        tBtn.classList.remove('hidden');
        tBtn.textContent = 'Nächster Test';
    }

    tBtn.addEventListener('click', async () => {
        playSound('click');
        tBtn.disabled = true;
        tBtn.textContent = 'Lädt...';
        currentQuote = await getRandomQuote();
        tBtn.disabled = false;
        tBtn.textContent = 'Test starten';
        tDisplay.textContent = currentQuote;
        tInput.disabled = false;
        tInput.value = '';
        tInput.focus();
        tBtn.classList.add('hidden');
        tStopBtn.classList.remove('hidden');
        window.clearInterval(tInterval);
        tStart = Date.now();
        tInterval = window.setInterval(() => {
            const seconds = (Date.now() - tStart) / 1000;
            timeLabel.textContent = `${seconds.toFixed(1)}s`;
            const wordCount = tInput.value.trim().split(/\s+/).filter(Boolean).length;

            if (tInput.value.length > 2) {
                wpmLabel.textContent = Math.round((wordCount / seconds) * 60);
            }
        }, 100);
    });

    tInput.addEventListener('input', () => {
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

        tDisplay.innerHTML = highlightedText;

        if (value.trim() === currentQuote.trim()) {
            playSound('success');
            finishTypingTest();
        }
    });

    tStopBtn.addEventListener('click', finishTypingTest);

    let vLevel = 1;
    let vSequence = [];
    let vUserSequence = [];
    let vCanClick = false;
    const vGrid = document.getElementById('visual-grid');
    const vLevelLabel = document.getElementById('visual-level');
    const vStartScreen = document.getElementById('visual-start-screen');
    const vStartBtn = document.getElementById('visual-start-btn');
    const vStopBtn = document.getElementById('visual-stop-btn');

    function stopVisualMemory() {
        playSound('click');
        vCanClick = false;
        vGrid.innerHTML = '';
        vStartScreen.classList.remove('hidden');
        vStartScreen.querySelector('h3').textContent = 'Visual Memory';
        vStopBtn.classList.add('hidden');
        vLevelLabel.textContent = '1';
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
            playSound('error');
            tile.classList.add('wrong');
            vCanClick = false;
            vStopBtn.classList.add('hidden');
            vSequence.forEach((correctIndex) => {
                vGrid.children[correctIndex]?.classList.add('correct');
            });
            window.setTimeout(() => {
                vStartScreen.classList.remove('hidden');
                vStartScreen.querySelector('h3').textContent = `Game Over! Level ${vLevel}`;
            }, 1200);
        }
    }

    function nextLevel() {
        if (!vStartScreen.classList.contains('hidden')) {
            return;
        }

        vCanClick = false;
        vUserSequence = [];
        vSequence = [];
        vLevelLabel.textContent = vLevel;

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
                if (vGrid.children[index] && vStartScreen.classList.contains('hidden')) {
                    playSound('go');
                    vGrid.children[index].classList.add('active');
                }
            }, order * 600 + 500);
            window.setTimeout(() => {
                vGrid.children[index]?.classList.remove('active');
            }, order * 600 + 1000);
        });

        window.setTimeout(() => {
            if (vGrid.innerHTML !== '') {
                vCanClick = true;
            }
        }, vSequence.length * 600 + 500);
    }

    function startVisualMemory() {
        playSound('click');
        vStartScreen.classList.add('hidden');
        vStopBtn.classList.remove('hidden');
        vLevel = 1;
        nextLevel();
    }

    vStartBtn.addEventListener('click', startVisualMemory);
    vStopBtn.addEventListener('click', stopVisualMemory);
});
