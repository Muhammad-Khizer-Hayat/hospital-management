/* MediCare+ shared UI helpers.
     UI.toast(message, 'success'|'error'|'warning'|'info', {title, duration})
     await UI.confirm(message, {title, confirmText, cancelText, type:'danger'|'warning'|'info'|'success', html:true})
     await UI.alert(message, {title, type})
     UI.busy(button, true|false)            // spinner on a button while it works
   The browser's own alert() is replaced by a toast, so old code keeps working but looks professional. */
(function () {
  const ICONS = {
    success: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>',
    error: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9.5"/><path d="M12 7.5v5.5M12 16.4v.1"/></svg>',
    warning: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0zM12 9.5v4.2M12 17.2v.1"/></svg>',
    info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9.5"/><path d="M12 11v5.5M12 7.6v.1"/></svg>'
  };
  const TITLES = { success: 'Done', error: 'Something went wrong', warning: 'Please check', info: 'Notice' };
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  function guess(m) {
    m = String(m || '');
    if (/could not|couldn'?t|can'?t|cannot|fail|error|invalid|not available|unable|wrong|denied|incorrect|not found|not allowed|no free/i.test(m)) return 'error';
    if (/success|saved|booked|completed|recorded|paid|done|updated|created|sent/i.test(m)) return 'success';
    return 'info';
  }
  function box() {
    let b = document.getElementById('ui-toasts');
    if (!b) { b = document.createElement('div'); b.id = 'ui-toasts'; b.setAttribute('aria-live', 'polite'); document.body.appendChild(b); }
    return b;
  }
  function toast(message, type, opts) {
    opts = opts || {}; type = ICONS[type] ? type : guess(message);
    const ms = opts.duration || (type === 'error' ? 7000 : 4500);
    const el = document.createElement('div'); el.className = 'ui-toast ui-' + type; el.setAttribute('role', type === 'error' ? 'alert' : 'status');
    el.innerHTML = `<div class="ui-ic">${ICONS[type]}</div><div class="ui-tx"><div class="ui-tt">${esc(opts.title || TITLES[type])}</div><div class="ui-mm">${esc(message)}</div></div><button class="ui-x" aria-label="Close">×</button><div class="ui-bar" style="animation-duration:${ms}ms"></div>`;
    const close = () => { if (!el.parentNode) return; el.classList.add('out'); setTimeout(() => el.remove(), 260); };
    el.querySelector('.ui-x').onclick = close;
    let t = setTimeout(close, ms);
    el.onmouseenter = () => { clearTimeout(t); el.querySelector('.ui-bar').style.display = 'none'; };
    el.onmouseleave = () => { t = setTimeout(close, 2200); };
    const b = box(); b.appendChild(el); while (b.children.length > 4) b.firstChild.remove();
    return close;
  }
  function dialog(message, opts, withCancel) {
    opts = opts || {};
    const type = ICONS[opts.type] ? opts.type : (opts.type === 'danger' ? 'error' : (withCancel ? 'warning' : guess(message)));
    const kind = opts.type === 'danger' ? 'error' : type;
    return new Promise(resolve => {
      const back = document.createElement('div'); back.className = 'ui-back';
      const body = opts.html ? message : esc(message).replace(/\n/g, '<br>');
      back.innerHTML = `<div class="ui-dialog ui-${kind}" role="dialog" aria-modal="true"><div class="ui-big">${ICONS[kind]}</div>
        <h3>${esc(opts.title || (withCancel ? 'Are you sure?' : TITLES[kind]))}</h3><div class="ui-body">${body}</div>
        <div class="ui-btns">${withCancel ? `<button type="button" class="ui-no">${esc(opts.cancelText || 'Cancel')}</button>` : ''}<button type="button" class="ui-ok">${esc(opts.confirmText || (withCancel ? 'Yes, continue' : 'OK'))}</button></div></div>`;
      const done = v => { document.removeEventListener('keydown', key, true); back.remove(); resolve(v); };
      const key = e => { if (e.key === 'Escape') { e.preventDefault(); done(false); } if (e.key === 'Enter' && document.activeElement === document.body) { e.preventDefault(); done(true); } };
      back.querySelector('.ui-ok').onclick = () => done(true);
      const no = back.querySelector('.ui-no'); if (no) no.onclick = () => done(false);
      back.addEventListener('mousedown', e => { if (e.target === back) done(false); });
      document.addEventListener('keydown', key, true);
      document.body.appendChild(back); back.querySelector('.ui-ok').focus();
    });
  }
  function busy(btn, on) {
    if (!btn) return;
    btn.disabled = !!on; btn.classList.toggle('ui-loading', !!on);
  }

  /* ───────── form helpers (all pages) ─────────
     UI.fieldError(inputOrId, 'message')  → red border + message under the field, focuses it
     UI.clearErrors(rootOrId)             → removes all inline errors in a form/modal
     Automatic: phone fields accept only digits + - ( ) space; text is trimmed on blur;
                numbers are kept inside min/max; textareas with maxlength get a live counter;
                an error disappears as soon as the user edits the field. */
  function $el(x) { return typeof x === 'string' ? document.getElementById(x) : x; }
  function fieldError(target, msg, noFocus) {
    const el = $el(target); if (!el) return;
    const holder = el.closest('.form-row, .f, .field') || el.parentNode;
    el.classList.add('ui-invalid'); el.setAttribute('aria-invalid', 'true');
    let m = holder.querySelector(':scope > .ui-ferr');
    if (!m) { m = document.createElement('div'); m.className = 'ui-ferr'; m.setAttribute('role', 'alert'); holder.appendChild(m); }
    m.textContent = msg;
    if (!noFocus) { try { el.focus({ preventScroll: true }); } catch (e) {} el.scrollIntoView({ block: 'center', behavior: 'smooth' }); }
  }
  function clearField(el) {
    el = $el(el); if (!el) return; el.classList.remove('ui-invalid'); el.removeAttribute('aria-invalid');
    const holder = el.closest('.form-row, .f, .field') || el.parentNode; const m = holder && holder.querySelector(':scope > .ui-ferr'); if (m) m.remove();
  }
  function clearErrors(root) {
    root = $el(root) || document;
    root.querySelectorAll('.ui-invalid').forEach(clearField);
    root.querySelectorAll('.ui-ferr').forEach(n => n.remove());
  }
  document.addEventListener('input', e => {
    const t = e.target; if (!(t instanceof HTMLElement)) return;
    if (t.classList.contains('ui-invalid')) clearField(t);
    if (t.matches('input[type=tel]')) { const c = t.value.replace(/[^\d+\-() ]/g, ''); if (c !== t.value) t.value = c; }
    if (t.matches('textarea[maxlength]')) {
      let c = t.parentNode.querySelector(':scope > .ui-count');
      if (!c) { c = document.createElement('div'); c.className = 'ui-count'; t.after(c); }
      c.textContent = t.value.length + ' / ' + t.maxLength;
    }
  }, true);
  document.addEventListener('focusout', e => {
    const t = e.target; if (!(t instanceof HTMLInputElement || t instanceof HTMLTextAreaElement)) return;
    if (['text', 'email', 'tel', 'search', 'textarea'].includes(t.type) && t.value !== t.value.trim()) t.value = t.value.trim();
    if (t.type === 'number' && t.value !== '') {
      const v = +t.value, lo = t.min !== '' ? +t.min : null, hi = t.max !== '' ? +t.max : null;
      if (lo !== null && v < lo) t.value = lo; if (hi !== null && v > hi) t.value = hi;
    }
  }, true);
  window.UI = { toast, busy, esc, fieldError, clearErrors, clearField, confirm: (m, o) => dialog(m, o, true), alert: (m, o) => dialog(m, o, false) };
  window.alert = m => { toast(String(m ?? '')); };      // old alert() calls now show a professional toast
})();
