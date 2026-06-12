document.addEventListener('DOMContentLoaded', () => {
    const darkModeButton = document.getElementById('darkmode-button');

    function syncAuthDarkClass() {
        document.documentElement.classList.toggle(
            'auth-dark',
            document.body.classList.contains('dark-mode')
        );
    }

    function resizeRecaptcha() {
        const captchaBlocks = document.querySelectorAll('.auth-captcha');
        const baseWidth = 304;
        const baseHeight = 78;

        captchaBlocks.forEach((block) => {
            const availableWidth = block.clientWidth;

            if (!availableWidth) {
                return;
            }

            const maxScale = 1.08;
            const minScale = 0.76;
            const scale = Math.min(maxScale, Math.max(minScale, availableWidth / baseWidth));
            block.style.setProperty('--captcha-scale', scale.toFixed(3));
            block.style.setProperty('--captcha-height', `${Math.ceil(baseHeight * scale)}px`);
        });
    }

    syncAuthDarkClass();
    resizeRecaptcha();

    darkModeButton?.addEventListener('click', syncAuthDarkClass);
    window.addEventListener('resize', resizeRecaptcha);

    if ('ResizeObserver' in window) {
        document.querySelectorAll('.auth-captcha').forEach((block) => {
            new ResizeObserver(resizeRecaptcha).observe(block);
        });
    }
});
