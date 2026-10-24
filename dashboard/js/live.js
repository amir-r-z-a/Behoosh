const API = (window.BEHOOSH && window.BEHOOSH.apiBase) || 'https://behoosh-api.hashpa.com/v1';
const $ = id => document.getElementById(id);
const fa = n => String(n).replace(/\d/g, d => '۰۱۲۳۴۵۶۷۸۹'[d]);

let token = localStorage.getItem('behoosh_token');
let sessionId = null, seq = 0, recording = false;
let recorder = null, stream = null, audioCtx = null, analyser = null, rafId = null;
let buf = null, levelData = null;
let chunkStart = 0, silenceSince = null, lastVoiceAt = 0;
let sessionStart = 0, chunkHadVoice = false, skippedChunks = 0;
let totalWords = 0, pendingWords = 0, sentCount = 0, sentWords = 0, replyCount = 0;
let silenceThreshold = 6, chunkMax = 20;   // ثانیه
let cutting = false;

if (!token) { $('noToken').classList.remove('hide'); $('btnStart').disabled = true; }

function log(cls, head, text) {
  const box = $('log');
  if (box.querySelector('.hint')) box.innerHTML = '';
  const d = document.createElement('div');
  d.className = 'line ' + (cls || '');
  const t = new Date().toLocaleTimeString('fa-IR');
  d.innerHTML = '<div class="t"><span>' + t + '</span><span>' + head + '</span></div>' +
                '<div>' + (text || '').replace(/</g, '&lt;') + '</div>';
  box.appendChild(d);
  box.scrollTop = box.scrollHeight;
}

// پاسخ ایجنت کارت جداگانه دارد. متن خودم یک لاگ است که می آید و می رود،
// ولی پاسخ ایجنت مهم است و باید بماند و دیده شود.
function logReply(head, text, cls) {
  const box = $('replies');
  if (!box) return;
  if (box.querySelector('.hint')) box.innerHTML = '';
  const d = document.createElement('div');
  d.className = 'line ' + (cls || '');
  const t = new Date().toLocaleTimeString('fa-IR');
  d.innerHTML = '<div class="t"><span>' + t + '</span><span>' + (head || '') + '</span></div>' +
                '<div>' + String(text || '').replace(/</g, '&lt;') + '</div>';
  box.appendChild(d);
  box.scrollTop = box.scrollHeight;
  replyCount++;
  const pill = $('replyPill');
  if (pill) pill.textContent = fa(replyCount) + ' پاسخ';
  layoutGrid();
  rmKeep();
}

function flushErr(j) {
  // پیام کلی «ارسال نشد» خطای واقعی را پنهان می‌کرد و کاربر نمی‌فهمید
  // کدام ایجنت و چرا شکست خورد. حالا خطای هر ایجنت جدا نشان داده می‌شود.
  const parts = [];
  if (j.reason) parts.push(j.reason);
  (j.recipients || []).forEach(function (x) {
    if (x.error) parts.push('«' + (x.agent_name || 'ایجنت') + '»: ' + String(x.error));
  });
  if (parts.length < 2 && j.error) parts.push(String(j.error));
  if (!parts.length) parts.push(JSON.stringify(j));
  return parts.join(' | ');
}

// پیل وضعیت از صفحه برداشته شد. وضعیت از رنگ و متن راهنمای دایره خوانده
// می شود. این تابع نگه داشته شده چون منطق ضبط و پایان به آن تکیه دارد.
function setState(txt, cls) {
  const p = $('statePill');
  if (p) { p.textContent = txt; p.className = 'pill ' + (cls || ''); }
  lastState = txt;
}
let lastState = '';

function refreshStats() {
  $('sWords').textContent = fa(totalWords);
  $('sPending').textContent = fa(pendingWords);
  $('sSent').textContent = fa(sentCount);
  const th = parseInt($('thWords').value || '400', 10);
  const pct = Math.min(100, Math.round(pendingWords / th * 100));
  $('bar').style.width = pct + '%';
  $('barHint').textContent = 'پیشرفت تا آستانه ارسال: ' + fa(pct) + '٪';
}

// ---------- فرم راه اندازی ----------
// صفحه اول عمدا خلوت است: فقط دایره ضبط. عنوان، ایجنت و تنظیمات داخل
// همین فرم می آیند تا کاربر پیش از شروع، صفحه شلوغ نبیند.
function openSetup() {
  if (!token) return;
  var e = $('setupErr'); if (e) e.classList.add('hide');
  var d = $('setupDlg');
  d.classList.add('on'); d.setAttribute('aria-hidden', 'false');
  document.body.style.overflow = 'hidden';
  setTimeout(function () { var t = $('title'); if (t) t.focus(); }, 60);
}
function closeSetup() {
  var d = $('setupDlg');
  if (!d) return;
  d.classList.remove('on'); d.setAttribute('aria-hidden', 'true');
  document.body.style.overflow = '';
}
function setupErr(msg) {
  var e = $('setupErr');
  if (!e) return;
  e.textContent = msg; e.classList.remove('hide');
  e.scrollIntoView({ block: 'nearest' });
}

// دایره ضبط دیگر مستقیم شروع نمی کند، فرم را باز می کند.
$('btnStart').onclick = function () { openSetup(); };
if ($('btnSetupCancel')) $('btnSetupCancel').onclick = closeSetup;
if ($('setupDlg')) $('setupDlg').onclick = function (e) { if (e.target === $('setupDlg')) closeSetup(); };

