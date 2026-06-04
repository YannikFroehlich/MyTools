(() => {
    const root = document.querySelector('[data-presence-api-url]');
    const presenceElements = Array.from(document.querySelectorAll('[data-presence-user-id]'));

    if (!root || presenceElements.length === 0) {
        return;
    }

    const apiUrl = root.dataset.presenceApiUrl;
    const userIds = Array.from(new Set(
        presenceElements
            .map((element) => Number.parseInt(element.dataset.presenceUserId || '', 10))
            .filter(Number.isFinite)
    ));

    if (!apiUrl || userIds.length === 0) {
        return;
    }

    const elementsByUserId = new Map();

    for (const element of presenceElements) {
        const userId = Number.parseInt(element.dataset.presenceUserId || '', 10);

        if (!Number.isFinite(userId)) {
            continue;
        }

        if (!elementsByUserId.has(userId)) {
            elementsByUserId.set(userId, []);
        }

        elementsByUserId.get(userId).push(element);
    }

    let isPolling = false;
    let lastPayload = '';

    function applyPresence(profile) {
        const elements = elementsByUserId.get(Number(profile.userId)) || [];
        const isOnline = Boolean(profile.isOnline);
        const activityStatus = profile.activityStatus || '';
        const statusLine = profile.statusLine || '';

        for (const element of elements) {
            const target = element.dataset.presenceTarget;

            if (target === 'dot') {
                element.hidden = !isOnline;
                continue;
            }

            if (target === 'activity-detail') {
                element.textContent = activityStatus;
                element.hidden = !activityStatus;
                continue;
            }

            if (target === 'status') {
                element.textContent = statusLine;
                element.classList.toggle('is-online', isOnline);
            }
        }
    }

    async function pollPresence() {
        if (isPolling || document.visibilityState === 'hidden') {
            return;
        }

        isPolling = true;

        try {
            const url = new URL(apiUrl, window.location.origin);
            url.searchParams.set('ids', userIds.join(','));
            url.searchParams.set('_', String(Date.now()));

            const response = await fetch(url.toString(), {
                headers: {
                    'Accept': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                },
                cache: 'no-store',
                credentials: 'same-origin',
            });

            if (!response.ok) {
                return;
            }

            const data = await response.json();
            const payload = JSON.stringify(data.profiles || []);

            if (payload === lastPayload) {
                return;
            }

            lastPayload = payload;

            for (const profile of data.profiles || []) {
                applyPresence(profile);
            }
        } catch (error) {
            console.debug('Nutzerstatus konnte nicht aktualisiert werden:', error);
        } finally {
            isPolling = false;
        }
    }

    pollPresence();
    window.setInterval(pollPresence, 7000);
    document.addEventListener('visibilitychange', pollPresence);
})();
