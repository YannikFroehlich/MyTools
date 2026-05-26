document.addEventListener('DOMContentLoaded', () => {
    const darkModeButton = document.getElementById('darkmode-button');

    function syncAuthDarkClass() {
        document.documentElement.classList.toggle(
            'auth-dark',
            document.body.classList.contains('dark-mode')
        );
    }

    syncAuthDarkClass();
    darkModeButton?.addEventListener('click', syncAuthDarkClass);
});
