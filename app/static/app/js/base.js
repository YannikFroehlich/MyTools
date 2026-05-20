document.addEventListener('DOMContentLoaded', () => {
    const body = document.body;
    const themeStorageKey = 'customTheme';
    const themePresetStorageKey = 'customThemePreset';

    const defaultTheme = {
        navStart: '#1a56d6',
        navEnd: '#5aadee',
        pageBg: '#dce5f5',
        footerBg: '#ffffff',
    };

    const darkDefaultTheme = {
        navStart: '#0e2d6e',
        navEnd: '#2a6ea0',
        pageBg: '#12151f',
        footerBg: '#1a1d2b',
    };

    const themePresets = {
        light: {
            sky: defaultTheme,
            forest: {
                navStart: '#0f766e',
                navEnd: '#34d399',
                pageBg: '#dff3ec',
                footerBg: '#f7fffb',
            },
            rose: {
                navStart: '#be185d',
                navEnd: '#fb7185',
                pageBg: '#f8dfe8',
                footerBg: '#fff7fa',
            },
            graphite: {
                navStart: '#111827',
                navEnd: '#64748b',
                pageBg: '#e2e8f0',
                footerBg: '#f8fafc',
            },
        },
        dark: {
            sky: darkDefaultTheme,
            forest: {
                navStart: '#064e3b',
                navEnd: '#047857',
                pageBg: '#0f1f1b',
                footerBg: '#13231f',
            },
            rose: {
                navStart: '#831843',
                navEnd: '#be185d',
                pageBg: '#21121b',
                footerBg: '#2a1621',
            },
            graphite: {
                navStart: '#020617',
                navEnd: '#334155',
                pageBg: '#111827',
                footerBg: '#1f2937',
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

    function applyCustomTheme(theme) {
        body.classList.add('custom-theme');

        document.documentElement.style.setProperty('--theme-nav-start', theme.navStart);
        document.documentElement.style.setProperty('--theme-nav-end', theme.navEnd);
        document.documentElement.style.setProperty('--theme-accent-start', theme.navStart);
        document.documentElement.style.setProperty('--theme-accent-end', theme.navEnd);
        document.documentElement.style.setProperty('--theme-accent-text', readableTextColor(theme.navStart));
        document.documentElement.style.setProperty('--theme-accent-rgb', rgbString(theme.navStart));
        document.documentElement.style.setProperty('--theme-accent-end-rgb', rgbString(theme.navEnd));
        document.documentElement.style.setProperty('--theme-page-bg', theme.pageBg);
        document.documentElement.style.setProperty('--theme-footer-bg', theme.footerBg);
        document.documentElement.style.setProperty('--theme-text', readableTextColor(theme.pageBg));
        document.documentElement.style.setProperty('--theme-footer-text', readableTextColor(theme.footerBg));
        document.documentElement.style.setProperty('--theme-footer-border', 'rgba(0, 0, 0, 0.08)');
        document.documentElement.style.setProperty('--theme-nav-shadow', `rgba(${rgbString(theme.navStart)}, 0.28)`);
    }

    function clearCustomTheme() {
        body.classList.remove('custom-theme');

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
                applyCustomTheme(storedTheme);
                return storedTheme;
            }
        } catch (error) {
            localStorage.removeItem(themeStorageKey);
        }

        return null;
    }

    let activeCustomTheme = loadCustomTheme();
    let activeThemePreset = localStorage.getItem(themePresetStorageKey);

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
            } else if (!activeCustomTheme) {
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
        pageBg: document.getElementById('theme-page-bg'),
        footerBg: document.getElementById('theme-footer-bg'),
    };

    function syncThemeInputs(theme) {
        Object.entries(themeInputs).forEach(([key, input]) => {
            if (input && theme[key]) {
                input.value = theme[key];
            }
        });
    }

    function readThemeInputs() {
        return {
            navStart: themeInputs.navStart?.value || defaultTheme.navStart,
            navEnd: themeInputs.navEnd?.value || defaultTheme.navEnd,
            pageBg: themeInputs.pageBg?.value || defaultTheme.pageBg,
            footerBg: themeInputs.footerBg?.value || defaultTheme.footerBg,
        };
    }

    function saveThemeFromInputs() {
        activeThemePreset = null;
        localStorage.removeItem(themePresetStorageKey);

        activeCustomTheme = readThemeInputs();
        applyCustomTheme(activeCustomTheme);
        localStorage.setItem(themeStorageKey, JSON.stringify(activeCustomTheme));
    }

    if (themeEditorButton && themeEditorPanel) {
        syncThemeInputs(activeCustomTheme || defaultThemeForMode());

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

        document.querySelectorAll('.theme-preset').forEach((button) => {
            button.addEventListener('click', () => {
                const preset = themePresets[currentMode()][button.dataset.preset] || defaultThemeForMode();

                syncThemeInputs(preset);
                activeThemePreset = button.dataset.preset;
                activeCustomTheme = { ...preset };

                applyCustomTheme(activeCustomTheme);

                localStorage.setItem(themePresetStorageKey, activeThemePreset);
                localStorage.setItem(themeStorageKey, JSON.stringify(activeCustomTheme));
            });
        });

        themeResetButton?.addEventListener('click', () => {
            activeCustomTheme = null;
            activeThemePreset = null;

            localStorage.removeItem(themeStorageKey);
            localStorage.removeItem(themePresetStorageKey);

            syncThemeInputs(defaultThemeForMode());
            clearCustomTheme();
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

    /* ── DROPDOWN MENÜS ── */

    function setupDropdown(buttonId, dropdownId, otherDropdownIds = []) {
        const button = document.getElementById(buttonId);
        const dropdown = document.getElementById(dropdownId);

        if (!button || !dropdown) return;

        button.addEventListener('click', (event) => {
            event.stopPropagation();

            otherDropdownIds.forEach((id) => {
                const otherDropdown = document.getElementById(id);

                if (otherDropdown) {
                    otherDropdown.classList.remove('open');
                }
            });

            dropdown.classList.toggle('open');
        });

        dropdown.querySelectorAll('a, button').forEach((item) => {
            item.addEventListener('click', () => {
                dropdown.classList.remove('open');
            });
        });

        document.addEventListener('click', (event) => {
            const clickedInsideDropdown = dropdown.contains(event.target);
            const clickedButton = button.contains(event.target);

            if (!clickedInsideDropdown && !clickedButton) {
                dropdown.classList.remove('open');
            }
        });

        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') {
                dropdown.classList.remove('open');
            }
        });
    }

    setupDropdown('games-menu-button', 'games-menu-dropdown', ['menu-dropdown']);
    setupDropdown('menu-button', 'menu-dropdown', ['games-menu-dropdown']);
});