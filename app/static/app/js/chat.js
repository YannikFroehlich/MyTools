document.addEventListener("DOMContentLoaded", () => {
    const layout = document.querySelector(".chat-layout");
    const messagesBox = document.getElementById("chat-messages");
    const pinnedBox = document.getElementById("chat-pinned-message");
    const form = document.getElementById("chat-compose-form");
    const textarea = form?.querySelector("textarea[name='text']");
    const attachmentInput = document.getElementById("chat-attachment-input");
    const attachmentName = document.getElementById("chat-attachment-name");
    const typingIndicator = document.getElementById("chat-typing-indicator");

    if (!layout || !messagesBox || !form || !textarea) return;

    const messagesUrl = layout.dataset.messagesUrl;
    const sendUrl = layout.dataset.sendUrl;
    const typingUrl = layout.dataset.typingUrl;
    const csrfInput = form.querySelector("input[name='csrfmiddlewaretoken']");
    const csrfToken = csrfInput?.value || "";
    const reactionEmojis = ["👍", "❤️", "😂", "😮", "😢", "🙏"];
    const browserNotificationsEnabled = layout.dataset.browserNotifications === "true";
    const soundNotificationsEnabled = layout.dataset.soundNotifications === "true";
    let notificationAudio = null;
    let typingSendTimer = null;
    let typingIdleTimer = null;
    let lastTypingSentAt = 0;
    const roomId = layout.dataset.roomId || "";
    let chatSocket = null;
    let socketReady = false;
    let socketReconnectTimer = null;
    let pollingTimer = null;

    if (browserNotificationsEnabled && "Notification" in window && Notification.permission === "default") {
        Notification.requestPermission().catch(() => {});
    }

    function lastMessageId() {
        const messages = messagesBox.querySelectorAll(".chat-message[data-message-id]");
        const last = messages[messages.length - 1];
        return last?.dataset.messageId || "0";
    }

    function visibleMessageIds() {
        return Array.from(messagesBox.querySelectorAll(".chat-message[data-message-id]"))
            .map((message) => message.dataset.messageId)
            .filter(Boolean)
            .join(",");
    }

    function hasMessage(messageId) {
        if (!messageId) return false;
        return Boolean(messagesBox.querySelector(`.chat-message[data-message-id="${CSS.escape(String(messageId))}"]`));
    }

    function scrollToBottom() {
        messagesBox.scrollTop = messagesBox.scrollHeight;
    }

    function escapeHtml(value) {
        return String(value || "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");
    }

    function renderMessageText(text) {
        const escaped = escapeHtml(text);
        return escaped
            .replace(/@([\w.@+-]{1,150})/g, '<span class="chat-mention">@$1</span>')
            .replaceAll("\n", "<br>");
    }

    function editedLabel(message) {
        if (!message?.is_edited) return "";
        return `Bearbeitet ${escapeHtml(message.edited_at || "")}`.trim();
    }

    function profileCardTemplate(sender = {}) {
        const avatar = sender.avatar_url
            ? `<img src="${escapeHtml(sender.avatar_url)}" alt="Profilbild" loading="lazy" decoding="async">`
            : escapeHtml(sender.initials || "MT");
        const detail = sender.status_text || sender.bio || sender.status || "";
        return `
            <span class="chat-profile-card" role="tooltip">
                <span class="chat-profile-card-avatar">${avatar}</span>
                <span class="chat-profile-card-copy">
                    <b>${escapeHtml(sender.display_name || sender.username || "Profil")}</b>
                    <small>@${escapeHtml(sender.username || "")}</small>
                    ${detail ? `<em>${escapeHtml(detail)}</em>` : ""}
                </span>
                ${sender.profile_url ? `<a href="${escapeHtml(sender.profile_url)}">Profil</a>` : ""}
            </span>
        `;
    }

    function dateSeparatorTemplate(message) {
        if (!message?.day_key) return "";
        return `<div class="chat-date-separator" data-date-key="${escapeHtml(message.day_key)}"><span>${escapeHtml(message.day_label || "")}</span></div>`;
    }

    function playNotificationSound() {
        if (!soundNotificationsEnabled) return;
        try {
            if (!notificationAudio) {
                notificationAudio = new Audio("data:audio/wav;base64,UklGRjQAAABXQVZFZm10IBAAAAABAAEAESsAACJWAAACABAAZGF0YRAAAAAAAP//AP//AAAA//8AAP//AAAA//8=");
                notificationAudio.volume = 0.28;
            }
            notificationAudio.currentTime = 0;
            notificationAudio.play().catch(() => {});
        } catch (error) {
            console.warn("Notification sound failed", error);
        }
    }

    function showBrowserNotification(message) {
        if (!browserNotificationsEnabled || !("Notification" in window) || Notification.permission !== "granted") return;
        if (document.visibilityState === "visible") return;
        const text = message.text || (message.attachments?.length ? "Neuer Anhang" : "Neue Nachricht");
        try {
            new Notification(message.sender?.display_name || "Neue Chatnachricht", {
                body: text,
                icon: message.sender?.avatar_url || undefined,
            });
        } catch (error) {
            console.warn("Browser notification failed", error);
        }
    }

    function reactionsTemplate(reactions = []) {
        const items = reactions.map((reaction) => {
            const mineClass = reaction.mine ? " is-mine" : "";
            return `<span class="chat-reaction${mineClass}">${escapeHtml(reaction.emoji)} <b>${escapeHtml(reaction.count)}</b></span>`;
        }).join("");
        return `<div class="chat-reactions ${reactions.length ? "" : "is-empty"}">${items}</div>`;
    }

    function emojiPickerTemplate() {
        return `<div class="chat-emoji-picker" aria-label="Emoji auswählen">${reactionEmojis.map((emoji) => (
            `<button type="button" data-emoji="${escapeHtml(emoji)}">${escapeHtml(emoji)}</button>`
        )).join("")}</div>`;
    }

    function attachmentsTemplate(attachments = []) {
        if (!attachments.length) return "";
        return `<div class="chat-attachments">${attachments.map((attachment) => {
            const imageUrl = attachment.preview_url || attachment.url;
            const image = attachment.is_image && imageUrl
                ? `<img src="${escapeHtml(imageUrl)}" alt="${escapeHtml(attachment.name)}" loading="lazy" decoding="async">`
                : `<i class="fa-solid fa-paperclip"></i>`;
            return `<a href="${escapeHtml(attachment.url)}" class="chat-attachment${attachment.is_image ? " is-image" : ""}" target="_blank" rel="noopener">${image}<span>${escapeHtml(attachment.name)}</span></a>`;
        }).join("")}</div>`;
    }

    function pinnedMessageTemplate(message) {
        if (!message) return "";
        const text = message.text || (message.attachments?.length ? "Anhang" : "Nachricht");
        return `
            <button type="button" class="chat-pinned-jump" data-pinned-jump="${escapeHtml(message.id)}">
                <i class="fa-solid fa-thumbtack"></i>
                <span>
                    <strong>Angepinnt</strong>
                    <small>${escapeHtml(message.sender?.display_name || message.sender?.username || "Chat")}: ${escapeHtml(text).slice(0, 92)}</small>
                </span>
            </button>
        `;
    }

    function updatePinMenuLabels() {
        messagesBox.querySelectorAll(".chat-message[data-message-id]").forEach((message) => {
            const button = message.querySelector('[data-chat-action="pin"]');
            const label = button?.querySelector("span");
            if (!button || !label) return;
            label.textContent = message.classList.contains("is-pinned")
                ? (button.dataset.unpinLabel || "Losloesen")
                : (button.dataset.pinLabel || "Anpinnen");
        });
    }

    function renderPinnedMessage(message) {
        if (!pinnedBox) return;
        pinnedBox.innerHTML = pinnedMessageTemplate(message);
        pinnedBox.classList.toggle("is-empty", !message);
        messagesBox.querySelectorAll(".chat-message.is-pinned").forEach((item) => {
            item.classList.remove("is-pinned");
        });
        if (message?.id) {
            messagesBox.querySelector(`.chat-message[data-message-id="${CSS.escape(String(message.id))}"]`)?.classList.add("is-pinned");
        }
        updatePinMenuLabels();
    }

    function messageTemplate(message) {
        const avatar = message.sender.avatar_url
            ? `<img src="${escapeHtml(message.sender.avatar_url)}" alt="Profilbild" loading="lazy" decoding="async">`
            : escapeHtml(message.sender.initials || "MT");
        const text = renderMessageText(message.text);
        const isOwn = Boolean(message.is_own);
        const deleteAction = isOwn
            ? `<button type="button" data-chat-action="delete"><i class="fa-solid fa-trash"></i>Löschen</button>`
            : "";
        const editAction = isOwn
            ? `<button type="button" data-chat-action="edit"><i class="fa-solid fa-pen"></i>Bearbeiten</button>`
            : "";
        const pinLabel = message.is_pinned ? "Losloesen" : "Anpinnen";

        return `
            <div class="chat-message ${isOwn ? "is-own" : ""} ${message.is_pinned ? "is-pinned" : ""}"
                 data-message-id="${escapeHtml(message.id)}"
                 data-date-key="${escapeHtml(message.day_key || "")}"
                 data-pin-url="${escapeHtml(message.pin_url)}"
                 data-react-url="${escapeHtml(message.react_url)}"
                 ${isOwn ? `data-delete-url="${escapeHtml(message.delete_url)}" data-edit-url="${escapeHtml(message.edit_url)}"` : ""}>
                <div class="chat-message-avatar">${avatar}</div>
                <div class="chat-bubble">
                    <button type="button" class="chat-message-menu-button" aria-label="Nachrichtoptionen">
                        <i class="fa-solid fa-ellipsis"></i>
                    </button>
                    <div class="chat-message-menu">
                        <button type="button" data-chat-action="react"><i class="fa-regular fa-face-smile"></i>Reagieren</button>
                        <button type="button" data-chat-action="pin" data-pin-label="Anpinnen" data-unpin-label="Losloesen"><i class="fa-solid fa-thumbtack"></i><span>${pinLabel}</span></button>
                        ${editAction}
                        ${deleteAction}
                    </div>
                    ${emojiPickerTemplate()}
                    <div class="chat-message-meta">
                        <span class="chat-sender-hover">
                            <strong>${escapeHtml(message.sender.display_name)}</strong>
                            ${profileCardTemplate(message.sender)}
                        </span>
                        <span>${escapeHtml(message.created_at)}</span>
                    </div>
                    ${text ? `<p class="chat-message-text" data-raw-text="${escapeHtml(message.text)}">${text}</p>` : ""}
                    <form class="chat-edit-form" hidden>
                        <textarea maxlength="1200">${escapeHtml(message.text)}</textarea>
                        <div>
                            <button type="submit"><i class="fa-solid fa-check"></i>Speichern</button>
                            <button type="button" data-chat-action="cancel-edit"><i class="fa-solid fa-xmark"></i>Abbrechen</button>
                        </div>
                    </form>
                    ${attachmentsTemplate(message.attachments || [])}
                    <small class="chat-edit-state ${message.is_edited ? "" : "is-empty"}">${editedLabel(message)}</small>
                    ${isOwn ? `<small class="chat-read-state">${escapeHtml(message.read_label || "")}</small>` : ""}
                    ${reactionsTemplate(message.reactions || [])}
                </div>
            </div>
        `;
    }

    function currentLastDateKey() {
        const messages = messagesBox.querySelectorAll(".chat-message[data-date-key]");
        const last = messages[messages.length - 1];
        return last?.dataset.dateKey || "";
    }

    function messagesWithDateSeparators(messages = []) {
        let lastDateKey = currentLastDateKey();
        return messages.map((message) => {
            const needsSeparator = message.day_key && message.day_key !== lastDateKey;
            lastDateKey = message.day_key || lastDateKey;
            return `${needsSeparator ? dateSeparatorTemplate(message) : ""}${messageTemplate(message)}`;
        }).join("");
    }

    function appendMessages(messages, fromPolling = false) {
        const newMessages = (messages || []).filter((message) => !hasMessage(message.id));
        if (!newMessages.length) return;
        document.getElementById("chat-empty-state")?.remove();
        const shouldStick = messagesBox.scrollHeight - messagesBox.scrollTop - messagesBox.clientHeight < 140;
        messagesBox.insertAdjacentHTML("beforeend", messagesWithDateSeparators(newMessages));
        if (shouldStick) scrollToBottom();
        if (fromPolling) {
            const incoming = newMessages.filter((message) => !message.is_own);
            if (incoming.length) {
                playNotificationSound();
                showBrowserNotification(incoming[incoming.length - 1]);
            }
        }
    }

    function applyDeletedMessages(deletedIds = []) {
        deletedIds.forEach((id) => {
            messagesBox.querySelector(`.chat-message[data-message-id="${CSS.escape(String(id))}"]`)?.remove();
        });
    }

    function updateMessageState(messageElement, update) {
        if (update.text !== undefined) {
            const textElement = messageElement.querySelector(".chat-message-text");
            const editForm = messageElement.querySelector(".chat-edit-form");
            const editTextarea = editForm?.querySelector("textarea");
            if (textElement) {
                textElement.dataset.rawText = update.text || "";
                textElement.innerHTML = renderMessageText(update.text || "");
                textElement.hidden = !update.text;
            }
            if (editTextarea) editTextarea.value = update.text || "";
        }
        const editState = messageElement.querySelector(".chat-edit-state");
        if (editState && update.is_edited !== undefined) {
            editState.textContent = editedLabel(update);
            editState.classList.toggle("is-empty", !update.is_edited);
        }
        const oldStrip = messageElement.querySelector(".chat-reactions");
        if (oldStrip) oldStrip.outerHTML = reactionsTemplate(update.reactions || []);
        const readState = messageElement.querySelector(".chat-read-state");
        if (readState && update.read_label !== undefined) readState.textContent = update.read_label || "";
        if (update.is_pinned !== undefined) {
            messageElement.classList.toggle("is-pinned", Boolean(update.is_pinned));
            updatePinMenuLabels();
        }
    }

    function applyMessageUpdates(updates = []) {
        updates.forEach((update) => {
            const messageElement = messagesBox.querySelector(`.chat-message[data-message-id="${CSS.escape(String(update.id))}"]`);
            if (messageElement) updateMessageState(messageElement, update);
        });
    }

    function renderTypingUsers(users = []) {
        if (!typingIndicator) return;
        if (!users.length) {
            typingIndicator.textContent = "";
            typingIndicator.classList.remove("is-visible");
            return;
        }
        const names = users.map((user) => user.display_name || user.username).filter(Boolean);
        typingIndicator.textContent = names.length === 1
            ? `${names[0]} tippt...`
            : `${names.slice(0, 2).join(", ")} tippen...`;
        typingIndicator.classList.add("is-visible");
    }

    async function sendTypingState(isTyping) {
        if (socketReady && chatSocket) {
            try {
                chatSocket.send(JSON.stringify({action: "typing", isTyping: Boolean(isTyping)}));
                return;
            } catch (error) {
                console.warn("Typing websocket update failed", error);
            }
        }

        if (!typingUrl) return;
        const formData = new FormData();
        formData.append("csrfmiddlewaretoken", csrfToken);
        formData.append("is_typing", isTyping ? "true" : "false");
        try {
            await fetch(typingUrl, {method: "POST", headers: {"X-Requested-With": "XMLHttpRequest"}, body: formData});
        } catch (error) {
            console.warn("Typing update failed", error);
        }
    }

    function scheduleTypingState() {
        if (!typingUrl) return;
        const now = Date.now();
        if (now - lastTypingSentAt > 1800) {
            lastTypingSentAt = now;
            sendTypingState(true);
        } else {
            window.clearTimeout(typingSendTimer);
            typingSendTimer = window.setTimeout(() => {
                lastTypingSentAt = Date.now();
                sendTypingState(true);
            }, 350);
        }
        window.clearTimeout(typingIdleTimer);
        typingIdleTimer = window.setTimeout(() => sendTypingState(false), 2600);
    }

    async function pollMessages() {
        if (socketReady) return;
        try {
            const url = `${messagesUrl}?after=${encodeURIComponent(lastMessageId())}&visible=${encodeURIComponent(visibleMessageIds())}`;
            const response = await fetch(url, {headers: {"X-Requested-With": "XMLHttpRequest"}});
            if (!response.ok) return;
            const data = await response.json();
            if (data.ok) {
                applyDeletedMessages(data.deleted_ids || []);
                applyMessageUpdates(data.updates || []);
                renderPinnedMessage(data.pinned_message || null);
                renderTypingUsers(data.typing_users || []);
                appendMessages(data.messages || [], true);
            }
        } catch (error) {
            console.warn("Chat polling failed", error);
        }
    }

    function websocketUrl() {
        if (!roomId) return "";
        const protocol = window.location.protocol === "https:" ? "wss" : "ws";
        return `${protocol}://${window.location.host}/ws/chat/${encodeURIComponent(roomId)}/`;
    }

    function handleSocketEvent(data) {
        if (!data || !data.type) return;
        if (data.type === "message_created" && data.message) {
            appendMessages([data.message], true);
            return;
        }
        if (data.type === "message_updated" && data.message) {
            applyMessageUpdates([data.message]);
            return;
        }
        if (data.type === "message_deleted") {
            applyDeletedMessages(data.deletedIds || data.deleted_ids || []);
            return;
        }
        if (data.type === "pinned_updated") {
            renderPinnedMessage(data.pinnedMessage || data.pinned_message || null);
            return;
        }
        if (data.type === "typing") {
            renderTypingUsers(data.typingUsers || data.typing_users || []);
        }
    }

    function startPollingFallback() {
        if (pollingTimer) return;
        pollingTimer = window.setInterval(pollMessages, 3500);
    }

    function stopPollingFallback() {
        if (!pollingTimer) return;
        window.clearInterval(pollingTimer);
        pollingTimer = null;
    }

    function connectChatSocket() {
        const url = websocketUrl();
        if (!url || !("WebSocket" in window)) {
            startPollingFallback();
            return;
        }

        try {
            chatSocket = new WebSocket(url);
        } catch (error) {
            console.warn("Chat websocket unavailable", error);
            startPollingFallback();
            return;
        }

        chatSocket.addEventListener("open", () => {
            socketReady = true;
            stopPollingFallback();
        });

        chatSocket.addEventListener("message", (event) => {
            try {
                handleSocketEvent(JSON.parse(event.data));
            } catch (error) {
                console.warn("Chat websocket message failed", error);
            }
        });

        chatSocket.addEventListener("close", () => {
            socketReady = false;
            chatSocket = null;
            startPollingFallback();
            window.clearTimeout(socketReconnectTimer);
            socketReconnectTimer = window.setTimeout(connectChatSocket, 2500);
        });

        chatSocket.addEventListener("error", () => {
            socketReady = false;
            startPollingFallback();
        });
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const text = textarea.value.trim();
        const hasAttachment = attachmentInput?.files?.length > 0;
        if (!text && !hasAttachment) return;

        const formData = new FormData();
        formData.append("text", text);
        formData.append("csrfmiddlewaretoken", csrfToken);
        if (hasAttachment) {
            Array.from(attachmentInput.files).forEach((file) => {
                formData.append("attachments", file);
            });
        }
        textarea.value = "";
        if (attachmentInput) attachmentInput.value = "";
        if (attachmentName) attachmentName.textContent = "";
        textarea.style.height = "auto";
        sendTypingState(false);

        try {
            const response = await fetch(sendUrl, {
                method: "POST",
                headers: {"X-Requested-With": "XMLHttpRequest"},
                body: formData,
            });
            const data = await response.json();
            if (data.ok && data.message) {
                appendMessages([data.message]);
                scrollToBottom();
            }
        } catch (error) {
            console.warn("Message send failed", error);
        }
    });

    textarea.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" || event.shiftKey) return;
        event.preventDefault();
        if (textarea.value.trim() || attachmentInput?.files?.length) form.requestSubmit();
    });

    textarea.addEventListener("input", () => {
        textarea.style.height = "auto";
        textarea.style.height = `${Math.min(textarea.scrollHeight, 140)}px`;
        if (textarea.value.trim()) scheduleTypingState();
        else sendTypingState(false);
    });

    attachmentInput?.addEventListener("change", () => {
        const files = Array.from(attachmentInput.files || []);
        if (attachmentName) {
            attachmentName.textContent = files.length
                ? files.map((file) => file.name).join(", ")
                : "";
        }
    });

    function setMessageEditing(message, isEditing) {
        const editForm = message.querySelector(".chat-edit-form");
        const textElement = message.querySelector(".chat-message-text");
        if (!editForm) return;
        editForm.hidden = !isEditing;
        if (textElement) textElement.hidden = isEditing;
        message.classList.toggle("is-editing", isEditing);
        if (isEditing) {
            const textarea = editForm.querySelector("textarea");
            textarea?.focus();
            textarea?.setSelectionRange(textarea.value.length, textarea.value.length);
        }
    }

    pinnedBox?.addEventListener("click", (event) => {
        const jumpButton = event.target.closest("[data-pinned-jump]");
        if (!jumpButton) return;
        const message = messagesBox.querySelector(`.chat-message[data-message-id="${CSS.escape(String(jumpButton.dataset.pinnedJump))}"]`);
        if (!message) return;
        message.scrollIntoView({block: "center", behavior: "smooth"});
        message.classList.add("is-highlighted");
        window.setTimeout(() => message.classList.remove("is-highlighted"), 1400);
    });

    messagesBox.addEventListener("click", async (event) => {
        const menuButton = event.target.closest(".chat-message-menu-button");
        const actionButton = event.target.closest("[data-chat-action]");
        const emojiButton = event.target.closest("[data-emoji]");

        if (menuButton) {
            event.preventDefault();
            const message = menuButton.closest(".chat-message");
            const wasOpen = message.classList.contains("is-menu-open");
            messagesBox.querySelectorAll(".chat-message.is-menu-open, .chat-message.is-emoji-open").forEach((item) => {
                item.classList.remove("is-menu-open", "is-emoji-open");
            });
            if (!wasOpen) message.classList.add("is-menu-open");
            return;
        }

        if (actionButton) {
            event.preventDefault();
            const message = actionButton.closest(".chat-message");
            const action = actionButton.dataset.chatAction;
            if (action === "pin") {
                const pinUrl = message.dataset.pinUrl;
                if (!pinUrl) return;
                const formData = new FormData();
                formData.append("csrfmiddlewaretoken", csrfToken);
                formData.append("action", message.classList.contains("is-pinned") ? "unpin" : "pin");
                try {
                    const response = await fetch(pinUrl, {method: "POST", headers: {"X-Requested-With": "XMLHttpRequest"}, body: formData});
                    const data = await response.json();
                    if (data.ok) {
                        renderPinnedMessage(data.pinned_message || null);
                        message.classList.remove("is-menu-open");
                    }
                } catch (error) {
                    console.warn("Message pin failed", error);
                }
                return;
            }
            if (action === "delete") {
                const deleteUrl = message.dataset.deleteUrl;
                if (!deleteUrl || !confirm("Diese Nachricht wirklich löschen?")) return;
                const formData = new FormData();
                formData.append("csrfmiddlewaretoken", csrfToken);
                try {
                    const response = await fetch(deleteUrl, {method: "POST", headers: {"X-Requested-With": "XMLHttpRequest"}, body: formData});
                    const data = await response.json();
                    if (data.ok) message.remove();
                } catch (error) {
                    console.warn("Message delete failed", error);
                }
                return;
            }
            if (action === "edit") {
                message.classList.remove("is-menu-open", "is-emoji-open");
                setMessageEditing(message, true);
                return;
            }
            if (action === "cancel-edit") {
                const editForm = message.querySelector(".chat-edit-form");
                const editTextarea = editForm?.querySelector("textarea");
                const textElement = message.querySelector(".chat-message-text");
                if (editTextarea && textElement) editTextarea.value = textElement.dataset.rawText || "";
                setMessageEditing(message, false);
                return;
            }
            if (action === "react") {
                message.classList.remove("is-menu-open");
                message.classList.toggle("is-emoji-open");
            }
            return;
        }

        if (emojiButton) {
            event.preventDefault();
            const message = emojiButton.closest(".chat-message");
            const reactUrl = message.dataset.reactUrl;
            if (!reactUrl) return;
            const formData = new FormData();
            formData.append("csrfmiddlewaretoken", csrfToken);
            formData.append("emoji", emojiButton.dataset.emoji);
            try {
                const response = await fetch(reactUrl, {method: "POST", headers: {"X-Requested-With": "XMLHttpRequest"}, body: formData});
                const data = await response.json();
                if (data.ok) {
                    updateMessageState(message, data);
                    message.classList.remove("is-emoji-open");
                }
            } catch (error) {
                console.warn("Message reaction failed", error);
            }
            return;
        }

        if (!event.target.closest(".chat-message-menu, .chat-emoji-picker")) {
            messagesBox.querySelectorAll(".chat-message.is-menu-open, .chat-message.is-emoji-open").forEach((item) => {
                item.classList.remove("is-menu-open", "is-emoji-open");
            });
        }
    });

    messagesBox.addEventListener("submit", async (event) => {
        const editForm = event.target.closest(".chat-edit-form");
        if (!editForm) return;
        event.preventDefault();
        const message = editForm.closest(".chat-message");
        const editUrl = message?.dataset.editUrl;
        const editTextarea = editForm.querySelector("textarea");
        const text = editTextarea?.value.trim() || "";
        if (!editUrl || !text) return;

        const formData = new FormData();
        formData.append("csrfmiddlewaretoken", csrfToken);
        formData.append("text", text);
        try {
            const response = await fetch(editUrl, {method: "POST", headers: {"X-Requested-With": "XMLHttpRequest"}, body: formData});
            const data = await response.json();
            if (data.ok && data.message) {
                updateMessageState(message, data.message);
                setMessageEditing(message, false);
            }
        } catch (error) {
            console.warn("Message edit failed", error);
        }
    });

    document.addEventListener("click", (event) => {
        if (event.target.closest("#chat-messages")) return;
        messagesBox.querySelectorAll(".chat-message.is-menu-open, .chat-message.is-emoji-open").forEach((item) => {
            item.classList.remove("is-menu-open", "is-emoji-open");
        });
    });

    messagesBox.querySelectorAll(".chat-message-text").forEach((textElement) => {
        const rawText = textElement.dataset.rawText || textElement.textContent || "";
        textElement.dataset.rawText = rawText;
        textElement.innerHTML = renderMessageText(rawText);
    });
    updatePinMenuLabels();
    scrollToBottom();
    connectChatSocket();
    startPollingFallback();
});
