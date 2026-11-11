let chatHistory = [];

function toggleChatbot() {
  const widget = document.getElementById('chatbot-widget');
  widget.style.display = widget.style.display === 'none' ? 'flex' : 'none';
  widget.style.flexDirection = 'column';
  if (widget.style.display !== 'none') {
    document.getElementById('chat-input').focus();
  }
}

async function sendChat() {
  const input = document.getElementById('chat-input');
  const msg = input.value.trim();
  if (!msg) return;
  input.value = '';

  appendMessage('user', msg);
  chatHistory.push({ role: 'user', content: msg });

  // Typing indicator
  const typingId = appendMessage('bot', '...');

  try {
    const res = await fetch('/api/chatbot/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages: chatHistory })
    });
    const data = await res.json();
    const reply = data.reply || 'Sorry, I could not process that.';
    updateMessage(typingId, reply);
    chatHistory.push({ role: 'assistant', content: reply });
  } catch (e) {
    updateMessage(typingId, 'Connection error. Please try again.');
  }
}

function appendMessage(role, content) {
  const container = document.getElementById('chat-msgs');
  const id = 'msg-' + Date.now() + '-' + Math.random().toString(36).slice(2, 7);
  const div = document.createElement('div');
  div.id = id;
  div.className = `cmsg ${role}`;
  div.innerHTML = role === 'bot' ? formatBotMessage(content) : escapeHtml(content);
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
  return id;
}

function updateMessage(id, content) {
  const el = document.getElementById(id);
  if (el) el.innerHTML = formatBotMessage(content);
  const container = document.getElementById('chat-msgs');
  container.scrollTop = container.scrollHeight;
}

// ─── Lightweight, safe markdown-ish renderer for bot replies ───
// Escapes all HTML first (so the model can never inject markup), then
// re-introduces a small whitelist of formatting: bold, italics, links,
// bullet/numbered lists, and paragraph/line breaks.
function formatBotMessage(raw) {
  if (!raw) return '';

  let text = escapeHtml(raw).trim();

  // Bold: **text** or __text__
  text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  text = text.replace(/__(.+?)__/g, '<strong>$1</strong>');

  // Italics: *text* or _text_ (after bold is already handled)
  text = text.replace(/\*(.+?)\*/g, '<em>$1</em>');
  text = text.replace(/(^|\s)_(.+?)_(?=\s|$)/g, '$1<em>$2</em>');

  // Auto-link URLs
  text = text.replace(
    /((https?:\/\/|www\.)[^\s<]+)/g,
    (match) => {
      const href = match.startsWith('http') ? match : `https://${match}`;
      return `<a href="${href}" target="_blank" rel="noopener noreferrer">${match}</a>`;
    }
  );

  // Split into blocks by line breaks, grouping consecutive list items
  // into a single <ul> or <ol>.
  const lines = text.split(/\n/);
  let html = '';
  let listBuffer = [];
  let listType = null; // 'ul' | 'ol'

  const flushList = () => {
    if (listBuffer.length) {
      html += `<${listType}>${listBuffer.map(li => `<li>${li}</li>`).join('')}</${listType}>`;
      listBuffer = [];
      listType = null;
    }
  };

  for (const line of lines) {
    const trimmed = line.trim();
    const bulletMatch = trimmed.match(/^[-*\u2022]\s+(.*)$/);
    const numberedMatch = trimmed.match(/^\d+[.)]\s+(.*)$/);

    if (bulletMatch) {
      if (listType !== 'ul') { flushList(); listType = 'ul'; }
      listBuffer.push(bulletMatch[1]);
    } else if (numberedMatch) {
      if (listType !== 'ol') { flushList(); listType = 'ol'; }
      listBuffer.push(numberedMatch[1]);
    } else {
      flushList();
      if (trimmed) html += `<p>${trimmed}</p>`;
    }
  }
  flushList();

  return html || `<p>${text}</p>`;
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
