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
    const drawerTitle = document.getElementById('drawer-title');
    const characterIdInput = document.getElementById('character-id');
    const imageInput = document.getElementById('image');
    const cancelEditBtn = document.getElementById('cancel-edit-btn');
    const saveCharacterBtn = document.getElementById('save-character-btn');
    const characterMap = new Map();
    let activeFilter = 'all';
    let draggedCard = null;

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
        resetForm();
    }

    function resetForm() {
        form.reset();
        characterIdInput.value = '';
        imageInput.required = true;
        drawerTitle.textContent = 'Charakter hinzufügen';
        saveCharacterBtn.textContent = 'Speichern';
        cancelEditBtn.classList.add('hidden');
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
                characterMap.delete(Number(id));
                updateEmptyState();
            }, 220);
        }
    }

    function editCharacter(id) {
        const character = characterMap.get(Number(id));

        if (!character) {
            return;
        }

        characterIdInput.value = character.id;
        document.getElementById('name').value = character.name;
        document.getElementById('nation').value = character.nation;
        document.getElementById('link').value = character.link || '';
        document.getElementById('description').value = character.description || '';
        imageInput.value = '';
        imageInput.required = false;
        drawerTitle.textContent = 'Charakter bearbeiten';
        saveCharacterBtn.textContent = 'Aktualisieren';
        cancelEditBtn.classList.remove('hidden');
        openDrawer();
    }

    async function saveOrder() {
        const characterIds = Array.from(cardsContainer.querySelectorAll('.avatar-card'))
            .map((card) => Number(card.dataset.id));

        try {
            const response = await fetch(charactersUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                },
                body: JSON.stringify({
                    action: 'update_order',
                    character_ids: characterIds,
                }),
            });

            if (!response.ok) {
                const data = await readResponse(response);
                alert(data.message || 'Reihenfolge konnte nicht gespeichert werden.');
            }
        } catch (error) {
            console.error('Reihenfolge konnte nicht gespeichert werden:', error);
            alert('Reihenfolge konnte nicht gespeichert werden.');
        }
    }

    function getDragAfterElement(container, y) {
        const cards = [...container.querySelectorAll('.avatar-card:not(.is-dragging)')];

        return cards.reduce((closest, card) => {
            const box = card.getBoundingClientRect();
            const offset = y - box.top - box.height / 2;

            if (offset < 0 && offset > closest.offset) {
                return { offset, element: card };
            }

            return closest;
        }, { offset: Number.NEGATIVE_INFINITY, element: null }).element;
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
        card.draggable = true;
        card.dataset.id = character.id;
        card.dataset.name = character.name.toLowerCase();
        card.dataset.nation = character.nation || '';
        card.innerHTML = `
            <div class="avatar-card-actions">
                <button class="edit-btn" type="button" title="Bearbeiten">
                    <i class="fa-solid fa-pen"></i>
                </button>
                <button class="delete-btn" type="button" title="Löschen">
                    <i class="fa-solid fa-xmark"></i>
                </button>
            </div>
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

        characterMap.set(Number(character.id), character);

        card.querySelector('.edit-btn').addEventListener('click', (event) => {
            event.stopPropagation();
            editCharacter(character.id);
        });

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

        card.addEventListener('dragstart', () => {
            draggedCard = card;
            card.classList.add('is-dragging');
        });

        card.addEventListener('dragend', () => {
            card.classList.remove('is-dragging');
            draggedCard = null;
            saveOrder();
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
            characterMap.clear();
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
    cancelEditBtn.addEventListener('click', closeDrawer);
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

    cardsContainer.addEventListener('dragover', (event) => {
        event.preventDefault();

        if (!draggedCard) {
            return;
        }

        const afterElement = getDragAfterElement(cardsContainer, event.clientY);

        if (afterElement) {
            cardsContainer.insertBefore(draggedCard, afterElement);
        } else {
            cardsContainer.appendChild(draggedCard);
        }
    });

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
        const imageFile = imageInput.files[0];
        const characterId = characterIdInput.value;

        if (!imageFile && !characterId) {
            return;
        }

        formData.append('name', document.getElementById('name').value.trim());
        formData.append('nation', document.getElementById('nation').value);
        formData.append('link', document.getElementById('link').value.trim());
        formData.append('description', document.getElementById('description').value.trim());
        if (imageFile) {
            formData.append('image', imageFile);
        }

        submitButton.disabled = true;
        submitButton.textContent = characterId ? 'Aktualisiere...' : 'Speichere...';

        try {
            const response = await fetch(characterId ? characterDetailUrl(characterId) : charactersUrl, {
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

            if (characterId) {
                await loadCharacters();
            } else {
                addCard(data.character);
            }
            applyFilters();
            closeDrawer();
        } catch (error) {
            console.error('Avatar-Charakter konnte nicht gespeichert werden:', error);
            alert('Charakter konnte nicht gespeichert werden.');
        } finally {
            submitButton.disabled = false;
            submitButton.textContent = characterIdInput.value ? 'Aktualisieren' : 'Speichern';
        }
    });

    loadCharacters();
});
