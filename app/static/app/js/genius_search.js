document.addEventListener('DOMContentLoaded', () => {
    const page = document.querySelector('.genius-page');

    if (!page) {
        return;
    }

    let currentPage = 1;
    const songsPerPage = 8;
    const searchUrl = page.dataset.searchUrl || '/api/genius/search/';

    const queryInput = document.getElementById('query');
    const searchBtn = document.getElementById('searchBtn');
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    const pageInfo = document.getElementById('pageInfo');
    const pagination = document.getElementById('pagination');
    const results = document.getElementById('results');

    function setEmptyState(message) {
        results.innerHTML = '';
        const empty = document.createElement('p');
        empty.className = 'genius-empty-state';
        empty.textContent = message;
        results.appendChild(empty);
        pagination.classList.add('hidden');
    }

    function createCard(song) {
        const card = document.createElement('article');
        card.className = 'genius-card';

        const image = document.createElement('img');
        image.src = song.image || '';
        image.alt = song.title ? `Cover: ${song.title}` : 'Song Cover';
        image.loading = 'lazy';

        const title = document.createElement('h3');
        title.textContent = song.title || 'Unbekannter Titel';

        const artist = document.createElement('p');
        artist.textContent = song.artist || 'Unbekannter Künstler';

        const link = document.createElement('a');
        link.href = song.url;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.textContent = 'Lyrics ansehen ->';

        card.append(image, title, artist, link);
        return card;
    }

    function displayResults(songs) {
        results.innerHTML = '';

        if (songs.length === 0) {
            setEmptyState('Keine Ergebnisse gefunden.');
            return;
        }

        songs.forEach((song) => {
            results.appendChild(createCard(song));
        });

        pagination.classList.remove('hidden');
    }

    function updatePagination(hitCount) {
        pageInfo.textContent = `Seite ${currentPage}`;
        prevBtn.disabled = currentPage === 1;
        nextBtn.disabled = hitCount < songsPerPage;
    }

    async function searchGenius() {
        const query = queryInput.value.trim();

        if (!query) {
            queryInput.focus();
            return;
        }

        setEmptyState('Suche läuft...');
        searchBtn.disabled = true;

        try {
            const url = `${searchUrl}?q=${encodeURIComponent(query)}&page=${currentPage}&per_page=${songsPerPage}`;
            const response = await fetch(url);
            const data = await response.json();

            if (!response.ok) {
                setEmptyState(data.message || 'Genius konnte nicht geladen werden.');
                return;
            }

            const songs = data.results || [];
            displayResults(songs);
            updatePagination(songs.length);
        } catch (error) {
            console.error('Genius API Fehler:', error);
            setEmptyState('Genius konnte nicht geladen werden.');
        } finally {
            searchBtn.disabled = false;
        }
    }

    searchBtn.addEventListener('click', () => {
        currentPage = 1;
        searchGenius();
    });

    queryInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            currentPage = 1;
            searchGenius();
        }
    });

    prevBtn.addEventListener('click', () => {
        if (currentPage > 1) {
            currentPage--;
            searchGenius();
        }
    });

    nextBtn.addEventListener('click', () => {
        currentPage++;
        searchGenius();
    });
});
