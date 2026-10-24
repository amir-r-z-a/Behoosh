/* بهوش — داشبورد سلامت
   همه اعداد از /v1/dashboard می‌آیند. داده دو برابر بازه گرفته می‌شود تا هر شاخص با
   بازه قبلیِ هم‌اندازه مقایسه شود. هر تب فقط وقتی باز می‌شود رسم می‌شود. */
(function () {
  'use strict';
  var BH = window.BH, C = window.BHChart;
  if (!BH.requireAuth()) return;
  var $ = BH.$, n = BH.n, esc = BH.esc;

  var state = { days: 14, raw: null, cur: null, prev: null, tab: 'today', rendered: {}, tpColor: 'mood' };
  try { var sd = +localStorage.getItem('behoosh_health_days'); if ([7, 14, 30, 90].indexOf(sd) >= 0) state.days = sd; } catch (e) {}

  var SERIES = ['kcal', 'protein', 'carbs', 'fat', 'sleep_hours', 'sleep_quality', 'workout_min', 'workout_kcal',
    'mood', 'stress', 'energy', 'screen_total', 'screen_instagram', 'screen_telegram', 'unlocks', 'notifications',
    'water', 'prayers_done', 'temp_cold_warm', 'temp_dry_wet'];
  var PRAY = [['fajr', 'صبح'], ['dhuhr', 'ظهر'], ['asr', 'عصر'], ['maghrib', 'مغرب'], ['isha', 'عشا']];
  var PRAY_ST = { done: 'خوانده', late: 'با تأخیر', qada: 'قضا', missed: 'نخوانده' };
  var SLOT = { breakfast: 'صبحانه', snack: 'میان‌وعده', lunch: 'ناهار', evening: 'عصرانه', dinner: 'شام', after_dinner: 'بعد از شام' };
  var SLOT_ORDER = ['breakfast', 'snack', 'lunch', 'evening', 'dinner', 'after_dinner'];
  var UNIT = { gram: 'گرم', spoon: 'قاشق', piece: 'عدد', glass: 'لیوان', palm: 'کف دست', bowl: 'پیاله' };
  var WATER_TARGET = 2.5;
  var MUSCLE_FA = {
    chest: 'سینه', obliques: 'مورب شکم', abs: 'شکم', biceps: 'جلو بازو', triceps: 'پشت بازو', neck: 'گردن',
    trapezius: 'ذوزنقه', deltoids: 'سرشانه', adductors: 'داخلی ران', quadriceps: 'چهارسر ران', knees: 'زانو',
    tibialis: 'جلوی ساق', calves: 'ساق', forearm: 'ساعد', hands: 'دست', ankles: 'مچ پا', feet: 'کف پا',
    head: 'سر', hair: 'مو', gluteal: 'باسن', hamstring: 'پشت ران', 'upper-back': 'زیربغل', 'lower-back': 'کمر'
  };
  var MUSCLE_ALIAS = { 'پشت‌بازو': 'triceps', 'جلو‌بازو': 'biceps', 'پا': 'quadriceps', 'هوازی': 'quadriceps', 'پشت': 'upper-back' };
  var NEUTRAL_PARTS = { head: 1, hair: 1, hands: 1, feet: 1, knees: 1, ankles: 1 };

  /* ---------- کمکی‌ها ---------- */
  function nz(v) { return v === null || v === undefined || isNaN(v) || v === 0 ? null : +v; }
  function vals(a) { return (a || []).filter(function (v) { return v !== null && v !== undefined && !isNaN(v); }); }
  function avg(a) { var v = vals(a); return v.length ? v.reduce(function (x, y) { return x + y; }, 0) / v.length : null; }
  function sum(a) { return vals(a).reduce(function (x, y) { return x + y; }, 0); }
  function last(a) { return a && a.length ? a[a.length - 1] : null; }
  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
  function tgt() { return (state.raw && state.raw.targets) || {}; }
  function labels() { return state.cur.days.map(function (d) { return BH.date(d, 'short'); }); }
  function tipLabels() { return state.cur.days.map(function (d) { return BH.date(d, 'weekday'); }); }
  function muscleKey(k) {
    k = String(k || '').trim();
    if (MUSCLE_FA[k]) return k;
    for (var en in MUSCLE_FA) if (MUSCLE_FA[en] === k) return en;
    return MUSCLE_ALIAS[k] || null;
  }

  function kpi(o) {
    return '<div class="card kpi ' + (o.tone || 't-health') + '">' +
      '<div class="kpi-top"><span class="kpi-label">' + esc(o.label) + '</span>' +
      (o.icon ? '<span class="kpi-icon">' + BH.icon(o.icon) + '</span>' : '') + '</div>' +
      '<div class="kpi-value">' + o.value + (o.unit ? '<small>' + esc(o.unit) + '</small>' : '') + '</div>' +
      (o.sub || o.delta ? '<div class="kpi-sub">' + (o.delta || '') + (o.sub ? '<span>' + o.sub + '</span>' : '') + '</div>' : '') +
      (o.progress !== undefined ? '<div class="progress ' + (o.progressTone || '') + '"><i style="width:' + clamp(o.progress, 0, 100) + '%"></i></div>' : '') +
      (o.spark ? '<div class="spark" data-spark="' + o.spark + '" data-color="' + (o.sparkColor || 'health') + '"></div>' : '') +
      '</div>';
  }
  function mountKpis(id, list, sparkData) {
    var host = document.getElementById(id);
    host.innerHTML = list.map(kpi).join('');
    BH.$$('[data-spark]', host).forEach(function (el) {
      var d = sparkData && sparkData[el.getAttribute('data-spark')];
      if (d) C.spark(el, d, el.getAttribute('data-color'));
    });
  }
  function skeletonKpis(id, k) {
    var host = document.getElementById(id); if (!host) return;
    var s = ''; for (var i = 0; i < k; i++) s += '<div class="card kpi"><span class="skeleton" style="width:60%;height:14px"></span><span class="skeleton" style="width:45%;height:28px;margin-top:6px"></span><span class="skeleton" style="width:70%;height:12px;margin-top:6px"></span></div>';
    host.innerHTML = s;
  }
  function table(head, rows, opts) {
    opts = opts || {};
    if (!rows.length) return BH.empty(opts.empty || 'هنوز داده‌ای ثبت نشده', opts.icon);
    return '<table class="table"><thead><tr>' + head.map(function (h) {
      return '<th' + (h.end ? ' class="end"' : '') + '>' + esc(h.t || h) + '</th>';
    }).join('') + '</tr></thead><tbody>' + rows.join('') + '</tbody>' + (opts.foot || '') + '</table>';
  }

  /* امتیاز روزانه: میانگین نزدیکی به هر هدف (۰ تا ۱) */
  function dayParts(i, S) {
    var T = tgt(), p = {};
    var k = S.kcal[i], pr = S.protein[i], sl = S.sleep_hours[i], sc = S.screen_total[i];
    if (T.kcal && k) p.kcal = clamp(1 - Math.abs(k - T.kcal) / T.kcal, 0, 1);
    if (T.protein_g && pr) p.protein = clamp(pr / T.protein_g, 0, 1);
    if (T.sleep_hours && sl) p.sleep = clamp(sl / T.sleep_hours, 0, 1);
    if (k || sl || S.mood[i]) p.workout = S.workout_min[i] > 0 ? 1 : 0;
    if (S.prayers_done[i] || k || sl) p.prayer = clamp((S.prayers_done[i] || 0) / 5, 0, 1);
    if (T.screen_total_min && sc) p.screen = clamp(1 - Math.max(0, sc - T.screen_total_min) / T.screen_total_min, 0, 1);
    if (S.water[i]) p.water = clamp(S.water[i] / WATER_TARGET, 0, 1);
    return p;
  }
  function dayScore(i, S) {
    var p = dayParts(i, S), ks = Object.keys(p);
    return ks.length ? Math.round(ks.reduce(function (a, k) { return a + p[k]; }, 0) / ks.length * 100) : null;
  }
  function scores(S) { return S.days.map(function (_, i) { return dayScore(i, S); }); }
  function verdict(s) {
    if (s === null) return ['بدون داده', 'muted'];
    return s >= 80 ? ['عالی، ادامه بده', 'ok'] : s >= 60 ? ['روز خوبی است', 'ok'] : s >= 40 ? ['قابل بهبود', 'warn'] : ['جای کار دارد', 'bad'];
  }
  function streak(arr, pred) {
    var k = 0;
    for (var i = arr.length - 1; i >= 0; i--) { if (pred(i)) k++; else break; }
    return k;
  }

  /* ---------- بارگذاری ---------- */
  async function load() {
    ['todayKpis', 'foodKpis', 'sleepKpis', 'gymKpis', 'mindKpis', 'screenKpis', 'adhKpis', 'tempKpis'].forEach(function (id) { skeletonKpis(id, 4); });
    skeletonKpis('bodyKpis', 6);
    try {
      var raw = await BH.api('/dashboard?days=' + state.days * 2);
      state.raw = raw;
      var N = state.days, cur = { days: raw.days.slice(-N) }, prev = { days: raw.days.slice(0, raw.days.length - N) };
      SERIES.forEach(function (k) { var a = raw[k] || []; cur[k] = a.slice(-N); prev[k] = a.slice(0, a.length - N); });
      state.cur = cur; state.prev = prev; state.rendered = {};
      header();
      renderTab(state.tab);
    } catch (e) {
      if (e.message !== 'auth') {
        $('#main').insertAdjacentHTML('afterbegin', '<div class="callout t-bad" style="margin-bottom:14px">' + BH.icon('alert') +
          '<span>بارگذاری داده‌ها ممکن نشد: ' + esc(e.message) + '</span></div>');
      }
    }
  }

  function header() {
    var me = null;
    try { me = JSON.parse(sessionStorage.getItem('behoosh_me') || 'null'); } catch (e) {}
    $('#hTitle').textContent = BH.greeting() + (me && me.display_name ? '، ' + me.display_name : '');
    $('#hDate').textContent = BH.date(state.raw.today || BH.todayISO(), 'weekday');
    $('#hSub').textContent = 'نمای ' + n(state.days) + ' روز اخیر، مقایسه با ' + n(state.days) + ' روز قبل از آن';
  }

  /* ---------- تب امروز ---------- */
  function renderToday() {
    var S = state.cur, P = state.prev, T = tgt(), R = state.raw, li = S.days.length - 1;
    var sc = scores(S), today = sc[li], prevAvg = avg(scores(P)), curAvg = avg(sc);
    C.ring('scoreRing', { value: today || 0, max: 100, size: 128, stroke: 12, label: today === null ? '—' : n(today), sub: 'از ۱۰۰', color: 'health', title: 'امتیاز امروز' });
    var v = verdict(today);
    $('#scoreVerdict').innerHTML = '<span style="color:var(--' + (v[1] === 'muted' ? 'muted' : v[1] + '-ink') + ')">' + v[0] + '</span>';
    $('#scoreDelta').innerHTML = curAvg !== null ? 'میانگین بازه ' + n(curAvg) + ' ' + BH.delta(curAvg, prevAvg) : '';

    var all = scores({ days: R.days, kcal: R.kcal, protein: R.protein, sleep_hours: R.sleep_hours, workout_min: R.workout_min,
      prayers_done: R.prayers_done, screen_total: R.screen_total, mood: R.mood, water: R.water });
    var logged = streak(R.days, function (i) { return R.kcal[i] > 0 || R.sleep_hours[i] > 0 || R.mood[i] > 0; });
    var pray = streak(R.days, function (i) { return R.prayers_done[i] >= 5; });
    var gymDays = vals(S.workout_min).filter(function (x) { return x > 0; }).length;
    var good = streak(R.days, function (i) { return all[i] !== null && all[i] >= 60; });
    $('#streaks').innerHTML = [
      ['flame', n(logged) + ' روز ثبت پیاپی', 't-warn'],
      ['pray', n(pray) + ' روز نماز کامل', 't-health'],
      ['dumbbell', n(gymDays) + ' روز ورزش', 't-info'],
      ['award', n(good) + ' روز خوب پیاپی', 't-finance']
    ].map(function (s) { return '<span class="chip ' + s[2] + '">' + BH.icon(s[0]) + s[1] + '</span>'; }).join('');

    var hab = R.habit_today || {}, pd = Object.keys(R.prayers_today || {}).filter(function (k) { return R.prayers_today[k] === 'done' || R.prayers_today[k] === 'late'; }).length;
    var k = S.kcal[li] || 0, p = S.protein[li] || 0, sl = S.sleep_hours[li] || 0, w = hab.water_liters || S.water[li] || 0, scr = S.screen_total[li] || 0;
    var goals = [
      ['کالری', 'flame', k, T.kcal, n(k) + ' از ' + n(T.kcal), 'c3'],
      ['پروتئین', 'egg', p, T.protein_g, n(p) + ' از ' + n(T.protein_g) + ' گرم', 'health'],
      ['خواب', 'bed', sl, T.sleep_hours, BH.hm(sl) + ' از ' + BH.hm(T.sleep_hours), 'c4'],
      ['آب', 'droplet', w, WATER_TARGET, n(w, 1) + ' از ' + n(WATER_TARGET, 1) + ' لیتر', 'c6'],
      ['نماز', 'pray', pd, 5, n(pd) + ' از ۵', 'ok'],
      ['اسکرین', 'phone', scr, T.screen_total_min, BH.minutes(scr) + ' از ' + BH.minutes(T.screen_total_min), scr > T.screen_total_min ? 'bad' : 'c1']
    ];
    $('#goalRings').innerHTML = goals.map(function (g, i) {
      return '<div class="goal" style="--acc:var(--' + g[5] + ')"><div id="gr' + i + '"></div><span class="goal-name">' + BH.icon(g[1]) + g[0] + '</span><span class="goal-sub num">' + g[4] + '</span></div>';
    }).join('');
    goals.forEach(function (g, i) {
      var pct = g[3] ? g[2] / g[3] * 100 : 0;
      C.ring('gr' + i, { value: g[2], max: g[3] || 1, size: 84, stroke: 8, color: g[5], label: BH.pct(Math.min(pct, 999)), title: g[0] });
    });

    var dK = BH.delta(avg(S.kcal.map(nz)), avg(P.kcal.map(nz))), dP = BH.delta(avg(S.protein.map(nz)), avg(P.protein.map(nz)));
    var dS = BH.delta(avg(S.sleep_hours.map(nz)), avg(P.sleep_hours.map(nz)));
    var body = (R.body || []).slice().reverse(), wNow = body.length ? body[body.length - 1].weight_kg : null;
    var wPrev = body.length > 1 ? body[0].weight_kg : null;
    mountKpis('todayKpis', [
      { label: 'کالری امروز', icon: 'flame', value: n(k), unit: 'از ' + n(T.kcal), delta: dK, sub: 'میانگین ' + n(avg(S.kcal.map(nz))), spark: 'kcal', sparkColor: 'c3', tone: 't-warn' },
      { label: 'پروتئین امروز', icon: 'egg', value: n(p), unit: 'گرم', delta: dP, sub: n(Math.max(0, (T.protein_g || 0) - p)) + ' گرم مانده', spark: 'protein', sparkColor: 'health' },
      { label: 'خواب دیشب', icon: 'bed', value: BH.hm(sl), unit: 'ساعت', delta: dS, sub: 'کیفیت ' + n(S.sleep_quality[li] || 0) + ' از ۱۰', spark: 'sleep', sparkColor: 'c4', tone: 't-info' },
      { label: 'وزن', icon: 'scale', value: wNow ? n(wNow, 1) : '—', unit: 'کیلوگرم', tone: 't-finance', spark: 'weight', sparkColor: 'c1',
        sub: wNow && wPrev ? (wNow <= wPrev ? 'کاهش ' : 'افزایش ') + n(Math.abs(wNow - wPrev), 1) + ' از ' + BH.date(body[0].d, 'short') : 'بدون ثبت' }
    ], { kcal: S.kcal.map(nz), protein: S.protein.map(nz), sleep: S.sleep_hours.map(nz), weight: body.map(function (b) { return b.weight_kg; }) });

    C.line('cTodayKcal', { labels: labels(), tipLabels: tipLabels(), height: 230, target: T.kcal,
      series: [{ name: 'کالری', data: S.kcal.map(nz), color: 'c3' }], fmt: function (v) { return n(v) + ' کالری'; } });
    C.bar('cTodaySleep', { labels: labels(), tipLabels: tipLabels(), data: S.sleep_hours.map(nz), name: 'خواب', color: 'c4', yMax: 10, height: 220,
      target: T.sleep_hours, fmt: function (v) { return BH.hm(v); }, overlay: { data: S.sleep_quality.map(nz), name: 'کیفیت', color: 'c2', max: 10, fmt: function (v) { return n(v) + ' از ۱۰'; } } });

    $('#insIcon').innerHTML = BH.icon('sparkles');
    $('#insights').innerHTML = insights().map(function (t) {
      return '<li><span class="ico ' + t[0] + '">' + BH.icon(t[1]) + '</span><span>' + t[2] + '</span></li>';
    }).join('') || '<li>' + BH.empty('برای بینش، چند روز داده ثبت کن', 'sparkles') + '</li>';

    checklist();
  }

  function insights() {
    var S = state.cur, P = state.prev, T = tgt(), out = [];
    var sl = S.sleep_hours.map(nz), sAvg = avg(sl);
    if (sAvg !== null && T.sleep_hours) {
      var below = vals(sl).filter(function (v) { return v < T.sleep_hours; }).length;
      out.push(['t-info', 'bed', 'میانگین خوابت <b>' + BH.hm(sAvg) + '</b> بود؛ ' + n(below) + ' شب از ' + n(vals(sl).length) + ' زیر هدف ' + BH.hm(T.sleep_hours) + '.']);
    }
    var hi = [], lo = [];
    S.days.forEach(function (_, i) { if (sl[i] && S.mood[i]) (sl[i] >= (T.sleep_hours || 7) ? hi : lo).push(S.mood[i]); });
    if (hi.length >= 2 && lo.length >= 2) {
      var d = avg(hi) - avg(lo);
      if (Math.abs(d) >= 0.4) out.push([d > 0 ? 't-ok' : 't-warn', 'smile', 'در روزهایی که به هدف خواب رسیدی، خلقت به‌طور میانگین <b>' + n(Math.abs(d), 1) + '</b> واحد ' + (d > 0 ? 'بالاتر' : 'پایین‌تر') + ' بود.']);
    }
    var sc = avg(S.screen_total.map(nz)), scp = avg(P.screen_total.map(nz));
    if (sc && scp) {
      var ch = (sc - scp) / scp * 100;
      if (Math.abs(ch) >= 3) out.push([ch < 0 ? 't-ok' : 't-warn', 'phone', 'اسکرین‌تایم روزانه <b>' + BH.pct(Math.abs(ch)) + ' ' + (ch < 0 ? 'کمتر' : 'بیشتر') + '</b> از بازه قبل.']);
    }
    if (T.protein_g) {
      var pv = vals(S.protein.map(nz)), hit = pv.filter(function (v) { return v >= T.protein_g; }).length;
      if (pv.length) out.push([hit / pv.length >= 0.5 ? 't-ok' : 't-warn', 'egg', 'پروتئین در <b>' + n(hit) + ' روز از ' + n(pv.length) + '</b> به هدف ' + n(T.protein_g) + ' گرم رسید.']);
    }
    var g = vals(S.workout_min).filter(function (v) { return v > 0; }).length, gp = vals(P.workout_min).filter(function (v) { return v > 0; }).length;
    if (g || gp) out.push([g >= gp ? 't-ok' : 't-warn', 'dumbbell', n(g) + ' روز ورزش کردی' + (gp ? '؛ بازه قبل ' + n(gp) + ' روز.' : '.')]);
    var scs = scores(S), best = -1, bi = -1;
    scs.forEach(function (v, i) { if (v !== null && v > best) { best = v; bi = i; } });
    if (bi >= 0) out.push(['t-finance', 'award', 'بهترین روزت <b>' + BH.date(S.days[bi], 'weekday') + '</b> با امتیاز ' + n(best) + ' بود.']);
    return out.slice(0, 5);
  }

  function checklist() {
    var R = state.raw, hab = R.habit_today, mood = R.mood_today, today = R.today;
    var pt = R.prayers_today || {}, rows = [];
    var done = Object.keys(pt).filter(function (k) { return pt[k] === 'done'; }).length;
    $('#checkSub').textContent = BH.date(today, 'weekday');
    rows.push(['t-health', 'pray', 'نماز', n(done) + ' از ۵ خوانده‌شده',
      '<div class="prayer-row">' + PRAY.map(function (p) { var s = pt[p[0]]; return '<span class="pray ' + (s || '') + '" title="' + (PRAY_ST[s] || 'ثبت نشده') + '">' + p[1] + '</span>'; }).join('') + '</div>']);
    var w = hab ? hab.water_liters : 0;
    rows.push(['t-info', 'droplet', 'آب', n(w, 1) + ' از ' + n(WATER_TARGET, 1) + ' لیتر',
      '<div class="progress" style="width:120px"><i style="width:' + clamp(w / WATER_TARGET * 100, 0, 100) + '%;background:var(--c6)"></i></div>']);
    rows.push(['t-info', 'smile', 'حال امروز', mood ? 'خلق ' + n(mood.mood) + '، استرس ' + n(mood.stress) + '، انرژی ' + n(mood.energy) : 'هنوز ثبت نشده',
      mood ? '<span class="badge ' + (mood.mood >= 7 ? 'ok' : mood.mood >= 5 ? 'warn' : 'bad') + '">' + n(mood.mood) + '/۱۰</span>' : '']);
    var wk = (R.workouts || []).filter(function (x) { return x.d === today; });
    rows.push(['t-warn', 'dumbbell', 'ورزش', wk.length ? wk.map(function (x) { return x.kind + '، ' + n(x.duration_min) + ' دقیقه'; }).join(' — ') : 'امروز ثبت نشده',
      wk.length ? '<span class="badge ok">' + BH.icon('check') + 'انجام شد</span>' : '']);
    var meals = R.meals_today || [];
    rows.push(['t-warn', 'flame', 'وعده‌ها', meals.length ? n(meals.length) + ' قلم، ' + n(sum(meals.map(function (m) { return m.kcal; }))) + ' کالری' : 'هنوز وعده‌ای ثبت نشده', '']);
    if (hab) rows.push(['t-health', 'leaf', 'عادت‌ها', [hab.breathing_done ? 'تنفس عمیق انجام شد' : 'تنفس عمیق مانده'].concat(hab.supplements || [], hab.teas || []).join('، '), '']);
    $('#checklist').innerHTML = rows.map(function (r) {
      return '<div class="list-row"><span class="ico ' + r[0] + '">' + BH.icon(r[1]) + '</span><div class="grow"><div class="title">' + r[2] +
        '</div><div class="meta">' + esc(r[3]) + '</div></div>' + r[4] + '</div>';
    }).join('');
  }

  /* ---------- تغذیه ---------- */
  function renderFood() {
    var S = state.cur, P = state.prev, T = tgt(), R = state.raw, li = S.days.length - 1;
    var pv = vals(S.protein.map(nz)), hit = pv.filter(function (v) { return v >= T.protein_g; }).length;
    mountKpis('foodKpis', [
      { label: 'میانگین کالری', icon: 'flame', tone: 't-warn', value: n(avg(S.kcal.map(nz))), unit: 'در روز', delta: BH.delta(avg(S.kcal.map(nz)), avg(P.kcal.map(nz))), sub: 'هدف ' + n(T.kcal) },
      { label: 'میانگین پروتئین', icon: 'egg', value: n(avg(S.protein.map(nz))), unit: 'گرم', delta: BH.delta(avg(S.protein.map(nz)), avg(P.protein.map(nz))), sub: 'هدف ' + n(T.protein_g) },
      { label: 'روزهای رسیدن به هدف پروتئین', icon: 'target', tone: 't-ok', value: n(hit), unit: 'از ' + n(pv.length), progress: pv.length ? hit / pv.length * 100 : 0, progressTone: 'ok' },
      { label: 'کربوهیدرات / چربی', icon: 'leaf', tone: 't-finance', value: n(avg(S.carbs.map(nz))) + ' / ' + n(avg(S.fat.map(nz))), unit: 'گرم', sub: 'میانگین روزانه' }
    ]);
    C.line('cFoodKcal', { labels: labels(), tipLabels: tipLabels(), target: T.kcal, height: 240,
      series: [{ name: 'کالری', data: S.kcal.map(nz), color: 'c3' }], fmt: function (v) { return n(v) + ' کالری'; } });
    C.bar('cFoodProt', { labels: labels(), tipLabels: tipLabels(), data: S.protein.map(nz), name: 'پروتئین', color: 'health', target: T.protein_g, height: 220,
      fmt: function (v) { return n(v) + ' گرم'; }, colorFn: function (v) { return v >= T.protein_g ? 'health' : 'c2'; } });
    C.stack('cFoodMacroStack', { labels: labels(), tipLabels: tipLabels(), height: 220, fmt: function (v) { return n(v) + ' گرم'; },
      series: [{ name: 'پروتئین', data: S.protein, color: 'c2' }, { name: 'کربوهیدرات', data: S.carbs, color: 'c1' }, { name: 'چربی', data: S.fat, color: 'c3' }] });
    var pr = S.protein[li] || 0, cb = S.carbs[li] || 0, ft = S.fat[li] || 0;
    C.donut('cMacro', { data: [pr * 4, cb * 4, ft * 9], labels: ['پروتئین ' + n(pr) + ' گرم', 'کربوهیدرات ' + n(cb) + ' گرم', 'چربی ' + n(ft) + ' گرم'],
      colors: ['c2', 'c1', 'c3'], size: 170, centerLabel: 'کالری', fmt: function (v) { return n(v) + ' کالری'; } });

    var meals = (R.meals_today || []).slice().sort(function (a, b) { return SLOT_ORDER.indexOf(a.slot) - SLOT_ORDER.indexOf(b.slot); });
    $('#mealsSub').textContent = BH.date(R.today, 'weekday');
    var tot = { k: 0, p: 0, c: 0, f: 0 };
    var rows = meals.map(function (m) {
      tot.k += m.kcal; tot.p += m.protein_g; tot.c += m.carbs_g; tot.f += m.fat_g;
      return '<tr><td><span class="badge">' + esc(SLOT[m.slot] || m.slot) + '</span></td><td><b>' + esc(m.name) + '</b></td><td class="num">' + n(m.quantity, 1) + ' ' + esc(UNIT[m.unit] || m.unit) +
        '</td><td class="end num">' + n(m.kcal) + '</td><td class="end num">' + n(m.protein_g) + '</td><td class="end num">' + n(m.carbs_g) + '</td><td class="end num">' + n(m.fat_g) + '</td></tr>';
    });
    var foot = '<tfoot><tr><td colspan="3"><b>جمع امروز</b></td><td class="end num"><b>' + n(tot.k) + '</b></td><td class="end num"><b>' + n(tot.p) + '</b></td><td class="end num"><b>' + n(tot.c) + '</b></td><td class="end num"><b>' + n(tot.f) + '</b></td></tr></tfoot>';
    $('#mealsTable').innerHTML = table(['وعده', 'غذا', 'مقدار', { t: 'کالری', end: 1 }, { t: 'پروتئین', end: 1 }, { t: 'کربو', end: 1 }, { t: 'چربی', end: 1 }], rows,
      { foot: rows.length ? foot : '', empty: 'امروز هنوز وعده‌ای ثبت نشده. به ایجنت بگو چه خوردی.', icon: 'flame' });
  }

  /* ---------- خواب ---------- */
  function bedHour(hm) {
    if (!hm) return null;
    var p = hm.split(':'), h = +p[0] + (+p[1]) / 60;
    return h < 12 ? h + 24 : h;
  }
  function fmtBed(v) { var h = Math.floor(v) % 24, m = Math.round((v % 1) * 60); return BH.fa(String(h).padStart(2, '0') + ':' + String(m).padStart(2, '0')); }
  function renderSleep() {
    var S = state.cur, P = state.prev, T = tgt(), R = state.raw;
    var log = (R.sleep_log || []).slice().reverse();
    var beds = log.map(function (s) { return bedHour(s.bedtime); }).filter(function (v) { return v !== null; });
    var sd = null;
    if (beds.length > 1) { var m = avg(beds); sd = Math.sqrt(avg(beds.map(function (b) { return (b - m) * (b - m); }))) * 60; }
    var sl = vals(S.sleep_hours.map(nz)), below = sl.filter(function (v) { return v < T.sleep_hours; }).length;
    mountKpis('sleepKpis', [
      { label: 'میانگین خواب', icon: 'bed', tone: 't-info', value: BH.hm(avg(sl)), unit: 'ساعت', delta: BH.delta(avg(sl), avg(P.sleep_hours.map(nz))), sub: 'هدف ' + BH.hm(T.sleep_hours) },
      { label: 'میانگین کیفیت', icon: 'sparkles', value: n(avg(S.sleep_quality.map(nz)), 1), unit: 'از ۱۰', delta: BH.delta(avg(S.sleep_quality.map(nz)), avg(P.sleep_quality.map(nz))) },
      { label: 'ثبات ساعت خواب', icon: 'clock', tone: 't-finance', value: sd === null ? '—' : '±' + n(sd), unit: 'دقیقه', sub: sd === null ? '' : sd <= 30 ? 'منظم' : sd <= 60 ? 'نسبتا منظم' : 'نامنظم' },
      { label: 'شب‌های زیر هدف', icon: 'alert', tone: below > sl.length / 2 ? 't-bad' : 't-warn', value: n(below), unit: 'از ' + n(sl.length), progress: sl.length ? below / sl.length * 100 : 0, progressTone: 'warn' }
    ]);
    C.bar('cSleepMain', { labels: labels(), tipLabels: tipLabels(), data: S.sleep_hours.map(nz), name: 'خواب', color: 'c4', yMax: 10, height: 250, target: T.sleep_hours,
      fmt: function (v) { return BH.hm(v); }, overlay: { data: S.sleep_quality.map(nz), name: 'کیفیت', color: 'c2', max: 10, fmt: function (v) { return n(v) + ' از ۱۰'; } } });
    C.line('cBedtime', { labels: log.map(function (s) { return BH.date(s.d, 'short'); }), tipLabels: log.map(function (s) { return BH.date(s.d, 'weekday'); }),
      height: 250, autoMin: true, yFmt: fmtBed, labelWidth: 70,
      series: [{ name: 'به خواب رفتن', data: log.map(function (s) { return bedHour(s.bedtime); }), color: 'c4', fmt: fmtBed, fill: false }] });
    $('#sleepTable').innerHTML = table(['شب', 'خواب', 'بیداری', { t: 'مدت', end: 1 }, 'کیفیت', { t: 'بیدار شدن', end: 1 }, { t: 'چرت', end: 1 }],
      (R.sleep_log || []).map(function (s) {
        var q = s.quality;
        return '<tr><td>' + BH.date(s.d, 'weekday') + '</td><td class="num ltr">' + (s.bedtime ? BH.fa(s.bedtime) : '—') + '</td><td class="num ltr">' + (s.wake_time ? BH.fa(s.wake_time) : '—') +
          '</td><td class="end num"><b>' + BH.hm(s.hours) + '</b></td><td><span class="badge ' + (q >= 7 ? 'ok' : q >= 5 ? 'warn' : 'bad') + '">' + n(q) + '/۱۰</span></td><td class="end num">' + n(s.wake_count) +
          '</td><td class="end num">' + (s.nap_min ? n(s.nap_min) + ' دقیقه' : '—') + '</td></tr>';
      }), { empty: 'هنوز خوابی ثبت نشده', icon: 'bed' });
  }

  /* ---------- ورزش ---------- */
  function recovery(d) {
    if (d === null || d === undefined) return ['surface-3', 'بدون تمرین ثبت‌شده'];
    if (d <= 1) return ['bad', 'تازه تمرین شده، ریکاوری نشده'];
    if (d <= 3) return ['warn', 'در حال ریکاوری'];
    if (d <= 6) return ['c6', 'نزدیک ریکاوری کامل'];
    return ['ok', 'ریکاوری کامل، آماده تمرین'];
  }
  function drawMap(id, side, last) {
    var svg = document.getElementById(id); if (!svg) return;
    svg.innerHTML = '';
    var groups = window.BODY_PATHS[side];
    Object.keys(groups).forEach(function (g) {
      var neutral = NEUTRAL_PARTS[g];
      var rc = neutral ? ['surface-3', ''] : recovery(last[g]);
      groups[g].forEach(function (d) {
        var p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        p.setAttribute('d', d);
        p.setAttribute('fill', C.color(rc[0]));
        p.setAttribute('stroke', C.color('surface'));
        p.setAttribute('stroke-width', '2');
        if (!neutral) {
          p.setAttribute('class', 'muscle'); p.setAttribute('tabindex', '0'); p.setAttribute('role', 'button');
          p.setAttribute('aria-label', (MUSCLE_FA[g] || g) + '، ' + rc[1]);
          var pick = function () {
            BH.$$('.muscle.sel').forEach(function (x) { x.classList.remove('sel'); });
            BH.$$('.muscle[data-m="' + g + '"]').forEach(function (x) { x.classList.add('sel'); });
            var dd = last[g], info = state.muscleInfo[g];
            $('#md').innerHTML = BH.icon('activity') + '<span><b>' + esc(MUSCLE_FA[g] || g) + '</b> — ' +
              (dd === undefined ? 'تمرینی ثبت نشده' : dd === 0 ? 'امروز تمرین شده' : n(dd) + ' روز پیش تمرین شده') +
              ' <span class="badge ' + (rc[0] === 'bad' ? 'bad' : rc[0] === 'warn' ? 'warn' : rc[0] === 'ok' ? 'ok' : '') + '">' + rc[1] + '</span>' +
              (info && info.kind ? '<br><span class="muted">نوع جلسه: ' + esc(info.kind) + (info.notes ? ' — ' + esc(info.notes) : '') + '</span>' : '') + '</span>';
          };
          p.addEventListener('click', pick);
          p.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(); } });
        }
        p.setAttribute('data-m', g);
        svg.appendChild(p);
      });
    });
  }
  function renderGym() {
    var S = state.cur, P = state.prev, R = state.raw;
    var sess = vals(S.workout_min).filter(function (v) { return v > 0; }), sessP = vals(P.workout_min).filter(function (v) { return v > 0; });
    mountKpis('gymKpis', [
      { label: 'روزهای ورزش', icon: 'dumbbell', tone: 't-warn', value: n(sess.length), unit: 'از ' + n(state.days), delta: BH.delta(sess.length, sessP.length) },
      { label: 'مجموع زمان', icon: 'clock', tone: 't-info', value: BH.minutes(sum(S.workout_min)), unit: 'ساعت', delta: BH.delta(sum(S.workout_min), sum(P.workout_min)) },
      { label: 'کالری سوخته', icon: 'flame', tone: 't-bad', value: n(sum(S.workout_kcal)), unit: 'کالری', delta: BH.delta(sum(S.workout_kcal), sum(P.workout_kcal)) },
      { label: 'میانگین هر جلسه', icon: 'activity', value: n(avg(sess)), unit: 'دقیقه' }
    ]);
    var last = {}, info = {};
    Object.keys(R.muscle_last || {}).forEach(function (k) {
      var en = muscleKey(k); if (!en) return;
      var d = R.muscle_last[k].days_ago;
      if (last[en] === undefined || d < last[en]) { last[en] = d; info[en] = R.muscle_last[k]; }
    });
    state.muscleInfo = info;
    drawMap('mf', 'front', last); drawMap('mb', 'back', last);
    $('.rec-legend').innerHTML = [['bad', 'تازه تمرین'], ['warn', 'در حال ریکاوری'], ['c6', 'نزدیک ریکاوری'], ['ok', 'آماده'], ['surface-3', 'بدون ثبت']]
      .map(function (x) { return '<span><i style="background:var(--' + x[0] + ')"></i>' + x[1] + '</span>'; }).join('');
    $('#md').innerHTML = BH.icon('info') + '<span>روی هر عضله بزن تا وضعیت ریکاوری و آخرین تمرینش را ببینی.</span>';

    var vol = {};
    Object.keys(R.muscle_volume || {}).forEach(function (k) { var en = muscleKey(k); if (en) vol[en] = (vol[en] || 0) + R.muscle_volume[k]; });
    var vl = Object.keys(vol).map(function (k) { return [k, vol[k]]; }).sort(function (a, b) { return b[1] - a[1]; }).slice(0, 10);
    var mx = vl.length ? vl[0][1] : 1;
    $('#volBars').innerHTML = vl.length ? vl.map(function (x, i) {
      return '<div class="hbar"><span class="nm">' + esc(MUSCLE_FA[x[0]] || x[0]) + '</span><div class="progress"><i style="width:' + (x[1] / mx * 100) + '%;background:var(--c' + (i % 6 + 1) + ')"></i></div><span class="v">' + n(x[1]) + '</span></div>';
    }).join('') : BH.empty('هنوز تمرینی با عضله ثبت نشده', 'dumbbell');

    C.bar('cGym', { labels: labels(), tipLabels: tipLabels(), data: S.workout_min, name: 'دقیقه', color: 'c3', height: 220,
      fmt: function (v) { return n(v) + ' دقیقه'; }, extra: [{ data: S.workout_kcal, name: 'کالری سوخته', color: 'c5', fmt: function (v) { return v ? n(v) + ' کالری' : '—'; } }] });
    $('#gymTable').innerHTML = table(['تاریخ', 'نوع', { t: 'مدت', end: 1 }, { t: 'کالری', end: 1 }, 'عضلات', 'حرکات'],
      (R.workouts || []).map(function (w) {
        return '<tr><td>' + BH.date(w.d, 'weekday') + '</td><td><b>' + esc(w.kind) + '</b></td><td class="end num">' + n(w.duration_min) + ' دقیقه</td><td class="end num">' + n(w.kcal) +
          '</td><td>' + (w.muscles || []).map(function (m) { var en = muscleKey(m); return '<span class="badge">' + esc(en ? MUSCLE_FA[en] : m) + '</span>'; }).join(' ') +
          '</td><td class="muted">' + (w.sets || []).map(function (s) { return esc(s.exercise) + ' ' + BH.fa(s.sets + '×' + s.reps) + (s.weight_kg ? ' @' + n(s.weight_kg) + 'kg' : ''); }).join('، ') + '</td></tr>';
      }), { empty: 'هنوز جلسه ورزشی ثبت نشده', icon: 'dumbbell' });
  }

  /* ---------- بدن ---------- */
  function renderBody() {
    var body = (state.raw.body || []).slice().reverse();
    var L = body.map(function (b) { return BH.date(b.d, 'short'); }), TL = body.map(function (b) { return BH.date(b.d, 'weekday'); });
    var f = body[0] || {}, l = body[body.length - 1] || {};
    function ch(k, d, invert) {
      if (body.length < 2 || !l[k] || !f[k]) return '';
      var diff = l[k] - f[k], good = invert ? diff <= 0 : diff >= 0;
      return '<span class="delta ' + (Math.abs(diff) < 0.05 ? 'flat' : good ? 'up' : 'down') + '">' + (diff > 0 ? '+' : diff < 0 ? '−' : '') + n(Math.abs(diff), d) + '</span>';
    }
    var bmi = l.bmi, bmiTxt = !bmi ? '' : bmi < 18.5 ? 'کم‌وزن' : bmi < 25 ? 'طبیعی' : bmi < 30 ? 'اضافه‌وزن' : 'چاق';
    mountKpis('bodyKpis', [
      { label: 'وزن', icon: 'scale', tone: 't-finance', value: l.weight_kg ? n(l.weight_kg, 1) : '—', unit: 'کیلوگرم', delta: ch('weight_kg', 1, true), sub: body.length > 1 ? 'از ' + BH.date(f.d, 'short') : '' },
      { label: 'چربی بدن', icon: 'droplet', tone: 't-warn', value: l.body_fat_pct ? n(l.body_fat_pct, 1) + '٪' : '—', delta: ch('body_fat_pct', 1, true) },
      { label: 'چربی احشایی', icon: 'shield', tone: (l.visceral_fat || 0) >= 12 ? 't-bad' : 't-ok', value: l.visceral_fat ? n(l.visceral_fat) : '—', sub: l.visceral_fat ? (l.visceral_fat >= 12 ? 'بالاتر از آستانه خطر' : 'در محدوده ایمن') : '' },
      { label: 'شاخص توده بدنی', icon: 'target', tone: 't-info', value: bmi ? n(bmi, 1) : '—', sub: bmiTxt },
      { label: 'عضله', icon: 'dumbbell', value: l.muscle_pct ? n(l.muscle_pct, 1) + '٪' : (l.muscle_kg ? n(l.muscle_kg, 1) : '—'), unit: l.muscle_pct ? '' : 'کیلوگرم', delta: ch('muscle_pct', 1) },
      { label: 'آب بدن', icon: 'droplet', tone: 't-info', value: l.water_pct ? n(l.water_pct, 1) + '٪' : '—', delta: ch('water_pct', 1) }
    ]);
    $('#wtSub').textContent = body.length ? n(body.length) + ' اندازه‌گیری آخر' : 'هنوز اندازه‌گیری ثبت نشده';
    if (!body.length) { ['cWeight', 'cComp', 'cVisceral'].forEach(function (id) { $('#' + id).innerHTML = BH.empty('با ترازوی بدن‌سنج اندازه بگیر و به ایجنت بگو', 'scale'); }); return; }
    C.line('cWeight', { labels: L, tipLabels: TL, autoMin: true, height: 240, yFmt: function (v) { return n(v, 1); },
      series: [{ name: 'وزن', data: body.map(function (b) { return nz(b.weight_kg); }), color: 'c1', fmt: function (v) { return n(v, 1) + ' کیلوگرم'; } }] });
    C.line('cComp', { labels: L, tipLabels: TL, autoMin: true, height: 220,
      series: [{ name: 'چربی بدن', data: body.map(function (b) { return nz(b.body_fat_pct); }), color: 'c3', fill: false, fmt: function (v) { return n(v, 1) + '٪'; } },
        { name: 'عضله', data: body.map(function (b) { return nz(b.muscle_pct); }), color: 'c2', dash: true, fill: false, fmt: function (v) { return n(v, 1) + '٪'; } }] });
    C.line('cVisceral', { labels: L, tipLabels: TL, yMin: 0, height: 220, target: { value: 12, label: 'آستانه خطر' },
      series: [{ name: 'چربی احشایی', data: body.map(function (b) { return nz(b.visceral_fat); }), color: 'c5' }] });
  }

  /* ---------- ذهن ---------- */
  function renderMind() {
    var S = state.cur, P = state.prev, R = state.raw, m = R.mood_today || {};
    var pd = sum(S.prayers_done), pdP = sum(P.prayers_done);
    mountKpis('mindKpis', [
      { label: 'خلق', icon: 'smile', tone: 't-info', value: m.mood !== undefined ? n(m.mood) : '—', unit: 'از ۱۰', delta: BH.delta(avg(S.mood.map(nz)), avg(P.mood.map(nz))), sub: 'میانگین ' + n(avg(S.mood.map(nz)), 1), spark: 'mood', sparkColor: 'c4' },
      { label: 'استرس', icon: 'zap', tone: 't-bad', value: m.stress !== undefined ? n(m.stress) : '—', unit: 'از ۱۰', delta: BH.delta(avg(S.stress.map(nz)), avg(P.stress.map(nz)), { invert: true }), sub: 'میانگین ' + n(avg(S.stress.map(nz)), 1), spark: 'stress', sparkColor: 'c5' },
      { label: 'انرژی', icon: 'activity', tone: 't-warn', value: m.energy !== undefined ? n(m.energy) : '—', unit: 'از ۱۰', delta: BH.delta(avg(S.energy.map(nz)), avg(P.energy.map(nz))), sub: 'میانگین ' + n(avg(S.energy.map(nz)), 1), spark: 'energy', sparkColor: 'c3' },
      { label: 'نماز در این بازه', icon: 'pray', value: n(pd), unit: 'از ' + n(state.days * 5), delta: BH.delta(pd, pdP), progress: pd / (state.days * 5) * 100, progressTone: 'ok' }
    ], { mood: S.mood.map(nz), stress: S.stress.map(nz), energy: S.energy.map(nz) });
    C.line('cMind', { labels: labels(), tipLabels: tipLabels(), yMin: 0, yMax: 10, height: 240,
      series: [{ name: 'خلق', data: S.mood.map(nz), color: 'c4', fill: false }, { name: 'استرس', data: S.stress.map(nz), color: 'c5', dash: true, fill: false },
        { name: 'انرژی', data: S.energy.map(nz), color: 'c3', dash: true, fill: false }] });
    var pts = [];
    S.days.forEach(function (d, i) {
      if (S.sleep_hours[i] && S.mood[i]) pts.push({ x: S.sleep_hours[i], y: S.mood[i], label: BH.date(d, 'weekday'),
        color: S.mood[i] >= 7 ? 'ok' : S.mood[i] >= 5 ? 'warn' : 'bad',
        rows: [{ name: 'خواب', value: BH.hm(S.sleep_hours[i]) }, { name: 'خلق', value: n(S.mood[i]) + ' از ۱۰' }] });
    });
    if (pts.length) C.scatter('cSleepMood', { points: pts, xMin: Math.floor(Math.min.apply(null, pts.map(function (p) { return p.x; })) - 0.5),
      xMax: Math.ceil(Math.max.apply(null, pts.map(function (p) { return p.x; })) + 0.5), yMin: 0, yMax: 10, trend: true, xTitle: 'ساعت خواب', yTitle: 'خلق', height: 240 });
    else $('#cSleepMood').innerHTML = BH.empty('برای این نمودار خواب و خلق را با هم ثبت کن', 'smile');
    C.bar('cPrayer', { labels: labels(), tipLabels: tipLabels(), data: S.prayers_done, name: 'نماز', yMax: 5, ticks: 5, height: 240,
      fmt: function (v) { return n(v) + ' از ۵'; }, colorFn: function (v) { return v >= 5 ? 'ok' : v >= 3 ? 'warn' : 'bad'; } });
  }

  /* ---------- اسکرین‌تایم ---------- */
  function renderScreen() {
    var S = state.cur, P = state.prev, T = tgt(), li = S.days.length - 1;
    var t = S.screen_total[li] || 0, ig = S.screen_instagram[li] || 0;
    var other = S.screen_total.map(function (v, i) { return Math.max(0, (v || 0) - (S.screen_instagram[i] || 0) - (S.screen_telegram[i] || 0)); });
    mountKpis('screenKpis', [
      { label: 'امروز', icon: 'phone', tone: t > T.screen_total_min ? 't-bad' : 't-finance', value: BH.minutes(t), unit: 'ساعت', sub: 'هدف زیر ' + BH.minutes(T.screen_total_min),
        progress: T.screen_total_min ? t / T.screen_total_min * 100 : 0, progressTone: t > T.screen_total_min ? 'bad' : 'ok' },
      { label: 'اینستاگرام امروز', icon: 'smile', tone: ig > T.screen_instagram_min ? 't-bad' : 't-info', value: BH.minutes(ig), unit: 'ساعت', sub: 'هدف زیر ' + BH.minutes(T.screen_instagram_min),
        progress: T.screen_instagram_min ? ig / T.screen_instagram_min * 100 : 0, progressTone: ig > T.screen_instagram_min ? 'bad' : 'ok' },
      { label: 'میانگین روزانه', icon: 'clock', tone: 't-warn', value: BH.minutes(avg(S.screen_total.map(nz))), unit: 'ساعت', delta: BH.delta(avg(S.screen_total.map(nz)), avg(P.screen_total.map(nz)), { invert: true }), spark: 'tot', sparkColor: 'c5' },
      { label: 'باز کردن قفل', icon: 'key', value: n(avg(S.unlocks.map(nz))), unit: 'در روز', delta: BH.delta(avg(S.unlocks.map(nz)), avg(P.unlocks.map(nz)), { invert: true }), sub: n(avg(S.notifications.map(nz))) + ' اعلان در روز' }
    ], { tot: S.screen_total.map(nz) });
    var fm = function (v) { return BH.minutes(v); };
    C.stack('cScreen', { labels: labels(), tipLabels: tipLabels(), height: 250, target: T.screen_total_min, fmt: fm, yFmt: function (v) { return BH.n(v / 60, 1) + 'h'; },
      series: [{ name: 'اینستاگرام', data: S.screen_instagram, color: 'c5' }, { name: 'تلگرام', data: S.screen_telegram, color: 'c1' }, { name: 'سایر', data: other, color: 'c6' }] });
    C.line('cInsta', { labels: labels(), tipLabels: tipLabels(), target: T.screen_instagram_min, height: 220, fmt: fm,
      series: [{ name: 'اینستاگرام', data: S.screen_instagram.map(nz), color: 'c5' }] });
    C.line('cUnlock', { labels: labels(), tipLabels: tipLabels(), height: 220,
      series: [{ name: 'باز کردن قفل', data: S.unlocks.map(nz), color: 'c1', fill: false }, { name: 'اعلان', data: S.notifications.map(nz), color: 'c3', dash: true, fill: false }] });
  }

  /* ---------- پایبندی ---------- */
  var DIMS = [['kcal', 'کالری'], ['protein', 'پروتئین'], ['sleep', 'خواب'], ['workout', 'ورزش'], ['prayer', 'نماز'], ['screen', 'اسکرین'], ['water', 'آب']];
  function renderAdhere() {
    var S = state.cur, P = state.prev;
    var parts = S.days.map(function (_, i) { return dayParts(i, S); });
    var sc = scores(S), scP = scores(P);
    var dimAvg = DIMS.map(function (d) { return [d[1], avg(parts.map(function (p) { return p[d[0]] === undefined ? null : p[d[0]]; }))]; }).filter(function (x) { return x[1] !== null; });
    dimAvg.sort(function (a, b) { return b[1] - a[1]; });
    var best = -1, bi = -1; sc.forEach(function (v, i) { if (v !== null && v > best) { best = v; bi = i; } });
    mountKpis('adhKpis', [
      { label: 'پایبندی این بازه', icon: 'target', value: avg(sc) === null ? '—' : BH.pct(avg(sc)), delta: BH.delta(avg(sc), avg(scP)), progress: avg(sc) || 0, progressTone: 'ok', spark: 'sc', sparkColor: 'health' },
      { label: 'قوی‌ترین شاخص', icon: 'award', tone: 't-ok', value: dimAvg.length ? dimAvg[0][0] : '—', sub: dimAvg.length ? BH.pct(dimAvg[0][1] * 100) + ' از هدف' : '' },
      { label: 'ضعیف‌ترین شاخص', icon: 'alert', tone: 't-warn', value: dimAvg.length ? dimAvg[dimAvg.length - 1][0] : '—', sub: dimAvg.length ? BH.pct(dimAvg[dimAvg.length - 1][1] * 100) + ' از هدف' : '' },
      { label: 'بهترین روز', icon: 'sparkles', tone: 't-finance', value: bi >= 0 ? BH.date(S.days[bi], 'short') : '—', sub: bi >= 0 ? 'امتیاز ' + n(best) : '' }
    ], { sc: sc });
    var N = S.days.length, step = Math.ceil(N / 16);
    var h = '<div class="heat-grid" style="grid-template-columns:repeat(' + N + ',minmax(' + (N > 45 ? 10 : 16) + 'px,1fr)) auto">';
    DIMS.forEach(function (d) {
      parts.forEach(function (p, i) {
        var v = p[d[0]];
        h += '<span class="cell" style="opacity:' + (v === undefined ? 0.08 : (0.15 + 0.85 * v).toFixed(2)) + '" title="' + esc(BH.date(S.days[i], 'short') + ' — ' + d[1] + ': ' + (v === undefined ? 'بدون داده' : BH.pct(v * 100))) + '"></span>';
      });
      h += '<span class="rl">' + d[1] + '</span>';
    });
    S.days.forEach(function (dd, i) { h += '<span class="cl">' + ((N - 1 - i) % step === 0 ? BH.date(dd, 'short').split(' ')[0] : '') + '</span>'; });
    h += '<span></span></div><div class="heat-scale">کم<i style="opacity:.15"></i><i style="opacity:.45"></i><i style="opacity:.75"></i><i></i>زیاد</div>';
    $('#heat').innerHTML = h;
    C.line('cScore', { labels: labels(), tipLabels: tipLabels(), yMin: 0, yMax: 100, target: { value: 75, label: 'هدف ۷۵' }, targetColor: 'muted', height: 230,
      series: [{ name: 'امتیاز', data: sc, color: 'health', fmt: function (v) { return n(v) + ' از ۱۰۰'; } }] });
  }

  /* ---------- مزاج ---------- */
  function tLabel(v, neg, pos) {
    if (v === null || v === undefined) return '—';
    if (Math.abs(v) < 0.1) return 'متعادل';
    return n(Math.abs(v), 2) + ' ' + (v < 0 ? neg : pos);
  }
  function plane(host, items, base) {
    var W = 520, H = 420, cx = W / 2, cy = H / 2 - 4, R = 165, NS = 'http://www.w3.org/2000/svg';
    host.innerHTML = '';
    var s = document.createElementNS(NS, 'svg');
    s.setAttribute('viewBox', '0 0 ' + W + ' ' + H); s.setAttribute('role', 'img'); s.setAttribute('aria-label', 'صفحه مزاج دو محوره');
    host.appendChild(s);
    function E(t, a) { var e = document.createElementNS(NS, t); for (var k in a) e.setAttribute(k, a[k]); s.appendChild(e); return e; }
    function T(x, y, txt, o) { o = o || {}; var e = E('text', { x: x, y: y, 'text-anchor': o.a || 'middle', direction: 'rtl', 'font-size': o.size || 14, fill: o.fill || C.color('c-axis'), 'font-weight': o.w || 500 }); e.textContent = txt; return e; }
    var P2 = function (cw, dw) { return [cx + clamp(cw, -1.2, 1.2) * R, cy - clamp(dw, -1.2, 1.2) * R]; };
    E('rect', { x: cx - R, y: cy - R, width: R * 2, height: R * 2, rx: 18, fill: C.color('surface-3'), opacity: .55 });
    var qs = [[1, 1, 'گرم و خشک'], [-1, 1, 'سرد و خشک'], [-1, -1, 'سرد و تر'], [1, -1, 'گرم و تر']];
    qs.forEach(function (q) { T(cx + q[0] * R * 0.62, cy - q[1] * R * 0.82, q[2], { fill: C.color('faint'), size: 13 }); });
    E('line', { x1: cx, y1: cy - R, x2: cx, y2: cy + R, stroke: C.color('border'), 'stroke-width': 1.2 });
    E('line', { x1: cx - R, y1: cy, x2: cx + R, y2: cy, stroke: C.color('border'), 'stroke-width': 1.2 });
    E('ellipse', { cx: cx, cy: cy, rx: 54, ry: 44, fill: C.color('ok'), opacity: .14 });
    T(cx, cy + 5, 'ناحیه تعادل', { fill: C.color('ok'), size: 13, w: 600 });
    T(cx + R + 12, cy + 4, 'گرمی', { a: 'end' }); T(cx - R - 12, cy + 4, 'سردی', { a: 'start' });
    T(cx, cy - R - 10, 'خشکی'); T(cx, cy + R + 20, 'تری');
    var defs = E('defs', {}), mk = document.createElementNS(NS, 'marker');
    [['id', 'tpArr'], ['markerWidth', 7], ['markerHeight', 7], ['refX', 5], ['refY', 3.5], ['orient', 'auto'], ['markerUnits', 'strokeWidth']].forEach(function (a) { mk.setAttribute(a[0], a[1]); });
    var mp = document.createElementNS(NS, 'path'); mp.setAttribute('d', 'M0,0 L7,3.5 L0,7 z'); mp.setAttribute('fill', C.color('c4')); mk.appendChild(mp); defs.appendChild(mk);
    var bv = base || { cold_warm: 0, dry_wet: 0 }, bp = P2(bv.cold_warm, bv.dry_wet);
    var ac = bv.cold_warm, ad = bv.dry_wet;
    (items || []).forEach(function (it) {
      var q = Math.max(+it.quantity || 0, 0), w = q > 0 ? Math.log1p(q) / Math.log1p(250) : 0.1;
      var nx = ac + (+it.cold_warm || 0) * w, ny = ad + (+it.dry_wet || 0) * w, a = P2(ac, ad), b = P2(nx, ny);
      var ln = E('line', { x1: a[0], y1: a[1], x2: b[0], y2: b[1], stroke: C.color('c4'), 'stroke-width': 2, 'marker-end': 'url(#tpArr)', style: 'cursor:pointer' });
      ln.addEventListener('pointermove', function (e) {
        C.showTip(C.tipRows(it.name, [{ name: 'سردی/گرمی', value: tLabel(it.cold_warm, 'سرد', 'گرم'), color: C.color('c3') },
          { name: 'تری/خشکی', value: tLabel(it.dry_wet, 'تر', 'خشک'), color: C.color('c1') }]), e.clientX, e.clientY);
      });
      ln.addEventListener('pointerleave', C.hideTip);
      ac = nx; ad = ny;
    });
    E('circle', { cx: bp[0], cy: bp[1], r: 8, fill: C.color('surface'), stroke: C.color('text'), 'stroke-width': 2.2 });
    var cpPre = P2(ac, ad), below = cpPre[1] <= bp[1];
    T(bp[0] + 14, bp[1] + 5, 'مزاج پایه', { a: 'end', fill: C.color('text'), size: 13, w: 600 });
    var cp = P2(ac, ad);
    E('circle', { cx: cp[0], cy: cp[1], r: 14, fill: C.color('c4'), opacity: .2 });
    E('circle', { cx: cp[0], cy: cp[1], r: 8, fill: C.color('c4') });
    T(cp[0], cp[1] + (below ? -20 : 30), 'نقطه کنونی', { fill: C.color('c4'), size: 13, w: 700 });
  }
  function renderTemp() {
    var S = state.cur, TP = state.raw.temperament || {}, td = TP.today || {}, base = TP.base || {};
    mountKpis('tempKpis', [
      { label: 'مزاج امروز', icon: 'thermo', tone: 't-warn', value: esc(td.label || 'بدون داده'), sub: td.items ? n(td.items) + ' قلم با بردار' : '' },
      { label: 'سردی / گرمی', icon: 'sun', tone: 't-bad', value: tLabel(td.cold_warm, 'سرد', 'گرم'), sub: 'بازه −۱ تا +۱' },
      { label: 'تری / خشکی', icon: 'droplet', tone: 't-info', value: tLabel(td.dry_wet, 'تر', 'خشک'), sub: 'بازه −۱ تا +۱' },
      { label: 'مزاج پایه', icon: 'compass', tone: 't-finance', value: esc(base.constitution || (base.set ? 'ثبت شده' : 'ثبت نشده')),
        sub: base.set ? tLabel(base.cold_warm, 'سرد', 'گرم') + '، ' + tLabel(base.dry_wet, 'تر', 'خشک') : 'با پرسشنامه ایجنت تعیین کن' }
    ]);
    var drawPlane = function () { plane($('#cPlane'), TP.items, base.set ? base : null); };
    drawPlane(); $('#cPlane')._bhDraw = drawPlane;
    tempDays();
    var all = vals(S.temp_cold_warm.concat(S.temp_dry_wet)).map(Math.abs), lim = Math.max(0.3, Math.ceil((Math.max.apply(null, all.concat([0])) * 1.3) * 10) / 10);
    C.line('cTempLine', { labels: labels(), tipLabels: tipLabels(), yMin: -lim, yMax: lim, height: 220, yFmt: function (v) { return n(v, 1); },
      series: [{ name: 'سردی/گرمی', data: S.temp_cold_warm, color: 'c3', fill: false, fmt: function (v) { return tLabel(v, 'سرد', 'گرم'); } },
        { name: 'تری/خشکی', data: S.temp_dry_wet, color: 'c1', dash: true, fill: false, fmt: function (v) { return tLabel(v, 'تر', 'خشک'); } }] });
    $('#tempItemsSub').textContent = n((TP.items || []).length) + ' قلم';
    $('#tempTable').innerHTML = table(['قلم', 'وعده', 'مقدار', 'سردی / گرمی', 'تری / خشکی', 'منبع'], (TP.items || []).map(function (it) {
      var src = it.source || '', cls = src === 'ثبت‌شده' ? 'info' : src.indexOf('تأییدنشده') >= 0 ? 'warn' : 'ok';
      return '<tr><td><b>' + esc(it.name) + '</b></td><td>' + esc(SLOT[it.slot] || it.slot || '') + '</td><td class="num">' + n(it.quantity, 1) + ' ' + esc(UNIT[it.unit] || it.unit || '') +
        '</td><td><span class="badge ' + (it.cold_warm > 0.1 ? 'bad' : it.cold_warm < -0.1 ? 'info' : '') + '">' + tLabel(it.cold_warm, 'سرد', 'گرم') + '</span></td><td><span class="badge ' +
        (it.dry_wet > 0.1 ? 'warn' : it.dry_wet < -0.1 ? 'primary' : '') + '">' + tLabel(it.dry_wet, 'تر', 'خشک') + '</span></td><td><span class="badge ' + cls + '">' + esc(src) + '</span></td></tr>';
    }), { empty: 'امروز قلمی با بردار مزاج ثبت نشده', icon: 'thermo' });
  }
  function tempDays() {
    var S = state.cur, pts = [];
    S.days.forEach(function (d, i) {
      var cw = S.temp_cold_warm[i], dw = S.temp_dry_wet[i];
      if (!cw && !dw) return;
      var by = state.tpColor, v, color = 'faint', rows = [{ name: 'سردی/گرمی', value: tLabel(cw, 'سرد', 'گرم') }, { name: 'تری/خشکی', value: tLabel(dw, 'تر', 'خشک') }];
      if (by === 'mood') { v = S.mood[i]; if (v) color = v >= 7 ? 'ok' : v >= 5 ? 'warn' : 'bad'; rows.push({ name: 'خلق', value: v ? n(v) + ' از ۱۰' : '—' }); }
      if (by === 'sleep') { v = S.sleep_hours[i]; if (v) color = v >= 7 ? 'ok' : v >= 6 ? 'warn' : 'bad'; rows.push({ name: 'خواب', value: v ? BH.hm(v) : '—' }); }
      if (by === 'screen') { v = S.screen_total[i]; if (v) color = v <= 240 ? 'ok' : v <= 360 ? 'warn' : 'bad'; rows.push({ name: 'اسکرین', value: v ? BH.minutes(v) : '—' }); }
      pts.push({ x: cw, y: dw, color: color, label: BH.date(d, 'weekday'), rows: rows, r: 7 });
    });
    if (!pts.length) { $('#cTempDays').innerHTML = BH.empty('هنوز روزی با بردار مزاج نداری', 'thermo'); return; }
    var lim = Math.max(0.3, Math.ceil(Math.max.apply(null, pts.map(function (p) { return Math.max(Math.abs(p.x), Math.abs(p.y)); })) * 13) / 10);
    C.scatter('cTempDays', { points: pts, xMin: -lim, xMax: lim, yMin: -lim, yMax: lim, xTitle: 'افقی: سردی (چپ) تا گرمی (راست) — عمودی: تری تا خشکی', yTitle: 'تری/خشکی', height: 300 });
  }

  /* ---------- تب‌ها و رویدادها ---------- */
  var RENDER = { today: renderToday, food: renderFood, sleep: renderSleep, gym: renderGym, body: renderBody, mind: renderMind, screen: renderScreen, adhere: renderAdhere, temp: renderTemp };
  function renderTab(t) {
    if (!state.cur || state.rendered[t]) return;
    state.rendered[t] = true;
    try { RENDER[t](); } catch (e) { console.error(e); }
  }
  function showTab(t, push) {
    if (!RENDER[t]) t = 'today';
    state.tab = t;
    BH.$$('#tabs .tab').forEach(function (b) { b.setAttribute('aria-selected', String(b.getAttribute('data-t') === t)); });
    BH.$$('.panel').forEach(function (p) { p.classList.toggle('active', p.id === t); });
    renderTab(t);
    if (push !== false) try { history.replaceState(null, '', '#' + t); } catch (e) {}
  }
  BH.$$('#tabs .tab').forEach(function (b) {
    b.addEventListener('click', function () { showTab(b.getAttribute('data-t')); });
    b.addEventListener('keydown', function (e) {
      if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
      var tabs = BH.$$('#tabs .tab'), i = tabs.indexOf(b) + (e.key === 'ArrowLeft' ? 1 : -1);
      var nx = tabs[(i + tabs.length) % tabs.length]; nx.focus(); showTab(nx.getAttribute('data-t'));
    });
  });
  BH.$$('#range button').forEach(function (b) {
    b.setAttribute('aria-pressed', String(+b.getAttribute('data-days') === state.days));
    b.addEventListener('click', function () {
      state.days = +b.getAttribute('data-days');
      try { localStorage.setItem('behoosh_health_days', state.days); } catch (e) {}
      BH.$$('#range button').forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); });
      load();
    });
  });
  BH.$$('#tpColor button').forEach(function (b) {
    b.addEventListener('click', function () {
      state.tpColor = b.getAttribute('data-c');
      BH.$$('#tpColor button').forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); });
      tempDays();
    });
  });

  /* ---------- خروجی CSV ---------- */
  $('#btnExport').innerHTML = BH.icon('download');
  $('#btnExport').addEventListener('click', function () {
    if (!state.cur) return;
    var S = state.cur, cols = ['date'].concat(SERIES);
    var lines = [cols.join(',')].concat(S.days.map(function (d, i) {
      return [d].concat(SERIES.map(function (k) { var v = S[k][i]; return v === null || v === undefined ? '' : Math.round(v * 100) / 100; })).join(',');
    }));
    var blob = new Blob(['﻿' + lines.join('\n')], { type: 'text/csv;charset=utf-8' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = 'behoosh-health-' + BH.todayISO() + '.csv';
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
    BH.toast('فایل CSV دانلود شد', 'download');
  });

  /* ---------- ثبت سریع ---------- */
  var sheet = $('#logSheet');
  $('#btnLog').innerHTML = BH.icon('plus') + '<span>ثبت سریع</span>';
  $('#logClose').innerHTML = BH.icon('x');
  $('#tempWarnIcon').outerHTML = BH.icon('alert');
  function outSync() { ['Mood', 'Stress', 'Energy'].forEach(function (k) { $('#o' + k).textContent = n(+$('#f' + k).value); }); }
  ['fMood', 'fStress', 'fEnergy'].forEach(function (id) { $('#' + id).addEventListener('input', outSync); });
  BH.$$('[data-step]').forEach(function (b) {
    b.addEventListener('click', function () { var i = $('#fWater'); i.value = Math.max(0, Math.round(((+i.value || 0) + +b.getAttribute('data-step')) * 100) / 100); });
  });
  function openLog() {
    var R = state.raw || {}, h = R.habit_today || {}, m = R.mood_today || {}, sl = (R.sleep_log || [])[0], today = R.today || BH.todayISO();
    var slToday = sl && sl.d === today ? sl : null;
    $('#fWater').value = h.water_liters || 0;
    $('#fMood').value = m.mood !== undefined ? m.mood : 5; $('#fStress').value = m.stress !== undefined ? m.stress : 5; $('#fEnergy').value = m.energy !== undefined ? m.energy : 5;
    $('#fSleep').value = slToday ? slToday.hours : ''; $('#fSleepQ').value = slToday ? slToday.quality : '';
    var pt = R.prayers_today || {};
    $('#fPrayers').innerHTML = PRAY.map(function (p) {
      var on = pt[p[0]] === 'done' || pt[p[0]] === 'late';
      return '<button type="button" data-p="' + p[0] + '" aria-pressed="' + on + '">' + BH.icon('check') + p[1] + '</button>';
    }).join('');
    BH.$$('#fPrayers button').forEach(function (b) { b.addEventListener('click', function () { b.setAttribute('aria-pressed', String(b.getAttribute('aria-pressed') !== 'true')); }); });
    sheet._initial = JSON.stringify(collect());
    outSync();
    sheet.showModal();
  }
  function collect() {
    return { water: +$('#fWater').value || 0, mood: +$('#fMood').value, stress: +$('#fStress').value, energy: +$('#fEnergy').value,
      sleep: $('#fSleep').value === '' ? null : +$('#fSleep').value, sleepQ: $('#fSleepQ').value === '' ? null : +$('#fSleepQ').value,
      prayers: BH.$$('#fPrayers button').map(function (b) { return [b.getAttribute('data-p'), b.getAttribute('aria-pressed') === 'true']; }) };
  }
  $('#btnLog').addEventListener('click', openLog);
  $('#logCancel').addEventListener('click', function () { sheet.close(); });
  $('#logClose').addEventListener('click', function () { sheet.close(); });
  $('#logForm').addEventListener('submit', async function (e) {
    e.preventDefault();
    var R = state.raw || {}, today = R.today || BH.todayISO(), v = collect(), init = JSON.parse(sheet._initial || '{}');
    var h = R.habit_today || {}, m = R.mood_today || {}, pt = R.prayers_today || {}, jobs = [];
    if (v.water !== init.water) jobs.push(['/log_habit', { log_date: today, water_liters: v.water, breathing_done: !!h.breathing_done, supplements: h.supplements || [], teas: h.teas || [] }]);
    if (v.mood !== init.mood || v.stress !== init.stress || v.energy !== init.energy) jobs.push(['/log_mood', { log_date: today, mood: v.mood, stress: v.stress, energy: v.energy, note: m.note || null }]);
    if (v.sleep !== null && (v.sleep !== init.sleep || v.sleepQ !== init.sleepQ)) {
      var sl = (R.sleep_log || [])[0], keep = sl && sl.d === today ? sl : {};
      jobs.push(['/log_sleep', { log_date: today, main_hours: v.sleep, quality: v.sleepQ || 0, bedtime: keep.bedtime || null, wake_time: keep.wake_time || null, nap_min: keep.nap_min || 0, wake_count: keep.wake_count || 0 }]);
    }
    v.prayers.forEach(function (p) {
      var was = pt[p[0]] === 'done' || pt[p[0]] === 'late';
      if (p[1] !== was) jobs.push(['/log_prayer', { log_date: today, prayer: p[0], status: p[1] ? 'done' : 'missed' }]);
    });
    if (!jobs.length) { sheet.close(); return; }
    var btn = $('#logSave'); btn.disabled = true;
    try {
      for (var i = 0; i < jobs.length; i++) await BH.api(jobs[i][0], { body: jobs[i][1] });
      sheet.close(); BH.toast('ثبت شد'); load();
    } catch (err) {
      BH.toast(err.status === 403 ? 'این توکن اجازه ثبت ندارد' : 'ثبت ناموفق بود: ' + err.message, 'alert');
    } finally { btn.disabled = false; }
  });

  window.addEventListener('themechange', function () {
    var host = $('#cPlane'); if (host && host._bhDraw && state.rendered.temp) host._bhDraw();
    if (state.rendered.gym) renderGym();
  });

  showTab((location.hash || '#today').slice(1), false);
  load();
})();
