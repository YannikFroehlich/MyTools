document.addEventListener("DOMContentLoaded", () => {
    const layout = document.querySelector(".chat-layout");
    const messagesBox = document.getElementById("chat-messages");
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
            const image = attachment.is_image && attachment.url
                ? `<img src="${escapeHtml(attachment.url)}" alt="${escapeHtml(attachment.name)}">`
                : `<i class="fa-solid fa-paperclip"></i>`;
            return `<a href="${escapeHtml(attachment.url)}" class="chat-attachment${attachment.is_image ? " is-image" : ""}" target="_blank" rel="noopener">${image}<span>${escapeHtml(attachment.name)}</span></a>`;
        }).join("")}</div>`;
    }

    function messageTemplate(message) {
        const avatar = message.sender.avatar_url
            ? `<img src="${escapeHtml(message.sender.avatar_url)}" alt="Profilbild">`
            : escapeHtml(message.sender.initials || "MT");
        const text = escapeHtml(message.text).replaceAll("\n", "<br>");
        const isOwn = Boolean(message.is_own);
        const menuButton = `
            <button type="button" class="chat-message-menu-button" aria-label="Nachrichtoptionen">
                <i class="fa-solid fa-ellipsis"></i>
            </button>
        `;
        const menu = isOwn
            ? `<div class="chat-message-menu"><button type="button" data-chat-action="delete"><i class="fa-solid fa-trash"></i>Löschen</button></div>`
            : `<div class="chat-message-menu"><button type="button" data-chat-action="react"><i class="fa-regular fa-face-smile"></i>Reagieren</button></div>${emojiPickerTemplate()}`;

        return `
            <div class="chat-message ${isOwn ? "is-own" : ""}"
                 data-message-id="${escapeHtml(message.id)}"
                 ${isOwn ? `data-delete-url="${escapeHtml(message.delete_url)}"` : `data-react-url="${escapeHtml(message.react_url)}"`}>
                <div class="chat-message-avatar">${avatar}</div>
                <div class="chat-bubble">
                    ${menuButton}
                    ${menu}
                    <div class="chat-message-meta">
                        <strong>${escapeHtml(message.sender.display_name)}</strong>
                        <span>${escapeHtml(message.created_at)}</span>
                    </div>
                    ${text ? `<p>${text}</p>` : ""}
                    ${attachmentsTemplate(message.attachments || [])}
                    ${reactionsTemplate(message.reactions || [])}
                </div>
            </div>
        `;
    }

    function appendMessages(messages) {
        if (!messages.length) return;
        document.getElementById("chat-empty-state")?.remove();
        const shouldStick = messagesBox.scrollHeight - messagesBox.scrollTop - messagesBox.clientHeight < 140;
        messagesBox.insertAdjacentHTML("beforeend", messages.map(messageTemplate).join(""));
        if (shouldStick) scrollToBottom();
    }

    function applyDeletedMessages(deletedIds = []) {
        deletedIds.forEach((id) => {
            messagesBox.querySelector(`.chat-message[data-message-id="${CSS.escape(String(id))}"]`)?.remove();
        });
    }

    function updateReactionStrip(messageElement, reactions = []) {
        const oldStrip = messageElement.querySelector(".chat-reactions");
        if (oldStrip) {
            oldStrip.outerHTML = reactionsTemplate(reactions);
        }
    }

    function applyMessageUpdates(updates = []) {
        updates.forEach((update) => {
            const messageElement = messagesBox.querySelector(`.chat-message[data-message-id="${CSS.escape(String(update.id))}"]`);
            if (messageElement) updateReactionStrip(messageElement, update.reactions || []);
        });
    }

    async function pollMessages() {
        try {
            const url = `${messagesUrl}?after=${encodeURIComponent(lastMessageId())}&visible=${encodeURIComponent(visibleMessageIds())}`;
            const response = await fetch(url, {
                headers: {"X-Requested-With": "XMLHttpRequest"},
            });
            if (!response.ok) return;
            const data = await response.json();
            if (data.ok) {
                applyDeletedMessages(data.deleted_ids || []);
                applyMessageUpdates(data.updates || []);
                appendMessages(data.messages || []);
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
                attachmentInput?.addEventListener("change", () => {
        const file = attachmentInput.files?.[0];
        if (attachmentName) attachmentName.textContent = file ? file.name : "";
    });

    scrollToBottom();
            }
        } catch (error) {
            console.warn("Message send failed", error);
        }
    });

    textarea.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" || event.shiftKey) return;

        event.preventDefault();
        if (textarea.value.trim()) {
            form.requestSubmit();
        }
    });

    textarea.addEventListener("input", () => {
        textarea.style.height = "auto";
        textarea.style.height = `${Math.min(textarea.scrollHeight, 140)}px`;
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

            if (action === "delete") {
                const deleteUrl = message.dataset.deleteUrl;
                if (!deleteUrl) return;
                if (!confirm("Diese Nachricht wirklich löschen?")) return;

                const formData = new FormData();
                formData.append("csrfmiddlewaretoken", csrfToken);

                try {
                    const response = await fetch(deleteUrl, {
                        method: "POST",
                        headers: {"X-Requested-With": "XMLHttpRequest"},
                        body: formData,
                    });
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
                const response = await fetch(reactUrl, {
                    method: "POST",
                    headers: {"X-Requested-With": "XMLHttpRequest"},
                    body: formData,
                });
                const data = await response.json();
                if (data.ok) {
                    updateReactionStrip(message, data.reactions || []);
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

    attachmentInput?.addEventListener("change", () => {
        const file = attachmentInput.files?.[0];
        if (attachmentName) attachmentName.textContent = file ? file.name : "";
    });

    scrollToBottom();
    setInterval(pollMessages, 3500);
});
