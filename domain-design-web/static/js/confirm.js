// 看圖確認：② 模型圖、確認卡（確認列附上它指到的內容）
import { $, $$, api, enc, esc, go, inline, loadReview, md, nextTask, setTop, state, write } from './core.js';
import { renderDone } from './decide.js';
import { flowsHtml } from './flows.js';

// ---------- 看圖確認 ----------

export function groupOf(what) {
  // ⑥：「黃金案例 GCnn（…：…）」「P0 Qnn：<題目>」括號或題目裡也有「：」，固定歸成一組
  if (/^黃金案例\s*GC\d+/.test(what)) return '黃金案例';
  if (/^P0\s*Q\d+/.test(what)) return 'P0 驗收問題';
  const g = what.split('：')[0].replace(/（[^）]*\d+\/\d+[^）]*）/, '').trim();
  // 「AI 提出、有依據的決定 D-01（哪些有狀態）」這種一個編號一列的，同一類放一組
  const m = g.match(/^(.+?)\s*(?:[A-Z]+-\d+|[A-Z]\d+)(?:（[^）]*）)?$/);
  return m ? m[1] : g;
}

// 每一類確認要人判斷什麼（類別是流程定的：精簡版 0.2「審查頁中各步〔關鍵決定〕要看的東西」，
// 加上 AI 提出的決定、自評「部分」）；AI 寫的「要看的」只是名稱，人常看不出要做什麼
export const ASK = [
  [/只需現況/, '這些資料只記目前的值，改了之後舊的值就不留。想一下：以後會不會有人要查「當時是什麼」（例：報表要印當時的名稱、對帳要看改之前的數字）？不會就按 ✓；會的話寫一句，這筆就要留歷史。'],
  [/有依據的決定/, 'AI 自己做的決定（有依據，所以沒寫成選擇題）。照你對業務的了解看每一條：這樣做可以嗎？可以就按 ✓，不同意就寫一句。'],
  [/^自評/, 'AI 自評這條完成標準只做到一部分（或沒做到）。看它說缺了什麼：可以先這樣就按 ✓，要補就寫一句。'],
  [/^黃金案例/, '你算的、設計推出的、系統跑出的並排在下面。通過的：三邊一致就按 ✓。失敗的：看差在哪一項、AI 寫的原因對不對（怎麼處理在第一節的問題裡回答），寫得對就按 ✓。'],
  [/^P0/, '驗收問題（P0）和系統的回答。看回答有沒有答到這一題（問的是什麼、答的是不是那個），有就按 ✓；答非所問或缺了一部分就寫一句。'],
  [/幾對幾/, '兩個東西之間是一對一、一對多還是多對多。錯了之後要改資料表、搬資料，很貴；照實際業務想一個反例看看。'],
  [/Entity/, '哪些要當成一個「東西」單獨記（有自己的身分、會被指到），哪些不用。'],
  [/推導值/, '這些不另外存，要用的時候從其他資料算出來。想一下：算得出來嗎？資料後來改了，當時的值還算得回來嗎？'],
  [/草圖/, '和一開始的全局名詞草圖不一樣的地方，看改得合不合理。'],
  [/守恆式/, '數量或金額要對得起來的算式（例：期初＋增加－減少＝期末），看有沒有漏掉會讓數字對不起來的情況。'],
  [/保存方式/, '這些資料改了就直接蓋掉、不留舊值；和 ③「只需現況」一起看，以後不會有人要查舊的值才按 ✓。'],
  [/範圍|做／不做/, '這條切片做什麼、不做什麼。看有沒有該做卻沒列的、或不該現在做的。'],
];
export const askOf = g => (ASK.find(([re]) => re.test(g)) || [null, ''])[1];

