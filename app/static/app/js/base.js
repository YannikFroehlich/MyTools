document.addEventListener('DOMContentLoaded', () => {
    const body = document.body;

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
        });
    }

    /* ── MENU BUTTON ── */
    const menuButton = document.getElementById('menu-button');
    const menuDropdown = document.getElementById('menu-dropdown');

    if (menuButton && menuDropdown) {
        menuButton.addEventListener('click', (event) => {
            event.stopPropagation();
            menuDropdown.classList.toggle('open');
        });

        document.addEventListener('click', (event) => {
            const clickedInsideDropdown = menuDropdown.contains(event.target);
            const clickedMenuButton = menuButton.contains(event.target);

            if (!clickedInsideDropdown && !clickedMenuButton) {
                menuDropdown.classList.remove('open');
            }
        });

        menuDropdown.querySelectorAll('a, button').forEach((item) => {
            item.addEventListener('click', () => {
                menuDropdown.classList.remove('open');
            });
        });

        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') {
                menuDropdown.classList.remove('open');
            }
        });
    }
});