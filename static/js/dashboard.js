/* Dashboard front end: fetches API data, renders charts, handles filters, files, tabs, theme, print. */
(() => {
'use strict';
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const PAL = { blue: '#1538FF', purple: '#8A2BE2', orange: '#FF9900', red: '#D92D3A', teal: '#12B5A6', sky: '#5B7CFA' };
const DONUT = [PAL.blue, PAL.purple, PAL.orange, PAL.teal, PAL.red, PAL.sky];
const FILTERS = ['year', 'month', 'category', 'state', 'status'];
const DATES = ['from', 'to'];
const ALL = '__all__';
const S = { file: '', files: [], data: {}, charts: {}, metric: 'sales', tab: 'overview' };

/* ---------- formatting (Indian style) ---------- */
const grp = (n) => { const s = String(Math.round(Math.abs(n))); const g = s.length > 3 ? s.slice(0, -3).replace(/\B(?=(\d\d)+(?!\d))/g, ',') + ',' + s.slice(-3) : s; return (n < 0 ? '-' : '') + g; };
const inr = (v) => { const a = Math.abs(v), s = v < 0 ? '-' : ''; return a >= 1e7 ? `${s}₹${(a / 1e7).toFixed(2)} Cr` : a >= 1e5 ? `${s}₹${(a / 1e5).toFixed(2)} Lakh` : `${s}₹${grp(a)}`; };
const short = (v) => { const a = Math.abs(v), s = v < 0 ? '-' : ''; return a >= 1e7 ? `${s}${+(a / 1e7).toFixed(1)} Cr` : a >= 1e5 ? `${s}${+(a / 1e5).toFixed(1)} L` : a >= 1e3 ? `${s}${+(a / 1e3).toFixed(1)}k` : String(v); };
const pct = (v) => `${Number(v).toFixed(1)}%`;
const esc = (t) => String(t).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

/* ---------- UI helpers ---------- */
let pending = 0;
const loader = (on) => { pending = Math.max(0, pending + (on ? 1 : -1)); $('#loader').hidden = pending === 0; };
function toast(msg, err) { const t = $('#toast'); t.textContent = msg; t.className = 'toast' + (err ? ' err' : ''); t.hidden = false; clearTimeout(toast.t); toast.t = setTimeout(() => (t.hidden = true), 4500); }
async function getJSON(url, opts) {
  const r = await fetch(url, opts); let d = {};
  try { d = await r.json(); } catch (e) { /* non-JSON error page */ }
  if (!r.ok) throw new Error(d.error || `Request failed (${r.status})`);
  return d;
}
const postJSON = (url, body) => getJSON(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
const setText = (id, t) => { const el = $('#' + id); if (el) el.textContent = t || ''; };

/* ---------- charts ---------- */
const valOf = (c) => (c.chart.options.indexAxis === 'y' ? c.parsed.x : c.parsed.y !== undefined ? c.parsed.y : c.parsed);
function mk(id, type, data, opts) {
  if (S.charts[id]) S.charts[id].destroy();
  S.charts[id] = new Chart($('#' + id), { type, data, options: opts });
}
function baseOpts(fmt, tick = short, horizontal = false) {
  const txt = css('--muted'), grid = css('--grid');
  const val = { ticks: { color: txt, callback: (v) => tick(v) }, grid: { color: grid }, beginAtZero: true };
  const cat = { ticks: { color: txt }, grid: { display: false } };
  return {
    responsive: true, maintainAspectRatio: false, indexAxis: horizontal ? 'y' : 'x',
    interaction: { mode: 'index', intersect: false },
    plugins: { legend: { labels: { color: txt, usePointStyle: true } },
      tooltip: { callbacks: { label: (c) => ` ${c.dataset.label || c.label}: ${fmt(valOf(c))}` } } },
    scales: horizontal ? { x: val, y: cat } : { x: cat, y: val },
  };
}
const donutOpts = (fmt) => ({ responsive: true, maintainAspectRatio: false, cutout: '62%',
  plugins: { legend: { position: 'bottom', labels: { color: css('--muted'), usePointStyle: true } },
    tooltip: { callbacks: { label: (c) => ` ${c.label}: ${fmt(c.parsed)}` } } } });
const redOrBlue = (rows, key) => rows.map((r) => (r.attention || r[key] < 0 ? PAL.red : PAL.blue));

/* ---------- rendering ---------- */
function activeFilters() {
  const parts = FILTERS.map((k) => $('#f-' + k)).filter((el) => el.value).map((el) => el.selectedOptions[0].textContent);
  if ($('#f-from').value) parts.push('from ' + $('#f-from').value);
  if ($('#f-to').value) parts.push('to ' + $('#f-to').value);
  return parts.length ? parts.join(' + ') : 'all data';
}
function panelState(name, d) {
  const p = $('#panel-' + name); const empty = !d || d.empty === true;
  if (empty && d && d.nodata) {
    p.querySelector('.empty-state').textContent = 'No data yet. Click "Upload Data" at the top and choose your .xlsx or .csv file.';
  } else if (empty) {
    const m = (d && d.meta) || {};
    p.querySelector('.empty-state').textContent = `No orders for: ${activeFilters()}. ` + (m.from ? `The data covers ${m.from} to ${m.to}. ` : '') + 'Change a filter or press Reset Filters.';
  }
  if (empty) p.classList.add('is-empty'); else p.classList.remove('is-empty');
  return !empty;
}
function kpis(id, list) {
  $('#' + id).innerHTML = list.map((k) => `<div class="kpi ${k.bad ? 'bad' : ''}"><div class="ico" aria-hidden="true">${k.icon}</div><div class="val">${esc(k.display)}</div><div class="lbl">${esc(k.label)}</div></div>`).join('');
}
function renderOverview(d) {
  if (!panelState('overview', d)) return;
  kpis('kpi-overview', d.kpis);
  const o = baseOpts(inr);
  o.scales.y1 = { position: 'right', beginAtZero: true, grid: { display: false }, ticks: { color: css('--muted'), callback: (v) => short(v) } };
  o.plugins.tooltip.callbacks.label = (c) => ` ${c.dataset.label}: ${inr(c.parsed.y)}`;
  mk('c-trend', 'bar', { labels: d.trend.labels, datasets: [
    { type: 'bar', label: 'Sales', data: d.trend.sales, backgroundColor: 'rgba(21,56,255,.75)', borderRadius: 4, yAxisID: 'y', order: 2 },
    { type: 'line', label: 'Profit', data: d.trend.profit, borderColor: PAL.orange, backgroundColor: PAL.orange, tension: .3, pointRadius: 3, yAxisID: 'y1', order: 1 }] }, o);
  setText('ins-trend', d.insights.trend);
}
function renderProducts(d) {
  if (!panelState('products', d)) return;
  const c = d.categories, labels = c.map((r) => r.name);
  mk('c-cat-sales', 'bar', { labels, datasets: [{ label: 'Sales', data: c.map((r) => r.sales), backgroundColor: PAL.blue, borderRadius: 4 }] }, baseOpts(inr));
  mk('c-cat-profit', 'bar', { labels, datasets: [{ label: 'Profit', data: c.map((r) => r.profit), backgroundColor: redOrBlue(c, 'profit'), borderRadius: 4 }] }, baseOpts(inr));
  mk('c-cat-units', 'doughnut', { labels, datasets: [{ data: c.map((r) => r.units), backgroundColor: DONUT, borderWidth: 0 }] }, donutOpts(grp));
  const t = d.top_products;
  mk('c-top', 'bar', { labels: t.map((r) => r.name), datasets: [{ label: 'Sales', data: t.map((r) => r.sales), backgroundColor: redOrBlue(t, 'profit'), borderRadius: 4 }] }, baseOpts(inr, short, true));
  $('#tbl-top tbody').innerHTML = t.map((r, i) => `<tr class="${r.attention ? 'attn' : ''}"><td>${i + 1}</td><td>${esc(r.name)}</td><td>${inr(r.sales)}</td><td>${inr(r.profit)}</td><td>${pct(r.margin)}</td><td><span class="badge ${r.attention ? 'red' : ''}">${r.attention ? 'Needs attention' : 'Healthy'}</span></td></tr>`).join('');
  setText('ins-cat-sales', d.insights.sales); setText('ins-cat-profit', d.insights.profit);
  setText('ins-cat-units', d.insights.units); setText('ins-products', d.insights.products);
}
function renderOrders(d) {
  if (!panelState('orders', d)) return;
  kpis('kpi-orders', d.kpis);
  const col = { Delivered: PAL.teal, Shipped: PAL.blue, Returned: PAL.orange, Cancelled: PAL.red };
  const sc = d.status_chart;
  mk('c-status', 'doughnut', { labels: sc.labels, datasets: [{ data: sc.values, backgroundColor: sc.labels.map((l, i) => col[l] || DONUT[i % 6]), borderWidth: 0 }] }, donutOpts(grp));
  const l = d.category_loss;
  mk('c-loss', 'bar', { labels: l.labels, datasets: [
    { label: 'Returned', data: l.returned, backgroundColor: PAL.orange, borderRadius: 4 },
    { label: 'Cancelled', data: l.cancelled, backgroundColor: PAL.red, borderRadius: 4 }] }, baseOpts(grp, (v) => v));
  setText('ins-status', d.insights.status); setText('ins-loss', d.insights.loss);
}
function pairChart(id, rows) {
  mk(id, 'bar', { labels: rows.map((r) => r.name), datasets: [
    { label: 'Sales', data: rows.map((r) => r.sales), backgroundColor: PAL.blue, borderRadius: 4 },
    { label: 'Profit', data: rows.map((r) => r.profit), backgroundColor: PAL.orange, borderRadius: 4 }] }, baseOpts(inr));
}
function renderStates() {
  const g = S.data.geo; if (!g || g.empty) return;
  const m = S.metric, rows = [...g.states].sort((a, b) => b[m] - a[m]).slice(0, 15);
  const label = { sales: 'Sales', profit: 'Profit', orders: 'Orders' }[m];
  const f = m === 'orders' ? grp : inr, tick = m === 'orders' ? (v) => v : short;
  mk('c-state', 'bar', { labels: rows.map((r) => r.name), datasets: [{ label, data: rows.map((r) => r[m]), backgroundColor: rows.map((r) => (r[m] < 0 ? PAL.red : PAL.purple)), borderRadius: 4 }] }, baseOpts(f, tick, true));
  setText('ins-state', g.insights.state[m]);
}
function renderGeo(d) {
  if (!panelState('geo', d)) return;
  pairChart('c-pay', d.payment); pairChart('c-ful', d.fulfillment);
  setText('ins-pay', d.insights.payment); setText('ins-ful', d.insights.fulfillment);
  renderStates();
}
function renderAll() {
  const d = S.data; renderOverview(d.overview); renderProducts(d.products); renderOrders(d.orders); renderGeo(d.geo);
  resizeCharts();
}
const resizeCharts = () => requestAnimationFrame(() => Object.values(S.charts).forEach((c) => c.resize()));

/* ---------- data loading ---------- */
const query = () => {
  const p = new URLSearchParams(); if (S.file) p.set('file', S.file);
  FILTERS.concat(DATES).forEach((k) => { const v = $('#f-' + k).value; if (v) p.set(k, v); });
  return p.toString();
};
let seq = 0;  // guards against slow, older responses overwriting newer ones
async function loadAll() {
  const mine = ++seq;
  loader(true);
  try {
    const q = query();
    const names = ['overview', 'products', 'orders', 'geo'];
    const res = await Promise.all(names.map((n) => getJSON(`/api/${n}?${q}`)));
    if (mine !== seq) return;  // a newer filter change is already loading
    names.forEach((n, i) => (S.data[n] = res[i]));
    renderAll();
  } catch (e) { toast(e.message, true); } finally { loader(false); }
}
async function loadFilters(keep) {
  const f = await getJSON('/api/filters?file=' + encodeURIComponent(S.file));
  const fill = (id, label, items) => {
    const el = $('#f-' + id), prev = keep ? el.value : '';
    el.innerHTML = `<option value="">${label}</option>` + items.map((i) => `<option value="${esc(i.value ?? i)}">${esc(i.name ?? i)}</option>`).join('');
    el.value = [...el.options].some((o) => o.value === prev) ? prev : '';
  };
  fill('year', 'All years', f.years); fill('month', 'All months', f.months); fill('category', 'All categories', f.categories);
  fill('state', 'All states', f.states); fill('status', 'All statuses', f.statuses);
  DATES.forEach((k) => { const el = $('#f-' + k); if (!keep) el.value = ''; el.min = f.date_min || ''; el.max = f.date_max || ''; el.disabled = !!f.nodata; });
}
/* Months list follows the chosen year (e.g. 2026 only offers months that exist in the data). */
async function refreshMonths() {
  const el = $('#f-month'), prev = el.value;
  const f = await getJSON(`/api/filters?file=${encodeURIComponent(S.file)}&year=${encodeURIComponent($('#f-year').value)}`);
  el.innerHTML = '<option value="">All months</option>' + f.months.map((m) => `<option value="${m.value}">${esc(m.name)}</option>`).join('');
  el.value = [...el.options].some((o) => o.value === prev) ? prev : '';
}
const clearFilters = () => FILTERS.concat(DATES).forEach((k) => ($('#f-' + k).value = ''));

/* ---------- files: Save file keeps an upload; Saved files lists everything saved before ---------- */
const UNSAVED = 'unsaved:';
const isUnsaved = () => S.file.startsWith(UNSAVED);
const niceName = (n) => (n.startsWith(UNSAVED) ? n.slice(UNSAVED.length).replace(/^[0-9a-f]{8}__/, '') : n);
function updateChip() {
  const chip = $('#file-chip');
  chip.textContent = !S.file ? 'No file yet' : S.file === ALL ? 'All saved files combined' : isUnsaved() ? `${niceName(S.file)} - not saved yet` : `${S.file} - saved`;
  chip.classList.toggle('unsaved', isUnsaved());
  $('#btn-save').disabled = !isUnsaved(); $('#btn-save').classList.toggle('attention', isUnsaved());
}
async function loadFiles() {
  const r = await getJSON('/api/files'); S.files = r.files; const names = r.files.map((f) => f.name);
  if (!isUnsaved() && (S.file === ALL ? names.length < 2 : !names.includes(S.file))) S.file = r.default;
  updateChip(); renderSaved();
}
function renderSaved() {
  const box = $('#saved-list');
  if (!S.files.length) { box.innerHTML = '<div class="saved-empty">No saved files yet. Click <b>Upload Data</b>, then <b>Save file</b>.</div>'; return; }
  const row = (cls, name, sub, acts) => `<div class="srow ${cls}"><div><div class="nm">${esc(name)}</div><div class="sub">${esc(sub)}</div></div><div class="acts">${acts}</div></div>`;
  let html = S.files.length > 1 ? row(S.file === ALL ? 'on' : '', 'All saved files combined', `${S.files.length} files merged (identical rows count once)`, `<button class="btn primary" data-open="${ALL}">Open</button>`) : '';
  html += S.files.map((f) => row(f.name === S.file ? 'on' : '', f.name, `Saved ${f.updated} - ${f.size_kb} KB${f.name === S.file ? ' - currently open' : ''}`,
    `<button class="btn primary" data-open="${esc(f.name)}">Open</button><button class="btn danger" data-del="${esc(f.name)}">Delete</button>`)).join('');
  box.innerHTML = html;
}
async function openFile(name) {
  S.file = name; clearFilters(); $('#modal').hidden = true; loader(true);
  try { await loadFiles(); await loadFilters(false); await loadAll(); toast('Showing ' + (name === ALL ? 'all saved files combined' : name)); }
  catch (err) { toast(err.message, true); } finally { loader(false); }
}
async function saveFile() {
  if (!isUnsaved()) return;
  loader(true);
  try { const r = await postJSON('/api/save', { name: S.file }); S.file = r.name; await loadFiles(); await loadAll(); toast(r.message); }
  catch (err) { toast(err.message, true); } finally { loader(false); }
}
async function deleteFile(name) {
  if (!confirm(`Delete "${name}" from your saved files? This cannot be undone.`)) return;
  loader(true);
  try {
    const r = await postJSON('/api/delete', { name });
    if (S.file === name) S.file = '';
    await loadFiles(); clearFilters(); await loadFilters(false); await loadAll(); toast(r.message);
  } catch (err) { toast(err.message, true); } finally { loader(false); }
}

/* ---------- events ---------- */
function showTab(name) {
  S.tab = name;
  $$('.tab').forEach((t) => t.classList.toggle('active', t.dataset.tab === name));
  $$('.panel').forEach((p) => p.classList.toggle('active', p.id === 'panel-' + name));
  resizeCharts();
}
function setTheme(t) {
  document.documentElement.dataset.theme = t; $('#btn-theme').textContent = t === 'dark' ? 'Light mode' : 'Dark mode';
  try { localStorage.setItem('theme', t); } catch (e) { /* storage blocked: ignore */ }
  if (S.data.overview) renderAll();
}
function addDownloadButtons() {   // small "Save image" button on every chart card
  $$('.chart canvas').forEach((cv) => {
    const btn = document.createElement('button');
    btn.type = 'button'; btn.className = 'dl'; btn.textContent = 'Save image'; btn.title = 'Download this chart as a PNG picture';
    btn.addEventListener('click', () => {
      const t = document.createElement('canvas'); t.width = cv.width; t.height = cv.height;
      const x = t.getContext('2d'); x.fillStyle = css('--card'); x.fillRect(0, 0, t.width, t.height); x.drawImage(cv, 0, 0);
      const a = document.createElement('a'); a.href = t.toDataURL('image/png'); a.download = cv.id + '.png'; a.click();
    });
    cv.closest('.card').appendChild(btn);
  });
}
function bind() {
  $$('.tab').forEach((t) => t.addEventListener('click', () => showTab(t.dataset.tab)));
  FILTERS.concat(DATES).forEach((k) => $('#f-' + k).addEventListener('change', loadAll));
  $('#f-year').addEventListener('change', async () => { try { await refreshMonths(); } catch (e) { toast(e.message, true); } loadAll(); });
  $('#btn-reset').addEventListener('click', async () => { clearFilters(); try { await refreshMonths(); } catch (e) { /* keep going */ } loadAll(); });
  $('#btn-theme').addEventListener('click', () => setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'));
  $('#btn-print').addEventListener('click', () => window.print());
  $$('#seg-metric button').forEach((b) => b.addEventListener('click', () => {
    S.metric = b.dataset.metric; $$('#seg-metric button').forEach((x) => x.classList.toggle('on', x === b)); renderStates();
  }));
  $('#btn-save').addEventListener('click', saveFile);
  $('#btn-saved').addEventListener('click', async () => { try { await loadFiles(); } catch (e) { toast(e.message, true); } $('#modal').hidden = false; });
  $('#modal-close').addEventListener('click', () => ($('#modal').hidden = true));
  $('#modal').addEventListener('click', (e) => { if (e.target.id === 'modal') e.target.hidden = true; });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') $('#modal').hidden = true; });
  $('#saved-list').addEventListener('click', (e) => {
    const o = e.target.closest('[data-open]'), d = e.target.closest('[data-del]');
    if (o) openFile(o.dataset.open); else if (d) deleteFile(d.dataset.del);
  });
  window.addEventListener('beforeunload', (e) => { if (isUnsaved()) { e.preventDefault(); e.returnValue = ''; } });  // warn: unsaved upload
  $('#btn-upload').addEventListener('click', () => $('#file-input').click());
  $('#file-input').addEventListener('change', async (e) => {
    const file = e.target.files[0]; if (!file) return;
    const fd = new FormData(); fd.append('file', file); loader(true);
    try {
      const r = await getJSON('/api/upload', { method: 'POST', body: fd });
      S.file = r.name; clearFilters(); toast(r.message);
      await loadFiles(); await loadFilters(false); await loadAll();
    } catch (err) { toast(err.message, true); } finally { loader(false); e.target.value = ''; }
  });
  window.addEventListener('beforeprint', resizeCharts); window.addEventListener('afterprint', resizeCharts);
}

/* ---------- start ---------- */
(async function init() {
  let t = 'light';
  try { t = localStorage.getItem('theme') || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'); } catch (e) { /* ignore */ }
  document.documentElement.dataset.theme = t; $('#btn-theme').textContent = t === 'dark' ? 'Light mode' : 'Dark mode';
  bind(); addDownloadButtons();
  loader(true);
  try { await loadFiles(); await loadFilters(false); } catch (e) { toast(e.message, true); } finally { loader(false); }
  await loadAll();
})();
})();
