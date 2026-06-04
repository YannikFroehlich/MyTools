(function () {
    const randomInt = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;
    const lines = (value) => (value || '').split('\n').map((item) => item.trim()).filter(Boolean);
    const shuffle = (items) => [...items].sort(() => Math.random() - 0.5);

    const tabs = document.querySelectorAll('[data-randomizer-tab]');
    const panels = document.querySelectorAll('[data-randomizer-panel]');

    function activateTab(name, updateHash = true) {
        if (!name || !document.querySelector(`[data-randomizer-panel="${name}"]`)) {
            name = 'wheel';
        }
        tabs.forEach((tab) => tab.classList.toggle('active', tab.dataset.randomizerTab === name));
        panels.forEach((panel) => panel.classList.toggle('active', panel.dataset.randomizerPanel === name));
        if (updateHash) {
            history.replaceState(null, '', `${window.location.pathname}${window.location.search}#${name}`);
        }
    }

    tabs.forEach((tab) => {
        tab.addEventListener('click', () => activateTab(tab.dataset.randomizerTab));
    });

    activateTab((window.location.hash || '').replace('#', ''), false);

    const wheel = document.getElementById('decision-wheel');
    const wheelOptions = document.getElementById('wheel-options');
    const wheelResult = document.getElementById('wheel-result');
    let wheelRotation = 0;
    const wheelColors = ['#7c3aed', '#06b6d4', '#f97316', '#22c55e', '#e11d48', '#facc15', '#3b82f6', '#ec4899', '#14b8a6', '#f43f5e'];

    function paintWheel() {
        const options = lines(wheelOptions?.value);
        if (!wheel || !options.length) return;

        const size = 360;
        const center = size / 2;
        const radius = 166;
        const labelRadius = options.length > 8 ? 100 : 108;
        const step = 360 / options.length;

        const sectors = options.map((option, index) => {
            const startAngle = index * step - 90;
            const endAngle = (index + 1) * step - 90;
            const midAngle = startAngle + step / 2;
            const largeArc = step > 180 ? 1 : 0;
            const startPoint = polarToCartesian(center, center, radius, endAngle);
            const endPoint = polarToCartesian(center, center, radius, startAngle);
            const labelPoint = polarToCartesian(center, center, labelRadius, midAngle);
            const color = wheelColors[index % wheelColors.length];
            const shortOption = shortenWheelText(option, options.length);

            return `
                <path class="wheel-sector" d="M ${center} ${center} L ${startPoint.x} ${startPoint.y} A ${radius} ${radius} 0 ${largeArc} 0 ${endPoint.x} ${endPoint.y} Z" fill="${color}"></path>
                <text class="wheel-sector-label" x="${labelPoint.x}" y="${labelPoint.y}" title="${escapeHtml(option)}">${escapeHtml(shortOption)}</text>
            `;
        }).join('');

        wheel.innerHTML = `
            <svg class="wheel-svg" viewBox="0 0 ${size} ${size}" aria-hidden="true">
                <defs>
                    <filter id="wheelTextShadow" x="-30%" y="-30%" width="160%" height="160%">
                        <feDropShadow dx="0" dy="2" stdDeviation="2" flood-color="#020617" flood-opacity="0.45"/>
                    </filter>
                    <radialGradient id="wheelGloss" cx="35%" cy="25%" r="75%">
                        <stop offset="0%" stop-color="rgba(255,255,255,.34)"/>
                        <stop offset="42%" stop-color="rgba(255,255,255,.08)"/>
                        <stop offset="100%" stop-color="rgba(255,255,255,0)"/>
                    </radialGradient>
                </defs>
                <circle class="wheel-rim-bg" cx="${center}" cy="${center}" r="${radius + 7}"></circle>
                ${sectors}
                <circle class="wheel-gloss" cx="${center}" cy="${center}" r="${radius}" fill="url(#wheelGloss)"></circle>
                <circle class="wheel-inner-ring" cx="${center}" cy="${center}" r="43"></circle>
                <circle class="wheel-center" cx="${center}" cy="${center}" r="29"></circle>
                <circle class="wheel-center-shine" cx="${center - 9}" cy="${center - 10}" r="9"></circle>
            </svg>
        `;
    }

    document.getElementById('wheel-spin')?.addEventListener('click', () => {
        const options = lines(wheelOptions?.value);
        if (!options.length) {
            wheelResult.textContent = 'Bitte erst Optionen eintragen.';
            return;
        }

        const winnerIndex = randomInt(0, options.length - 1);
        const step = 360 / options.length;

        /*
         * Wichtig:
         * Das SVG-Rad wird ab -90° gezeichnet. Der Pointer steht oben.
         * Sektor 0 liegt deshalb im ungedrehten Zustand bereits oben/rechts.
         * Damit der Gewinner exakt unter dem Pointer steht, setzen wir die absolute
         * Endrotation direkt auf: -Mitte des Gewinner-Sektors.
         */
        const winnerCenter = winnerIndex * step + step / 2;
        const currentNormalized = ((wheelRotation % 360) + 360) % 360;
        const targetNormalized = ((-winnerCenter % 360) + 360) % 360;
        const deltaToTarget = ((targetNormalized - currentNormalized + 360) % 360);
        const fullSpins = 1440 + randomInt(0, 2) * 360;

        wheelRotation += fullSpins + deltaToTarget;

        wheel.classList.add('is-spinning');
        wheel.style.transform = `rotate(${wheelRotation}deg)`;
        wheelResult.classList.remove('result-pop');
        wheelResult.textContent = 'Dreht...';

        window.setTimeout(() => {
            wheel.classList.remove('is-spinning');
            wheelResult.textContent = `Gewinner: ${options[winnerIndex]}`;
            wheelResult.classList.add('result-pop');
        }, 3300);
    });
    wheelOptions?.addEventListener('input', () => {
        wheelRotation = 0;
        if (wheel) {
            wheel.style.transform = 'rotate(0deg)';
        }
        paintWheel();
        if (wheelResult) {
            wheelResult.textContent = '';
        }
    });
    paintWheel();

    document.getElementById('teams-generate')?.addEventListener('click', () => {
        const names = shuffle(lines(document.getElementById('teams-names')?.value));
        const count = Math.max(2, Math.min(10, Number(document.getElementById('teams-count')?.value) || 2));
        const result = document.getElementById('teams-result');
        if (!result) return;
        if (!names.length) {
            result.textContent = 'Bitte Namen eintragen.';
            return;
        }
        result.classList.remove('result-pop');
        const teams = Array.from({ length: Math.min(count, names.length) }, () => []);
        names.forEach((name, index) => teams[index % teams.length].push(name));
        result.innerHTML = teams.map((team, index) => `<div class="team-card"><strong>Team ${index + 1}</strong><ul>${team.map((name) => `<li>${escapeHtml(name)}</li>`).join('')}</ul></div>`).join('');
        requestAnimationFrame(() => result.classList.add('result-pop'));
    });

    document.getElementById('number-roll')?.addEventListener('click', () => {
        let min = Number(document.getElementById('number-min')?.value) || 0;
        let max = Number(document.getElementById('number-max')?.value) || 0;
        if (min > max) [min, max] = [max, min];
        const result = document.getElementById('number-result');
        if (!result) return;

        result.classList.add('number-rolling');
        let ticks = 0;
        const interval = window.setInterval(() => {
            result.textContent = randomInt(min, max);
            ticks += 1;
            if (ticks >= 14) {
                window.clearInterval(interval);
                result.textContent = randomInt(min, max);
                result.classList.remove('number-rolling');
                result.classList.remove('result-pop');
                requestAnimationFrame(() => result.classList.add('result-pop'));
            }
        }, 45);
    });

    document.getElementById('dice-roll')?.addEventListener('click', () => {
        const count = Math.max(1, Math.min(12, Number(document.getElementById('dice-count')?.value) || 1));
        const sides = Math.max(2, Math.min(100, Number(document.getElementById('dice-sides')?.value) || 6));
        const result = document.getElementById('dice-result');
        const rollButton = document.getElementById('dice-roll');
        if (!result) return;

        rollButton?.setAttribute('disabled', 'disabled');
        result.classList.add('dice-board', 'is-rolling');
        result.innerHTML = Array.from({ length: count }, (_, index) => createDieMarkup('?', index, sides, true)).join('')
            + '<strong class="dice-total dice-total-rolling">Würfelt...</strong>';

        let ticks = 0;
        const maxTicks = 22;
        const interval = window.setInterval(() => {
            result.querySelectorAll('.die').forEach((die) => {
                const value = randomInt(1, sides);
                die.dataset.value = String(value);
                if (sides === 6) {
                    die.innerHTML = createPips(value);
                } else {
                    die.textContent = value;
                }
            });
            ticks += 1;
            if (ticks >= maxTicks) {
                window.clearInterval(interval);
                const rolls = Array.from({ length: count }, () => randomInt(1, sides));
                const total = rolls.reduce((sum, roll) => sum + roll, 0);

                result.classList.remove('is-rolling');
                result.innerHTML = rolls.map((roll, index) => createDieMarkup(roll, index, sides, false)).join('')
                    + `<strong class="dice-total result-pop">Summe: ${total}</strong>`;

                result.querySelectorAll('.die').forEach((die, index) => {
                    window.setTimeout(() => die.classList.add('landed'), index * 55);
                });
                rollButton?.removeAttribute('disabled');
            }
        }, 46);
    });

    document.getElementById('starter-pick')?.addEventListener('click', () => {
        const names = lines(document.getElementById('starter-names')?.value);
        const result = document.getElementById('starter-result');
        if (!result) return;
        result.classList.remove('result-pop');
        result.textContent = 'Wählt...';
        let ticks = 0;
        const interval = window.setInterval(() => {
            result.textContent = names.length ? names[randomInt(0, names.length - 1)] : 'Bitte Spieler eintragen.';
            ticks += 1;
            if (ticks >= 12) {
                window.clearInterval(interval);
                result.textContent = names.length ? `${names[randomInt(0, names.length - 1)]} fängt an!` : 'Bitte Spieler eintragen.';
                result.classList.add('result-pop');
            }
        }, 55);
    });


    function createDieMarkup(value, index, sides, rolling) {
        const numericValue = Number(value);
        const isClassicD6 = sides === 6 && Number.isFinite(numericValue) && numericValue >= 1 && numericValue <= 6;
        const content = isClassicD6 ? createPips(numericValue) : escapeHtml(value);
        const classicClass = sides === 6 ? ' classic-d6' : ' number-die';
        const stateClass = rolling ? ' rolling' : ' final';
        return `<span class="die${classicClass}${stateClass}" data-value="${escapeHtml(value)}" style="--delay:${index * 60}ms; --spin:${randomInt(-22, 22)}deg">${content}</span>`;
    }

    function createPips(value) {
        return Array.from({ length: value }, () => '<i class="pip"></i>').join('');
    }

    function polarToCartesian(cx, cy, r, angleInDegrees) {
        const angleInRadians = (angleInDegrees - 90) * Math.PI / 180.0;
        return {
            x: cx + (r * Math.cos(angleInRadians)),
            y: cy + (r * Math.sin(angleInRadians)),
        };
    }

    function shortenWheelText(value, itemCount) {
        const max = itemCount > 10 ? 8 : itemCount > 7 ? 10 : 13;
        const clean = String(value).trim();
        return clean.length > max ? `${clean.slice(0, Math.max(1, max - 1))}…` : clean;
    }

    function escapeHtml(value) {
        return String(value).replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#039;', '"': '&quot;' }[char]));
    }
})();
