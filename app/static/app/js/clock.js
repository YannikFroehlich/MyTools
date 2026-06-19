(() => {
    const page = document.querySelector('.clock-page');
    if (!page) return;

    const pad = (value, length = 2) => String(value).padStart(length, '0');

    const i18n = {
        start: page.dataset.clockTextStart || 'Start',
        stop: page.dataset.clockTextStop || 'Stoppen',
        lap: page.dataset.clockTextLap || 'Runde',
        running: page.dataset.clockTextRunning || 'Läuft gerade',
        paused: page.dataset.clockTextPaused || 'Pausiert',
        ready: page.dataset.clockTextReady || 'Bereit',
        setTime: page.dataset.clockTextSetTime || 'Zeit einstellen',
        expired: page.dataset.clockTextExpired || 'Abgelaufen',
        setTimeFirst: page.dataset.clockTextSetTimeFirst || 'Bitte erst eine Zeit einstellen',
        setTimerAlert: page.dataset.clockTextSetTimerAlert || 'Bitte stelle erst eine Timer-Zeit ein.',
        soundSizeAlert: page.dataset.clockTextSoundSizeAlert || 'Der eigene Klingelton darf maximal 5 MB groß sein.',
        overwriteSoundConfirm: page.dataset.clockTextOverwriteSoundConfirm || 'Du hast bereits einen eigenen Klingelton gespeichert. Soll der alte Ton wirklich überschrieben werden?',
    };

    function getIconButtonHtml(iconClass, label, spanLabel = false) {
        const iconHtml = `<i class="${iconClass}"></i>`;
        return spanLabel ? `${iconHtml}<span>${label}</span>` : `${iconHtml} ${label}`;
    }

    function getCurrentLocale() {
        const htmlLang = (document.documentElement.lang || '').trim().replace('_', '-').toLowerCase();

        if (htmlLang.startsWith('en')) {
            return 'en-US';
        }

        if (htmlLang.startsWith('de')) {
            return 'de-DE';
        }

        return navigator.language || 'de-DE';
    }

    function formatClockTime(date, options = {}) {
        return new Intl.DateTimeFormat(getCurrentLocale(), {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hourCycle: 'h23',
            ...options,
        }).format(date);
    }

    function formatClockDate(date, options = {}) {
        return new Intl.DateTimeFormat(getCurrentLocale(), options).format(date);
    }

    function formatStopwatch(ms) {
        const minutes = Math.floor(ms / 60000);
        const seconds = Math.floor((ms % 60000) / 1000);
        const centiseconds = Math.floor((ms % 1000) / 10);
        return `${pad(minutes)}:${pad(seconds)}.${pad(centiseconds)}`;
    }

    function formatTimer(seconds) {
        const safeSeconds = Math.max(0, Math.ceil(seconds));
        const hours = Math.floor(safeSeconds / 3600);
        const minutes = Math.floor((safeSeconds % 3600) / 60);
        const secs = safeSeconds % 60;
        return `${pad(hours)}:${pad(minutes)}:${pad(secs)}`;
    }

    function updateClocks() {
        const now = new Date();
        const localTime = document.querySelector('[data-local-time]');
        const localDate = document.querySelector('[data-local-date]');

        if (localTime) {
            localTime.textContent = formatClockTime(now);
        }

        if (localDate) {
            localDate.textContent = formatClockDate(now, {
                weekday: 'long', day: '2-digit', month: 'long', year: 'numeric'
            });
        }

        document.querySelectorAll('[data-world-clock]').forEach((card) => {
            const timezone = card.dataset.timezone;
            const timeTarget = card.querySelector('[data-world-time]');
            const dateTarget = card.querySelector('[data-world-date]');

            try {
                if (timeTarget) {
                    timeTarget.textContent = formatClockTime(now, { timeZone: timezone });
                }

                if (dateTarget) {
                    dateTarget.textContent = formatClockDate(now, {
                        weekday: 'short', day: '2-digit', month: '2-digit', year: 'numeric', timeZone: timezone
                    });
                }
            } catch (error) {
                if (timeTarget) timeTarget.textContent = '--:--:--';
                if (dateTarget) dateTarget.textContent = timezone;
            }
        });
    }

    updateClocks();
    setInterval(updateClocks, 1000);

    const settingsModal = document.querySelector('[data-clock-settings-modal]');
    const openSettingsButton = document.querySelector('[data-open-clock-settings]');
    const closeSettingsButtons = document.querySelectorAll('[data-close-clock-settings]');

    function openSettings() {
        if (!settingsModal) return;
        settingsModal.hidden = false;
        document.body.classList.add('clock-modal-open');
        settingsModal.querySelector('input, button, select')?.focus();
    }

    function closeSettings() {
        if (!settingsModal) return;
        settingsModal.hidden = true;
        document.body.classList.remove('clock-modal-open');
        openSettingsButton?.focus();
    }

    openSettingsButton?.addEventListener('click', openSettings);
    closeSettingsButtons.forEach((button) => button.addEventListener('click', closeSettings));
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && settingsModal && !settingsModal.hidden) closeSettings();
    });

    let audioContext = null;

    function getVolume() {
        const value = Number(page.dataset.volume || 80);
        return Math.max(0, Math.min(value, 100)) / 100;
    }

    function getSelectedRingtone() {
        const checked = document.querySelector('input[name="ringtone"]:checked');
        return checked ? checked.value : (page.dataset.ringtone || 'bell');
    }

    function playToneSequence(sequence, type = 'sine') {
        audioContext = audioContext || new (window.AudioContext || window.webkitAudioContext)();
        const volume = getVolume();
        const now = audioContext.currentTime;

        sequence.forEach((tone) => {
            const oscillator = audioContext.createOscillator();
            const gain = audioContext.createGain();

            oscillator.type = tone.type || type;
            oscillator.frequency.setValueAtTime(tone.frequency, now + tone.start);
            gain.gain.setValueAtTime(0.0001, now + tone.start);
            gain.gain.exponentialRampToValueAtTime(Math.max(0.0001, volume * 0.35), now + tone.start + 0.02);
            gain.gain.exponentialRampToValueAtTime(0.0001, now + tone.start + tone.duration);

            oscillator.connect(gain);
            gain.connect(audioContext.destination);
            oscillator.start(now + tone.start);
            oscillator.stop(now + tone.start + tone.duration + 0.03);
        });
    }

    function playSound() {
        const ringtone = getSelectedRingtone();
        const customUrl = page.dataset.customSoundUrl;

        if (ringtone === 'custom' && customUrl) {
            const audio = new Audio(customUrl);
            audio.volume = getVolume();
            audio.play().catch(() => playToneSequence([{ frequency: 880, start: 0, duration: 0.25 }]));
            return;
        }

        const sounds = {
            bell: [
                { frequency: 880, start: 0, duration: 0.22 },
                { frequency: 660, start: 0.24, duration: 0.28 }
            ],
            chime: [
                { frequency: 523.25, start: 0, duration: 0.18 },
                { frequency: 659.25, start: 0.18, duration: 0.18 },
                { frequency: 783.99, start: 0.36, duration: 0.34 }
            ],
            digital: [
                { frequency: 1200, start: 0, duration: 0.08, type: 'square' },
                { frequency: 1200, start: 0.16, duration: 0.08, type: 'square' },
                { frequency: 1200, start: 0.32, duration: 0.08, type: 'square' }
            ],
            soft: [
                { frequency: 392, start: 0, duration: 0.28 },
                { frequency: 523.25, start: 0.28, duration: 0.38 }
            ],
            alarm: [
                { frequency: 880, start: 0, duration: 0.16, type: 'square' },
                { frequency: 440, start: 0.18, duration: 0.16, type: 'square' },
                { frequency: 880, start: 0.36, duration: 0.16, type: 'square' },
                { frequency: 440, start: 0.54, duration: 0.16, type: 'square' }
            ]
        };

        playToneSequence(sounds[ringtone] || sounds.bell);
    }

    document.querySelector('[data-test-sound]')?.addEventListener('click', playSound);

    const volumeInput = document.querySelector('[data-volume-input]');
    const volumeValue = document.querySelector('[data-volume-value]');
    volumeInput?.addEventListener('input', () => {
        page.dataset.volume = volumeInput.value;
        if (volumeValue) volumeValue.textContent = volumeInput.value;
    });

    document.querySelectorAll('input[name="ringtone"]').forEach((input) => {
        input.addEventListener('change', () => {
            page.dataset.ringtone = input.value;
        });
    });

    const settingsForm = document.querySelector('[data-clock-settings-form]');
    const customSoundInput = document.querySelector('[data-custom-sound-input]');

    customSoundInput?.addEventListener('change', () => {
        const file = customSoundInput.files?.[0];
        if (!file) return;

        if (file.size > 5 * 1024 * 1024) {
            alert(i18n.soundSizeAlert);
            customSoundInput.value = '';
            return;
        }

        const customRadio = document.querySelector('input[name="ringtone"][value="custom"]');
        if (customRadio) {
            customRadio.checked = true;
            page.dataset.ringtone = 'custom';
        }
    });

    settingsForm?.addEventListener('submit', (event) => {
        const file = customSoundInput?.files?.[0];
        if (!file) return;

        if (settingsForm.dataset.hasCustomSound === 'true') {
            const overwrite = confirm(i18n.overwriteSoundConfirm);
            if (!overwrite) {
                event.preventDefault();
            }
        }
    });

    let stopwatchStart = 0;
    let stopwatchElapsed = 0;
    let stopwatchInterval = null;
    let lapCount = 0;

    const stopwatchDisplay = document.querySelector('[data-stopwatch-display]');
    const stopwatchStartButton = document.querySelector('[data-stopwatch-start]');
    const lapList = document.querySelector('[data-lap-list]');
    const lapEmpty = document.querySelector('[data-lap-empty]');

    function renderStopwatch() {
        const elapsed = stopwatchInterval ? stopwatchElapsed + (performance.now() - stopwatchStart) : stopwatchElapsed;
        if (stopwatchDisplay) stopwatchDisplay.textContent = formatStopwatch(elapsed);
    }

    stopwatchStartButton?.addEventListener('click', () => {
        if (stopwatchInterval) {
            stopwatchElapsed += performance.now() - stopwatchStart;
            clearInterval(stopwatchInterval);
            stopwatchInterval = null;
            stopwatchStartButton.innerHTML = getIconButtonHtml('fa-solid fa-play', i18n.start);
            stopwatchStartButton.classList.remove('is-running');
            renderStopwatch();
            return;
        }

        stopwatchStart = performance.now();
        stopwatchInterval = setInterval(renderStopwatch, 50);
        stopwatchStartButton.innerHTML = getIconButtonHtml('fa-solid fa-pause', i18n.stop);
        stopwatchStartButton.classList.add('is-running');
    });

    document.querySelector('[data-stopwatch-lap]')?.addEventListener('click', () => {
        const elapsed = stopwatchInterval ? stopwatchElapsed + (performance.now() - stopwatchStart) : stopwatchElapsed;
        if (elapsed <= 0 || !lapList) return;

        lapCount += 1;
        const li = document.createElement('li');
        const lapLabel = document.createElement('span');
        const lapTime = document.createElement('strong');
        lapLabel.textContent = `${i18n.lap} ${lapCount}`;
        lapTime.textContent = formatStopwatch(elapsed);
        li.append(lapLabel, lapTime);
        lapList.prepend(li);
        if (lapEmpty) lapEmpty.hidden = true;
    });

    document.querySelector('[data-stopwatch-reset]')?.addEventListener('click', () => {
        clearInterval(stopwatchInterval);
        stopwatchInterval = null;
        stopwatchElapsed = 0;
        lapCount = 0;
        if (lapList) lapList.innerHTML = '';
        if (lapEmpty) lapEmpty.hidden = false;
        if (stopwatchStartButton) {
            stopwatchStartButton.innerHTML = getIconButtonHtml('fa-solid fa-play', i18n.start);
            stopwatchStartButton.classList.remove('is-running');
        }
        renderStopwatch();
    });

    renderStopwatch();

    let timerTotal = 0;
    let timerRemaining = 0;
    let timerInterval = null;
    let timerEndTime = 0;
    let timerWasStarted = false;

    const timerPanel = document.querySelector('[data-timer-panel]');
    const timerDisplay = document.querySelector('[data-timer-display]');
    const timerProgress = document.querySelector('[data-timer-progress]');
    const timerToggleButton = document.querySelector('[data-timer-toggle]');
    const timerApplyButton = document.querySelector('[data-timer-apply]');
    const timerStatus = document.querySelector('[data-timer-status]');
    const timerHoursInput = document.querySelector('[data-timer-hours]');
    const timerMinutesInput = document.querySelector('[data-timer-minutes]');
    const timerSecondsInput = document.querySelector('[data-timer-seconds]');
    const saveHoursInput = document.querySelector('[data-save-hours]');
    const saveMinutesInput = document.querySelector('[data-save-minutes]');
    const saveSecondsInput = document.querySelector('[data-save-seconds]');

    function clampNumber(value, min, max) {
        const number = Number(value);
        if (!Number.isFinite(number)) return min;
        return Math.max(min, Math.min(Math.floor(number), max));
    }

    function getManualSeconds() {
        const hours = clampNumber(timerHoursInput?.value ?? 0, 0, 23);
        const minutes = clampNumber(timerMinutesInput?.value ?? 0, 0, 59);
        const seconds = clampNumber(timerSecondsInput?.value ?? 0, 0, 59);
        return (hours * 3600) + (minutes * 60) + seconds;
    }

    function setManualInputsFromSeconds(totalSeconds) {
        const safe = Math.max(0, Math.floor(Number(totalSeconds) || 0));
        const hours = Math.floor(safe / 3600);
        const minutes = Math.floor((safe % 3600) / 60);
        const seconds = safe % 60;
        if (timerHoursInput) timerHoursInput.value = hours;
        if (timerMinutesInput) timerMinutesInput.value = minutes;
        if (timerSecondsInput) timerSecondsInput.value = seconds;
        updateSaveInputs();
    }

    function updateSaveInputs() {
        const hours = clampNumber(timerHoursInput?.value ?? 0, 0, 23);
        const minutes = clampNumber(timerMinutesInput?.value ?? 0, 0, 59);
        const seconds = clampNumber(timerSecondsInput?.value ?? 0, 0, 59);
        if (saveHoursInput) saveHoursInput.value = hours;
        if (saveMinutesInput) saveMinutesInput.value = minutes;
        if (saveSecondsInput) saveSecondsInput.value = seconds;
    }

    function updateTimerControls(state = null) {
        const running = Boolean(timerInterval);
        timerPanel?.classList.toggle('is-running', running);
        timerToggleButton?.classList.toggle('is-running', running);

        if (timerToggleButton) {
            if (running) {
                timerToggleButton.innerHTML = getIconButtonHtml('fa-solid fa-pause', i18n.stop, true);
            } else {
                timerToggleButton.innerHTML = getIconButtonHtml('fa-solid fa-play', i18n.start, true);
            }
        }

        if (timerApplyButton) timerApplyButton.disabled = running;

        if (timerStatus) {
            if (state) {
                timerStatus.textContent = state;
            } else if (running) {
                timerStatus.textContent = i18n.running;
            } else if (timerWasStarted && timerRemaining > 0) {
                timerStatus.textContent = i18n.paused;
            } else if (timerTotal > 0) {
                timerStatus.textContent = i18n.ready;
            } else {
                timerStatus.textContent = i18n.setTime;
            }
        }
    }

    function renderTimer() {
        if (timerInterval) {
            timerRemaining = Math.max(0, (timerEndTime - Date.now()) / 1000);
        }

        if (timerDisplay) timerDisplay.textContent = formatTimer(timerRemaining);

        if (timerProgress) {
            const progress = timerTotal > 0 ? ((timerTotal - timerRemaining) / timerTotal) * 100 : 0;
            timerProgress.style.width = `${Math.max(0, Math.min(progress, 100))}%`;
        }

        if (timerInterval && timerRemaining <= 0) {
            clearInterval(timerInterval);
            timerInterval = null;
            timerRemaining = 0;
            timerWasStarted = false;
            renderTimer();
            updateTimerControls(i18n.expired);
            playSound();
            return;
        }

        updateTimerControls();
    }

    function loadTimer(seconds, updateInputs = true) {
        clearInterval(timerInterval);
        timerInterval = null;
        timerTotal = Math.max(0, Number(seconds) || 0);
        timerRemaining = timerTotal;
        timerWasStarted = false;
        if (updateInputs) setManualInputsFromSeconds(timerTotal);
        renderTimer();
    }

    function applyManualTimer() {
        updateSaveInputs();
        loadTimer(getManualSeconds(), false);
    }

    [timerHoursInput, timerMinutesInput, timerSecondsInput].forEach((input) => {
        input?.addEventListener('input', () => {
            input.value = clampNumber(input.value, Number(input.min || 0), Number(input.max || 59));
            updateSaveInputs();
            if (!timerInterval && !timerWasStarted) {
                timerTotal = getManualSeconds();
                timerRemaining = timerTotal;
                renderTimer();
            }
        });
    });

    document.querySelectorAll('[data-load-timer]').forEach((button) => {
        button.addEventListener('click', () => {
            loadTimer(button.dataset.timerSeconds);
            document.querySelector('[data-timer-toggle]')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
        });
    });

    timerApplyButton?.addEventListener('click', applyManualTimer);

    timerToggleButton?.addEventListener('click', () => {
        if (timerInterval) {
            renderTimer();
            clearInterval(timerInterval);
            timerInterval = null;
            updateTimerControls(i18n.paused);
            return;
        }

        if (timerRemaining <= 0) {
            applyManualTimer();
        }

        if (timerRemaining <= 0) {
            updateTimerControls(i18n.setTimeFirst);
            return;
        }

        timerWasStarted = true;
        timerEndTime = Date.now() + (timerRemaining * 1000);
        timerInterval = setInterval(renderTimer, 250);
        renderTimer();
    });

    document.querySelector('[data-timer-reset]')?.addEventListener('click', () => {
        clearInterval(timerInterval);
        timerInterval = null;
        timerRemaining = timerTotal || getManualSeconds();
        timerTotal = timerRemaining;
        timerWasStarted = false;
        renderTimer();
        updateTimerControls(i18n.ready);
    });

    document.querySelector('.timer-save-form')?.addEventListener('submit', (event) => {
        updateSaveInputs();
        if (getManualSeconds() <= 0) {
            event.preventDefault();
            alert(i18n.setTimerAlert);
        }
    });

    loadTimer(getManualSeconds(), false);
})();