// 「AI 提出、有依據的決定 D-01（哪些有狀態）」在組裡只顯示「D-01」和「哪些有狀態」
export function rowTitle(what, group) {
  let t = group && what.startsWith(group) && what.length > group.length ? what.slice(group.length).trim() : what;
  t = t.replace(/^[：:]\s*/, '');
  if (group === 'P0 驗收問題') t = t.replace(/^P0\s*/, '');
  const q = t.match(/^((?:GC|Q)\d+)\s*(?:[：:]\s*(.+)|（(.+)）)$/);   // ⑥：「GC01（失敗：…）」「Q01：題目」
  if (q) return `<span class="rid">${esc(q[1])}</span> ${inline(q[2] || q[3])}`;
  const m = t.match(/^((?:[A-Z]+-\d+|[A-Z]\d+)(?:[、,，]\s*(?:[A-Z]+-\d+|[A-Z]\d+))*)\s*(?:（(.+)）)?$/);
  return m ? `<span class="rid">${esc(m[1])}</span>${m[2] ? ` ${inline(m[2])}` : ''}` : inline(t);
}

// 長的一句拆成幾點：只在括號、引號外的「。」「；」斷開
export function clauses(s) {
  const out = [];
  let depth = 0, cur = '';
  for (const ch of s) {
    cur += ch;
    if ('（(「『['.includes(ch)) depth++;
    else if ('）)」』]'.includes(ch)) depth = Math.max(0, depth - 1);
    else if (!depth && '。；'.includes(ch)) { out.push(cur.slice(0, -1).trim()); cur = ''; }
  }
  if (cur.trim()) out.push(cur.trim());
  return out.filter(Boolean);
}

// 「在哪裡」指到的那一列或那一段（伺服器從交付物拿出來）：短欄位直接列，最主要的一欄放大，
// 其他長的（理由、依據、替代做法…）收在「為什麼」；原文摘的字句用螢光標出來
export const CTX_MAIN = ['決定', 'AI 自評', '內容', '說明', '定義', '前提條件', '問題'];
export const CTX_LONG = 60;

export function ctxHtml(c, frags) {
  const mark = h => frags.reduce((s, f) => s.split(esc(f)).join(`<mark>${esc(f)}</mark>`), h);
  return (c.context || []).map(x => {
    const link = `<a class="small ref-link" data-file="${esc(x.file)}" data-line="${x.line}">${esc(x.file.split('/').pop())} 第 ${x.line} 行 ›</a>`;
    const head = `<div class="row spread"><span class="muted small">${esc(x.title || '')}</span>${link}</div>`;
    if (!x.fields) return `<div class="ctx">${head}<div class="md">${mark(x.text.includes('\n') ? md(x.text) : inline(x.text.replace(/^\s*[-*]\s+/, '')))}</div></div>`;
    const fs = x.fields.filter(([h, v], k) => v && v !== '—' && !(k === 0 && /^[A-Z]+-?\d+$/.test(v)));
    const id = /^[A-Z]+-?\d+$/.test((x.fields[0] || [])[1] || '') ? x.fields[0][1] : '';
    const main = CTX_MAIN.map(n => fs.find(([h]) => h === n)).find(Boolean) || fs.find(([, v]) => v.length > CTX_LONG);
    const rest = fs.filter(f => f !== main);
    const dl = list => `<dl>${list.map(([h, v]) => `<dt>${esc(h)}</dt><dd>${mark(inline(v))}</dd>`).join('')}</dl>`;
    // 欄位都短（例：狀態機的一列）就直接列；有決定這種主要的一欄時，其他欄收起來，要看再點
    if (!main) return `<div class="ctx">${head}${dl(rest)}</div>`;
    return `<div class="ctx">${head}
      ${(() => {
        const cs = main[1].length > CTX_LONG ? clauses(main[1]) : [main[1]];
        return cs.length > 1 ? `<ul class="main">${cs.map(x => `<li>${mark(inline(x))}</li>`).join('')}</ul>` : `<div class="main">${mark(inline(main[1]))}</div>`;
      })()}
      ${rest.length ? `<details><summary>${rest.map(f => esc(f[0])).join('、')}</summary>${dl(rest)}</details>` : ''}</div>`;
  }).join('');
}

