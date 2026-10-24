const BASE = (window.BEHOOSH && window.BEHOOSH.apiBase) || 'https://behoosh-api.hashpa.com/v1';
const MCP_HEALTH = 'https://behoosh-mcp.hashpa.com/mcp';
const MCP_FINANCE = 'https://behoosh-mcp.hashpa.com/finance/mcp';

let TOKEN = null;
try { TOKEN = localStorage.getItem('behoosh_token'); } catch (e) {}
if (!TOKEN) location.replace('login.html');

function authHeaders(extra){
  const h = Object.assign({'X-API-Key': TOKEN}, extra || {});
  return h;
}

async function api(path, opts){
  opts = opts || {};
  opts.headers = authHeaders(opts.headers);
  const r = await fetch(BASE + path, opts);
  if (r.status === 401 || r.status === 403) {
    try { localStorage.removeItem('behoosh_token'); } catch (e) {}
    location.replace('login.html');
    throw new Error('auth');
  }
  return r;
}

function say(id, text, kind){
  const el = document.getElementById('msg-' + id);
  el.textContent = text;
  el.className = 'msg ' + (kind || 'err');
}
function clearSay(id){
  const el = document.getElementById('msg-' + id);
  el.className = 'msg';
  el.textContent = '';
}

document.getElementById('logout').addEventListener('click', function(){
  try {
    localStorage.removeItem('behoosh_token');
    localStorage.removeItem('behoosh_scopes');
  } catch (e) {}
  location.replace('login.html');
});

// چک‌باکس‌ها ظاهر خاموش/روشن
document.querySelectorAll('.chk input').forEach(function(cb){
  function sync(){ cb.closest('.chk').classList.toggle('off', !cb.checked); }
  cb.addEventListener('change', sync); sync();
});

function buildJson(key, url, token){
  const obj = { mcpServers: {} };
  obj.mcpServers[key] = {
    type: 'http',
    url: url,
    headers: { Authorization: 'Bearer ' + token }
  };
  return JSON.stringify(obj, null, 2);
}

function renderOut(domain, token, scopes){
  const isFin = domain === 'finance';
  const url = isFin ? MCP_FINANCE : MCP_HEALTH;
  const key = isFin ? 'behoosh-finance' : 'behoosh-health';
  const json = buildJson(key, url, token);
  const box = document.getElementById('out-' + domain);

  box.innerHTML =
    '<div class="msg warn">این توکن فقط همین یک بار نشان داده می‌شود. همین حالا کپی کن.</div>' +
    '<div class="lbl"><span>توکن</span><button class="ghost sm" data-copy="tok">کپی</button></div>' +
    '<div class="tokbox" id="tok-' + domain + '">' + token + '</div>' +
    '<div class="lbl"><span>JSON آماده برای ایجنت</span><button class="ghost sm" data-copy="json">کپی JSON</button></div>' +
    '<pre id="json-' + domain + '">' + json.replace(/&/g,'&amp;').replace(/</g,'&lt;') + '</pre>' +
    '<ol class="steps">' +
      '<li>فایل تنظیمات MCP ایجنتت را باز کن (در کلود دسکتاپ: <code>claude_desktop_config.json</code>).</li>' +
      '<li>محتوای بالا را داخلش بگذار. اگر <code>mcpServers</code> از قبل هست، فقط کلید <code>' + key + '</code> را اضافه کن.</li>' +
      '<li>ایجنت را ری‌استارت کن. ابزارها باید بیایند.</li>' +
    '</ol>';

  box.classList.add('show');

  box.querySelectorAll('[data-copy]').forEach(function(btn){
    btn.addEventListener('click', async function(){
      const isTok = btn.getAttribute('data-copy') === 'tok';
      const text = isTok ? token : json;
      try {
        await navigator.clipboard.writeText(text);
        const old = btn.textContent;
        btn.textContent = 'کپی شد';
        setTimeout(function(){ btn.textContent = old; }, 1500);
      } catch (e) {
        const r = document.createRange();
        r.selectNodeContents(document.getElementById((isTok ? 'tok-' : 'json-') + domain));
        const s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
        btn.textContent = 'دستی کپی کن';
      }
    });
  });
}

async function createToken(domain){
  const isFin = domain === 'finance';
  const btn = document.getElementById('go-' + domain);
  clearSay(domain);

  const name = document.getElementById('name-' + domain).value.trim() || (isFin ? 'ایجنت مالی' : 'ایجنت سلامت');
  const scopes = Array.from(
    document.querySelectorAll('#sc-' + domain + ' input:checked')
  ).map(function(c){ return c.value; });

  if (!scopes.length) { say(domain, 'حداقل یک دسترسی انتخاب کن.'); return; }

  btn.disabled = true;
  const old = btn.textContent;
  btn.textContent = 'در حال ساخت...';

  try {
    const r = await api('/auth/tokens', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({name: name, scopes: scopes, kind: 'api'})
    });
    const data = await r.json().catch(function(){ return {}; });

    if (!r.ok) {
      say(domain, 'ساخت توکن نشد (کد ' + r.status + ').');
      return;
    }
    const raw = data.token || data.raw_token || data.key;
    if (!raw) {
      say(domain, 'سرور توکن برنگرداند.');
      return;
    }
    renderOut(domain, raw, scopes);
    say(domain, 'توکن ساخته شد.', 'ok');
    loadTokens();
  } catch (e) {
    if (e.message !== 'auth') say(domain, 'اتصال به سرور برقرار نشد.');
  } finally {
    btn.disabled = false;
    btn.textContent = old;
  }
}

document.getElementById('go-health').addEventListener('click', function(){ createToken('health'); });
document.getElementById('go-finance').addEventListener('click', function(){ createToken('finance'); });

async function loadTokens(){
  const list = document.getElementById('tlist');
  try {
    const r = await api('/auth/tokens');
    const data = await r.json().catch(function(){ return {}; });
    const items = data.tokens || data.items || (Array.isArray(data) ? data : []);

    if (!items.length) {
      list.innerHTML = '<div class="empty">هنوز توکنی نساخته‌ای.</div>';
      return;
    }
    list.innerHTML = items.map(function(t){
      const sc = (t.scopes || []).join('، ') || '—';
      const nm = t.name || 'بدون نام';
      const id = t.id || t.token_id;
      return '<div class="trow">' +
        '<div><div class="nm">' + nm + '</div><div class="sc">' + sc + '</div></div>' +
        '<button class="ghost sm" data-revoke="' + id + '">باطل</button>' +
      '</div>';
    }).join('');

    list.querySelectorAll('[data-revoke]').forEach(function(btn){
      btn.addEventListener('click', async function(){
        if (!confirm('این توکن باطل شود؟')) return;
        btn.disabled = true;
        try {
          const r = await api('/auth/tokens/' + btn.getAttribute('data-revoke'), {method: 'DELETE'});
          if (r.ok || r.status === 204) loadTokens();
          else { btn.disabled = false; alert('باطل نشد (کد ' + r.status + ')'); }
        } catch (e) {
          if (e.message !== 'auth') { btn.disabled = false; alert('اتصال برقرار نشد.'); }
        }
      });
    });
  } catch (e) {
    if (e.message !== 'auth') list.innerHTML = '<div class="empty">لیست توکن‌ها نیامد.</div>';
  }
}

loadTokens();
