(function () {
    const preview = document.getElementById('profile-card-preview');
    if (!preview) return;

    const inputs = {
        style: document.getElementById('designer-style'),
        pattern: document.getElementById('designer-pattern'),
        patternStrength: document.getElementById('designer-pattern-strength'),
        gradientAngle: document.getElementById('designer-gradient-angle'),
        primary: document.getElementById('designer-primary'),
        secondary: document.getElementById('designer-secondary'),
        tertiary: document.getElementById('designer-tertiary'),
        text: document.getElementById('designer-text'),
        border: document.getElementById('designer-border'),
        badgeBg: document.getElementById('designer-badge-bg'),
        radius: document.getElementById('designer-radius'),
        avatarShape: document.getElementById('designer-avatar-shape'),
        textEffect: document.getElementById('designer-text-effect'),
        glow: document.getElementById('designer-glow'),
        shine: document.getElementById('designer-shine'),
        badgeText: document.getElementById('designer-badge-text'),
        badgeIcon: document.getElementById('designer-badge-icon'),
    };

    const badge = document.getElementById('preview-badge');

    const styleClasses = [
        'profile-showcase-card-glass',
        'profile-showcase-card-neon',
        'profile-showcase-card-gamer',
        'profile-showcase-card-soft',
        'profile-showcase-card-minimal',
    ];
    const patternClasses = [
        'profile-showcase-pattern-none',
        'profile-showcase-pattern-grid',
        'profile-showcase-pattern-dots',
        'profile-showcase-pattern-lines',
        'profile-showcase-pattern-orbs',
    ];
    const strengthClasses = [
        'profile-showcase-pattern-strength-subtle',
        'profile-showcase-pattern-strength-normal',
        'profile-showcase-pattern-strength-strong',
    ];
    const radiusClasses = [
        'profile-showcase-radius-soft',
        'profile-showcase-radius-round',
        'profile-showcase-radius-bold',
        'profile-showcase-radius-max',
    ];
    const avatarClasses = [
        'profile-showcase-avatar-rounded',
        'profile-showcase-avatar-circle',
        'profile-showcase-avatar-square',
        'profile-showcase-avatar-hex',
    ];
    const textEffectClasses = [
        'profile-showcase-text-none',
        'profile-showcase-text-shadow',
        'profile-showcase-text-glow',
        'profile-showcase-text-outline',
    ];

    function cleanIcon(value) {
        const icon = (value || '').trim();
        return /^[a-z0-9\- ]{1,40}$/i.test(icon) ? icon : 'fa-solid fa-star';
    }

    function value(input, fallback = '') {
        return input ? input.value : fallback;
    }

    function checked(input) {
        return input ? input.checked : false;
    }

    function updatePreview() {
        preview.style.setProperty('--profile-card-primary', value(inputs.primary, '#7c3aed'));
        preview.style.setProperty('--profile-card-secondary', value(inputs.secondary, '#06b6d4'));
        preview.style.setProperty('--profile-card-tertiary', value(inputs.tertiary, '#c026d3'));
        preview.style.setProperty('--profile-card-text', value(inputs.text, '#ffffff'));
        preview.style.setProperty('--profile-card-border', value(inputs.border, '#ffffff'));
        preview.style.setProperty('--profile-card-badge-bg', value(inputs.badgeBg, '#ffffff'));
        preview.style.setProperty('--profile-card-angle', `${value(inputs.gradientAngle, '135')}deg`);

        preview.classList.remove(
            ...styleClasses,
            ...patternClasses,
            ...strengthClasses,
            ...radiusClasses,
            ...avatarClasses,
            ...textEffectClasses,
            'profile-showcase-card-glow',
            'profile-showcase-card-shine',
        );
        preview.classList.add(`profile-showcase-card-${value(inputs.style, 'glass')}`);
        preview.classList.add(`profile-showcase-pattern-${value(inputs.pattern, 'orbs')}`);
        preview.classList.add(`profile-showcase-pattern-strength-${value(inputs.patternStrength, 'normal')}`);
        preview.classList.add(`profile-showcase-radius-${value(inputs.radius, 'bold')}`);
        preview.classList.add(`profile-showcase-avatar-${value(inputs.avatarShape, 'rounded')}`);
        preview.classList.add(`profile-showcase-text-${value(inputs.textEffect, 'shadow')}`);
        if (checked(inputs.glow)) preview.classList.add('profile-showcase-card-glow');
        if (checked(inputs.shine)) preview.classList.add('profile-showcase-card-shine');

        const text = (value(inputs.badgeText) || '').trim();
        badge.hidden = !text;
        badge.innerHTML = `<i class="${cleanIcon(value(inputs.badgeIcon))}"></i><span></span>`;
        badge.querySelector('span').textContent = text;
    }

    Object.values(inputs).forEach((input) => {
        if (!input) return;
        input.addEventListener('input', updatePreview);
        input.addEventListener('change', updatePreview);
    });

    updatePreview();
})();
