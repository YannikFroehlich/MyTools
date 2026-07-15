(() => {
    "use strict";

    const DB_NAME = "mytools-shopping-v1";
    const DB_VERSION = 1;
    const SNAPSHOT_STORE = "snapshots";
    const QUEUE_STORE = "queue";
    let databasePromise = null;

    const openDatabase = () => {
        if (!("indexedDB" in window)) return Promise.resolve(null);
        if (databasePromise) return databasePromise;
        databasePromise = new Promise((resolve, reject) => {
            const request = indexedDB.open(DB_NAME, DB_VERSION);
            request.onupgradeneeded = () => {
                const database = request.result;
                if (!database.objectStoreNames.contains(SNAPSHOT_STORE)) {
                    database.createObjectStore(SNAPSHOT_STORE, {keyPath: "scope"});
                }
                if (!database.objectStoreNames.contains(QUEUE_STORE)) {
                    const queue = database.createObjectStore(QUEUE_STORE, {keyPath: "id", autoIncrement: true});
                    queue.createIndex("scope", "scope", {unique: false});
                }
            };
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
        return databasePromise;
    };

    const requestResult = (request) => new Promise((resolve, reject) => {
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });

    const transactionDone = (transaction) => new Promise((resolve, reject) => {
        transaction.oncomplete = () => resolve();
        transaction.onerror = () => reject(transaction.error);
        transaction.onabort = () => reject(transaction.error);
    });

    const serializeForm = (form) => new URLSearchParams(new FormData(form)).toString();

    const create = ({userId, listId, statusElement}) => {
        const scope = `${userId}:${listId}`;
        let flushing = false;

        const setStatus = (message, kind = "info", hidden = false) => {
            if (!statusElement) return;
            statusElement.hidden = hidden;
            statusElement.textContent = message;
            statusElement.dataset.kind = kind;
        };

        const queuedRequests = async () => {
            const database = await openDatabase();
            if (!database) return [];
            const transaction = database.transaction(QUEUE_STORE, "readonly");
            const requests = await requestResult(transaction.objectStore(QUEUE_STORE).index("scope").getAll(scope));
            await transactionDone(transaction);
            return requests.sort((left, right) => left.id - right.id);
        };

        const updateStatus = async () => {
            const count = (await queuedRequests()).length;
            if (!navigator.onLine) {
                setStatus(count ? `Offline · ${count} Änderung${count === 1 ? "" : "en"} wartet${count === 1 ? "" : "en"}` : "Offline · Änderungen werden lokal gespeichert", "offline");
            } else if (count) {
                setStatus(`${count} Änderung${count === 1 ? "" : "en"} wartet${count === 1 ? "" : "en"} auf Synchronisierung`, "pending");
            } else {
                setStatus("Alles synchronisiert", "success");
                window.setTimeout(() => {
                    if (statusElement?.dataset.kind === "success") statusElement.hidden = true;
                }, 2200);
            }
            return count;
        };

        const enqueue = async ({url, body, kind}) => {
            const database = await openDatabase();
            if (!database) throw new Error("Offline-Speicher wird von diesem Browser nicht unterstützt.");
            const transaction = database.transaction(QUEUE_STORE, "readwrite");
            transaction.objectStore(QUEUE_STORE).add({
                scope,
                userId: String(userId),
                listId: String(listId),
                url,
                body,
                kind,
                createdAt: Date.now(),
            });
            await transactionDone(transaction);
            await updateStatus();
            try {
                const registration = await navigator.serviceWorker?.ready;
                if (registration?.sync) await registration.sync.register("mytools-shopping-sync");
            } catch (_error) {
                // The online event remains the universal synchronization fallback.
            }
        };

        const removeQueuedRequest = async (id) => {
            const database = await openDatabase();
            if (!database) return;
            const transaction = database.transaction(QUEUE_STORE, "readwrite");
            transaction.objectStore(QUEUE_STORE).delete(id);
            await transactionDone(transaction);
        };

        const flush = async ({onSynced, onError} = {}) => {
            if (flushing || !navigator.onLine) return false;
            const queue = await queuedRequests();
            if (!queue.length) {
                await updateStatus();
                return true;
            }

            flushing = true;
            setStatus(`${queue.length} Änderung${queue.length === 1 ? " wird" : "en werden"} synchronisiert …`, "syncing");
            let latestPayload = null;
            try {
                for (const queued of queue) {
                    const response = await fetch(queued.url, {
                        method: "POST",
                        body: queued.body,
                        headers: {
                            "Accept": "application/json",
                            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                            "X-Requested-With": "XMLHttpRequest",
                        },
                        credentials: "same-origin",
                    });
                    const payload = await response.json().catch(() => ({}));
                    if (!response.ok || !payload.ok) {
                        throw new Error(payload.error || "Eine Offline-Änderung konnte nicht synchronisiert werden.");
                    }
                    latestPayload = payload;
                    await removeQueuedRequest(queued.id);
                }
                if (onSynced) await onSynced(latestPayload);
                await updateStatus();
                return true;
            } catch (error) {
                setStatus(error.message || "Synchronisierung fehlgeschlagen", "error");
                if (onError) onError(error);
                return false;
            } finally {
                flushing = false;
            }
        };

        const saveSnapshot = async ({listHtml, summary, csrfToken}) => {
            const database = await openDatabase();
            if (!database) return;
            const transaction = database.transaction(SNAPSHOT_STORE, "readwrite");
            transaction.objectStore(SNAPSHOT_STORE).put({
                scope,
                userId: String(userId),
                listId: String(listId),
                listHtml,
                summary,
                csrfToken,
                savedAt: Date.now(),
            });
            await transactionDone(transaction);
        };

        return {
            scope,
            enqueue,
            flush,
            saveSnapshot,
            serializeForm,
            updateStatus,
        };
    };

    const latestSnapshot = async () => {
        const database = await openDatabase();
        if (!database) return null;
        const transaction = database.transaction(SNAPSHOT_STORE, "readonly");
        const snapshots = await requestResult(transaction.objectStore(SNAPSHOT_STORE).getAll());
        await transactionDone(transaction);
        return snapshots.sort((left, right) => right.savedAt - left.savedAt)[0] || null;
    };

    const clearAll = () => new Promise((resolve) => {
        if (!("indexedDB" in window)) {
            resolve();
            return;
        }
        if (databasePromise) {
            databasePromise.then((database) => database?.close()).catch(() => {});
            databasePromise = null;
        }
        const request = indexedDB.deleteDatabase(DB_NAME);
        request.onsuccess = request.onerror = request.onblocked = () => resolve();
    });

    window.MyToolsShoppingOffline = {create, latestSnapshot, clearAll, serializeForm};
})();