// ---------- شروع واقعی ضبط ----------
$('btnGo').onclick = async () => {
  if (!token) return;
  $('btnGo').disabled = true;
  try {
    const r = await fetch(API + '/live/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-API-Key': token },
      body: JSON.stringify({
        title: $('title').value || null,
        word_threshold: parseInt($('thWords').value || '400', 10),
        time_threshold_s: parseInt($('thTime').value || '90', 10),
        silence_threshold_s: parseInt($('thSilence').value || '6', 10),
        min_words_to_send: parseInt($('thMin').value || '60', 10),
        agent_ids: pickedAgents()
      })
    });
    if (r.status === 401 || r.status === 403) {
      setupErr('توکن معتبر نیست یا دسترسی جلسه ندارد. از صفحه اتصال توکن تازه بساز.');
      $('btnGo').disabled = false; return;
    }
    const j = await r.json();
    if (!j.ok) { setupErr('ساخت جلسه نشد: ' + JSON.stringify(j)); $('btnGo').disabled = false; return; }
    sessionId = j.session_id;
    silenceThreshold = parseInt($('thSilence').value || '6', 10);
    sessionStart = Date.now(); skippedChunks = 0;
    seq = 0; totalWords = 0; pendingWords = 0; sentCount = 0; sentWords = 0;
    replyCount = 0; refreshStats();
    $('log').innerHTML = '';
    if ($('replies')) $('replies').innerHTML = '<div class="hint">هنوز پاسخی نیامده. وقتی ایجنت جواب بدهد اینجا می آید.</div>';
    if ($('replyPill')) $('replyPill').textContent = '۰ پاسخ';
    log('', 'نشست ساخته شد', 'شناسه: ' + sessionId + (j.agent_attached ? ' — ایجنت وصل است' : ' — بدون ایجنت'));
    await startMic();
    startArchive();
    closeSetup();
    recording = true;
    setState('در حال ضبط', 'rec');
    // فرم وضعیت و متن زنده تا شروع ضبط پنهان اند. با شروع ضبط باز می شوند
    // تا کاربر پیش از ضبط صفحه شلوغ نبیند و بعد از شروع، همه چیز را ببیند.
    showLiveCards();
    rmOpen();
    $('btnStop').disabled = false; $('btnAsk').disabled = false;
    if ($('btnTest')) $('btnTest').disabled = false;
    if (j.start_note) {
      if (j.start_note.ok) {
        log('sent', 'پیام شروع جلسه', 'به ' + fa(j.start_note.sent_count || 0) + ' ایجنت فرستاده شد');
      } else {
        log('err', 'پیام شروع نرفت', flushErr(j.start_note));
      }
    }
    startChunk();
  } catch (e) {
    // اگر فرم بسته شده بود (خطای بعد از ساخت نشست) دوباره بازش کن تا
    // پیام خطا دیده شود. خطای میکروفون رایج ترین مورد است.
    if ($('setupDlg') && !$('setupDlg').classList.contains('on')) openSetup();
    setupErr('شروع ضبط نشد: ' + String(e));
    $('btnGo').disabled = false;
  }
};

async function startMic() {
  stream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
  });
  audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  const src = audioCtx.createMediaStreamSource(stream);
  analyser = audioCtx.createAnalyser();
  analyser.fftSize = 1024;
  src.connect(analyser);
  levelData = new Uint8Array(analyser.fftSize);
  watchLevel();
}

// ---------- تشخیص سکوت سمت مرورگر ----------
function watchLevel() {
  if (!analyser) return;
  analyser.getByteTimeDomainData(levelData);
  let sum = 0;
  for (let i = 0; i < levelData.length; i++) {
    const v = (levelData[i] - 128) / 128;
    sum += v * v;
  }
  const rms = Math.sqrt(sum / levelData.length);
  $('lvl').style.width = Math.min(100, Math.round(rms * 400)) + '%';

  const now = Date.now();
  if (rms > 0.02) { lastVoiceAt = now; silenceSince = null; chunkHadVoice = true; }
  else if (silenceSince === null) { silenceSince = now; }

  // سکوت طولانی: تکه را ببند. ولی فقط اگر در این تکه صدایی بوده باشد.
  if (recording && !cutting && silenceSince && lastVoiceAt > chunkStart &&
      (now - silenceSince) / 1000 >= silenceThreshold) {
    log('sil', 'سکوت', 'سکوت ' + fa(silenceThreshold) + ' ثانیه‌ای، تکه بسته شد');
    cutChunk(true);
  }
  rafId = requestAnimationFrame(watchLevel);
}

// ---------- پاسخ ایجنت ----------
// ارسال غیرهمگام است. پس پاسخ را چند بار می‌پرسیم تا برسد.
async function pollReply(segId, tries) {
  tries = tries || 8;
  const seen = new Set();
  for (let i = 0; i < tries; i++) {
    await new Promise(r => setTimeout(r, 5000));
    if (!recording && i > 2) return;
    try {
      // پاسخ ایجنت در کانال AMP می‌ماند، پس اول آن را می‌کشیم سمت خودمان
      const r = await fetch(API + '/live/sessions/' + sessionId + '/sync-replies',
        { method: 'POST', headers: { 'X-API-Key': token } });
      const j = await r.json();
      for (const x of (j.replies || [])) {
        if (seen.has(x.segment_id)) continue;
        seen.add(x.segment_id);
        const t = x.reply || '';
        logReply('«' + (x.agent_name || 'ایجنت') + '»',
                 t.length > 900 ? t.slice(0, 900) + '…' : t);
      }
      const mine = (j.replies || []).find(x => x.segment_id === segId);
      if (mine && mine.reply) return;
    } catch (e) { return; }
  }
}

