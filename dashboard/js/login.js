const base = (window.BEHOOSH && window.BEHOOSH.apiBase) || 'https://behoosh-api.hashpa.com/v1';
const msg = document.getElementById('msg');
const go = document.getElementById('go');

function say(text, kind){
  msg.textContent = text;
  msg.className = 'msg ' + (kind || 'err');
}

// اگر قبلا وارد شده، مستقیم برو داشبورد
try {
  if (localStorage.getItem('behoosh_token')) {
    location.replace('dashboard.html');
  }
} catch (e) {}

document.getElementById('f').addEventListener('submit', async function(ev){
  ev.preventDefault();
  const email = document.getElementById('email').value.trim();
  const password = document.getElementById('password').value;
  if (!email || !password) return;

  go.disabled = true;
  go.textContent = 'در حال ورود...';
  msg.className = 'msg';

  try {
    const r = await fetch(base + '/auth/login', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({email: email, password: password})
    });
    const data = await r.json().catch(function(){ return {}; });

    if (!r.ok) {
      say(r.status === 401 ? 'ایمیل یا رمز اشتباه است.' : ('ورود ناموفق بود (کد ' + r.status + ')'));
      go.disabled = false; go.textContent = 'ورود';
      return;
    }
    if (!data.token) {
      say('پاسخ سرور توکن نداشت.');
      go.disabled = false; go.textContent = 'ورود';
      return;
    }

    localStorage.setItem('behoosh_token', data.token);
    try { localStorage.setItem('behoosh_scopes', JSON.stringify(data.scopes || [])); } catch (e) {}
    say('ورود موفق. در حال انتقال...', 'ok');
    location.replace('dashboard.html');
  } catch (e) {
    say('اتصال به سرور برقرار نشد.');
    go.disabled = false; go.textContent = 'ورود';
  }
});
