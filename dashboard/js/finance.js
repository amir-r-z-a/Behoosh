const API_BASE=(window.BEHOOSH&&window.BEHOOSH.apiBase)||'https://behoosh-api.hashpa.com/v1';
let CACHE={};

function getToken(){ try{ return localStorage.getItem('behoosh_token')||''; }catch(e){ return ''; } }
function logout(){
  try{ localStorage.removeItem('behoosh_token'); localStorage.removeItem('behoosh_scopes'); }catch(e){}
  location.replace('login.html');
}
async function apiGet(path){
  const token=getToken();
  const r=await fetch(API_BASE+path,{headers:token?{'X-API-Key':token}:{}});
  if(r.status===401||r.status===403){ logout(); throw new Error('auth'); }
  if(!r.ok)throw new Error('HTTP '+r.status);
  return r.json();
}
function el(id){ return document.getElementById(id); }
function esc(s){ return String(s==null?'':s).replace(/[&<>"]/g,function(c){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
function money(v){
  const n=Number(v||0);
  return n.toLocaleString('fa-IR',{maximumFractionDigits:0})+' تومان';
}
function jdate(s){
  if(!s)return '';
  try{ return new Date(s).toLocaleDateString('fa-IR'); }catch(e){ return String(s).slice(0,10); }
}
function empty(t){ return '<div class="empty">'+t+'</div>'; }

// ---------- نمای کلی ----------
async function loadOver(){
  const d=await apiGet('/finance/summary?period=month');
  const net=Number(d.net||0);
  el('k-over').innerHTML=
    '<div class="kpi"><div class="lbl">درآمد این ماه</div><div class="val ok">'+esc(money(d.income))+'</div></div>'+
    '<div class="kpi"><div class="lbl">هزینه این ماه</div><div class="val bad">'+esc(money(d.expense))+'</div></div>'+
    '<div class="kpi"><div class="lbl">خالص</div><div class="val '+(net>=0?'blue':'bad')+'">'+esc(money(net))+'</div>'+
      '<div class="sub">'+esc((d.from||'')+' تا '+(d.to||''))+'</div></div>';
  const cats=d.by_category||[];
  if(!cats.length){ el('over-cats').innerHTML=empty('هنوز هزینه‌ای در این ماه ثبت نشده.'); return; }
  const max=Math.max.apply(null,cats.map(function(c){return Number(c.amount)||0;}))||1;
  el('over-cats').innerHTML='<div class="tl">'+cats.map(function(c){
    const pct=Math.round((Number(c.amount)||0)/max*100);
    return '<div class="row"><div class="l" style="flex:1">'+esc(c.category)+
      '<div class="track"><i style="width:'+pct+'%"></i></div></div>'+
      '<div class="r">'+esc(money(c.amount))+'</div></div>';
  }).join('')+'</div>';
}

// ---------- حساب‌ها ----------
async function loadAcc(){
  const d=await apiGet('/finance/accounts');
  const rows=d.accounts||[];
  if(!rows.length){ el('acc-list').innerHTML=empty('حسابی ثبت نشده.'); return; }
  el('acc-list').innerHTML='<div class="tl">'+rows.map(function(a){
    const t={asset:'دارایی',expense:'هزینه',income:'درآمد',liability:'بدهی'}[a.type]||a.type;
    return '<div class="row"><div class="l"><span>'+esc(a.name)+' <span class="badge">'+esc(t)+'</span></span>'+
      (a.card_last4?'<small>کارت •••• '+esc(a.card_last4)+'</small>':'')+'</div>'+
      '<div class="r amt '+(Number(a.balance)>=0?'credit':'debit')+'">'+esc(money(a.balance))+'</div></div>';
  }).join('')+'</div>';
}

// ---------- تراکنش‌ها ----------
async function loadTx(){
  const period=el('tx-period').value;
  const d=await apiGet('/finance/transactions?limit=100');
  const rows=d.transactions||[];
  if(!rows.length){ el('tx-list').innerHTML=empty('تراکنشی ثبت نشده.'); return; }
  el('tx-list').innerHTML='<div class="tl">'+rows.map(function(t){
    const deb=t.direction==='debit';
    return '<div class="row"><div class="l"><span>'+esc(t.description||t.counterparty||'بدون شرح')+'</span>'+
      '<small>'+esc(jdate(t.occurred_at))+(t.category?' • '+esc(t.category):'')+
      (t.source?' • '+esc(t.source):'')+'</small></div>'+
      '<div class="r amt '+(deb?'debit':'credit')+'">'+(deb?'−':'+')+esc(money(t.amount))+'</div></div>';
  }).join('')+'</div>';
}

// ---------- بودجه ----------
async function loadBud(){
  const d=await apiGet('/finance/budget');
  const rows=d.budgets||[];
  if(!rows.length){ el('bud-list').innerHTML=empty('بودجه‌ای تعریف نشده.'); return; }
  el('bud-list').innerHTML='<div class="tl">'+rows.map(function(b){
    const pct=Math.min(100,Number(b.pct)||0);
    const cls=b.over?'bad':(pct>=80?'warn':'ok');
    return '<div class="row"><div class="l" style="flex:1"><span>'+esc(b.category)+
      ' <span class="badge '+cls+'">'+esc(pct.toLocaleString('fa-IR'))+'٪</span></span>'+
      '<div class="track '+cls+'"><i style="width:'+pct+'%"></i></div>'+
      '<small>'+esc(money(b.spent))+' از '+esc(money(b.budget))+
      ' — باقی '+esc(money(b.remaining))+'</small></div></div>';
  }).join('')+'</div>';
}

// ---------- دسته‌ها ----------
async function loadCat(){
  const d=await apiGet('/finance/categories');
  const rows=d.categories||[];
  if(!rows.length){ el('cat-list').innerHTML=empty('دسته‌ای ثبت نشده.'); return; }
  const exp=rows.filter(function(c){return c.kind==='expense';});
  const inc=rows.filter(function(c){return c.kind==='income';});
  el('cat-list').innerHTML=
    '<h2>هزینه</h2><div class="chips">'+(exp.length?exp.map(function(c){
      return '<span class="chip">'+esc(c.name)+'</span>';}).join(''):'<span class="chip">—</span>')+'</div>'+
    '<h2>درآمد</h2><div class="chips">'+(inc.length?inc.map(function(c){
      return '<span class="chip">'+esc(c.name)+'</span>';}).join(''):'<span class="chip">—</span>')+'</div>';
}

// ---------- پیامک‌ها ----------
async function loadSms(){
  const d=await apiGet('/finance/raw?limit=50');
  const rows=d.messages||[];
  if(!rows.length){ el('sms-list').innerHTML=empty('پیامکی ثبت نشده.'); return; }
  el('sms-list').innerHTML='<div class="tl">'+rows.map(function(m){
    const cls=m.parsed?'ok':'warn';
    return '<div class="row"><div class="l"><span>'+esc(m.body)+'</span>'+
      '<small>'+esc(jdate(m.received_at))+(m.bank?' • '+esc(m.bank):'')+'</small></div>'+
      '<div class="r"><span class="badge '+cls+'">'+(m.parsed?'دسته‌بندی‌شده':'در صف')+'</span></div></div>';
  }).join('')+'</div>';
}

// ---------- گزارش ایجنت ----------
async function loadAud(){
  const d=await apiGet('/finance/audit?limit=50');
  const rows=d.audit||[];
  if(!rows.length){ el('aud-list').innerHTML=empty('نوشتنی از ایجنت ثبت نشده.'); return; }
  el('aud-list').innerHTML='<div class="tl">'+rows.map(function(a){
    return '<div class="row"><div class="l"><span>'+esc(a.tool)+'</span>'+
      '<small>'+esc(jdate(a.created_at))+' • '+esc(a.actor)+'</small></div>'+
      '<div class="r"><span class="badge">'+esc(a.id.slice(0,8))+'</span></div></div>';
  }).join('')+'</div>';
}

const LOADERS={over:loadOver,acc:loadAcc,tx:loadTx,bud:loadBud,cat:loadCat,sms:loadSms,aud:loadAud};

function showTab(t){
  document.querySelectorAll('.pill').forEach(function(x){
    x.classList.toggle('active',x.dataset.t===t); });
  document.querySelectorAll('.panel').forEach(function(x){
    x.classList.toggle('active',x.id===t); });
  const fn=LOADERS[t];
  if(fn)fn().catch(function(e){
    if(e&&e.message==='auth')return;
    el(t).innerHTML='<div class="empty">بارگذاری نشد: '+esc(e.message)+'</div>';
  });
}

document.querySelectorAll('.pill').forEach(function(b){
  b.addEventListener('click',function(){ showTab(b.dataset.t); });
});
el('tx-period').addEventListener('change',function(){
  loadTx().catch(function(){});
});

async function boot(){
  if(!getToken()){ location.replace('login.html'); return; }
  try{ await loadOver(); }
  catch(e){
    if(e&&e.message==='auth')return;
    const b=document.createElement('div'); b.className='err';
    b.textContent='اتصال به API برقرار نشد'; document.body.appendChild(b);
  }
}
boot();
