/* بهوش — پوسته برنامه
   روی صفحه‌هایی که <div class="app"> دارند: سایدبار دسکتاپ، نوار بالا و ناوبری پایین موبایل،
   سوییچ تم و کارت کاربر. به توکن دست نمی‌زند جز برای خواندن نام کاربر. */
(function () {
  'use strict';
  var BH = window.BH;

  var ITEMS = [
    { f: 'index.html', k: 'home', t: 'خانه', s: 'خانه', i: 'home' },
    { f: 'dashboard.html', k: 'health', t: 'داشبورد سلامت', s: 'سلامت', i: 'heart' },
    { f: 'finance.html', k: 'finance', t: 'داشبورد مالی', s: 'مالی', i: 'wallet' },
    { f: 'live.html', k: 'live', t: 'دستیار جلسه', s: 'جلسه', i: 'mic' },
    { f: 'connect.html', k: 'connect', t: 'اتصال به ایجنت', s: 'ایجنت', i: 'plug' }
  ];

  function themeSwitch() {
    var p = window.BHTheme ? window.BHTheme.pref() : 'system';
    var opts = [['light', 'sun', 'روشن'], ['system', 'monitor', 'خودکار'], ['dark', 'moon', 'تیره']];
    return '<div class="theme-switch" role="group" aria-label="تم">' + opts.map(function (o) {
      return '<button type="button" data-theme-set="' + o[0] + '" aria-pressed="' + (p === o[0]) + '" title="' + o[2] + '" aria-label="تم ' + o[2] + '">' +
        BH.icon(o[1]) + '</button>';
    }).join('') + '</div>';
  }
  BH.themeSwitch = themeSwitch;

  function bindTheme(root) {
    BH.$$('[data-theme-set]', root).forEach(function (b) {
      b.addEventListener('click', function () { window.BHTheme.set(b.getAttribute('data-theme-set')); });
    });
    BH.$$('[data-theme-toggle]', root).forEach(function (b) {
      b.addEventListener('click', function () { window.BHTheme.toggle(); });
    });
  }
  function syncTheme() {
    var p = window.BHTheme.pref(), cur = window.BHTheme.current();
    BH.$$('[data-theme-set]').forEach(function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-theme-set') === p)); });
    BH.$$('[data-theme-toggle]').forEach(function (b) {
      b.innerHTML = BH.icon(cur === 'dark' ? 'sun' : 'moon');
      b.setAttribute('aria-label', cur === 'dark' ? 'تم روشن' : 'تم تیره');
    });
  }
  BH.bindTheme = function (root) { bindTheme(root || document); syncTheme(); };
  window.addEventListener('themechange', syncTheme);

  function userChip() {
    var me = null;
    try { me = JSON.parse(sessionStorage.getItem('behoosh_me') || 'null'); } catch (e) {}
    var name = me && me.display_name ? me.display_name : 'حساب من';
    return '<div class="user-chip"><span class="avatar" id="bhAvatar">' + BH.esc(name.charAt(0)) + '</span>' +
      '<div class="who"><b id="bhName">' + BH.esc(name) + '</b><span>' + (BH.token() ? 'وارد شده‌ای' : 'وارد نشده‌ای') + '</span></div>' +
      (BH.token()
        ? '<button class="icon-btn" id="bhOut" type="button" aria-label="خروج از حساب" title="خروج">' + BH.icon('logout') + '</button>'
        : '<a class="icon-btn" href="login.html" aria-label="ورود" title="ورود">' + BH.icon('login') + '</a>') +
      '</div>';
  }

  function loadMe() {
    if (!BH.token()) return;
    try { if (sessionStorage.getItem('behoosh_me')) return; } catch (e) {}
    BH.api('/auth/me').then(function (me) {
      try { sessionStorage.setItem('behoosh_me', JSON.stringify(me)); } catch (e) {}
      var n = document.getElementById('bhName'), a = document.getElementById('bhAvatar');
      if (n && me.display_name) n.textContent = me.display_name;
      if (a && me.display_name) a.textContent = me.display_name.charAt(0);
    }).catch(function () {});
  }

  function boot() {
    var app = document.querySelector('.app');
    if (!app || document.getElementById('bhSidebar')) { BH.bindTheme(); return; }
    var here = (location.pathname.split('/').pop() || 'index.html').toLowerCase();
    var main = app.querySelector('.app-main');
    app.classList.add('has-sidebar');

    var side = document.createElement('aside');
    side.className = 'sidebar'; side.id = 'bhSidebar'; side.setAttribute('aria-label', 'منوی اصلی');
    side.innerHTML =
      '<a class="brand" href="index.html"><span class="brand-mark">ب</span><span>بهوش<small>سلامت و مالی، یک‌جا</small></span></a>' +
      '<nav aria-label="بخش‌ها">' + ITEMS.map(function (it) {
        return '<a class="nav-link" data-k="' + it.k + '" href="' + it.f + '"' + (it.f === here ? ' aria-current="page"' : '') + '>' +
          BH.icon(it.i) + '<span>' + it.t + '</span></a>';
      }).join('') + '</nav>' +
      '<div class="sidebar-foot"><div class="nav-label" style="padding:0 4px">ظاهر</div>' + themeSwitch() + userChip() + '</div>';
    app.insertBefore(side, main);

    var bar = document.createElement('header');
    bar.className = 'mobile-bar';
    bar.innerHTML = '<a class="brand" href="index.html"><span class="brand-mark">ب</span>بهوش</a>' +
      '<div style="display:flex;gap:8px">' +
      '<button class="icon-btn" type="button" data-theme-toggle></button>' +
      (BH.token() ? '<button class="icon-btn" type="button" id="bhOut2" aria-label="خروج">' + BH.icon('logout') + '</button>'
                  : '<a class="icon-btn" href="login.html" aria-label="ورود">' + BH.icon('login') + '</a>') +
      '</div>';
    app.insertBefore(bar, main);

    var bn = document.createElement('nav');
    bn.className = 'bottom-nav'; bn.setAttribute('aria-label', 'بخش‌ها');
    bn.innerHTML = ITEMS.map(function (it) {
      return '<a data-k="' + it.k + '" href="' + it.f + '"' + (it.f === here ? ' aria-current="page"' : '') + '>' + BH.icon(it.i) + '<span>' + it.s + '</span></a>';
    }).join('');
    app.appendChild(bn);

    ['bhOut', 'bhOut2'].forEach(function (id) {
      var b = document.getElementById(id);
      if (b) b.addEventListener('click', function () {
        if (typeof window.logout === 'function') window.logout(); else BH.logout();
      });
    });
    BH.bindTheme();
    loadMe();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
