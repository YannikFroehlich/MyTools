(() => {
    const script = document.getElementById('mytools-ga-script');

    if (!script) {
        return;
    }

    const measurementId = (script.dataset.measurementId || '').trim();
    const consentKey = 'mytools_google_analytics_consent_v1';
    const validConsentValues = new Set(['granted', 'denied']);

    if (!measurementId || !measurementId.startsWith('G-')) {
        return;
    }

    window.dataLayer = window.dataLayer || [];
    window.gtag = window.gtag || function gtag() {
        window.dataLayer.push(arguments);
    };

    window.gtag('consent', 'default', {
        analytics_storage: 'denied',
        ad_storage: 'denied',
        ad_user_data: 'denied',
        ad_personalization: 'denied',
    });

    function readStoredConsent() {
        try {
            const value = localStorage.getItem(consentKey);
            return validConsentValues.has(value) ? value : null;
        } catch (error) {
            return null;
        }
    }

    function storeConsent(value) {
        try {
            localStorage.setItem(consentKey, value);
        } catch (error) {
            // If localStorage is unavailable, the decision still applies for this page load.
        }
    }

    function updateConsent(value) {
        const consentValue = value === 'granted' ? 'granted' : 'denied';

        window.gtag('consent', 'update', {
            analytics_storage: consentValue,
            ad_storage: 'denied',
            ad_user_data: 'denied',
            ad_personalization: 'denied',
        });
    }

    function loadGoogleTag() {
        if (document.querySelector(`script[data-mytools-ga-loader="${measurementId}"]`)) {
            return;
        }

        const gaScript = document.createElement('script');
        gaScript.async = true;
        gaScript.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(measurementId)}`;
        gaScript.dataset.mytoolsGaLoader = measurementId;
        document.head.appendChild(gaScript);

        window.gtag('js', new Date());
        window.gtag('config', measurementId, {
            send_page_view: true,
        });
    }

    function acceptAnalytics(banner) {
        storeConsent('granted');
        updateConsent('granted');
        loadGoogleTag();
        banner?.remove();
    }

    function declineAnalytics(banner) {
        storeConsent('denied');
        updateConsent('denied');
        banner?.remove();
    }

    function buildBanner() {
        const banner = document.createElement('section');
        banner.className = 'ga-consent-banner';
        banner.setAttribute('aria-label', script.dataset.title || 'Analyse-Cookies erlauben?');

        const eyebrow = document.createElement('div');
        eyebrow.className = 'ga-consent-banner__eyebrow';
        eyebrow.textContent = 'Analytics';

        const title = document.createElement('h2');
        title.className = 'ga-consent-banner__title';
        title.textContent = script.dataset.title || 'Analyse-Cookies erlauben?';

        const message = document.createElement('p');
        message.className = 'ga-consent-banner__message';
        message.textContent = script.dataset.message || 'Google Analytics wird erst geladen, wenn du zustimmst.';

        const actions = document.createElement('div');
        actions.className = 'ga-consent-banner__actions';

        const declineButton = document.createElement('button');
        declineButton.className = 'ga-consent-banner__button ga-consent-banner__button--decline';
        declineButton.type = 'button';
        declineButton.textContent = script.dataset.declineLabel || 'Ablehnen';

        const acceptButton = document.createElement('button');
        acceptButton.className = 'ga-consent-banner__button ga-consent-banner__button--accept';
        acceptButton.type = 'button';
        acceptButton.textContent = script.dataset.acceptLabel || 'Erlauben';

        declineButton.addEventListener('click', () => declineAnalytics(banner));
        acceptButton.addEventListener('click', () => acceptAnalytics(banner));

        actions.append(declineButton, acceptButton);
        banner.append(eyebrow, title, message, actions);

        return banner;
    }

    function showBannerWhenReady() {
        const appendBanner = () => document.body.appendChild(buildBanner());

        if (document.body) {
            appendBanner();
            return;
        }

        document.addEventListener('DOMContentLoaded', appendBanner, { once: true });
    }

    const storedConsent = readStoredConsent();

    if (storedConsent === 'granted') {
        updateConsent('granted');
        loadGoogleTag();
        return;
    }

    if (storedConsent === 'denied') {
        updateConsent('denied');
        return;
    }

    showBannerWhenReady();
})();
