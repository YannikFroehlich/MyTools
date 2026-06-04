document.addEventListener('DOMContentLoaded', () => {
    let currentStations = [];
    let cheapestPrice = 0;

    const page = document.querySelector('.fuel-page');
    const spinner = document.getElementById('loading-spinner');
    const stationList = document.getElementById('station-list');
    const fuelType = document.getElementById('fuel-type');
    const geoBtn = document.getElementById('geo-btn');
    const searchBtn = document.getElementById('search-btn');
    const cityInput = document.getElementById('city-input');
    const kmInput = document.getElementById('km-input');
    const consumptionInput = document.getElementById('consumption');
    const timeUnit = document.getElementById('time-unit');
    const resultElement = document.getElementById('calc-result');
    const tankSizeInput = document.getElementById('tank-size');
    const rangeResultElement = document.getElementById('range-result');
    const apiUrl = page?.dataset.apiUrl || '/api/tankstellen/';

    if (!page || !spinner || !stationList || !fuelType || !resultElement || !rangeResultElement) {
        return;
    }

    function setMessage(message) {
        stationList.innerHTML = '';
        const empty = document.createElement('p');
        empty.className = 'empty-state';
        empty.textContent = message;
        stationList.appendChild(empty);
    }

    function toggleLoading(show) {
        spinner.classList.toggle('hidden', !show);

        if (show) {
            stationList.innerHTML = '';
        }
    }

    function formatPrice(price) {
        return `${Number(price).toLocaleString('de-DE', {
            minimumFractionDigits: 3,
            maximumFractionDigits: 3,
        })} €`;
    }

    function pulseResult(element) {
        element.classList.add('is-updated');
        window.setTimeout(() => element.classList.remove('is-updated'), 180);
    }

    function formatGermanNumber(value, fractionDigits = 1) {
        return Number(value).toLocaleString('de-DE', {
            minimumFractionDigits: fractionDigits,
            maximumFractionDigits: fractionDigits,
        });
    }

    function calculateCosts(consumption) {
        const km = parseFloat(kmInput.value);
        const multiplier = parseFloat(timeUnit.value);
        const period = timeUnit.options[timeUnit.selectedIndex].text;

        if (km > 0 && consumption > 0 && multiplier > 0 && cheapestPrice > 0) {
            const total = ((km * multiplier) / 100) * consumption * cheapestPrice;
            resultElement.textContent = `Kosten ${period}: ${total.toFixed(2).replace('.', ',')} €`;
            pulseResult(resultElement);
            return;
        }

        resultElement.textContent = 'Kosten: -- €';
    }

    function calculateRange(consumption) {
        const tankSize = parseFloat(tankSizeInput?.value);

        if (tankSize > 0 && consumption > 0) {
            const range = (tankSize / consumption) * 100;
            rangeResultElement.textContent = `Reichweite: ca. ${formatGermanNumber(range, 1)} km`;
            pulseResult(rangeResultElement);
            return;
        }

        rangeResultElement.textContent = 'Reichweite: -- km';
    }

    function calculate() {
        const consumption = parseFloat(consumptionInput.value);

        calculateCosts(consumption);
        calculateRange(consumption);
    }

    function renderStations(stations) {
        const fuel = fuelType.value;
        const sortedStations = [...stations].sort((a, b) => (a[fuel] || 9.99) - (b[fuel] || 9.99));
        const validPrices = sortedStations.map((station) => station[fuel]).filter((price) => price > 0);

        cheapestPrice = validPrices.length > 0 ? validPrices[0] : 0;
        stationList.innerHTML = '';

        if (sortedStations.length === 0) {
            setMessage('Keine Tankstellen gefunden.');
            calculate();
            return;
        }

        sortedStations.forEach((station, index) => {
            const price = station[fuel];
            const item = document.createElement('article');
            item.className = 'station-item';
            item.style.animationDelay = `${index * 0.04}s`;

            const info = document.createElement('div');
            info.className = 'station-info';

            const name = document.createElement('strong');
            name.textContent = station.name || 'Unbekannte Tankstelle';

            const address = document.createElement('span');
            address.className = 'station-address';
            address.textContent = [
                station.street,
                station.houseNumber,
                station.postCode,
                station.place,
            ].filter(Boolean).join(' ');

            const distance = document.createElement('span');
            distance.className = 'station-dist';
            const dist = Number(station.dist);
            distance.textContent = Number.isFinite(dist) ? `${dist.toFixed(1)} km entfernt` : '';

            info.append(name, address, distance);

            const priceBox = document.createElement('div');
            priceBox.className = 'station-price';
            priceBox.textContent = price ? formatPrice(price) : 'n.v.';

            item.append(info, priceBox);
            stationList.appendChild(item);
        });

        calculate();
    }

    async function fetchStations(lat, lon) {
        const url = `${apiUrl}?lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}`;

        try {
            const response = await fetch(url);
            const data = await response.json();

            if (!response.ok || data.status !== 'ok') {
                setMessage(data.message || 'Tankstellen konnten nicht geladen werden.');
                cheapestPrice = 0;
                calculate();
                return;
            }

            currentStations = data.stations || [];
            renderStations(currentStations);
        } catch (error) {
            console.error('Tankstellen-Fehler:', error);
            setMessage('Tankstellen konnten nicht geladen werden.');
            cheapestPrice = 0;
            calculate();
        } finally {
            toggleLoading(false);
        }
    }

    function isLocalhost() {
        return ['localhost', '127.0.0.1', '[::1]'].includes(window.location.hostname);
    }

    function requestBrowserLocation() {
        if (!navigator.geolocation) {
            setMessage('Dein Browser unterstützt keine Standortabfrage.');
            return;
        }

        if (!window.isSecureContext && !isLocalhost()) {
            setMessage('Standortabfrage braucht HTTPS oder localhost. Suche stattdessen per Stadt.');
            return;
        }

        toggleLoading(true);
        navigator.geolocation.getCurrentPosition(
            (position) => fetchStations(position.coords.latitude, position.coords.longitude),
            (error) => {
                toggleLoading(false);
                const blockedByPolicy = error.message?.toLowerCase().includes('permissions policy');
                const blockedByUser = error.code === error.PERMISSION_DENIED;

                if (blockedByPolicy) {
                    setMessage('Standortabfrage ist durch die Seiten-Berechtigungen blockiert. Suche stattdessen per Stadt.');
                } else if (blockedByUser) {
                    setMessage('Standortzugriff wurde abgelehnt. Erlaube den Standort im Browser oder suche per Stadt.');
                } else {
                    setMessage('Standort konnte nicht ermittelt werden. Suche stattdessen per Stadt.');
                }
            },
            {
                enableHighAccuracy: true,
                maximumAge: 0,
                timeout: 12000,
            }
        );
    }

    geoBtn?.addEventListener('click', async () => {
        if (navigator.permissions?.query) {
            try {
                const permission = await navigator.permissions.query({ name: 'geolocation' });
                if (permission.state === 'denied') {
                    setMessage('Standortzugriff ist im Browser blockiert. Erlaube den Standort in den Website-Einstellungen und klicke dann erneut.');
                    return;
                }
            } catch (error) {
                console.debug('Berechtigungsstatus konnte nicht gelesen werden:', error);
            }
        }

        requestBrowserLocation();
    });

    searchBtn?.addEventListener('click', async () => {
        const city = cityInput.value.trim();

        if (!city) {
            cityInput.focus();
            return;
        }

        toggleLoading(true);

        try {
            const response = await fetch(`https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${encodeURIComponent(city)}`);
            const data = await response.json();

            if (data.length > 0) {
                fetchStations(data[0].lat, data[0].lon);
            } else {
                toggleLoading(false);
                setMessage('Ort nicht gefunden.');
            }
        } catch (error) {
            console.error('Geocoding-Fehler:', error);
            toggleLoading(false);
            setMessage('Ort konnte nicht gesucht werden.');
        }
    });

    cityInput?.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            searchBtn?.click();
        }
    });

    fuelType.addEventListener('change', () => {
        if (currentStations.length > 0) {
            renderStations(currentStations);
        }
    });

    [kmInput, consumptionInput, timeUnit, tankSizeInput].forEach((element) => {
        element?.addEventListener('input', calculate);
    });
});
