// 第 ③ 步的狀態圖（看圖確認上方）
import { $, esc, inline, md, plain } from './core.js';
import { askOf, confirmRow, groupOf } from './confirm.js';

// ---------- 第 ③ 步：狀態圖 ----------
// 03_flows.md 的狀態機表畫成圖：方塊是狀態，箭頭上的字是觸發事件（點了看誰可以做、前提條件）；
// 由左到右照「從起點走幾步到得了」排，自己到自己的（更正）畫在方塊上方

export function flowDiagram(sm, tsel) {
  const BW = 140, BH = 52, CW = 260, RH = 150, LH = 19;
  const ts = sm.transitions;
  const depth = new Map(), hasStart = ts.some(t => !t.from);
  const seeds = hasStart ? [...new Set(ts.filter(t => !t.from).map(t => t.to))] : [sm.states[0] && sm.states[0].id];
  seeds.forEach(s => s && depth.set(s, 1));
  for (let changed = true; changed;) {
    changed = false;
    for (const t of ts) if (t.from && t.from !== t.to && depth.has(t.from) && !depth.has(t.to)) { depth.set(t.to, depth.get(t.from) + 1); changed = true; }
  }
  let maxD = Math.max(1, ...depth.values());
  for (const s of sm.states) if (!depth.has(s.id)) depth.set(s.id, ++maxD);
  const cols = new Map();
  for (const s of sm.states) { const d = depth.get(s.id); cols.set(d, [...(cols.get(d) || []), s.id]); }
  const loops = id => ts.map((t, i) => [t, i]).filter(([t]) => t.from === id && t.to === id);
  const top = 30 + Math.max(0, ...sm.states.map(s => loops(s.id).length)) * LH + (sm.states.some(s => loops(s.id).length) ? 40 : 0);
  const pos = new Map();
  const X0 = hasStart ? 190 : 30;   // 起點的字放在黑點和第一個方塊之間
  for (const [d, ids] of cols) ids.forEach((id, k) => pos.set(id, { x: X0 + (d - 1) * CW, y: top + k * RH }));
  const sameCol = ts.some(t => t.from && t.from !== t.to && depth.get(t.from) === depth.get(t.to));
  const back = ts.some(t => t.from && depth.get(t.from) > depth.get(t.to));
  const W = X0 + (maxD - 1) * CW + BW + (sameCol ? 130 : 20), H = top + Math.max(...[...cols.values()].map(c => c.length)) * RH - RH + BH + (back ? 100 : 30);
  const lbl = (t, i) => `${esc(t.label || t.on)}${/^系統/.test(t.who) ? ' ⚙' : ''}`;
  const text = (x, y, anchor, items) => items.map(([t, i], k) =>
    `<text class="tlabel ${i === tsel ? 'on' : ''}" data-t="${i}" x="${x}" y="${y + k * LH}" text-anchor="${anchor}">${lbl(t, i)}<title>${esc(t.on)}：${esc(t.who)}</title></text>`).join('');
  const groups = new Map();
  ts.forEach((t, i) => { if (t.from !== t.to) { const k = `${t.from}|${t.to}`; groups.set(k, [...(groups.get(k) || []), [t, i]]); } });
  let out = '';
  for (const [k, items] of groups) {
    const [f, to] = k.split('|');
    const b = pos.get(to);
    if (!b) continue;
    const on = items.some(([, i]) => i === tsel) ? ' hot' : '';
    if (!f) {   // 起點：方塊左邊一個黑點
      const sx = 30, sy = b.y + BH / 2;
      out += `<circle cx="${sx}" cy="${sy}" r="8" class="start"></circle><path class="fedge${on}" d="M${sx + 8},${sy} L${b.x - 4},${sy}" marker-end="url(#arr)"></path>`;
      out += text((sx + b.x) / 2 + 4, sy - 8 - (items.length - 1) * LH, 'middle', items);
      continue;
    }
    const a = pos.get(f);
    if (!a) continue;
    if (depth.get(f) === depth.get(to)) {   // 同一欄：上下直線，字放右邊
      const [u, d] = a.y < b.y ? [a, b] : [b, a];
      const x = a.x + BW / 2;
      out += `<path class="fedge${on}" d="M${x},${a.y < b.y ? u.y + BH : d.y} L${x},${a.y < b.y ? d.y - 4 : u.y + BH + 4}" marker-end="url(#arr)"></path>`;
      out += text(x + 10, (u.y + BH + d.y) / 2 - (items.length - 1) * LH / 2 + 5, 'start', items);
    } else if (depth.get(f) < depth.get(to)) {
      const x1 = a.x + BW, y1 = a.y + BH / 2, x2 = b.x - 4, y2 = b.y + BH / 2, mx = (x1 + x2) / 2;
      out += `<path class="fedge${on}" d="M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}" marker-end="url(#arr)"></path>`;
      out += text(mx, (y1 + y2) / 2 - 8 - (items.length - 1) * LH / 2, 'middle', items);
    } else {   // 往回：從下面繞
      const x1 = a.x + BW / 2, x2 = b.x + BW / 2, y = Math.max(a.y, b.y) + BH;
      out += `<path class="fedge${on}" d="M${x1},${a.y + BH} C${x1},${y + 70} ${x2},${y + 70} ${x2},${b.y + BH + 4}" marker-end="url(#arr)"></path>`;
      out += text((x1 + x2) / 2, y + 66, 'middle', items);
    }
  }
  for (const s of sm.states) {
    const { x, y } = pos.get(s.id);
    const ls = loops(s.id);
    if (ls.length) {
      const on = ls.some(([, i]) => i === tsel) ? ' hot' : '';
      out += `<path class="fedge${on}" d="M${x + BW * 0.3},${y} C${x + BW * 0.3},${y - 36} ${x + BW * 0.7},${y - 36} ${x + BW * 0.7},${y - 4}" marker-end="url(#arr)"></path>`;
      out += text(x + BW / 2, y - 34 - (ls.length - 1) * LH, 'middle', ls);
    }
    const term = sm.terminal.includes(s.id);
    out += `<g class="snode ${term ? 'term' : ''}"><rect x="${x}" y="${y}" width="${BW}" height="${BH}" rx="14"></rect>
      ${term ? `<rect x="${x + 4}" y="${y + 4}" width="${BW - 8}" height="${BH - 8}" rx="11" class="inner"></rect>` : ''}
      <text x="${x + BW / 2}" y="${y + 23}" text-anchor="middle" class="zh">${esc(s.label || s.id)}</text>
      <text x="${x + BW / 2}" y="${y + 41}" text-anchor="middle" class="en">${esc(s.id)}</text></g>`;
  }
  return `<svg viewBox="0 0 ${W} ${H}" width="${W}" role="img" aria-label="${esc(sm.label)}的狀態圖">
    <defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z"></path></marker></defs>${out}</svg>`;
}

