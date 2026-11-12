// 共用核心（core/）的閱讀頁：名詞與關係（關係圖＋卡片）、狀態與事件（狀態圖）、規則、詞彙、變更紀錄
import { $, $$, api, enc, esc, go, inline, md, plain, setTop, state } from './core.js';
import { edgeLabels, edgePath, short } from './confirm.js';
import { flowsHtml } from './flows.js';
import { markNav } from './nav.js';

const TABS = [['entities', '名詞與關係'], ['flows', '狀態與事件'], ['rules', '規則'], ['glossary', '詞彙'], ['changelog', '變更紀錄']];

// [候選]／[已驗證]／[已取代: …]／[已停用: …]
export function statusChip(s) {
  if (!s) return '';
  const cls = s.startsWith('已驗證') ? 'ok' : s.startsWith('已取代') || s.startsWith('已停用') ? 'gone' : 'cand';
  return `<span class="st-chip ${cls}">${esc(s)}</span>`;
}
// 「electricity-emission（② @ electricity-emission/02-v1）」→ 切片＋步驟
export function srcShort(s) {
  const m = String(s || '').match(/^([\w-]+)（(\S+) @ ([^）]+)）/);
  return m ? `<span class="small muted src" title="${esc(s)}">${esc(m[1])} ${esc(m[2])}</span>` : esc(s);
}

export async function renderCore(tab, item) {
  state.slice = null; state.scope = null;
  markNav();
  setTop(['#/', '總覽'], '<strong>共用核心 core/</strong>');
  if (!state.core || !item) state.core = await api('/api/core');
  const C = state.core;
  tab = TABS.some(t => t[0] === tab) ? tab : 'entities';
  const head = `<div class="row spread page-head-row"><div class="page-head"><div class="label">唯讀・各切片 ②③④ 凍結後合併進來</div><h1>共用核心</h1></div>
    <nav class="tabs core-tabs">${TABS.map(([k, n]) => `<a href="#/core/${k}" class="${k === tab ? 'on' : ''}">${n}</a>`).join('')}</nav></div>`;
  if (C.empty) {
    $('#app').innerHTML = head + '<div class="card dashed">還沒有 core/。第一次凍結 ②③④ 時會建立。</div>';
    return;
  }
  const body = { entities: entitiesView, flows: flowsView, rules: rulesView, glossary: glossaryView, changelog: changelogView }[tab](C, item);
  $('#app').innerHTML = `<div class="core-view">${head}${body}</div>`;
  bindCore(C, tab, item);
}

// ---------- 名詞與關係 ----------

// 由上到下：被指到的在上面（Organization），指出去的在下面；同一排依相連的位置排，少一點交叉
export function coreLayout(ents, rels) {
  const ids = new Set(ents.map(e => e.id));
  const out = new Map(ents.map(e => [e.id, rels.filter(r => r.from === e.id && r.to !== e.id && ids.has(r.to)).map(r => r.to)]));
  const rank = new Map();
  const rk = (id, seen = new Set()) => {
    if (rank.has(id)) return rank.get(id);
    if (seen.has(id)) return 0;
    seen.add(id);
    const v = out.get(id).length ? 1 + Math.max(...out.get(id).map(t => rk(t, seen))) : 0;
    rank.set(id, v);
    return v;
  };
  ents.forEach(e => rk(e.id));
  const rows = [];
  ents.forEach(e => (rows[rank.get(e.id)] = rows[rank.get(e.id)] || []).push(e.id));
  const W = 136, H = 56, GX = 64, GY = 120, PER = 5;   // 間隔放寬，關係的字放得下（圖可以縮放）
  const pos = new Map();
  const bands = [];
  rows.filter(Boolean).forEach(row => {
    const near = id => {
      const xs = rels.filter(r => r.from === id || r.to === id).map(r => pos.get(r.from === id ? r.to : r.from)).filter(v => v !== undefined);
      return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 99;
    };
    row.sort((a, b) => near(a) - near(b));
    for (let k = 0; k < row.length; k += PER) {
      const band = row.slice(k, k + PER);
      band.forEach((id, j) => pos.set(id, j + 0.5 - band.length / 2));
      bands.push(band);
    }
  });
  const width = Math.max(...bands.map(b => b.length)) * (W + GX) - GX + 80;
  const nodes = new Map();
  bands.forEach((band, bi) => {
    const rowW = band.length * (W + GX) - GX;
    band.forEach((id, k) => nodes.set(id, { id, x: 40 + (width - 80 - rowW) / 2 + k * (W + GX), y: 24 + bi * (H + GY), w: W, h: H }));
  });
  return { nodes, width, height: 48 + bands.length * (H + GY) - GY };
}

