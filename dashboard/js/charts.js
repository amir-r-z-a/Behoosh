/* بهوش — کتابخانه نمودار SVG
   رنگ‌ها از توکن‌های تم خوانده می‌شوند و با عوض شدن تم یا اندازه، نمودار دوباره رسم می‌شود.
   هر نمودار راهنمای شناور دارد (موس، لمس و کلیدهای جهت) و سری‌ها علاوه بر رنگ با شیوه خط
   هم از هم جدا می‌شوند. محور زمان چپ‌به‌راست است. */
(function () {
  'use strict';
  var BH = window.BH;
  var NS = 'http://www.w3.org/2000/svg';
  var TOKENS = /^(c[1-6]|ok|warn|bad|info|primary|muted|faint|text|text-2|health|finance|meeting|agent|border|c-grid|c-axis|surface|surface-3)$/;
  var uid = 0;

  function col(c) {
    if (!c) return BH.css('--c1');
    if (TOKENS.test(c)) return BH.css('--' + c);
    if (c.indexOf('--') === 0) return BH.css(c);
    return c;
  }
  function E(tag, attrs, parent) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) if (attrs[k] !== undefined && attrs[k] !== null) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  function T(parent, x, y, text, o) {
    o = o || {};
    /* متن فارسی در SVG چپ‌به‌راست: جهت متن راست‌به‌چپ و لنگر start/end جابه‌جا می‌شود */
    var anchor = o.anchor === 'end' ? 'start' : o.anchor === 'start' ? 'end' : 'middle';
    var t = E('text', { x: x, y: y, 'text-anchor': anchor, direction: 'rtl', 'font-size': o.size || 11,
      'font-weight': o.weight || 400, fill: o.fill || col('c-axis'), 'dominant-baseline': o.base || 'auto' }, parent);
    t.textContent = text;
    return t;
  }
  function niceMax(v) {
    if (v <= 0) return 1;
    var p = Math.pow(10, Math.floor(Math.log10(v))), n = v / p;
    var m = n <= 1 ? 1 : n <= 1.5 ? 1.5 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 3 ? 3 : n <= 4 ? 4 : n <= 5 ? 5 : n <= 6 ? 6 : n <= 8 ? 8 : 10;
    return m * p;
  }
  function compact(v) {
    var a = Math.abs(v);
    if (a >= 1e9) return BH.n(v / 1e9, 1) + 'B';
    if (a >= 1e6) return BH.n(v / 1e6, 1) + 'M';
    if (a >= 1e4) return BH.n(v / 1e3, 0) + 'k';
    if (a >= 1e3) return BH.n(v / 1e3, 1) + 'k';
    return BH.n(v, a < 10 && a % 1 ? 1 : 0);
  }

  /* ---------- راهنمای شناور ---------- */
  var tip;
  function getTip() {
    if (!tip) { tip = document.createElement('div'); tip.className = 'chart-tip'; tip.setAttribute('role', 'status'); document.body.appendChild(tip); }
    return tip;
  }
  function showTip(html, x, y) {
    var t = getTip();
    t.innerHTML = html;
    t.classList.add('on');
    var w = t.offsetWidth, h = t.offsetHeight, vw = window.innerWidth;
    var left = x + 14; if (left + w > vw - 8) left = x - w - 14; if (left < 8) left = 8;
    var top = y - h - 12; if (top < 8) top = y + 16;
    t.style.left = left + 'px'; t.style.top = top + 'px';
  }
  function hideTip() { if (tip) tip.classList.remove('on'); }
  function tipRows(title, rows) {
    return '<b>' + BH.esc(title) + '</b>' + rows.map(function (r) {
      return '<div class="r"><span><i style="background:' + r.color + '"></i>' + BH.esc(r.name) + '</span><em>' + r.value + '</em></div>';
    }).join('');
  }

  /* ---------- ثبت و رسم دوباره ---------- */
  var registry = [];
  function mount(el, draw) {
    if (typeof el === 'string') el = document.getElementById(el);
    if (!el) return null;
    el.classList.add('chart');
    el._bhDraw = draw;
    if (registry.indexOf(el) < 0) registry.push(el);
    if (!el._bhRO && window.ResizeObserver) {
      var lastW = 0;
      el._bhRO = new ResizeObserver(function () {
        var w = el.clientWidth;
        if (Math.abs(w - lastW) > 4) { lastW = w; el._bhDraw && el._bhDraw(); }
      });
      el._bhRO.observe(el);
    }
    draw();
    return el;
  }
  window.addEventListener('themechange', function () {
    registry = registry.filter(function (el) { return document.body.contains(el); });
    registry.forEach(function (el) { el._bhDraw && el._bhDraw(); });
  });
  function svgFor(el, W, H, label) {
    el.innerHTML = '';
    var s = E('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': label || '' }, el);
    return s;
  }
  function gradient(svg, color, id, top, bottom) {
    var defs = E('defs', {}, svg);
    var g = E('linearGradient', { id: id, x1: 0, y1: 0, x2: 0, y2: 1 }, defs);
    E('stop', { offset: '0%', 'stop-color': color, 'stop-opacity': top === undefined ? 0.24 : top }, g);
    E('stop', { offset: '100%', 'stop-color': color, 'stop-opacity': bottom === undefined ? 0 : bottom }, g);
    return 'url(#' + id + ')';
  }

  /* مسیر هموار یکنوا (Fritsch–Carlson): بدون بیرون‌زدگی از داده */
  function smoothPath(pts) {
    if (pts.length < 2) return pts.length ? 'M' + pts[0][0] + ',' + pts[0][1] : '';
    if (pts.length === 2) return 'M' + pts[0] + 'L' + pts[1];
    var n = pts.length, dx = [], dy = [], m = [], t = [];
    for (var i = 0; i < n - 1; i++) { dx[i] = pts[i + 1][0] - pts[i][0]; dy[i] = pts[i + 1][1] - pts[i][1]; m[i] = dy[i] / dx[i]; }
    t[0] = m[0]; t[n - 1] = m[n - 2];
    for (i = 1; i < n - 1; i++) t[i] = m[i - 1] * m[i] <= 0 ? 0 : (m[i - 1] + m[i]) / 2;
    for (i = 0; i < n - 1; i++) {
      if (m[i] === 0) { t[i] = t[i + 1] = 0; continue; }
      var a = t[i] / m[i], b = t[i + 1] / m[i], s = a * a + b * b;
      if (s > 9) { var k = 3 / Math.sqrt(s); t[i] = k * a * m[i]; t[i + 1] = k * b * m[i]; }
    }
    var d = 'M' + pts[0][0] + ',' + pts[0][1];
    for (i = 0; i < n - 1; i++) {
      var h = dx[i] / 3;
      d += 'C' + (pts[i][0] + h) + ',' + (pts[i][1] + t[i] * h) + ' ' + (pts[i + 1][0] - h) + ',' + (pts[i + 1][1] - t[i + 1] * h) + ' ' + pts[i + 1][0] + ',' + pts[i + 1][1];
    }
    return d;
  }
  function segments(values, xf, yf) {
    var segs = [], cur = [];
    values.forEach(function (v, i) {
      if (v === null || v === undefined || isNaN(v)) { if (cur.length) segs.push(cur); cur = []; }
      else cur.push([xf(i), yf(v)]);
    });
    if (cur.length) segs.push(cur);
    return segs;
  }

  /* محور و شبکه مشترک نمودارهای شاخص‌دار (خطی، میله‌ای، انباشته) */
  function frame(el, cfg, maxVal, minVal) {
    var W = Math.max(280, el.clientWidth || 600), H = cfg.height || 240;
    var P = { t: 14, r: 12, b: 26, l: cfg.yLabelWidth || 40 };
    var svg = svgFor(el, W, H, cfg.title);
    var lo = cfg.yMin !== undefined ? cfg.yMin : (minVal < 0 ? -niceMax(-minVal) : 0);
    var hi = cfg.yMax !== undefined ? cfg.yMax : niceMax(maxVal * 1.08 || 1);
    if (hi <= lo) hi = lo + 1;
    var n = cfg.labels.length;
    var iw = W - P.l - P.r, ih = H - P.t - P.b;
    var band = cfg.band ? iw / Math.max(n, 1) : 0;
    var xf = cfg.band
      ? function (i) { return P.l + band * i + band / 2; }
      : function (i) { return P.l + (n <= 1 ? iw / 2 : iw * i / (n - 1)); };
    var yf = function (v) { return P.t + ih - (v - lo) / (hi - lo) * ih; };
    var ticks = cfg.ticks || 4;
    for (var k = 0; k <= ticks; k++) {
      var v = lo + (hi - lo) * k / ticks, y = yf(v);
      E('line', { x1: P.l, x2: W - P.r, y1: y, y2: y, stroke: col('c-grid'), 'stroke-width': 1,
        'stroke-dasharray': k === 0 ? null : '3 4' }, svg);
      T(svg, P.l - 8, y + 4, (cfg.yFmt || compact)(v), { anchor: 'end' });
    }
    var maxLabels = Math.max(2, Math.floor(iw / (cfg.labelWidth || 64)));
    var step = Math.ceil(n / maxLabels);
    for (var i = 0; i < n; i++) {
      if ((n - 1 - i) % step === 0) T(svg, xf(i), H - 6, cfg.labels[i]);
    }
    if (cfg.target !== undefined && cfg.target !== null) {
      var tv = typeof cfg.target === 'object' ? cfg.target.value : cfg.target;
      if (tv >= lo && tv <= hi) {
        var ty = yf(tv), tc = col(cfg.targetColor || 'bad');
        E('line', { x1: P.l, x2: W - P.r, y1: ty, y2: ty, stroke: tc, 'stroke-width': 1.5, 'stroke-dasharray': '6 5', opacity: .8 }, svg);
        var tl = typeof cfg.target === 'object' && cfg.target.label ? cfg.target.label : 'هدف ' + compact(tv);
        var tb = E('g', {}, svg);
        var tt = T(tb, W - P.r - 4, ty - 6, tl, { anchor: 'end', fill: tc, size: 11, weight: 600 });
        tt.setAttribute('paint-order', 'stroke'); tt.setAttribute('stroke', col('surface')); tt.setAttribute('stroke-width', 4);
      }
    }
    return { svg: svg, W: W, H: H, P: P, xf: xf, yf: yf, lo: lo, hi: hi, n: n, band: band, iw: iw, ih: ih };
  }

  function interact(el, f, cfg, rows, onIndex) {
    var ov = E('rect', { x: f.P.l, y: f.P.t, width: f.iw, height: f.ih, fill: 'transparent', style: 'cursor:crosshair' }, f.svg);
    var guide = E('line', { y1: f.P.t, y2: f.P.t + f.ih, stroke: col('border'), 'stroke-width': 1, opacity: 0 }, f.svg);
    var dots = E('g', {}, f.svg);
    var cur = -1;
    function idxAt(clientX) {
      var r = f.svg.getBoundingClientRect(), x = (clientX - r.left) * f.W / r.width;
      if (f.band) return Math.max(0, Math.min(f.n - 1, Math.floor((x - f.P.l) / f.band)));
      return Math.max(0, Math.min(f.n - 1, Math.round((x - f.P.l) / (f.iw / Math.max(1, f.n - 1)))));
    }
    function show(i, cx, cy) {
      cur = i;
      var x = f.xf(i);
      guide.setAttribute('x1', x); guide.setAttribute('x2', x); guide.setAttribute('opacity', 1);
      dots.innerHTML = '';
      if (onIndex) onIndex(i, dots);
      var r = f.svg.getBoundingClientRect();
      var px = cx !== undefined ? cx : r.left + x * r.width / f.W;
      var py = cy !== undefined ? cy : r.top + f.P.t * r.height / f.H + 30;
      showTip(tipRows(cfg.tipLabels ? cfg.tipLabels[i] : cfg.labels[i], rows(i)), px, py);
    }
    function hide() { guide.setAttribute('opacity', 0); dots.innerHTML = ''; hideTip(); cur = -1; }
    ov.addEventListener('pointermove', function (e) { show(idxAt(e.clientX), e.clientX, e.clientY); });
    ov.addEventListener('pointerdown', function (e) { show(idxAt(e.clientX), e.clientX, e.clientY); });
    ov.addEventListener('pointerleave', hide);
    el.tabIndex = 0;
    el.onkeydown = function (e) {
      if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
        e.preventDefault();
        var d = e.key === 'ArrowRight' ? 1 : -1;
        show(cur < 0 ? f.n - 1 : Math.max(0, Math.min(f.n - 1, cur + d)));
      } else if (e.key === 'Escape') hide();
    };
    el.onblur = hide;
  }
  function fmtVal(s, v, cfg) {
    if (v === null || v === undefined || isNaN(v)) return '—';
    if (s.fmt) return s.fmt(v);
    if (cfg.fmt) return cfg.fmt(v);
    return BH.n(v, v % 1 ? 1 : 0) + (s.unit || cfg.unit ? ' ' + (s.unit || cfg.unit) : '');
  }

  /* ---------- خطی / سطحی ---------- */
  function line(el, cfg0) {
    var host = typeof el === 'string' ? document.getElementById(el) : el;
    return mount(host, function () {
      var cfg = cfg0;
      var all = [];
      cfg.series.forEach(function (s) { (s.data || []).forEach(function (v) { if (v !== null && !isNaN(v)) all.push(v); }); });
      if (cfg.target) all.push(typeof cfg.target === 'object' ? cfg.target.value : cfg.target);
      var mx = all.length ? Math.max.apply(null, all) : 1, mn = all.length ? Math.min.apply(null, all) : 0;
      if (cfg.autoMin && cfg.yMin === undefined) {
        var span = (mx - mn) || Math.abs(mx) * 0.1 || 1;
        cfg = Object.assign({}, cfg, { yMin: Math.floor(mn - span * 0.25), yMax: Math.ceil(mx + span * 0.25) });
      }
      var f = frame(host, cfg, mx, mn);
      cfg.series.forEach(function (s, si) {
        var c = col(s.color || ('c' + (si + 1)));
        var segs = segments(s.data || [], f.xf, f.yf);
        segs.forEach(function (pts) {
          if (s.fill !== false && (s.fill || cfg.series.length === 1)) {
            var gid = 'g' + (++uid);
            var area = smoothPath(pts) + 'L' + pts[pts.length - 1][0] + ',' + f.yf(Math.max(f.lo, 0)) + 'L' + pts[0][0] + ',' + f.yf(Math.max(f.lo, 0)) + 'Z';
            E('path', { d: area, fill: gradient(f.svg, c, gid) }, f.svg);
          }
          var p = E('path', { d: smoothPath(pts), fill: 'none', stroke: c, 'stroke-width': s.width || 2.4,
            'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-dasharray': s.dash ? '6 5' : null }, f.svg);
          if (!s.dash && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            var len = p.getTotalLength ? p.getTotalLength() : 0;
            if (len) { p.style.strokeDasharray = len; p.style.strokeDashoffset = len;
              p.getBoundingClientRect(); p.style.transition = 'stroke-dashoffset .9s cubic-bezier(.22,.7,.3,1)'; p.style.strokeDashoffset = 0; }
          }
          if (pts.length === 1) E('circle', { cx: pts[0][0], cy: pts[0][1], r: 3.5, fill: c }, f.svg);
        });
        var last = (s.data || []).length - 1;
        while (last >= 0 && (s.data[last] === null || s.data[last] === undefined)) last--;
        if (last >= 0 && cfg.lastDot !== false) {
          E('circle', { cx: f.xf(last), cy: f.yf(s.data[last]), r: 4, fill: col('surface'), stroke: c, 'stroke-width': 2.2 }, f.svg);
        }
      });
      interact(host, f, cfg, function (i) {
        return cfg.series.map(function (s, si) {
          return { name: s.name || '', color: col(s.color || ('c' + (si + 1))), value: fmtVal(s, (s.data || [])[i], cfg) };
        });
      }, function (i, g) {
        cfg.series.forEach(function (s, si) {
          var v = (s.data || [])[i];
          if (v === null || v === undefined || isNaN(v)) return;
          E('circle', { cx: f.xf(i), cy: f.yf(v), r: 5, fill: col(s.color || ('c' + (si + 1))), stroke: col('surface'), 'stroke-width': 2 }, g);
        });
      });
    });
  }

  /* ---------- میله‌ای (با خط روی آن، اختیاری) ---------- */
  function bar(el, cfg) {
    var host = typeof el === 'string' ? document.getElementById(el) : el;
    return mount(host, function () {
      var data = cfg.data || [];
      var mx = Math.max.apply(null, data.concat([0, cfg.target ? (cfg.target.value || cfg.target) : 0]));
      var f = frame(host, Object.assign({ band: true }, cfg), mx, 0);
      var c = col(cfg.color || 'c1');
      var bw = Math.max(3, Math.min(34, f.band * 0.62));
      var gid = 'b' + (++uid);
      var fill = gradient(f.svg, c, gid, 1, 0.55);
      data.forEach(function (v, i) {
        if (!v) return;
        var y = f.yf(v), h = f.yf(0) - y, x = f.xf(i) - bw / 2;
        var colr = cfg.colorFn ? col(cfg.colorFn(v, i)) : null;
        var r = E('rect', { x: x, y: y, width: bw, height: Math.max(0, h), rx: Math.min(6, bw / 2), fill: colr || fill }, f.svg);
        if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
          r.style.transformOrigin = 'center ' + f.yf(0) + 'px'; r.style.transformBox = 'view-box';
          r.animate([{ transform: 'scaleY(0)' }, { transform: 'scaleY(1)' }], { duration: 600, easing: 'cubic-bezier(.22,.7,.3,1)', delay: i * 12 });
        }
      });
      var ov = cfg.overlay;
      if (ov) {
        var oc = col(ov.color || 'c2');
        var omax = ov.max || niceMax(Math.max.apply(null, ov.data.concat([1])));
        var oy = function (v) { return f.P.t + f.ih - v / omax * f.ih; };
        segments(ov.data.map(function (v) { return v || null; }), f.xf, oy).forEach(function (pts) {
          E('path', { d: smoothPath(pts), fill: 'none', stroke: oc, 'stroke-width': 2.2, 'stroke-dasharray': '6 4', 'stroke-linecap': 'round' }, f.svg);
          pts.forEach(function (p) { E('circle', { cx: p[0], cy: p[1], r: 2.6, fill: oc }, f.svg); });
        });
      }
      interact(host, f, cfg, function (i) {
        var rows = [{ name: cfg.name || '', color: c, value: fmtVal(cfg, data[i], cfg) }];
        if (ov) rows.push({ name: ov.name || '', color: col(ov.color || 'c2'), value: fmtVal(ov, ov.data[i], cfg) });
        (cfg.extra || []).forEach(function (x) { rows.push({ name: x.name, color: col(x.color || 'muted'), value: fmtVal(x, x.data[i], cfg) }); });
        return rows;
      });
    });
  }

  /* ---------- میله انباشته ---------- */
  function stack(el, cfg) {
    var host = typeof el === 'string' ? document.getElementById(el) : el;
    return mount(host, function () {
      var n = cfg.labels.length, totals = [];
      for (var i = 0; i < n; i++) totals[i] = cfg.series.reduce(function (a, s) { return a + (s.data[i] || 0); }, 0);
      var f = frame(host, Object.assign({ band: true }, cfg), Math.max.apply(null, totals.concat([cfg.target || 0, 1])), 0);
      var bw = Math.max(3, Math.min(34, f.band * 0.62));
      for (i = 0; i < n; i++) {
        var acc = 0;
        cfg.series.forEach(function (s, si) {
          var v = s.data[i] || 0; if (!v) return;
          var y0 = f.yf(acc), y1 = f.yf(acc + v); acc += v;
          E('rect', { x: f.xf(i) - bw / 2, y: y1, width: bw, height: Math.max(0, y0 - y1 - 1.5),
            rx: 3, fill: col(s.color || ('c' + (si + 1))) }, f.svg);
        });
      }
      interact(host, f, cfg, function (i) {
        var rows = cfg.series.map(function (s, si) { return { name: s.name, color: col(s.color || ('c' + (si + 1))), value: fmtVal(s, s.data[i], cfg) }; });
        rows.push({ name: 'جمع', color: 'transparent', value: fmtVal({}, totals[i], cfg) });
        return rows;
      });
    });
  }

  /* ---------- دونات ---------- */
  function donut(el, cfg) {
    var host = typeof el === 'string' ? document.getElementById(el) : el;
    return mount(host, function () {
      var size = cfg.size || 200, R = size / 2, r = R * (cfg.thickness || 0.68);
      host.innerHTML = '';
      var wrap = document.createElement('div');
      wrap.style.cssText = 'display:flex;align-items:center;gap:20px;flex-wrap:wrap;justify-content:center';
      host.appendChild(wrap);
      var holder = document.createElement('div');
      holder.style.cssText = 'position:relative;width:' + size + 'px;max-width:100%;flex:none';
      wrap.appendChild(holder);
      var svg = E('svg', { viewBox: '0 0 ' + size + ' ' + size, role: 'img', 'aria-label': cfg.title || '' }, holder);
      var total = cfg.data.reduce(function (a, b) { return a + (b || 0); }, 0);
      if (!total) {
        E('circle', { cx: R, cy: R, r: (R + r) / 2, fill: 'none', stroke: col('surface-3'), 'stroke-width': R - r }, svg);
      }
      var a0 = -Math.PI / 2, gap = cfg.data.filter(Boolean).length > 1 ? 0.025 : 0;
      cfg.data.forEach(function (v, i) {
        if (!v) return;
        var ang = v / total * Math.PI * 2, a1 = a0 + ang;
        var s0 = a0 + gap / 2, s1 = a1 - gap / 2, large = s1 - s0 > Math.PI ? 1 : 0;
        var p = function (rad, a) { return [R + rad * Math.cos(a), R + rad * Math.sin(a)]; };
        var o0 = p(R - 2, s0), o1 = p(R - 2, s1), i1 = p(r, s1), i0 = p(r, s0);
        var d = 'M' + o0 + 'A' + (R - 2) + ',' + (R - 2) + ' 0 ' + large + ' 1 ' + o1 + 'L' + i1 + 'A' + r + ',' + r + ' 0 ' + large + ' 0 ' + i0 + 'Z';
        var c = col(cfg.colors ? cfg.colors[i] : ('c' + (i % 6 + 1)));
        var seg = E('path', { d: d, fill: c, style: 'cursor:pointer;transition:opacity .15s' }, svg);
        var label = cfg.labels[i], pct = v / total * 100;
        seg.addEventListener('pointermove', function (e) {
          svg.querySelectorAll('path').forEach(function (q) { q.style.opacity = q === seg ? 1 : .45; });
          showTip(tipRows(label, [{ name: BH.pct(pct, 1), color: c, value: (cfg.fmt || BH.n)(v) }]), e.clientX, e.clientY);
        });
        seg.addEventListener('pointerleave', function () {
          svg.querySelectorAll('path').forEach(function (q) { q.style.opacity = 1; }); hideTip();
        });
        a0 = a1;
      });
      var center = document.createElement('div');
      center.style.cssText = 'position:absolute;inset:0;display:grid;place-items:center;text-align:center;pointer-events:none;line-height:1.35';
      center.innerHTML = '<div><div style="font-size:' + Math.round(size / 9) + 'px;font-weight:800">' + BH.esc(cfg.centerValue !== undefined ? cfg.centerValue : (cfg.fmt || BH.n)(total)) +
        '</div><div style="font-size:12px;color:var(--muted)">' + BH.esc(cfg.centerLabel || 'جمع') + '</div></div>';
      holder.appendChild(center);
      if (cfg.legend !== false) {
        var lg = document.createElement('div');
        lg.style.cssText = 'display:flex;flex-direction:column;gap:7px;min-width:160px;flex:1';
        lg.innerHTML = cfg.data.map(function (v, i) {
          if (!v && cfg.hideZero) return '';
          var c = col(cfg.colors ? cfg.colors[i] : ('c' + (i % 6 + 1)));
          return '<div style="display:flex;align-items:center;justify-content:space-between;gap:10px;font-size:13px">' +
            '<span style="display:inline-flex;align-items:center;gap:8px;min-width:0"><i style="width:10px;height:10px;border-radius:3px;background:' + c + ';flex:none"></i>' +
            '<span style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">' + BH.esc(cfg.labels[i]) + '</span></span>' +
            '<span class="num" style="color:var(--muted);white-space:nowrap">' + (total ? BH.pct(v / total * 100) : '—') + '</span></div>';
        }).join('');
        wrap.appendChild(lg);
      }
    });
  }

  /* ---------- پراکندگی ---------- */
  function scatter(el, cfg) {
    var host = typeof el === 'string' ? document.getElementById(el) : el;
    return mount(host, function () {
      var W = Math.max(280, host.clientWidth || 500), H = cfg.height || 260;
      var P = { t: 14, r: 14, b: 40, l: 44 };
      var svg = svgFor(host, W, H, cfg.title);
      var xs = cfg.points.map(function (p) { return p.x; }), ys = cfg.points.map(function (p) { return p.y; });
      var x0 = cfg.xMin !== undefined ? cfg.xMin : Math.min.apply(null, xs.concat([0]));
      var x1 = cfg.xMax !== undefined ? cfg.xMax : niceMax(Math.max.apply(null, xs.concat([1])));
      var y0 = cfg.yMin !== undefined ? cfg.yMin : 0, y1 = cfg.yMax !== undefined ? cfg.yMax : niceMax(Math.max.apply(null, ys.concat([1])));
      var xf = function (v) { return P.l + (v - x0) / (x1 - x0 || 1) * (W - P.l - P.r); };
      var yf = function (v) { return H - P.b - (v - y0) / (y1 - y0 || 1) * (H - P.t - P.b); };
      for (var k = 0; k <= 4; k++) {
        var yv = y0 + (y1 - y0) * k / 4, xv = x0 + (x1 - x0) * k / 4;
        E('line', { x1: P.l, x2: W - P.r, y1: yf(yv), y2: yf(yv), stroke: col('c-grid'), 'stroke-dasharray': k ? '3 4' : null }, svg);
        T(svg, P.l - 8, yf(yv) + 4, compact(yv), { anchor: 'end' });
        T(svg, xf(xv), H - P.b + 16, compact(xv));
      }
      if (cfg.xTitle) T(svg, (W + P.l) / 2, H - 4, cfg.xTitle, { size: 11.5, weight: 600 });
      if (cfg.trend && cfg.points.length > 2) {
        var n = cfg.points.length, mx = xs.reduce(function (a, b) { return a + b; }, 0) / n, my = ys.reduce(function (a, b) { return a + b; }, 0) / n;
        var num = 0, den = 0;
        cfg.points.forEach(function (p) { num += (p.x - mx) * (p.y - my); den += (p.x - mx) * (p.x - mx); });
        if (den) {
          var sl = num / den, ic = my - sl * mx;
          E('line', { x1: xf(x0), y1: yf(sl * x0 + ic), x2: xf(x1), y2: yf(sl * x1 + ic), stroke: col('muted'), 'stroke-width': 1.5, 'stroke-dasharray': '6 5' }, svg);
        }
      }
      var c = col(cfg.color || 'c4');
      cfg.points.forEach(function (p) {
        var dot = E('circle', { cx: xf(p.x), cy: yf(p.y), r: p.r || 6, fill: p.color ? col(p.color) : c, 'fill-opacity': .75,
          stroke: col('surface'), 'stroke-width': 1.5, style: 'cursor:pointer' }, svg);
        dot.addEventListener('pointermove', function (e) {
          showTip(tipRows(p.label || '', (p.rows || [{ name: cfg.yTitle || 'y', value: BH.n(p.y, 1) }, { name: cfg.xTitle || 'x', value: BH.n(p.x, 1) }])
            .map(function (r) { return { name: r.name, value: r.value, color: p.color ? col(p.color) : c }; })), e.clientX, e.clientY);
        });
        dot.addEventListener('pointerleave', hideTip);
      });
    });
  }

  /* ---------- حلقه پیشرفت (HTML + SVG) ---------- */
  function ring(el, cfg) {
    var host = typeof el === 'string' ? document.getElementById(el) : el;
    if (!host) return;
    var size = cfg.size || 92, sw = cfg.stroke || 9, r = (size - sw) / 2, C = 2 * Math.PI * r;
    var pct = Math.max(0, Math.min(1, cfg.max ? cfg.value / cfg.max : 0));
    host.classList.add('ring');
    host.style.width = size + 'px'; host.style.height = size + 'px';
    host.innerHTML = '<svg width="' + size + '" height="' + size + '" viewBox="0 0 ' + size + ' ' + size + '" aria-hidden="true">' +
      '<circle cx="' + size / 2 + '" cy="' + size / 2 + '" r="' + r + '" fill="none" stroke="var(--surface-3)" stroke-width="' + sw + '"/>' +
      '<circle cx="' + size / 2 + '" cy="' + size / 2 + '" r="' + r + '" fill="none" stroke="' + (cfg.color ? 'var(--' + cfg.color + ')' : 'var(--acc,var(--primary))') +
      '" stroke-width="' + sw + '" stroke-linecap="round" stroke-dasharray="' + C + '" stroke-dashoffset="' + C + '" style="transition:stroke-dashoffset 1s cubic-bezier(.22,.7,.3,1)"/></svg>' +
      '<div class="ring-label"><b>' + BH.esc(cfg.label !== undefined ? cfg.label : BH.pct(pct * 100)) + '</b>' + (cfg.sub ? '<span>' + BH.esc(cfg.sub) + '</span>' : '') + '</div>';
    host.setAttribute('role', 'img');
    host.setAttribute('aria-label', (cfg.title || '') + ' ' + BH.pct(pct * 100));
    var arc = host.querySelectorAll('circle')[1];
    requestAnimationFrame(function () { requestAnimationFrame(function () { arc.style.strokeDashoffset = C * (1 - pct); }); });
  }

  /* ---------- اسپارک‌لاین ---------- */
  function spark(el, data, color) {
    var host = typeof el === 'string' ? document.getElementById(el) : el;
    return mount(host, function () {
      var W = Math.max(80, host.clientWidth || 160), H = host.clientHeight || 36;
      var svg = svgFor(host, W, H, '');
      var vals = (data || []).filter(function (v) { return v !== null && v !== undefined && !isNaN(v); });
      if (vals.length < 2) return;
      var mx = Math.max.apply(null, vals), mn = Math.min.apply(null, vals), sp = (mx - mn) || 1;
      var c = col(color || 'c1');
      var xf = function (i) { return 2 + (W - 4) * i / (data.length - 1); };
      var yf = function (v) { return H - 3 - (v - mn) / sp * (H - 8); };
      segments(data, xf, yf).forEach(function (pts) {
        var gid = 's' + (++uid);
        E('path', { d: smoothPath(pts) + 'L' + pts[pts.length - 1][0] + ',' + H + 'L' + pts[0][0] + ',' + H + 'Z', fill: gradient(svg, c, gid, .22, 0) }, svg);
        E('path', { d: smoothPath(pts), fill: 'none', stroke: c, 'stroke-width': 1.8, 'stroke-linecap': 'round' }, svg);
      });
    });
  }

  window.BHChart = { line: line, bar: bar, stack: stack, donut: donut, scatter: scatter, ring: ring, spark: spark,
    color: col, compact: compact, showTip: showTip, hideTip: hideTip, tipRows: tipRows };
})();
