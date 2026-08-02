document.addEventListener('DOMContentLoaded', () => {
    const panel = document.querySelector('[data-tool-rules-panel]');
    const form = panel?.querySelector('.moderation-tool-access-form');

    if (!panel || !form) {
        return;
    }

    const cards = Array.from(panel.querySelectorAll('[data-tool-rule-card]'));
    const searchInput = panel.querySelector('[data-tool-rule-search]');
    const categorySelect = panel.querySelector('[data-tool-rule-category]');
    const kindSelect = panel.querySelector('[data-tool-rule-kind]');
    const resetButton = panel.querySelector('[data-tool-rule-reset]');
    const emptyState = panel.querySelector('[data-tool-rule-empty]');
    const dirtyIndicator = panel.querySelector('[data-tool-rule-dirty]');

    const normalize = (value) => String(value || '')
        .toLowerCase()
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '');

    const checkedRuleState = () => Array.from(form.querySelectorAll('input[type="radio"]:checked'))
        .map((input) => `${input.name}:${input.value}`)
        .sort()
        .join('|');

    const initialRuleState = checkedRuleState();
    let hasUnsavedChanges = false;

    function selectedLabel(input) {
        return input?.nextElementSibling?.querySelector('b')?.textContent?.trim() || '';
    }

    function updateCard(card) {
        const accessInput = card.querySelector('input[name^="access_"]:checked');
        const deviceInput = card.querySelector('input[name^="device_"]:checked');
        const accessLevel = accessInput?.value || 'all';
        const deviceTarget = deviceInput?.value || 'both';

        card.dataset.accessLevel = accessLevel;
        card.dataset.ruleDeviceTarget = deviceTarget;
        card.classList.remove('is-level-all', 'is-level-admin', 'is-level-hidden', 'is-device-both', 'is-device-mobile', 'is-device-desktop');
        card.classList.add(`is-level-${accessLevel}`, `is-device-${deviceTarget}`);

        const accessBadge = card.querySelector('[data-access-badge]');
        const deviceBadge = card.querySelector('[data-device-badge]');
        if (accessBadge) accessBadge.textContent = selectedLabel(accessInput);
        if (deviceBadge) deviceBadge.textContent = selectedLabel(deviceInput);
    }

    function updateSummary() {
        const counts = new Map();
        cards.forEach((card) => {
            const accessKey = `access:${card.dataset.accessLevel || 'all'}`;
            const deviceKey = `device:${card.dataset.ruleDeviceTarget || 'both'}`;
            counts.set(accessKey, (counts.get(accessKey) || 0) + 1);
            counts.set(deviceKey, (counts.get(deviceKey) || 0) + 1);
        });

        panel.querySelectorAll('[data-rule-count]').forEach((element) => {
            element.textContent = String(counts.get(element.dataset.ruleCount) || 0);
        });
    }

    function updateDirtyState() {
        hasUnsavedChanges = checkedRuleState() !== initialRuleState;
        if (dirtyIndicator) dirtyIndicator.hidden = !hasUnsavedChanges;
        form.classList.toggle('has-unsaved-changes', hasUnsavedChanges);
    }

    function filterCards() {
        const query = normalize(searchInput?.value);
        const category = normalize(categorySelect?.value);
        const kind = normalize(kindSelect?.value);
        let visibleCount = 0;

        cards.forEach((card) => {
            const name = normalize(card.querySelector('.moderation-tool-access-name')?.textContent);
            const cardCategory = normalize(card.dataset.toolCategory);
            const cardKind = normalize(card.dataset.toolKind);
            const matches = (!query || name.includes(query))
                && (!category || cardCategory === category)
                && (!kind || cardKind === kind);
            card.hidden = !matches;
            if (matches) visibleCount += 1;
        });

        if (emptyState) emptyState.hidden = visibleCount > 0;
    }

    cards.forEach((card) => {
        updateCard(card);
        card.querySelectorAll('input[type="radio"]').forEach((input) => {
            input.addEventListener('change', () => {
                updateCard(card);
                updateSummary();
                updateDirtyState();
            });
        });
    });

    searchInput?.addEventListener('input', filterCards);
    categorySelect?.addEventListener('change', filterCards);
    kindSelect?.addEventListener('change', filterCards);
    resetButton?.addEventListener('click', () => {
        if (searchInput) searchInput.value = '';
        if (categorySelect) categorySelect.value = '';
        if (kindSelect) kindSelect.value = '';
        filterCards();
        searchInput?.focus();
    });

    form.addEventListener('submit', () => {
        hasUnsavedChanges = false;
    });
    window.addEventListener('beforeunload', (event) => {
        if (!hasUnsavedChanges) return;
        event.preventDefault();
        event.returnValue = '';
    });

    updateSummary();
    updateDirtyState();
    filterCards();
});