function entityMatch(e, C) {
  const layer = (e.fields.find(f => f[0] === '層') || [])[1] || '';
  const q = (state.coreQ || '').trim().toLowerCase();
  if (state.coreLayer && state.coreLayer !== 'all' && layer !== state.coreLayer) return false;
  return !q || `${e.id} ${e.label} ${e.fields.map(f => f[1]).join(' ')} ${e.attrs.map(a => a.name + a.text).join(' ')}`.toLowerCase().includes(q);
}

function entityDiagram(C, sel) {
  const L = coreLayout(C.entities, C.relations);
  const byId = new Map(C.entities.map(e => [e.id, e]));
  const labels = [];
  const edges = C.relations.filter(r => L.nodes.has(r.from) && L.nodes.has(r.to)).map(r => {
    const g = edgePath(L.nodes.get(r.from), L.nodes.get(r.to));
    const hot = sel && (r.from === sel || r.to === sel);
    if (hot) labels.push({ x: g.mx, y: g.my, text: `${r.label || r.name} ${r.card}` });
    return { hot, svg: `<path class="edge ${hot ? 'hot' : ''}" marker-end="url(#carr)" d="${g.d}"><title>${esc(r.from)} ${esc(r.name)}（${esc(r.label)}）→ ${esc(r.to)}　${esc(r.card)}</title></path>` };
  });
  const nodes = [...L.nodes.values()].map(n => {
    const e = byId.get(n.id);
    const cls = ['own', sel === n.id ? 'sel' : '', entityMatch(e, C) ? '' : 'dim', /^已(取代|停用)/.test(e.status) ? 'gone' : ''].join(' ');
    return `<g class="node ${cls}" data-ent="${esc(n.id)}" transform="translate(${n.x},${n.y})">
      <rect width="${n.w}" height="${n.h}" rx="14"></rect>
      <text x="${n.w / 2}" y="25" text-anchor="middle">${esc(short(e.label, 10))}</text>
      <text class="sub" x="${n.w / 2}" y="44" text-anchor="middle">${esc(short(e.id, 22))}</text>
      <title>${esc(plain((e.fields.find(f => f[0] === '定義') || [])[1] || e.id))}</title></g>`;
  });
  // 選到的那個的線畫在最上面
  const es = [...edges.filter(x => !x.hot), ...edges.filter(x => x.hot)].map(x => x.svg).join('');
  const f = sel && L.nodes.get(sel);
  return `<svg width="${L.width}" height="${L.height}" viewBox="0 0 ${L.width} ${L.height}" role="img" aria-label="共用核心的名詞關係圖"${f ? ` data-focus="${f.x + f.w / 2},${f.y + f.h / 2}"` : ''}>
    <defs><marker id="carr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z"></path></marker></defs>${es}${nodes.join('')}${edgeLabels(labels, [...L.nodes.values()])}</svg>`;
}

const MAIN_FIELDS = ['定義', '不是什麼', '不能跟誰合併'];
const LIFE_FIELDS = ['身分', '何時開始', '何時結束'];

