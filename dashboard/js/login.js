/* صفحه ورود: ایمیل و رمز، توکن در localStorage، بازگشت به صفحه درخواستی. */
(function () {
  'use strict';
  var BH = window.BH;
  var msg = document.getElementById('msg');
  var go = document.getElementById('go');
  var label = go.querySelector('.go-label');

  // فقط نام فایل‌های داخلی مجاز است؛ جلوی تغییر مسیر به سایت دیگر را می‌گیرد.
  function nextPage() {
    var n = new URLSearchParams(location.search).get('next') || '';
    return /^[a-z0-9_-]+\.html$/i.test(n) && n !== 'login.html' ? n : 'dashboard.html';
  }

  try { if (localStorage.getItem('behoosh_token')) { location.replace(nextPage()); return; } } catch (e) {}

  BH.$$('[data-icon]').forEach(function (el) { el.innerHTML = BH.icon(el.getAttribute('data-icon')); });
  // shell.js بعد از این فایل بار می‌شود؛ سوییچ تم را در DOMContentLoaded می‌گذاریم و shell آن را وصل می‌کند.
  document.addEventListener('DOMContentLoaded', function () {
    document.getElementById('themeSlot').innerHTML = BH.themeSwitch ? BH.themeSwitch() : '';
  });

  var pw = document.getElementById('password'), tg = document.getElementById('pwToggle');
  function syncPw() {
    var shown = pw.type === 'text';
    tg.innerHTML = shown
      ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9.9 4.2A10 10 0 0 1 12 4c7 0 10 8 10 8a17 17 0 0 1-2.2 3.3M6.6 6.6A17 17 0 0 0 2 12s3 8 10 8a9.7 9.7 0 0 0 5.4-1.6"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2M2 2l20 20"/></svg>'
      : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 12s3-8 10-8 10 8 10 8-3 8-10 8-10-8-10-8Z"/><circle cx="12" cy="12" r="3"/></svg>';
    tg.setAttribute('aria-pressed', String(shown));
    tg.setAttribute('aria-label', shown ? 'پنهان کردن رمز' : 'نمایش رمز');
  }
  tg.addEventListener('click', function () { pw.type = pw.type === 'password' ? 'text' : 'password'; syncPw(); pw.focus(); });
  syncPw();

  function say(text, kind) {
    msg.hidden = !text;
    msg.className = 'form-alert ' + (kind || 'err');
    msg.innerHTML = text ? BH.icon(kind === 'ok' ? 'check' : 'alert') + '<span>' + BH.esc(text) + '</span>' : '';
  }
  function busy(on) {
    go.disabled = on;
    go.classList.toggle('loading', on);
    label.textContent = on ? 'در حال ورود…' : 'ورود';
  }

  document.getElementById('f').addEventListener('submit', async function (ev) {
    ev.preventDefault();
    var email = document.getElementById('email').value.trim();
    var password = pw.value;
    if (!email || !password) { say('ایمیل و رمز را وارد کن.'); (email ? pw : document.getElementById('email')).focus(); return; }

    busy(true); say('');
    try {
      var r = await fetch(BH.apiBase() + '/auth/login', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email, password: password })
      });
      var data = await r.json().catch(function () { return {}; });
      if (!r.ok) {
        say(r.status === 401 ? 'ایمیل یا رمز اشتباه است.'
          : r.status === 429 ? 'تلاش‌های زیادی انجام شد. چند دقیقه بعد دوباره امتحان کن.'
          : r.status === 422 ? 'ایمیل معتبر نیست.'
          : 'ورود ناموفق بود (کد ' + BH.fa(r.status) + ').');
        busy(false); return;
      }
      if (!data.token) { say('پاسخ سرور توکن نداشت.'); busy(false); return; }
      localStorage.setItem('behoosh_token', data.token);
      try {
        localStorage.setItem('behoosh_scopes', JSON.stringify(data.scopes || []));
        sessionStorage.removeItem('behoosh_me');
      } catch (e) {}
      say('ورود موفق. در حال انتقال…', 'ok');
      location.replace(nextPage());
    } catch (e) {
      say('اتصال به سرور برقرار نشد.');
      busy(false);
    }
  });
})();
