document.addEventListener('DOMContentLoaded', () => {
    const page = document.querySelector('.avatar-page');

    if (!page) {
        return;
    }

    const charactersUrl = page.dataset.charactersUrl || '/api/avatar-characters/';
    const form = document.getElementById('characterForm');
    const cardsContainer = document.getElementById('cards');
    const addBtn = document.getElementById('add-btn');
    const drawer = document.getElementById('form-drawer');
    const backdrop = document.getElementById('drawer-backdrop');
    const searchInput = document.getElementById('search-input');
    const modalOverlay = document.getElementById('modal-overlay');
    const modalClose = document.getElementById('modal-close');
    let activeFilter = 'all';

    function getCookie(name) {
        const cookies = document.cookie ? document.cookie.split(';') : [];

        for (const cookie of cookies) {
            const trimmed = cookie.trim();

            if (trimmed.startsWith(`${name}=`)) {
                return decodeURIComponent(trimmed.slice(name.length + 1));
            }
        }

        return '';
    }

    function getCsrfToken() {
        return getCookie('csrftoken') || form.querySelector('[name="csrfmiddlewaretoken"]')?.value || '';
    }

    function characterDetailUrl(id) {
        return `${charactersUrl.replace(/\/?$/, '/')}${id}/`;
    }

    async function readResponse(response) {
        const text = await response.text();

        try {
            return JSON.parse(text);
        } catch (error) {
            return {
                status: 'error',
                message: text ? text.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 240) : '',
            };
        }
    }

    function openDrawer() {
        drawer.classList.add('open');
        backdrop.classList.add('open');
        addBtn.classList.add('open');
    }

    function closeDrawer() {
        drawer.classList.remove('open');
        backdrop.classList.remove('open');
        addBtn.classList.remove('open');
    }

    function setEmptyMessage(message) {
        const empty = document.getElementById('empty-state');

        if (empty) {
            empty.textContent = message;
            empty.style.display = 'block';
        }
    }

    function updateEmptyState() {
        const empty = document.getElementById('empty-state');

        if (!empty) {
            return;
        }

        const visibleCards = page.querySelectorAll('.avatar-card:not(.hidden)');
        empty.textContent = 'Noch keine Charaktere hinzugefügt.';
        empty.style.display = visibleCards.length === 0 ? 'block' : 'none';
    }

    function nationClass(nation) {
        const value = (nation || '').toLowerCase();

        if (value.includes('feuer') || value.includes('fire')) return 'nation-fire';
        if (value.includes('wasser') || value.includes('water')) return 'nation-water';
        if (value.includes('erde') || value.includes('earth')) return 'nation-earth';
        if (value.includes('luft') || value.includes('air')) return 'nation-air';
        return 'nation-other';
    }

    function escapeHtml(value) {
        if (!value) return '';

        return String(value)
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#039;');
    }

    function openModal(character) {
        const badge = document.getElementById('modal-nation-badge');
        const link = document.getElementById('modal-link');
        const description = document.getElementById('modal-description');

        document.getElementById('modal-img').src = character.image;
        document.getElementById('modal-img').alt = character.name;
        document.getElementById('modal-name').textContent = character.name;
        description.textContent = character.description || '';
        description.style.display = character.description ? 'block' : 'none';

        badge.innerHTML = character.nation
            ? `<span class="nation-badge ${nationClass(character.nation)}">${escapeHtml(character.nation)}</span>`
            : '';

        if (character.link) {
            link.href = character.link;
            link.classList.remove('hidden');
        } else {
            link.classList.add('hidden');
        }

        modalOverlay.classList.add('open');
        document.body.style.overflow = 'hidden';
    }

    function closeModal() {
        modalOverlay.classList.remove('open');
        document.body.style.overflow = '';
    }

    async function deleteCharacter(id) {
        const response = await fetch(characterDetailUrl(id), {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': getCsrfToken(),
            },
        });

        if (!response.ok) {
            const data = await readResponse(response);
            alert(data.message || 'Charakter konnte nicht gelöscht werden.');
            return;
        }

        const card = document.getElementById(`card-${id}`);

        if (card) {
            card.style.transform = 'scale(0.9)';
            card.style.opacity = '0';
            window.setTimeout(() => {
                card.remove();
                updateEmptyState();
            }, 220);
        }
    }

    function addCard(character) {
        const empty = document.getElementById('empty-state');
        const card = document.createElement('article');
        const badgeClass = nationClass(character.nation);

        if (empty) {
            empty.style.display = 'none';
        }

        card.className = 'avatar-card';
        card.id = `card-${character.id}`;
        card.dataset.name = character.name.toLowerCase();
        card.dataset.nation = character.nation || '';
        card.innerHTML = `
            <button class="delete-btn" type="button" title="Löschen">
                <i class="fa-solid fa-xmark"></i>
            </button>
            <div class="card-img-wrap">
                <img src="${escapeHtml(character.image)}" alt="${escapeHtml(character.name)}">
            </div>
            <div class="card-body">
                <h3>${escapeHtml(character.name)}</h3>
                ${character.nation ? `<span class="nation-badge ${badgeClass}">${escapeHtml(character.nation)}</span>` : ''}
                ${character.description ? `<p>${escapeHtml(character.description)}</p>` : ''}
                ${character.link ? `<a href="${escapeHtml(character.link)}" target="_blank" rel="noopener">Mehr Infos</a>` : ''}
            </div>
        `;

        card.querySelector('.delete-btn').addEventListener('click', (event) => {
            event.stopPropagation();
            deleteCharacter(character.id);
        });

        card.addEventListener('click', (event) => {
            if (event.target.closest('.delete-btn')) {
                return;
            }

            openModal(character);
        });

        cardsContainer.appendChild(card);
    }

    function applyFilters() {
        const query = searchInput.value.trim().toLowerCase();

        page.querySelectorAll('.avatar-card').forEach((card) => {
            const name = (card.dataset.name || '').toLowerCase();
            const nation = card.dataset.nation || '';
            const matchesSearch = !query || name.includes(query);
            const matchesFilter = activeFilter === 'all' || nation === activeFilter;
            card.classList.toggle('hidden', !(matchesSearch && matchesFilter));
        });

        updateEmptyState();
    }

    async function loadCharacters() {
        setEmptyMessage('Charaktere werden geladen...');

        try {
            const response = await fetch(charactersUrl);
            const data = await readResponse(response);

            if (!response.ok) {
                setEmptyMessage(data.message || 'Charaktere konnten nicht geladen werden.');
                return;
            }

            page.querySelectorAll('.avatar-card').forEach((card) => card.remove());
            data.characters.forEach(addCard);
            applyFilters();
        } catch (error) {
            console.error('Avatar-Charaktere konnten nicht geladen werden:', error);
            setEmptyMessage('Charaktere konnten nicht geladen werden.');
        }
    }

    addBtn.addEventListener('click', () => {
        if (drawer.classList.contains('open')) {
            closeDrawer();
        } else {
            openDrawer();
        }
    });

    backdrop.addEventListener('click', closeDrawer);
    modalClose.addEventListener('click', closeModal);
    modalOverlay.addEventListener('click', (event) => {
        if (event.target === modalOverlay) {
            closeModal();
        }
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            closeDrawer();
            closeModal();
        }
    });

    searchInput.addEventListener('input', applyFilters);

    page.querySelectorAll('.pill').forEach((pill) => {
        pill.addEventListener('click', () => {
            const activeClassMap = {
                all: 'active-all',
                Feuer: 'active-fire',
                Wasser: 'active-water',
                Erde: 'active-earth',
                Luft: 'active-air',
            };

            activeFilter = pill.dataset.filter;
            page.querySelectorAll('.pill').forEach((item) => {
                item.className = 'pill';

                if (item.dataset.filter === activeFilter) {
                    item.classList.add(activeClassMap[activeFilter] || 'active-all');
                }
            });
            applyFilters();
        });
    });

    form.addEventListener('submit', async (event) => {
        event.preventDefault();

        const submitButton = form.querySelector('button[type="submit"]');
        const formData = new FormData();
        const imageFile = document.getElementById('image').files[0];

        if (!imageFile) {
            return;
        }

        formData.append('name', document.getElementById('name').value.trim());
        formData.append('nation', document.getElementById('nation').value);
        formData.append('link', document.getElementById('link').value.trim());
        formData.append('description', document.getElementById('description').value.trim());
        formData.append('image', imageFile);

        submitButton.disabled = true;
        submitButton.textContent = 'Speichere...';

        try {
            const response = await fetch(charactersUrl, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                },
                body: formData,
            });
            const data = await readResponse(response);

            if (!response.ok) {
                alert(data.message || 'Charakter konnte nicht gespeichert werden.');
                return;
            }

            addCard(data.character);
            applyFilters();
            form.reset();
            closeDrawer();
        } catch (error) {
            console.error('Avatar-Charakter konnte nicht gespeichert werden:', error);
            alert('Charakter konnte nicht gespeichert werden.');
        } finally {
            submitButton.disabled = false;
            submitButton.textContent = 'Speichern';
        }
    });

    loadCharacters();
});