// ---------- تکه‌ها ----------
// نکته مهم: هر تکه یک ریکوردر مستقل دارد. تکه‌های timeslice در WebM
// مستقل قابل رمزگشایی نیستند و سرویس صوت آن‌ها را نمی‌فهمد.
function startChunk() {
  if (!recording) return;
  cutting = false;
  chunkStart = Date.now();
  chunkHadVoice = false;
  const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
    ? 'audio/webm;codecs=opus' : 'audio/webm';
  const parts = [];
  recorder = new MediaRecorder(stream, { mimeType: mime, audioBitsPerSecond: 32000 });
  recorder.ondataavailable = e => { if (e.data && e.data.size) parts.push(e.data); };
  recorder.onstop = () => {
    const blob = new Blob(parts, { type: mime });
    const stoppedAt = Date.now();
    const dur = (stoppedAt - chunkStart) / 1000;
    // زمان و وضعیت را همین لحظه قفل می کنیم. اگر بعد از آپلود بخوانیم،
    // متغیرهای سراسری عوض شده اند و بازه اشتباه ثبت می شود.
    const startS = Math.max(0, (chunkStart - sessionStart) / 1000);
    const hadVoice = chunkHadVoice;
    const wasSilence = !!recorder._silence;
    // تکه بعدی فورا شروع می شود، پیش از آپلود. قبلا ضبط تا پایان آپلود
    // خواب می رفت و صدای آن فاصله کامل گم می شد. این ریشه گم شدن متن بود.
    if (recording) startChunk();
    if (hadVoice && blob.size > 1500) {
      uploadChunk(blob, dur, startS, wasSilence);   // بدون await: پس زمینه
    } else if (blob.size > 1500) {
      skippedChunks++;
      log('', 'تکه بی‌صدا', 'آپلود نشد. تا الان ' + fa(skippedChunks) + ' تکه بی‌صدا رد شد.');
    }
  };
  recorder.start();
  setTimeout(() => { if (recording && !cutting) cutChunk(false); }, chunkMax * 1000);
}

function cutChunk(bySilence) {
  if (!recorder || cutting || recorder.state === 'inactive') return;
  cutting = true;
  recorder._silence = !!bySilence;
  recorder.stop();
}

async function uploadChunk(blob, dur, startS, wasSilence) {
  const mySeq = seq++;
  // زمان نسبت به شروع جلسه، نه نسبت به شروع همین تکه.
  // قبلا این عدد همیشه صفر می‌شد چون Date.now() منهای chunkStart تقریبا خود dur بود.
  const fd = new FormData();
  fd.append('seq', String(mySeq));
  fd.append('start_s', String(Math.max(0, startS)));
  fd.append('end_s', String(Math.max(0, startS + dur)));
  fd.append('silence', String(!!wasSilence));
  fd.append('file', blob, 'chunk_' + mySeq + '.webm');

  $('chunkPill').textContent = fa(seq) + ' تکه';
  try {
    const r = await fetch(API + '/live/sessions/' + sessionId + '/chunk', {
      method: 'POST', headers: { 'X-API-Key': token }, body: fd
    });
    const j = await r.json();
    if (!r.ok) {
      // ۴۰۹ یعنی جلسه همین لحظه تمام شده و این تکه معلق بعد از پایان رسیده.
      // این خطای کاربر نیست، پس بی صدا رد می شود تا متن زنده را شلوغ نکند.
      if (r.status === 409) return;
      log('err', 'تکه ' + fa(mySeq), j.detail || JSON.stringify(j));
      return;
    }
    if (j.duplicate) return;
    totalWords = j.session_words || totalWords;
    if (j.text) log('', 'تکه ' + fa(mySeq) + ' — ' + fa(j.words) + ' کلمه', j.text);
    else log('', 'تکه ' + fa(mySeq), 'صدایی تشخیص داده نشد');
    if (j.trigger) {
      const map = { words: 'آستانه کلمه', time: 'آستانه زمان', silence: 'سکوت', manual: 'دستی' };
      if (j.sent && j.sent.ok) {
        sentCount++;
        sentWords = j.session_words;   // تا این لحظه همه‌چیز فرستاده شده
        log('sent', 'ارسال به ایجنت — ' + (map[j.trigger] || j.trigger),
            fa(j.sent.words) + ' کلمه فرستاده شد');
        if (j.sent.segment_id) pollReply(j.sent.segment_id);
      } else {
        log('err', 'ارسال نشد', (j.sent && (j.sent.error || j.sent.reason)) || 'خطای نامشخص');
      }
    }
    pendingWords = Math.max(0, totalWords - sentWords);
    refreshStats();
  } catch (e) {
    log('err', 'تکه ' + fa(mySeq), 'خطای شبکه: ' + String(e));
  }
}

// ---------- دکمه‌ها ----------
function showLiveCards() {
  ['statsCard', 'replyCard', 'logCard'].forEach(function (id) {
    var el = $(id);
    if (el) el.classList.remove('hide');
  });
  layoutGrid();
}

// دو ستونه شدن مشروط. ستون راست تا وقتی محتوایی ندارد نمایش داده نمی شود،
// وگرنه کاربر در حالت آماده نیم صفحه خالی می بیند. کلاس .two فقط وقتی
// ستون راست واقعا چیزی برای نشان دادن دارد فعال می شود.
function layoutGrid() {
  var g = $('grid'), right = document.querySelectorAll('.col')[1];
  if (!g || !right) return;
  var has = false;
  Array.prototype.forEach.call(right.children, function (c) {
    if (c.classList.contains('hide')) return;
    if (c.offsetHeight > 8) has = true;
  });
  g.classList.toggle('two', has);
  // راهنمای «الان نظر بده» فقط تا وقتی پاسخی نیامده معنی دارد
  var nx = $('replyNext');
  if (nx) nx.classList.toggle('hide', replyCount > 0);
}

