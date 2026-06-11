document.addEventListener('DOMContentLoaded', () => {
    if (window.__myToolsBaseInitialized) {
        return;
    }
    window.__myToolsBaseInitialized = true;

    const body = document.body;
    /* ── FIXED HEADER ABSTAND ──
       Der Header ist fixed, damit er beim Scrollen immer sichtbar bleibt.
       Da die Header-Höhe auf Handy/Tablet durch Umbruch größer werden kann,
       wird der Abstand darunter automatisch gemessen.
    */
    function syncFixedHeaderOffset() {
        const nav = document.querySelector('nav');

        if (!nav) {
            return;
        }

        document.documentElement.style.setProperty('--nav-height', `${nav.offsetHeight}px`);
    }

    syncFixedHeaderOffset();
    window.addEventListener('resize', syncFixedHeaderOffset);

    if ('ResizeObserver' in window) {
        const nav = document.querySelector('nav');

        if (nav) {
            new ResizeObserver(syncFixedHeaderOffset).observe(nav);
        }
    }

    function hydrateDeferredImages(root = document) {
        root.querySelectorAll('img.js-deferred-image[data-src]').forEach((image) => {
            const source = image.dataset.src;
            const sourceSet = image.dataset.srcset;

            if (!source) {
                return;
            }

            if (sourceSet) {
                image.srcset = sourceSet;
                image.removeAttribute('data-srcset');
            }

            image.src = source;
            image.removeAttribute('data-src');
            image.classList.remove('js-deferred-image');
        });
    }

    document.querySelectorAll('.js-obfuscated-email[data-email-local][data-email-domain]').forEach((element) => {
        const local = element.dataset.emailLocal || '';
        const domain = element.dataset.emailDomain || '';

        if (local && domain) {
            element.textContent = `${local}@${domain}`;
        }
    });

    const themeStorageKey = 'customTheme';
    const themePresetStorageKey = 'customThemePreset';
    const themeSlotsStorageKey = 'customThemeSlots';

    const defaultTheme = {
        navStart: '#1a56d6',
        navEnd: '#5aadee',
        pageBgLight: '#dce5f5',
        pageBgDark: '#12151f',
        cardBg: '#ffffff',
        footerBg: '#ffffff',
        radius: 22,
        pattern: false,
    };

    const darkDefaultTheme = {
        navStart: '#0e2d6e',
        navEnd: '#2a6ea0',
        pageBgLight: '#dce5f5',
        pageBgDark: '#12151f',
        cardBg: '#1c2231',
        footerBg: '#1a1d2b',
        radius: 22,
        pattern: false,
    };

    const themePresets = {
        light: {
            sky: defaultTheme,
            forest: {
                navStart: '#0f766e',
                navEnd: '#34d399',
                pageBgLight: '#dff3ec',
                pageBgDark: '#0f1f1b',
                cardBg: '#f7fffb',
                footerBg: '#f7fffb',
            },
            rose: {
                navStart: '#be185d',
                navEnd: '#fb7185',
                pageBgLight: '#f8dfe8',
                pageBgDark: '#21121b',
                cardBg: '#fff7fa',
                footerBg: '#fff7fa',
            },
            graphite: {
                navStart: '#111827',
                navEnd: '#64748b',
                pageBgLight: '#e2e8f0',
                pageBgDark: '#111827',
                cardBg: '#f8fafc',
                footerBg: '#f8fafc',
            },
            violet: {
                navStart: '#6d28d9',
                navEnd: '#a78bfa',
                pageBgLight: '#ede9fe',
                pageBgDark: '#171026',
                cardBg: '#faf5ff',
                footerBg: '#f5f3ff',
            },
            sunset: {
                navStart: '#ea580c',
                navEnd: '#facc15',
                pageBgLight: '#ffedd5',
                pageBgDark: '#1f130d',
                cardBg: '#fff7ed',
                footerBg: '#fff7ed',
            },
        },
        dark: {
            sky: darkDefaultTheme,
            forest: {
                navStart: '#064e3b',
                navEnd: '#047857',
                pageBgLight: '#dff3ec',
                pageBgDark: '#0f1f1b',
                cardBg: '#13231f',
                footerBg: '#13231f',
            },
            rose: {
                navStart: '#831843',
                navEnd: '#be185d',
                pageBgLight: '#f8dfe8',
                pageBgDark: '#21121b',
                cardBg: '#2a1621',
                footerBg: '#2a1621',
            },
            graphite: {
                navStart: '#020617',
                navEnd: '#334155',
                pageBgLight: '#e2e8f0',
                pageBgDark: '#111827',
                cardBg: '#1f2937',
                footerBg: '#1f2937',
            },
            violet: {
                navStart: '#4c1d95',
                navEnd: '#7c3aed',
                pageBgLight: '#ede9fe',
                pageBgDark: '#171026',
                cardBg: '#211734',
                footerBg: '#211734',
            },
            sunset: {
                navStart: '#7c2d12',
                navEnd: '#c2410c',
                pageBgLight: '#ffedd5',
                pageBgDark: '#1f130d',
                cardBg: '#2c1a10',
                footerBg: '#2c1a10',
            },
        },
    };

    function currentMode() {
        return body.classList.contains('dark-mode') ? 'dark' : 'light';
    }

    function defaultThemeForMode() {
        return currentMode() === 'dark' ? darkDefaultTheme : defaultTheme;
    }

    function hexToRgb(hex) {
        const normalized = hex.replace('#', '');
        const value = parseInt(normalized, 16);

        return {
            r: (value >> 16) & 255,
            g: (value >> 8) & 255,
            b: value & 255,
        };
    }

    function colorDistance(hexA, hexB) {
        const a = hexToRgb(hexA);
        const b = hexToRgb(hexB);

        return Math.abs(a.r - b.r) + Math.abs(a.g - b.g) + Math.abs(a.b - b.b);
    }

    function readableTextColor(backgroundColor) {
        return colorDistance(backgroundColor, '#ffffff') < 210 ? '#1a202c' : '#e2e8f0';
    }

    function rgbString(hex) {
        const { r, g, b } = hexToRgb(hex);

        return `${r}, ${g}, ${b}`;
    }

    function migrateLegacyTheme(theme) {
        const migratedTheme = { ...(theme || {}) };

        if (migratedTheme.pageBg && !migratedTheme.pageBgLight && !migratedTheme.pageBgDark) {
            if (currentMode() === 'dark') {
                migratedTheme.pageBgDark = migratedTheme.pageBg;
                migratedTheme.pageBgLight = defaultTheme.pageBgLight;
            } else {
                migratedTheme.pageBgLight = migratedTheme.pageBg;
                migratedTheme.pageBgDark = darkDefaultTheme.pageBgDark;
            }
        }

        delete migratedTheme.pageBg;
        return migratedTheme;
    }

    function themePageBgForMode(theme) {
        const completeTheme = migrateLegacyTheme(theme);
        return currentMode() === 'dark'
            ? (completeTheme.pageBgDark || darkDefaultTheme.pageBgDark)
            : (completeTheme.pageBgLight || defaultTheme.pageBgLight);
    }

    function applyCustomTheme(theme) {
        const completeTheme = migrateLegacyTheme(theme);
        const pageBackground = themePageBgForMode(completeTheme);

        body.classList.add('custom-theme');

        document.documentElement.style.setProperty('--theme-nav-start', completeTheme.navStart);
        document.documentElement.style.setProperty('--theme-nav-end', completeTheme.navEnd);
        document.documentElement.style.setProperty('--theme-accent-start', completeTheme.navStart);
        document.documentElement.style.setProperty('--theme-accent-end', completeTheme.navEnd);
        document.documentElement.style.setProperty('--theme-accent-text', readableTextColor(completeTheme.navStart));
        document.documentElement.style.setProperty('--theme-accent-rgb', rgbString(completeTheme.navStart));
        document.documentElement.style.setProperty('--theme-accent-end-rgb', rgbString(completeTheme.navEnd));
        document.documentElement.style.setProperty('--theme-page-bg', pageBackground);
        document.documentElement.style.setProperty('--theme-footer-bg', completeTheme.footerBg);
        document.documentElement.style.setProperty('--theme-card-bg', completeTheme.cardBg || completeTheme.footerBg || '#ffffff');
        document.documentElement.style.setProperty('--theme-card-radius', `${completeTheme.radius || 22}px`);
        document.documentElement.style.setProperty('--theme-text', readableTextColor(pageBackground));
        body.classList.toggle('theme-pattern-mode', Boolean(completeTheme.pattern));
        document.documentElement.style.setProperty('--theme-footer-text', readableTextColor(completeTheme.footerBg));
        document.documentElement.style.setProperty('--theme-footer-border', 'rgba(0, 0, 0, 0.08)');
        document.documentElement.style.setProperty('--theme-nav-shadow', `rgba(${rgbString(completeTheme.navStart)}, 0.28)`);
    }

    function clearCustomTheme() {
        body.classList.remove('custom-theme');
        body.classList.remove('theme-pattern-mode');

        [
            '--theme-nav-start',
            '--theme-nav-end',
            '--theme-accent-start',
            '--theme-accent-end',
            '--theme-accent-text',
            '--theme-accent-rgb',
            '--theme-accent-end-rgb',
            '--theme-page-bg',
            '--theme-footer-bg',
            '--theme-card-bg',
            '--theme-card-radius',
            '--theme-text',
            '--theme-footer-text',
            '--theme-footer-border',
            '--theme-nav-shadow',
        ].forEach((property) => document.documentElement.style.removeProperty(property));
    }

    function loadCustomTheme() {
        try {
            const storedTheme = JSON.parse(localStorage.getItem(themeStorageKey));

            if (storedTheme) {
                const migratedTheme = migrateLegacyTheme(storedTheme);
                applyCustomTheme(migratedTheme);
                localStorage.setItem(themeStorageKey, JSON.stringify(migratedTheme));
                return migratedTheme;
            }
        } catch (error) {
            localStorage.removeItem(themeStorageKey);
        }

        return null;
    }

    /* ── THEME FLASH OVERLAY ── */
    const flash = document.createElement('div');
    flash.className = 'theme-flash';
    document.body.appendChild(flash);

    /* ── DARK MODE LADEN ── */
    if (localStorage.getItem('theme') === 'dark') {
        const noTrans = document.createElement('style');
        noTrans.textContent = '*, *::before, *::after { transition: none !important; }';

        document.head.appendChild(noTrans);
        body.classList.add('dark-mode');

        void document.body.offsetHeight;

        document.head.removeChild(noTrans);
    }

    let activeCustomTheme = loadCustomTheme();
    let activeThemePreset = localStorage.getItem(themePresetStorageKey);

    /* ── DARK MODE BUTTON ── */
    const darkModeButton = document.getElementById('darkmode-button');

    if (darkModeButton) {
        darkModeButton.addEventListener('click', () => {
            darkModeButton.classList.remove('pulsing');
            void darkModeButton.offsetWidth;
            darkModeButton.classList.add('pulsing');

            darkModeButton.addEventListener(
                'animationend',
                () => darkModeButton.classList.remove('pulsing'),
                { once: true }
            );

            const goingDark = !body.classList.contains('dark-mode');

            flash.style.background = goingDark
                ? 'rgba(15, 22, 55, 1)'
                : 'rgba(235, 244, 255, 1)';

            flash.classList.remove('flash-in');
            void flash.offsetWidth;
            flash.classList.add('flash-in');

            body.classList.toggle('dark-mode');

            localStorage.setItem(
                'theme',
                body.classList.contains('dark-mode') ? 'dark' : 'light'
            );

            if (activeThemePreset) {
                const preset = themePresets[currentMode()][activeThemePreset] || defaultThemeForMode();

                activeCustomTheme = { ...preset };
                syncThemeInputs(activeCustomTheme);
                applyCustomTheme(activeCustomTheme);
                localStorage.setItem(themeStorageKey, JSON.stringify(activeCustomTheme));
            } else if (activeCustomTheme) {
                syncThemeInputs(activeCustomTheme);
                applyCustomTheme(activeCustomTheme);
                localStorage.setItem(themeStorageKey, JSON.stringify(activeCustomTheme));
            } else {
                syncThemeInputs(defaultThemeForMode());
            }
        });
    }

    /* ── THEME EDITOR ── */
    const themeEditorButton = document.getElementById('theme-editor-button');
    const themeEditorPanel = document.getElementById('theme-editor-panel');
    const themeEditorClose = document.getElementById('theme-editor-close');
    const themeResetButton = document.getElementById('theme-reset-button');

    const themeInputs = {
        navStart: document.getElementById('theme-nav-start'),
        navEnd: document.getElementById('theme-nav-end'),
        pageBgLight: document.getElementById('theme-page-bg-light'),
        pageBgDark: document.getElementById('theme-page-bg-dark'),
        cardBg: document.getElementById('theme-card-bg'),
        footerBg: document.getElementById('theme-footer-bg'),
        radius: document.getElementById('theme-radius'),
    };

    const themeRadiusValue = document.getElementById('theme-radius-value');
    const themeSaveHint = document.getElementById('theme-save-hint');
    const themeRandomButton = document.getElementById('theme-random-button');

    function normalizedTheme(theme) {
        return { ...defaultThemeForMode(), ...migrateLegacyTheme(theme || {}) };
    }

    function updateThemeRadiusLabel(theme) {
        if (themeRadiusValue) {
            themeRadiusValue.textContent = `${Number(theme.radius || defaultTheme.radius)}px`;
        }
    }

    function syncThemeInputs(theme) {
        const completeTheme = normalizedTheme(theme);

        Object.entries(themeInputs).forEach(([key, input]) => {
            if (input && completeTheme[key] !== undefined) {
                input.value = completeTheme[key];
            }
        });

        updateThemeRadiusLabel(completeTheme);
    }

    function updateActivePresetButton(presetName) {
        document.querySelectorAll('.theme-preset').forEach((button) => {
            button.classList.toggle('is-active', Boolean(presetName && button.dataset.preset === presetName));
        });
    }

    function showThemeSaveHint() {
        if (!themeSaveHint) {
            return;
        }

        themeSaveHint.classList.remove('is-visible');
        void themeSaveHint.offsetWidth;
        themeSaveHint.classList.add('is-visible');

        window.clearTimeout(showThemeSaveHint.timeoutId);
        showThemeSaveHint.timeoutId = window.setTimeout(() => {
            themeSaveHint.classList.remove('is-visible');
        }, 1200);
    }

    function loadThemeSlots() {
        try {
            const slots = JSON.parse(localStorage.getItem(themeSlotsStorageKey));
            return Array.from({ length: 3 }, (_, index) => slots?.[index] || null);
        } catch (error) {
            localStorage.removeItem(themeSlotsStorageKey);
            return [null, null, null];
        }
    }

    let themeSlots = loadThemeSlots();

    function saveThemeSlots() {
        localStorage.setItem(themeSlotsStorageKey, JSON.stringify(themeSlots));
    }

    function slotColorPreview(theme) {
        if (!theme) {
            return '';
        }

        return `linear-gradient(135deg, ${theme.navStart}, ${theme.navEnd})`;
    }

    function updateThemeSlotsUi() {
        document.querySelectorAll('.theme-slot').forEach((slotElement) => {
            const slotIndex = Number(slotElement.dataset.slot);
            const slotTheme = themeSlots[slotIndex];
            const status = slotElement.querySelector('[data-slot-status]');
            const loadButton = slotElement.querySelector('[data-slot-load]');
            const deleteButton = slotElement.querySelector('[data-slot-delete]');

            slotElement.classList.toggle('is-filled', Boolean(slotTheme));
            slotElement.style.setProperty('--slot-preview', slotColorPreview(slotTheme) || 'linear-gradient(135deg, #cbd5e1, #94a3b8)');

            if (status) {
                status.textContent = slotTheme ? 'Gespeichert' : 'Leer';
            }

            if (loadButton) {
                loadButton.disabled = !slotTheme;
            }

            if (deleteButton) {
                deleteButton.disabled = !slotTheme;
            }
        });
    }

    function readThemeInputs() {
        return {
            navStart: themeInputs.navStart?.value || defaultTheme.navStart,
            navEnd: themeInputs.navEnd?.value || defaultTheme.navEnd,
            pageBgLight: themeInputs.pageBgLight?.value || defaultTheme.pageBgLight,
            pageBgDark: themeInputs.pageBgDark?.value || darkDefaultTheme.pageBgDark,
            cardBg: themeInputs.cardBg?.value || defaultTheme.cardBg,
            footerBg: themeInputs.footerBg?.value || defaultTheme.footerBg,
            radius: Number(themeInputs.radius?.value || defaultTheme.radius),
            pattern: document.getElementById('theme-pattern-toggle')?.classList.contains('is-active') || false,
        };
    }

    function saveThemeFromInputs() {
        activeThemePreset = null;
        localStorage.removeItem(themePresetStorageKey);
        updateActivePresetButton(null);

        activeCustomTheme = readThemeInputs();
        applyCustomTheme(activeCustomTheme);
        updateThemeRadiusLabel(activeCustomTheme);
        localStorage.setItem(themeStorageKey, JSON.stringify(activeCustomTheme));
        showThemeSaveHint();
    }

    if (themeEditorButton && themeEditorPanel) {
        syncThemeInputs(activeCustomTheme || defaultThemeForMode());
        updateActivePresetButton(activeThemePreset);
        document.getElementById('theme-pattern-toggle')?.classList.toggle('is-active', Boolean((activeCustomTheme || {}).pattern));
        updateThemeSlotsUi();

        themeEditorButton.addEventListener('click', (event) => {
            event.stopPropagation();
            themeEditorPanel.classList.toggle('open');
        });

        themeEditorClose?.addEventListener('click', () => {
            themeEditorPanel.classList.remove('open');
        });

        Object.values(themeInputs).forEach((input) => {
            input?.addEventListener('input', saveThemeFromInputs);
        });

        document.querySelectorAll('[data-slot-save]').forEach((button) => {
            button.addEventListener('click', () => {
                const slotIndex = Number(button.dataset.slotSave);
                themeSlots[slotIndex] = { ...readThemeInputs() };
                saveThemeSlots();
                updateThemeSlotsUi();
                showThemeSaveHint();
            });
        });

        document.querySelectorAll('[data-slot-load]').forEach((button) => {
            button.addEventListener('click', () => {
                const slotIndex = Number(button.dataset.slotLoad);
                const slotTheme = themeSlots[slotIndex];

                if (!slotTheme) {
                    return;
                }

                activeThemePreset = null;
                localStorage.removeItem(themePresetStorageKey);
                updateActivePresetButton(null);

                activeCustomTheme = normalizedTheme(slotTheme);
                syncThemeInputs(activeCustomTheme);
                document.getElementById('theme-pattern-toggle')?.classList.toggle('is-active', Boolean(activeCustomTheme.pattern));
                applyCustomTheme(activeCustomTheme);
                localStorage.setItem(themeStorageKey, JSON.stringify(activeCustomTheme));
                showThemeSaveHint();
            });
        });

        document.querySelectorAll('[data-slot-delete]').forEach((button) => {
            button.addEventListener('click', () => {
                const slotIndex = Number(button.dataset.slotDelete);
                themeSlots[slotIndex] = null;
                saveThemeSlots();
                updateThemeSlotsUi();
                showThemeSaveHint();
            });
        });

        document.getElementById('theme-pattern-toggle')?.addEventListener('click', () => {
            document.getElementById('theme-pattern-toggle')?.classList.toggle('is-active');
            saveThemeFromInputs();
        });

        document.querySelectorAll('.theme-preset').forEach((button) => {
            button.addEventListener('click', () => {
                const preset = normalizedTheme(themePresets[currentMode()][button.dataset.preset]);

                syncThemeInputs(preset);
                document.getElementById('theme-pattern-toggle')?.classList.remove('is-active');
                activeThemePreset = button.dataset.preset;
                activeCustomTheme = { ...preset };

                applyCustomTheme(activeCustomTheme);
                updateActivePresetButton(activeThemePreset);
                showThemeSaveHint();

                localStorage.setItem(themePresetStorageKey, activeThemePreset);
                localStorage.setItem(themeStorageKey, JSON.stringify(activeCustomTheme));
            });
        });

        themeRandomButton?.addEventListener('click', () => {
            const hue = Math.floor(Math.random() * 360);
            const secondHue = (hue + 38) % 360;
            const isDark = currentMode() === 'dark';

            activeThemePreset = null;
            localStorage.removeItem(themePresetStorageKey);
            updateActivePresetButton(null);

            const hslToHex = (h, s, l) => {
                const saturation = s / 100;
                const lightness = l / 100;
                const k = (n) => (n + h / 30) % 12;
                const a = saturation * Math.min(lightness, 1 - lightness);
                const f = (n) => lightness - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
                const toHex = (value) => Math.round(255 * value).toString(16).padStart(2, '0');

                return `#${toHex(f(0))}${toHex(f(8))}${toHex(f(4))}`;
            };

            activeCustomTheme = {
                navStart: hslToHex(hue, 72, isDark ? 36 : 44),
                navEnd: hslToHex(secondHue, 82, isDark ? 48 : 62),
                pageBgLight: hslToHex(hue, 58, 92),
                pageBgDark: hslToHex(hue, 26, 10),
                cardBg: hslToHex(hue, isDark ? 24 : 60, isDark ? 15 : 98),
                footerBg: hslToHex(hue, isDark ? 24 : 55, isDark ? 13 : 97),
                radius: Number(themeInputs.radius?.value || defaultTheme.radius),
                pattern: document.getElementById('theme-pattern-toggle')?.classList.contains('is-active') || false,
            };

            syncThemeInputs(activeCustomTheme);
            applyCustomTheme(activeCustomTheme);
            localStorage.setItem(themeStorageKey, JSON.stringify(activeCustomTheme));
            showThemeSaveHint();
        });

        themeResetButton?.addEventListener('click', () => {
            activeCustomTheme = null;
            activeThemePreset = null;

            localStorage.removeItem(themeStorageKey);
            localStorage.removeItem(themePresetStorageKey);

            syncThemeInputs(defaultThemeForMode());
            updateActivePresetButton(null);
            document.getElementById('theme-pattern-toggle')?.classList.remove('is-active');
            clearCustomTheme();
            showThemeSaveHint();
        });

        document.addEventListener('click', (event) => {
            const clickedPanel = themeEditorPanel.contains(event.target);
            const clickedButton = themeEditorButton.contains(event.target);

            if (!clickedPanel && !clickedButton) {
                themeEditorPanel.classList.remove('open');
            }
        });

        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') {
                themeEditorPanel.classList.remove('open');
            }
        });
    }


    /* ── LIVE BENACHRICHTIGUNGS-ZÄHLER ── */
    const liveStatusUrl = body.dataset.liveStatusUrl;
    const notificationCountsUrl = body.dataset.notificationCountsUrl;
    const notificationPollMs = liveStatusUrl ? 5000 : 3000;
    const liveStatusState = window.__myToolsLiveStatusState || {
        inFlight: false,
        lastFetchAt: 0,
        intervalId: null,
    };
    window.__myToolsLiveStatusState = liveStatusState;

    function setNotificationBadgeValue(badge, value) {
        const normalizedValue = Number.isFinite(Number(value)) ? Number(value) : 0;
        const oldValue = Number(badge.dataset.currentValue ?? badge.textContent.trim() ?? 0);

        badge.textContent = String(normalizedValue);
        badge.dataset.currentValue = String(normalizedValue);

        const singularLabel = badge.dataset.labelSingular || '';
        const pluralLabel = badge.dataset.labelPlural || singularLabel;
        const label = normalizedValue === 1 ? singularLabel : pluralLabel;

        if (label) {
            badge.setAttribute('aria-label', `${normalizedValue} ${label}`);
            badge.title = `${normalizedValue} ${label}`;
        }

        if (oldValue !== normalizedValue) {
            badge.classList.remove('badge-updated');
            void badge.offsetWidth;
            badge.classList.add('badge-updated');

            window.setTimeout(() => {
                badge.classList.remove('badge-updated');
            }, 180);
        }
    }

    function updateProfileNotificationDot(counts) {
        const dot = document.querySelector('.js-profile-notification-dot');

        if (!dot || !counts) {
            return;
        }

        const total = Number(counts.total_notifications ?? 0);
        dot.classList.toggle('is-visible', total > 0);
    }

    function updateNotificationBadges(counts) {
        if (!counts) {
            return;
        }

        document.querySelectorAll('.js-notification-badge[data-notification-key]').forEach((badge) => {
            const key = badge.dataset.notificationKey;

            if (Object.prototype.hasOwnProperty.call(counts, key)) {
                setNotificationBadgeValue(badge, counts[key]);
            }
        });

        updateProfileNotificationDot(counts);
    }


    function collectPresenceUserIds() {
        return Array.from(new Set(
            Array.from(document.querySelectorAll('[data-presence-user-id]'))
                .map((element) => Number.parseInt(element.dataset.presenceUserId || '', 10))
                .filter(Number.isFinite)
        )).slice(0, 50);
    }

    function applyPresenceProfile(profile) {
        const userId = Number(profile.userId);
        if (!Number.isFinite(userId)) {
            return;
        }

        const isOnline = Boolean(profile.isOnline);
        const activityStatus = profile.activityStatus || '';
        const statusLine = profile.statusLine || '';

        document.querySelectorAll(`[data-presence-user-id="${userId}"]`).forEach((element) => {
            const target = element.dataset.presenceTarget;

            if (target === 'dot') {
                element.hidden = !isOnline;
                return;
            }

            if (target === 'activity-detail') {
                element.textContent = activityStatus;
                element.hidden = !activityStatus;
                return;
            }

            if (target === 'status') {
                element.textContent = statusLine;
                element.classList.toggle('is-online', isOnline);
            }
        });
    }

    function updatePresenceProfiles(profiles) {
        if (!Array.isArray(profiles)) {
            return;
        }

        profiles.forEach(applyPresenceProfile);
    }


    const notificationCenterUrl = body.dataset.notificationCenterUrl;
    const notificationDismissUrl = body.dataset.notificationDismissUrl;
    const notificationDismissAllUrl = body.dataset.notificationDismissAllUrl;
    const notificationList = document.querySelector('.js-notification-list');
    const notificationTotal = document.querySelector('.js-notification-total');
    const notificationClearAllButton = document.querySelector('.js-notification-clear-all');

    function escapeHtml(value) {
        return String(value ?? '')
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#039;');
    }

    function getCookie(name) {
        const cookies = document.cookie ? document.cookie.split(';') : [];

        for (const cookie of cookies) {
            const trimmed = cookie.trim();
            if (trimmed.startsWith(`${name}=`)) {
                return decodeURIComponent(trimmed.slice(name.length + 1));
            }
        }

        return '';
    }

    async function postNotificationAction(url, data = {}) {
        if (!url) return;

        const formData = new FormData();
        Object.entries(data).forEach(([key, value]) => formData.append(key, value));

        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCookie('csrftoken'),
                'Accept': 'application/json',
            },
            body: formData,
            cache: 'no-store',
        });

        if (!response.ok) return;
        const payload = await response.json();

        if (payload.ok) {
            updateNotificationBadges(payload.counts);
            updateNotificationCenter(payload.counts, payload.items);
        }
    }

    function renderNotificationItems(items = []) {
        if (!notificationList) return;

        if (!items.length) {
            notificationList.innerHTML = `
                <div class="notification-center-empty">
                    <i class="fa-regular fa-bell"></i>
                    <p>Keine neuen Benachrichtigungen.</p>
                </div>
            `;
            return;
        }

        notificationList.innerHTML = items.map((item) => `
            <div class="notification-center-item is-${escapeHtml(item.type)}" data-notification-key="${escapeHtml(item.key || '')}">
                <a class="notification-center-item-link" href="${escapeHtml(item.url || '#')}">
                    <span class="notification-center-item-icon"><i class="${escapeHtml(item.icon || 'fa-solid fa-bell')}"></i></span>
                    <span class="notification-center-item-main">
                        <strong>${escapeHtml(item.title)}</strong>
                        <small>${escapeHtml(item.text)}</small>
                    </span>
                    ${item.action_label ? `<em>${escapeHtml(item.action_label)}</em>` : ''}
                    ${Number(item.badge || 0) > 1 ? `<b>${escapeHtml(item.badge)}</b>` : ''}
                </a>
                <button class="notification-item-delete js-notification-delete" type="button" title="Benachrichtigung löschen" aria-label="Benachrichtigung löschen">
                    <i class="fa-solid fa-xmark"></i>
                </button>
            </div>
        `).join('');
    }

    function updateNotificationCenter(counts, items) {
        if (notificationTotal && counts) {
            notificationTotal.textContent = String(Number(counts.total_notifications || 0));
        }
        if (notificationClearAllButton && counts) {
            notificationClearAllButton.disabled = Number(counts.total_notifications || 0) <= 0;
        }
        if (Array.isArray(items)) {
            renderNotificationItems(items);
        }
    }

    if (notificationList) {
        notificationList.addEventListener('click', (event) => {
            const deleteButton = event.target.closest('.js-notification-delete');
            if (!deleteButton) return;

            event.preventDefault();
            event.stopPropagation();

            const item = deleteButton.closest('.notification-center-item');
            const key = item?.dataset.notificationKey || '';
            if (!key) return;

            deleteButton.disabled = true;
            postNotificationAction(notificationDismissUrl, { key }).catch(() => {
                deleteButton.disabled = false;
            });
        });
    }

    if (notificationClearAllButton) {
        notificationClearAllButton.addEventListener('click', (event) => {
            event.preventDefault();
            event.stopPropagation();

            notificationClearAllButton.disabled = true;
            postNotificationAction(notificationDismissAllUrl).catch(() => {
                notificationClearAllButton.disabled = false;
            });
        });
    }

    async function refreshNotificationCounts(options = {}) {
        if ((!liveStatusUrl && !notificationCountsUrl) || document.hidden) {
            return;
        }

        const includeItems = Boolean(options.includeItems);
        const force = Boolean(options.force);
        const now = Date.now();

        if (liveStatusState.inFlight) {
            return;
        }

        if (!force && now - liveStatusState.lastFetchAt < 1200) {
            return;
        }

        liveStatusState.inFlight = true;
        liveStatusState.lastFetchAt = now;

        try {
            let url = null;

            if (liveStatusUrl) {
                url = new URL(liveStatusUrl, window.location.origin);
                const presenceIds = collectPresenceUserIds();

                if (presenceIds.length) {
                    url.searchParams.set('ids', presenceIds.join(','));
                }

                if (includeItems) {
                    url.searchParams.set('items', '1');
                }
            } else {
                url = new URL((includeItems && notificationCenterUrl) ? notificationCenterUrl : notificationCountsUrl, window.location.origin);
            }

            url.searchParams.set('_', String(Date.now()));

            const response = await fetch(url.toString(), {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'Accept': 'application/json',
                },
                cache: 'no-store',
                credentials: 'same-origin',
            });

            if (!response.ok) {
                return;
            }

            const data = await response.json();

            if (data.ok) {
                updateNotificationBadges(data.counts);
                updateNotificationCenter(data.counts, data.items);
                updatePresenceProfiles(data.profiles);
            }
        } catch (error) {
            // Wenn der Server kurz nicht erreichbar ist, probieren wir es beim nächsten Intervall erneut.
        } finally {
            liveStatusState.inFlight = false;
        }
    }

    if ((liveStatusUrl || notificationCountsUrl) && !liveStatusState.intervalId) {
        refreshNotificationCounts({ includeItems: false, force: true });
        liveStatusState.intervalId = window.setInterval(() => refreshNotificationCounts({
            includeItems: document.getElementById('notification-center-dropdown')?.classList.contains('open'),
        }), notificationPollMs);
        window.addEventListener('focus', () => refreshNotificationCounts({ includeItems: false, force: true }));
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                refreshNotificationCounts({ includeItems: false, force: true });
            }
        });
    }

    /* ── DROPDOWN MENÜS ── */

    function closeAllDropdowns(exceptDropdown = null, exceptButton = null) {
        document.querySelectorAll('.menu-dropdown.open, .profile-menu-dropdown.open, .notification-center-dropdown.open').forEach((dropdown) => {
            if (dropdown !== exceptDropdown) {
                dropdown.classList.remove('open');
            }
        });

        document.querySelectorAll('.menu-button.active, .profile-menu-button.active, .notification-center-button.active').forEach((button) => {
            if (button !== exceptButton) {
                button.classList.remove('active');
                button.setAttribute('aria-expanded', 'false');
            }
        });
    }

    function setupLibraryMenuFilters() {
        const normalize = (value) => String(value || '')
            .toLowerCase()
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '');

        document.querySelectorAll('.games-menu-panel').forEach((menu) => {
            const searchInput = menu.querySelector('[data-menu-search], #games-menu-search');

            if (!searchInput) {
                return;
            }

            const cards = Array.from(menu.querySelectorAll('[data-menu-card], [data-game-card]'));
            const sections = Array.from(menu.querySelectorAll('[data-menu-section], [data-game-section]'));
            const emptyState = menu.querySelector('[data-menu-empty], [data-game-empty]');

            function filterMenuCards() {
                const query = normalize(searchInput.value);
                let visibleCards = 0;

                cards.forEach((card) => {
                    const searchText = normalize([
                        card.dataset.menuName,
                        card.dataset.menuCategory,
                        card.dataset.gameName,
                        card.dataset.gameCategory,
                        card.textContent,
                    ].join(' '));
                    const isVisible = !query || searchText.includes(query);

                    card.hidden = !isVisible;

                    if (isVisible) {
                        visibleCards += 1;
                    }
                });

                sections.forEach((section) => {
                    section.hidden = !section.querySelector('[data-menu-card]:not([hidden]), [data-game-card]:not([hidden])');
                });

                if (emptyState) {
                    emptyState.hidden = visibleCards > 0;
                }
            }

            searchInput.addEventListener('input', filterMenuCards);
        });
    }

    function setupDropdown(buttonId, dropdownId) {
        const button = document.getElementById(buttonId);
        const dropdown = document.getElementById(dropdownId);

        if (!button || !dropdown) {
            return;
        }

        button.setAttribute('aria-expanded', 'false');

        button.addEventListener('click', (event) => {
            event.preventDefault();
            event.stopPropagation();

            const shouldOpen = !dropdown.classList.contains('open');

            closeAllDropdowns(dropdown, button);

            dropdown.classList.toggle('open', shouldOpen);
            button.classList.toggle('active', shouldOpen);
            button.setAttribute('aria-expanded', String(shouldOpen));

            if (shouldOpen) {
                hydrateDeferredImages(dropdown);
            }

            if (shouldOpen && buttonId === 'notification-center-button') {
                refreshNotificationCounts({ includeItems: true });
            }

            if (shouldOpen && dropdown.classList.contains('games-menu-panel') && window.matchMedia('(pointer: fine)').matches) {
                window.setTimeout(() => {
                    dropdown.querySelector('[data-menu-search], #games-menu-search')?.focus({ preventScroll: true });
                }, 40);
            }
        });

        dropdown.addEventListener('click', (event) => {
            event.stopPropagation();
        });

        dropdown.querySelectorAll('a').forEach((link) => {
            link.addEventListener('click', () => {
                closeAllDropdowns();
            });
        });

        dropdown.querySelectorAll('form').forEach((form) => {
            form.addEventListener('submit', () => {
                closeAllDropdowns();
            });
        });
    }

    setupLibraryMenuFilters();
    setupDropdown('games-menu-button', 'games-menu-dropdown');
    setupDropdown('google-apps-menu-button', 'google-apps-menu-dropdown');
    setupDropdown('menu-button', 'menu-dropdown');
    setupDropdown('profile-menu-button', 'profile-menu-dropdown');
    setupDropdown('notification-center-button', 'notification-center-dropdown');

    document.addEventListener('click', () => {
        closeAllDropdowns();
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            closeAllDropdowns();
        }
    });
});
