// Domain 設計：任務板。資料都在切片 repo 的 .md，這裡只讀寫審查頁裡人要填的欄位。
'use strict';

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const CIRCLED = ['', '①', '②', '③', '④', '⑤', '⑥'];
const state = { slices: [], slice: null, home: null, review: null, path: null, sel: null, showAll: false, sessionChoice: null, busy: false };

// ---------- 工具 ----------

async function api(url, body) {
  const r = await fetch(url, body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {});
  if (!r.ok) {
    let msg = r.statusText;
    try { msg = (await r.json()).detail || msg; } catch (e) { /* 不是 JSON */ }
    throw new Error(msg);
  }
  return r.json();
}

function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// 行內：`code`，「檔名:行號」做成點了打開檔案的連結
const FILE_REF = /`?([^\s`「」（）()、，；<>]+?\.(?:md|ya?ml|js|sql|py)):(\d+)`?/g;
function inline(s) {
  return esc(s)
    .replace(FILE_REF, (m, f, n) => `<a class="ref-link" data-file="${f}" data-line="${n}">${f}:${n}</a>`)
    .replace(/`([^`]+)`/g, '<code>$1</code>');
}

// 給人看的白話：拿掉出處括號、〔日期〕與標記，技術細節另外收起來
function plain(s) {
  return String(s || '')
    .replace(/〔[^〕]*〕/g, '')
    .replace(/\[(解讀|待專家確認|未核對|靜態替代|推導)[^\]]*\]/g, '')
    .replace(/（[^（）]*(?:D-\d+|X-\d+|Q\d+|EQ-\d+|\.md|#\d+)[^（）]*）/g, '')
    .replace(/`/g, '').replace(/\s+/g, ' ').trim();
}

function today() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function remember(k, v) {
  try { if (v === undefined) return localStorage.getItem(k) || ''; localStorage.setItem(k, v); } catch (e) { /* 私密視窗 */ }
  return '';
}

let toastTimer;
function toast(msg) {
  const t = $('#toast');
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 5000);
}

function go(h) { if (location.hash === h) route(); else location.hash = h; }
const enc = encodeURIComponent;

function setTop(back, mid) {
  const b = $('#back');
  b.hidden = !back;
  if (back) { b.href = back[0]; b.textContent = '← ' + back[1]; }
  $('#topMid').innerHTML = mid || '';
}

function stepName(step) {
  const nums = (step.match(/\d+/g) || []).map(Number);
  if (!nums.length) return step;
  return nums.length > 1 ? `${CIRCLED[nums[0]]}～${CIRCLED[nums[nums.length - 1]]}` : CIRCLED[nums[0]];
}

const LEVEL_NAME = { 1: '範圍', 2: '名詞盤點', 3: '流程', 4: '規則', 5: '對照與紙上驗證', 6: '驗收' };

// ---------- 資料 ----------

async function loadReview(path) {
  state.path = path;
  state.review = await api('/api/review?path=' + enc(path));
  return state.review;
}

async function write(url, body) {
  const r = state.review;
  try {
    const res = await api(url, { path: r.path, digest: r.digest, ...body });
    r.digest = res.digest;
    await loadReview(r.path);
    return true;
  } catch (e) {
    toast(e.message);
    if (/重新載入/.test(e.message)) { await loadReview(r.path); route(); }
    return false;
  }
}

function tasksOf(r) {
  const c = r.counts;
  return {
    decide: { total: c.questions, open: c.questions_open },
    confirm: { total: c.confirms, open: c.confirms_open },
    golden: { total: c.cases, open: c.cases_open },
    finish: { spot: c.spot_done, sign: c.conclusion_done },
  };
}

function nextTask(r) {
  const c = r.counts;
  const p = enc(r.path);
  if (c.questions_open) return `#/r/${p}/decide/${firstOpenQ(r)}`;
  if (c.confirms_open) return `#/r/${p}/confirm`;
  if (c.cases_open) return `#/r/${p}/golden/${r.cases.findIndex(caseOpen)}`;
  return `#/r/${p}/finish`;
}

function firstOpenQ(r, after = -1) {
  const qs = r.questions;
  let i = qs.findIndex((q, k) => k > after && !q.answer.trim());
  if (i < 0) i = qs.findIndex(q => !q.answer.trim());
  return i;
}

const HUMAN = ['預期結果', '計算過程', '計算者'];
function caseOpen(c) { return HUMAN.some(k => !(c.fields[k] && c.fields[k].value.trim())); }

// ---------- 首頁：輪到你 ----------

async function renderHome(slice) {
  state.slice = slice;
  syncSlicePick();
  const h = state.home = await api('/api/home?slice=' + enc(slice));
  setTop(null, '');
  const app = $('#app');
  const levels = h.levels.map(l => {
    const label = { frozen: '過關', review: '挑戰中', draft: '', locked: '' }[l.state];
    return `<div class="level ${l.state}" title="${esc(l.tag)}"><b>${CIRCLED[l.n]}</b><span>${esc(l.name)}${label ? '　' + label : ''}</span></div>`;
  }).join('');

  let hero, tasks = '', changes = '';
  const cur = h.current;
  if (cur) {
    const r = await loadReview(cur.path);
    const c = r.counts;
    const nums = (cur.step.match(/\d+/g) || []).map(Number);
    const title = nums.length > 1 ? `關卡 ${stepName(cur.step)}` : `關卡 ${CIRCLED[nums[0]]}　${LEVEL_NAME[nums[0]] || ''}`;
    const parts = [];
    if (c.questions) parts.push(`<strong>${c.questions} 個決定</strong>`);
    if (c.confirms) parts.push(r.model ? `<strong>1 張模型圖</strong>（${c.confirms} 項確認）` : `<strong>${c.confirms} 項確認</strong>`);
    if (c.cases) parts.push(`<strong>${c.cases} 個案例要算</strong>`);
    parts.push('抽查與簽名');
    const mins = Math.max(5, Math.round(c.questions_open * 2 + c.confirms_open * 0.5 + c.cases_open * 10 + 4));
    const why = (r.meta.find(m => m.key === '起因') || {}).value || '';
    hero = `
      <section class="hero">
        <div style="flex:999 1 480px;min-width:0">
          <span class="chip">輪到你</span>
          <h1>${esc(title)}</h1>
          <p>${esc(plain(why.split('，依據')[0]))}</p>
          <p>過關條件：${parts.join('＋')}，還要大約 ${mins} 分鐘。</p>
        </div>
        <a class="btn big yellow" href="${nextTask(r)}">${c.open === (c.questions + c.confirms + c.cases + 2) ? '開始' : '繼續'} ›</a>
      </section>`;
    const t = tasksOf(r);
    const p = enc(r.path);
    const bar = (total, open) => {
      const pct = total ? Math.round((total - open) / total * 100) : 100;
      return `<span class="bar"><i class="${open ? '' : 'full'}" style="width:${Math.max(pct, open ? 4 : 100)}%"></i></span>`;
    };
    const task = (href, name, total, open) => total ? `
      <a class="task ${open ? '' : 'complete'}" href="${href}">
        <span class="head"><span>${name}</span><span>${total - open} / ${total}</span></span>${bar(total, open)}</a>` : '';
    const before = t.decide.open + t.confirm.open + t.golden.open;
    tasks = `
      <section class="side">
        <h2>任務</h2>
        ${task(`#/r/${p}/decide/${Math.max(0, firstOpenQ(r))}`, `做 ${t.decide.total} 個決定`, t.decide.total, t.decide.open)}
        ${task(`#/r/${p}/confirm`, r.model ? '看模型圖，確認這輪的改動' : '確認這輪的改動', t.confirm.total, t.confirm.open)}
        ${task(`#/r/${p}/golden/0`, `算 ${t.golden.total} 個黃金案例`, t.golden.total, t.golden.open)}
        ${before ? `<div class="task locked"><span>抽查 1～2 條、簽名過關</span><span>前面完成後解鎖</span></div>`
                 : task(`#/r/${p}/finish`, '抽查 1～2 條、簽名過關', 2, (t.finish.spot ? 0 : 1) + (t.finish.sign ? 0 : 1))}
      </section>`;
    const items = r.model ? r.model.entities.filter(e => e.changed) : [];
    changes = items.length
      ? `<div class="grid2">${items.map(e => `<a class="change" href="#/r/${p}/confirm/${e.id}" style="text-decoration:none;color:inherit">
          <span class="chip new">新</span><b>${esc(e.label)}</b><div>${esc(e.definition)}</div></a>`).join('')}</div>`
      : `<div class="card">${r.meta.filter(m => !/填完之後/.test(m.key)).map(m => `<div class="small"><b>${esc(m.key)}</b>　${esc(plain(m.value))}</div>`).join('')}</div>`;
  } else {
    hero = `
      <section class="hero idle">
        <div style="flex:999 1 480px;min-width:0">
          <span class="chip">沒有要你審的</span>
          <h1>目前輪到 AI</h1>
          <p class="muted">沒有待作答的審查頁。請 AI 做下一步，它做完會產生新的審查頁，這裡就會出現新的關卡。</p>
        </div>
        <button class="btn big primary" id="askNext">請 AI 做下一步 ›</button>
      </section>`;
  }

  const past = h.reviews.filter(x => !cur || x.path !== cur.path);
  app.innerHTML = `
    <nav class="levels" aria-label="切片關卡">${levels}</nav>
    ${hero}
    <div class="cols">
      ${tasks}
      <section class="wide">
        ${cur ? `<h2>這一關 AI 改了什麼</h2>${changes}` : ''}
        ${h.eq_open ? `<div class="card hint row spread"><span><strong>支線：等專家回答 ${h.eq_open} 題</strong>　不擋這一關。專家回覆後交給 AI 處理。</span>
          <button class="btn" id="expertReply">專家回覆了</button></div>` : ''}
        ${past.length ? `<details class="past"><summary>之前的關卡（${past.length}）</summary>${past.map(x => `<a href="#/r/${enc(x.path)}/finish">${esc(x.date)} ${esc(stepName(x.step))}${x.counts && !x.counts.open ? ' ✓' : ''}</a>`).join('')}</details>` : ''}
      </section>
    </div>`;
  const askNext = $('#askNext');
  if (askNext) askNext.onclick = () => aiPrompt('繼續做下一步');
  const er = $('#expertReply');
  if (er) er.onclick = () => aiPrompt('專家回覆了：EQ-', false);
}

// ---------- 一次一個決定 ----------

function progressSegs(items, cur, isDone, hrefOf) {
  return `<div class="segs" style="grid-template-columns:repeat(${items.length},minmax(0,1fr))">${items.map((x, k) =>
    `<span class="${k === cur ? 'cur' : isDone(x) ? 'done' : ''}" data-href="${hrefOf(k)}" title="${k + 1}"></span>`).join('')}</div>`;
}

async function renderDecide(path, i) {
  const r = state.review && state.path === path ? state.review : await loadReview(path);
  const qs = r.questions;
  const p = enc(path);
  const homeHref = `#/s/${enc(r.slice)}`;
  if (!qs.length) { go(nextTask(r)); return; }
  if (!qs[i]) i = 0;
  const q = qs[i];
  setTop([homeHref, '關卡'], progressSegs(qs, i, x => x.answer.trim(), k => `#/r/${p}/decide/${k}`) +
    `<span class="count">${qs.length - r.counts.questions_open} / ${qs.length}</span>`);

  const ans = q.answer.trim();
  const chosen = /^[A-Z]$/.test(ans) ? ans : null;
  const topic = q.topic || (q.ref || '').replace(/^[①-⑥]\s*/, '');
  $('#app').innerHTML = `
    <div class="narrow">
      <div>
        <span class="chip">${esc(topic || `問題 ${q.n}`)}</span>
        <h1 class="qtitle">${esc(q.question)}</h1>
      </div>
      ${q.example ? `<section class="card"><div class="label">舉個例子</div>${inline(q.example)}</section>` : ''}
      <fieldset style="border:0;margin:0;padding:0;display:flex;flex-direction:column;gap:14px">
        <legend class="label">選一個${ans && !chosen ? `（你寫了：${esc(ans)}）` : ''}</legend>
        <div class="opts">${q.options.map(o => `
          <button class="opt ${o.recommended ? 'rec' : ''} ${chosen === o.key ? 'on' : ''}" data-opt="${o.key}">
            <span class="row spread"><span class="k">${o.key}</span>${o.recommended ? '<span class="badge-rec">★ AI 建議</span>' : ''}${chosen === o.key ? '<span class="badge-rec">你選的</span>' : ''}</span>
            <span class="sum">${inline(o.summary || o.text)}</span>
            ${o.outcome ? `<span class="out">選了之後：${inline(o.outcome)}</span>` : ''}
          </button>`).join('')}</div>
        <label class="label" style="color:var(--ink);font-size:15px">都不是？寫一句你的想法
          <div class="row" style="margin-top:6px"><input type="text" id="other" style="flex:1" value="${chosen || !ans ? '' : esc(ans)}" placeholder="寫一句，按 Enter 送出">
          <button class="btn" id="otherSave">送出</button></div>
        </label>
      </fieldset>
      ${q.background ? `<section class="card hint"><strong>為什麼要你決定：</strong>${inline(q.background)}</section>` : ''}
      <section class="card">
        <label class="label" for="ask" style="color:var(--ink);font-size:16px">看不懂？直接問 AI</label>
        <div class="row"><input type="text" id="ask" class="soft" style="flex:1" placeholder="例：選 B 的話，哪裡會不一樣？">
          <button class="btn go" id="askBtn">問</button></div>
        <div class="small muted" style="margin-top:6px">AI 只解釋這一題，不改檔案。</div>
        <div class="ask-answer" id="askOut" hidden></div>
      </section>
      <div class="row spread">
        <button class="btn ghost" id="skip">先跳過，等等再回來</button>
        <details class="tech"><summary>技術細節</summary>
          <div>問題 ${q.n}${q.ref ? `（${esc(q.ref)}）` : ''} · <a class="ref-link" data-file="${esc(path)}" data-line="${q.line}">審查頁第 ${q.line} 行</a>
          ${q.section && !q.section.startsWith('一') ? ` · ${esc(q.section)}` : ''}</div>
        </details>
      </div>
    </div>`;

  const after = async () => {
    const n = firstOpenQ(state.review, i);
    if (n >= 0 && n !== i) go(`#/r/${p}/decide/${n}`);
    else if (n < 0) renderDone('決定', `${qs.length} 個決定都做完了`, nextTask(state.review));
    else renderDecide(path, i);
  };
  const save = async v => { if (await write('/api/review/answer', { line: q.answer_line, value: v })) after(); };
  $$('[data-opt]').forEach(b => b.onclick = () => save(b.dataset.opt));
  const other = () => { const v = $('#other').value.trim(); if (v) save(v); };
  $('#otherSave').onclick = other;
  $('#other').onkeydown = e => { if (e.key === 'Enter') other(); };
  $('#skip').onclick = () => {
    const n = qs.findIndex((x, k) => k > i && !x.answer.trim());
    go(`#/r/${p}/decide/${n >= 0 ? n : (i + 1) % qs.length}`);
  };
  const ask = () => {
    const v = $('#ask').value.trim();
    if (!v) return;
    askAi(`只解釋，不要修改任何檔案。審查頁 ${path} 的問題 ${q.n}（${q.ref}）：「${q.question}」。我的疑問：${v}`, $('#askOut'));
  };
  $('#askBtn').onclick = ask;
  $('#ask').onkeydown = e => { if (e.key === 'Enter') ask(); };
}

function renderDone(what, msg, nextHref) {
  setTop([`#/s/${enc(state.review.slice)}`, '關卡'], '');
  $('#app').innerHTML = `
    <section class="card lift celebrate pop">
      <div class="stars">★ ★ ★</div>
      <h1>${esc(what)}完成！</h1>
      <p class="muted">${esc(msg)}。答案已經寫回審查頁。</p>
      <div class="row" style="justify-content:center;margin-top:16px">
        <a class="btn big primary" href="${nextHref}">下一個任務 ›</a>
        <a class="btn big" href="#/s/${enc(state.review.slice)}">回關卡</a>
      </div>
    </section>`;
}

// ---------- 看圖確認 ----------

function groupOf(what) {
  return what.split('：')[0].replace(/（[^）]*\d+\/\d+[^）]*）/, '').trim();
}

function confirmRow(c) {
  const ans = (c.answer || '').trim();
  return `<div class="crow ${ans ? 'done' : ''}">
    <div>${inline(c.cells['要看的'] || '')}</div>
    <div class="orig">${inline(c.cells['原文'] || '')}　${inline(c.cells['在哪裡'] || '')}</div>
    <div class="acts">
      ${ans ? `<span class="val">${ans === '✓' ? '✓ 沒問題' : '意見：' + esc(ans)}</span>` : ''}
      <button class="btn ${ans ? '' : 'go'}" data-ok="${c.line}">✓ 合理</button>
      <button class="btn" data-note="${c.line}">寫意見</button>
    </div>
  </div>`;
}

function layout(model, showAll) {
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
  const W = 150, H = 56, GX = 22, GY = 80, PER = 4;
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

function short(s, n) { s = String(s); return s.length > n ? s.slice(0, n - 1) + '…' : s; }

function edgePath(a, b) {
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

function renderDiagram(r) {
  const L = layout(r.model, state.showAll);
  const sel = state.sel;
  const okd = id => {
    const e = r.model.entities.find(x => x.id === id);
    const lines = new Set([...(e ? e.confirm_lines : []), ...r.model.relations.filter(x => x.from === id && x.changed).flatMap(x => x.confirm_lines)]);
    return lines.size && [...lines].every(l => (r.confirms.find(c => c.line === l) || {}).answer);
  };
  const edges = L.edges.map(x => {
    const g = edgePath(L.nodes.get(x.from), L.nodes.get(x.to));
    const hot = sel && (x.from === sel || x.to === sel);
    const label = hot ? `<g class="elabel" transform="translate(${g.mx},${g.my})"><rect x="-38" y="-10" width="76" height="20" rx="10"></rect><text text-anchor="middle" y="4">${esc(x.label.slice(0, 6))} ${esc(x.card)}</text></g>` : '';
    return `<path class="edge ${x.changed ? 'changed' : ''} ${hot ? 'hot' : ''} ${x.cancelled ? 'cancelled' : ''}" d="${g.d}"><title>${esc(x.from)} ${esc(x.name)}（${esc(x.label)}）→ ${esc(x.to)}　${esc(x.card)}</title></path>${label}`;
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
  return `<svg width="${L.width}" height="${L.height}" viewBox="0 0 ${L.width} ${L.height}" role="img" aria-label="模型圖">${edges.join('')}${nodes.join('')}</svg>`;
}

function entityPanel(r, id) {
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
    ${e.attrs && e.attrs.length ? `<div class="box"><div class="label">記下什麼</div><div class="attrs">${e.attrs.map(a => `<span title="${esc(a.name)}">${esc(short(a.label.split(/[，：；]/)[0] || a.name, 14))}</span>`).join('')}</div></div>` : ''}
    ${e.separate ? `<div class="box"><div class="label">為什麼要單獨記</div>${esc(e.separate)}</div>` : ''}
    ${e.not ? `<div class="box"><div class="label">它不是</div>${esc(e.not)}</div>` : ''}
    ${rows.length ? `<div class="label" style="margin-top:4px">要你確認（${rows.length - open.length} / ${rows.length}）</div>${rows.map(confirmRow).join('')}` : ''}
    ${open.length ? `<div class="row"><button class="btn primary" id="allOk">合理，下一個</button><button class="btn" id="entNote">不對，寫意見</button></div>` : ''}
    <details class="tech"><summary>技術細節</summary>${e.line ? `<a class="ref-link" data-file="${esc(r.model.path)}" data-line="${e.line}">${esc(r.model.path.split('/').pop())} 第 ${e.line} 行</a>` : '不在本切片定義'}</details>`;
}

async function renderConfirm(path, sel) {
  const r = state.review && state.path === path ? state.review : await loadReview(path);
  const p = enc(path);
  const homeHref = `#/s/${enc(r.slice)}`;
  const total = r.counts.confirms, open = r.counts.confirms_open;
  setTop([homeHref, '關卡'], `<span class="bar" style="flex:1"><i class="${open ? '' : 'full'}" style="width:${total ? (total - open) / total * 100 : 100}%"></i></span><span class="count">${total - open} / ${total}</span>`);

  const inModel = new Set();
  let modelHtml = '';
  if (r.model) {
    for (const e of r.model.entities) (e.confirm_lines || []).forEach(l => inModel.add(l));
    for (const x of r.model.relations) (x.confirm_lines || []).forEach(l => inModel.add(l));
    const changed = r.model.entities.filter(e => e.changed);
    if (!sel) {
      const firstOpen = changed.find(e => e.confirm_lines.some(l => !(r.confirms.find(c => c.line === l) || {}).answer));
      sel = (firstOpen || changed[0] || {}).id || null;
    }
    state.sel = sel;
    modelHtml = `
      <div class="legend">
        <span><i style="background:var(--done);border:3px solid var(--ink)"></i>這輪新增或改動</span>
        <span><i style="background:#fff;border:2px solid var(--ink)"></i>本切片原本就有</span>
        <span><i style="background:#fff;border:2px solid var(--faint)"></i>引用其他地方的</span>
        <label class="small" style="font-weight:400"><input type="checkbox" id="showAll" ${state.showAll ? 'checked' : ''}> 顯示全部名詞</label>
      </div>
      <div class="cols">
        <section class="diagram">${renderDiagram(r)}</section>
        <aside class="panel" id="panel">${entityPanel(r, sel)}</aside>
      </div>`;
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
      <div class="row spread"><h3>${esc(g.name)}</h3>${open.length > 1 ? `<button class="btn go" data-group="${k}">這 ${open.length} 項都沒問題</button>` : ''}</div>
      <div class="list">${g.rows.map(confirmRow).join('')}</div></section>`;
  }).join('');

  $('#app').innerHTML = `
    ${r.model ? `<div><h1 style="margin:0">看圖確認：這輪改了哪些東西</h1><p class="muted" style="margin:4px 0 0">點綠色方塊看說明；合理就按「合理，下一個」。</p></div>${modelHtml}` : ''}
    ${groups.length ? `<div><h2 style="margin:0">${r.model ? '其他要確認的' : '確認這輪的改動'}</h2><p class="muted small" style="margin:4px 0 0">每一項打 ✓ 或寫一句意見。原文和行號可以點開看。</p></div><div class="groups">${groupsHtml}</div>` : ''}
    ${!open ? `<div class="row"><a class="btn big primary" href="${nextTask(r)}">確認完成，下一個任務 ›</a></div>` : ''}`;

  const refresh = s => renderConfirm(path, s === undefined ? state.sel : s);
  const okAll = async lines => {
    for (const l of lines) if (!await write('/api/review/cells', { line: l, cells: { '確認': '✓' } })) return false;
    return true;
  };
  $$('[data-ok]').forEach(b => b.onclick = async () => { if (await okAll([+b.dataset.ok])) refresh(); });
  $$('[data-note]').forEach(b => b.onclick = () => openNote(b, +b.dataset.note, refresh));
  $$('[data-group]').forEach(b => b.onclick = async () => {
    const g = groups[+b.dataset.group];
    if (await okAll(g.rows.filter(c => !(c.answer || '').trim()).map(c => c.line))) refresh();
  });
  $$('[data-node]').forEach(n => n.onclick = () => history.replaceState(null, '', `#/r/${p}/confirm/${n.dataset.node}`) || refresh(n.dataset.node));
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
function openNote(btn, line, done) {
  const row = btn.closest('.crow') || btn.parentElement;
  if ($('.note-box', row)) return;
  row.insertAdjacentHTML('beforeend', `<div class="note-box row"><input type="text" style="flex:1" placeholder="哪裡不對？寫一句，按 Enter"><button class="btn primary">寫入</button></div>`);
  const inp = $('.note-box input', row);
  inp.focus();
  const save = async () => {
    const v = inp.value.trim();
    if (v && await write('/api/review/cells', { line, cells: { '確認': v } })) done();
  };
  $('.note-box button', row).onclick = save;
  inp.onkeydown = e => { if (e.key === 'Enter') save(); };
}

// ---------- 黃金案例 ----------

// 時間軸：取情境裡的日期（情境不到兩個日期才用輸入），每個日期一點
function timelineOf(c) {
  const pick = k => (c.fields[k] || {}).value || '';
  const build = text => {
    const evs = new Map();
    for (const seg of text.split(/[；。，\n]/)) {
      const m = seg.match(/(\d{4})-(\d{2})-(\d{2})/);
      if (!m) continue;
      const label = seg.replace(m[0], ' ').replace(/\s+/g, ' ').replace(/^[\s、：:]+|[\s、：:]+$/g, '');
      if (!evs.has(m[0])) evs.set(m[0], { date: m[0], t: new Date(m[0]).getTime(), labels: [] });
      if (label && !evs.get(m[0]).labels.includes(label)) evs.get(m[0]).labels.push(label);
    }
    return [...evs.values()].sort((x, y) => x.t - y.t);
  };
  let evs = build(pick('情境'));
  if (evs.length < 2) evs = build(pick('情境') + '；' + pick('輸入'));
  // 「要回答」問到的日期標成「你來算」
  for (const a of askParts(pick('要回答'))) {
    for (const d of a.text.match(/\d{4}-\d{2}-\d{2}/g) || []) {
      let e = evs.find(x => x.date === d);
      if (!e) { e = { date: d, t: new Date(d).getTime(), labels: [] }; evs.push(e); }
      e.ask = (e.ask || []).concat(a.no || '');
    }
  }
  evs.sort((x, y) => x.t - y.t);
  // 位置太近的放到第二排，免得字疊在一起
  const span = evs.length > 1 ? evs[evs.length - 1].t - evs[0].t : 1;
  let lastLeft = -100;
  evs.forEach(e => {
    e.left = (e.t - evs[0].t) / span * 82;
    e.low = e.left - lastLeft < 16 && !(evs[evs.indexOf(e) - 1] || {}).low;
    if (!e.low) lastLeft = e.left;
  });
  return evs;
}

function askParts(s) {
  return String(s || '').split(/；\s*(?=[①-⑨])/).map(x => x.trim()).filter(Boolean)
    .map(x => ({ no: /^[①-⑨]/.test(x) ? x[0] : '', text: x.replace(/^[①-⑨]\s*/, '') }));
}

async function renderGolden(path, i) {
  const r = state.review && state.path === path ? state.review : await loadReview(path);
  const cs = r.cases;
  const p = enc(path);
  if (!cs.length) { go(nextTask(r)); return; }
  if (!cs[i]) i = 0;
  const c = cs[i];
  setTop([`#/s/${enc(r.slice)}`, '關卡'], progressSegs(cs, i, x => !caseOpen(x), k => `#/r/${p}/golden/${k}`) + `<span class="count">案例 ${i + 1} / ${cs.length}</span>`);
  const f = k => (c.fields[k] || {}).value || '';
  const evs = timelineOf(c);
  const tl = evs.length > 1 ? `
    <section class="card lift timeline"><div class="tl" style="height:${evs.some(e => e.low) ? 190 : 130}px"><div class="axis"></div>${evs.map(e => `
      <div class="ev ${e.ask ? 'ask' : ''}" style="left:${e.left}%;${e.low ? 'top:96px' : ''}">
        <div class="d">${esc(e.date)}</div><div class="o"></div><div class="t">${esc(e.labels.join('；'))}${e.ask ? ` <span class="chip turn" style="font-size:11px">你來算 ${[...new Set(e.ask)].join('')}</span>` : ''}</div></div>`).join('')}
    </div></section>` : '';
  const [kind, ...rest] = c.title.split('：');
  const done = !caseOpen(c);
  const name = remember('reviewer');
  $('#app').innerHTML = `
    <div>
      <span class="chip">${esc(rest.length ? kind : c.id)}</span>
      <h1 style="margin:10px 0 4px;font-size:30px">${esc(rest.length ? rest.join('：') : c.title)}</h1>
      <p class="muted" style="margin:0">需要的資料都在這頁，不用翻檔案。你獨立算完並送出後，才會顯示設計推出的答案，兩邊對不上的地方就是要討論的地方。</p>
    </div>
    ${tl}
    <div class="cols">
      <section class="wide">
        <div class="card"><div class="label">情境</div>${inline(f('情境'))}</div>
        <div class="card"><div class="label">要回答</div><ul class="ask-list">${askParts(f('要回答')).map(a => `<li>${a.no ? `<span class="no">${a.no}</span>` : ''}<span>${inline(a.text)}</span></li>`).join('')}</ul></div>
        <div class="card" style="display:flex;flex-direction:column;gap:10px">
          <label class="label" for="g_exp" style="color:var(--ink);font-size:17px">你的答案（預期結果）</label>
          <textarea id="g_exp" rows="5" placeholder="一行一題，例：① 2026-01-01 給 3 日…">${esc(f('預期結果'))}</textarea>
          <label class="label" for="g_how" style="color:var(--ink)">怎麼算的（計算過程，附依據）</label>
          <textarea id="g_how" class="soft" rows="4">${esc(f('計算過程'))}</textarea>
          <label class="label" for="g_who" style="color:var(--ink)">計算者</label>
          <input type="text" id="g_who" class="soft" value="${esc(f('計算者') || name)}" placeholder="你的名字（不能是 AI）">
          <div class="row"><button class="btn big primary" id="g_save">送出，對答案</button></div>
        </div>
      </section>
      <aside class="side">
        <div class="card hint"><h2 style="font-size:17px;margin:0 0 8px">提示卡</h2>
          <ul style="margin:0;padding-left:20px;font-size:15px;display:flex;flex-direction:column;gap:4px">${f('輸入').split('；').filter(Boolean).map(x => `<li>${inline(x)}</li>`).join('')}</ul>
          ${f('專家確認') ? `<div class="small" style="margin-top:8px"><b>還在等專家：</b>${inline(plain(f('專家確認')))}</div>` : ''}
          <details class="tech" style="margin-top:8px"><summary>技術細節</summary>${c.id} · ${inline(f('驗證'))} · <a class="ref-link" data-file="${esc(path)}" data-line="${c.line}">審查頁第 ${c.line} 行</a></details>
        </div>
        <div class="card ${done ? '' : 'dashed'}"><h2 style="font-size:17px;margin:0 0 8px">對答案</h2>
          ${done ? `<div class="compare"><div><b>你</b>\n${esc(f('預期結果'))}</div><div><b>設計推出的</b>\n${esc(plain(f('紙上推演')) || '（AI 還沒推演，交給 AI 後補上）')}</div></div>
            <p class="small muted">對不上時，交給 AI 說明差在哪一步，由你決定哪個對。</p>`
          : `<div class="lockbox">送出你的答案後才顯示，<br>免得被設計的答案影響。</div>`}
        </div>
      </aside>
    </div>`;
  $('#g_save').onclick = async () => {
    const vals = { '預期結果': $('#g_exp').value.trim(), '計算過程': $('#g_how').value.trim(), '計算者': $('#g_who').value.trim() };
    if (!vals['預期結果'] || !vals['計算者']) { toast('預期結果與計算者要填'); return; }
    if (/^(ai|claude)$/i.test(vals['計算者'])) { toast('計算者不能是 AI'); return; }
    remember('reviewer', vals['計算者']);
    for (const k of HUMAN) {
      const cur = state.review.cases[i];
      if (!cur.fields[k]) { toast(`審查頁 ${cur.id} 沒有「${k}」這一欄，請 AI 照範本補上`); return; }
      if ((cur.fields[k].value || '') === vals[k]) continue;
      if (!await write('/api/review/case', { line: cur.fields[k].line, key: k, value: vals[k] })) return;
    }
    renderGolden(path, i);
  };
}

// ---------- 抽查與簽名過關 ----------

async function renderFinish(path) {
  const r = state.review && state.path === path ? state.review : await loadReview(path);
  const c = r.counts;
  setTop([`#/s/${enc(r.slice)}`, '關卡'], '<strong>最後一關：抽查與簽名</strong>');
  const left = [];
  if (c.questions_open) left.push(`<a href="#/r/${enc(path)}/decide/${firstOpenQ(r)}">${c.questions_open} 個決定</a>`);
  if (c.confirms_open) left.push(`<a href="#/r/${enc(path)}/confirm">${c.confirms_open} 項確認</a>`);
  if (c.cases_open) left.push(`<a href="#/r/${enc(path)}/golden/0">${c.cases_open} 個案例</a>`);
  const spotRow = r.spot.find(s => s.items.trim()) || r.spot[0];
  const picked = new Set((spotRow && spotRow.items.match(/\d+/g) || []).map(Number));
  const name = remember('reviewer');
  const signed = c.conclusion_done;
  $('#app').innerHTML = `
    <div class="narrow">
      ${left.length ? `<div class="card hint">還有 ${left.join('、')} 沒完成，完成後才能簽名。</div>` : ''}
      <section class="card lift" style="display:flex;flex-direction:column;gap:12px">
        <div><span class="chip">抽查</span><h2 style="margin:8px 0 0">挑 1～2 條，看 AI 的自評是不是真的</h2>
          <p class="muted small" style="margin:4px 0 0">這些是 AI 自評做到的完成標準。點一條會顯示 AI 怎麼說，再打開檔案看是不是這樣。發現不實，這一步改為逐條審查。</p></div>
        ${r.spot_items.length ? `<div class="picks">${r.spot_items.map(s => `
          <button class="pick ${picked.has(s.n) ? 'on' : ''}" data-pick="${s.n}">第 ${s.n} 條：${inline(s.text.replace(/\*\*/g, ''))}
            ${picked.has(s.n) ? `<div class="self">AI 自評：${esc(plain(s.self)).slice(0, 400)}<br><a class="ref-link" data-file="${esc(s.file)}" data-line="${s.line}">打開檔案看</a></div>` : ''}</button>`).join('')}</div>`
          : `<div class="small">${inline(r.spot_hint || '（審查頁沒有列出可挑的條目）')}</div><input type="text" id="spotItems" value="${esc(spotRow ? spotRow.items : '')}" placeholder="抽查了哪幾條，例：第 3、7 條">`}
        <div class="row">
          <button class="btn go" id="spotOk" ${picked.size || !r.spot_items.length ? '' : 'disabled'}>自評屬實</button>
          <input type="text" id="spotBad" style="flex:1;min-width:200px" class="soft" placeholder="或寫一句發現的問題，按 Enter" value="${spotRow && spotRow.result && !/^(屬實|符合|✓)/.test(spotRow.result) ? esc(spotRow.result) : ''}">
        </div>
        ${spotRow && spotRow.result ? `<div class="small"><b>已記下：</b>${esc(spotRow.items)} → ${esc(spotRow.result)}</div>` : ''}
      </section>
      <section class="card lift" style="display:flex;flex-direction:column;gap:12px">
        <div><span class="chip">簽名過關</span><h2 style="margin:8px 0 0">你是審查者（不是產出這一步的人）</h2></div>
        <input type="text" id="who" value="${esc(name)}" placeholder="你的名字">
        ${r.conclusion.map(x => `
          <div><div class="label">步驟 ${esc(x.cells['步驟'])}${x.cells['結論'] ? `　已簽：${esc(x.cells['結論'])}（${esc(x.cells['日期'])}）` : ''}</div>
          <div class="verdict">
            <button class="btn pass ${x.cells['結論'] === '通過' ? 'on' : ''}" data-verdict="${x.line}" data-v="通過" ${left.length || !c.spot_done ? 'disabled' : ''}>通過</button>
            <button class="btn fail ${x.cells['結論'] === '不通過' ? 'on' : ''}" data-verdict="${x.line}" data-v="不通過" ${!c.spot_done ? 'disabled' : ''}>不通過</button>
          </div></div>`).join('')}
        ${!c.spot_done ? '<div class="small muted">先完成抽查。</div>' : ''}
      </section>
      ${signed ? `
      <section class="card lift celebrate pop">
        <div class="stars">★ ★ ★</div><h1>關卡完成！</h1>
        <p class="muted">審查頁都填好了。交給 AI：它會依你的答案修改設計；全部通過的話，再請它凍結。</p>
        <div class="row" style="justify-content:center">
          <button class="btn big primary" id="handover">審查好了，交給 AI</button>
          <button class="btn big" id="freeze">請 AI 凍結</button>
        </div>
      </section>` : ''}
    </div>`;

  const spotLine = spotRow ? spotRow.line : null;
  const saveSpot = async (items, result) => {
    if (!spotLine) { toast('審查頁沒有抽查表'); return; }
    if (await write('/api/review/cells', { line: spotLine, cells: { '抽查了哪幾條': items, '結果': result } })) renderFinish(path);
  };
  const itemsText = () => {
    const inp = $('#spotItems');
    if (inp) return inp.value.trim();
    return picked.size ? `${r.spot_items[0] ? r.spot_items[0].file.split('/').pop() + ' ' : ''}完成標準第 ${[...picked].sort((a, b) => a - b).join('、')} 條` : '';
  };
  $$('[data-pick]').forEach(b => b.onclick = async e => {
    if (e.target.closest('.ref-link')) return;
    const n = +b.dataset.pick;
    if (picked.has(n)) picked.delete(n); else picked.add(n);
    if (picked.size > 2) { picked.delete(n); toast('挑 1～2 條就好'); return; }
    const items = picked.size ? `${r.spot_items[0].file.split('/').pop()} 完成標準第 ${[...picked].sort((a, b) => a - b).join('、')} 條` : '';
    await saveSpot(items, '');
  });
  $('#spotOk').onclick = () => { const it = itemsText(); if (!it) { toast('先挑 1～2 條'); return; } saveSpot(it, '自評屬實'); };
  $('#spotBad').onkeydown = e => {
    const v = e.target.value.trim();
    if (e.key === 'Enter' && v) { const it = itemsText(); if (!it) { toast('先挑 1～2 條'); return; } saveSpot(it, v); }
  };
  $$('[data-verdict]').forEach(b => b.onclick = async () => {
    const who = $('#who').value.trim();
    if (!who) { toast('先寫你的名字'); return; }
    remember('reviewer', who);
    const x = r.conclusion.find(y => y.line === +b.dataset.verdict);
    const key = Object.keys(x.cells).find(k => k.startsWith('審查者'));
    if (await write('/api/review/cells', { line: x.line, cells: { [key]: who, '日期': today(), '結論': b.dataset.v } })) renderFinish(path);
  });
  const ho = $('#handover');
  if (ho) ho.onclick = () => aiPrompt(`審查好了。審查頁：${path}`, true);
  const fz = $('#freeze');
  if (fz) fz.onclick = () => {
    const step = (path.match(/_([\d-]+)\.md$/) || [])[1] || '';
    aiPrompt(`/domain-freeze ${(step.match(/\d+/g) || []).map(Number).join(' ')}`, false);
  };
}

// ---------- 檔案 ----------

async function openFile(file, line) {
  const base = state.review && state.review.slice ? `slices/${state.review.slice}` : '';
  try {
    const f = await api(`/api/file?path=${enc(file)}&base=${enc(base)}`);
    $('#fileDrawer').hidden = false;
    $('#filePath').textContent = f.path + (line ? `:${line}` : '');
    const n = +line || 0;
    $('#fileBody').innerHTML = f.text.split('\n').map((l, k) => `<span class="ln ${k + 1 === n ? 'hit' : ''}" data-n="${k + 1}">${esc(l) || ' '}</span>`).join('');
    const hit = $('#fileBody .hit');
    if (hit) hit.scrollIntoView({ block: 'center' });
  } catch (e) { toast(e.message); }
}

// ---------- AI session ----------

function curSession() {
  const s = state.slices.find(x => x.slice === state.slice);
  return s && s.session;
}
function curPurpose() {
  const m = (state.path || '').match(/_([^/]+)\.md$/);
  return m ? `審查 ${m[1]}` : '設計';
}

async function refreshSlices() {
  const st = await api('/api/status');
  state.slices = st.slices;
  state.gitignored = st.gitignored;
  syncSlicePick();
  renderAiHead();
}

function syncSlicePick() {
  const sel = $('#slicePick');
  sel.innerHTML = state.slices.map(s => `<option value="${esc(s.slice)}" ${s.slice === state.slice ? 'selected' : ''}>${esc(s.slice)}</option>`).join('');
}

function renderAiHead() {
  const s = curSession();
  $('#aiDot').className = 'dot ' + (state.busy ? 'busy' : s ? 'on' : '');
  $('#aiLabel').textContent = state.busy ? 'AI 處理中' : s ? 'AI 待命中' : 'AI';
}

function openAi() { $('#aiDrawer').hidden = false; renderAi(); }

async function renderAi() {
  const box = $('#aiSession');
  if (!state.slice) { box.innerHTML = '先選一條切片。'; return; }
  const s = curSession();
  let warn = state.gitignored === false ? `<div class="small" style="background:var(--hint);padding:6px 10px;border-radius:10px">切片 repo 的 <code>.gitignore</code> 沒有排除 <code>.domain-web/</code>（session 登記表放在這裡），請加上這一行。</div>` : '';
  if (!s) { box.innerHTML = warn + await newSessionCard(`<b>${esc(state.slice)}</b> 還沒有使用中的 AI session。`); bindNewSession(); return; }
  const mismatch = s.purpose !== curPurpose();
  if ((mismatch || s.compacted) && state.sessionChoice !== s.id) {
    const why = s.compacted ? '這個 session 經過摘要壓縮，容易憑記憶回答' : `使用中的 session 是「${esc(s.purpose)}」，現在要做的是「${esc(curPurpose())}」`;
    box.innerHTML = warn + await newSessionCard(`${why}。要開新的 session 嗎？`, true);
    bindNewSession();
    $('#keepSession').onclick = () => { state.sessionChoice = s.id; renderAi(); };
    return;
  }
  box.innerHTML = warn + `<div>session：<b>${esc(s.name)}</b>（第 ${s.turns} 次）</div>
    <details class="tech"><summary>在 terminal 接著做</summary><code>claude --resume ${esc(s.id)}</code></details>
    <div><button class="btn" id="endSession">結束這個 session</button></div>`;
  $('#endSession').onclick = async () => { await api(`/api/sessions/${s.id}/end`, {}); await refreshSlices(); renderAi(); };
}

async function newSessionCard(msg, withKeep) {
  const h = await api(`/api/handoff?slice=${enc(state.slice)}&purpose=${enc(curPurpose())}&review=${enc(state.path || '')}`);
  return `<div>${msg}</div>
    <details><summary class="small">交接提示（由檔案產生，送出前可以改）</summary><textarea id="handoff">${esc(h.text)}</textarea></details>
    <div class="row"><button class="btn primary" id="newSession">A（建議）：開新的 session</button>
    ${withKeep ? '<button class="btn" id="keepSession">B：繼續用這個</button>' : ''}</div>`;
}

function bindNewSession() {
  $('#newSession').onclick = async () => {
    try {
      const s = await api('/api/sessions', { slice: state.slice, purpose: curPurpose(), handoff: $('#handoff').value });
      await refreshSlices();
      await renderAi();
      await aiSend(s.handoff);
    } catch (e) { toast(e.message); }
  };
}

// 主要動作：打開 AI 抽屜；send=true 直接送出，false 只填進輸入框讓人補完
async function aiPrompt(text, send = true) {
  openAi();
  if (!curSession()) { $('#aiInput').value = text; toast('先開一個 AI session，再送出'); return; }
  if (send) aiSend(text);
  else { $('#aiInput').value = text; $('#aiInput').focus(); }
}

// 行內問 AI：答案顯示在題目旁邊，不必打開抽屜
async function askAi(text, out) {
  if (!curSession()) { openAi(); toast('先開一個 AI session（右邊），再問'); return; }
  out.hidden = false;
  out.innerHTML = '<span class="tool">AI 思考中…</span>';
  let first = true;
  await aiSend(text, ev => {
    if (first) { out.innerHTML = ''; first = false; }
    if (ev.kind === 'text' && !ev.sub) out.insertAdjacentHTML('beforeend', inline(ev.text) + '\n');
    else if (ev.kind === 'tool' && !ev.sub) out.insertAdjacentHTML('beforeend', `<span class="tool">· ${esc(ev.name)} ${esc(ev.brief)}</span>\n`);
  }, true);
}

async function aiSend(text, onEvent, quiet) {
  const s = curSession();
  if (!s) { openAi(); return; }
  if (state.busy) { toast('AI 還在處理上一件事'); return; }
  const log = $('#aiLog');
  log.insertAdjacentHTML('beforeend', `<div class="me">› ${esc(text)}</div>`);
  if (!quiet) $('#aiDrawer').hidden = false;
  state.busy = true; renderAiHead();
  $('#aiSend').disabled = true;
  try {
    const r = await fetch(`/api/sessions/${s.id}/send`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }) });
    if (!r.ok) throw new Error((await r.json()).detail);
    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let k;
      while ((k = buf.indexOf('\n')) >= 0) {
        const line = buf.slice(0, k); buf = buf.slice(k + 1);
        if (!line.trim()) continue;
        const ev = JSON.parse(line);
        showEvent(ev);
        if (onEvent) onEvent(ev);
      }
    }
  } catch (e) { toast(e.message); }
  state.busy = false;
  $('#aiSend').disabled = false;
  await refreshSlices();
  if (!quiet) route();  // AI 可能改了審查頁或產生了新的
}

function showEvent(ev) {
  const log = $('#aiLog');
  const sub = ev.sub ? ' sub' : '';
  if (ev.kind === 'text') log.insertAdjacentHTML('beforeend', `<div class="t${sub}">${inline(ev.text)}</div>`);
  else if (ev.kind === 'tool') log.insertAdjacentHTML('beforeend', `<div class="tool${sub}">· ${esc(ev.name)} ${esc(ev.brief)}</div>`);
  else if (ev.kind === 'compacted') log.insertAdjacentHTML('beforeend', '<div class="deny">這個 session 剛經過摘要壓縮，建議做完這一段就開新的 session。</div>');
  else if (ev.kind === 'error') log.insertAdjacentHTML('beforeend', `<div class="err">${esc(ev.text)}</div>`);
  else if (ev.kind === 'result') {
    for (const d of ev.denials || []) log.insertAdjacentHTML('beforeend', `<div class="deny">被擋下（要核准）：${esc(d.tool)}。請在 terminal 用 <code>claude --resume</code> 處理。</div>`);
    if (!ev.ok) log.insertAdjacentHTML('beforeend', `<div class="err">${esc(ev.text)}</div>`);
  }
  log.scrollTop = log.scrollHeight;
}

// ---------- 路由 ----------
// #/s/<切片>　#/r/<審查頁>/decide/<n>　#/r/<審查頁>/confirm[/<Entity>]　#/r/<審查頁>/golden/<n>　#/r/<審查頁>/finish

async function route() {
  $('#fileDrawer').hidden = true;
  const parts = location.hash.replace(/^#\/?/, '').split('/').map(decodeURIComponent);
  try {
    if (parts[0] === 's' && parts[1]) return await renderHome(parts[1]);
    if (parts[0] === 'r' && parts[1]) {
      const path = parts[1];
      const m = path.match(/^slices\/([^/]+)\//);
      if (m) { state.slice = m[1]; syncSlicePick(); renderAiHead(); }
      if (state.path !== path) await loadReview(path);
      const view = parts[2] || 'decide';
      if (view === 'decide') return await renderDecide(path, +parts[3] || 0);
      if (view === 'confirm') return await renderConfirm(path, parts[3] || null);
      if (view === 'golden') return await renderGolden(path, +parts[3] || 0);
      return await renderFinish(path);
    }
    const first = state.slices.find(s => s.reviews.some(r => r.counts && r.counts.open)) || state.slices[0];
    if (first) go(`#/s/${enc(first.slice)}`);
    else $('#app').innerHTML = '<div class="card">這個 repo 的 <code>slices/</code> 底下還沒有切片。請 AI 先做規劃（<code>/domain-plan</code>）。</div>';
  } catch (e) { toast(e.message); }
}

document.addEventListener('click', e => {
  const a = e.target.closest('a.ref-link');
  if (a) { e.preventDefault(); e.stopPropagation(); openFile(a.dataset.file, a.dataset.line); return; }
  const seg = e.target.closest('[data-href]');
  if (seg) go(seg.dataset.href);
  const x = e.target.closest('[data-close]');
  if (x) $('#' + x.dataset.close).hidden = true;
}, true);
document.addEventListener('keydown', e => { if (e.key === 'Escape') { $('#fileDrawer').hidden = true; $('#aiDrawer').hidden = true; } });
$('#aiBtn').onclick = () => { if ($('#aiDrawer').hidden) openAi(); else $('#aiDrawer').hidden = true; };
$('#slicePick').onchange = e => go(`#/s/${enc(e.target.value)}`);
$('#aiForm').onsubmit = e => {
  e.preventDefault();
  const v = $('#aiInput').value.trim();
  if (v) { $('#aiInput').value = ''; aiSend(v); }
};
window.addEventListener('hashchange', route);

refreshSlices().then(route).catch(e => toast(e.message));