$('btnTest').onclick = async () => {
  if (!sessionId) return;
  $('btnTest').disabled = true;
  try {
    const r = await fetch(API + '/live/sessions/' + sessionId + '/test',
      { method: 'POST', headers: { 'X-API-Key': token } });
    const j = await r.json();
    if (j.ok) {
      log('sent', 'آزمون سریع', 'به ' + fa(j.sent_count || 0) + ' ایجنت رفت. پاسخش در متن زنده می آید.');
      (j.recipients || []).forEach(function (x) {
        if (x.segment_id) pollReply(x.segment_id);
      });
    } else {
      log('err', 'آزمون ناموفق', flushErr(j));
    }
  } catch (e) { log('err', 'خطای آزمون', String(e)); }
  $('btnTest').disabled = false;
};

$('btnAsk').onclick = async () => {
  if (!sessionId) return;
  $('btnAsk').disabled = true;
  try {
    const r = await fetch(API + '/live/sessions/' + sessionId + '/flush',
      { method: 'POST', headers: { 'X-API-Key': token } });
    const j = await r.json();
    if (j.ok) { sentCount++; pendingWords = 0; refreshStats();
      log('sent', 'ارسال دستی', fa(j.words) + ' کلمه به ایجنت رفت'); }
    else log('err', 'ارسال نشد', flushErr(j));
  } catch (e) { log('err', 'خطا', String(e)); }
  $('btnAsk').disabled = false;
};

$('btnStop').onclick = async () => {
  recording = false;
  $('btnStop').disabled = true; $('btnAsk').disabled = true;
  if ($('btnTest')) $('btnTest').disabled = true;
  if (rafId) cancelAnimationFrame(rafId);
  if (recorder && recorder.state !== 'inactive') { cutting = true; recorder.stop(); }
  stopArchive();
  setState('پایان یافته', 'ok');
  rmClose();
  try {
    const r = await fetch(API + '/live/sessions/' + sessionId + '/stop',
      { method: 'POST', headers: { 'X-API-Key': token } });
    const j = await r.json();
    log('', 'پایان جلسه', 'جمع کل: ' + fa(j.total_words) + ' کلمه');
  } catch (e) { log('err', 'خطا در پایان', String(e)); }
  $('btnStart').disabled = false; $('btnGo').disabled = false;
  rmClose();
};
// ================= دفترچه ایجنت =================
// توکن یک بار ثبت می‌شود و می‌ماند. در هر جلسه فقط انتخاب می‌کنیم چه کسی
// مشارکت کند. این کار دو فایده دارد: توکن در هر جلسه دوباره تایپ نمی‌شود،
// و می‌شود چند ایجنت را همزمان در یک جلسه داشت.
let agentBook = [];            // فهرست کامل دفترچه
let agentPicked = new Set();   // شناسه‌های انتخاب‌شده برای این جلسه

function api(path, opt) {
  opt = opt || {};
  opt.headers = Object.assign({ 'X-API-Key': token }, opt.headers || {});
  if (opt.body && typeof opt.body !== 'string') {
    opt.headers['Content-Type'] = 'application/json';
    opt.body = JSON.stringify(opt.body);
  }
  return fetch(API + path, opt);
}

function pickedAgents() { return Array.from(agentPicked); }

function paintAgentCount() {
  const n = agentPicked.size;
  const el = $('agentCount');
  if (el) {
    el.textContent = n ? fa(n) + ' انتخاب' : '۰ انتخاب';
    el.className = 'pill' + (n ? ' ok' : '');
  }
  const sa = $('sAgents');
  if (sa) sa.textContent = fa(n);
}

function renderAgentBook() {
  const box = $('agentBook');
  if (!box) return;
  if (!agentBook.length) {
    // وضعیت خالی: صفحه خالی نگذار، راهنمای گام بعد بده.
    box.innerHTML = '<div class="ab-empty">هنوز ایجنتی ثبت نشده. با دکمه زیر اولی را اضافه کن. ' +
                    'اگر ایجنت نداشته باشی، جلسه فقط رونویسی می‌شود.</div>';
    paintAgentCount();
    return;
  }
  box.innerHTML = '';
  agentBook.forEach(function (a) {
    const on = agentPicked.has(a.agent_id);
    const chip = document.createElement('span');
    chip.className = 'ab-chip' + (on ? ' on' : '');
    chip.setAttribute('role', 'button');
    chip.setAttribute('tabindex', '0');
    chip.setAttribute('aria-pressed', on ? 'true' : 'false');

    const dot = document.createElement('span');
    dot.className = 'st ' + (a.token_ok ? 'ok' : (a.last_error ? 'bad' : ''));
    dot.title = a.token_ok ? 'توکن سالم است' : (a.last_error ? 'توکن مشکل دارد، برای آزمون بزن' : 'هنوز آزمون نشده');
    chip.appendChild(dot);

    const nm = document.createElement('span');
    nm.textContent = a.name;
    chip.appendChild(nm);

    const hint = document.createElement('span');
    hint.className = 'hint2';
    hint.textContent = a.token_hint || '';
    chip.appendChild(hint);

    const x = document.createElement('button');
    x.type = 'button'; x.className = 'x'; x.textContent = '×';
    x.title = 'حذف از دفترچه';
    x.onclick = function (e) { e.stopPropagation(); archiveAgent(a); };
    chip.appendChild(x);

    function toggle() {
      if (agentPicked.has(a.agent_id)) agentPicked.delete(a.agent_id);
      else agentPicked.add(a.agent_id);
      renderAgentBook();
      if (sessionId && recording) syncSessionAgents();
    }
    chip.onclick = toggle;
    chip.onkeydown = function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); }
    };
    dot.onclick = function (e) { e.stopPropagation(); testAgent(a); };
    box.appendChild(chip);
  });
  paintAgentCount();
}

