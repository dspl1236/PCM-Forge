/* WireView — static browser for Porsche SchaltplanViewer data.
 *
 * No server-side code. Navigation and pinouts come from JSON built by
 * build.py; drawings are the original SVG files fetched as-is.
 *
 * Point CONFIG at wherever the data lives relative to this page.
 */
'use strict';

const CONFIG = {
  data:   'data',            // tree.json + pins/ from build.py
  sheets: 'sv_projects',     // the WireView data tree
  styles: 'style_sheets',    // WireView's own CSS, needed to render sheets
  lang:   'en'
};

const $ = (s) => document.querySelector(s);
let TREE = null, WVCSS = null, ZOOM = 1, BASEW = 1200, CUR = null;

/* ---------------------------------------------------------------- data --- */

async function loadTree() {
  if (TREE) return TREE;
  const r = await fetch(CONFIG.data + '/tree.json');
  if (!r.ok) throw new Error('tree.json not found — run build.py');
  TREE = await r.json();
  return TREE;
}

/* WireView's sheets are unreadable without its own stylesheet: common.css
   carries path{fill:none} and the stroke widths, sv_sheet.css carries
   .frame{fill:white} and .text{fill:black}. Missing either renders the sheet
   as a black slab or a page of filled blobs. Scoped to .sheet so its bare
   element selectors cannot reach this page's chrome. */
async function loadWvCss() {
  if (WVCSS !== null) return WVCSS;
  let raw = '';
  for (const name of ['common.css', 'sv_sheet.css']) {
    try {
      const r = await fetch(CONFIG.styles + '/' + name);
      if (r.ok) raw += await r.text();
    } catch (e) { /* keep going; a partial sheet beats none */ }
  }
  raw = raw.replace(/\/\*[\s\S]*?\*\//g, '');
  WVCSS = raw.split('}').map(rule => {
    const i = rule.indexOf('{');
    if (i < 0) return '';
    const sel = rule.slice(0, i).split(',')
      .map(s => s.trim()).filter(Boolean)
      .map(s => '.sheet ' + s).join(',');
    return sel ? sel + '{' + rule.slice(i + 1).trim() + '}' : '';
  }).join('\n');

  const el = document.createElement('style');
  el.textContent = WVCSS;
  document.head.appendChild(el);
  return WVCSS;
}

/* Sheets carry ten language variants inside <switch>. Browsers choose by
   their own locale, which for these files usually means German, so the
   branch is picked explicitly. */
function localize(doc) {
  doc.querySelectorAll('switch').forEach(sw => {
    let pick = null, first = null;
    sw.querySelectorAll(':scope > g[systemLanguage]').forEach(g => {
      if (!first) first = g;
      if (!pick && g.getAttribute('systemLanguage') === CONFIG.lang) pick = g;
    });
    const keep = pick || first;
    if (keep) sw.replaceWith(...keep.childNodes);
    else sw.remove();
  });
}

/* ---------------------------------------------------------------- view --- */

function setZoom(v) {
  const svg = $('#sheet svg');
  if (!svg) return;
  ZOOM = Math.min(12, Math.max(0.05, v));
  svg.style.width = Math.round(BASEW * ZOOM) + 'px';
  svg.style.height = 'auto';
}

function fitWidth() {
  const box = $('#sheet');
  if (box && BASEW) setZoom((box.clientWidth - 24) / BASEW);
}

function crumbFor(id) {
  const parts = [];
  let cur = id;
  while (cur) {
    const n = TREE[cur];
    if (n && n.l) parts.unshift({ id: cur, label: n.l });
    if (cur.indexOf('.') < 0) break;
    cur = cur.slice(0, cur.lastIndexOf('.'));
  }
  const nav = $('#crumb');
  nav.textContent = '';
  parts.forEach((p, i) => {
    if (i) {
      const s = document.createElement('span');
      s.className = 'sep'; s.textContent = '/';
      nav.appendChild(s);
    }
    const a = document.createElement('a');
    a.textContent = p.label;
    a.href = '#' + p.id;
    nav.appendChild(a);
  });
}

function showBrowse(id) {
  const n = TREE[id];
  const box = $('#browse');
  box.textContent = '';
  box.hidden = false;
  $('#split').hidden = true;
  $('#tools').hidden = true;
  $('#status').textContent = '';

  (n ? n.k : []).forEach(kid => {
    const k = TREE[kid];
    if (!k) return;
    const a = document.createElement('a');
    a.textContent = k.l || '(unnamed)';
    a.href = '#' + kid;
    box.appendChild(a);
  });
  if (!box.children.length) $('#status').textContent = 'Nothing here.';
}

async function showSheet(id) {
  const n = TREE[id];
  const parts = n.p.replace(/^\/+|\/+$/g, '').split('/');
  if (parts.length !== 3) { showBrowse(id); return; }
  const [proj, year, sheet] = parts;
  CUR = { proj, year, sheet, label: n.l };

  $('#browse').hidden = true;
  $('#split').hidden = false;
  $('#tools').hidden = false;
  $('#status').textContent = 'loading…';

  await loadWvCss();
  const url = [CONFIG.sheets, proj, year, sheet, 'sheet.svg'].join('/');
  const r = await fetch(url);
  if (!r.ok) { $('#status').textContent = 'sheet not found: ' + url; return; }
  const text = await r.text();

  const doc = new DOMParser().parseFromString(text, 'image/svg+xml');
  const svg = doc.documentElement;
  if (svg.nodeName === 'parsererror' || !svg.viewBox) {
    $('#status').textContent = 'could not parse ' + url;
    return;
  }
  localize(doc);

  /* The sheets are wide and short — 2112x435 units is typical — so a
     percentage width squashes them into an unreadable strip. Natural size
     with scrolling is legible; fit-width stays available. */
  BASEW = svg.viewBox.baseVal.width || 1200;
  svg.removeAttribute('width');
  svg.removeAttribute('height');

  const box = $('#sheet');
  box.textContent = '';
  box.appendChild(document.importNode(svg, true));
  setZoom(1);
  box.scrollTop = 0;
  box.scrollLeft = 0;
  window.scrollTo(0, 0);
  $('#status').textContent = '';

  loadPins(proj, year, sheet, n.l);
}

async function loadPins(proj, year, sheet, label) {
  const side = $('#pins');
  $('#sidetitle').textContent = 'Pinout — ' + (label || sheet);
  side.textContent = 'loading…';
  let data = null;
  try {
    const r = await fetch(`${CONFIG.data}/pins/${proj}/${year}.json`);
    if (r.ok) data = await r.json();
  } catch (e) { /* not built for this project */ }

  const rows = data && data[sheet];
  if (!rows || !rows.length) {
    side.innerHTML = '<p class="empty">No connector pins on this sheet.</p>';
    return;
  }
  const t = document.createElement('table');
  rows.forEach(([pin, sig, wire]) => {
    const tr = document.createElement('tr');
    for (const [cls, val] of [['pin', pin], ['', sig], ['wire', wire]]) {
      const td = document.createElement('td');
      if (cls) td.className = cls;
      td.textContent = val || '';
      tr.appendChild(td);
    }
    t.appendChild(tr);
  });
  side.textContent = '';
  side.appendChild(t);
}

/* ---------------------------------------------------------------- save --- */

function currentSvgMarkup() {
  const svg = $('#sheet svg');
  if (!svg) return null;
  const clone = svg.cloneNode(true);
  /* Inline the scoped stylesheet with the .sheet prefix removed, so the
     saved file stands alone instead of rendering black elsewhere. */
  const st = document.createElementNS('http://www.w3.org/2000/svg', 'style');
  st.textContent = (WVCSS || '').replace(/\.sheet /g, '');
  clone.insertBefore(st, clone.firstChild);
  clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
  return new XMLSerializer().serializeToString(clone);
}

function baseName() {
  return CUR ? [CUR.proj, CUR.year, CUR.sheet].join('_')
                 .replace(/[^\w.-]+/g, '_')
             : 'sheet';
}

function download(blob, name) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
}

