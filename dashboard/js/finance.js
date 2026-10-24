/* بهوش — داشبورد مالی
   بازه‌ها شمسی‌اند: شروع هر ماه شمسی از /finance/cashflow خوانده می‌شود تا در مرورگر
   تبدیل تقویم لازم نباشد. همه مبالغ تومان‌اند. */
(function () {
  'use strict';
  if (!BH.requireAuth()) return;
  var $ = BH.$, $$ = BH.$$, esc = BH.esc;

  var S = {
    months: [], period: null, range: null, prevRange: null,
    summary: null, prevSummary: null, accounts: [], liab: null, budgets: [],
    cats: [], txs: [], recent: [], raw: [], audit: [], kind: 'all', q: ''
  };

  /* ---------- کمک‌تابع‌ها ---------- */
  function addDays(iso, n) {
    var d = new Date(iso + 'T12:00:00Z'); d.setUTCDate(d.getUTCDate() + n);
    return d.toISOString().slice(0, 10);
  }
  function daysBetween(a, b) { return Math.round((new Date(b + 'T12:00:00Z') - new Date(a + 'T12:00:00Z')) / 864e5); }
  function toman(v, compact) { return BH.money(v, compact) + ' تومان'; }
  function icons(root) {
    $$('[data-ic]', root).forEach(function (s) { s.innerHTML = BH.icon(s.getAttribute('data-ic')); s.removeAttribute('data-ic'); });
  }
  function skel(n, h) {
    var o = ''; for (var i = 0; i < n; i++) o += '<div class="skeleton" style="height:' + (h || 44) + 'px;margin:8px 0;border-radius:12px"></div>';
    return o;
  }
  function kindOf(t) { return t.kind || (t.direction === 'debit' ? 'expense' : 'income'); }
  var KIND = {
    expense: { fa: 'هزینه', ic: 'trend-down', cls: 'k-expense' },
    income: { fa: 'درآمد', ic: 'trend-up', cls: 'k-income' },
    transfer: { fa: 'انتقال', ic: 'swap', cls: 'k-transfer' }
  };
  function signedAmount(t) {
    var k = kindOf(t);
    if (k === 'income') return '<span class="amt in">+' + BH.money(t.amount) + '</span>';
    if (k === 'transfer') return '<span class="amt tr">' + BH.money(t.amount) + '</span>';
    return '<span class="amt out">−' + BH.money(t.amount) + '</span>';
  }

  /* ---------- بازه‌ها ---------- */
  function computeRange(p) {
    var m = S.months, today = BH.todayISO(), L = m.length - 1;
    if (L < 0) return { start: addDays(today, -29), end: today };
    switch (p) {
      case 'prev': return { start: m[Math.max(0, L - 1)].from, end: addDays(m[L].from, -1) };
      case 'q': return { start: m[Math.max(0, L - 2)].from, end: today };
      case 'year':
        for (var i = L; i >= 0; i--) if (/\/01$/.test(m[i].month)) return { start: m[i].from, end: today };
        return { start: m[0].from, end: today };
      default: return { start: m[L].from, end: today };
    }
  }
  function prevOf(r) {
    var len = daysBetween(r.start, r.end) + 1, pe = addDays(r.start, -1);
    return { start: addDays(pe, -(len - 1)), end: pe };
  }
  var PERIOD_FA = { month: 'این ماه', prev: 'ماه قبل', q: 'سه ماه اخیر', year: 'امسال' };

  /* ---------- بارگذاری ---------- */
  async function loadStatic() {
    var r = await Promise.all([
      BH.api('/finance/cashflow?months=12'),
      BH.api('/finance/accounts?active_only=true'),
      BH.api('/finance/liabilities'),
      BH.api('/finance/categories'),
      BH.api('/finance/budget'),
      BH.api('/finance/transactions?limit=6&start=' + addDays(BH.todayISO(), -365)),
      BH.api('/finance/raw?limit=50').catch(function () { return { messages: [] }; }),
      BH.api('/finance/audit?limit=50').catch(function () { return { audit: [] }; })
    ]);
    S.months = r[0].months || [];
    S.accounts = (r[1].accounts || []).filter(function (a) { return a.type !== 'income' && a.type !== 'expense'; });
    S.liab = r[2];
    S.cats = r[3].categories || [];
    S.budgets = r[4].budgets || [];
    S.recent = r[5].transactions || [];
    S.raw = r[6].messages || [];
    S.audit = r[7].audit || [];
  }
  async function loadPeriod() {
    S.range = computeRange(S.period);
    S.prevRange = prevOf(S.range);
    var q = function (r) { return 'start=' + r.start + '&end=' + r.end; };
    var r = await Promise.all([
      BH.api('/finance/summary?' + q(S.range)),
      BH.api('/finance/summary?' + q(S.prevRange)),
      BH.api('/finance/transactions?limit=500&' + q(S.range))
    ]);
    S.summary = r[0]; S.prevSummary = r[1]; S.txs = r[2].transactions || [];
    $('#fin-range').textContent = PERIOD_FA[S.period] + ': ' + BH.date(S.range.start) + ' تا ' + BH.date(S.range.end);
  }

  /* ---------- نمای کلی ---------- */
  function kpi(cls, label, icon, value, sub) {
    return '<div class="card kpi card-glow ' + cls + '"><div class="kpi-top"><span class="kpi-label">' + label + '</span>' +
      '<span class="kpi-icon">' + BH.icon(icon) + '</span></div><div class="kpi-value">' + value + '</div>' +
      '<div class="kpi-sub">' + sub + '</div></div>';
  }
  function big(v) {
    var a = Math.abs(v), s = v < 0 ? '−' : '';
    if (a >= 1e9) return s + BH.n(a / 1e9, 1) + '<small>میلیارد تومان</small>';
    if (a >= 1e6) return s + BH.n(a / 1e6, 1) + '<small>میلیون تومان</small>';
    return s + BH.n(a) + '<small>تومان</small>';
  }
  function renderKpis() {
    var s = S.summary, p = S.prevSummary;
    var rate = s.income ? s.net / s.income * 100 : null;
    var prate = p.income ? p.net / p.income * 100 : null;
    var assets = S.accounts.filter(function (a) { return a.type === 'asset'; })
      .reduce(function (t, a) { return t + a.balance; }, 0);
    var debt = S.liab ? S.liab.total_remaining || 0 : 0;
    var rateTxt = rate === null ? 'بدون درآمد در بازه'
      : 'نرخ پس‌انداز ' + BH.pct(rate) + (prate !== null ? ' <span class="muted">(قبل ' + BH.pct(prate) + ')</span>' : '');
    $('#k-over').innerHTML =
      kpi('t-ok', 'درآمد', 'trend-up', big(s.income),
        (BH.delta(s.income, p.income) || '') + '<span>نسبت به دوره قبل</span>') +
      kpi('t-bad', 'هزینه', 'receipt', big(s.expense),
        (BH.delta(s.expense, p.expense, { invert: true }) || '') + '<span>نسبت به دوره قبل</span>') +
      kpi(s.net >= 0 ? 't-finance' : 't-warn', 'خالص', 'piggy',
        '<span class="' + (s.net < 0 ? 'neg' : '') + '">' + big(s.net) + '</span>', rateTxt) +
      kpi('t-info', 'موجودی دارایی‌ها', 'bank', big(assets),
        debt ? 'مانده بدهی ' + BH.money(debt, true) : 'بدون بدهی فعال');
  }

  function renderInsights() {
    var s = S.summary, p = S.prevSummary, out = [];
    if (s.expense && s.by_category && s.by_category.length) {
      var top = s.by_category[0];
      out.push(['pie', 't-finance', '<b>' + esc(top.category) + '</b> بیشترین هزینه بازه است: ' +
        BH.pct(top.amount / s.expense * 100) + ' از کل، یعنی ' + toman(top.amount, true) + '.']);
    }
    if (p.expense && s.expense && S.period !== 'month') {
      var ch = (s.expense - p.expense) / p.expense * 100;
      out.push([ch > 0 ? 'trend-up' : 'trend-down', ch > 0 ? 't-warn' : 't-ok',
        'هزینه‌ها نسبت به دوره مشابه قبل <b>' + BH.pct(Math.abs(ch)) + (ch > 0 ? ' بیشتر' : ' کمتر') + '</b> شده است.']);
    }
    if (S.period === 'month' && S.months.length > 3) {
      var past = S.months.slice(-4, -1).map(function (m) { return m.expense; }).filter(Boolean);
      if (past.length) {
        var avg = past.reduce(function (a, b) { return a + b; }, 0) / past.length;
        var done = (daysBetween(S.range.start, S.range.end) + 1) / 30;
        var pace = s.expense / Math.max(done, 0.1);
        out.push([pace > avg ? 'alert' : 'check', pace > avg ? 't-warn' : 't-ok',
          'با این روند، هزینه این ماه حدود <b>' + toman(pace, true) + '</b> می‌شود؛ میانگین سه ماه قبل ' + toman(avg, true) + ' بوده است.']);
      }
    }
    var over = S.budgets.filter(function (b) { return b.over; });
    if (over.length) out.push(['alert', 't-bad', '<b>' + BH.n(over.length) + ' بودجه</b> از سقف گذشته است: ' + over.map(function (b) { return esc(b.category); }).join('، ') + '.']);
    $('#insights').innerHTML = out.slice(0, 3).map(function (x) {
      return '<div class="insight ' + x[1] + '"><span class="ico">' + BH.icon(x[0]) + '</span><div>' + x[2] + '</div></div>';
    }).join('');
  }

  function renderCash() {
    var m = S.months.slice(-6);
    if (!m.some(function (x) { return x.income || x.expense; })) { $('#c-cash').innerHTML = BH.empty('هنوز تراکنشی ثبت نشده', 'chart'); return; }
    BHChart.line('c-cash', {
      labels: m.map(function (x) { return BH.date(x.from, 'monthShort'); }),
      tipLabels: m.map(function (x) { return BH.date(x.from, 'month'); }),
      height: 260, labelWidth: 50,
      fmt: function (v) { return toman(v, true); },
      series: [
        { name: 'درآمد', data: m.map(function (x) { return x.income; }), color: 'ok', fill: true },
        { name: 'هزینه', data: m.map(function (x) { return x.expense; }), color: 'c5', fill: true },
        { name: 'خالص', data: m.map(function (x) { return x.net; }), color: 'finance', dash: true, fill: false }
      ]
    });
  }

  function renderCats() {
    var bc = (S.summary.by_category || []).slice();
    $('#cat-sub').textContent = PERIOD_FA[S.period];
    if (!bc.length) { $('#c-cats').innerHTML = BH.empty('در این بازه هزینه‌ای نیست', 'pie'); return; }
    var top = bc.slice(0, 5), rest = bc.slice(5).reduce(function (a, b) { return a + b.amount; }, 0);
    var labels = top.map(function (c) { return c.category; }), data = top.map(function (c) { return c.amount; });
    if (rest) { labels.push('سایر'); data.push(rest); }
    BHChart.donut('c-cats', {
      data: data, labels: labels, size: 170, colors: ['c1', 'c5', 'c3', 'c4', 'c6', 'faint'],
      fmt: function (v) { return toman(v, true); }, centerValue: BH.money(S.summary.expense, true), centerLabel: 'تومان هزینه'
    });
  }

  function budClass(pct) { return pct >= 100 ? 'bad' : pct >= 80 ? 'warn' : 'ok'; }
  function budRow(b) {
    var pct = Math.min(100, b.pct || 0);
    return '<div class="bud-row"><div class="top"><b>' + esc(b.category) + '</b><span class="num">' + BH.money(b.spent, true) + ' از ' + BH.money(b.budget, true) + '</span></div>' +
      '<div class="progress ' + budClass(b.pct) + '" role="progressbar" aria-valuenow="' + Math.round(b.pct) + '" aria-valuemin="0" aria-valuemax="100" aria-label="' + esc(b.category) + '"><i style="width:' + pct + '%"></i></div></div>';
  }
  function renderOverBudget() {
    var b = S.budgets.slice().sort(function (a, c) { return c.pct - a.pct; }).slice(0, 4);
    $('#over-bud').innerHTML = b.length ? b.map(budRow).join('') : BH.empty('بودجه‌ای تعریف نشده', 'target');
    animateBars($('#over-bud'));
  }

  function activeLiabs() {
    return ((S.liab && S.liab.liabilities) || []).filter(function (l) { return l.status === 'active'; });
  }
  function renderNextDue() {
    var l = activeLiabs().filter(function (x) { return x.next_due; })
      .sort(function (a, b) { return a.next_due < b.next_due ? -1 : 1; })[0];
    if (!l) { $('#next-due').innerHTML = BH.empty('قسط فعالی نداری', 'check'); return; }
    var days = daysBetween(BH.todayISO(), l.next_due);
    var when = days < 0 ? BH.n(-days) + ' روز گذشته' : days === 0 ? 'امروز' : BH.n(days) + ' روز دیگر';
    var paidPct = l.installments_total ? l.installments_paid / l.installments_total * 100 : (l.principal ? l.paid / l.principal * 100 : 0);
    $('#next-due').innerHTML =
      '<div class="list-row" style="border:0;padding-top:0"><span class="ico">' + BH.icon('calendar') + '</span><div class="grow"><div class="title">' + esc(l.name) + '</div>' +
      '<div class="meta">سررسید ' + BH.date(l.next_due) + '</div></div></div>' +
      '<div class="due-amount">' + toman(l.installment_amount) + '</div>' +
      '<div class="due-meta"><span class="due-when">' + BH.icon('clock') + when + '</span>' +
      '<span>قسط ' + BH.n(l.installments_paid) + ' از ' + BH.n(l.installments_total) + '</span></div>' +
      '<div class="progress warn"><i style="width:' + Math.min(100, paidPct) + '%"></i></div>' +
      '<div class="due-meta" style="margin:8px 0 0"><span>مانده</span><b class="num" style="color:var(--text)">' + toman(l.remaining, true) + '</b></div>';
    animateBars($('#next-due'));
  }

  function txRow(t) {
    var k = KIND[kindOf(t)];
    return '<div class="list-row ' + k.cls + '"><span class="ico">' + BH.icon(k.ic) + '</span><div class="grow">' +
      '<div class="title" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">' + esc(t.counterparty || t.category || t.description || k.fa) + '</div>' +
      '<div class="meta">' + BH.date(t.occurred_at, 'short') + ' · ' + esc(t.account || '') + '</div></div>' + signedAmount(t) + '</div>';
  }
  function renderRecent() {
    $('#recent').innerHTML = S.recent.length ? S.recent.map(txRow).join('') : BH.empty('تراکنشی ثبت نشده', 'receipt');
  }

  /* ---------- تراکنش‌ها ---------- */
  function filteredTx() {
    var q = S.q.trim().toLowerCase();
    return S.txs.filter(function (t) {
      if (S.kind !== 'all' && kindOf(t) !== S.kind) return false;
      if (!q) return true;
      return [t.description, t.counterparty, t.category, t.account].join(' ').toLowerCase().indexOf(q) >= 0;
    });
  }
  function renderTx() {
    var rows = filteredTx();
    var inSum = 0, outSum = 0;
    rows.forEach(function (t) { var k = kindOf(t); if (k === 'income') inSum += t.amount; else if (k === 'expense') outSum += t.amount; });
    $('#tx-sum').innerHTML = '<span class="chip">' + BH.n(rows.length) + ' تراکنش</span>' +
      '<span class="chip"><span class="dot" style="background:var(--ok)"></span>ورودی ' + toman(inSum, true) + '</span>' +
      '<span class="chip"><span class="dot" style="background:var(--c5)"></span>خروجی ' + toman(outSum, true) + '</span>';
    $('#tx-body').innerHTML = rows.length ? rows.map(function (t) {
      var k = KIND[kindOf(t)];
      return '<tr><td class="tx-date">' + BH.date(t.occurred_at, 'short') + '</td>' +
        '<td><div class="tx-desc"><div class="title" title="' + esc(t.description) + '">' + esc(t.counterparty || t.description || k.fa) + '</div>' +
        (t.counterparty && t.description ? '<div class="meta">' + esc(t.description) + '</div>' : '') + '</div></td>' +
        '<td>' + (t.category ? '<span class="badge">' + esc(t.category) + '</span>' : '<span class="badge ' + (k === KIND.transfer ? '' : 'warn') + '">' + (k === KIND.transfer ? 'انتقال' : 'بدون دسته') + '</span>') + '</td>' +
        '<td class="hide-sm muted">' + esc(t.account || '') + (k === KIND.transfer && t.counter_account ? ' ← ' + esc(t.counter_account) : '') + '</td>' +
        '<td class="end">' + signedAmount(t) + '</td></tr>';
    }).join('') : '<tr><td colspan="5">' + BH.empty(S.txs.length ? 'با این فیلتر چیزی پیدا نشد' : 'در این بازه تراکنشی نیست', 'search') + '</td></tr>';
  }
  function exportCsv() {
    var rows = filteredTx();
    var head = ['تاریخ شمسی', 'تاریخ میلادی', 'نوع', 'شرح', 'طرف حساب', 'دسته', 'حساب', 'مبلغ (تومان)'];
    var q = function (v) { v = v === null || v === undefined ? '' : String(v); return '"' + v.replace(/"/g, '""') + '"'; };
    var lines = [head.map(q).join(',')].concat(rows.map(function (t) {
      var k = kindOf(t), sign = k === 'expense' ? -1 : 1;
      return [BH.date(t.occurred_at, 'num'), String(t.occurred_at).slice(0, 10), KIND[k].fa, t.description, t.counterparty,
        t.category, t.account, k === 'transfer' ? t.amount : sign * t.amount].map(q).join(',');
    }));
    var blob = new Blob(['﻿' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'behoosh-transactions-' + S.range.start + '_' + S.range.end + '.csv';
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
    BH.toast('فایل CSV با ' + BH.n(rows.length) + ' ردیف ساخته شد', 'download');
  }

  /* ---------- حساب‌ها و بدهی‌ها ---------- */
  function renderAccounts() {
    var assets = S.accounts.filter(function (a) { return a.type === 'asset'; });
    var total = assets.reduce(function (t, a) { return t + a.balance; }, 0);
    $('#acc-total').textContent = 'جمع دارایی ' + toman(total, true);
    $('#acc-list').innerHTML = S.accounts.length ? S.accounts.map(function (a) {
      var cash = /نقد|کیف/.test(a.name), liab = a.type === 'liability';
      var cls = liab ? 't-warn' : cash ? 't-ok' : a.balance < 0 ? 't-bad' : 't-finance';
      return '<div class="card acc-card ' + cls + '"><div class="row"><span class="ico">' + BH.icon(liab ? 'flag' : cash ? 'wallet' : 'bank') + '</span>' +
        '<div class="grow" style="flex:1;min-width:0"><div class="name">' + esc(a.name) + '</div><div class="sub">' +
        (liab ? 'بدهی' : cash ? 'نقد' : 'حساب بانکی') + (a.card_last4 ? ' · کارت <span class="ltr">•••• ' + BH.fa(a.card_last4) + '</span>' : '') + '</div></div>' +
        (a.balance < 0 ? '<span class="badge bad">منفی</span>' : '') + '</div>' +
        '<div class="bal ' + (a.balance < 0 ? 'neg' : '') + '">' + BH.money(a.balance) + ' <small class="muted" style="font-size:12px;font-weight:500">تومان</small></div></div>';
    }).join('') : BH.empty('حسابی تعریف نشده', 'bank');

    var L = (S.liab && S.liab.liabilities) || [];
    $('#liab-total').textContent = L.length ? 'مانده کل ' + toman(S.liab.total_remaining || 0, true) : '';
    $('#liab-list').innerHTML = L.length ? L.map(function (l) {
      var pct = l.principal ? Math.min(100, l.paid / l.principal * 100) : 0;
      var settled = l.status !== 'active';
      return '<div class="card t-warn"><div class="list-row" style="border:0;padding:0 0 10px"><span class="ico">' + BH.icon('flag') + '</span>' +
        '<div class="grow"><div class="title">' + esc(l.name) + '</div><div class="meta">' +
        (settled ? 'تسویه شده' : (l.next_due ? 'قسط بعدی ' + BH.date(l.next_due) : 'فعال')) +
        (l.interest_rate ? ' · سود ' + BH.pct(l.interest_rate, 1) : '') + '</div></div>' +
        '<span class="badge ' + (settled ? 'ok' : 'warn') + '">' + (settled ? 'تسویه' : 'فعال') + '</span></div>' +
        '<div class="progress ' + (settled ? 'ok' : 'warn') + '"><i style="width:' + pct + '%"></i></div>' +
        '<div class="liab-stats"><div>اصل<b>' + BH.money(l.principal, true) + '</b></div><div>پرداخت‌شده<b>' + BH.money(l.paid, true) + '</b></div>' +
        '<div>مانده<b>' + BH.money(l.remaining, true) + '</b></div></div>' +
        (l.installments_total ? '<div class="kpi-sub" style="margin-top:10px">' + BH.n(l.installments_paid) + ' از ' + BH.n(l.installments_total) + ' قسط · هر قسط ' + toman(l.installment_amount, true) + '</div>' : '') +
        '</div>';
    }).join('') : '<div class="card">' + BH.empty('بدهی یا وامی ثبت نشده', 'check') + '</div>';
    animateBars($('#liab-list'));
  }

  /* ---------- بودجه ---------- */
  function renderBudgets() {
    $('#bud-list').innerHTML = S.budgets.length ? S.budgets.slice().sort(function (a, b) { return b.pct - a.pct; }).map(function (b) {
      var cls = budClass(b.pct);
      var tone = cls === 'bad' ? 't-bad' : cls === 'warn' ? 't-warn' : 't-ok';
      return '<div class="card kpi ' + tone + '"><div class="kpi-top"><span class="kpi-label">' + esc(b.category) + '</span>' +
        '<span class="badge ' + cls + '">' + BH.pct(b.pct) + '</span></div>' +
        '<div class="kpi-value" style="font-size:22px">' + BH.money(b.spent, true) + '<small>از ' + BH.money(b.budget, true) + '</small></div>' +
        '<div class="progress ' + cls + '"><i style="width:' + Math.min(100, b.pct) + '%"></i></div>' +
        '<div class="kpi-sub">' + (b.over ? 'بیش از سقف: ' + toman(-b.remaining, true) : 'باقی‌مانده ' + toman(b.remaining, true)) + '</div></div>';
    }).join('') : '<div class="card">' + BH.empty('بودجه‌ای تعریف نشده. ایجنت مالی می‌تواند برای هر دسته سقف ماهانه بگذارد.', 'target') + '</div>';
    animateBars($('#bud-list'));
  }

  /* ---------- پیامک‌ها ---------- */
  function renderSms() {
    var pending = S.raw.filter(function (m) { return !m.parsed; }).length;
    var b = $('#sms-count');
    if (pending) { b.textContent = BH.n(pending); b.classList.remove('hidden'); } else b.classList.add('hidden');
    $('#sms-list').innerHTML = S.raw.length ? S.raw.map(function (m) {
      var ok = m.parsed;
      return '<div class="list-row ' + (ok ? 't-ok' : 't-warn') + '" style="align-items:flex-start"><span class="ico">' + BH.icon(ok ? 'check' : 'alert') + '</span>' +
        '<div class="grow"><div class="sms-body">' + esc(m.body) + '</div><div class="meta">' + BH.date(m.received_at, 'full') +
        (m.bank ? ' · ' + esc(m.bank) : '') + (m.parse_error ? ' · ' + esc(m.parse_error) : '') + '</div></div>' +
        '<span class="badge ' + (ok ? 'ok' : 'warn') + '">' + (ok ? 'ثبت شد' : 'نیاز به بازبینی') + '</span></div>';
    }).join('') : BH.empty('پیامکی دریافت نشده', 'message');
  }

  /* ---------- گزارش ایجنت ---------- */
  var TOOL_FA = {
    finance_transaction_log: ['ثبت تراکنش', 'receipt', 't-finance'],
    finance_transaction_correct: ['اصلاح تراکنش', 'file', 't-warn'],
    finance_account_create: ['ساخت حساب', 'bank', 't-info'],
    finance_category_create: ['ساخت دسته', 'list', 't-info'],
    finance_budget_set: ['تنظیم بودجه', 'target', 't-ok'],
    finance_liability_create: ['ثبت بدهی', 'flag', 't-warn'],
    finance_liability_update: ['اصلاح بدهی', 'flag', 't-warn'],
    finance_sms_log: ['پیامک بانک', 'message', 't-finance']
  };
  var KEY_FA = { amount: 'مبلغ', account: 'حساب', counter_account: 'حساب مقابل', direction: 'جهت', description: 'شرح',
    name: 'نام', category: 'دسته', principal: 'اصل', period: 'دوره', type: 'نوع' };
  function renderAudit() {
    $('#aud-list').innerHTML = S.audit.length ? S.audit.map(function (a) {
      var t = TOOL_FA[a.tool] || [a.tool, 'zap', 't-info'];
      var kv = Object.keys(a.payload || {}).filter(function (k) {
        var v = a.payload[k]; return KEY_FA[k] && v !== null && v !== '' && v !== false;
      }).slice(0, 5).map(function (k) {
        var v = a.payload[k];
        if (k === 'amount' || k === 'principal') v = toman(v, true);
        if (k === 'direction') v = v === 'debit' ? 'خروج' : 'ورود';
        return '<span title="' + esc(String(v)) + '">' + KEY_FA[k] + ': ' + esc(String(v).slice(0, 60)) + '</span>';
      }).join('');
      return '<div class="tl-item ' + t[2] + '"><span class="ico">' + BH.icon(t[1]) + '</span><div class="grow">' +
        '<div class="title">' + esc(t[0]) + ' <span class="badge" style="margin-inline-start:4px">' + (a.actor === 'agent' ? 'ایجنت' : esc(a.actor)) + '</span></div>' +
        '<div class="meta">' + BH.date(a.created_at, 'full') + '</div>' + (kv ? '<div class="kv">' + kv + '</div>' : '') + '</div></div>';
    }).join('') : BH.empty('ایجنت هنوز چیزی ننوشته', 'shield');
  }

  function animateBars(root) {
    if (!root) return;
    $$('.progress > i', root).forEach(function (i) {
      var w = i.style.width; i.style.width = '0';
      requestAnimationFrame(function () { requestAnimationFrame(function () { i.style.width = w; }); });
    });
  }

  function renderAll() {
    renderKpis(); renderInsights(); renderCash(); renderCats(); renderOverBudget(); renderNextDue(); renderRecent();
    renderTx(); renderAccounts(); renderBudgets(); renderSms(); renderAudit();
  }

  /* ---------- تب‌ها ---------- */
  function showTab(t) {
    if (!document.getElementById(t)) t = 'over';
    $$('.tab').forEach(function (b) { b.setAttribute('aria-selected', String(b.getAttribute('data-t') === t)); });
    $$('.panel').forEach(function (p) { p.classList.toggle('active', p.id === t); });
    // #tab=… با هیچ id ای جور نیست، پس مرورگر صفحه را به سمت بخش اسکرول نمی‌کند.
    if (location.hash !== '#tab=' + t) history.replaceState(null, '', '#tab=' + t);
  }

  /* ---------- ثبت تراکنش ---------- */
  var dlg = $('#dlg-add'), fKind = 'debit';
  function normDigits(s) {
    return String(s).replace(/[۰-۹]/g, function (c) { return '۰۱۲۳۴۵۶۷۸۹'.indexOf(c); })
      .replace(/[٠-٩]/g, function (c) { return '٠١٢٣٤٥٦٧٨٩'.indexOf(c); });
  }
  function parseAmount() { return Number(normDigits($('#f-amount').value).replace(/[^\d.]/g, '')) || 0; }
  function fillCats() {
    var want = fKind === 'debit' ? 'expense' : 'income';
    $('#f-cat').innerHTML = '<option value="">بدون دسته</option>' + S.cats.filter(function (c) { return c.kind === want; })
      .map(function (c) { return '<option value="' + c.id + '">' + esc(c.name) + '</option>'; }).join('');
  }
  function setKind(k) {
    fKind = k;
    $$('#f-kind button').forEach(function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-k') === k)); });
    fillCats();
  }
  function openAdd() {
    var acc = S.accounts.filter(function (a) { return a.type === 'asset'; });
    if (!acc.length) { BH.toast('اول یک حساب بانکی یا نقد بساز', 'alert'); return; }
    $('#f-acc').innerHTML = acc.map(function (a) { return '<option value="' + a.id + '">' + esc(a.name) + '</option>'; }).join('');
    $('#add-form').reset(); setKind('debit');
    $('#f-date').value = BH.todayISO(); $('#f-amount-hint').textContent = '';
    $('#f-date-hint').textContent = BH.date(BH.todayISO());
    $('#f-err').classList.add('hidden');
    dlg.showModal();
    setTimeout(function () { $('#f-amount').focus(); }, 30);
  }
  async function submitAdd(e) {
    e.preventDefault();
    var amount = parseAmount(), err = $('#f-err');
    if (!amount) { err.textContent = 'مبلغ را وارد کن.'; err.classList.remove('hidden'); $('#f-amount').focus(); return; }
    var btn = $('#f-submit'); btn.disabled = true;
    try {
      await BH.api('/finance/transaction', { body: {
        occurred_at: $('#f-date').value || BH.todayISO(), amount: amount, direction: fKind,
        account_id: $('#f-acc').value, category_id: $('#f-cat').value || null,
        description: $('#f-desc').value.trim(), counterparty: $('#f-party').value.trim() || null, source: 'manual'
      } });
      dlg.close();
      BH.toast((fKind === 'debit' ? 'هزینه ' : 'درآمد ') + toman(amount) + ' ثبت شد');
      await refresh();
    } catch (ex) {
      err.textContent = ex.status === 403 ? 'این توکن اجازه نوشتن مالی ندارد.' : 'ثبت نشد: ' + ex.message;
      err.classList.remove('hidden');
    } finally { btn.disabled = false; }
  }

  async function refresh() {
    await loadStatic(); await loadPeriod(); renderAll();
  }

  /* ---------- راه‌اندازی ---------- */
  async function boot() {
    icons(document);
    $('#recent').innerHTML = skel(4); $('#over-bud').innerHTML = skel(3, 30); $('#next-due').innerHTML = skel(3, 30);
    $('#c-cash').innerHTML = '<div class="skeleton" style="height:240px;border-radius:14px"></div>';
    $('#c-cats').innerHTML = '<div class="skeleton" style="height:240px;border-radius:14px"></div>';
    $('#tx-body').innerHTML = '<tr><td colspan="5">' + skel(5, 34) + '</td></tr>';

    $$('.tab').forEach(function (b) { b.addEventListener('click', function () { showTab(b.getAttribute('data-t')); }); });
    $$('[data-go]').forEach(function (b) { b.addEventListener('click', function () { showTab(b.getAttribute('data-go')); window.scrollTo({ top: 0, behavior: 'smooth' }); }); });
    showTab((location.hash.match(/tab=(\w+)/) || [0, 'over'])[1]);

    $('#tx-q').addEventListener('input', function (e) { S.q = e.target.value; renderTx(); });
    $$('#tx-kind button').forEach(function (b) {
      b.addEventListener('click', function () {
        S.kind = b.getAttribute('data-k');
        $$('#tx-kind button').forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); });
        renderTx();
      });
    });
    $('#tx-csv').addEventListener('click', exportCsv);
    $('#period').addEventListener('change', async function (e) {
      S.period = e.target.value;
      try { await loadPeriod(); renderAll(); } catch (ex) { BH.toast('بارگذاری نشد', 'alert'); }
    });

    $('#btn-add').addEventListener('click', openAdd);
    $('#dlg-close').addEventListener('click', function () { dlg.close(); });
    $('#f-cancel').addEventListener('click', function () { dlg.close(); });
    dlg.addEventListener('click', function (e) { if (e.target === dlg) dlg.close(); });
    $$('#f-kind button').forEach(function (b) { b.addEventListener('click', function () { setKind(b.getAttribute('data-k')); }); });
    $('#f-amount').addEventListener('input', function () {
      var v = parseAmount();
      $('#f-amount-hint').textContent = v ? toman(v) + (v >= 1e6 ? ' (' + BH.money(v, true) + ')' : '') : '';
    });
    $('#f-date').addEventListener('change', function (e) { $('#f-date-hint').textContent = e.target.value ? BH.date(e.target.value) : ''; });
    $('#add-form').addEventListener('submit', submitAdd);

    try {
      await loadStatic();
      // اوایل ماه شمسی «این ماه» تقریبا خالی است؛ آن موقع ماه قبل پیش‌فرض است.
      var L = S.months.length ? S.months[S.months.length - 1].from : BH.todayISO();
      S.period = daysBetween(L, BH.todayISO()) < 6 ? 'prev' : 'month';
      $('#period').value = S.period;
      await loadPeriod();
      renderAll();
    } catch (ex) {
      if (ex.message === 'auth') return;
      $('#k-over').innerHTML = '<div class="card" style="grid-column:1/-1">' +
        BH.empty(ex.status === 403 ? 'این حساب دسترسی مالی ندارد.' : 'داده مالی بارگذاری نشد. اتصال به سرور را بررسی کن.', 'alert') + '</div>';
    }
  }

  window.logout = BH.logout;
  boot();
})();