export function flowPanel(r, sm, tsel) {
  const F = r.flows;
  const rows = r.confirms.filter(c => c.machine === sm.id);
  const confirmsHtml = rows.length ? `<div class="list">${rows.map(c => {
    const g = groupOf(c.cells['要看的'] || '');
    return `<div><div class="small"><b>要你確認：${esc(g)}</b></div>${askOf(g) ? `<p class="ask small">${esc(askOf(g))}</p>` : ''}${confirmRow({ ...c, context: (c.context || []).filter(x => x.line !== sm.line) }, g)}</div>`;
  }).join('')}</div>` : '';
  const link = (line, text) => `<a class="small ref-link" data-file="${esc(F.path)}" data-line="${line}">${text || `${esc(F.path.split('/').pop())} 第 ${line} 行`} ›</a>`;
  const nameOf = id => { const s = sm.states.find(x => x.id === id); return s && s.label ? s.label : id || '（新建立）'; };
  const t = tsel !== null && tsel !== undefined ? sm.transitions[tsel] : null;
  if (t) {
    const ev = F.events[t.on] || {};
    const dl = [['誰可以做', t.who], ['前提條件', t.guard], ['規則', t.rules], ['這個事件改變什麼', ev.changes], ['層', ev.layer], ['觸發來源', ev.trigger]]
      .filter(([, v]) => v && v !== '—');
    return `<button class="btn ghost small-btn" data-back>← ${esc(sm.label)}的全部狀態</button>
      <div><span class="chip">${esc(nameOf(t.from))} → ${esc(nameOf(t.to))}</span>
        <h2>${esc(ev.label || t.on)}</h2><div class="muted small">${esc(t.on)}${/^系統/.test(t.who) ? '　⚙ 系統自動' : ''}</div></div>
      <dl class="kv">${dl.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${inline(v)}</dd>`).join('')}</dl>
      <div class="row">${link(t.line, '狀態機表這一列')}${ev.line ? link(ev.line, '事件表這一列') : ''}</div>${confirmsHtml}`;
  }
  const stateless = !sm.transitions.length;
  return `<div><span class="chip">歷史需求：${esc(sm.history || '—')}</span><h2>${esc(sm.label)}<span class="muted small">　${esc(sm.id)}</span></h2></div>
    ${confirmsHtml}
    ${stateless ? '' : `
      <div class="small muted">點一列（或圖上的字）看誰可以做、前提條件</div>
      <div class="tlist">${sm.transitions.map((x, i) => `<button class="trow ${i === tsel ? 'on' : ''}" data-t="${i}">
        <span class="muted">${esc(nameOf(x.from))} → ${esc(nameOf(x.to))}</span><b>${esc(x.label || x.on)}${/^系統/.test(x.who) ? ' ⚙' : ''}</b></button>`).join('')}</div>`}
    ${sm.notes.length && !stateless ? `<div class="md small">${md(sm.notes.map(n => '- ' + n.replace(/\n/g, '\n  ')).join('\n'))}</div>` : ''}
    ${link(sm.line)}`;
}

// intro：換掉上方的標題與說明（core 的閱讀頁沒有要確認的項目）
export function flowsHtml(r, sel, tsel, inModel, intro) {
  const ms = r.flows.machines;
  const sm = ms.find(m => m.id === sel) || ms.find(m => (m.confirms || []).length) || ms.find(m => m.transitions.length) || ms[0];
  ms.forEach(m => (m.confirms || []).forEach(l => inModel.add(l)));
  const answered = l => ((r.confirms.find(c => c.line === l) || {}).answer || '').trim();
  const chip = m => {
    const ls = m.confirms || [];
    const done = ls.filter(answered).length;
    return `<button class="todo-chip ${ls.length ? done === ls.length ? 'ok' : '' : 'plain'} ${m === sm ? 'on' : ''}" data-mach="${esc(m.id)}">${esc(m.label)}${ls.length ? ` <b>${done}/${ls.length}</b>` : ''}</button>`;
  };
  const withSm = ms.filter(m => m.transitions.length), without = ms.filter(m => !m.transitions.length);
  return {
    sm, html: `
    ${intro || `<div><h1 style="margin:0">看圖確認：流程與狀態</h1><p class="muted" style="margin:4px 0 0">點名稱看它的狀態圖；點圖上箭頭的字，看誰可以做、前提條件。⚙ 是系統自動做的；雙框是終點（之後不會再變）。有數字的名稱有要你確認的項目。</p></div>`}
    <div class="todo">
      <div class="small"><b>有狀態的（${withSm.length}）</b></div><div class="todo-chips">${withSm.map(chip).join('')}</div>
      ${without.length ? `<div class="small" style="margin-top:8px"><b>沒有狀態、變化用日期記的（${without.length}）</b></div><div class="todo-chips">${without.map(chip).join('')}</div>` : ''}
    </div>
    <div class="model-split flow-split">
      <section class="diagram">${sm.transitions.length ? flowDiagram(sm, tsel) : `<div class="card" style="box-shadow:none"><h3 style="margin-top:0">${esc(sm.label)}：${esc(sm.stateless || '沒有狀態')}</h3>
        <p class="muted small">不會從一個狀態走到另一個狀態；要記的變化寫在下面。</p>
        ${sm.notes.length ? `<div class="md">${md(sm.notes.map(n => '- ' + n.replace(/\n/g, '\n  ')).join('\n'))}</div>` : ''}</div>`}</section>
      <aside class="panel" id="panel">${flowPanel(r, sm, tsel)}</aside>
    </div>`,
  };
}