// ⑥ 的黃金案例：一列並排三欄（你算的、設計推出的、系統跑出的），內容從 golden_cases.md 來
function goldenOf(what) {
  const m = what.match(/^(?:黃金案例\s*)?(GC\d+)/);
  const g = m && state.review && state.review.golden && state.review.golden[m[1]];
  if (!g) return '';
  const col = (t, v) => `<div class="gc-col"><div class="label">${t}</div><div class="md">${md(v || '（沒有）').replace(/不一致/g, '<b class="gc-off">不一致</b>')}</div></div>`;
  const pass = /^通過/.test((g['判定'] || '').trim());
  return `${g['判定'] ? `<div class="gc-verdict ${pass ? 'ok' : 'bad'}">判定：${inline(g['判定'])}</div>` : ''}
    <div class="gc-cols">${col('你算的（預期結果）', g['預期結果'])}${col('設計推出的（紙上判定）', g['紙上判定'])}${col('系統跑出的（系統結果）', g['系統結果'])}</div>`;
}

function rowShell(c, ans, what, group, body) {
  return `<div class="crow ${!ans ? '' : ans === '✓' ? 'done' : 'noted'}">
    <div class="what">${rowTitle(what, group)}</div>
    ${body}
    ${c.cells['在哪裡'] ? `<div class="where">${inline(c.cells['在哪裡'])}</div>` : ''}
    <div class="acts">${actsHtml(c, ans)}</div>
  </div>`;
}

function actsHtml(c, ans) {
  return !ans ? `
      <button class="btn go" data-ok="${c.line}">✓ 合理</button>
      <button class="btn" data-note="${c.line}">寫意見</button>`
    : ans === '✓' ? `
      <span class="val">✓ 合理</span>
      <button class="btn ghost" data-clear="${c.line}">撤回</button>
      <button class="btn" data-note="${c.line}">改成寫意見</button>`
    : `
      <span class="val note">意見：${esc(ans)}</span>
      <button class="btn" data-note="${c.line}" data-prev="${esc(ans)}">改意見</button>
      <button class="btn" data-ok="${c.line}">改成合理</button>
      <button class="btn ghost" data-clear="${c.line}">撤回</button>`;
}