function entityPanel(C, id) {
  const e = C.entities.find(x => x.id === id);
  if (!e) return '<p class="muted">點圖上的方塊或下面的卡片，看它是什麼、有哪些屬性、和誰有關係。</p>';
  const f = k => (e.fields.find(x => x[0] === k) || [])[1] || '';
  const rels = C.relations.filter(r => r.from === id || r.to === id);
  const relRow = r => {
    const outward = r.from === id;
    const other = outward ? r.to : r.from;
    const o = C.entities.find(x => x.id === other);
    return `<li><span class="rel-dir">${outward ? '→' : '←'}</span> <b>${esc(r.label || r.name)}</b>
      <a href="#/core/entities/${enc(other)}">${esc(o ? o.label : other)}</a> <span class="muted small">${esc(r.name)}　${esc(r.card)}${r.period === '有' ? '　有期間' : ''}</span>
      ${r.why ? `<div class="small muted">${inline(r.why)}</div>` : ''}</li>`;
  };
  const sm = C.flows && C.flows.machines.find(m => m.id === id);
  const qs = f('對應驗收問題').split(/[、，,]\s*/).filter(Boolean);
  return `<div>${statusChip(e.status)} <span class="chip">${esc(f('層') || '—')}</span>
      <h2>${esc(e.label)}<span class="muted small">　${esc(e.id)}</span></h2><div>${srcShort(f('出處'))}</div></div>
    <div class="box"><div class="label">定義</div>${inline(f('定義'))}</div>
    <dl class="kv">${LIFE_FIELDS.filter(f).map(k => `<dt>${k}</dt><dd>${inline(f(k))}</dd>`).join('')}
      ${['不是什麼', '不能跟誰合併'].filter(f).map(k => `<dt>${k}</dt><dd>${inline(f(k))}</dd>`).join('')}</dl>
    ${e.attrs.length ? `<div><div class="label">屬性（${e.attrs.length}）</div><ul class="attr-list">${e.attrs.map(a => `<li><code>${esc(a.name)}</code>　${inline(a.text)}</li>`).join('')}</ul></div>` : ''}
    ${rels.length ? `<div><div class="label">關係（${rels.length}）</div><ul class="rel-list">${rels.map(relRow).join('')}</ul></div>` : ''}
    ${sm ? `<div class="small"><a href="#/core/flows/${enc(id)}">看它的狀態與事件 ›</a>${sm.transitions.length ? '' : `　（${esc(sm.stateless || '沒有狀態')}）`}</div>` : ''}
    ${qs.length ? `<div class="small"><span class="muted">對應驗收問題：</span>${qs.map(q => `<span class="q-chip">${esc(q)}</span>`).join(' ')}</div>` : ''}
    <div class="small"><span class="muted">被引用：</span>${esc(f('被引用') || '（還沒有）')}</div>
    ${e.fields.filter(([k]) => ![...MAIN_FIELDS, ...LIFE_FIELDS, '出處', '層', '對應驗收問題', '被引用'].includes(k)).map(([k, v]) => `<div class="small"><span class="muted">${esc(k)}：</span>${inline(v)}</div>`).join('')}
    <a class="small ref-link" data-file="core/entities.md" data-line="${e.line}">entities.md 第 ${e.line} 行 ›</a>`;
}

function entitiesView(C, item) {
  const sel = item || state.coreSel || (C.entities[0] || {}).id;
  state.coreSel = sel;
  const layers = [...new Set(C.entities.map(e => (e.fields.find(f => f[0] === '層') || [])[1]).filter(Boolean))];
  const card = e => {
    const def = plain((e.fields.find(f => f[0] === '定義') || [])[1] || '');
    return `<button class="ent-card ${e.id === sel ? 'on' : ''} ${entityMatch(e, C) ? '' : 'dim'}" data-ent="${esc(e.id)}">
      <span class="row spread"><b>${esc(e.label)}</b>${statusChip(e.status)}</span><code class="small">${esc(e.id)}</code>
      <span class="small muted clamp2">${esc(def)}</span></button>`;
  };
  return `
    <p class="muted" style="margin:6px 0 12px">方塊是名詞，箭頭從「指出去的」到「被指到的」（例：據點 → 企業）。點一個方塊看定義、屬性和關係；被選到的那個，關係的名稱和幾對幾會標在線上。</p>
    <div class="row core-filter">
      <input type="search" id="coreQ" placeholder="找名詞、屬性（中文或英文）" value="${esc(state.coreQ || '')}">
      ${layers.length > 1 ? `<span class="todo-chips">${['all', ...layers].map(l => `<button class="todo-chip plain ${(state.coreLayer || 'all') === l ? 'on' : ''}" data-layer="${esc(l)}">${l === 'all' ? '全部' : esc(l)}</button>`).join('')}</span>` : ''}
      <span class="small muted">${C.entities.length} 個名詞、${C.relations.length} 條關係</span>
    </div>
    <div class="model-split">
      <section class="diagram">${entityDiagram(C, sel)}</section>
      <aside class="panel" id="panel">${entityPanel(C, sel)}</aside>
    </div>
    <div class="ent-grid">${C.entities.map(card).join('')}</div>`;
}

