/* صفحه معرفی: آیکن‌ها، دکمه ورود/ادامه، نمایش آرام هنگام اسکرول. */
(function () {
  'use strict';
  var BH = window.BH;

  BH.$$('[data-icon]').forEach(function (el) { el.innerHTML = BH.icon(el.getAttribute('data-icon')); });

  if (BH.token()) {
    BH.$$('[data-cta]').forEach(function (a) { a.setAttribute('href', 'dashboard.html'); });
    BH.$$('[data-cta-label]').forEach(function (s) { s.textContent = 'ادامه به داشبورد'; });
  }

  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var els = BH.$$('.reveal-up');
  if (reduce || !('IntersectionObserver' in window)) { els.forEach(function (e) { e.classList.add('in'); }); return; }
  document.documentElement.classList.add('js-reveal');
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); } });
  }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
  els.forEach(function (e) { io.observe(e); });
})();