async function loadAgents() {
  if (!token) return;
  const box = $('agentBook');
  if (box) box.innerHTML = '<div class="ab-empty">در حال خواندن دفترچه…</div>';
  try {
    const r = await api('/live/agents');
    const j = await r.json();
    agentBook = j.agents || [];
    // شناسه‌های حذف‌شده از دفترچه را از انتخاب بیرون بیاور
    const live = new Set(agentBook.map(function (a) { return a.agent_id; }));
    Array.from(agentPicked).forEach(function (id) { if (!live.has(id)) agentPicked.delete(id); });
    renderAgentBook();
  } catch (e) {
    if (box) box.innerHTML = '<div class="ab-empty">دفترچه خوانده نشد. اتصال را بررسی کن.</div>';
  }
}

async function testAgent(a) {
  try {
    const r = await api('/live/agents/' + a.agent_id + '/test', { method: 'POST' });
    const j = await r.json();
    a.token_ok = !!j.ok;
    a.last_error = j.error || null;
    renderAgentBook();
    log(j.ok ? 'sent' : 'err', j.ok ? 'توکن سالم است' : 'توکن مشکل دارد',
        j.ok ? ('ایجنت «' + a.name + '» پاسخ داد.') : ('«' + a.name + '»: ' + (j.error || 'خطای نامعلوم')));
  } catch (e) { log('err', 'خطا در آزمون توکن', String(e)); }
}

async function archiveAgent(a) {
  if (!confirm('«' + a.name + '» از دفترچه حذف شود؟ تاریخچه جلسات پاک نمی‌شود.')) return;
  try {
    await api('/live/agents/' + a.agent_id, { method: 'DELETE' });
    agentPicked.delete(a.agent_id);
    await loadAgents();
    log('', 'حذف از دفترچه', '«' + a.name + '» بایگانی شد.');
  } catch (e) { log('err', 'خطا در حذف', String(e)); }
}

// افزودن ایجنت وسط جلسه: کسی که دیر پیوسته کل متن جلسه را یک بار می‌گیرد.
async function syncSessionAgents() {
  if (!sessionId) return;
  const ids = pickedAgents();
  try {
    const r = await api('/live/sessions/' + sessionId + '/agents', { method: 'POST', body: { agent_ids: ids } });
    if (r.ok) {
      const j = await r.json();
      if (j.added_count) {
        j.added.forEach(function (x) { log('sent', 'ایجنت پیوست', x.name + ' به جلسه اضافه شد.'); });
      }
    }
  } catch (e) { /* وسط ضبط، خطای اتصال را پرصدا نمی‌کنیم */ }
}

function openAgentDlg() {
  $('adErr').classList.add('hide');
  $('adName').value = ''; $('adToken').value = '';
  $('agentDlg').classList.add('on');
  $('agentDlg').setAttribute('aria-hidden', 'false');
  setTimeout(function () { $('adName').focus(); }, 60);
}
function closeAgentDlg() {
  $('agentDlg').classList.remove('on');
  $('agentDlg').setAttribute('aria-hidden', 'true');
}
function adErr(msg) {
  const e = $('adErr');
  e.textContent = msg; e.classList.remove('hide');
}

async function saveAgent() {
  const name = ($('adName').value || '').trim();
  const tok = ($('adToken').value || '').trim();
  if (!name) return adErr('نام ایجنت را بنویس.');
  if (!tok) return adErr('توکن ایجنت را بگذار.');
  if (tok.indexOf('amp_') !== 0) return adErr('توکن باید با amp_ شروع شود.');
  $('adSave').disabled = true;
  try {
    const r = await api('/live/agents', { method: 'POST', body: { name: name, token: tok } });
    const j = await r.json();
    if (!r.ok) { adErr(j.detail || 'ثبت نشد.'); return; }
    const id = j.agent_id || (j.agent && j.agent.agent_id);
    closeAgentDlg();
    await loadAgents();
    if (id) { agentPicked.add(id); renderAgentBook(); }
    log('sent', 'ایجنت ثبت شد', '«' + name + '» به دفترچه اضافه شد.');
    // ثبت بدون آزمون بی‌معنی است: توکن غلط تا وسط جلسه لو نمی‌رفت.
    const a = agentBook.find(function (x) { return x.agent_id === id; });
    if (a) await testAgent(a);
  } catch (e) { adErr('خطا در ثبت: ' + e); }
  finally { $('adSave').disabled = false; }
}

if ($('btnAddAgent')) $('btnAddAgent').onclick = openAgentDlg;
if ($('adCancel')) $('adCancel').onclick = closeAgentDlg;
if ($('adSave')) $('adSave').onclick = saveAgent;
if ($('btnReloadAgents')) $('btnReloadAgents').onclick = loadAgents;
if ($('agentDlg')) $('agentDlg').onclick = function (e) { if (e.target === $('agentDlg')) closeAgentDlg(); };
if ($('adToken')) $('adToken').onkeydown = function (e) { if (e.key === 'Enter') saveAgent(); };
document.addEventListener('keydown', function (e) {
  if (e.key === 'Escape' && $('agentDlg') && $('agentDlg').classList.contains('on')) { closeAgentDlg(); return; }
  if (e.key === 'Escape' && $('setupDlg') && $('setupDlg').classList.contains('on')) closeSetup();
});

