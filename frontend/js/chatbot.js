let chatHistory = [];

function toggleChatbot() {
  const widget = document.getElementById('chatbot-widget');
  widget.style.display = widget.style.display === 'none' ? 'flex' : 'none';
  widget.style.flexDirection = 'column';
  if (widget.style.display !== 'none') {
    document.getElementById('chat-input').focus();
  }
}

async function sendChat(viaVoice) {
  const input = document.getElementById('chat-input');
  const msg = input.value.trim();
  if (!msg) return;
  input.value = '';

  stopSpeaking();
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
    if (viaVoice === true || voiceOn) speak(reply);      // questions asked by voice are answered by voice
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


// ─── Voice: speak to the assistant (🎤) and have it read answers aloud (🔊) ───
// Uses the browser's built-in speech recognition and speech synthesis (no extra service or key needed).
const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
let voiceOn = localStorage.getItem('chatVoice') === '1';
let voiceLang = localStorage.getItem('chatLang') || 'en-US';
let recog = null, listening = false;

function plainForSpeech(t) {
  return String(t || '').replace(/\[(.*?)\]\(.*?\)/g, '$1').replace(/https?:\/\/\S+/g, '').replace(/[*_`#>]/g, '')
    .replace(/^\s*[-•]\s+/gm, '').replace(/^\s*\d+[.)]\s+/gm, '').replace(/\n+/g, '. ').trim();
}
function stopSpeaking() { try { window.speechSynthesis && speechSynthesis.cancel(); } catch (e) {} }
function speak(text) {
  if (!('speechSynthesis' in window)) return;
  stopSpeaking();
  const u = new SpeechSynthesisUtterance(plainForSpeech(text));
  u.lang = voiceLang; u.rate = 1;
  const v = speechSynthesis.getVoices().find(x => x.lang && x.lang.toLowerCase().startsWith(voiceLang.slice(0, 2).toLowerCase()));
  if (v) u.voice = v;
  speechSynthesis.speak(u);
}
function stopListening() { listening = false; try { recog && recog.abort(); } catch (e) {} setMicState(); }
function setMicState() {
  const m = document.getElementById('chat-mic'); if (!m) return;
  m.classList.toggle('listening', listening); m.title = listening ? 'Listening… tap to stop' : 'Speak your question';
}
function toggleMic() {
  if (listening) { stopListening(); return; }
  stopSpeaking();
  recog = new SpeechRec(); recog.lang = voiceLang; recog.interimResults = true; recog.maxAlternatives = 1;
  const input = document.getElementById('chat-input'); let finalText = '';
  recog.onresult = e => { let t = ''; for (const r of e.results) t += r[0].transcript; finalText = t; input.value = t; };
  recog.onerror = e => { listening = false; setMicState(); if (e.error === 'not-allowed') alert('Please allow microphone access to talk to the assistant.'); };
  recog.onend = () => { const was = listening; listening = false; setMicState(); if (was && finalText.trim()) sendChat(true); };
  listening = true; setMicState();
  try { recog.start(); } catch (e) { listening = false; setMicState(); }
}
function toggleVoice() {
  voiceOn = !voiceOn; localStorage.setItem('chatVoice', voiceOn ? '1' : '0');
  if (!voiceOn) stopSpeaking();
  const b = document.getElementById('chat-voice'); b.textContent = voiceOn ? '🔊' : '🔇'; b.title = voiceOn ? 'Replies are read aloud (tap to mute)' : 'Tap to hear replies aloud';
}
function toggleLang() {
  voiceLang = voiceLang === 'en-US' ? 'ur-PK' : 'en-US'; localStorage.setItem('chatLang', voiceLang);
  document.getElementById('chat-lang').textContent = voiceLang === 'en-US' ? 'EN' : 'اردو';
}

(function initVoiceUI() {
  const input = document.getElementById('chat-input'); if (!input) return;
  const row = input.parentElement;
  const st = document.createElement('style');
  st.textContent = '.chat-input-row{gap:.35rem!important}.chat-input-row input{min-width:0!important}.chat-input-row .chat-send{flex-shrink:0}.vbtn{width:32px;height:32px;flex-shrink:0;border-radius:50%;border:1.5px solid #e2e8f0;background:#fff;cursor:pointer;font-size:.95rem;display:flex;align-items:center;justify-content:center;padding:0}' +
    '.vbtn:hover{border-color:#2563eb}.vbtn.listening{background:#fee2e2;border-color:#ef4444;animation:vpulse 1s infinite}.vbtn.txt{font-size:.68rem;font-weight:700;color:#475569}' +
    '@keyframes vpulse{0%,100%{box-shadow:0 0 0 0 rgba(239,68,68,.4)}50%{box-shadow:0 0 0 6px rgba(239,68,68,0)}}';
  document.head.appendChild(st);
  const mk = (id, txt, title, fn, cls) => { const b = document.createElement('button'); b.type = 'button'; b.id = id; b.className = 'vbtn ' + (cls || '');
    b.textContent = txt; b.title = title; b.onclick = fn; return b; };
  const send = row.querySelector('.chat-send');
  const anchor = send || null;
  if (SpeechRec) {
    row.insertBefore(mk('chat-lang', voiceLang === 'en-US' ? 'EN' : 'اردو', 'Voice language', toggleLang, 'txt'), anchor);
    row.insertBefore(mk('chat-mic', '🎤', 'Speak your question', toggleMic), anchor);
  }
  if ('speechSynthesis' in window) {
    row.insertBefore(mk('chat-voice', voiceOn ? '🔊' : '🔇', voiceOn ? 'Replies are read aloud (tap to mute)' : 'Tap to hear replies aloud', toggleVoice), anchor);
    speechSynthesis.getVoices();                       // some browsers load voices lazily
  }
  // stop talking / listening when the chat window is closed or the page is left
  const w = document.getElementById('chatbot-widget');
  if (w) new MutationObserver(() => { const open = w.classList.contains('open') || (w.style.display && w.style.display !== 'none'); if (!open) { stopSpeaking(); stopListening(); } })
    .observe(w, { attributes: true, attributeFilter: ['class', 'style'] });
  window.addEventListener('beforeunload', stopSpeaking);
})();
