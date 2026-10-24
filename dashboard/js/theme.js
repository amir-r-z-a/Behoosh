/* بهوش — تم روشن/تیره
   در <head> و پیش از رندر اجرا می‌شود تا صفحه با تم اشتباه چشمک نزند.
   ترجیح کاربر: light | dark | system (پیش‌فرض: system، یعنی تابع سیستم‌عامل). */
(function () {
  'use strict';
  var KEY = 'behoosh_theme';
  var mq = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;

  function pref() {
    try { var v = localStorage.getItem(KEY); return v === 'light' || v === 'dark' ? v : 'system'; }
    catch (e) { return 'system'; }
  }
  function resolve(p) { return p === 'system' ? (mq && mq.matches ? 'dark' : 'light') : p; }

  function apply(p) {
    var r = resolve(p), root = document.documentElement;
    var changed = root.getAttribute('data-theme') !== r;
    root.setAttribute('data-theme', r);
    root.setAttribute('data-theme-pref', p);
    var meta = document.querySelector('meta[name="theme-color"]');
    if (!meta) { meta = document.createElement('meta'); meta.name = 'theme-color'; document.head.appendChild(meta); }
    meta.content = r === 'dark' ? '#0A0F1C' : '#F3F5FA';
    if (changed) {
      try { window.dispatchEvent(new CustomEvent('themechange', { detail: { theme: r, pref: p } })); } catch (e) {}
    }
  }

  window.BHTheme = {
    pref: pref,
    current: function () { return resolve(pref()); },
    set: function (p) {
      try { if (p === 'system') localStorage.removeItem(KEY); else localStorage.setItem(KEY, p); } catch (e) {}
      apply(p);
    },
    toggle: function () { this.set(this.current() === 'dark' ? 'light' : 'dark'); }
  };

  apply(pref());
  if (mq) {
    var onChange = function () { if (pref() === 'system') apply('system'); };
    if (mq.addEventListener) mq.addEventListener('change', onChange); else if (mq.addListener) mq.addListener(onChange);
  }
})();