// ---------- 狀態與事件 ----------

function flowsView(C, item) {
  if (!C.flows || !C.flows.machines.length) return '<div class="card dashed">還沒有狀態機與事件（第一次凍結 ③ 後才有）。</div>';
  const r = { flows: C.flows, confirms: [] };
  const ms = C.flows.machines;
  const id = (ms.find(m => m.id === item) || ms.find(m => m.transitions.length) || ms[0]).id;
  if (state.coreMach !== id) state.tsel = null;   // 換了名詞，箭頭的選擇歸零
  state.coreMach = id;
  const { html } = flowsHtml(r, id, state.tsel, new Set(),
    '<p class="muted" style="margin:6px 0 0">點名稱看它的狀態圖；點箭頭上的字，看誰可以做、前提條件。⚙ 是系統自動做的；雙框是終點。</p>');
  return html + C.flow_tables.map(t => tableSection(t, t.h2.replace(/（[^）]*）$/, ''))).join('');
}

// ---------- 規則、詞彙、變更紀錄 ----------

const CODE_COLS = new Set(['編號', 'ID', '事件', '代碼', '分類值']);

function cellHtml(h, v) {
  if (h === '狀態') return statusChip(v.replace(/^\[|\]$/g, '')) || esc(v);
  if (h === '出處') return srcShort(v);
  if (CODE_COLS.has(h)) return `<code>${esc(v)}</code>`;
  return inline(v);
}

function searchText(cells) { return esc(cells.join(' ').toLowerCase()); }

export function tableSection(t, title, kindCol) {
  const hide = new Set(['被引用'].filter(h => t.rows.every(r => !(r.cells[t.header.indexOf(h)] || '').trim())));
  const cols = t.header.map((h, i) => [h, i]).filter(([h]) => !hide.has(h));
  return `<section class="core-sec"><h2>${esc(title)}<span class="muted small">　${t.rows.length}</span></h2>
    <div class="tbl core-tbl"><table><thead><tr>${cols.map(([h]) => `<th>${esc(h)}</th>`).join('')}</tr></thead>
    <tbody>${t.rows.map(r => { const k = kindCol ? r.cells[t.header.indexOf(kindCol)] || '' : '';
      return `<tr data-q="${searchText(r.cells)}"${kindCol ? ` data-k="${esc(k)}"` : ''}${k === 'Entity' ? ' class="grp"' : ''}>${cols.map(([h, i]) => `<td>${cellHtml(h, r.cells[i] || '')}</td>`).join('')}</tr>`; }).join('')}</tbody></table></div></section>`;
}

function filterBar(placeholder, kinds) {
  return `<div class="row core-filter"><input type="search" id="coreFind" placeholder="${esc(placeholder)}">
    ${kinds.length > 1 ? `<span class="todo-chips">${['全部', ...kinds].map((k, i) => `<button class="todo-chip plain ${i ? '' : 'on'}" data-kind="${esc(i ? k : '')}">${esc(k)}</button>`).join('')}</span>` : ''}</div>`;
}

function rulesView(C) {
  if (!C.rules.length) return '<div class="card dashed">還沒有規則（第一次凍結 ④ 後才有）。</div>';
  const rt = C.rules.find(t => t.h2 === '規則' && t.header[0] === '編號');
  const others = C.rules.filter(t => t !== rt);
  const col = (r, h) => r.cells[rt.header.indexOf(h)] || '';
  const kinds = rt ? [...new Set(rt.rows.map(r => col(r, '種類')).filter(Boolean))] : [];
  const card = r => `<article class="rule-card" data-q="${searchText(r.cells)}" data-k="${esc(col(r, '種類'))}">
      <div class="row spread"><span><b class="rid">${esc(col(r, '編號'))}</b> <span class="chip">${esc(col(r, '種類'))}</span></span>${statusChip(col(r, '狀態').replace(/^\[|\]$/g, ''))}</div>
      <div class="rule-text">${inline(col(r, '規則'))}</div>
      <dl class="kv small">${['套用對象', '判斷方式', '違反時', '來源', '版本／生效日', '核對'].filter(h => col(r, h) && col(r, h) !== '—')
        .map(h => `<dt>${h}</dt><dd>${h === '套用對象' ? col(r, h).split('、').map(x => `<code>${esc(x)}</code>`).join(' ') : inline(col(r, h))}</dd>`).join('')}</dl>
      <div class="row spread small">${srcShort(col(r, '出處'))}<a class="ref-link" data-file="core/rules.md" data-line="${r.line}">rules.md 第 ${r.line} 行 ›</a></div>
    </article>`;
  return filterBar('找規則（編號、內容、事件名稱）', kinds)
    + (rt ? `<section class="core-sec"><h2>規則<span class="muted small">　${rt.rows.length}</span></h2><div class="rule-list">${rt.rows.map(card).join('')}</div></section>` : '')
    + others.map(t => tableSection(t, t.h2)).join('');
}