export function confirmRow(c, group = '') {
  const ans = (c.answer || '').trim();
  const what = c.cells['要看的'] || '';
  // 原文的「…」拆成片段（「…」中間的省略號也拆開），在上下文裡找得到就標出來，全部找得到就不再另外列原文
  const raw = [...(c.cells['原文'] || '').matchAll(/「([^」]+)」/g)].flatMap(m => m[1].split('…')).map(s => s.trim()).filter(s => s.length >= 2);
  const frags = raw.map(s => s.replace(/^#+\s*/, ''));
  const ctxText = JSON.stringify(c.context || []);
  const covered = frags.length && (c.context || []).length && frags.every(f => ctxText.includes(f));
  // 「要確認」只放句子：標題（### …）不算；指到決定這種有主要欄位的表格列時，主要欄位本身就是要確認的，不重複
  const hasMain = (c.context || []).some(x => x.fields && x.fields.some(([h]) => CTX_MAIN.includes(h)));
  const claim = hasMain ? [] : raw.filter(s => !s.startsWith('#'));
  const gc = goldenOf(what);
  if (gc) return rowShell(c, ans, what, group, gc);
  return `<div class="crow ${!ans ? '' : ans === '✓' ? 'done' : 'noted'}${(c.context || []).length ? ' has-ctx' : ''}">
    <div class="what">${rowTitle(what, group)}</div>
    ${claim.length ? `<div class="claim"><span class="muted small">要確認</span>${claim.length > 1 ? `<ul>${claim.map(f => `<li>${esc(f)}</li>`).join('')}</ul>` : `<div>${esc(claim[0])}</div>`}</div>` : ''}
    ${(c.context || []).length ? ctxHtml(c, frags) : ''}
    ${c.cells['原文'] && !covered && !frags.length ? `<div class="orig">${inline(c.cells['原文'])}</div>` : ''}
    ${c.cells['在哪裡'] && !(c.context || []).length ? `<div class="where">${inline(c.cells['在哪裡'])}</div>` : ''}
    <div class="acts">${actsHtml(c, ans)}</div>
  </div>`;
}

export function layout(model, showAll) {
  // 這輪改到的放中間一排；它們指到的放上排、指到它們的放下排；「全部」時其他的也放進去
  const rels = model.relations.filter(x => !x.cancelled || x.changed);
  const own = new Map(model.entities.map(e => [e.id, e]));
  const all = new Map([...model.refs.map(e => [e.id, e]), ...model.entities.map(e => [e.id, e])]);
  const changed = new Set(model.entities.filter(e => e.changed).map(e => e.id));
  rels.filter(x => x.changed).forEach(x => { if (own.has(x.from)) changed.add(x.from); });
  const rows = [[], [], []];
  const place = new Map();
  [...changed].forEach(id => { place.set(id, 1); });
  for (const x of rels) {
    if (changed.has(x.from) && !place.has(x.to)) place.set(x.to, 0);
  }
  for (const x of rels) {
    if (changed.has(x.to) && !place.has(x.from)) place.set(x.from, 2);
  }
  if (showAll) for (const id of all.keys()) if (!place.has(id)) place.set(id, own.has(id) ? 2 : 0);
  for (const [id, row] of place) if (all.has(id)) rows[row].push(id);
  // 依相連節點的平均位置排序，少一點交叉
  const pos = new Map();
  rows[1].forEach((id, k) => pos.set(id, k));
  for (const row of [0, 2, 1]) {
    const score = id => {
      const ns = rels.filter(x => x.from === id || x.to === id).map(x => pos.get(x.from === id ? x.to : x.from)).filter(v => v !== undefined);
      return ns.length ? ns.reduce((a, b) => a + b, 0) / ns.length : 99;
    };
    rows[row].sort((a, b) => score(a) - score(b));
    const w = rows[row].length;
    rows[row].forEach((id, k) => pos.set(id, w > 1 ? k * (Math.max(...rows.map(r => r.length)) - 1) / (w - 1) : 0));
  }
  // 每排最多 PER 個，多的換到下一排（上排往上長、下排往下長），圖不會比框寬
  const W = 150, H = 56, GX = 56, GY = 120, PER = 4;   // 間隔放寬，關係的字放得下
  const chunk = ids => { const out = []; for (let k = 0; k < ids.length; k += PER) out.push(ids.slice(k, k + PER)); return out; };
  const bands = [...chunk(rows[0]).reverse(), ...chunk(rows[1]), ...chunk(rows[2])].filter(b => b.length);
  const width = Math.min(PER, Math.max(...bands.map(b => b.length))) * (W + GX) - GX;
  const nodes = new Map();
  bands.forEach((band, bi) => {
    const rowW = band.length * (W + GX) - GX;
    band.forEach((id, k) => nodes.set(id, { id, x: 10 + (width - rowW) / 2 + k * (W + GX), y: 20 + bi * (H + GY), w: W, h: H, e: all.get(id) }));
  });
  const edges = rels.filter(x => nodes.has(x.from) && nodes.has(x.to));
  return { nodes, edges, width: width + 60, height: 40 + bands.length * (H + GY) - GY, changed };
}

export function short(s, n) { s = String(s); return s.length > n ? s.slice(0, n - 1) + '…' : s; }

export function edgePath(a, b) {
  const ax = a.x + a.w / 2, bx = b.x + b.w / 2;
  if (a === b) return { d: `M${a.x + a.w - 30},${a.y} C${a.x + a.w + 40},${a.y - 50} ${a.x + a.w + 40},${a.y + a.h + 50} ${a.x + a.w - 30},${a.y + a.h}`, mx: a.x + a.w + 26, my: a.y + a.h / 2 };
  if (Math.abs(a.y - b.y) < 1) {
    const [l, r] = ax < bx ? [a, b] : [b, a];
    return { d: `M${l.x + l.w},${l.y + l.h / 2} L${r.x},${r.y + r.h / 2}`, mx: (l.x + l.w + r.x) / 2, my: l.y + l.h / 2 - 10 };
  }
  const [t, u] = a.y < b.y ? [a, b] : [b, a];
  const x1 = t.x + t.w / 2, y1 = t.y + t.h, x2 = u.x + u.w / 2, y2 = u.y;
  return { d: `M${x1},${y1} C${x1},${(y1 + y2) / 2} ${x2},${(y1 + y2) / 2} ${x2},${y2}`, mx: (x1 + x2) / 2, my: (y1 + y2) / 2 };
}

// 關係的字（名稱＋幾對幾）：畫在方塊上面一層；和別的字或方塊（nodes）重疊時往下移開，不互相蓋住
export function edgeLabels(items, nodes = []) {
  const placed = [];
  const onNode = (x, y, w) => nodes.some(n => x + w / 2 > n.x - 4 && x - w / 2 < n.x + n.w + 4 && y + 10 > n.y - 4 && y - 10 < n.y + n.h + 4);
  return items.map(({ x, y, text }) => {
    const w = [...text].reduce((n, ch) => n + (/[\u3000-\u9fff\uff00-\uffef]/.test(ch) ? 13 : 7.5), 0) + 18;
    const y0 = y;
    for (let k = 0; k < 12 && (placed.some(p => Math.abs(p.x - x) < (p.w + w) / 2 + 4 && Math.abs(p.y - y) < 23) || onNode(x, y, w)); k++) {
      y = y0 + (k % 2 ? -1 : 1) * 23 * Math.ceil((k + 1) / 2);   // 上下交替找空位
    }
    placed.push({ x, y, w });
    return `<g class="elabel" transform="translate(${x},${y})"><rect x="${-w / 2}" y="-10" width="${w}" height="20" rx="10"></rect><text text-anchor="middle" y="4">${esc(text)}</text></g>`;
  }).join('');
}

export function renderDiagram(r) {
  const L = layout(r.model, state.showAll);
  const sel = state.sel;
  const okd = id => {
    const e = r.model.entities.find(x => x.id === id);
    const lines = new Set([...(e ? e.confirm_lines : []), ...r.model.relations.filter(x => x.from === id && x.changed).flatMap(x => x.confirm_lines)]);
    return lines.size && [...lines].every(l => (r.confirms.find(c => c.line === l) || {}).answer);
  };
  const labels = [];
  const edges = L.edges.map(x => {
    const g = edgePath(L.nodes.get(x.from), L.nodes.get(x.to));
    const hot = sel && (x.from === sel || x.to === sel);
    if (hot) labels.push({ x: g.mx, y: g.my, text: `${x.label || x.name} ${x.card}` });
    return `<path class="edge ${x.changed ? 'changed' : ''} ${hot ? 'hot' : ''} ${x.cancelled ? 'cancelled' : ''}" d="${g.d}"><title>${esc(x.from)} ${esc(x.name)}（${esc(x.label)}）→ ${esc(x.to)}　${esc(x.card)}</title></path>`;
  });
  const nodes = [...L.nodes.values()].map(n => {
    const e = n.e;
    const cls = [e.kind === 'own' ? 'own' : '', L.changed.has(n.id) ? 'changed' : '', okd(n.id) ? 'okd' : '', sel === n.id ? 'sel' : ''].join(' ');
    return `<g class="node ${cls}" data-node="${esc(n.id)}" transform="translate(${n.x},${n.y})">
      <rect width="${n.w}" height="${n.h}" rx="14"></rect>
      <text x="${n.w / 2}" y="${e.kind === 'own' ? 25 : 34}" text-anchor="middle">${esc(short(e.kind === 'own' ? e.label : e.id, 10))}</text>
      ${e.kind === 'own' ? `<text class="sub" x="${n.w / 2}" y="44" text-anchor="middle">${esc(short(e.id, 22))}</text>` : ''}
      <title>${esc(e.definition || e.id)}</title></g>`;
  });
  return `<svg width="${L.width}" height="${L.height}" viewBox="0 0 ${L.width} ${L.height}" role="img" aria-label="模型圖">${edges.join('')}${nodes.join('')}${edgeLabels(labels, [...L.nodes.values()])}</svg>`;
}

export function entityPanel(r, id) {
  const e = r.model.entities.find(x => x.id === id) || r.model.refs.find(x => x.id === id);
  if (!e) return `<p class="muted">點圖上的綠色方塊，這裡會說明它是什麼、要你確認什麼。</p>`;
  const rels = r.model.relations.filter(x => (x.from === id || x.to === id) && x.changed);
  const lines = new Set([...(e.confirm_lines || []), ...rels.flatMap(x => x.confirm_lines)]);
  const rows = r.confirms.filter(c => lines.has(c.line));
  const open = rows.filter(c => !(c.answer || '').trim());
  return `
    <div>${e.changed ? '<span class="chip new">這輪新增或改動</span>' : e.kind === 'own' ? '<span class="chip">本切片</span>' : '<span class="chip">引用</span>'}
      <h2>${esc(e.label)}</h2><div class="small muted">${esc(e.id)}</div></div>
    ${e.definition ? `<div style="font-size:17px">${esc(e.definition)}</div>` : ''}
    ${e.attrs && e.attrs.length ? `<div class="box"><div class="label">記下什麼</div><div class="attrs">${e.attrs.map(a => `<span title="${esc(a.name)}">${esc(short(a.label.split(/[，：；]/)[0] || a.name, 24))}</span>`).join('')}</div></div>` : ''}
    ${e.separate ? `<div class="box"><div class="label">為什麼要單獨記</div>${esc(e.separate)}</div>` : ''}
    ${e.not ? `<div class="box"><div class="label">它不是</div>${esc(e.not)}</div>` : ''}
    ${rows.length ? `<div class="label" style="margin-top:4px">要你確認（${rows.length - open.length} / ${rows.length}）</div>${rows.map(confirmRow).join('')}` : ''}
    ${open.length ? `<div class="row"><button class="btn primary" id="allOk">合理，下一個</button><button class="btn" id="entNote">不對，寫意見</button></div>` : ''}
    <details class="tech"><summary>技術細節</summary>${e.line ? `<a class="ref-link" data-file="${esc(r.model.path)}" data-line="${e.line}">${esc(r.model.path.split('/').pop())} 第 ${e.line} 行</a>` : '不在本切片定義'}</details>`;
}

export async function renderConfirm(path, sel) {
  const r = state.review && state.path === path ? state.review : await loadReview(path);
  const p = enc(path);
  const homeHref = `#/s/${enc(r.slice)}`;
  const total = r.counts.confirms, open = r.counts.confirms_open;
  setTop([homeHref, '關卡'], `<span class="bar" style="flex:1"><i class="${open ? '' : 'full'}" style="width:${total ? (total - open) / total * 100 : 100}%"></i></span><span class="count">${total - open} / ${total}</span>`);

  const inModel = new Set();
  let modelHtml = '';
  if (r.model) {
    // 只算圖上點得到的：畫出來的方塊自己的確認列，加上碰到它、這輪改到的關係（說明欄就是顯示這些）。
    // 圖上沒畫出來的（例：兩端都不是這輪改到的名詞）放到下面「其他要確認的」，不然會有確認列沒地方點
    const drawn = new Set(layout(r.model, state.showAll).nodes.keys());
    const all = [...r.model.entities, ...(r.model.refs || [])];
    const owner = new Map();   // 方塊 → 它負責的確認列（關係算在起點；起點沒畫出來才算終點），用來列「要確認的清單」
    const own = (id, ls) => { if (ls && ls.length) owner.set(id, [...new Set([...(owner.get(id) || []), ...ls])]); };
    for (const e of all) if (drawn.has(e.id)) own(e.id, e.confirm_lines);
    for (const x of r.model.relations) if (x.changed) own(drawn.has(x.from) ? x.from : drawn.has(x.to) ? x.to : null, x.confirm_lines);
    owner.delete(null);
    for (const ls of owner.values()) ls.forEach(l => inModel.add(l));
    const answered = l => ((r.confirms.find(c => c.line === l) || {}).answer || '').trim();
    if (!sel) sel = ([...owner].find(([, ls]) => ls.some(l => !answered(l))) || [...owner][0] || [null])[0];
    state.sel = sel;
    const restN = r.confirms.filter(c => !inModel.has(c.line));
    const nameOf = id => { const e = all.find(x => x.id === id); return e ? e.label : id; };
    const todo = `<div class="todo">
        <div class="small"><b>要確認 ${r.confirms.length} 項</b>：圖上 ${inModel.size} 項（點名稱或方塊），下面清單 ${restN.length} 項</div>
        <div class="todo-chips">${[...owner].map(([id, ls]) => {
          const done = ls.filter(answered).length;
          return `<button class="todo-chip ${done === ls.length ? 'ok' : ''} ${id === sel ? 'on' : ''}" data-node="${esc(id)}">${esc(nameOf(id))} <b>${done}/${ls.length}</b></button>`;
        }).join('')}
        ${restN.length ? `<a class="todo-chip ${restN.every(c => answered(c.line)) ? 'ok' : ''}" href="#others" id="toOthers">其他（清單）<b>${restN.filter(c => answered(c.line)).length}/${restN.length}</b> ↓</a>` : ''}</div>
      </div>`;
    modelHtml = todo + `
      <div class="legend">
        <span><i style="background:var(--done);border:3px solid var(--ink)"></i>這輪新增或改動</span>
        <span><i style="background:#fff;border:2px solid var(--ink)"></i>本切片原本就有</span>
        <span><i style="background:#fff;border:2px solid var(--faint)"></i>引用其他地方的</span>
        <label class="small" style="font-weight:400"><input type="checkbox" id="showAll" ${state.showAll ? 'checked' : ''}> 顯示全部名詞</label>
      </div>
      <div class="model-split">
        <section class="diagram">${renderDiagram(r)}</section>
        <aside class="panel" id="panel">${entityPanel(r, sel)}</aside>
      </div>`;
  }
  let flowHtml = '';
  if (r.flows) {
    const f = flowsHtml(r, sel, state.tsel, inModel);
    flowHtml = f.html;
    if (!r.model) state.sel = f.sm.id;
  }
  const rest = r.confirms.filter(c => !inModel.has(c.line));
  const groups = [];
  for (const c of rest) {
    let g = groupOf(c.cells['要看的'] || '');
    if (g === '同上' && groups.length) g = groups[groups.length - 1].name;
    if (!groups.length || groups[groups.length - 1].name !== g) groups.push({ name: g, rows: [] });
    groups[groups.length - 1].rows.push(c);
  }
  const groupsHtml = groups.map((g, k) => {
    const open = g.rows.filter(c => !(c.answer || '').trim());
    return `<section class="group card">
      <div class="row spread"><h3>${esc(g.name)}</h3>${open.length > 1 ? `<button class="btn small-btn go" data-group="${k}">這 ${open.length} 項都沒問題</button>` : ''}</div>
      ${askOf(g.name) ? `<p class="ask">${esc(askOf(g.name))}</p>` : ''}
      <div class="list">${g.rows.map(c => confirmRow(c, g.name)).join('')}</div></section>`;
  }).join('');

  $('#app').innerHTML = `
    ${r.model ? `<div><h1 style="margin:0">看圖確認：這輪改了哪些東西</h1><p class="muted" style="margin:4px 0 0">點上面的名稱或圖上的方塊看說明；橘色的還沒確認完。合理就按「合理，下一個」。</p></div>${modelHtml}` : ''}
    ${flowHtml}
    ${groups.length ? `<div id="others"><h2 style="margin:0">${r.model || r.flows ? '其他要確認的' : '確認這輪的改動'}</h2><p class="muted small" style="margin:4px 0 0">每一項打 ✓ 或寫一句意見。原文和行號可以點開看。</p></div><div class="groups">${groupsHtml}</div>` : ''}
    ${!open ? `<div class="row"><a class="btn big primary" href="${nextTask(r)}">確認完成，下一個任務<span class="arr">›</span></a></div>` : ''}`;

  const refresh = s => renderConfirm(path, s === undefined ? state.sel : s);
  const okAll = async lines => {
    for (const l of lines) if (!await write('/api/review/cells', { line: l, cells: { '確認': '✓' } })) return false;
    return true;
  };
  $$('[data-ok]').forEach(b => b.onclick = async () => { if (await okAll([+b.dataset.ok])) refresh(); });
  $$('[data-note]').forEach(b => b.onclick = () => openNote(b, +b.dataset.note, refresh));
  $$('[data-clear]').forEach(b => b.onclick = async () => { if (await write('/api/review/cells', { line: +b.dataset.clear, cells: { '確認': '' } })) refresh(); });
  $$('[data-group]').forEach(b => b.onclick = async () => {
    const g = groups[+b.dataset.group];
    if (await okAll(g.rows.filter(c => !(c.answer || '').trim()).map(c => c.line))) refresh();
  });
  const to = $('#toOthers'); if (to) to.onclick = e => { e.preventDefault(); $('#others').scrollIntoView({ behavior: 'smooth' }); };
  $('#app').classList.add('wide');   // 這一頁要並排圖與說明，主畫面放寬
  // 主畫面窄、圖和說明上下排時，點了方塊就捲到說明欄
  $$('[data-node]').forEach(n => n.onclick = async () => {
    history.replaceState(null, '', `#/r/${p}/confirm/${n.dataset.node}`);
    await refresh(n.dataset.node);
    const panel = $('#panel'), split = $('.model-split');
    if (panel && split && getComputedStyle(split).gridTemplateColumns.split(' ').length === 1) panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
  // 狀態圖：點名稱換名詞，點箭頭的字（或說明欄的一列）看那個轉換
  $$('[data-mach]').forEach(b => b.onclick = () => {
    state.tsel = null;
    history.replaceState(null, '', `#/r/${p}/confirm/${b.dataset.mach}`);
    refresh(b.dataset.mach);
  });
  $$('[data-t]').forEach(b => b.onclick = () => {
    state.tsel = +b.dataset.t;
    refresh();
    const panel = $('#panel'), split = $('.model-split');
    if (panel && split && getComputedStyle(split).gridTemplateColumns.split(' ').length === 1) panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
  const back = $('[data-back]'); if (back) back.onclick = () => { state.tsel = null; refresh(); };
  const sa = $('#showAll');
  if (sa) sa.onchange = () => { state.showAll = sa.checked; refresh(); };
  const allOk = $('#allOk');
  if (allOk) allOk.onclick = async () => {
    const lines = $$('#panel [data-ok]').map(b => +b.dataset.ok).filter(l => !(r.confirms.find(c => c.line === l) || {}).answer);
    if (!await okAll(lines)) return;
    const changed = state.review.model.entities.filter(e => e.changed);
    const nxt = changed.find(e => e.confirm_lines.some(l => !(state.review.confirms.find(c => c.line === l) || {}).answer));
    if (nxt) { history.replaceState(null, '', `#/r/${p}/confirm/${nxt.id}`); refresh(nxt.id); }
    else if (!state.review.counts.confirms_open) renderDone('確認', `${total} 項都確認了`, nextTask(state.review));
    else refresh(null);
  };
  const en = $('#entNote');
  if (en) en.onclick = () => { const first = $('#panel [data-note]'); if (first) openNote(first, +first.dataset.note, refresh); };
}

// 意見就地展開一個輸入框（不用瀏覽器的 prompt 對話框）
export function openNote(btn, line, done) {
  const row = btn.closest('.crow') || btn.parentElement;
  if ($('.note-box', row)) return;
  row.insertAdjacentHTML('beforeend', `<div class="note-box row"><input type="text" style="flex:1" placeholder="哪裡不對？寫一句，按 Enter"><button class="btn primary">寫入</button></div>`);
  const inp = $('.note-box input', row);
  if (btn.dataset.prev) inp.value = btn.dataset.prev;
  inp.focus();
  const save = async () => {
    const v = inp.value.trim();
    if (v && await write('/api/review/cells', { line, cells: { '確認': v } })) done();
  };
  $('.note-box button', row).onclick = save;
  inp.onkeydown = e => { if (e.key === 'Enter') save(); };
}
