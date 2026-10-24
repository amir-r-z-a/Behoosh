/* اتصال به ایجنت: ساخت توکن scope‌دار برای هر حوزه، نمایش یک‌باره توکن و JSON کلاینت MCP،
   فهرست و ابطال توکن‌ها. */
(function () {
  'use strict';
  var BH = window.BH;
  if (!BH.requireAuth()) return;

  var MCP_HEALTH = 'https://behoosh-mcp.hashpa.com/mcp';
  var MCP_FINANCE = 'https://behoosh-mcp.hashpa.com/finance/mcp';

  // ابزارهای جلسه روی همان سرور MCP سلامت ثبت شده‌اند (app/mcp/server.py).
  var DOMAINS = [
    { k: 'health', t: 'سلامت', icon: 'heart', cls: 't-health', name: 'ایجنت سلامت', key: 'behoosh-health', url: MCP_HEALTH,
      desc: 'غذا، خواب، ورزش، بدن، نماز، حال، اسکرین‌تایم و مزاج', tools: 21, read: true, write: true },
    { k: 'finance', t: 'مالی', icon: 'wallet', cls: 't-finance', name: 'ایجنت مالی', key: 'behoosh-finance', url: MCP_FINANCE,
      desc: 'حساب‌ها، تراکنش‌ها، بودجه، وام، دسته‌ها و پیامک بانکی', tools: 20, read: true, write: false },
    { k: 'meeting', t: 'جلسه', icon: 'mic', cls: 't-meeting', name: 'ایجنت جلسه', key: 'behoosh-meeting', url: MCP_HEALTH,
      desc: 'خواندن متن زنده جلسه و ثبت نظر وسط جلسه', tools: 13, read: true, write: true }
  ];
  var SCOPE_FA = { read: 'خواندن', write: 'نوشتن' };
  var DOMAIN_FA = { health: 'سلامت', finance: 'مالی', meeting: 'جلسه' };

  /* ---------- کارت‌های حوزه ---------- */
  function sw(d, s, on) {
    var id = 'sc-' + d.k + '-' + s;
    return '<label class="switch" for="' + id + '"><input type="checkbox" id="' + id + '" value="' + d.k + ':' + s + '"' + (on ? ' checked' : '') + '>' +
      '<span class="track" aria-hidden="true"><i></i></span><span class="sw-txt"><b>' + SCOPE_FA[s] + '</b><small>' +
      (s === 'read' ? 'گزارش و پرس‌وجو' : 'ثبت و ویرایش داده') + '</small></span></label>';
  }
  document.getElementById('domains').innerHTML = DOMAINS.map(function (d) {
    return '<section class="card domain ' + d.cls + '" aria-labelledby="h-' + d.k + '">' +
      '<div class="domain-top"><span class="kpi-icon">' + BH.icon(d.icon) + '</span>' +
      '<span class="badge">' + BH.n(d.tools) + ' ابزار</span></div>' +
      '<h3 id="h-' + d.k + '">حوزه ' + d.t + '</h3><p class="domain-desc">' + d.desc + '</p>' +
      '<div class="field"><label for="name-' + d.k + '">نام توکن</label>' +
      '<input class="input" id="name-' + d.k + '" type="text" value="' + d.name + '" dir="auto" maxlength="120"></div>' +
      '<fieldset class="scopes"><legend class="label">دسترسی</legend>' + sw(d, 'read', d.read) + sw(d, 'write', d.write) + '</fieldset>' +
      '<div class="domain-msg" id="msg-' + d.k + '" role="alert"></div>' +
      '<button class="btn btn-soft domain-go" type="button" id="go-' + d.k + '">' + BH.icon('key') + '<span>ساخت توکن ' + d.t + '</span></button>' +
      '</section>';
  }).join('');

  function say(k, text) {
    var el = document.getElementById('msg-' + k);
    el.innerHTML = text ? BH.icon('alert') + '<span>' + BH.esc(text) + '</span>' : '';
  }

  /* ---------- نمایش یک‌باره توکن ---------- */
  var reveal = document.getElementById('reveal');
  var current = { token: '', json: '' };
  document.getElementById('reveal-close').innerHTML = BH.icon('x');
  document.getElementById('reveal-warn').innerHTML = BH.icon('alert') +
    '<span>این توکن <b>فقط همین یک بار</b> نشان داده می‌شود. همین حالا کپی کن و جای امن نگه دار.</span>';
  BH.$$('[data-copy]', reveal).forEach(function (b) { b.innerHTML = BH.icon('copy') + '<span>کپی</span>'; });
  document.getElementById('reveal-close').addEventListener('click', function () {
    reveal.hidden = true; current = { token: '', json: '' };
    document.getElementById('reveal-token').textContent = '';
    document.getElementById('reveal-json').textContent = '';
  });

  function buildJson(key, url, token) {
    var obj = { mcpServers: {} };
    obj.mcpServers[key] = { type: 'http', url: url, headers: { Authorization: 'Bearer ' + token } };
    return JSON.stringify(obj, null, 2);
  }
  function showReveal(d, token, scopes, name) {
    current.token = token;
    current.json = buildJson(d.key, d.url, token);
    reveal.className = 'card reveal ' + d.cls;
    document.getElementById('reveal-title').textContent = 'توکن «' + name + '» ساخته شد';
    document.getElementById('reveal-sub').textContent = 'حوزه ' + d.t + ' — ' + scopes.map(function (s) { return SCOPE_FA[s.split(':')[1]]; }).join(' و ');
    document.getElementById('reveal-token').textContent = token;
    document.getElementById('reveal-json').textContent = current.json;
    document.getElementById('reveal-hint').innerHTML = 'اگر <code class="ltr">mcpServers</code> از قبل در فایل تنظیمات هست، فقط کلید <code class="ltr">' +
      d.key + '</code> را به آن اضافه کن و ایجنت را دوباره راه بینداز.';
    reveal.hidden = false;
    reveal.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  async function copyText(text, btn) {
    try { await navigator.clipboard.writeText(text); BH.toast('کپی شد'); }
    catch (e) {
      var r = document.createRange(); r.selectNodeContents(btn.closest('.field').querySelector('.secret,.code'));
      var s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
      BH.toast('انتخاب شد؛ دستی کپی کن', 'info');
    }
  }
  BH.$$('[data-copy]', reveal).forEach(function (b) {
    b.addEventListener('click', function () { copyText(b.getAttribute('data-copy') === 'tok' ? current.token : current.json, b); });
  });

  /* ---------- ساخت توکن ---------- */
  async function createToken(d) {
    var btn = document.getElementById('go-' + d.k);
    say(d.k, '');
    var name = document.getElementById('name-' + d.k).value.trim() || d.name;
    var scopes = BH.$$('#domains .domain.' + d.cls + ' input[type=checkbox]:checked').map(function (c) { return c.value; });
    if (!scopes.length) { say(d.k, 'حداقل یک دسترسی انتخاب کن.'); return; }
    btn.disabled = true;
    var lbl = btn.querySelector('span'), old = lbl.textContent;
    lbl.textContent = 'در حال ساخت…';
    try {
      var data = await BH.api('/auth/tokens', { body: { name: name, scopes: scopes, kind: 'api' } });
      var raw = data && (data.token || data.raw_token || data.key);
      if (!raw) { say(d.k, 'سرور توکن برنگرداند.'); return; }
      showReveal(d, raw, scopes, name);
      BH.toast('توکن ساخته شد');
      loadTokens();
    } catch (e) {
      if (e.message === 'auth') return;
      say(d.k, e.status === 403 ? 'این دسترسی را نداری که به توکن بدهی.' : e.status ? 'ساخت توکن نشد (کد ' + BH.fa(e.status) + ').' : 'اتصال به سرور برقرار نشد.');
    } finally {
      btn.disabled = false; lbl.textContent = old;
    }
  }
  DOMAINS.forEach(function (d) {
    document.getElementById('go-' + d.k).addEventListener('click', function () { createToken(d); });
  });

  /* ---------- فهرست و ابطال ---------- */
  function scopeChips(scopes) {
    var by = {};
    (scopes || []).forEach(function (s) { var p = s.split(':'); (by[p[0]] = by[p[0]] || []).push(SCOPE_FA[p[1]] || p[1]); });
    var ks = Object.keys(by);
    if (!ks.length) return '<span class="muted">—</span>';
    return ks.map(function (k) {
      var cls = k === 'health' ? 't-health' : k === 'finance' ? 't-finance' : k === 'meeting' ? 't-meeting' : '';
      return '<span class="scope-chip ' + cls + '"><i class="dot"></i>' + (DOMAIN_FA[k] || k) + ': ' + by[k].join('، ') + '</span>';
    }).join('');
  }
  function ago(iso) {
    if (!iso) return 'هرگز';
    var d = new Date(iso), diff = (Date.now() - d.getTime()) / 1000;
    if (diff < 90) return 'همین حالا';
    if (diff < 3600) return BH.n(Math.round(diff / 60)) + ' دقیقه پیش';
    if (diff < 86400) return BH.n(Math.round(diff / 3600)) + ' ساعت پیش';
    if (diff < 86400 * 7) return BH.n(Math.round(diff / 86400)) + ' روز پیش';
    return BH.date(iso, 'short');
  }

  var dlg = document.getElementById('confirm');
  function confirmRevoke(name, isSession) {
    document.getElementById('confirm-text').textContent = 'توکن «' + name + '» برای همیشه باطل می‌شود و هر ایجنت یا مرورگری که از آن استفاده می‌کند قطع می‌شود.' +
      (isSession ? ' اگر این نشست همین مرورگر باشد، از حساب خارج می‌شوی.' : '');
    if (!dlg.showModal) return Promise.resolve(window.confirm(document.getElementById('confirm-text').textContent));
    return new Promise(function (res) {
      dlg.returnValue = '';
      dlg.addEventListener('close', function h() { dlg.removeEventListener('close', h); res(dlg.returnValue === 'ok'); });
      dlg.showModal();
    });
  }

  async function loadTokens() {
    var list = document.getElementById('tlist');
    try {
      var data = await BH.api('/auth/tokens');
      var items = data.tokens || data.items || (Array.isArray(data) ? data : []);
      document.getElementById('tok-count').textContent = items.length ? BH.n(items.length) + ' توکن فعال' : '';
      if (!items.length) { list.innerHTML = BH.empty('هنوز توکنی نساخته‌ای.', 'key'); return; }
      list.innerHTML = '<div class="tok-head" aria-hidden="true"><span>نام</span><span>دسترسی</span><span>ساخته‌شده</span><span>آخرین استفاده</span><span></span></div>' +
        items.map(function (t) {
          var session = t.kind === 'session';
          var id = t.id || t.token_id;
          return '<div class="tok-row">' +
            '<div class="tok-name"><span class="ico ' + (session ? 't-info' : 't-agent') + '">' + BH.icon(session ? 'monitor' : 'key') + '</span>' +
              '<div><b>' + BH.esc(t.name || (session ? 'ورود' : 'بدون نام')) + '</b>' +
              '<span class="badge ' + (session ? 'info' : 'warn') + '">' + (session ? 'نشست مرورگر' : 'ایجنت') + '</span></div></div>' +
            '<div class="tok-scopes">' + scopeChips(t.scopes) + '</div>' +
            '<div class="tok-meta"><span class="m-lbl">ساخته‌شده</span>' + BH.date(t.created_at, 'short') + '</div>' +
            '<div class="tok-meta"><span class="m-lbl">آخرین استفاده</span>' + ago(t.last_used_at) + '</div>' +
            '<div class="tok-act"><button class="btn btn-ghost btn-sm" type="button" data-revoke="' + BH.esc(id) + '" data-name="' + BH.esc(t.name || '') +
              '" data-session="' + session + '">' + BH.icon('x') + '<span>ابطال</span></button></div>' +
            '</div>';
        }).join('');
      BH.$$('[data-revoke]', list).forEach(function (btn) {
        btn.addEventListener('click', async function () {
          var ok = await confirmRevoke(btn.getAttribute('data-name') || 'بدون نام', btn.getAttribute('data-session') === 'true');
          if (!ok) return;
          btn.disabled = true;
          try {
            await BH.api('/auth/tokens/' + btn.getAttribute('data-revoke'), { method: 'DELETE' });
            BH.toast('توکن باطل شد');
            loadTokens();
          } catch (e) {
            if (e.message !== 'auth') { btn.disabled = false; BH.toast('ابطال نشد', 'alert'); }
          }
        });
      });
    } catch (e) {
      if (e.message !== 'auth') list.innerHTML = BH.empty('فهرست توکن‌ها نیامد.', 'alert');
    }
  }
  loadTokens();
})();
