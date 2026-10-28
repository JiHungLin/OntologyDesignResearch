// Domain 設計：任務板。從主題草案、規劃、開切片，到每一步的審查與凍結。
// 資料都在設計 repo 的 .md；網頁只寫人做的事（作答、接受草稿、存資料），其他交給 AI（claude -p，在背景跑）。
'use strict';

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const CIRCLED = ['', '①', '②', '③', '④', '⑤', '⑥'];
const state = { slices: [], sessions: [], scope: null, slice: null, home: null, project: null, review: null, path: null, sel: null, showAll: false, watching: {} };

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
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>');
}

// 給人看的白話：拿掉出處括號、〔日期〕與標記，技術細節另外收起來
function plain(s) {
  return String(s || '')
    .replace(/〔[^〕]*〕/g, '')
    .replace(/\[(解讀|待專家確認|未核對|靜態替代|推導)[^\]]*\]/g, '')
    .replace(/（[^（）]*(?:D-\d+|X-\d+|Q\d+|EQ-\d+|\.md|#\d+)[^（）]*）/g, '')
    .replace(/`/g, '').replace(/\s+/g, ' ').trim();
}

// 給草稿、說明用的簡單 Markdown：標題、清單、表格、引用、段落
function md(text) {
  const out = [];
  let para = [], list = null, table = null;
  const flush = () => {
    if (para.length) { out.push(`<p>${inline(para.join(' '))}</p>`); para = []; }
    if (list) { out.push(`<${list.tag}>${list.items.map(x => `<li>${inline(x)}</li>`).join('')}</${list.tag}>`); list = null; }
    if (table) {
      const [h, ...rows] = table.filter(r => !/^\s*\|[\s:|-]+\|\s*$/.test(r));
      const cells = r => r.trim().replace(/^\||\|$/g, '').split(/(?<!\\)\|/).map(c => c.trim());
      out.push(`<div class="tbl"><table><tr>${cells(h).map(c => `<th>${inline(c)}</th>`).join('')}</tr>${rows.map(r => `<tr>${cells(r).map(c => `<td>${inline(c)}</td>`).join('')}</tr>`).join('')}</table></div>`);
      table = null;
    }
  };
  let inComment = false;
  for (const line of String(text || '').split('\n')) {
    if (inComment) { if (line.includes('-->')) inComment = false; continue; }
    if (line.includes('<!--')) { if (!line.includes('-->')) inComment = true; continue; }
    let m;
    if ((m = line.match(/^(#{1,4})\s+(.*)$/))) { flush(); out.push(`<h${Math.min(m[1].length + 1, 5)}>${inline(m[2])}</h${Math.min(m[1].length + 1, 5)}>`); }
    else if (line.startsWith('|')) { if (!table) { flush(); table = []; } table.push(line); }
    else if ((m = line.match(/^\s*(?:[-*]|(\d+)\.)\s+(.*)$/))) {
      const tag = m[1] ? 'ol' : 'ul';
      if (!list || list.tag !== tag) { flush(); list = { tag, items: [] }; }
      list.items.push(m[2]);
    }
    else if ((m = line.match(/^>\s?(.*)$/))) { flush(); out.push(`<blockquote>${inline(m[1])}</blockquote>`); }
    else if (!line.trim()) flush();
    else { if (list || table) flush(); para.push(line.trim()); }
  }
  flush();
  return out.join('');
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

// ---------- 切片首頁：輪到你 ----------

// 每一步 AI 做什麼、做完要你做什麼（給還沒開始的關卡看）
const STEP_INFO = {
  1: ['範圍與驗收問題', '這條切片做到哪裡、做完要能回答哪些問題', '回答範圍的選擇題、確認驗收問題'],
  2: ['名詞盤點', '哪些是「一個東西」、彼此什麼關係', '看模型圖，確認新增的名詞與關係'],
  3: ['流程與狀態', '事情怎麼發生、誰能做、錯了怎麼改', '確認狀態、歷史需求與更正方式'],
  4: ['規則與限制', '什麼情況允許、什麼必須成立、依據是什麼', '回答規則的選擇題、確認依據'],
  5: ['投影到實作與紙上驗證', '每個概念放在哪張表、哪支 API；照設計推演黃金案例', '自己算 1～3 個黃金案例，和設計對答案'],
  6: ['跑起來驗證', '在真的系統上跑黃金案例、回答驗收問題', '簽核（執行者和簽核者不同人）'],
};

function levelStrip(levels) {
  return `<nav class="levels" aria-label="切片關卡">${levels.map(l => {
    const label = { frozen: '過關', review: '挑戰中', wait: '等你凍結', draft: '進行中', locked: '未開始' }[l.state];
    const href = l.state !== 'locked' && state.slice ? `#/f/${enc(`slices/${state.slice}/${STEP_FILE[l.n]}`)}` : '';
    return `<div class="level ${l.state}" title="${esc(l.status)} ${esc(l.tag)}${href ? '（點一下看檔案）' : ''}" ${href ? `data-href="${href}" role="link" tabindex="0"` : ''}>
      <b>${CIRCLED[l.n]}</b><span>${esc(l.name)}<small>${label}</small></span></div>`;
  }).join('')}</nav>`;
}

async function renderHome(slice) {
  state.slice = slice;
  state.scope = slice;
  markNav();
  const h = state.home = await api('/api/home?slice=' + enc(slice));
  setTop(['#/', '總覽'], `<strong>${esc(slice)}</strong>`);
  const app = $('#app');
  const s = sessionOf(slice);
  let hero = '', tasks = '', changes = '';
  const cur = h.current;
  const wait = h.levels.filter(l => l.state === 'wait');
  if (s && s.running) {
    hero = runningCard(slice);
  } else if (cur) {
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
    changes = `<h2>這一關 AI 改了什麼</h2>` + (items.length
      ? `<div class="grid2">${items.map(e => `<a class="change" href="#/r/${p}/confirm/${e.id}" style="text-decoration:none;color:inherit">
          <span class="chip new">新</span><b>${esc(e.label)}</b><div>${esc(e.definition)}</div></a>`).join('')}</div>`
      : `<div class="card">${r.meta.filter(m => !/填完之後/.test(m.key)).map(m => `<div class="small"><b>${esc(m.key)}</b>　${esc(plain(m.value))}</div>`).join('')}</div>`);
  } else if (wait.length) {
    // 審查頁都填好了、還沒凍結
    const last = h.reviews[0];
    const step = last ? last.step : String(wait[0].n).padStart(2, '0');
    hero = `
      <section class="hero">
        <div style="flex:999 1 480px;min-width:0">
          <span class="chip">輪到你</span>
          <h1>審查填好了：${esc(stepName(step))}</h1>
          <p>交給 AI 依你的答案修改；結論都是「通過」的話，請 AI 凍結（凍結＝之後的修改都要留紀錄）。</p>
        </div>
        <div class="row"><button class="btn big yellow" id="handover">交給 AI 處理答案</button><button class="btn big" id="freeze">請 AI 凍結</button></div>
      </section>`;
  } else if (h.next) {
    const n = h.next.n;
    const info = STEP_INFO[n];
    const going = h.next.status !== '未開始';
    hero = `
      <section class="hero idle">
        <div style="flex:999 1 480px;min-width:0">
          <span class="chip">輪到 AI</span>
          <h1>${going ? `第 ${CIRCLED[n]} 步還沒做完` : `下一關：${CIRCLED[n]} ${esc(info[0])}`}</h1>
          <p>AI 會整理：${esc(info[1])}。做完後另開 AI 挑錯、核對，產生一份審查頁，這裡就會出現新的關卡。</p>
          <p class="muted small">之後輪到你：${esc(info[2])}。${n === 6 ? '第 ⑥ 步要有實作好的系統才做。' : ''}</p>
        </div>
        <button class="btn big primary" id="doStep">${going ? `請 AI 繼續第 ${CIRCLED[n]} 步` : `請 AI 開始第 ${CIRCLED[n]} 步`} ›</button>
      </section>`;
  } else {
    hero = `<section class="card lift celebrate pop"><div class="stars">★ ★ ★</div><h1>這條切片全部完成！</h1>
      <p class="muted">①～⑥ 都凍結了。回總覽挑下一條。</p><a class="btn big primary" href="#/">回總覽</a></section>`;
  }

  const designDone = h.levels.slice(0, 5).every(l => l.state === 'frozen') && h.levels[5].state !== 'frozen';
  if (designDone && !(s && s.running)) {
    hero = `<section class="card lift celebrate pop"><div class="stars">★ ★ ★</div><h1>設計完成（待驗證）</h1>
      <p class="muted">①～⑤ 都凍結了，這是一個設計版本。第 ⑥ 步等系統實作好再做；現在可以開始下一條切片。</p>
      <div class="row" style="justify-content:center"><a class="btn big primary" href="#/">挑下一條切片 ›</a><button class="btn big" id="doStep">系統好了，開始 ⑥</button></div></section>`;
  }

  const eqOpen = h.eqs.filter(e => e['狀態'] !== '已回覆');
  const eqTodo = h.eqs.filter(e => e['狀態'] === '已回覆' && !e['處理']);
  const past = h.reviews.filter(x => !cur || x.path !== cur.path);
  app.innerHTML = `
    ${levelStrip(h.levels)}
    ${waitingCard(slice)}
    ${hero}
    <div class="cols">
      ${tasks}
      <section class="wide">
        ${changes}
        ${eqOpen.length || eqTodo.length ? `<a class="card hint row spread" href="#/eq/${enc(slice)}" style="text-decoration:none;color:inherit">
          <span><strong>支線：專家問題</strong>　${eqOpen.length ? `${eqOpen.length} 題還沒有答覆（不擋關卡）` : ''}${eqTodo.length ? `　${eqTodo.length} 題答覆了、還沒處理` : ''}</span><span class="btn">打開 ›</span></a>` : ''}
        <section class="card">
          <div class="label">發現問題、專家或客戶有新說法？</div>
          <div class="row"><input type="text" id="changeText" style="flex:1" placeholder="例：店長說兼職人員也有特休、實作時發現餘額算錯…">
            <button class="btn" id="changeBtn">交給 AI 判斷</button></div>
          <div class="small muted" style="margin-top:6px">AI 會判斷要回哪一步、影響多大，先提出方案，不會直接改。</div>
        </section>
        ${past.length ? `<details class="past"><summary>之前的關卡（${past.length}）</summary>${past.map(x => `<a href="#/r/${enc(x.path)}/finish">${esc(x.date)} ${esc(stepName(x.step))}${x.counts && !x.counts.open ? ' ✓' : ''}</a>`).join('')}</details>` : ''}
      </section>
    </div>`;
  bindWaiting();
  const sa = $('#showAi'); if (sa) sa.onclick = openAi;
  const ds = $('#doStep');
  if (ds) ds.onclick = () => {
    const n = designDone ? 6 : h.next.n;
    runAi(slice, `第 ${n} 步`, `/domain-step ${n} ${slice}`);
  };
  const ho = $('#handover');
  if (ho) ho.onclick = () => { const r0 = h.reviews[0]; runAi(slice, `審查 ${r0.step}`, `審查好了。審查頁：${r0.path}`, { review: r0.path }); };
  const fz = $('#freeze');
  if (fz) fz.onclick = () => { const r0 = h.reviews[0]; runAi(slice, `凍結 ${r0.step}`, `/domain-freeze ${(r0.step.match(/\d+/g) || []).map(Number).join(',')} ${slice}`, { review: r0.path }); };
  const cb = $('#changeBtn');
  const change = () => { const v = $('#changeText').value.trim(); if (v) runAi(slice, '修改', `/domain-change ${v}`); };
  cb.onclick = change;
  $('#changeText').onkeydown = e => { if (e.key === 'Enter') change(); };
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
      ${q.background ? `<section class="why"><div class="label">為什麼要你決定</div>${inline(q.background)}</section>` : ''}
      <fieldset style="border:0;margin:0;padding:0;display:flex;flex-direction:column;gap:18px">
        <legend class="label">選一個${ans && !chosen ? `（你寫了：${esc(ans)}）` : ''}</legend>
        <div class="opts">${q.options.map(o => `
          <button class="opt ${o.recommended ? 'rec' : ''} ${chosen === o.key ? 'on' : ''}" data-opt="${o.key}">
            <span class="row spread"><span class="k">${o.key}</span>${o.recommended ? '<span class="badge-rec">★ AI 建議</span>' : ''}${chosen === o.key ? '<span class="badge-rec">你選的</span>' : ''}</span>
            <span class="sum">${inline(o.summary || o.text)}</span>
            ${o.outcome ? `<span class="out">選了之後：${inline(o.outcome)}</span>` : ''}
          </button>`).join('')}</div>
        <label class="label" style="color:var(--ink);font-size:15px;margin-top:6px">都不是？寫一句你的想法
          <div class="row" style="margin-top:10px"><input type="text" id="other" style="flex:1" value="${chosen || !ans ? '' : esc(ans)}" placeholder="寫一句，按 Enter 送出">
          <button class="btn" id="otherSave">送出</button></div>
        </label>
      </fieldset>
      <section class="card soft-card">
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
      const label = seg.replace(m[0], ' ').replace(/\s+/g, ' ').replace(/^[\s、：:]+|[\s、：:]+$/g, '').replace(/([^\x00-\xff])\s+(?=[^\x00-\xff])/g, '$1');
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
    e.left = (e.t - evs[0].t) / span * 100;
    e.low = e.left - lastLeft < 14 && !(evs[evs.indexOf(e) - 1] || {}).low;
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
  const askChip = e => e.ask ? `<span class="chip turn">你來算 ${[...new Set(e.ask)].join('')}</span>` : '';
  const tl = evs.length > 1 ? `
    <section class="card timeline">
      <div class="tl-wrap"><div class="tl"><div class="axis"></div>${evs.map((e, k) => `
        <div class="ev ${e.ask ? 'ask' : ''} ${e.low ? 'low' : ''}" style="left:${e.left}%"><div class="d">${esc(e.date)}</div><div class="o">${k + 1}</div></div>`).join('')}
      </div></div>
      <ol class="tl-list">${evs.map((e, k) => `<li class="${e.ask ? 'ask' : ''}"><span class="o">${k + 1}</span><b>${esc(e.date)}</b><span>${esc(e.labels.join('；')) || '<span class="muted">算到這一天</span>'}</span>${askChip(e)}</li>`).join('')}</ol>
    </section>` : '';
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
  const step = (path.match(/_([\d-]+)(?:-\d)?\.md$/) || [])[1] || '';
  if (ho) ho.onclick = () => runAi(r.slice, `審查 ${step}`, `審查好了。審查頁：${path}`, { review: path });
  const fz = $('#freeze');
  if (fz) fz.onclick = () => runAi(r.slice, `凍結 ${step}`, `/domain-freeze ${(step.match(/\d+/g) || []).map(Number).join(',')} ${r.slice}`, { review: path });
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
// 範圍（scope）：規劃用 _plan，其他用切片代號。一個範圍同一時間一個使用中的 session。
// 換一件事（用途不同）或 session 經過摘要壓縮時，用選擇題問要不要開新的（精簡版「換 session 的時機」）。

function sessionOf(scope) { return state.sessions.find(s => s.slice === scope && s.status === '使用中'); }
// AI 抽屜跟著「最後交給 AI 的範圍」走，換頁不會斷；頁面自己的範圍是 state.scope
function aiScope() { return state.aiScope || state.scope; }
function curSession() { return sessionOf(aiScope()); }
function scopeName(scope) { return scope === '_plan' ? '規劃' : scope; }

async function refreshSessions() {
  const r = await api('/api/sessions');
  state.sessions = r.sessions;
  state.gitignored = r.gitignored;
  for (const s of state.sessions) if (s.running) watch(s.id);
  renderAiHead();
}

async function refreshSlices() {
  const st = await api('/api/status');
  state.slices = st.slices;
  markNav();
  await refreshSessions();
}

// ---------- 左側導覽 ----------
// 總覽、主題草案、規劃、各切片（狀態＋各步驟檔案）、core/、inputs/。展開狀態記在這個瀏覽器。

const STEP_FILE = { 1: '01_scope.md', 2: '02_entities.md', 3: '03_flows.md', 4: '04_rules.md', 5: '05_mapping.md', 6: '06_evidence/signoff.md' };

function navOpenSet() { try { return new Set(JSON.parse(localStorage.getItem('nav-open') || '[]')); } catch (e) { return new Set(); } }
function navSaveOpen(set) { try { localStorage.setItem('nav-open', JSON.stringify([...set])); } catch (e) { } }

function sliceState(f, row) {
  if (!f) return { text: (row && row['狀態']) || '', cls: '' };
  if (f.session && f.session.running) return { text: 'AI 進行中', cls: 'busy' };
  if (f.review) return { text: '輪到你審查', cls: 'turn' };
  if (!f.next) return { text: '完成', cls: 'ok' };
  if (f.next.n === 6) return { text: '設計完成', cls: 'ok' };
  return { text: `下一關 ${CIRCLED[f.next.n]}`, cls: '' };
}

function stepCls(status) { return status.startsWith('已凍結') ? 'frozen' : status === '待檢查' ? 'wait' : status === '未開始' ? '' : 'draft'; }

function renderNav() {
  const P = state.project;
  const nav = $('#navTree');
  if (!P) return;
  const open = navOpenSet();
  const a = (href, label, extra = '', cls = '') => `<a class="nav-a ${cls}" href="${href}">${label}${extra ? `<span class="nav-x">${extra}</span>` : ''}</a>`;
  const fileA = (path, label) => a(`#/f/${enc(path)}`, esc(label || path.split('/').pop()));
  const node = (key, summary, body, dflt) => {
    const isOpen = open.has(key) || (dflt && !open.has('!' + key));
    return `<details class="nav-node" data-nav="${esc(key)}" ${isOpen ? 'open' : ''}><summary>${summary}</summary><div class="nav-kids">${body}</div></details>`;
  };
  const folderTree = (groups, top, fileLink) => {
    const dirs = Object.keys(groups).sort();
    return dirs.map(d => {
      const files = groups[d].map(fileLink).join('');
      return d === top ? files : node('dir:' + d, `<span class="nav-dir">${esc(d.slice(top.length + 1))}/</span><span class="nav-x">${groups[d].length}</span>`, files);
    }).join('');
  };
  const plan = P.plan;
  const list = planSlices(P);
  const started = list.filter(x => x.f), waiting = list.filter(x => !x.f);
  const pendingDrafts = P.drafts.filter(d => d.pending).length;

  const sliceNode = x => {
    const f = x.f;
    const st = sliceState(f, x.row);
    const steps = f.steps.map(t => {
      const label = `<i class="${stepCls(t.status)}">${CIRCLED[t.n]}</i>${esc(t.name)}`;
      return t.status === '未開始' ? `<span class="nav-a off">${label}<span class="nav-x">未開始</span></span>`
        : a(`#/f/${enc(`slices/${x.code}/${t.file}`)}`, label, esc(t.status.replace(/（.*/, '')));
    }).join('');
    const others = f.files.filter(p => !Object.values(STEP_FILE).some(sf => p.endsWith('/' + sf)));
    const body = a(`#/s/${enc(x.code)}`, '切片首頁')
      + (f.review ? a(`#/r/${enc(f.review.path)}`, '審查（輪到你）', `${f.review.counts.open} 件`, 'hot') : '')
      + a(`#/eq/${enc(x.code)}`, '專家問題', f.eq_open ? `${f.eq_open} 題待答` : '')
      + `<div class="nav-steps">${steps}</div>`
      + (others.length ? node('files:' + x.code, '<span class="nav-dir">其他檔案</span>', others.map(p => fileA(p)).join('')) : '');
    return node('s:' + x.code, `<span class="nav-name" title="${esc(x.code)}">${esc(x.code)}</span><span class="nav-st ${st.cls}">${esc(st.text)}</span>`, body, state.slice === x.code);
  };

  nav.innerHTML = `
    ${a('#/', '總覽')}
    ${P.topic ? fileA(P.topic, '主題草案') : plan ? '' : a('#/start', '主題草案', '還沒寫')}
    ${node('plan', `<span class="nav-name">規劃</span><span class="nav-st ${plan && plan.agreed ? 'ok' : plan ? 'turn' : ''}">${plan ? (plan.agreed ? '已同意' : '討論中') : '還沒有'}</span>`,
      a('#/plan', '規劃頁') + (plan ? fileA('slices/PLAN.md', '切片地圖 PLAN.md') : '')
      + (P.sketch ? fileA('slices/ENTITY_SKETCH.md', '名詞草圖') : '')
      + (P.drafts.length ? node('drafts', `<span class="nav-dir">推想草稿</span><span class="nav-x">${pendingDrafts ? pendingDrafts + ' 待接受' : P.drafts.length}</span>`,
        P.drafts.map(d => a(`#/draft/${enc(d.path)}`, esc(d.title), d.pending ? '待接受' : '')).join('')) : ''), !plan || !plan.agreed)}
    <div class="nav-h">切片</div>
    ${started.map(sliceNode).join('') || '<div class="nav-empty">還沒有開始的切片</div>'}
    ${waiting.length ? node('waiting', `<span class="nav-dir">還沒開始</span><span class="nav-x">${waiting.length}</span>`,
      waiting.map(x => a(plan && plan.agreed && x.row['狀態'] === '候選' ? `#/new/${enc(x.code)}` : '#/plan', esc(x.code), esc(x.row['狀態'] || ''))).join('')) : ''}
    <div class="nav-h">資料與成果</div>
    ${node('core', `<span class="nav-name">core</span><span class="nav-x">共用核心</span>`,
      Object.keys(P.core).length ? folderTree(P.core, 'core', p => fileA(p)) : '<div class="nav-empty">第一次凍結 ②③④ 後才有</div>')}
    ${node('inputs', `<span class="nav-name">inputs</span><span class="nav-x">收集的資料</span>`,
      (Object.keys(P.inputs).length ? folderTree(P.inputs, 'inputs', p => p.startsWith('inputs/drafts/') ? a(`#/draft/${enc(p)}`, esc(p.split('/').pop())) : fileA(p)) : '<div class="nav-empty">還沒有資料</div>')
      + `<button class="nav-add" id="navAddInput">＋ 加資料</button>`)}
    ${a('#/f/' + enc('slices/CHANGELOG.md'), '變更紀錄 CHANGELOG')}`;
  nav.querySelectorAll('details.nav-node').forEach(d => d.addEventListener('toggle', () => {
    const set = navOpenSet(), k = d.dataset.nav;
    set.delete(k); set.delete('!' + k);
    set.add(d.open ? k : '!' + k);
    navSaveOpen(set);
  }));
  $('#navAddInput').onclick = () => inputDialog({ folder: 'shared' });
  markNav();
}

function markNav() {
  const h = location.hash || '#/';
  let best = null;
  $$('#sideNav a.nav-a').forEach(x => {
    x.classList.remove('on');
    const href = x.getAttribute('href');
    if (h === href || (href !== '#/' && h.startsWith(href + '/'))) if (!best || href.length > best.getAttribute('href').length) best = x;
  });
  if (best) {
    best.classList.add('on');
    for (let d = best.closest('details'); d; d = d.parentElement.closest('details')) d.open = true;
  }
}

async function refreshNav() { try { await loadProject(); renderNav(); } catch (e) { } }

// 像 Notion：側欄是獨立的一欄（展開時頂列往右擠）。收起時頂列最左邊是 ☰，點了才展開（滑過不彈出）；展開時側欄頂列最左邊是收起鈕；Ctrl+\ 切換
function setNav(open) {
  document.body.classList.toggle('nav-closed', !open);
  syncNav();
  if (!narrow()) try { localStorage.setItem('nav-closed', open ? '' : '1'); } catch (e) { }
}
function syncNav() {
  const closed = document.body.classList.contains('nav-closed');
  const b = $('#navBtn');
  b.title = '展開側欄（Ctrl+\\）';
  b.setAttribute('aria-label', b.title);
  b.setAttribute('aria-expanded', String(!closed));
}
function narrow() { return matchMedia('(max-width: 900px)').matches; }

// ---------- 檔案（唯讀） ----------

async function renderFile(path) {
  state.slice = (path.match(/^slices\/([^/]+)\//) || [])[1] || null;
  state.scope = state.slice || (path.startsWith('slices/') || path.startsWith('inputs/') ? '_plan' : null);
  setTop(state.slice ? [`#/s/${enc(state.slice)}`, state.slice] : ['#/', '總覽'], `<strong>${esc(path.split('/').pop())}</strong>`);
  const f = await api('/api/file?path=' + enc(path));
  const ext = (path.match(/\.([^./]+)$/) || [])[1] || '';
  $('#app').innerHTML = `
    <div class="file-view">
      <div class="row spread"><div><div class="label">唯讀</div><h1 style="margin:0;font-size:26px">${esc(f.path)}</h1></div>
        ${f.binary ? '' : `<button class="btn small-btn" id="rawView">看行號</button>`}</div>
      ${f.binary ? `<div class="card dashed">這是原始檔（${Math.round(f.size / 1024)} KB），網頁不顯示內容。AI 會直接讀它。</div>`
        : ext === 'md' ? `<article class="card doc">${md(f.text)}</article>`
        : `<pre class="card code-view">${esc(f.text)}</pre>`}
      <p class="small muted">網頁不直接改這些檔案。要改，在切片首頁「發現問題」或規劃頁「寫意見」交給 AI。</p>
    </div>`;
  const rv = $('#rawView'); if (rv) rv.onclick = () => openFile(f.path, 1);
}

function anyRunning() { return state.sessions.some(s => s.running); }

function renderAiHead() {
  const s = curSession();
  const run = state.sessions.find(x => x.running);
  $('#aiDot').className = 'dot ' + (run ? 'busy' : s ? 'on' : '');
  $('#aiLabel').textContent = run ? `AI 處理中（${scopeName(run.slice)}）` : s ? 'AI 待命中' : 'AI';
}

function openAi(scope) { if (scope) state.aiScope = scope; else if (state.scope) state.aiScope = state.scope; $('#aiDrawer').hidden = false; renderAi(); }

async function renderAi() {
  const box = $('#aiSession');
  const warn = state.gitignored === false ? `<div class="small" style="background:var(--hint);padding:6px 10px;border-radius:10px">設計 repo 的 <code>.gitignore</code> 沒有排除 <code>.domain-web/</code>（AI session 的登記與紀錄放在這裡），請加上這一行。</div>` : '';
  if (state.pending) { box.innerHTML = warn + state.pending.html; state.pending.bind(); return; }
  const s = curSession();
  if (!aiScope()) { box.innerHTML = warn + '<div class="muted">在總覽頁時，AI 對話跟著你按的按鈕走（規劃或某條切片）。</div>'; $('#aiLog').innerHTML = ''; return; }
  if (!s) { box.innerHTML = warn + `<div><b>${esc(scopeName(aiScope()))}</b> 還沒有 AI session。按畫面上的按鈕交給 AI 時會自動開一個。</div>`; $('#aiLog').innerHTML = ''; return; }
  box.innerHTML = warn + `<div>session：<b>${esc(s.name)}</b>（第 ${s.turns} 次）${s.running ? '　<span class="chip turn">處理中</span>' : ''}</div>
    <details class="tech"><summary>在 terminal 接著做</summary><code>claude --resume ${esc(s.id)}</code></details>
    <div><button class="btn" id="endSession" ${s.running ? 'disabled' : ''}>結束這個 session</button></div>`;
  $('#endSession').onclick = async () => { await api(`/api/sessions/${s.id}/end`, {}); await refreshSessions(); renderAi(); };
  const ev = await api(`/api/sessions/${s.id}/events`);
  const log = $('#aiLog');
  log.innerHTML = '';
  ev.events.slice(-300).forEach(showEvent);
  log.dataset.sid = s.id;
  log.dataset.n = ev.n;
}

// 交給 AI 的唯一入口：scope 範圍、purpose 用途、message 要說的話
async function runAi(scope, purpose, message, opts = {}) {
  await refreshSessions();
  const s = sessionOf(scope);
  state.aiScope = scope;
  if (s && s.running) { openAi(scope); toast('AI 還在處理上一件事，做完再交下一件'); return; }
  const same = s && s.purpose === purpose && !s.compacted;
  if (same || (s && opts.keep)) return send(s, message, opts);
  if (!s) return startNew(scope, purpose, message, opts);
  // 用途不同或壓縮過：問人
  const why = s.compacted ? '現在的 session 經過摘要壓縮，容易憑記憶回答' : `現在的 session 是「${esc(s.purpose)}」，這件事是「${esc(purpose)}」`;
  const h = await api(`/api/handoff?slice=${enc(scope)}&purpose=${enc(purpose)}&review=${enc(opts.review || '')}`);
  state.pending = {
    html: `<div class="card hint" style="padding:12px 14px"><b>${why}。</b>要開新的 session 嗎？
      <details style="margin-top:6px"><summary class="small">新 session 的交接提示（由檔案產生，可以改）</summary><textarea id="handoff">${esc(h.text)}</textarea></details>
      <div class="row" style="margin-top:8px"><button class="btn primary" id="newSession">A（建議）：開新的</button><button class="btn" id="keepSession">B：繼續用這個</button></div></div>`,
    bind() {
      $('#newSession').onclick = () => { const t = $('#handoff').value; state.pending = null; startNew(scope, purpose, message, opts, t); };
      $('#keepSession').onclick = () => { state.pending = null; send(s, message, opts); };
    },
  };
  openAi(scope);
}

async function startNew(scope, purpose, message, opts, handoffText) {
  try {
    if (handoffText === undefined) handoffText = (await api(`/api/handoff?slice=${enc(scope)}&purpose=${enc(purpose)}&review=${enc(opts.review || '')}`)).text;
    // 交接提示叫 AI 先讀檔、執行 /domain-status；接著做這件事，不用再等一輪
    const first = handoffText.replace(/讀完後執行 \/domain-status，用一句話說明現在的狀態與下一步，等我指示。/, '讀完後執行 /domain-status，然後做下面這件事。') + '\n\n' + message;
    const s = await api('/api/sessions', { slice: scope, purpose, handoff: handoffText });
    await refreshSessions();
    return send(s, first, opts);
  } catch (e) { toast(e.message); }
}

async function send(s, text, opts = {}) {
  try {
    await api(`/api/sessions/${s.id}/send`, { text });
  } catch (e) { toast(e.message); return; }
  state.aiScope = s.slice;
  await refreshSessions();
  if (!opts.quiet) openAi(s.slice);
  watch(s.id, opts.onEvent);
  if (!opts.quiet) route();
}

// 輪詢背景工作的事件；做完時重新整理畫面（AI 可能改了檔案）
function watch(sid, onEvent) {
  const w = state.watching[sid] = state.watching[sid] || { n: 0 };
  if (onEvent) w.onEvent = onEvent;
  if (w.timer) return;
  const tick = async () => {
    let r;
    try { r = await api(`/api/sessions/${sid}/events?after=${w.n}`); } catch (e) { w.timer = null; return; }
    const log = $('#aiLog');
    const shown = !$('#aiDrawer').hidden && log.dataset.sid === sid;
    r.events.forEach((ev, k) => {
      if (shown && w.n + k >= +log.dataset.n) { showEvent(ev); log.dataset.n = w.n + k + 1; }
    });
    w.n += r.events.length;
    for (const ev of r.events) {
      if (w.onEvent) w.onEvent(ev);
      if (ev.kind === 'tool' && !ev.sub) state.lastTool = `${ev.name} ${ev.brief}`;
    }
    const live = $('#liveTool');
    if (live && state.lastTool) live.textContent = state.lastTool;
    if (r.running) { w.timer = setTimeout(tick, 1500); return; }
    w.timer = null; w.onEvent = null;
    await refreshSessions();
    if (!$('#aiDrawer').hidden) renderAi();
    if (!w.quietDone) { toast('AI 做完了，畫面已更新'); route(); }
    w.quietDone = false;
  };
  w.timer = setTimeout(tick, 300);
}

// 行內問 AI：答案顯示在題目旁邊；用這條切片目前的 session，只解釋不改檔
async function askAi(text, out) {
  const scope = state.scope;
  state.aiScope = scope;
  const s = sessionOf(scope);
  out.hidden = false;
  out.innerHTML = '<span class="tool">AI 思考中…</span>';
  let first = true;
  const onEvent = ev => {
    if (ev.kind === 'me') return;
    if (first) { out.innerHTML = ''; first = false; }
    if (ev.kind === 'text' && !ev.sub) out.insertAdjacentHTML('beforeend', inline(ev.text) + '\n');
    else if (ev.kind === 'tool' && !ev.sub) out.insertAdjacentHTML('beforeend', `<span class="tool">· ${esc(ev.name)} ${esc(ev.brief)}</span>\n`);
  };
  if (s && s.running) { out.innerHTML = 'AI 還在處理別的事，等一下再問。'; return; }
  const w = s && (state.watching[s.id] = state.watching[s.id] || { n: 0 });
  if (w) w.quietDone = true;
  if (s) return send(s, text, { quiet: true, onEvent });
  await startNew(scope, curPurpose(), text, { quiet: true, onEvent });
}

function curPurpose() {
  const m = (state.path || '').match(/_([^/]+)\.md$/);
  return m ? `審查 ${m[1]}` : '設計';
}

function showEvent(ev) {
  const log = $('#aiLog');
  const sub = ev.sub ? ' sub' : '';
  if (ev.kind === 'me') state.lastText = '';
  if (ev.kind === 'me') log.insertAdjacentHTML('beforeend', `<div class="me">› ${esc(ev.text.length > 600 ? ev.text.slice(0, 600) + '…' : ev.text)}</div>`);
  else if (ev.kind === 'text') { log.insertAdjacentHTML('beforeend', `<div class="t${sub}">${inline(ev.text)}</div>`); if (!ev.sub) state.lastText = ev.text; }
  else if (ev.kind === 'tool') log.insertAdjacentHTML('beforeend', `<div class="tool${sub}">· ${esc(ev.name)} ${esc(ev.brief)}</div>`);
  else if (ev.kind === 'compacted') log.insertAdjacentHTML('beforeend', '<div class="deny">這個 session 剛經過摘要壓縮，建議做完這一段就開新的 session。</div>');
  else if (ev.kind === 'error') log.insertAdjacentHTML('beforeend', `<div class="err">${esc(ev.text)}</div>`);
  else if (ev.kind === 'result') {
    for (const d of ev.denials || []) log.insertAdjacentHTML('beforeend', `<div class="deny">被擋下（要核准）：${esc(d.tool)} ${esc(JSON.stringify(d.input || '').slice(0, 160))}。請在 terminal 用 <code>claude --resume</code> 處理。</div>`);
    if (!ev.ok) log.insertAdjacentHTML('beforeend', `<div class="err">${esc(ev.text)}</div>`);
    else if (ev.text && ev.text.trim() !== (state.lastText || '').trim()) log.insertAdjacentHTML('beforeend', `<div class="t">${inline(ev.text)}</div>`);
    log.insertAdjacentHTML('beforeend', '<div class="tool">— 這一輪結束 —</div>');
  }
  log.scrollTop = log.scrollHeight;
}

// AI 最後一則回覆裡的選擇題（WEB_PROMPT 要它照「問題／例子／A（建議）／B／其他」寫）
function parseAsk(text) {
  const lines = String(text || '').split('\n').map(l => l.replace(/^\s*[-*]\s*/, '').replace(/\*\*/g, '').trim());
  const opts = [];
  let q = '', ex = '';
  for (const l of lines) {
    let m;
    if ((m = l.match(/^問題[：:]\s*(.+)$/))) q = m[1];
    else if ((m = l.match(/^例子[：:]\s*(.+)$/))) ex = m[1];
    else if ((m = l.match(/^([A-H])(（建議）)?[：:]\s*(.+)$/))) {
      const [sum, out] = m[3].split(/\s*→\s*/);
      opts.push({ key: m[1], rec: !!m[2], sum, out: out || '' });
    }
  }
  return opts.length >= 2 ? { q, ex, opts } : null;
}

// 「AI 在等你」：範圍內的 session 最後一則回覆；有選擇題就做成按鈕
function waitingCard(scope) {
  const s = sessionOf(scope);
  if (!s || s.running || !s.last_reply) return '';
  const key = 'seen:' + s.id + ':' + s.last_at;
  if (remember(key)) return '';
  const ask = parseAsk(s.last_reply);
  const body = ask
    ? `${ask.q ? `<h2 style="margin:6px 0">${esc(ask.q)}</h2>` : ''}${ask.ex ? `<div class="box"><div class="label">舉個例子</div>${inline(ask.ex)}</div>` : ''}
       <div class="opts" style="margin-top:10px">${ask.opts.map(o => `<button class="opt ${o.rec ? 'rec' : ''}" data-reply="${o.key}"><span class="row spread"><span class="k">${o.key}</span>${o.rec ? '<span class="badge-rec">★ AI 建議</span>' : ''}</span><span class="sum">${inline(o.sum)}</span>${o.out ? `<span class="out">選了之後：${inline(o.out)}</span>` : ''}</button>`).join('')}</div>`
    : '';
  if (!ask) {
    const first = s.last_reply.split('\n').map(x => x.trim()).filter(Boolean).pop() || '';
    return `<details class="card waiting quiet" data-scope="${esc(scope)}"><summary><span class="chip">AI 上次說</span> ${esc(plain(first).slice(0, 120))}</summary>
      <div class="ai-said">${md(s.last_reply.length > 1500 ? s.last_reply.slice(-1500) : s.last_reply)}</div>
      <div class="row" style="margin-top:10px"><input type="text" class="soft" data-replytext style="flex:1" placeholder="回覆 AI（例：好，繼續）"><button class="btn primary" data-replysend>送出</button><button class="btn ghost small-btn" data-seen="${esc(key)}">收起來</button></div></details>`;
  }
  return `<section class="card lift waiting" data-scope="${esc(scope)}">
    <div class="row spread"><span class="chip turn">${ask ? 'AI 在等你回答' : 'AI 上次說'}</span><button class="btn ghost small-btn" data-seen="${esc(key)}">不用回了</button></div>
    ${body}
    <div class="row" style="margin-top:10px"><input type="text" class="soft" data-replytext style="flex:1" placeholder="都不是？寫一句"><button class="btn primary" data-replysend>送出</button></div>
  </section>`;
}

function bindWaiting() {
  $$('.waiting').forEach(card => {
    const scope = card.dataset.scope;
    const s = sessionOf(scope);
    const reply = v => runAi(scope, s.purpose, v, { keep: true });
    $$('[data-reply]', card).forEach(b => b.onclick = () => reply(b.dataset.reply));
    const inp = $('[data-replytext]', card);
    const go1 = () => { const v = inp.value.trim(); if (v) reply(v); };
    $('[data-replysend]', card).onclick = go1;
    inp.onkeydown = e => { if (e.key === 'Enter') go1(); };
    $('[data-seen]', card).onclick = () => { remember($('[data-seen]', card).dataset.seen, '1'); card.remove(); };
  });
}

// 「AI 正在做…」：範圍內有背景工作時顯示
function runningCard(scope, what) {
  const s = sessionOf(scope);
  if (!s || !s.running) return '';
  return `<section class="hero idle working">
    <div style="flex:999 1 480px;min-width:0">
      <span class="chip">輪到 AI</span><h1>${esc(what || `AI 正在做：${s.purpose}`)}</h1>
      <p class="muted small">做完畫面會自動更新。可以先去做別的事，或打開右上角的 AI 看過程。</p>
      <p class="small live"><span class="dot busy"></span> <span id="liveTool">${esc(state.lastTool || '準備中…')}</span></p>
    </div>
    <button class="btn big" id="showAi">看過程</button>
  </section>`;
}

// ---------- 總覽：整個 domain 走到哪 ----------

async function loadProject() { state.project = await api('/api/project'); return state.project; }

function planSlices(P) {
  // 地圖上的切片，依建議順序；加上資料夾裡的進度
  const rows = (P.plan ? P.plan.slices : []).slice().sort((a, b) => (+a['建議順序'] || 99) - (+b['建議順序'] || 99));
  const folders = new Map(P.slices.map(x => [x.slice, x]));
  const out = rows.map(r => ({ code: r['切片'], row: r, f: folders.get(r['切片']) }));
  for (const f of P.slices) if (!rows.some(r => r['切片'] === f.slice)) out.push({ code: f.slice, row: null, f });
  return out;
}

function scenario(text) {
  const parts = String(text || '').split(/\s*→\s*/);
  return parts.length > 1 ? `<span class="scn">${parts.map((x, k) => `<span class="${k === 0 ? 'from' : k === parts.length - 1 ? 'to' : 'mid'}">${inline(x)}</span>`).join('<i>→</i>')}</span>` : inline(text);
}

function miniSteps(f) {
  if (!f) return '';
  return `<span class="mini">${f.steps.map(x => `<i class="${x.status.startsWith('已凍結') ? 'frozen' : x.status === '待檢查' ? 'wait' : x.status === '未開始' ? '' : 'draft'}" title="${CIRCLED[x.n]} ${esc(x.name)}：${esc(x.status)}">${CIRCLED[x.n]}</i>`).join('')}</span>`;
}

// 現在整個 domain 輪到誰、做什麼
function nextOfProject(P) {
  const plan = P.plan;
  const ps = P.plan_session;
  if (ps && ps.running) return { kind: 'running', scope: '_plan' };
  if (!plan && !P.topic) return { kind: 'start' };
  if (!plan) return { kind: 'plan-ai' };
  if (!plan.agreed) return { kind: 'plan' };
  const list = planSlices(P);
  const active = list.find(x => x.f && x.f.next && x.f.next.n <= 5);
  if (active) {
    const f = active.f;
    if (f.session && f.session.running) return { kind: 'running', scope: f.slice, item: active };
    return { kind: f.review ? 'review' : 'slice', item: active };
  }
  const nxt = list.find(x => !x.f && x.row && x.row['狀態'] === '候選');
  if (nxt) return { kind: 'pick', item: nxt };
  return { kind: 'done' };
}

async function renderHub() {
  state.slice = null; state.scope = null; state.path = null;
  markNav();
  setTop(null, '');
  const P = await loadProject();
  const N = nextOfProject(P);
  const plan = P.plan;
  const list = planSlices(P);
  const pendingDrafts = P.drafts.filter(d => d.pending).length;
  const toProvide = plan ? plan.inventory.filter(x => x['狀態'] === '待提供').length : 0;
  const pq = plan ? plan.pending.filter(x => x['狀態'] !== '已回覆' && !x['答覆']).length : 0;
  const stage = { start: 0, 'plan-ai': 1, plan: 1, running: N.scope === '_plan' ? 1 : 2, pick: 2, slice: 2, review: 2, done: 3 }[N.kind];
  const journey = ['主題草案', '規劃：資料、切片地圖、名詞', '一條一條切片做 ①～⑤', '設計完成，有系統再做 ⑥'];

  let hero;
  if (N.kind === 'start') hero = `<section class="hero"><div style="flex:999 1 480px;min-width:0"><span class="chip">從這裡開始</span>
      <h1>想做什麼系統？</h1><p>先用幾句話寫下方向：給誰用、要解決什麼、明確不做什麼。不用懂這套流程，AI 會依它問清楚、盤點資料、提出怎麼切。</p></div>
      <a class="btn big yellow" href="#/start">寫主題草案 ›</a></section>`;
  else if (N.kind === 'plan-ai') hero = `<section class="hero idle"><div style="flex:999 1 480px;min-width:0"><span class="chip">輪到 AI</span>
      <h1>主題草案寫好了，請 AI 規劃</h1><p>AI 會盤點這個領域通常有哪些資料（你有的、公開找得到的、只能先推想的），把要做的事切成一條條情境（切片），並列出全局會用到的名詞。</p>
      <p class="muted small">之後輪到你：補資料、看推想草稿、看切片地圖，同意後才開始第一條。</p></div>
      <button class="btn big primary" id="doPlan">請 AI 規劃 ›</button></section>`;
  else if (N.kind === 'running') hero = runningCard(N.scope, N.scope === '_plan' ? 'AI 正在規劃' : `AI 正在做 ${N.scope}`);
  else if (N.kind === 'plan') {
    const parts = [];
    if (pendingDrafts) parts.push(`<strong>${pendingDrafts} 份推想草稿</strong>要你看`);
    if (toProvide) parts.push(`<strong>${toProvide} 份資料</strong>等你提供`);
    if (pq) parts.push(`<strong>${pq} 個待釐清</strong>`);
    hero = `<section class="hero"><div style="flex:999 1 480px;min-width:0"><span class="chip">輪到你</span>
      <h1>看規劃：${plan.slices.length} 條切片、${P.sketch ? P.sketch.nouns.length : 0} 個名詞</h1>
      <p>${parts.length ? parts.join('、') + '；' : ''}看完切片地圖與名詞草圖，有意見就寫，沒問題就同意。</p></div>
      <a class="btn big yellow" href="#/plan">看規劃 ›</a></section>`;
  } else if (N.kind === 'review') {
    const f = N.item.f;
    hero = `<section class="hero"><div style="flex:999 1 480px;min-width:0"><span class="chip">輪到你</span>
      <h1>審查 ${esc(f.slice)} ${esc(stepName(f.review.step))}</h1><p>${scenario(N.item.row ? N.item.row['情境（起點 → 可驗證的結果）'] : '')}</p>
      <p>還有 ${f.review.counts.open} 件事要做。</p></div><a class="btn big yellow" href="#/s/${enc(f.slice)}">去審查 ›</a></section>`;
  } else if (N.kind === 'slice') {
    const f = N.item.f;
    hero = `<section class="hero idle"><div style="flex:999 1 480px;min-width:0"><span class="chip">進行中</span>
      <h1>${esc(f.slice)}：下一關 ${CIRCLED[f.next.n]} ${esc(STEP_INFO[f.next.n][0])}</h1><p>${scenario(N.item.row ? N.item.row['情境（起點 → 可驗證的結果）'] : '')}</p></div>
      <a class="btn big primary" href="#/s/${enc(f.slice)}">打開 ›</a></section>`;
  } else if (N.kind === 'pick') {
    const r = N.item.row;
    hero = `<section class="hero"><div style="flex:999 1 480px;min-width:0"><span class="chip">下一條切片</span>
      <h1>${esc(r['切片'])}</h1><p class="big-scn">${scenario(r['情境（起點 → 可驗證的結果）'])}</p>
      <p class="small">建議順序 ${esc(r['建議順序'])}${r['依賴'] && r['依賴'] !== '—' ? `　依賴：${esc(r['依賴'])}` : ''}</p></div>
      <a class="btn big yellow" href="#/new/${enc(r['切片'])}">開始這一條 ›</a></section>`;
  } else hero = `<section class="card lift celebrate pop"><div class="stars">★ ★ ★</div><h1>地圖上的切片都做完了</h1>
      <p class="muted">有新的情境或需求，到「規劃」補進地圖。</p><a class="btn big" href="#/plan">看規劃</a></section>`;

  const eqTotal = P.slices.reduce((n, x) => n + x.eq_open, 0);
  const started = list.filter(x => x.f), waiting = list.filter(x => !x.f);
  $('#app').innerHTML = `
    <nav class="journey">${journey.map((j, k) => `<div class="${k < stage ? 'done' : k === stage ? 'now' : ''}"><b>${k + 1}</b><span>${esc(j)}</span></div>`).join('')}</nav>
    ${waitingCard('_plan')}
    ${hero}
    ${list.length ? `<section><div class="row spread"><h2 style="margin:0">切片</h2>${plan ? `<a href="#/plan">切片地圖${plan.agreed ? '（已同意）' : '（討論中）'}</a>` : ''}</div>
      ${started.length ? `<div class="slices">${started.map(x => {
        const r = x.row || {};
        const st = x.f.review ? '輪到你審查' : x.f.session && x.f.session.running ? 'AI 進行中' : !x.f.next ? '完成' : x.f.next.n === 6 ? '設計完成（待驗證）' : `下一關 ${CIRCLED[x.f.next.n]}`;
        const sc = r['情境（起點 → 可驗證的結果）'] || '';
        return `<a class="slice ${x.f.review ? 'turn' : ''}" href="#/s/${enc(x.code)}" title="${esc(sc)}">
          <span class="row spread"><b>${esc(x.code)}</b><span class="chip ${x.f.review ? 'turn' : ''}">${esc(st)}</span></span>
          <span class="small clamp3">${scenario(sc)}</span>
          ${miniSteps(x.f)}
          ${x.f.eq_open || x.f.eq_answered ? `<span class="small muted">專家問題：${x.f.eq_open} 題等答覆${x.f.eq_answered ? `、${x.f.eq_answered} 題答覆了待處理` : ''}</span>` : ''}
        </a>`;
      }).join('')}</div>` : ''}
      ${waiting.length ? `<div class="sub-h"><h3>還沒開始（${waiting.length}）</h3><span class="small muted">照建議順序；點一條看地圖上的說明${plan && plan.agreed ? '或開始' : ''}</span></div>
      <ol class="slice-list">${waiting.map((x, k) => {
        const r = x.row || {};
        const href = plan && plan.agreed && r['狀態'] === '候選' ? `#/new/${enc(x.code)}` : '#/plan';
        const sc = r['情境（起點 → 可驗證的結果）'] || '';
        return `<li><a href="${href}" title="${esc(sc)}"><span class="order">${esc(r['建議順序'] || '')}</span><b>${esc(x.code)}</b>
          <span class="chip">${esc(r['狀態'] || '')}</span><span class="scn-1">${esc(sc)}</span></a></li>`;
      }).join('')}</ol>` : ''}</section>` : ''}
    <div class="cols">
      <section class="wide">
        <div class="card"><div class="row spread"><div><div class="label">資料（inputs/）</div>
          <span class="small">${Object.entries(P.inputs).map(([d, fs]) => `${esc(d.replace(/^inputs\/?/, '') || '根目錄')} ${fs.length}`).join('、') || '還沒有資料'}</span></div>
          <button class="btn" id="addInput">加資料</button></div>
          ${P.topic ? `<div class="small" style="margin-top:8px">主題草案：<a class="ref-link" data-file="${esc(P.topic)}" data-line="1">${esc(P.topic)}</a>　<a href="#/start">補充</a></div>` : ''}
        </div>
      </section>
      <section class="side">${eqTotal ? `<div class="card hint"><strong>支線：${eqTotal} 題專家問題等答覆</strong><div class="small">${P.slices.filter(x => x.eq_open).map(x => `<a href="#/eq/${enc(x.slice)}">${esc(x.slice)} ${x.eq_open}</a>`).join('、')}</div></div>` : ''}</section>
    </div>`;
  bindWaiting();
  const dp = $('#doPlan');
  if (dp) dp.onclick = () => runAi('_plan', '規劃', `/domain-plan 主題草案在 ${P.topic}（使用者自己寫的方向）。先盤點現實資料，再提出切片地圖與全局名詞草圖。`);
  const sa = $('#showAi'); if (sa) sa.onclick = () => openAi(N.scope);
  $('#addInput').onclick = () => inputDialog({ folder: 'shared' });
}

// ---------- 主題草案 ----------

const TOPIC_Q = [
  ['想做的系統', '想做什麼系統？一兩句話就好', '例：連鎖飲料店的人資系統，先做請假與特休'],
  ['給誰用', '給誰用？', '例：店長、員工、總部人資'],
  ['要解決什麼', '現在哪裡最痛、要解決什麼？', '例：特休天數常算錯、事後補請假很亂'],
  ['這一階段一定要做到', '這一階段一定要做到什麼？', '例：特休天數正確、到期提醒'],
  ['明確不做', '明確不做什麼？', '例：薪資計算、招募'],
  ['有沒有專家或客戶', '有沒有 Domain 專家或客戶端使用者可以問？是誰？', '例：總部人資主管王小姐，每週可以問一次'],
  ['其他', '其他想讓 AI 知道的（規模、時程、已有的系統）', '例：20 家店、每店 10 人；月初結算'],
];

async function renderStart() {
  state.slice = null; state.scope = '_plan';
  markNav();
  setTop(['#/', '總覽'], '<strong>主題草案</strong>');
  const P = state.project || await loadProject();
  $('#app').innerHTML = `
    <div class="narrow">
      <div><span class="chip">第 1 步</span><h1 class="qtitle">寫下你想做的系統</h1>
        <p class="muted">用自己的話寫，不用專業術語；空著的 AI 之後會用選擇題問。存成 <code>inputs/shared/主題草案.md</code>${P.topic ? '（已經有了，這次寫的會加成一節「補充」，不改舊的）' : ''}。</p></div>
      <section class="card lift" style="display:flex;flex-direction:column;gap:16px">
        ${TOPIC_Q.map(([k, q, ph], i) => `<label class="label" style="color:var(--ink);font-size:16px">${esc(q)}
          ${i === 0 ? `<textarea data-k="${k}" rows="2" placeholder="${esc(ph)}"></textarea>` : `<input type="text" data-k="${k}" class="soft" placeholder="${esc(ph)}">`}</label>`).join('')}
      </section>
      <section class="card">
        <div class="label">手上有的資料（表單、規章、Excel、訪談）</div>
        <p class="small muted" style="margin:0 0 8px">可以現在放，也可以之後。放進來的存在 <code>inputs/shared/</code>，原樣保留。</p>
        <button class="btn" id="addInput">加資料</button>
      </section>
      <div class="row"><button class="btn big primary" id="saveTopic">存好，請 AI 規劃 ›</button><button class="btn big" id="saveOnly">只存起來</button></div>
    </div>`;
  const collect = () => Object.fromEntries($$('[data-k]').map(x => [x.dataset.k, x.value.trim()]));
  const save = async () => {
    const f = collect();
    if (!Object.values(f).some(Boolean)) { toast('至少寫一項'); return null; }
    try { return (await api('/api/topic', { fields: f })).path; } catch (e) { toast(e.message); return null; }
  };
  $('#saveTopic').onclick = async () => {
    const p = await save();
    if (!p) return;
    await loadProject();
    const again = !!(state.project.plan);
    runAi('_plan', '規劃', again
      ? `/domain-plan 使用者在 ${p} 補充了方向（最後一節）。依它更新切片地圖與名詞草圖。`
      : `/domain-plan 主題草案在 ${p}（使用者自己寫的方向）。先盤點現實資料，再提出切片地圖與全局名詞草圖。`);
    go('#/');
  };
  $('#saveOnly').onclick = async () => { if (await save()) { toast('存好了'); go('#/'); } };
  $('#addInput').onclick = () => inputDialog({ folder: 'shared' });
}

// ---------- 加資料（貼上或上傳） ----------

function inputDialog({ folder = 'shared', name = '', hint = '' } = {}) {
  const d = $('#dlg');
  d.innerHTML = `<form method="dialog" class="dlg">
    <h2 style="margin:0">加資料到 <code>inputs/${esc(folder)}/</code></h2>
    ${hint ? `<p class="small muted" style="margin:0">${esc(hint)}</p>` : ''}
    <label class="label" style="color:var(--ink)">名稱<input type="text" id="inName" value="${esc(name)}" placeholder="例：到職檢核表、店長訪談 10-28"></label>
    <label class="label" style="color:var(--ink)">貼上文字（訪談、規章、需求…）<textarea id="inText" rows="8"></textarea></label>
    <label class="label" style="color:var(--ink)">或上傳檔案（Excel、PDF、圖片，原樣保存）<input type="file" id="inFile"></label>
    <div class="row"><button class="btn primary" id="inSave" value="save">存起來</button><button class="btn" value="cancel">取消</button></div>
  </form>`;
  d.showModal();
  $('#inSave').onclick = async e => {
    e.preventDefault();
    const file = $('#inFile').files[0];
    const nm = $('#inName').value.trim() || (file && file.name) || '';
    try {
      let r;
      if (file) {
        const buf = new Uint8Array(await file.arrayBuffer());
        let bin = '';
        for (let i = 0; i < buf.length; i += 0x8000) bin += String.fromCharCode(...buf.subarray(i, i + 0x8000));
        const ext = file.name.includes('.') ? file.name.slice(file.name.lastIndexOf('.')) : '';
        r = await api('/api/inputs', { folder, name: nm.endsWith(ext) ? nm : nm + ext, b64: btoa(bin) });
      } else {
        if (!nm) { toast('寫個名稱'); return; }
        r = await api('/api/inputs', { folder, name: nm, text: $('#inText').value });
      }
      d.close();
      toast(`存好了：${r.path}`);
      if (state.onInput) state.onInput(r.path, nm);
      route();
    } catch (err) { toast(err.message); }
  };
}

// ---------- 規劃：資料、草稿、切片地圖、名詞草圖 ----------
// 人的意見先放進「回饋籃」，一次交給 AI 改（不一條一條打斷 AI）

function basket(scope) { try { return JSON.parse(remember('fb:' + scope) || '[]'); } catch (e) { return []; } }
function setBasket(scope, items) { remember('fb:' + scope, JSON.stringify(items)); renderBasket(scope); }
function addFeedback(scope, text) { const b = basket(scope); b.push(text); setBasket(scope, b); toast('放進回饋了，看完再一起交給 AI'); }

function renderBasket(scope) {
  const el = $('#basket');
  if (!el) return;
  const items = basket(scope);
  el.hidden = !items.length;
  el.innerHTML = `<div class="row spread"><strong>你的回饋（${items.length}）</strong><button class="btn primary" id="sendFb">交給 AI 修改 ›</button></div>
    <ol>${items.map((x, k) => `<li>${esc(x)} <button class="x-del" data-del="${k}" aria-label="刪除">✕</button></li>`).join('')}</ol>`;
  $$('[data-del]', el).forEach(b => b.onclick = () => { const it = basket(scope); it.splice(+b.dataset.del, 1); setBasket(scope, it); });
  $('#sendFb').onclick = () => {
    const msg = `/domain-plan 使用者看了切片地圖、名詞草圖與資料盤點，回饋如下（逐條處理，改了的記 slices/CHANGELOG.md；答覆待釐清的照格式填寫）：\n` + items.map((x, k) => `${k + 1}. ${x}`).join('\n');
    setBasket(scope, []);
    runAi('_plan', '規劃', msg);
  };
}

function fbButton(text, label = '寫意見') { return `<button class="btn small-btn" data-fb="${esc(text)}">${label}</button>`; }

function bindFb() {
  $$('[data-fb]').forEach(b => b.onclick = () => {
    const host = b.closest('.fb-host') || b.parentElement;
    if ($('.note-box', host)) return;
    host.insertAdjacentHTML('beforeend', `<div class="note-box row"><input type="text" style="flex:1" placeholder="寫一句，按 Enter"><button class="btn primary">放進回饋</button></div>`);
    const inp = $('.note-box input', host);
    inp.focus();
    const save = () => { const v = inp.value.trim(); if (!v) return; addFeedback('_plan', `${b.dataset.fb}：${v}`); $('.note-box', host).remove(); };
    $('.note-box button', host).onclick = save;
    inp.onkeydown = e => { if (e.key === 'Enter') save(); };
  });
}

const INV_CLASS = { '已有': 'ok', '已蒐集': 'ok', '推想草稿': 'guess', '待提供': 'need', '找不到': 'none' };

async function renderPlan() {
  state.slice = null; state.scope = '_plan';
  markNav();
  setTop(['#/', '總覽'], '<strong>規劃</strong>');
  const P = await loadProject();
  const plan = P.plan;
  if (!plan) { $('#app').innerHTML = runningCard('_plan', 'AI 正在規劃') || `<div class="card">還沒有切片地圖。<a href="#/">回總覽</a>請 AI 規劃。</div>`; const sa = $('#showAi'); if (sa) sa.onclick = openAi; return; }
  const sk = P.sketch;
  const drafts = P.drafts;
  const pendingDrafts = drafts.filter(d => d.pending);
  const name = remember('reviewer');
  const byLayer = {};
  for (const n of (sk ? sk.nouns : [])) (byLayer[n['層'] || '其他'] = byLayer[n['層'] || '其他'] || []).push(n);
  const aiDecisions = plan.decisions.filter(d => /待確認/.test(d['提出／同意'] || ''));
  const blockers = [];
  if (pendingDrafts.length) blockers.push(`${pendingDrafts.length} 份推想草稿還沒接受`);
  if (basket('_plan').length) blockers.push('回饋還沒交給 AI');
  const running = sessionOf('_plan') && sessionOf('_plan').running;

  $('#app').innerHTML = `
    ${runningCard('_plan', 'AI 正在改規劃')}
    ${waitingCard('_plan')}
    <div class="row spread"><div><span class="chip ${plan.agreed ? 'new' : ''}">${esc(plan.status || '討論中')}</span>
      <h1 style="margin:8px 0 0">規劃</h1><p class="muted small clamp2" style="margin:6px 0 0;max-width:46em" title="${esc(plan.basis)}">${esc(plan.basis)}</p></div>
      <nav class="tabs"><button data-jump="p-data">資料</button><button data-jump="p-map">切片地圖</button><button data-jump="p-nouns">名詞</button><button data-jump="p-ask">待釐清與決定</button></nav></div>

    <section class="card fb-host"><div class="label">方向（整體目標）</div>
      <ul class="goals">${plan.goals.map(g => `<li>${inline(g)}</li>`).join('')}</ul>
      <div class="row">${fbButton('整體目標')}<a class="btn small-btn" href="#/start">補充主題草案</a></div></section>

    <section id="p-data"><h2>1　現實資料</h2>
      <p class="muted small">AI 先列出這個領域通常有哪些資料。綠色是有了；黃色是 AI 推想的，要你看過、接受才能當假設用；橘色等你提供。</p>
      ${(() => {
        const draftOf = x => { const loc = x['位置'] && x['位置'] !== '—' ? x['位置'] : ''; return drafts.find(dd => loc && loc.includes(dd.path.replace(/^inputs\//, ''))); };
        const todo = plan.inventory.filter(x => x['狀態'] === '待提供' || (draftOf(x) || {}).pending);
        const rest = plan.inventory.filter(x => !todo.includes(x));
        const card = x => {
          const st = x['狀態'];
          const loc = x['位置'] && x['位置'] !== '—' ? x['位置'] : '';
          const d = draftOf(x);
          return `<div class="inv-item ${INV_CLASS[st] || ''} fb-host">
            <div class="what"><div><b>${esc(x['資料'])}</b><span class="chip">${esc(st)}</span></div>
            <div class="small muted">${inline(x['內容'] || '')}</div>
            ${loc ? `<div class="small muted">${loc.includes('/') ? `<a class="ref-link" data-file="${esc(loc.replace(/[\s、，].*$/, ''))}" data-line="1">${esc(loc)}</a>` : esc(loc)}</div>` : ''}</div>
            <div class="row">
              ${st === '待提供' ? `<button class="btn small-btn go" data-give="${esc(x['資料'])}">我有，放進來</button>${fbButton(`資料「${x['資料']}」`, '沒有／說明')}` : ''}
              ${d ? `<a class="btn small-btn yellow" href="#/draft/${enc(d.path)}">看草稿、決定接不接受</a>` : ''}
            </div></div>`;
        };
        const line = x => {
          const d = draftOf(x);
          return `<li class="fb-host"><span class="chip ${INV_CLASS[x['狀態']] === 'ok' ? 'new' : ''}">${esc(x['狀態'])}</span> <b>${esc(x['資料'])}</b> <span class="small muted">${inline(x['內容'] || '')}</span>
            ${d ? `<a class="small" href="#/draft/${enc(d.path)}">看草稿（${esc(d.status.replace(/（.*/, ''))}）</a>` : ''} ${fbButton(`資料「${x['資料']}」`)}</li>`;
        };
        return `${todo.length ? `<div class="inv">${todo.map(card).join('')}</div>` : '<p class="small">資料都處理過了（沒有待提供、待接受的）。</p>'}
          ${rest.length ? `<details class="card inv-rest" ${todo.length ? '' : 'open'}><summary><b>已有或已處理的資料（${rest.length}）</b></summary><ul>${rest.map(line).join('')}</ul></details>` : ''}`;
      })()}
      ${drafts.filter(d => !plan.inventory.some(x => (x['位置'] || '').includes(d.path.replace(/^inputs\//, '')))).map(d => `<a class="small" href="#/draft/${enc(d.path)}">${esc(d.title)}（${esc(d.status)}）</a>`).join('　')}
      <div class="row" style="margin-top:10px"><button class="btn" id="addInput">加其他資料</button></div>
    </section>

    <section id="p-map"><h2>2　切片地圖</h2>
      <p class="muted small">一條切片＝一個情境，從起點走到一個可以驗證的結果。照建議順序一條一條做，第一條通常是正常流程，用來建立共用的名詞。</p>
      <div class="map">${planSlices(P).filter(x => x.row).map((x, k) => {
        const r = x.row;
        const guess = /推想/.test(r['依據'] || '');
        return `<div class="map-item fb-host">
          <div class="row spread"><span><span class="order">${esc(r['建議順序'] || k + 1)}</span> <b>${esc(r['切片'])}</b></span>
            <span class="row" style="gap:6px"><span class="chip ${/^太大/.test(r['大小估計'] || '') ? 'turn' : ''}" title="${esc(r['大小估計'] || '')}">${esc((r['大小估計'] || '').replace(/（.*$/, ''))}${/（/.test(r['大小估計'] || '') ? ' …' : ''}</span><span class="chip">${esc(r['狀態'])}</span></span></div>
          <div class="big-scn">${scenario(r['情境（起點 → 可驗證的結果）'])}</div>
          <div class="small muted">${esc(r['主要領域'] || '')}${r['會碰到的領域'] && r['會碰到的領域'] !== '—' ? '；也會碰到 ' + esc(r['會碰到的領域']) : ''}${r['依賴'] && r['依賴'] !== '—' ? '　依賴：' + esc(r['依賴']) : ''}</div>
          <details class="small muted"><summary style="cursor:pointer">依據${guess ? ' <span class="chip guess-chip">推想</span>' : ''}</summary><div style="margin-top:6px">${inline(r['依據'] || '')}</div></details>
          <div class="row">${fbButton(`切片 ${r['切片']}`)}</div></div>`;
      }).join('')}</div>
    </section>

    <section id="p-nouns"><h2>3　全局名詞草圖</h2>
      <p class="muted small">所有切片會用到的名詞，先看全局，避免第一條切片把共用的名詞定得太窄。這裡只是草圖，正式定義在每條切片的第 ② 步。</p>
      ${sk ? `<details ${plan.agreed ? '' : 'open'}><summary class="small" style="cursor:pointer;margin-bottom:8px">${sk.nouns.length} 個名詞${plan.agreed ? '（地圖已同意，點開看）' : ''}</summary><div class="layers">${['core', 'shared', 'domain', ...Object.keys(byLayer).filter(k => !['core', 'shared', 'domain'].includes(k))].filter(k => byLayer[k]).map(k => `
        <div class="layer-col"><div class="label">${{ core: 'core：大家共用', shared: 'shared：幾個領域共用', domain: 'domain：這個領域自己的' }[k] || esc(k)}</div>
          ${byLayer[k].map(n => `<div class="noun fb-host"><b>${esc(n['名詞'])}</b><div class="small">${inline(n['一句意思'] || '')}</div>
            <div class="small muted">${n['主要關係'] ? '關係：' + esc(n['主要關係']) + '　' : ''}由 ${esc(n['正式定義於'] || '?')} 定義${/推想/.test(n['依據'] || '') ? '　<span class="chip guess-chip">推想</span>' : ''}</div>
            ${fbButton(`名詞 ${n['名詞']}`)}</div>`).join('')}</div>`).join('')}</div></details>
        ${sk.unsure.length ? `<div class="card hint fb-host" style="margin-top:12px"><b>AI 拿不準的地方</b><ul>${sk.unsure.map(u => `<li>${inline(u)}</li>`).join('')}</ul>${fbButton('名詞草圖不確定的地方', '回答')}</div>` : ''}`
      : '<div class="card dashed">還沒有名詞草圖。</div>'}
    </section>

    <section id="p-ask"><h2>4　待釐清與 AI 的決定</h2>
      ${plan.pending.length ? plan.pending.map(q => `<div class="card fb-host" style="margin-bottom:10px">
        <div class="row spread"><b>${esc(q['編號'])}　${inline(q['問題'])}</b><span class="chip">${esc(q['狀態'])}</span></div>
        <div class="small muted">問誰：${esc(q['問誰'] || '')}${q['答覆'] ? '　答覆：' + inline(q['答覆']) : ''}</div>
        ${q['答覆'] ? '' : `<div class="row" style="margin-top:6px">${fbButton(`待釐清 ${q['編號']}（${q['問題']}）的答覆`, '我知道答案')}</div>`}</div>`).join('') : '<p class="muted small">沒有待釐清的問題。</p>'}
      ${aiDecisions.length ? `<div class="label" style="margin-top:12px">AI 提出、還沒有人同意的決定</div>${aiDecisions.map(d => `<div class="card fb-host" style="margin-bottom:10px">
        <b>${esc(d['#'])}　${inline(d['決定'])}</b><div class="small">理由：${inline(d['理由'] || '')}${d['考慮過的替代做法'] ? '　沒選：' + inline(d['考慮過的替代做法']) : ''}</div>
        <div class="row" style="margin-top:6px"><button class="btn small-btn go" data-agree="${esc(d['#'])}">同意</button>${fbButton(`決定 ${d['#']}`, '不同意，寫理由')}</div></div>`).join('')}` : ''}
    </section>

    <section class="card lift agree">
      <h2 style="margin:0">都看過了？</h2>
      <p class="muted" style="margin:4px 0 10px">同意後，切片地圖與名詞草圖改為「已同意」，就可以開始第一條切片。之後有新資料、新情境，隨時可以回來改。</p>
      ${blockers.length ? `<div class="small" style="margin-bottom:8px">還不能同意：${blockers.join('、')}。</div>` : ''}
      <div class="row"><input type="text" id="who" value="${esc(name)}" placeholder="你的名字" style="max-width:220px">
        <button class="btn big go" id="agree" ${blockers.length || plan.agreed || running ? 'disabled' : ''}>${plan.agreed ? '已同意' : '同意切片地圖與名詞草圖'}</button></div>
    </section>
    <aside class="basket card lift" id="basket" hidden></aside>`;
  renderBasket('_plan');
  bindFb();
  bindWaiting();
  $$('[data-jump]').forEach(b => b.onclick = () => document.getElementById(b.dataset.jump).scrollIntoView({ behavior: 'smooth' }));
  const sa = $('#showAi'); if (sa) sa.onclick = openAi;
  $('#addInput').onclick = () => inputDialog({ folder: 'shared' });
  $$('[data-give]').forEach(b => b.onclick = () => {
    state.onInput = (path) => addFeedback('_plan', `資料「${b.dataset.give}」已提供：${path}`);
    inputDialog({ folder: 'shared', name: b.dataset.give, hint: `AI 列的「${b.dataset.give}」。存好後會放進回饋，交給 AI 時它會改盤點表的狀態與位置。` });
  });
  $$('[data-agree]').forEach(b => b.onclick = () => { addFeedback('_plan', `同意決定 ${b.dataset.agree}（${$('#who').value.trim() || '使用者'}，${today()}）`); b.disabled = true; });
  $('#agree').onclick = () => {
    const who = $('#who').value.trim();
    if (!who) { toast('寫你的名字'); return; }
    remember('reviewer', who);
    runAi('_plan', '規劃', `我同意切片地圖與全局名詞草圖（同意者：${who}，${today()}）。請照 domain-plan 第 4 節把兩份狀態改為「已同意（${who}，${today()}）」，記 slices/CHANGELOG.md，然後告訴我下一步要開始哪條切片。`);
  };
}

// ---------- 推想草稿 ----------

async function renderDraft(path) {
  state.slice = null; state.scope = '_plan';
  setTop(['#/plan', '規劃'], '<strong>推想草稿</strong>');
  const f = await api('/api/file?path=' + enc(path));
  const P = state.project || await loadProject();
  const d = P.drafts.find(x => x.path === path) || {};
  const name = remember('reviewer');
  const body = f.text.split(/^## 內容\s*$/m);
  $('#app').innerHTML = `
    <div class="narrow">
      <div><span class="chip ${d.pending ? 'turn' : 'new'}">${esc(d.status || '')}</span><h1 class="qtitle">${esc(d.title || path)}</h1>
        <p class="muted">這是 AI 依一般知識寫的，<b>不是</b>你們的實際做法。判斷標準：這個一般做法大致對嗎、能不能先當假設用？不用逐句確認；有了真實資料會取代它。</p></div>
      ${d.unsure ? `<section class="card hint"><b>AI 最不確定的地方：</b>${inline(d.unsure)}${d.who ? `<div class="small">需要誰確認：${inline(d.who)}</div>` : ''}</section>` : ''}
      <section class="card lift draft-body">${md(body.length > 1 ? body[1] : f.text)}</section>
      ${d.pending ? `<section class="card fb-host" style="display:flex;flex-direction:column;gap:10px">
        <div class="row"><input type="text" id="who" value="${esc(name)}" placeholder="你的名字" style="max-width:220px">
          <button class="btn big go" id="accept">大致對，先當假設用</button></div>
        <div class="row">${fbButton(`推想草稿 ${d.title}`, '有地方不對，寫意見')}</div>
        <div class="small muted">接受不代表內容已確認；法條數字仍待核對。</div></section>` : ''}
      <details class="tech"><summary>原始檔</summary><a class="ref-link" data-file="${esc(path)}" data-line="1">${esc(path)}</a></details>
    </div>
    <aside class="basket card lift" id="basket" hidden></aside>`;
  renderBasket('_plan');
  bindFb();
  const ac = $('#accept');
  if (ac) ac.onclick = async () => {
    const who = $('#who').value.trim();
    if (!who) { toast('寫你的名字'); return; }
    remember('reviewer', who);
    try {
      await api('/api/draft/accept', { path, who, digest: f.digest });
      toast('已接受為假設');
      await loadProject();
      const nxt = state.project.drafts.find(x => x.pending);
      go(nxt ? `#/draft/${enc(nxt.path)}` : '#/plan');
    } catch (e) { toast(e.message); }
  };
}

// ---------- 開始一條切片 ----------

async function renderKickoff(code) {
  state.slice = null; state.scope = code;
  setTop(['#/', '總覽'], `<strong>開始 ${esc(code)}</strong>`);
  const P = await loadProject();
  const r = (P.plan ? P.plan.slices : []).find(x => x['切片'] === code) || {};
  if (P.slices.some(x => x.slice === code)) { go(`#/s/${enc(code)}`); return; }
  const qs = [
    ['不做', '這條切片明確不做什麼？', '例：兼職人員先不處理'],
    ['專家', '有沒有 Domain 專家或客戶端使用者可以確認？是誰？', '例：總部人資王小姐'],
    ['替代', '依賴、但這次不實作的東西，先用什麼代替？', '例：班表先用固定的週一到週五'],
    ['資料', '還有沒有訪談紀錄、既有 User Story？（沒有也可以）', '可以用下面的「加資料」放進來'],
  ];
  $('#app').innerHTML = `
    <div class="narrow">
      <div><span class="chip">開始一條切片</span><h1 class="qtitle">${esc(code)}</h1>
        <p class="big-scn">${scenario(r['情境（起點 → 可驗證的結果）'] || '')}</p>
        <p class="muted">開工前先回答幾件事（知道的就寫，不知道空著）。AI 會建立切片資料夾，接著做第 ① 步：範圍與驗收問題。</p></div>
      <section class="card lift" style="display:flex;flex-direction:column;gap:14px">
        ${qs.map(([k, q, ph]) => `<label class="label" style="color:var(--ink);font-size:16px">${esc(q)}<input type="text" class="soft" data-k="${k}" placeholder="${esc(ph)}"></label>`).join('')}
        <div><button class="btn" id="addInput">加資料（放進 inputs/${esc(code)}/）</button></div>
      </section>
      <div class="row"><button class="btn big primary" id="go1">開始 ›</button></div>
    </div>`;
  $('#addInput').onclick = () => inputDialog({ folder: code });
  $('#go1').onclick = () => {
    const a = Object.fromEntries($$('[data-k]').map(x => [x.dataset.k, x.value.trim()]));
    const lines = qs.map(([k, q]) => `- ${q}${a[k] || '（使用者沒寫）'}`).join('\n');
    runAi(code, '第 1 步', `/domain-new-slice ${code}\n\n使用者在網頁上先回答了開工的問題（原話，存成 inputs/${code}/ 的檔案時照抄）：\n${lines}\n\n建立好就接著做第 ① 步。`);
    setTimeout(() => go('#/'), 300);
  };
}

// ---------- 專家問題 ----------

async function renderEq(slice) {
  state.slice = slice; state.scope = slice;
  markNav();
  setTop([`#/s/${enc(slice)}`, slice], '<strong>專家問題</strong>');
  const h = await api('/api/home?slice=' + enc(slice));
  const f = await api(`/api/file?path=${enc(`slices/${slice}/questions.md`)}`);
  const order = { '待問': 0, '已問': 1, '暫依整理': 2, '已回覆': 3 };
  const eqs = h.eqs.slice().sort((a, b) => (order[a['狀態']] ?? 9) - (order[b['狀態']] ?? 9));
  const toAsk = eqs.filter(e => e['狀態'] === '待問');
  $('#app').innerHTML = `
    <div><h1 style="margin:0">專家問題</h1><p class="muted" style="margin:4px 0 0">AI 答不了、要問 Domain 專家或客戶的事。不擋關卡：相關的地方先標「待專家確認」，答覆回來再交給 AI 回頭改。</p></div>
    ${toAsk.length ? `<div class="row"><button class="btn primary" id="copyAll">複製 ${toAsk.length} 題待問的（給專家）</button></div>` : ''}
    <div class="eqs">${eqs.map(e => {
      const st = e['狀態'];
      return `<section class="card eq ${st === '待問' ? 'need' : st === '已回覆' ? 'ok' : ''}" data-line="${e.line}">
        <div class="row spread"><b>${esc(e['編號'])}</b><span class="chip ${st === '待問' ? 'turn' : st === '已回覆' ? 'new' : ''}">${esc(st)}</span></div>
        <div class="eq-q">${inline(e['問題（業務語言）'] || e['問題'] || '')}</div>
        <div class="small muted">問誰：${esc(e['問誰'] || '')}　提出於 ${esc(e['提出於'] || '')}</div>
        ${e['答覆'] ? `<div class="box"><div class="label">答覆（${esc(e['答覆日'] || '')}）</div>${inline(e['答覆'])}</div>` : ''}
        ${e['影響'] ? `<details class="tech"><summary>影響哪些地方</summary>${inline(e['影響'])}</details>` : ''}
        <div class="row">
          ${st === '待問' ? `<button class="btn small-btn" data-copy="${e.line}">複製這題</button><button class="btn small-btn go" data-asked="${e.line}">我問了</button>` : ''}
          ${st === '已問' || st === '暫依整理' || st === '待問' ? `<button class="btn small-btn primary" data-reply-eq="${esc(e['編號'])}">專家回覆了</button>` : ''}
          ${st === '已回覆' && !e['處理'] ? `<button class="btn small-btn primary" data-handle="${esc(e['編號'])}">交給 AI 處理</button>` : ''}
          ${e['處理'] ? `<span class="small">處理：${inline(e['處理'])}</span>` : ''}
        </div></section>`;
    }).join('') || '<div class="card dashed">沒有專家問題。</div>'}</div>`;
  const qText = e => `${e['編號']}：${e['問題（業務語言）'] || e['問題'] || ''}`;
  const copy = t => navigator.clipboard.writeText(t).then(() => toast('已複製（不含 AI 的建議答案）'), () => toast('複製失敗'));
  const ca = $('#copyAll'); if (ca) ca.onclick = () => copy(toAsk.map(qText).join('\n\n'));
  $$('[data-copy]').forEach(b => b.onclick = () => copy(qText(eqs.find(e => e.line === +b.dataset.copy))));
  $$('[data-asked]').forEach(b => b.onclick = async () => {
    try { await api('/api/eq/asked', { slice, line: +b.dataset.asked, digest: f.digest }); renderEq(slice); } catch (e) { toast(e.message); }
  });
  $$('[data-handle]').forEach(b => b.onclick = () => runAi(slice, '專家回覆', `/domain-expert-reply ${b.dataset.handle}`));
  $$('[data-reply-eq]').forEach(b => b.onclick = () => {
    const id = b.dataset.replyEq;
    const host = b.closest('.eq');
    if ($('.note-box', host)) return;
    host.insertAdjacentHTML('beforeend', `<div class="note-box" style="display:flex;flex-direction:column;gap:8px">
      <textarea rows="4" placeholder="貼上專家的原話（照抄，不要改寫）"></textarea>
      <div class="row"><input type="text" class="soft" placeholder="誰回答的、怎麼回的（例：王小姐，Line）" style="flex:1"><button class="btn primary">存起來，交給 AI</button></div></div>`);
    const [ta, who] = [$('.note-box textarea', host), $('.note-box input', host)];
    ta.focus();
    $('.note-box button', host).onclick = async () => {
      const v = ta.value.trim();
      if (!v) { toast('貼上答覆'); return; }
      try {
        const r = await api('/api/inputs', { folder: slice, name: `專家答覆_${id}_${today()}`, text: `- 問題：${id}\n- 回答者：${who.value.trim() || '（沒寫）'}\n\n${v}` });
        runAi(slice, '專家回覆', `/domain-expert-reply ${id} 專家答覆原文已存成 ${r.path}（照抄，不改寫）。`);
      } catch (e) { toast(e.message); }
    };
  });
}

// ---------- 路由 ----------
// #/ 總覽　#/start 主題草案　#/plan 規劃　#/draft/<檔> 推想草稿　#/new/<切片> 開始切片　#/eq/<切片> 專家問題
// #/s/<切片> 切片首頁　#/r/<審查頁>/decide/<n>　/confirm[/<Entity>]　/golden/<n>　/finish

async function route() {
  $('#fileDrawer').hidden = true;
  const parts = location.hash.replace(/^#\/?/, '').split('/').map(decodeURIComponent);
  try {
    if (parts[0] === 's' && parts[1]) return await renderHome(parts[1]);
    if (parts[0] === 'r' && parts[1]) {
      const path = parts[1];
      const m = path.match(/^slices\/([^/]+)\//);
      if (m) { state.slice = m[1]; state.scope = m[1]; markNav(); renderAiHead(); }
      if (state.path !== path) await loadReview(path);
      const view = parts[2] || 'decide';
      if (view === 'decide') return await renderDecide(path, +parts[3] || 0);
      if (view === 'confirm') return await renderConfirm(path, parts[3] || null);
      if (view === 'golden') return await renderGolden(path, +parts[3] || 0);
      return await renderFinish(path);
    }
    state.path = null;
    if (parts[0] === 'start') return await renderStart();
    if (parts[0] === 'plan') return await renderPlan();
    if (parts[0] === 'draft' && parts[1]) return await renderDraft(parts.slice(1).join('/'));
    if (parts[0] === 'new' && parts[1]) return await renderKickoff(parts[1]);
    if (parts[0] === 'eq' && parts[1]) return await renderEq(parts[1]);
    if (parts[0] === 'f' && parts[1]) return await renderFile(parts.slice(1).join('/'));
    return await renderHub();
  } catch (e) { toast(e.message); } finally { refreshNav(); }
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
$('#navBtn').onclick = () => setNav(true);
$('#navClose').onclick = () => setNav(false);
document.addEventListener('keydown', e => { if (e.ctrlKey && e.key === '\\') { e.preventDefault(); setNav(document.body.classList.contains('nav-closed')); } });
$('#sideNav').addEventListener('click', e => { if (narrow() && e.target.closest('a.nav-a')) setNav(false); });
$('#app').addEventListener('click', () => { if (narrow() && !document.body.classList.contains('nav-closed')) setNav(false); });
try { if (narrow() || localStorage.getItem('nav-closed')) document.body.classList.add('nav-closed'); } catch (e) { if (narrow()) document.body.classList.add('nav-closed'); }
syncNav();
const fitTop = () => document.documentElement.style.setProperty('--top-h', $('.top').offsetHeight + 'px');
window.addEventListener('resize', fitTop); fitTop();
$('#aiForm').onsubmit = e => {
  e.preventDefault();
  const v = $('#aiInput').value.trim();
  if (!v) return;
  if (!state.scope) { toast('先打開一條切片或規劃，再和 AI 對話'); return; }
  $('#aiInput').value = '';
  const s = curSession();
  runAi(state.scope, s ? s.purpose : '對話', v, { keep: true });
};
window.addEventListener('hashchange', route);

refreshSlices().then(route).catch(e => toast(e.message));