function glossaryView(C) {
  if (!C.glossary.length) return '<div class="card dashed">還沒有詞彙。</div>';
  const t = C.glossary[0];
  const k = t.header.indexOf('種類');
  const kinds = k >= 0 ? [...new Set(t.rows.map(r => r.cells[k]).filter(Boolean))] : [];
  return filterBar('找詞彙（英文 ID、中文、定義）', kinds) + tableSection(t, '詞彙對照表', k >= 0 ? '種類' : '');
}

function changelogView(C) {
  return `<article class="card doc">${md(C.changelog || '（沒有變更紀錄）')}</article>`;
}

// ---------- 事件 ----------

function bindCore(C, tab, item) {
  $$('[data-ent]').forEach(b => b.onclick = () => go(`#/core/entities/${enc(b.dataset.ent)}`));
  const q = $('#coreQ');
  if (q) q.oninput = () => { state.coreQ = q.value; redrawEntities(C); };
  $$('[data-layer]').forEach(b => b.onclick = () => { state.coreLayer = b.dataset.layer; renderCore('entities', state.coreSel); });
  // 狀態與事件：和看圖確認同一套按鈕
  $$('[data-mach]').forEach(b => b.onclick = () => go(`#/core/flows/${enc(b.dataset.mach)}`));
  $$('[data-t]').forEach(b => b.onclick = () => { state.tsel = +b.dataset.t; renderCore('flows', state.coreMach); });
  const back = $('[data-back]'); if (back) back.onclick = () => { state.tsel = null; renderCore('flows', state.coreMach); };
  // 規則、詞彙、事件表：打字篩選、種類篩選（只藏列，不重畫）
  const find = $('#coreFind');
  const apply = () => {
    const v = (find ? find.value : '').trim().toLowerCase();
    const kind = ($('[data-kind].on') || {}).dataset ? $('[data-kind].on').dataset.kind : '';
    $$('[data-q]').forEach(el => { el.hidden = !!(v && !el.dataset.q.includes(v)) || !!(kind && el.dataset.k !== undefined && el.dataset.k !== kind); });
  };
  if (find) find.oninput = apply;
  $$('[data-kind]').forEach(b => b.onclick = () => { $$('[data-kind]').forEach(x => x.classList.toggle('on', x === b)); apply(); });
  if (tab === 'flows' && !find) {
    // 事件表也要能找：狀態圖下面加一個搜尋框
    const first = $('.core-sec');
    if (first) {
      first.insertAdjacentHTML('beforebegin', filterBar('找事件、更正方式', []));
      $('#coreFind').oninput = () => { const v = $('#coreFind').value.trim().toLowerCase(); $$('[data-q]').forEach(el => { el.hidden = !!(v && !el.dataset.q.includes(v)); }); };
    }
  }
}

// 名詞頁打字時只重畫圖和卡片（輸入框不重建，游標不跳）
function redrawEntities(C) {
  const d = $('.core-view .diagram');
  if (d) d.innerHTML = entityDiagram(C, state.coreSel);
  $$('.ent-card').forEach(b => { const e = C.entities.find(x => x.id === b.dataset.ent); b.classList.toggle('dim', !entityMatch(e, C)); });
  $$('.core-view .diagram [data-ent]').forEach(b => b.onclick = () => go(`#/core/entities/${enc(b.dataset.ent)}`));
}
