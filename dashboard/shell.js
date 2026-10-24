/* بهوش — پوسته مشترک
   سایدبار کشویی موبایل، جایگزین منوی بالا در عرض کم.
   در همه صفحات صدا زده می‌شود و به توکن کاربر دست نمی‌زند. */
(function () {
  'use strict';

  var I = {
    home: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3 10.6 12 3.5l9 7.1"/><path d="M5.5 9.6V20h13V9.6"/><path d="M10 20v-5h4v5"/></svg>',
    heart: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20.4S4.6 15.6 4.6 10.5A4.4 4.4 0 0 1 12 7.7a4.4 4.4 0 0 1 7.4 2.8c0 5.1-7.4 9.9-7.4 9.9Z"/></svg>',
    card: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="2.8" y="5.6" width="18.4" height="12.8" rx="2.4"/><path d="M2.8 10h18.4"/><path d="M6.6 14.6h3.2"/></svg>',
    mic: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.6 11.4a6.4 6.4 0 0 0 12.8 0"/><path d="M12 17.8V21"/></svg>',
    plug: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M9 3v4.6M15 3v4.6"/><path d="M6.6 7.6h10.8V11a5.4 5.4 0 0 1-10.8 0Z"/><path d="M12 16.4V21"/></svg>'
  };

  var ITEMS = [
    { f: 'index.html',     t: 'خانه',           i: I.home },
    { f: 'dashboard.html', t: 'داشبورد سلامت',  i: I.heart },
    { f: 'finance.html',   t: 'داشبورد مالی',   i: I.card },
    { f: 'live.html',      t: 'دستیار جلسه',    i: I.mic },
    { f: 'connect.html',   t: 'اتصال به ایجنت', i: I.plug }
  ];

  var SCOPE_FA = { health: 'سلامت', finance: 'مالی', meeting: 'جلسه' };

  var CSS = `
.bh-burger{display:none;position:fixed;top:11px;inset-inline-end:11px;z-index:70;width:42px;height:42px;
  border-radius:12px;border:1px solid var(--hair,#e4e4e7);background:rgba(255,255,255,.94);
  -webkit-backdrop-filter:blur(10px);backdrop-filter:blur(10px);cursor:pointer;padding:0;
  place-items:center;gap:4px;box-shadow:0 1px 2px rgba(0,0,0,.04)}
.bh-burger span{display:block;width:17px;height:2px;border-radius:2px;background:var(--ink,#111)}
.bh-scrim{position:fixed;inset:0;background:rgba(17,17,17,.44);opacity:0;visibility:hidden;
  transition:opacity .22s ease,visibility .22s;z-index:80}
html.bh-open .bh-scrim{opacity:1;visibility:visible}
.bh-drawer{position:fixed;top:0;bottom:0;inset-inline-start:0;width:292px;max-width:86vw;background:#fff;
  z-index:90;display:flex;flex-direction:column;box-shadow:0 0 0 1px var(--hair,#e4e4e7);
  transform:translateX(102%);transition:transform .26s cubic-bezier(.22,.7,.3,1)}
html[dir=ltr] .bh-drawer{transform:translateX(-102%)}
html.bh-open .bh-drawer{transform:none}
.bh-dhead{display:flex;align-items:center;justify-content:space-between;gap:10px;
  padding:15px 15px 12px;border-bottom:1px solid var(--hair,#e4e4e7)}
.bh-logo{display:flex;align-items:center;gap:9px;font-weight:800;font-size:17px;letter-spacing:-.02em}
.bh-dot{width:26px;height:26px;border-radius:9px;background:var(--ink,#111);color:#fff;display:grid;
  place-items:center;font-size:13px;font-weight:700}
.bh-x{width:44px;height:44px;border:0;background:var(--soft);color:var(--ink);border-radius:12px;font-size:21px;line-height:1;cursor:pointer;flex:none}
.bh-links{display:flex;flex-direction:column;gap:2px;padding:10px;overflow-y:auto;flex:1}
.bh-link{display:flex;align-items:center;gap:11px;padding:12px;border-radius:12px;min-height:48px;
  color:var(--body,#3f3f46);text-decoration:none;font-size:14.5px;font-weight:500}
.bh-link .bh-ic{width:22px;height:22px;flex:none;display:grid;place-items:center;color:var(--muted,#71717a)}
.bh-link .bh-ic svg{width:21px;height:21px}
.bh-link:hover{background:var(--card,#f5f5f5);color:var(--ink,#111)}
.bh-link.on{background:var(--card,#f5f5f5);color:var(--ink,#111);font-weight:700}
.bh-link.on .bh-ic{color:var(--ink,#111)}
.bh-foot{padding:12px 14px calc(14px + env(safe-area-inset-bottom));border-top:1px solid var(--hair,#e4e4e7)}
.bh-meta{font-size:12.5px;color:var(--muted,#71717a);margin-bottom:9px;line-height:1.8}
.bh-out{display:block;width:100%;text-align:center;text-decoration:none;font-family:inherit;
  font-size:13.5px;font-weight:600;padding:12px;border-radius:12px;border:1px solid var(--hair,#e4e4e7);
  background:#fff;color:var(--body,#3f3f46);cursor:pointer}
body.bh-lock{overflow:hidden}
@media (max-width:880px){
  [data-shell-hide]{display:none !important}
  header.top nav{display:none !important}
  .topbar{display:none !important}
  header.top a.btn{display:none !important}
  header.top .wrap{height:58px;padding-inline-end:56px}
  .bh-burger{display:grid}
  .pill{min-height:44px;display:inline-flex;align-items:center;justify-content:center}
  .kpi .lbl{font-size:12.5px}
  .kpi .sub,.hint,.hsub,.sub{font-size:12px}
  main{padding-bottom:130px}
}
`;

  function ls(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }

  function boot() {
    if (document.getElementById('bhBurger')) return;
    var here = (location.pathname.split('/').pop() || 'index.html').toLowerCase();
    var hasToken = !!ls('behoosh_token');
    var scopes = [];
    try {
      JSON.parse(ls('behoosh_scopes') || '[]').forEach(function (s) {
        var d = String(s).split(':')[0];
        if (scopes.indexOf(d) < 0) scopes.push(d);
      });
    } catch (e) {}

    var st = document.createElement('style');
    st.textContent = CSS;
    document.head.appendChild(st);

    var links = ITEMS.map(function (it) {
      return '<a class="bh-link' + (it.f === here ? ' on' : '') + '" href="' + it.f + '">' +
             '<span class="bh-ic">' + it.i + '</span><span>' + it.t + '</span></a>';
    }).join('');

    var box = document.createElement('div');
    box.innerHTML =
      '<div class="bh-scrim" id="bhScrim"></div>' +
      '<aside class="bh-drawer" id="bhDrawer" aria-hidden="true" aria-label="منوی اصلی">' +
        '<div class="bh-dhead"><div class="bh-logo"><span class="bh-dot">ب</span> بهوش</div>' +
        '<button class="bh-x" id="bhClose" aria-label="بستن منو">&#215;</button></div>' +
        '<nav class="bh-links">' + links + '</nav>' +
        '<div class="bh-foot">' +
          '<div class="bh-meta">' + (hasToken
            ? ('وارد شده‌ای' + (scopes.length ? '، دسترسی: ' + scopes.map(function (s) { return SCOPE_FA[s] || s; }).join('، ') : ''))
            : 'وارد نشده‌ای') + '</div>' +
          (hasToken ? '<button class="bh-out" id="bhOut">خروج از حساب</button>'
                    : '<a class="bh-out" href="login.html">ورود</a>') +
        '</div>' +
      '</aside>' +
      '<button class="bh-burger" id="bhBurger" aria-label="نمایش منو" aria-expanded="false">' +
        '<span></span><span></span><span></span></button>';
    while (box.firstChild) document.body.appendChild(box.firstChild);

    var drawer = document.getElementById('bhDrawer');
    var burger = document.getElementById('bhBurger');

    function open() {
      document.documentElement.classList.add('bh-open');
      drawer.setAttribute('aria-hidden', 'false');
      burger.setAttribute('aria-expanded', 'true');
      document.body.classList.add('bh-lock');
    }
    function close() {
      document.documentElement.classList.remove('bh-open');
      drawer.setAttribute('aria-hidden', 'true');
      burger.setAttribute('aria-expanded', 'false');
      document.body.classList.remove('bh-lock');
    }
    burger.onclick = function () {
      if (document.documentElement.classList.contains('bh-open')) close(); else open();
    };
    document.getElementById('bhScrim').onclick = close;
    document.getElementById('bhClose').onclick = close;
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); });
    var sx = 0, sy = 0;
    drawer.addEventListener('touchstart', function (e) {
      sx = e.touches[0].clientX; sy = e.touches[0].clientY;
    }, { passive: true });
    drawer.addEventListener('touchend', function (e) {
      var dx = e.changedTouches[0].clientX - sx, dy = Math.abs(e.changedTouches[0].clientY - sy);
      if (dx > 55 && dy < 60) close();
    }, { passive: true });

    var out = document.getElementById('bhOut');
    if (out) out.onclick = function () {
      if (typeof window.logout === 'function') { window.logout(); return; }
      try { localStorage.removeItem('behoosh_token'); localStorage.removeItem('behoosh_scopes'); } catch (e) {}
      location.href = 'login.html';
    };
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
