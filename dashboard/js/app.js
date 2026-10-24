/* بهوش — ابزار مشترک صفحه‌ها: API، قالب‌بندی فارسی، تاریخ شمسی، آیکن، اعلان. */
(function () {
  'use strict';
  var BH = window.BH = window.BH || {};

  /* ---------- API ---------- */
  BH.apiBase = function () {
    return (window.BEHOOSH && window.BEHOOSH.apiBase) || 'https://behoosh-api.hashpa.com/v1';
  };
  BH.token = function () { try { return localStorage.getItem('behoosh_token') || ''; } catch (e) { return ''; } };
  BH.scopes = function () {
    try { return JSON.parse(localStorage.getItem('behoosh_scopes') || '[]'); } catch (e) { return []; }
  };
  BH.logout = function () {
    try {
      localStorage.removeItem('behoosh_token'); localStorage.removeItem('behoosh_scopes');
      sessionStorage.removeItem('behoosh_me');
    } catch (e) {}
    location.href = 'login.html';
  };
  BH.requireAuth = function () {
    if (!BH.token()) { location.replace('login.html?next=' + encodeURIComponent(location.pathname.split('/').pop())); return false; }
    return true;
  };
  BH.api = async function (path, opts) {
    opts = opts || {};
    var headers = { 'X-API-Key': BH.token() };
    if (opts.body !== undefined) headers['Content-Type'] = 'application/json';
    var r = await fetch(BH.apiBase() + path, {
      method: opts.method || (opts.body !== undefined ? 'POST' : 'GET'),
      headers: headers,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined
    });
    if (r.status === 401) { BH.logout(); throw new Error('auth'); }
    var data = null;
    try { data = await r.json(); } catch (e) {}
    if (!r.ok) {
      var err = new Error((data && data.detail && (typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail))) || ('HTTP ' + r.status));
      err.status = r.status; throw err;
    }
    return data;
  };

  /* ---------- قالب‌بندی ---------- */
  var nfCache = {};
  function nf(d) {
    var k = String(d);
    if (!nfCache[k]) nfCache[k] = new Intl.NumberFormat('fa-IR', { maximumFractionDigits: d, minimumFractionDigits: 0 });
    return nfCache[k];
  }
  BH.n = function (v, d) {
    if (v === null || v === undefined || isNaN(v)) return '—';
    return nf(d === undefined ? 0 : d).format(v);
  };
  BH.fa = function (s) { return String(s).replace(/[0-9]/g, function (c) { return '۰۱۲۳۴۵۶۷۸۹'[+c]; }); };
  BH.pct = function (v, d) { return BH.n(v, d === undefined ? 0 : d) + '٪'; };
  /* مبلغ تومان. compact: ۱۲۴٫۳ میلیون */
  BH.money = function (v, compact) {
    if (v === null || v === undefined || isNaN(v)) return '—';
    var a = Math.abs(v), s = v < 0 ? '−' : '';
    if (compact) {
      if (a >= 1e9) return s + BH.n(a / 1e9, 1) + ' میلیارد';
      if (a >= 1e6) return s + BH.n(a / 1e6, 1) + ' میلیون';
      if (a >= 1e4) return s + BH.n(a / 1e3, 0) + ' هزار';
    }
    return s + BH.n(a, 0);
  };
  BH.hm = function (hours) {
    if (!hours) return '—';
    var h = Math.floor(hours), m = Math.round((hours - h) * 60);
    if (m === 60) { h += 1; m = 0; }
    return BH.fa(h + ':' + String(m).padStart(2, '0'));
  };
  BH.minutes = function (min) {
    if (!min) return BH.fa('0:00');
    return BH.fa(Math.floor(min / 60) + ':' + String(Math.round(min % 60)).padStart(2, '0'));
  };

  /* ---------- تاریخ شمسی (تقویم ایرانی از Intl) ---------- */
  function toDate(iso) {
    if (iso instanceof Date) return iso;
    var s = String(iso);
    return new Date(s.length <= 10 ? s + 'T12:00:00' : s);
  }
  var dfCache = {};
  function df(opts) {
    var k = JSON.stringify(opts);
    if (!dfCache[k]) dfCache[k] = new Intl.DateTimeFormat('fa-IR-u-ca-persian', opts);
    return dfCache[k];
  }
  BH.date = function (iso, style) {
    if (!iso) return '—';
    var d = toDate(iso);
    if (isNaN(d)) return String(iso);
    switch (style) {
      case 'short': return df({ day: 'numeric', month: 'short' }).format(d);          // ۲ آبان
      case 'weekday': return df({ weekday: 'long', day: 'numeric', month: 'long' }).format(d);
      case 'month': return df({ month: 'long', year: 'numeric' }).format(d);
      case 'monthShort': return df({ month: 'short' }).format(d);
      case 'num': return df({ year: 'numeric', month: '2-digit', day: '2-digit' }).format(d);
      case 'time': return df({ hour: '2-digit', minute: '2-digit' }).format(d);
      case 'full': return df({ year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(d);
      default: return df({ year: 'numeric', month: 'long', day: 'numeric' }).format(d);
    }
  };
  BH.todayISO = function () {
    var d = new Date(); return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  };
  BH.greeting = function () {
    var h = new Date().getHours();
    return h < 5 ? 'شب بخیر' : h < 12 ? 'صبح بخیر' : h < 17 ? 'ظهر بخیر' : h < 21 ? 'عصر بخیر' : 'شب بخیر';
  };

  /* ---------- DOM ---------- */
  BH.$ = function (sel, root) { return (root || document).querySelector(sel); };
  BH.$$ = function (sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); };
  BH.esc = function (s) {
    return String(s === null || s === undefined ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  };
  BH.css = function (name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); };
  BH.empty = function (text, icon) {
    return '<div class="empty">' + BH.icon(icon || 'inbox') + '<div>' + BH.esc(text) + '</div></div>';
  };
  /* نشان تغییر: good=true یعنی افزایش خوب است */
  BH.delta = function (cur, prev, opts) {
    opts = opts || {};
    if (!prev || cur === null || cur === undefined || isNaN(cur)) return '';
    var ch = (cur - prev) / Math.abs(prev) * 100;
    if (!isFinite(ch)) return '';
    var dir = Math.abs(ch) < 1 ? 'flat' : ch > 0 ? 'up' : 'down';
    var good = opts.invert ? (dir === 'down') : (dir === 'up');
    var cls = dir === 'flat' ? 'flat' : (good ? 'up' : 'down');
    var ic = dir === 'flat' ? 'minus' : dir === 'up' ? 'trend-up' : 'trend-down';
    return '<span class="delta ' + cls + '" title="نسبت به دوره قبل">' + BH.icon(ic) + BH.n(Math.abs(ch), 0) + '٪</span>';
  };

  /* ---------- اعلان ---------- */
  BH.toast = function (msg, icon) {
    var host = document.querySelector('.toast-host');
    if (!host) { host = document.createElement('div'); host.className = 'toast-host'; host.setAttribute('role', 'status'); document.body.appendChild(host); }
    var t = document.createElement('div');
    t.className = 'toast';
    t.innerHTML = BH.icon(icon || 'check') + '<span>' + BH.esc(msg) + '</span>';
    host.appendChild(t);
    setTimeout(function () { t.style.transition = 'opacity .3s'; t.style.opacity = '0'; }, 2600);
    setTimeout(function () { t.remove(); }, 3000);
  };

  /* ---------- آیکن‌ها (سبک Lucide، خطی) ---------- */
  var P = {
    home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/><path d="M9.5 21v-6h5v6"/>',
    heart: '<path d="M19 14c1.5-1.5 3-3.2 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.8 0-3 .5-4.5 2-1.5-1.5-2.7-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4 3 5.5l7 7Z"/><path d="M3.2 12h4.3l2-3 3 6 2-3h6.3"/>',
    wallet: '<path d="M19 7V5a2 2 0 0 0-2-2H5a2 2 0 0 0 0 4h14a2 2 0 0 1 2 2v3"/><path d="M3 5v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-3"/><path d="M21 12h-4a2 2 0 0 0 0 4h4v-4Z"/>',
    mic: '<rect x="9" y="2.5" width="6" height="12" rx="3"/><path d="M5 10.5a7 7 0 0 0 14 0"/><path d="M12 17.5V21"/>',
    plug: '<path d="M9 2v6M15 2v6"/><path d="M6 8h12v3a6 6 0 0 1-12 0V8Z"/><path d="M12 17v5"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    moon: '<path d="M20.5 14.5A8.5 8.5 0 1 1 9.5 3.5a7 7 0 0 0 11 11Z"/>',
    monitor: '<rect x="2.5" y="3.5" width="19" height="13" rx="2"/><path d="M8 20.5h8M12 16.5v4"/>',
    logout: '<path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><path d="m10 17-5-5 5-5"/><path d="M5 12h12"/>',
    login: '<path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><path d="m10 17 5-5-5-5"/><path d="M15 12H3"/>',
    flame: '<path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.4-.5-2-1-3-1.1-2.1-.2-4 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.2.4-2.3 1-3.3.3 1.3 1.3 2.8 2.5 2.8Z"/>',
    egg: '<path d="M12 22c4 0 7-3 7-7.5C19 9 15.5 2 12 2S5 9 5 14.5C5 19 8 22 12 22Z"/>',
    bed: '<path d="M2 4v16M2 8h18a2 2 0 0 1 2 2v10M2 17h20"/><path d="M6 8v9"/>',
    scale: '<path d="M16 16.5 19 9l3 7.5a4 4 0 0 1-6 0ZM2 16.5 5 9l3 7.5a4 4 0 0 1-6 0Z"/><path d="M7 21h10M12 3v18M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/>',
    droplet: '<path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5S12.5 5.5 12 2.5c-.5 3-2 4.9-4 6.5S5 13 5 15a7 7 0 0 0 7 7Z"/>',
    smile: '<circle cx="12" cy="12" r="10"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><path d="M9 9h.01M15 9h.01"/>',
    phone: '<rect x="5" y="2" width="14" height="20" rx="2.5"/><path d="M11 18h2"/>',
    dumbbell: '<path d="M14.4 14.4 9.6 9.6"/><path d="M18.66 21.51a2 2 0 1 1-2.83-2.83l-1.77 1.77a2 2 0 1 1-2.83-2.83l6.37-6.37a2 2 0 1 1 2.83 2.83l-1.77 1.77a2 2 0 1 1 2.83 2.83Z"/><path d="m21.5 21.5-1.4-1.4M3.9 3.9 2.5 2.5"/><path d="M6.4 12.77a2 2 0 1 1-2.83-2.83l1.77-1.77a2 2 0 1 1-2.83-2.83l2.83-2.83a2 2 0 1 1 2.83 2.83l1.77-1.77a2 2 0 1 1 2.83 2.83Z"/>',
    activity: '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    sparkles: '<path d="M9.94 15.5A2 2 0 0 0 8.5 14.06l-6.13-1.58a.5.5 0 0 1 0-.96L8.5 9.94A2 2 0 0 0 9.94 8.5l1.58-6.13a.5.5 0 0 1 .96 0L14.06 8.5A2 2 0 0 0 15.5 9.94l6.13 1.58a.5.5 0 0 1 0 .96L15.5 14.06a2 2 0 0 0-1.44 1.44l-1.58 6.13a.5.5 0 0 1-.96 0Z"/><path d="M20 3v4M22 5h-4"/>',
    'trend-up': '<path d="m22 7-8.5 8.5-5-5L2 17"/><path d="M16 7h6v6"/>',
    'trend-down': '<path d="m22 17-8.5-8.5-5 5L2 7"/><path d="M16 17h6v-6"/>',
    minus: '<path d="M5 12h14"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    x: '<path d="M18 6 6 18M6 6l12 12"/>',
    alert: '<path d="m21.7 18-8-14a2 2 0 0 0-3.4 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.7-3Z"/><path d="M12 9v4M12 17h.01"/>',
    info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
    target: '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    award: '<circle cx="12" cy="8" r="6"/><path d="M15.5 12.9 17 22l-5-3-5 3 1.5-9.1"/>',
    clock: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    calendar: '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    search: '<circle cx="11" cy="11" r="7.5"/><path d="m20.5 20.5-4.2-4.2"/>',
    download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5M12 15V3"/>',
    refresh: '<path d="M21 12a9 9 0 0 1-15 6.7L3 16"/><path d="M3 21v-5h5"/><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M21 3v5h-5"/>',
    card: '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20M6 15h4"/>',
    piggy: '<path d="M19 5c-1.5 0-2.8 1.4-3 2-3.5-1.5-11-.3-11 5 0 1.8 0 3 2 4.5V20h4v-2h3v2h4v-4c1-.5 1.7-1 2-2h2v-4h-2c0-1-.5-1.5-1-2V5Z"/><path d="M2 9v1c0 1.1.9 2 2 2h1"/><path d="M16 11h.01"/>',
    bank: '<path d="M3 22h18M6 18v-7M10 18v-7M14 18v-7M18 18v-7"/><path d="m12 2 8 5H4Z"/>',
    receipt: '<path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1Z"/><path d="M16 8H8M16 12H8M13 16H8"/>',
    message: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2Z"/>',
    file: '<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5Z"/><path d="M14 2v6h6M16 13H8M16 17H8M10 9H8"/>',
    pie: '<path d="M21.2 15.9A10 10 0 1 1 8 2.8"/><path d="M22 12A10 10 0 0 0 12 2v10Z"/>',
    chart: '<path d="M3 3v18h18"/><path d="M18 17V9M13 17V5M8 17v-3"/>',
    list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
    shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/>',
    zap: '<path d="M13 2 3 14h9l-1 8 10-12h-9l1-8Z"/>',
    leaf: '<path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.5 19 2c1 2 2 4.2 2 8 0 5.5-4.8 10-10 10Z"/><path d="M2 21c0-3 1.9-5.4 5.2-6.1 2.4-.5 4.9-2 5.8-3.9"/>',
    moonstar: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/><path d="M19 3v4M21 5h-4"/>',
    compass: '<circle cx="12" cy="12" r="10"/><path d="m16.2 7.8-2.1 6.3-6.3 2.1 2.1-6.3Z"/>',
    inbox: '<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.5 5.1 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.5-6.9A2 2 0 0 0 16.8 4H7.2a2 2 0 0 0-1.7 1.1Z"/>',
    copy: '<rect x="8" y="8" width="14" height="14" rx="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
    key: '<circle cx="7.5" cy="15.5" r="5.5"/><path d="m21 2-9.6 9.6M15.5 7.5l3 3L22 7l-3-3"/>',
    user: '<circle cx="12" cy="8" r="5"/><path d="M20 21a8 8 0 0 0-16 0"/>',
    menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
    chevron: '<path d="m15 18-6-6 6-6"/>',
    arrowLeft: '<path d="M19 12H5M12 19l-7-7 7-7"/>',
    swap: '<path d="m16 3 4 4-4 4M20 7H4M8 21l-4-4 4-4M4 17h16"/>',
    flag: '<path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1zM4 22v-7"/>',
    brain: '<path d="M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .556 6.588A4 4 0 1 0 12 18Z"/><path d="M12 5a3 3 0 1 1 5.997.125 4 4 0 0 1 2.526 5.77 4 4 0 0 1-.556 6.588A4 4 0 1 1 12 18Z"/><path d="M12 5v13"/>',
    thermo: '<path d="M14 4v10.54a4 4 0 1 1-4 0V4a2 2 0 0 1 4 0Z"/>',
    pray: '<path d="M12 3c-2 3-3 5.5-3 8.5 0 2 1 3.5 3 3.5s3-1.5 3-3.5C15 8.5 14 6 12 3Z"/><path d="M5 21c1-3 3.5-5 7-5s6 2 7 5"/>',
    stop: '<rect x="6" y="6" width="12" height="12" rx="2.5"/>'
  };
  BH.icon = function (name, cls) {
    return '<svg class="' + (cls || '') + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" ' +
      'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (P[name] || P.info) + '</svg>';
  };
  BH.hasIcon = function (name) { return !!P[name]; };
})();
