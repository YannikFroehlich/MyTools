document.addEventListener("DOMContentLoaded", () => {
    const layout = document.querySelector(".chat-layout");
    const messagesBox = document.getElementById("chat-messages");
    const pinnedBox = document.getElementById("chat-pinned-message");
    const form = document.getElementById("chat-compose-form");
    const textarea = form?.querySelector("textarea[name='text']");
    const attachmentInput = form?.querySelector("input[name='attachment']");
    const attachmentName = document.getElementById("chat-attachment-name");

    if (!layout || !messagesBox || !form || !textarea) return;

    const messagesUrl = layout.dataset.messagesUrl;
    const sendUrl = layout.dataset.sendUrl;
    const csrfInput = form.querySelector("input[name='csrfmiddlewaretoken']");
    const csrfToken = csrfInput?.value || "";
    const reactionEmojis = ["👍", "❤️", "😂", "😮", "😢", "🙏"];
    const browserNotificationsEnabled = layout.dataset.browserNotifications === "true";
    const soundNotificationsEnabled = layout.dataset.soundNotifications === "true";
    let notificationAudio = null;

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
        const text = escapeHtml(message.text).replaceAll("\n", "<br>");
        const isOwn = Boolean(message.is_own);
        const deleteAction = isOwn
            ? `<button type="button" data-chat-action="delete"><i class="fa-solid fa-trash"></i>Löschen</button>`
            : "";
        const pinLabel = message.is_pinned ? "Losloesen" : "Anpinnen";

        return `
            <div class="chat-message ${isOwn ? "is-own" : ""} ${message.is_pinned ? "is-pinned" : ""}"
                 data-message-id="${escapeHtml(message.id)}"
                 data-pin-url="${escapeHtml(message.pin_url)}"
                 data-react-url="${escapeHtml(message.react_url)}"
                 ${isOwn ? `data-delete-url="${escapeHtml(message.delete_url)}"` : ""}>
                <div class="chat-message-avatar">${avatar}</div>
                <div class="chat-bubble">
                    <button type="button" class="chat-message-menu-button" aria-label="Nachrichtoptionen">
                        <i class="fa-solid fa-ellipsis"></i>
                    </button>
                    <div class="chat-message-menu">
                        <button type="button" data-chat-action="react"><i class="fa-regular fa-face-smile"></i>Reagieren</button>
                        <button type="button" data-chat-action="pin" data-pin-label="Anpinnen" data-unpin-label="Losloesen"><i class="fa-solid fa-thumbtack"></i><span>${pinLabel}</span></button>
                        ${deleteAction}
                    </div>
                    ${emojiPickerTemplate()}
                    <div class="chat-message-meta">
                        <strong>${escapeHtml(message.sender.display_name)}</strong>
                        <span>${escapeHtml(message.created_at)}</span>
                    </div>
                    ${text ? `<p>${text}</p>` : ""}
                    ${attachmentsTemplate(message.attachments || [])}
                    ${isOwn ? `<small class="chat-read-state">${escapeHtml(message.read_label || "")}</small>` : ""}
                    ${reactionsTemplate(message.reactions || [])}
                </div>
            </div>
        `;
    }

    function appendMessages(messages, fromPolling = false) {
        if (!messages.length) return;
        document.getElementById("chat-empty-state")?.remove();
        const shouldStick = messagesBox.scrollHeight - messagesBox.scrollTop - messagesBox.clientHeight < 140;
        messagesBox.insertAdjacentHTML("beforeend", messages.map(messageTemplate).join(""));
        if (shouldStick) scrollToBottom();
        if (fromPolling) {
            const incoming = messages.filter((message) => !message.is_own);
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

    async function pollMessages() {
        try {
            const url = `${messagesUrl}?after=${encodeURIComponent(lastMessageId())}&visible=${encodeURIComponent(visibleMessageIds())}`;
            const response = await fetch(url, {headers: {"X-Requested-With": "XMLHttpRequest"}});
            if (!response.ok) return;
            const data = await response.json();
            if (data.ok) {
                applyDeletedMessages(data.deleted_ids || []);
                applyMessageUpdates(data.updates || []);
                renderPinnedMessage(data.pinned_message || null);
                appendMessages(data.messages || [], true);
            }
        } catch (error) {
            console.warn("Chat polling failed", error);
        }
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const text = textarea.value.trim();
        const hasAttachment = attachmentInput?.files?.length > 0;
        if (!text && !hasAttachment) return;

        const formData = new FormData();
        formData.append("text", text);
        formData.append("csrfmiddlewaretoken", csrfToken);
        if (hasAttachment) formData.append("attachment", attachmentInput.files[0]);
        textarea.value = "";
        if (attachmentInput) attachmentInput.value = "";
        if (attachmentName) attachmentName.textContent = "";
        textarea.style.height = "auto";

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
    });

    attachmentInput?.addEventListener("change", () => {
        const file = attachmentInput.files?.[0];
        if (attachmentName) attachmentName.textContent = file ? file.name : "";
    });

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

    document.addEventListener("click", (event) => {
        if (event.target.closest("#chat-messages")) return;
        messagesBox.querySelectorAll(".chat-message.is-menu-open, .chat-message.is-emoji-open").forEach((item) => {
            item.classList.remove("is-menu-open", "is-emoji-open");
        });
    });

    updatePinMenuLabels();
    scrollToBottom();
    setInterval(pollMessages, 3500);
});