// وضعیت زنده گیرنده‌ها: چه کسی در جلسه است و چقدر متن برایش معلق مانده
async function paintAgentLive() {
  const box = $('agentLive');
  if (!box || !sessionId) return;
  try {
    const r = await api('/live/sessions/' + sessionId);
    const j = await r.json();
    const ags = j.agents || [];
    if (!ags.length) { box.innerHTML = ''; return; }
    box.innerHTML = ags.map(function (a) {
      const ready = a.amp_ready ? '' : ' (در انتظار اتصال)';
      return '<div class="ag-row"><b>' + a.name + '</b>' + ready +
             '<span class="ag-n">' + fa(a.words_since || 0) + ' کلمه معلق</span></div>';
    }).join('');
  } catch (e) { /* نمایش زنده حیاتی نیست */ }
}

loadAgents();
setInterval(paintAgentLive, 5000);

// تغییر اندازه یا چرخش گوشی یعنی چیدمان باید دوباره حساب شود.
let rzT = null;
window.addEventListener('resize', function () {
  if (rzT) clearTimeout(rzT);
  rzT = setTimeout(layoutGrid, 120);
});
window.addEventListener('orientationchange', function () { setTimeout(layoutGrid, 220); });
layoutGrid();

// ================= حالت دایره ضبط =================
// در موبایل تجربه ضبط تمام‌صفحه می‌شود: یک دایره با موج صدا، بدون فرم و عدد.
const rm = {
  on:false, t0:0, timer:null, bars:null, canvas:null, ctx2d:null, pts:[]
};

function rmFmt(ms){
  const s=Math.max(0,Math.floor(ms/1000));
  return fa(String(Math.floor(s/60)).padStart(2,'0'))+':'+fa(String(s%60).padStart(2,'0'));
}

function rmBars(){
  const h=document.getElementById('rmBars');
  if(h.childElementCount) return;
  for(let i=0;i<32;i++) h.appendChild(document.createElement('i'));
}

function rmValues(){
  const b=document.getElementById('lvl');
  const w=parseFloat((b&&b.style.width)||'0')/100;
  return Math.max(0,w);
}

function rmDraw(){
  if(!rm.on) return;
  const c=rm.canvas; if(!c) return;
  const w=c.width/2, h=c.height/2, cx=w/2, cy=h/2;
  const R=Math.min(w,h)/2-3;
  rm.pts.push(rmValues());
  if(rm.pts.length>150) rm.pts.shift();
  rm.ctx2d.clearRect(0,0,w,h);
  // موج زنده دور دایره
  rm.ctx2d.beginPath();
  for(let i=0;i<rm.pts.length;i++){
    const a=(i/rm.pts.length)*Math.PI*2-Math.PI/2;
    const r=R-Math.min(26,rm.pts[i]*38);
    const x=cx+Math.cos(a)*r, y=cy+Math.sin(a)*r;
    if(i===0) rm.ctx2d.moveTo(x,y); else rm.ctx2d.lineTo(x,y);
  }
  rm.ctx2d.closePath();
  rm.ctx2d.strokeStyle=(getComputedStyle(document.documentElement).getPropertyValue('--meeting').trim()||'#7C3AED'); rm.ctx2d.lineWidth=2; rm.ctx2d.globalAlpha=.7; rm.ctx2d.stroke();
  rm.ctx2d.globalAlpha=1;
  // نوارهای میله‌ای زیر دایره
  if(rm.bars){
    const live=rmValues();
    Array.prototype.forEach.call(rm.bars.children,function(el,i){
      const d=Math.abs(i-(rm.bars.children.length-1))/rm.bars.children.length;
      const hv=Math.max(10,live*120-Math.abs(Math.sin((Date.now()/140)+i))*26*(1-d*0.6));
      el.style.height=Math.min(100,Math.max(10,hv))+'%';
      el.className=live>0.12?'hi':'';
    });
  }
  requestAnimationFrame(rmDraw);
}

function rmOpen(){
  const el=document.getElementById('recMode');
  if(!el||rm.on) return;
  rm.on=true; el.classList.add('on'); el.setAttribute('aria-hidden','false');
  document.body.classList.add('bh-lock');
  rmBars();
  rm.bars=document.getElementById('rmBars');
  rm.canvas=document.getElementById('rmWave');
  if(rm.canvas){
    const r=rm.canvas.getBoundingClientRect(), dpr=window.devicePixelRatio||1;
    rm.canvas.width=Math.max(160,r.width*dpr); rm.canvas.height=Math.max(160,r.height*dpr);
    rm.ctx2d=rm.canvas.getContext('2d'); rm.ctx2d.scale(dpr,dpr);
  }
  rm.t0=Date.now();
  rm.timer=setInterval(function(){
    const ms=recording?(Date.now()-(sessionStart||rm.t0)):(Date.now()-rm.t0);
    document.getElementById('rmTime').textContent=rmFmt(ms);
    document.getElementById('rmWords').textContent=fa(totalWords)+' کلمه ثبت شده'+(pendingWords?' — '+fa(pendingWords)+' معلق':'');
    rmKeep();
  },500);
  document.getElementById('rmCore').classList.toggle('rec',!!recording);
  requestAnimationFrame(rmDraw);
}

function rmClose(){
  const el=document.getElementById('recMode');
  if(!el||!rm.on) return;
  rm.on=false; el.classList.remove('on'); el.setAttribute('aria-hidden','true');
  document.body.classList.remove('bh-lock');
  if(rm.timer) clearInterval(rm.timer);
}

