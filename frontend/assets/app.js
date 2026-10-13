/* Smart Retail Checkout - single-page front end (no build step, no external dependencies).
   All prices/totals shown come from the API; nothing here is authoritative. */
(function () {
  'use strict';

  /* ---------- helpers ---------- */
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const fmt = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' });
  const money = (n) => fmt.format(Number(n || 0));
  const num = (n) => Number(n || 0);
  const uuid = () => Array.from(crypto.getRandomValues(new Uint8Array(16)), (b) => b.toString(16).padStart(2, '0')).join('');
  const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };

  const ICONS = {
    home: '<path d="M3 11l9-8 9 8"/><path d="M5 10v10h14V10"/>',
    scan: '<path d="M4 8V6a2 2 0 012-2h2M16 4h2a2 2 0 012 2v2M20 16v2a2 2 0 01-2 2h-2M8 20H6a2 2 0 01-2-2v-2"/><path d="M4 12h16"/>',
    receipt: '<path d="M6 3h12v18l-3-2-3 2-3-2-3 2z"/><path d="M9 8h6M9 12h6"/>',
    box: '<path d="M21 8l-9-5-9 5 9 5z"/><path d="M3 8v8l9 5 9-5V8M12 13v8"/>',
    cart: '<circle cx="9" cy="20" r="1.5"/><circle cx="18" cy="20" r="1.5"/><path d="M3 4h2l2.4 10.5a1 1 0 001 .8h8.9a1 1 0 001-.8L20 8H6.2"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>',
    plus: '<path d="M12 5v14M5 12h14"/>', trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
    edit: '<path d="M4 20h4L19 9l-4-4L4 16z"/>', x: '<path d="M6 6l12 12M18 6L6 18"/>',
    check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>', alert: '<path d="M12 4l9 16H3z"/><path d="M12 10v4M12 17.5v.01"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8v.01"/>',
    camera: '<path d="M4 8h3l1.5-2h7L17 8h3a1 1 0 011 1v9a1 1 0 01-1 1H4a1 1 0 01-1-1V9a1 1 0 011-1z"/><circle cx="12" cy="13" r="3.5"/>',
    upload: '<path d="M12 16V4M7 9l5-5 5 5M4 20h16"/>', download: '<path d="M12 4v12M7 11l5 5 5-5M4 20h16"/>',
    print: '<path d="M7 9V3h10v6M7 17H4v-7h16v7h-3M7 14h10v7H7z"/>', logout: '<path d="M9 4H5a1 1 0 00-1 1v14a1 1 0 001 1h4M16 8l4 4-4 4M20 12H9"/>',
    eye: '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    eyeoff: '<path d="M3 3l18 18M10.6 6.2A10 10 0 0112 6c6 0 10 6 10 6a17 17 0 01-3.2 3.7M6.5 6.9C3.8 8.6 2 12 2 12s4 7 10 7a9.700 9.700 0 004-.9"/>',
    refresh: '<path d="M20 11a8 8 0 10-2.3 5.7M20 4v7h-7"/>', shield: '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.500-1-8-4-8-9V6z"/><path d="M9 12l2 2 4-4"/>',
    zap: '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>', tag: '<path d="M3 12V4h8l10 10-8 8z"/><circle cx="7.500" cy="8.500" r="1.200"/>',
  };
  const icon = (n, cls = '') => `<svg class="icon ${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[n] || ''}</svg>`;

  /* ---------- state ---------- */
  const store = {
    get(k, d) { try { const v = sessionStorage.getItem(k); return v ? JSON.parse(v) : d; } catch { return d; } },
    set(k, v) { try { sessionStorage.setItem(k, JSON.stringify(v)); } catch { /* storage unavailable */ } },
    del(k) { try { sessionStorage.removeItem(k); } catch { /* ignore */ } },
  };
  const state = {
    token: store.get('token', null), user: store.get('user', null),
    cart: store.get('cart', []), idemKey: store.get('idem', null) || uuid(),
    scan: null, classes: null,
  };
  let cleanup = null;

  function saveCart() {
    store.set('cart', state.cart); store.set('idem', state.idemKey);
    const n = state.cart.reduce((a, l) => a + l.quantity, 0);
    $$('.cart-badge').forEach((b) => { b.textContent = n; b.style.display = n ? '' : 'none'; });
  }
  function mutateCart(fn) { fn(); state.idemKey = uuid(); saveCart(); }   // new key whenever cart content changes
  function clearCart() { state.cart = []; state.idemKey = uuid(); saveCart(); }
  function cartCount() { return state.cart.reduce((a, l) => a + l.quantity, 0); }
  function addToCart(product, qty, meta = {}) {
    mutateCart(() => {
      const ex = state.cart.find((l) => l.product.id === product.id);
      if (ex) { ex.quantity = Math.min(999, ex.quantity + qty); if (meta.source === 'ai' && ex.source !== 'ai') Object.assign(ex, meta); }
      else state.cart.push({ product, quantity: Math.min(999, qty), source: meta.source || 'manual', ai_class: meta.ai_class || null, ai_confidence: meta.ai_confidence ?? null });
    });
  }
  const cartPayload = () => state.cart.map((l) => ({ product_id: l.product.id, quantity: l.quantity, source: l.source, ai_class: l.source === 'ai' ? l.ai_class : null, ai_confidence: l.source === 'ai' ? l.ai_confidence : null }));

  /* ---------- API ---------- */
  class ApiError extends Error { constructor(msg, status) { super(msg); this.status = status; } }
  function detailText(d) {
    if (!d) return 'Something went wrong. Please try again.';
    if (typeof d === 'string') return d;
    if (Array.isArray(d)) return d.map((e) => { const f = (e.loc || []).slice(1).join('.'); return (f ? f + ': ' : '') + String(e.msg || '').replace(/^Value error, /, ''); }).join(' · ');
    return 'Something went wrong. Please try again.';
  }
  async function api(path, { method = 'GET', json, form, blob } = {}) {
    const headers = {};
    if (state.token) headers.Authorization = 'Bearer ' + state.token;
    let body;
    if (json !== undefined) { headers['Content-Type'] = 'application/json'; body = JSON.stringify(json); } else if (form) body = form;
    let res;
    try { res = await fetch(path, { method, headers, body }); }
    catch { throw new ApiError('Cannot reach the server. Check that the backend is running and try again.', 0); }
    if (res.status === 401 && !path.endsWith('/auth/login')) { logout(true); throw new ApiError('Your session has ended. Please sign in again.', 401); }
    if (!res.ok) {
      let d = null; try { d = (await res.json()).detail; } catch { /* non-JSON error */ }
      throw new ApiError(detailText(d), res.status);
    }
    if (res.status === 204) return null;
    return blob ? res.blob() : res.json();
  }

  /* ---------- UI primitives ---------- */
  function toast(msg, kind = '') {
    const el = document.createElement('div');
    el.className = 'toast ' + kind; el.setAttribute('role', 'status');
    el.innerHTML = `${icon(kind === 'bad' ? 'alert' : 'check')}<div>${esc(msg)}</div>`;
    $('#toasts').appendChild(el);
    setTimeout(() => el.remove(), kind === 'bad' ? 7000 : 3800);
  }
  function modal({ title, body, footer = '', size = '' }) {
    const ov = document.createElement('div');
    ov.className = 'overlay';
    ov.innerHTML = `<div class="modal ${size}" role="dialog" aria-modal="true" aria-label="${esc(title)}">
      <div class="modal-head"><h2>${esc(title)}</h2><button class="btn ghost sm" data-close aria-label="Close">${icon('x')}</button></div>
      <div class="modal-body">${body}</div>${footer ? `<div class="modal-foot">${footer}</div>` : ''}</div>`;
    const prevFocus = document.activeElement;
    const close = () => { ov.remove(); document.removeEventListener('keydown', onKey); prevFocus && prevFocus.focus && prevFocus.focus(); };
    const onKey = (e) => { if (e.key === 'Escape') close(); };
    document.addEventListener('keydown', onKey);
    ov.addEventListener('mousedown', (e) => { if (e.target === ov) close(); });
    $$('[data-close]', ov).forEach((b) => b.addEventListener('click', close));
    document.body.appendChild(ov);
    const first = $('input,select,button.primary', ov); first && first.focus();
    return { el: ov, close };
  }
  function confirmDialog({ title, message, confirmText = 'Confirm', danger = false }) {
    return new Promise((resolve) => {
      const m = modal({ title, size: 'sm', body: `<p style="margin:0">${esc(message)}</p>`,
        footer: `<button class="btn" data-close>Cancel</button><button class="btn ${danger ? 'danger solid' : 'primary'}" id="ok">${esc(confirmText)}</button>` });
      let done = false;
      $('#ok', m.el).addEventListener('click', () => { done = true; m.close(); resolve(true); });
      new MutationObserver(() => { if (!document.body.contains(m.el) && !done) { done = true; resolve(false); } }).observe(document.body, { childList: true });
    });
  }
  const btnBusy = (btn, on, label) => { if (!btn) return; btn.classList.toggle('loading', on); if (on) { btn.dataset.l = btn.innerHTML; btn.innerHTML = `<span class="spinner"></span>${esc(label || 'Working…')}`; } else if (btn.dataset.l) { btn.innerHTML = btn.dataset.l; } };
  const emptyState = (ic, title, text, action = '') => `<div class="empty"><div class="art">${icon(ic)}</div><h3>${esc(title)}</h3><p style="margin:0">${text}</p>${action}</div>`;
  const loading = (t = 'Loading…') => `<div class="center-load"><span class="spinner"></span><span>${esc(t)}</span></div>`;
  const errorBox = (msg, retry = true) => `<div class="alert bad">${icon('alert')}<div><b>Couldn’t load this.</b> ${esc(msg)}${retry ? ' <a href="#" data-retry>Try again</a>' : ''}</div></div>`;
  const prodThumb = (p, cls = '') => p && p.image_url ? `<img class="thumb ${cls}" src="${esc(p.image_url)}" alt="" loading="lazy">` : `<div class="thumb ${cls}">${icon('box')}</div>`;
  const pack = (p) => [p.pack_size, p.unit].filter(Boolean).join(' ');
  const statusBadge = (active) => active ? '<span class="badge ok">Active</span>' : '<span class="badge gray">Inactive</span>';

  /* ---------- auth ---------- */
  // Set the hash and let `hashchange` render; render directly only if the hash is unchanged.
  function navigate(h) { if (location.hash === h) route(); else location.hash = h; }
  function logout(expired = false) {
    state.token = null; state.user = null; store.del('token'); store.del('user');
    if (expired) sessionStorage.setItem('flash', 'Your session ended. Please sign in again.');
    navigate('#/login');
  }

  function pageLogin() {
    const flash = sessionStorage.getItem('flash'); sessionStorage.removeItem('flash');
    $('#app').innerHTML = `<div class="login">
      <section class="login-hero"><div class="brand"><span class="brand-mark">${icon('cart')}</span>Smart Retail Checkout</div>
        <div><h1>Faster, more accurate billing.</h1><p style="margin-top:14px">Scan a counter full of products, confirm what the AI finds, and print the invoice.</p></div>
        <ul><li>${icon('scan')} Camera or photo upload</li><li>${icon('shield')} Low-confidence items always reviewed by you</li><li>${icon('receipt')} Itemised invoices with PDF download</li></ul></section>
      <section class="login-form"><form class="login-card" id="lf" novalidate>
        <div><h1 style="font-size:1.6rem">Welcome back</h1><p class="muted" style="margin:6px 0 0">Sign in to start billing.</p></div>
        ${flash ? `<div class="alert info">${icon('info')}<div>${esc(flash)}</div></div>` : ''}
        <div id="lerr"></div>
        <div class="field"><label for="u">Username <span class="req">*</span></label><input class="input" id="u" autocomplete="username" autocapitalize="none" required><div class="err" id="ue"></div></div>
        <div class="field"><label for="p">Password <span class="req">*</span></label><div class="input-wrap"><input class="input" id="p" type="password" autocomplete="current-password" required><button type="button" class="btn ghost sm toggle" id="tg" aria-label="Show password">${icon('eye')}</button></div><div class="err" id="pe"></div></div>
        <button class="btn primary lg" id="go" type="submit">Sign in</button>
        <p class="hint" style="margin:0">Accounts are created by an administrator (see README).</p></form></section></div>`;
    $('#tg').addEventListener('click', () => { const p = $('#p'); const show = p.type === 'password'; p.type = show ? 'text' : 'password'; $('#tg').innerHTML = icon(show ? 'eyeoff' : 'eye'); $('#tg').setAttribute('aria-label', show ? 'Hide password' : 'Show password'); });
    $('#lf').addEventListener('submit', async (e) => {
      e.preventDefault();
      const u = $('#u').value.trim(), p = $('#p').value;
      $('#ue').textContent = u ? '' : 'Enter your username.'; $('#pe').textContent = p ? '' : 'Enter your password.';
      if (!u || !p) return;
      btnBusy($('#go'), true, 'Signing in…'); $('#lerr').innerHTML = '';
      try {
        const r = await api('/api/auth/login', { method: 'POST', json: { username: u, password: p } });
        state.token = r.access_token; state.user = r.user; store.set('token', r.access_token); store.set('user', r.user);
        navigate('#/dashboard');
      } catch (err) {
        $('#lerr').innerHTML = `<div class="alert bad" role="alert">${icon('alert')}<div>${esc(err.message)}</div></div>`;
        btnBusy($('#go'), false);
      }
    });
    $('#u').focus();
  }

  /* ---------- shell ---------- */
  const NAV = [
    ['#/dashboard', 'home', 'Dashboard'], ['#/scan', 'scan', 'New bill'], ['#/bills', 'receipt', 'Bills'], ['#/products', 'box', 'Products', 'admin'],
  ];
  function shell(active, inner) {
    const items = NAV.filter((n) => !n[3] || state.user.role === 'admin');
    const link = (n, cls) => `<a class="${cls} ${active === n[0] ? 'active' : ''}" href="${n[0]}" ${active === n[0] ? 'aria-current="page"' : ''}>${icon(n[1])}<span>${n[2]}${n[0] === '#/scan' ? ` <span class="badge info cart-badge" style="${cartCount() ? '' : 'display:none'}">${cartCount()}</span>` : ''}</span></a>`;
    $('#app').innerHTML = `<div class="shell"><aside class="nav"><div class="brand"><span class="brand-mark">${icon('cart')}</span>Smart Retail<br>Checkout</div>
      ${items.map((n) => link(n, 'item')).join('')}<div class="spacer"></div>
      <div class="userbox"><div class="avatar">${esc((state.user.full_name || state.user.username)[0].toUpperCase())}</div><div style="min-width:0"><b style="display:block;overflow:hidden;text-overflow:ellipsis">${esc(state.user.full_name || state.user.username)}</b><span class="muted small">${esc(state.user.role)}</span></div><button class="btn ghost sm" id="lo" title="Sign out" aria-label="Sign out">${icon('logout')}</button></div></aside>
      <main class="main" id="view"><div class="mobile-top"><div class="brand" style="padding:0"><span class="brand-mark">${icon('cart')}</span>Smart Retail Checkout</div><button class="btn ghost sm" id="lo2" aria-label="Sign out">${icon('logout')}</button></div>${inner}</main></div>
      <nav class="bottom-nav" aria-label="Main">${items.map((n) => link(n, '')).join('')}</nav>`;
    $('#lo').addEventListener('click', () => logout()); $('#lo2').addEventListener('click', () => logout());
    return $('#view');
  }

  /* ---------- dashboard ---------- */
  async function pageDashboard() {
    const v = shell('#/dashboard', `<div class="page-head"><div><h1>Dashboard</h1><p>Live overview of your shop.</p></div><div class="row"><a class="btn primary lg" href="#/scan">${icon('scan')} Start scanning</a></div></div><div id="dash">${loading()}</div>`);
    const target = $('#dash', v);
    try {
      const d = await api('/api/dashboard');
      const admin = state.user.role === 'admin';
      target.innerHTML = `<div class="grid g-stats">
        <div class="card stat"><div class="label">${icon('box')} Products (active / total)</div><div class="value">${d.products_active} <span class="muted" style="font-size:1rem">/ ${d.products_total}</span></div></div>
        <div class="card stat"><div class="label">${icon('receipt')} Bills generated</div><div class="value">${d.bills_total}</div></div>
        <div class="card stat"><div class="label">${icon('tag')} Total billed</div><div class="value">${money(d.billed_amount_total)}</div></div></div>
        <div class="grid g-2" style="margin-top:16px">
        <div class="card flush"><div class="card-head" style="padding:18px 20px 0"><h2>Recent bills</h2><a href="#/bills">View all</a></div>${d.recent_bills.length ? `<div class="table-wrap"><table><thead><tr><th>Bill</th><th>Date</th><th class="right">Total</th></tr></thead><tbody>${d.recent_bills.map((b) => `<tr><td><a href="#/bill/${b.id}"><b>${esc(b.bill_number)}</b></a></td><td class="muted">${esc(b.created_display)}</td><td class="right">${money(b.total)}</td></tr>`).join('')}</tbody></table></div>` : emptyState('receipt', 'No bills yet', 'Your finished bills will appear here.', `<a class="btn primary" href="#/scan">Create the first bill</a>`)}</div>
        <div class="card flush"><div class="card-head" style="padding:18px 20px 0"><h2>Recently added products</h2>${admin ? '<a href="#/products">Manage</a>' : ''}</div>${d.recent_products.length ? `<div style="padding:6px 8px 12px">${d.recent_products.map((p) => `<div class="cell-prod" style="padding:8px 12px">${prodThumb(p)}<div><b>${esc(p.name)}</b><span class="muted small">${esc(p.sku)} · ${money(p.selling_price)}</span></div></div>`).join('')}</div>` : emptyState('box', 'No products yet', admin ? 'Add your first product to start billing.' : 'Ask an administrator to add products.', admin ? `<a class="btn primary" href="#/products">Add a product</a>` : '')}</div></div>`;
    } catch (e) { target.innerHTML = errorBox(e.message); const r = $('[data-retry]', target); r && r.addEventListener('click', (ev) => { ev.preventDefault(); pageDashboard(); }); }
  }

  /* ---------- product picker ---------- */
  function pickProduct(onPick, { title = 'Choose a product', candidates = null } = {}) {
    const m = modal({ title, body: `<div class="search"><span>${icon('search')}</span><input class="input" id="pq" placeholder="Search by name, SKU, brand or barcode" aria-label="Search products" autocomplete="off"></div><div id="pl" class="pick-list"></div>` });
    const list = $('#pl', m.el);
    const row = (p) => `<button class="pick" data-id="${p.id}">${prodThumb(p)}<div style="flex:1;min-width:0"><b>${esc(p.name)}</b><div class="muted small">${esc(p.sku)}${pack(p) ? ' · ' + esc(pack(p)) : ''}${p.variant ? ' · ' + esc(p.variant) : ''}</div></div><b>${money(p.selling_price)}</b></button>`;
    let found = [];
    const draw = (items, head = '') => { found = items; list.innerHTML = head + (items.length ? items.map(row).join('') : `<div class="empty" style="padding:24px">No matching active products.</div>`); $$('.pick', list).forEach((b) => b.addEventListener('click', () => { const p = found.find((x) => String(x.id) === b.dataset.id); m.close(); onPick(p); })); };
    const search = async (q) => { try { const r = await api('/api/products?active=true&page_size=30&q=' + encodeURIComponent(q)); draw(r.items); } catch (e) { list.innerHTML = errorBox(e.message, false); } };
    if (candidates && candidates.length) draw(candidates, `<div class="hint">Suggested by the recognition model:</div>`); else search('');
    $('#pq', m.el).addEventListener('input', debounce((e) => search(e.target.value.trim()), 250));
  }

  /* ---------- scan (camera / upload) ---------- */
  async function pageScan() {
    const v = shell('#/scan', `<div class="page-head"><div><h1>New bill</h1><p>Scan products with the camera, upload a photo, or add items by hand.</p></div><div class="row">${cartCount() ? `<a class="btn" href="#/cart">${icon('cart')} Review bill (${cartCount()})</a>` : ''}<button class="btn" id="manual">${icon('plus')} Add item manually</button></div></div><div id="scanbox"></div>`);
    let mode = 'idle', stream = null, blob = null, url = null, error = null, busy = false, aiStatus = null;
    const box = $('#scanbox', v);
    const stop = () => { if (stream) { stream.getTracks().forEach((t) => t.stop()); stream = null; } };
    cleanup = () => { stop(); if (url && !(state.scan && state.scan.imageUrl === url)) URL.revokeObjectURL(url); };
    $('#manual').addEventListener('click', () => pickProduct((p) => { addToCart(p, 1, { source: 'manual' }); toast(`${p.name} added`, 'ok'); location.hash = '#/cart'; }));
    api('/api/scan/status').then((s) => { aiStatus = s; draw(); }).catch(() => {});

    async function openCamera() {
      error = null;
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) { error = { t: 'Camera is not available here', m: 'Browsers only allow camera access on https:// pages or on localhost. Open the app at http://localhost:8000, or use “Upload / take photo” instead.' }; return draw(); }
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' }, width: { ideal: 1920 }, height: { ideal: 1080 } }, audio: false });
        mode = 'live'; draw();
      } catch (e) {
        const map = { NotAllowedError: ['Camera permission was blocked', 'Allow camera access in your browser’s address bar, then press “Open camera” again. You can still upload a photo.'],
          NotFoundError: ['No camera found', 'Connect a camera, or upload a photo instead.'], NotReadableError: ['Camera is in use', 'Close other apps using the camera, then try again.'],
          OverconstrainedError: ['Camera could not start', 'Try again or upload a photo.'] };
        const [t, m] = map[e.name] || ['Camera could not start', 'Try again or upload a photo instead.'];
        error = { t, m }; mode = 'idle'; draw();
      }
    }
    function setBlob(b) { if (url) URL.revokeObjectURL(url); blob = b; url = URL.createObjectURL(b); mode = 'preview'; error = null; stop(); draw(); }
    function capture() {
      const vid = $('video', box); if (!vid || !vid.videoWidth) { toast('Camera is still starting. Try again in a moment.', 'bad'); return; }
      const c = document.createElement('canvas'); c.width = vid.videoWidth; c.height = vid.videoHeight; c.getContext('2d').drawImage(vid, 0, 0);
      c.toBlob((b) => b ? setBlob(b) : toast('Capture failed. Please try again.', 'bad'), 'image/jpeg', 0.92);
    }
    async function analyse() {
      if (busy) return; busy = true; mode = 'processing'; draw();
      const fd = new FormData(); fd.append('file', blob, 'capture.jpg');
      try {
        const r = await api('/api/scan', { method: 'POST', form: fd });
        state.scan = { result: r, imageUrl: url };
        location.hash = '#/review';
      } catch (e) { busy = false; mode = 'preview'; error = { t: 'Analysis failed', m: e.message }; draw(); }
    }
    function draw() {
      const ai = aiStatus && !aiStatus.available ? `<div class="alert warn" style="margin-bottom:16px">${icon('alert')}<div><b>AI recognition is not available.</b> ${esc(aiStatus.reason || '')} You can still bill by adding items manually; nothing will be auto-detected.</div></div>` : '';
      const err = error ? `<div class="alert bad" role="alert" style="margin-bottom:16px">${icon('alert')}<div><b>${esc(error.t)}.</b> ${esc(error.m)}</div></div>` : '';
      let stage = '', controls = '';
      if (mode === 'idle') {
        stage = `<div class="scan-msg">${icon('camera')}<h3 style="color:#fff;margin:10px 0 6px">Ready to scan</h3><p style="margin:0">Place the products in view, then open the camera or upload a photo.</p></div>`;
        controls = `<button class="btn primary lg" id="oc">${icon('camera')} Open camera</button><label class="btn lg" for="fu" style="cursor:pointer">${icon('upload')} Upload / take photo</label>`;
      } else if (mode === 'live') {
        stage = `<video autoplay playsinline muted></video><div class="scan-guide"></div>`;
        controls = `<button class="btn" id="cx">Cancel</button><button class="shutter" id="cap" aria-label="Capture photo"></button>`;
      } else if (mode === 'preview') {
        stage = `<img src="${url}" alt="Captured products">`;
        controls = `<button class="btn" id="rt">${icon('refresh')} Retake</button><button class="btn" id="cx">Cancel</button><button class="btn primary lg" id="go">${icon('zap')} Continue</button>`;
      } else {
        stage = `<img src="${url}" alt="" style="opacity:.45">`;
        controls = '';
      }
      box.innerHTML = `${ai}${err}<div class="split"><div><div class="scan-stage">${stage}</div><div class="row" style="justify-content:center;margin-top:16px">${controls}</div></div>
        <div class="card"><h2 style="margin-bottom:12px">What happens next</h2>${mode === 'processing' ? `<ul class="steps"><li class="done"><span class="dot">${icon('check')}</span>Image uploaded</li><li class="active"><span class="dot"><span class="spinner" style="width:14px;height:14px;border-width:2px"></span></span>Analysing on the server: detecting products, classifying each one and checking confidence</li></ul><p class="hint" style="margin-top:14px">The server runs these steps in a single request, so no finer progress is available.</p>`
          : `<ul class="steps"><li><span class="dot">1</span>Capture or upload a photo</li><li><span class="dot">2</span>The server detects products and classifies them</li><li><span class="dot">3</span>You confirm anything uncertain and pick the exact SKU</li><li><span class="dot">4</span>Review the bill and generate the invoice</li></ul>`}</div></div>
        <input type="file" id="fu" accept="image/jpeg,image/png,image/webp" capture="environment" class="sr">`;
      const on = (id, fn) => { const el = $(id, box); el && el.addEventListener('click', fn); };
      on('#oc', openCamera); on('#cap', capture); on('#go', analyse);
      on('#rt', () => { mode = 'idle'; blob = null; openCamera(); });
      on('#cx', () => { stop(); mode = 'idle'; blob = null; draw(); });
      const fu = $('#fu', box); fu && fu.addEventListener('change', () => { const f = fu.files[0]; if (!f) return; if (f.size > 8 * 1024 * 1024) { error = { t: 'Image is too large', m: 'Choose an image under 8 MB.' }; draw(); return; } setBlob(f); });
      const vid = $('video', box); if (vid && stream) vid.srcObject = stream;
    }
    draw();
  }

  /* ---------- review recognition results ---------- */
  function pageReview() {
    if (!state.scan) { location.hash = '#/scan'; return; }
    const { result, imageUrl } = state.scan;
    const rows = result.detections.map((d) => {
      const one = d.candidates.length === 1 ? d.candidates[0] : null;
      return { d, product: one, confirmed: !d.needs_review && !!one };
    });
    const v = shell('#/scan', `<div class="page-head"><div><h1>Review products</h1><p>Confirm what was recognised before it goes on the bill.</p></div><div class="row"><a class="btn" href="#/scan">${icon('refresh')} Scan again</a><button class="btn" id="manual">${icon('plus')} Add item manually</button></div></div><div id="rv"></div>`);
    $('#manual', v).addEventListener('click', () => pickProduct((p) => { addToCart(p, 1, { source: 'manual' }); draw(); }));
    const box = $('#rv', v);
    function draw() {
      const nConfirmed = rows.filter((r) => r.confirmed && r.product).length;
      let head = `<div class="alert info" style="margin-bottom:16px">${icon('info')}<div>Recognition identifies product <b>classes</b>. Where several SKUs (pack sizes/variants) exist, you choose the exact one. Nothing is added to the bill until you confirm it.</div></div>`;
      if (!result.ai_available) head = `<div class="alert warn" style="margin-bottom:16px">${icon('alert')}<div><b>AI recognition is unavailable, so nothing was detected.</b> ${esc(result.reason || '')} Add the items manually instead.</div></div>`;
      else if (!rows.length) head = `<div class="alert warn" style="margin-bottom:16px">${icon('alert')}<div><b>No products were detected in this image.</b> Try a closer, better-lit photo, or add items manually.</div></div>`;
      const cards = rows.map((r, i) => {
        const d = r.d, pct = Math.round(d.confidence * 100), low = d.confidence < (result.confidence_threshold || 0.8);
        const cls = r.confirmed ? 'confirmed' : (d.needs_review ? 'review' : '');
        const prod = r.product;
        return `<div class="det ${cls}"><img src="${esc(d.thumbnail)}" alt="Detected item ${i + 1}">
          <div style="min-width:0"><div class="row" style="justify-content:space-between;gap:6px"><b>${esc(d.ai_class.replace(/_/g, ' '))}</b>${r.confirmed ? `<span class="badge ok">${icon('check')}Confirmed</span>` : `<span class="badge warn">Needs review</span>`}</div>
          <div class="meter ${low ? 'low' : ''}" title="Model confidence"><i style="width:${pct}%"></i></div>
          <div class="muted small">Model confidence ${pct}%${low ? ' (below threshold)' : ''} · detector ${Math.round(d.detector_confidence * 100)}%</div>
          ${d.match === 'ambiguous' ? `<div class="small" style="color:var(--warn);margin-top:4px">${d.candidates.length} SKUs share this class — pick the exact one.</div>` : ''}${d.match === 'none' ? `<div class="small" style="color:var(--warn);margin-top:4px">No active catalog product is mapped to this class.</div>` : ''}
          <div style="margin-top:10px">${prod ? `<div class="small"><b>${esc(prod.name)}</b><br><span class="muted">${esc(prod.sku)}${pack(prod) ? ' · ' + esc(pack(prod)) : ''} · ${money(prod.selling_price)}</span></div>` : '<span class="muted small">No product selected</span>'}</div>
          <div class="row" style="margin-top:10px;gap:8px"><button class="btn sm" data-pick="${i}">${prod ? 'Change' : 'Select product'}</button>${prod && !r.confirmed ? `<button class="btn sm primary" data-ok="${i}">Confirm</button>` : ''}${r.confirmed ? `<button class="btn sm ghost" data-un="${i}">Undo</button>` : ''}</div></div></div>`;
      }).join('');
      box.innerHTML = `${head}<div class="grid" style="grid-template-columns:minmax(0,1fr);gap:16px"><div class="row" style="align-items:flex-start;gap:16px">${imageUrl ? `<img src="${imageUrl}" alt="Scanned photo" style="width:140px;border-radius:12px;border:1px solid var(--line)">` : ''}<div><b>${rows.length} item${rows.length === 1 ? '' : 's'} detected</b><div class="muted small">${nConfirmed} confirmed</div></div></div>
        ${rows.length ? `<div class="det-grid">${cards}</div>` : ''}
        <div class="row" style="justify-content:flex-end"><button class="btn primary lg" id="addc" ${nConfirmed ? '' : 'disabled'}>${icon('cart')} Add ${nConfirmed} confirmed to bill</button>${cartCount() ? `<a class="btn lg" href="#/cart">Review bill (${cartCount()})</a>` : ''}</div></div>`;
      $$('[data-pick]', box).forEach((b) => b.addEventListener('click', () => { const r = rows[+b.dataset.pick]; pickProduct((p) => { r.product = p; r.confirmed = true; draw(); }, { title: 'Select the exact product', candidates: r.d.candidates }); }));
      $$('[data-ok]', box).forEach((b) => b.addEventListener('click', () => { rows[+b.dataset.ok].confirmed = true; draw(); }));
      $$('[data-un]', box).forEach((b) => b.addEventListener('click', () => { rows[+b.dataset.un].confirmed = false; draw(); }));
      const add = $('#addc', box);
      add && add.addEventListener('click', () => {
        const ok = rows.filter((r) => r.confirmed && r.product);
        ok.forEach((r) => addToCart(r.product, 1, { source: 'ai', ai_class: r.d.ai_class, ai_confidence: r.d.confidence }));
        state.scan = { result: { ...result, detections: [] }, imageUrl };
        location.hash = '#/cart';
      });
    }
    draw();
  }

  /* ---------- cart / bill review ---------- */
  function pageCart() {
    const v = shell('#/scan', `<div class="page-head"><div><h1>Review bill</h1><p>Prices and totals are calculated by the server.</p></div><div class="row"><a class="btn" href="#/scan">${icon('scan')} Scan more</a><button class="btn" id="manual">${icon('plus')} Add item</button></div></div><div id="cartbox"></div>`);
    const box = $('#cartbox', v);
    let preview = null, perr = null, pending = false, saving = false, seq = 0;
    $('#manual', v).addEventListener('click', () => pickProduct((p) => { addToCart(p, 1); refresh(); }));
    async function refresh() {
      if (!state.cart.length) { preview = null; perr = null; return draw(); }
      pending = true; const my = ++seq; draw();
      try { const p = await api('/api/bills/preview', { method: 'POST', json: { items: cartPayload() } }); if (my !== seq) return; preview = p; perr = null; }
      catch (e) { if (my !== seq) return; preview = null; perr = e.message; }
      pending = false; draw();
    }
    const line = (pid) => preview && preview.lines.find((l) => l.product_id === pid);
    function draw() {
      if (!state.cart.length) { box.innerHTML = `<div class="card">${emptyState('cart', 'Your bill is empty', 'Scan products or add them manually to begin.', `<a class="btn primary" href="#/scan">Start scanning</a>`)}</div>`; return; }
      const lines = state.cart.map((l) => {
        const pl = line(l.product.id), p = l.product;
        return `<div class="cart-line"><div class="cell-prod">${prodThumb(p)}<div style="min-width:0"><b>${esc(p.name)}</b><span class="muted small">${esc(p.sku)}${pack(p) ? ' · ' + esc(pack(p)) : ''}</span><div class="small">${l.source === 'ai' ? '<span class="badge info">AI-suggested, confirmed</span>' : '<span class="badge gray">Manual</span>'} <a href="#" data-chg="${p.id}">Change product</a></div></div></div>
          <div class="qty-cell"><div class="stepper"><button data-dec="${p.id}" aria-label="Decrease quantity">−</button><span aria-live="polite">${l.quantity}</span><button data-inc="${p.id}" aria-label="Increase quantity">+</button></div>${pl ? `<div class="muted small" style="margin-top:4px">${money(pl.effective_unit_price)} each${num(pl.festival_discount) > 0 ? ' (offer)' : ''}</div>` : ''}</div>
          <div class="line-total right"><b>${pl ? money(pl.line_total) : '<span class="skeleton" style="display:inline-block;width:70px"></span>'}</b></div>
          <div class="rm-cell"><button class="btn ghost sm" data-rm="${p.id}" aria-label="Remove ${esc(p.name)}">${icon('trash')}</button></div></div>`;
      }).join('');
      const t = preview;
      box.innerHTML = `${perr ? `<div class="alert bad" role="alert" style="margin-bottom:16px">${icon('alert')}<div><b>Couldn’t price this bill.</b> ${esc(perr)}</div></div>` : ''}<div class="split"><div class="card flush">${lines}</div>
        <div class="card sticky-side"><h2 style="margin-bottom:14px">Summary</h2>${t ? `<div class="totals" style="${pending ? 'opacity:.6' : ''}">
          <div class="line"><span class="muted">Items</span><span>${t.item_count}</span></div>
          <div class="line"><span class="muted">Subtotal</span><span>${money(t.subtotal)}</span></div>
          ${num(t.festival_discount) > 0 ? `<div class="line"><span>${esc(t.festival_name)} offer (${num(t.festival_percent)}%)</span><span class="minus">−${money(t.festival_discount)}</span></div>` : ''}
          ${t.combos.map((c) => `<div class="line"><span>${esc(c.name)} ×${c.sets} (${num(c.discount_percent)}%)</span><span class="minus">−${money(c.discount_amount)}</span></div>`).join('')}
          <div class="line grand"><span>Total</span><span>${money(t.total)}</span></div>
          ${num(t.mrp_total) > num(t.total) ? `<div class="small minus">You save ${money(num(t.mrp_total) - num(t.total))} vs MRP</div>` : ''}</div>`
          : (perr ? '<p class="muted">Fix the issue above to see totals.</p>' : '<div class="skeleton" style="height:120px"></div>')}
          <button class="btn primary lg" id="fin" style="width:100%;margin-top:18px" ${t && !saving && !pending ? '' : 'disabled'}>${icon('receipt')} Generate bill</button>
          <button class="btn danger" id="clr" style="width:100%;margin-top:10px">Clear bill</button>
          <p class="hint" style="margin:12px 0 0">Prices are fixed on the invoice when generated. Payment is not recorded by this app.</p></div></div>`;
      $$('[data-inc]', box).forEach((b) => b.addEventListener('click', () => { mutateCart(() => { const l = state.cart.find((x) => x.product.id === +b.dataset.inc); l.quantity = Math.min(999, l.quantity + 1); }); refresh(); }));
      $$('[data-dec]', box).forEach((b) => b.addEventListener('click', () => { mutateCart(() => { const l = state.cart.find((x) => x.product.id === +b.dataset.dec); l.quantity = Math.max(1, l.quantity - 1); }); refresh(); }));
      $$('[data-rm]', box).forEach((b) => b.addEventListener('click', () => { mutateCart(() => { state.cart = state.cart.filter((x) => x.product.id !== +b.dataset.rm); }); refresh(); }));
      $$('[data-chg]', box).forEach((a) => a.addEventListener('click', (e) => { e.preventDefault(); const old = +a.dataset.chg; pickProduct((p) => { mutateCart(() => { const l = state.cart.find((x) => x.product.id === old); const dup = state.cart.find((x) => x.product.id === p.id && x !== l); if (dup) { dup.quantity = Math.min(999, dup.quantity + l.quantity); state.cart = state.cart.filter((x) => x !== l); } else { l.product = p; l.source = 'manual'; l.ai_class = null; l.ai_confidence = null; } }); refresh(); }, { title: 'Select a different product' }); }));
      $('#clr', box).addEventListener('click', async () => { if (await confirmDialog({ title: 'Clear this bill?', message: 'All items will be removed from the current bill.', confirmText: 'Clear bill', danger: true })) { clearCart(); refresh(); } });
      $('#fin', box).addEventListener('click', async () => {
        if (saving) return; saving = true; btnBusy($('#fin', box), true, 'Generating…');
        try {
          const bill = await api('/api/bills', { method: 'POST', json: { idempotency_key: state.idemKey, items: cartPayload() } });
          clearCart(); state.scan = null; location.hash = '#/bill/' + bill.id;
        } catch (e) { saving = false; toast(e.message, 'bad'); perr = e.message; draw(); }
      });
    }
    refresh();
  }

  /* ---------- bill detail + pdf ---------- */
  async function fetchPdf(id) { return api(`/api/bills/${id}/invoice.pdf`, { blob: true }); }
  async function downloadPdf(id, number, btn) {
    btnBusy(btn, true, 'Preparing…');
    try { const b = await fetchPdf(id); const a = document.createElement('a'); a.href = URL.createObjectURL(b); a.download = number + '.pdf'; document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 5000); }
    catch (e) { toast(e.message, 'bad'); } finally { btnBusy(btn, false); }
  }
  async function printPdf(id, btn) {
    btnBusy(btn, true, 'Preparing…');
    try {
      const b = await fetchPdf(id), u = URL.createObjectURL(b), f = document.createElement('iframe');
      f.style.cssText = 'position:fixed;right:0;bottom:0;width:0;height:0;border:0'; f.src = u;
      f.onload = () => { try { f.contentWindow.focus(); f.contentWindow.print(); } catch { window.open(u, '_blank'); } setTimeout(() => { f.remove(); URL.revokeObjectURL(u); }, 60000); };
      document.body.appendChild(f);
    } catch (e) { toast(e.message, 'bad'); } finally { btnBusy(btn, false); }
  }
  async function pageBill(id) {
    const v = shell('#/bills', `<div id="bd">${loading('Loading bill…')}</div>`);
    const box = $('#bd', v);
    try {
      const b = await api('/api/bills/' + id);
      box.innerHTML = `<div class="page-head"><div><h1>${esc(b.bill_number)}</h1><p>${esc(b.created_display)} · <span class="badge ok">${esc(b.status.charAt(0) + b.status.slice(1).toLowerCase())}</span> <span class="badge gray">Payment not recorded</span></p></div>
        <div class="row"><button class="btn" id="dl">${icon('download')} Download PDF</button><button class="btn" id="pr">${icon('print')} Print</button><a class="btn primary" href="#/scan" id="nb">${icon('plus')} New bill</a></div></div>
        <div class="split"><div class="card flush"><div class="table-wrap"><table><thead><tr><th>Item</th><th class="right">Qty</th><th class="right">Unit price</th><th class="right">Discount</th><th class="right">Amount</th></tr></thead><tbody>
        ${b.items.map((i) => `<tr><td><b>${esc(i.name)}</b><div class="muted small">${esc(i.sku)}${i.pack ? ' · ' + esc(i.pack) : ''}</div></td><td class="right">${i.quantity}</td><td class="right">${money(i.unit_price)}</td><td class="right">${num(i.festival_discount) > 0 ? '−' + money(i.festival_discount) : '—'}</td><td class="right"><b>${money(i.line_total)}</b></td></tr>`).join('')}</tbody></table></div></div>
        <div class="card sticky-side"><h2 style="margin-bottom:14px">Totals</h2><div class="totals"><div class="line"><span class="muted">Subtotal</span><span>${money(b.subtotal)}</span></div>
        ${num(b.festival_discount) > 0 ? `<div class="line"><span>${esc(b.festival_name)} offer (${num(b.festival_percent)}%)</span><span class="minus">−${money(b.festival_discount)}</span></div>` : ''}
        ${b.combos.map((c) => `<div class="line"><span>${esc(c.name)} ×${c.sets}</span><span class="minus">−${money(c.discount_amount)}</span></div>`).join('')}
        <div class="line grand"><span>Total</span><span>${money(b.total)}</span></div></div></div></div>`;
      $('#dl', box).addEventListener('click', (e) => downloadPdf(b.id, b.bill_number, e.currentTarget));
      $('#pr', box).addEventListener('click', (e) => printPdf(b.id, e.currentTarget));
    } catch (e) { box.innerHTML = errorBox(e.message, false); }
  }

  /* ---------- bill history ---------- */
  async function pageBills() {
    const v = shell('#/bills', `<div class="page-head"><div><h1>Bills</h1><p>Search and reopen past invoices.</p></div></div><div class="card flush"><div style="padding:16px"><div class="search"><span>${icon('search')}</span><input class="input" id="bq" placeholder="Search by bill number" aria-label="Search bills"></div></div><div id="bl">${loading()}</div></div>`);
    let page = 1, q = '';
    async function load() {
      const box = $('#bl', v);
      try {
        const r = await api(`/api/bills?page=${page}&page_size=15&q=${encodeURIComponent(q)}`);
        if (!r.items.length) { box.innerHTML = emptyState('receipt', q ? 'No bills match your search' : 'No bills yet', q ? 'Try a different bill number.' : 'Generated bills will be listed here.', q ? '' : `<a class="btn primary" href="#/scan">Create a bill</a>`); return; }
        const pages = Math.max(1, Math.ceil(r.total / r.page_size));
        box.innerHTML = `<div class="table-wrap"><table><thead><tr><th>Bill number</th><th>Date</th><th class="right">Items</th><th class="right">Total</th><th>Status</th><th></th></tr></thead><tbody>${r.items.map((b) => `<tr><td><b>${esc(b.bill_number)}</b></td><td class="muted nowrap">${esc(b.created_display)}</td><td class="right">${b.item_count}</td><td class="right"><b>${money(b.total)}</b></td><td><span class="badge ok">${esc(b.status.charAt(0) + b.status.slice(1).toLowerCase())}</span></td><td class="right nowrap"><a class="btn sm" href="#/bill/${b.id}">View</a> <button class="btn sm" data-pdf="${b.id}" data-no="${esc(b.bill_number)}">${icon('download')} PDF</button></td></tr>`).join('')}</tbody></table></div>
          <div class="pager"><span class="muted small">${r.total} bill${r.total === 1 ? '' : 's'} · page ${r.page} of ${pages}</span><div class="row"><button class="btn sm" id="pv" ${page <= 1 ? 'disabled' : ''}>Previous</button><button class="btn sm" id="nx" ${page >= pages ? 'disabled' : ''}>Next</button></div></div>`;
        $$('[data-pdf]', box).forEach((b) => b.addEventListener('click', () => downloadPdf(b.dataset.pdf, b.dataset.no, b)));
        $('#pv', box).addEventListener('click', () => { page--; load(); }); $('#nx', box).addEventListener('click', () => { page++; load(); });
      } catch (e) { box.innerHTML = `<div style="padding:16px">${errorBox(e.message)}</div>`; const r = $('[data-retry]', box); r && r.addEventListener('click', (ev) => { ev.preventDefault(); load(); }); }
    }
    $('#bq', v).addEventListener('input', debounce((e) => { q = e.target.value.trim(); page = 1; load(); }, 300));
    load();
  }

  /* ---------- admin: products ---------- */
  async function pageProducts() {
    if (state.user.role !== 'admin') { location.hash = '#/dashboard'; return; }
    const v = shell('#/products', `<div class="page-head"><div><h1>Products</h1><p>Add products and keep prices up to date. Changes apply to new bills immediately.</p></div><button class="btn primary lg" id="add">${icon('plus')} Add product</button></div>
      <div class="card flush"><div class="row" style="padding:16px"><div class="search"><span>${icon('search')}</span><input class="input" id="pq" placeholder="Search name, SKU, brand or barcode" aria-label="Search products"></div><select class="input" id="pf" style="width:auto" aria-label="Filter by status"><option value="">All statuses</option><option value="true">Active</option><option value="false">Inactive</option></select></div><div id="pl">${loading()}</div></div>`);
    let page = 1, q = '', active = '';
    async function load() {
      const box = $('#pl', v);
      try {
        const r = await api(`/api/products?page=${page}&page_size=15&q=${encodeURIComponent(q)}${active ? '&active=' + active : ''}`);
        if (!r.items.length) { box.innerHTML = emptyState('box', q || active ? 'No products match' : 'No products yet', q || active ? 'Adjust your search or filter.' : 'Add your first product to start billing.', q || active ? '' : `<button class="btn primary" id="add2">${icon('plus')} Add product</button>`); const a = $('#add2', box); a && a.addEventListener('click', () => productForm(null, load)); return; }
        const pages = Math.max(1, Math.ceil(r.total / r.page_size));
        box.innerHTML = `<div class="table-wrap"><table><thead><tr><th>Product</th><th>SKU</th><th>Pack</th><th class="right">MRP</th><th class="right">Price</th><th class="right">Disc.</th><th>Status</th><th class="actions-col"></th></tr></thead><tbody>${r.items.map((p) => `<tr><td><div class="cell-prod">${prodThumb(p)}<div><b>${esc(p.name)}</b>${[p.brand, p.variant].filter(Boolean).length ? `<span class="muted small">${esc([p.brand, p.variant].filter(Boolean).join(' · '))}</span>` : ''}</div></div></td><td class="nowrap">${esc(p.sku)}</td><td class="nowrap">${esc(pack(p) || '—')}</td><td class="right">${money(p.mrp)}</td><td class="right"><b>${money(p.selling_price)}</b></td><td class="right">${num(p.discount_percent) > 0 ? num(p.discount_percent) + '%' : '—'}</td><td>${statusBadge(p.is_active)}</td>
          <td class="right nowrap actions-col"><button class="btn sm" data-edit="${p.id}">${icon('edit')} Edit</button> <button class="btn sm" data-tog="${p.id}" data-act="${p.is_active}">${p.is_active ? 'Deactivate' : 'Activate'}</button> <button class="btn sm danger" data-del="${p.id}" aria-label="Delete ${esc(p.name)}">${icon('trash')}</button></td></tr>`).join('')}</tbody></table></div>
          <div class="pager"><span class="muted small">${r.total} product${r.total === 1 ? '' : 's'} · page ${r.page} of ${pages}</span><div class="row"><button class="btn sm" id="pv" ${page <= 1 ? 'disabled' : ''}>Previous</button><button class="btn sm" id="nx" ${page >= pages ? 'disabled' : ''}>Next</button></div></div>`;
        const byId = (id) => r.items.find((p) => String(p.id) === String(id));
        $$('[data-edit]', box).forEach((b) => b.addEventListener('click', () => productForm(byId(b.dataset.edit), load)));
        $$('[data-tog]', box).forEach((b) => b.addEventListener('click', async () => {
          const p = byId(b.dataset.tog), to = !p.is_active;
          if (!to && !(await confirmDialog({ title: 'Deactivate product?', message: `“${p.name}” will no longer be available for billing. Past bills are not affected.`, confirmText: 'Deactivate', danger: true }))) return;
          try { await api(`/api/products/${p.id}/${to ? 'activate' : 'deactivate'}`, { method: 'POST' }); toast(`${p.name} ${to ? 'activated' : 'deactivated'}`, 'ok'); load(); } catch (e) { toast(e.message, 'bad'); }
        }));
        $$('[data-del]', box).forEach((b) => b.addEventListener('click', async () => {
          const p = byId(b.dataset.del);
          if (!(await confirmDialog({ title: 'Delete product?', message: `Permanently delete “${p.name}” (${p.sku})? This cannot be undone. Products used on past bills can only be deactivated.`, confirmText: 'Delete', danger: true }))) return;
          try { await api('/api/products/' + p.id, { method: 'DELETE' }); toast('Product deleted', 'ok'); load(); } catch (e) { toast(e.message, 'bad'); }
        }));
        $('#pv', box).addEventListener('click', () => { page--; load(); }); $('#nx', box).addEventListener('click', () => { page++; load(); });
      } catch (e) { box.innerHTML = `<div style="padding:16px">${errorBox(e.message)}</div>`; const rt = $('[data-retry]', box); rt && rt.addEventListener('click', (ev) => { ev.preventDefault(); load(); }); }
    }
    $('#add', v).addEventListener('click', () => productForm(null, load));
    $('#pq', v).addEventListener('input', debounce((e) => { q = e.target.value.trim(); page = 1; load(); }, 300));
    $('#pf', v).addEventListener('change', (e) => { active = e.target.value; page = 1; load(); });
    load();
  }

  async function productForm(p, done) {
    if (!state.classes) { try { state.classes = (await api('/api/scan/status')).classes || []; } catch { state.classes = []; } }
    const val = (k, d = '') => esc(p ? (p[k] ?? d) : d);
    const m = modal({ title: p ? 'Edit product' : 'Add product', body: `<form id="pf" novalidate><div class="form-grid">
      <div class="field full"><label for="f-name">Product name <span class="req">*</span></label><input class="input" id="f-name" maxlength="160" value="${val('name')}"><div class="err" data-e="name"></div></div>
      <div class="field"><label for="f-sku">SKU <span class="req">*</span></label><input class="input" id="f-sku" maxlength="64" value="${val('sku')}" placeholder="e.g. LAYS-CLASSIC-10"><div class="hint">Unique. Letters, digits, . _ -</div><div class="err" data-e="sku"></div></div>
      <div class="field"><label for="f-barcode">Barcode</label><input class="input" id="f-barcode" maxlength="64" value="${val('barcode')}"><div class="err" data-e="barcode"></div></div>
      <div class="field"><label for="f-brand">Brand</label><input class="input" id="f-brand" maxlength="80" value="${val('brand')}"></div>
      <div class="field"><label for="f-category">Category</label><input class="input" id="f-category" maxlength="80" value="${val('category')}"></div>
      <div class="field"><label for="f-variant">Variant</label><input class="input" id="f-variant" maxlength="80" value="${val('variant')}" placeholder="e.g. Classic Salted"></div>
      <div class="field"><label>Pack size / unit</label><div class="row" style="flex-wrap:nowrap"><input class="input" id="f-pack" maxlength="30" value="${val('pack_size')}" placeholder="26" aria-label="Pack size"><input class="input" id="f-unit" maxlength="20" value="${val('unit')}" placeholder="g" aria-label="Unit" style="max-width:96px"></div></div>
      <div class="field"><label for="f-mrp">MRP (₹) <span class="req">*</span></label><input class="input" id="f-mrp" inputmode="decimal" value="${p ? esc(p.mrp) : ''}"><div class="err" data-e="mrp"></div></div>
      <div class="field"><label for="f-price">Selling price (₹) <span class="req">*</span></label><input class="input" id="f-price" inputmode="decimal" value="${p ? esc(p.selling_price) : ''}"><div class="hint" id="disc">Discount: —</div><div class="err" data-e="price"></div></div>
      <div class="field full"><label for="f-class">Recognition class</label><select class="input" id="f-class"><option value="">None (not recognised by AI)</option>${state.classes.map((c) => `<option value="${esc(c)}" ${p && p.ai_class === c ? 'selected' : ''}>${esc(c.replace(/_/g, ' '))}</option>`).join('')}</select><div class="hint">Links this SKU to a class the classifier can output. Several SKUs may share one class; the cashier then picks the exact SKU. A brand-new product the model was never trained on cannot be recognised until the model is retrained (see README).</div></div>
      <div class="field full"><label for="f-img">Product image</label><div class="row">${p ? prodThumb(p) : ''}<input id="f-img" type="file" accept="image/jpeg,image/png,image/webp"></div><div class="hint">JPEG, PNG or WebP, up to 8 MB.</div><div class="err" data-e="img"></div></div>
      <div class="field full"><label for="f-ref">Reference images</label>${p && p.reference_images.length ? `<div class="refs" id="refs">${p.reference_images.map((r) => `<div class="ref"><img src="${esc(r.url)}" alt="Reference"><button type="button" data-delref="${r.id}" aria-label="Remove reference image">×</button></div>`).join('')}</div>` : ''}<input id="f-ref" type="file" accept="image/jpeg,image/png,image/webp" multiple><div class="hint">Stored for future model enrolment. The current classifier does not use them.</div></div>
      <div class="field full"><label style="display:flex;gap:10px;align-items:center;font-weight:600"><input type="checkbox" id="f-active" ${!p || p.is_active ? 'checked' : ''}> Active (available for billing)</label></div></div><div id="ferr" style="margin-top:12px"></div></form>`,
      footer: `<button class="btn" data-close>Cancel</button><button class="btn primary" id="save">${p ? 'Save changes' : 'Add product'}</button>` });
    const g = (id) => $(id, m.el);
    const upd = () => { const a = parseFloat(g('#f-mrp').value), b = parseFloat(g('#f-price').value); g('#disc').textContent = (a > 0 && b >= 0 && b <= a) ? `Discount: ${(((a - b) / a) * 100).toFixed(1)}% (₹${(a - b).toFixed(2)})` : 'Discount: —'; };
    g('#f-mrp').addEventListener('input', upd); g('#f-price').addEventListener('input', upd); upd();
    $$('[data-delref]', m.el).forEach((b) => b.addEventListener('click', async () => { try { await api(`/api/products/${p.id}/reference-images/${b.dataset.delref}`, { method: 'DELETE' }); b.closest('.ref').remove(); done && done(); } catch (e) { toast(e.message, 'bad'); } }));
    g('#save').addEventListener('click', async () => {
      $$('.err', m.el).forEach((e) => (e.textContent = '')); $$('.input', m.el).forEach((i) => i.classList.remove('invalid')); g('#ferr').innerHTML = '';
      const body = { name: g('#f-name').value.trim(), sku: g('#f-sku').value.trim().toUpperCase(), brand: g('#f-brand').value.trim(), category: g('#f-category').value.trim(), variant: g('#f-variant').value.trim(), pack_size: g('#f-pack').value.trim(), unit: g('#f-unit').value.trim(), barcode: g('#f-barcode').value.trim() || null, mrp: g('#f-mrp').value.trim(), selling_price: g('#f-price').value.trim(), ai_class: g('#f-class').value || null, is_active: g('#f-active').checked };
      const bad = {}; const isMoney = (s) => /^\d{1,8}(\.\d{1,2})?$/.test(s);
      if (!body.name) bad.name = 'Enter a product name.';
      if (!/^[A-Z0-9][A-Z0-9._-]{1,63}$/.test(body.sku)) bad.sku = 'Use 2–64 characters: letters, digits, . _ -';
      if (!isMoney(body.mrp)) bad.mrp = 'Enter a valid amount (max 2 decimals).';
      if (!isMoney(body.selling_price)) bad.price = 'Enter a valid amount (max 2 decimals).';
      else if (isMoney(body.mrp) && parseFloat(body.selling_price) > parseFloat(body.mrp)) bad.price = 'Selling price cannot be higher than MRP.';
      const imgF = g('#f-img').files[0], refs = Array.from(g('#f-ref').files);
      if (imgF && imgF.size > 8 * 1024 * 1024) bad.img = 'Image is larger than 8 MB.';
      if (Object.keys(bad).length) { Object.entries(bad).forEach(([k, msg]) => { const e = $(`[data-e="${k}"]`, m.el); e.textContent = msg; const inp = e.parentElement.querySelector('.input'); inp && inp.classList.add('invalid'); }); const f = $('.input.invalid', m.el); f && f.focus(); return; }
      btnBusy(g('#save'), true, 'Saving…');
      try {
        let saved = await api(p ? '/api/products/' + p.id : '/api/products', { method: p ? 'PUT' : 'POST', json: body });
        const fails = [];
        if (imgF) { const fd = new FormData(); fd.append('file', imgF); try { saved = await api(`/api/products/${saved.id}/image`, { method: 'POST', form: fd }); } catch (e) { fails.push('Product image: ' + e.message); } }
        for (const f of refs) { const fd = new FormData(); fd.append('file', f); try { await api(`/api/products/${saved.id}/reference-images`, { method: 'POST', form: fd }); } catch (e) { fails.push(`${f.name}: ${e.message}`); } }
        if (fails.length) { toast(`Product saved, but some images failed: ${fails.join(' | ')}`, 'bad'); } else toast(p ? 'Product updated' : 'Product added', 'ok');
        m.close(); done && done();
      } catch (e) {
        btnBusy(g('#save'), false);
        g('#ferr').innerHTML = `<div class="alert bad" role="alert">${icon('alert')}<div>${esc(e.message)}</div></div>`;
        if (e.status === 409) { const s = $('[data-e="sku"]', m.el); s.textContent = e.message; g('#f-sku').classList.add('invalid'); }
      }
    });
  }

  /* ---------- router ---------- */
  function route() {
    if (cleanup) { try { cleanup(); } catch { /* ignore */ } cleanup = null; }
    const hash = location.hash || '#/dashboard';
    const [, name, arg] = hash.split('/');
    if (!state.token || !state.user) { if (name !== 'login') { location.hash = '#/login'; return; } return pageLogin(); }
    if (name === 'login') { location.hash = '#/dashboard'; return; }
    const pages = { dashboard: pageDashboard, scan: pageScan, review: pageReview, cart: pageCart, bills: pageBills, products: pageProducts, bill: () => pageBill(arg) };
    (pages[name] || pageDashboard)();
    window.scrollTo(0, 0);
  }
  window.addEventListener('hashchange', route);
  route();
})();
