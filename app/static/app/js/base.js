document.addEventListener('DOMContentLoaded', () => {
    const btn   = document.getElementById('darkmode-button');
    const body  = document.body;

    const flash = document.createElement('div');
    flash.className = 'theme-flash';
    document.body.appendChild(flash);

    if (localStorage.getItem('theme') === 'dark') {
        const noTrans = document.createElement('style');
        noTrans.textContent = '*, *::before, *::after { transition: none !important; }';
        document.head.appendChild(noTrans);
        body.classList.add('dark-mode');
        void document.body.offsetHeight;
        document.head.removeChild(noTrans);
    }

    if (!btn) return;

    btn.addEventListener('click', () => {
        btn.classList.remove('pulsing');
        void btn.offsetWidth;
        btn.classList.add('pulsing');
        btn.addEventListener('animationend', () => btn.classList.remove('pulsing'), { once: true });

        const goingDark = !body.classList.contains('dark-mode');
        flash.style.background = goingDark
            ? 'rgba(15, 22, 55, 1)'
            : 'rgba(235, 244, 255, 1)';
        flash.classList.remove('flash-in');
        void flash.offsetWidth;
        flash.classList.add('flash-in');

        body.classList.toggle('dark-mode');
        localStorage.setItem('theme', body.classList.contains('dark-mode') ? 'dark' : 'light');
    });
});