function saveSvg() {
  const m = currentSvgMarkup();
  if (m) download(new Blob([m], { type: 'image/svg+xml' }),
                  baseName() + '.svg');
}

function savePng() {
  const markup = currentSvgMarkup();
  const svg = $('#sheet svg');
  if (!markup || !svg) return;
  const vb = svg.viewBox.baseVal;
  /* Sheets are line art, so rasterising at 1:1 is unreadable. Scale up,
     but cap it — a 2112-unit sheet at 4x is already 8448px wide and some
     browsers refuse to draw much beyond that. */
  const scale = Math.min(4, 8000 / (vb.width || 1200));
  const w = Math.round((vb.width || 1200) * scale);
  const h = Math.round((vb.height || 400) * scale);

  const img = new Image();
  img.onload = () => {
    const c = document.createElement('canvas');
    c.width = w; c.height = h;
    const ctx = c.getContext('2d');
    ctx.fillStyle = '#fff';
    ctx.fillRect(0, 0, w, h);
    ctx.drawImage(img, 0, 0, w, h);
    c.toBlob(b => b && download(b, baseName() + '.png'), 'image/png');
  };
  img.onerror = () => { $('#status').textContent =
    'PNG export failed — use Save SVG.'; };
  img.src = 'data:image/svg+xml;charset=utf-8,' +
            encodeURIComponent(markup);
}

/* ---------------------------------------------------------------- wire --- */

function route() {
  const id = location.hash.slice(1) || 'dfs0';
  if (!TREE[id]) { $('#status').textContent = 'unknown page'; return; }
  crumbFor(id);
  const n = TREE[id];
  if (n.p && (!n.k || !n.k.length)) showSheet(id);
  else showBrowse(id);
}

function search(q) {
  q = q.trim().toLowerCase();
  $('#browse').hidden = false;
  $('#split').hidden = true;
  $('#tools').hidden = true;
  const box = $('#browse');
  box.textContent = '';
  if (!q) { route(); return; }
  let n = 0;
  for (const id in TREE) {
    const t = TREE[id];
    if (!t.l || !t.p) continue;
    if (t.l.toLowerCase().indexOf(q) < 0) continue;
    const a = document.createElement('a');
    a.textContent = t.l + '  ·  ' + t.p.replace(/^\//, '');
    a.href = '#' + id;
    box.appendChild(a);
    if (++n >= 300) break;
  }
  $('#status').textContent = n ? n + ' matches' : 'no matches';
}

window.addEventListener('hashchange', route);
document.addEventListener('DOMContentLoaded', async () => {
  document.querySelectorAll('[data-zoom]').forEach(b => {
    b.onclick = () => {
      const k = b.dataset.zoom;
      if (k === 'fit') fitWidth();
      else setZoom(k === 'in' ? ZOOM * 1.35 : k === 'out' ? ZOOM / 1.35 : 1);
    };
  });
  $('#print').onclick = () => window.print();
  $('#saveSvg').onclick = saveSvg;
  $('#savePng').onclick = savePng;
  $('#showPins').onchange = (e) => { $('#side').hidden = !e.target.checked; };
  $('#searchform').onsubmit = (e) => { e.preventDefault(); search($('#q').value); };

  try {
    await loadTree();
    route();
  } catch (e) {
    $('#status').textContent = e.message;
  }
});