// آخرین چند خط متن زنده را داخل دایره نشان بده
function rmKeep(){
  const box=document.getElementById('rmLive'); if(!box) return;
  // پاسخ ایجنت مهم تر است، پس اول آن را نشان بده. اگر پاسخی نبود،
  // متن خودم را نشان بده تا دایره ضبط هیچ وقت خالی نماند.
  const rep=document.getElementById('replies');
  const mine=document.getElementById('log');
  const pick=[];
  if(rep){
    const rl=Array.prototype.slice.call(rep.querySelectorAll('.line')).slice(-3);
    rl.forEach(function(l){ pick.push(l); });
  }
  if(mine){
    const ml=Array.prototype.slice.call(mine.querySelectorAll('.line')).slice(-3);
    ml.forEach(function(l){ pick.push(l); });
  }
  if(!pick.length) return;
  box.innerHTML=pick.map(function(l){return l.outerHTML.replace(/class="line/g,'class="line rm-min');}).join('');
  box.scrollTop=box.scrollHeight;
}

var rmSkipClick=false;   // جلوگیری از کلیک مصنوعی بعد از لمس
function closeHint(msg){
  var box=document.getElementById('rmHint');
  if(!box){ box=document.createElement('div'); box.id='rmHint'; box.className='rm-hint';
    document.getElementById('recMode').appendChild(box); }
  box.textContent=msg; box.classList.add('on');
  clearTimeout(window.__rmHintT);
  window.__rmHintT=setTimeout(function(){ box.classList.remove('on'); },2400);
}
document.getElementById('rmClose').onclick=rmClose;
document.getElementById('rmCore').onclick=function(){
  if(rmSkipClick){ rmSkipClick=false; return; }   // لمس قبلا مدیریت شده
  if(recording) rmClose(); else rmOpen();
};
document.getElementById('rmStop').onclick=function(){ var b=document.getElementById('btnStop'); if(b&&!b.disabled) b.click(); };
document.getElementById('rmAsk').onclick=function(){ var b=document.getElementById('btnAsk'); if(b&&!b.disabled) b.click(); };
document.addEventListener('keydown',function(e){ if(e.key==='Escape') rmClose(); });
// لمس دایره در حالت ضبط = پایان
document.getElementById('rmCore').addEventListener('touchend',function(e){
  rmSkipClick=true;                     // کلیکی که مرورگر بعد از لمس می‌سازد را بی‌اثر کن
  if(recording){
    e.preventDefault();
    var b=document.getElementById('btnStop');
    if(b&&!b.disabled){ b.click(); return; }
    closeHint('دکمه پایان فعال نیست، چند لحظه صبر کن');
  } else { rmOpen(); }
},{passive:false});
/* ---------- چسب رابط جدید ---------- */
// نمایش مقدار اسلایدرها
function paintSlider(id,out,unit){
  var el=$(id), box=$(out);
  function upd(){
    var v=parseInt(el.value,10)||0;
    box.innerHTML = fa(v) + (unit?'<i>'+unit+'</i>':'');
  }
  el.addEventListener('input',upd); upd();
}
paintSlider('thWords','vWords','');
paintSlider('thTime','vTime','ثانیه');
paintSlider('thSilence','vSilence','ثانیه');
paintSlider('thMin','vMin','');

// حالت های پیش فرض
var PRESETS={
  short:{w:200,t:45,s:4,m:30,label:'کوتاه',hint:'ارسال زودتر، مناسب جلسه های سریع'},
  norm :{w:400,t:90,s:6,m:60,label:'متعادل',hint:'تنظیم پیشنهادی برای بیشتر جلسه ها'},
  long :{w:800,t:180,s:12,m:120,label:'بلند',hint:'ارسال کمتر، مناسب جلسه های طولانی'}
};
function applyPreset(k){
  var p=PRESETS[k]; if(!p) return;
  $('thWords').value=p.w; $('thTime').value=p.t; $('thSilence').value=p.s; $('thMin').value=p.m;
  ['thWords','thTime','thSilence','thMin'].forEach(function(id){ $(id).dispatchEvent(new Event('input')); });
  $('presetPill').textContent=p.label;
  document.querySelectorAll('.seg button').forEach(function(b){ b.classList.toggle('on', b.dataset.preset===k); });
}
document.querySelectorAll('.seg button').forEach(function(b){
  b.onclick=function(){ applyPreset(b.dataset.preset); };
});
// اگر کاربر خودش اسلایدر را کشید، برچسب پیش فرض به «دستی» برود
['thWords','thTime','thSilence','thMin'].forEach(function(id){
  $(id).addEventListener('input',function(){
    $('presetPill').textContent='دستی';
    document.querySelectorAll('.seg button').forEach(function(b){ b.classList.remove('on'); });
  });
});
if(token) applyPreset('norm');

// دایره ضبط وضعیت را از خود پیل بخواند تا منطق قدیمی دست نخورد
var _setState=setState;
setState=function(txt,cls){
  _setState(txt,cls);
  var live = cls==='rec';
  $('recRing').classList.toggle('live',live);
  $('btnStart').setAttribute('aria-label', live?'پایان ضبط':'شروع ضبط');
  $('ctaHint').textContent = live ? 'در حال ضبط؛ دایره را بزن تا تمام شود' : 'برای شروع، دایره را بزن';
  var c=$('chunkPill'); if(c) c.textContent = fa(seq) + ' تکه';
};
// تکه شمار هم زنده شود
var _log=log;
log=function(cls,head,text){ _log(cls,head,text); var c=$('chunkPill'); if(c) c.textContent=fa(seq)+' تکه'; };


// ---------- آرشیو صدا ----------
// یک ریکوردر مستقل که از شروع تا پایان جلسه یک بار روشن می ماند و در
// پایان یک فایل یکپارچه می دهد. ریکوردر تکه ها برای این کار به درد
// نمی خورد چون هر تکه هدر خودش را دارد و چسباندنشان فایل خراب می دهد.
var archRec = null, archParts = [], archStart = 0, archBlob = null, archUrl = null, archMime = '';

function pickMime() {
  var list = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus'];
  for (var i = 0; i < list.length; i++) {
    try { if (MediaRecorder.isTypeSupported(list[i])) return list[i]; } catch (e) {}
  }
  return '';
}
function mimeExt(m) {
  if (!m) return 'webm';
  if (m.indexOf('mp4') >= 0) return 'm4a';
  if (m.indexOf('ogg') >= 0) return 'ogg';
  return 'webm';
}
function faTime(sec) {
  sec = Math.max(0, Math.round(sec));
  var m = Math.floor(sec / 60), r = sec % 60;
  return fa(m) + ':' + fa(r < 10 ? '0' + r : String(r));
}
function faNum(x) { return fa(String(x)).replace('.', '\u066b'); }

function startArchive() {
  archParts = []; archBlob = null; archStart = Date.now();
  if (archUrl) { URL.revokeObjectURL(archUrl); archUrl = null; }
  $('audioCard').classList.add('hide');
  if (!stream || typeof MediaRecorder === 'undefined') return;
  archMime = pickMime();
  try {
    archRec = archMime
      ? new MediaRecorder(stream, { mimeType: archMime, audioBitsPerSecond: 32000 })
      : new MediaRecorder(stream);
  } catch (e) { archRec = null; return; }
  archRec.ondataavailable = function (e) { if (e.data && e.data.size) archParts.push(e.data); };
  archRec.onstop = finishArchive;
  try { archRec.start(5000); } catch (e) { archRec = null; }
}

// پایان آرشیو. استریم میکروفون تا آمدن رویداد stop باز نگه داشته می شود
// وگرنه آخرین قاب ها قبل از بسته شدن فایل از دست می رود.
function stopArchive() {
  var mic = stream;
  function releaseMic() { if (mic) { try { mic.getTracks().forEach(function (t) { t.stop(); }); } catch (e) {} mic = null; } }
  if (stream) stream = null;
  if (audioCtx) { try { audioCtx.close(); } catch (e) {} audioCtx = null; }
  if (!archRec || archRec.state === 'inactive') { releaseMic(); return; }
  var done = false;
  var guard = setTimeout(function () { if (!done) { done = true; releaseMic(); } }, 1500);
  var prev = archRec.onstop;
  archRec.onstop = function () {
    try { if (prev) prev(); } finally { if (!done) { done = true; clearTimeout(guard); releaseMic(); } }
  };
  try { archRec.requestData(); archRec.stop(); } catch (e) { clearTimeout(guard); releaseMic(); }
}

function finishArchive() {
  if (!archParts.length) {
    $('auHint').textContent = 'صدایی ضبط نشد، پس فایلی ساخته نشد.';
    $('audioCard').classList.remove('hide'); layoutGrid();
    return;
  }
  archBlob = new Blob(archParts, { type: archMime || 'audio/webm' });
  archParts = [];
  if (archUrl) URL.revokeObjectURL(archUrl);
  archUrl = URL.createObjectURL(archBlob);

  var ext = mimeExt(archMime);
  var raw = ($('title').value || 'جلسه').replace(/[\\/:*?"<>|]/g, '-').replace(/\s+/g, '-').slice(0, 40);
  var name = raw + '-' + ext;

  var a = $('btnSaveAudio');
  a.href = archUrl; a.download = name;
  $('auPlayer').src = archUrl;
  $('auDur').textContent = faTime((Date.now() - archStart) / 1000);
  $('auSize').textContent = faNum((archBlob.size / 1048576).toFixed(1));
  $('auFmt').textContent = ext.toUpperCase();
  $('auHint').textContent = 'فایل تا وقتی این صفحه باز است در مرورگر می ماند. برای نگه داشتن، ذخیره کن.';

  // مسیر اشتراک گذاری برای موبایل. در آیفون ذخیره مستقیم همیشه کار نمی کند
  // ولی از پنجره اشتراک گذاری می شود «ذخیره در فایل ها» را زد.
  var sb = $('btnShareAudio'), can = false;
  try { can = !!(navigator.canShare && navigator.canShare({ files: [new File([archBlob], name, { type: archBlob.type })] })); } catch (e) { can = false; }
  sb.classList.toggle('hide', !can);
  sb.onclick = async function () {
    try { await navigator.share({ files: [new File([archBlob], name, { type: archBlob.type })], title: 'صدای جلسه' }); }
    catch (e) { if (e && e.name !== 'AbortError') $('auHint').textContent = 'اشتراک گذاری نشد: ' + String(e); }
  };

  $('audioCard').classList.remove('hide');
  layoutGrid();
  log('ok', 'فایل صدا', 'آماده شد. دکمه ذخیره در گوشی را بزن.');
}

// اگر وسط ضبط صفحه بسته شود، صدا از دست می رود. هشدار می دهیم.
window.addEventListener('beforeunload', function (e) {
  if (!recording) return;
  e.preventDefault(); e.returnValue = '';
});

// آیکن‌های جای‌گذار صفحه (data-ico) از مجموعه آیکن مشترک پر می‌شوند.
(function () {
  if (!window.BH || !BH.icon) return;
  document.querySelectorAll('[data-ico]').forEach(function (el) {
    el.innerHTML = BH.icon(el.getAttribute('data-ico'));
  });
})();
