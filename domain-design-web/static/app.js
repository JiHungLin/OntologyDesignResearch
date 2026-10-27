// Domain 設計審查（第一版）：讀寫審查頁、查閱檔案、透過 session 交給 AI。
'use strict';

const $ = (s, el = document) => el.querySelector(s);
const state = { status: null, review: null, path: null, tab: 'q', qi: 0, sessionChoice: null };

async function api(url, opts = {}) {
  const r = await fetch(url, opts.body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(opts.body) } : opts);
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

// 行內格式：`code`，以及「檔名:行號」做成可以點開側欄的連結
const FILE_REF = /`?([^\s`「」（）()、，<>]+?\.(?:md|ya?ml|js|sql|py)):(\d+)`?/g;
function inline(s) {
  let h = esc(s);
  h = h.replace(FILE_REF, (m, f, n) => `<a class="ref-link" data-file="${f}" data-line="${n}">${f}:${n}</a>`);
  h = h.replace(/`([^`]+)`/g, '<code>$1</code>');
  return h;
}

function today() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function toast(msg) {
  const log = $('#aiLog');
  log.insertAdjacentHTML('beforeend', `<div class="err">${esc(msg)}</div>`);
  openAi(true);
}

// ---------- 左邊：切片與審查頁 ----------

async function loadStatus() {
  state.status = await api('/api/status');
  $('#repo').textContent = state.status.repo;
  const nav = $('#nav');
  let h = '';
  if (!state.status.gitignored) {
    h += `<div class="warn">切片 repo 的 <code>.gitignore</code> 沒有排除 <code>.domain-web/</code>（session 登記表放在這裡），請加上一行 <code>.domain-web/</code>。</div>`;
  }
  for (const s of state.status.slices) {
    h += `<h3>${esc(s.slice)}</h3>`;
    if (!s.reviews.length) h += `<div class="hint">（沒有審查頁）</div>`;
    for (const r of s.reviews) {
      const open = r.counts ? r.counts.open : '?';
      const badge = open === 0 ? '<span class="badge done">✓</span>' : `<span class="badge">${open}</span>`;
      h += `<a href="#${encodeURIComponent(r.path)}" class="${r.path === state.path ? 'on' : ''}" title="${esc(r.title)}"><span>${esc(r.date)}　${esc(r.step)}</span>${badge}</a>`;
    }
  }
  nav.innerHTML = h;
}

// ---------- 中間：審查頁 ----------

async function openReview(path, keepTab) {
  state.path = path;
  state.review = await api('/api/review?path=' + encodeURIComponent(path));
  if (!keepTab) {
    const c = state.review.counts;
    state.tab = c.questions_open ? 'q' : c.confirms_open ? 'c' : !c.spot_done ? 's' : 'r';
    state.qi = Math.max(0, state.review.questions.findIndex(q => !q.answer.trim()));
  }
  render();
  loadStatus();
  renderAi();
}

function render() {
  const r = state.review;
  const c = r.counts;
  const main = $('#main');
  const golden = r.golden && !/^（這輪沒有）$/.test(r.golden.trim());
  const tabs = [
    ['q', '要你回答', c.questions_open],
    ['c', '要你確認', c.confirms_open],
    golden ? ['g', '黃金案例', ''] : null,
    ['s', '抽查', c.spot_done ? 0 : 1],
    ['r', '結論與交給 AI', c.conclusion_done ? 0 : 1],
  ].filter(Boolean);
  main.innerHTML = `
    <h2>${esc(r.title)}</h2>
    <details class="meta"><summary>這輪的範圍、起因、挑錯與核對</summary>${r.meta.map(m => `<div><b>${esc(m.key)}</b>　${inline(m.value)}</div>`).join('')}</details>
    ${r.problems.length ? `<div class="problems">審查頁有看不懂的列：${r.problems.map(esc).join('；')}</div>` : ''}
    <div class="tabs">${tabs.map(([k, label, n]) => `<button data-tab="${k}" class="${state.tab === k ? 'on' : ''}">${label}${n ? `<span class="n">${n}</span>` : ''}</button>`).join('')}</div>
    <div id="pane"></div>`;
  ({ q: renderQuestions, c: renderConfirms, g: renderGolden, s: renderSpot, r: renderConclusion })[state.tab]($('#pane'));
}

function renderQuestions(pane) {
  const qs = state.review.questions;
  if (!qs.length) { pane.innerHTML = '<p class="hint">這輪沒有要你回答的問題。</p>'; return; }
  const i = Math.min(state.qi, qs.length - 1);
  const q = qs[i];
  const ans = q.answer.trim();
  const chosen = /^[A-Z]$/.test(ans) ? ans : null;
  pane.innerHTML = `
    <div class="card">
      <div class="ref">問題 ${q.n}${q.ref ? `（${esc(q.ref)}）` : ''}${q.section && !q.section.startsWith('一') ? `　· ${esc(q.section)}` : ''}</div>
      ${q.background ? `<div class="bg">${inline(q.background)}</div>` : ''}
      <div class="q">${inline(q.question)}</div>
      ${q.options.map(o => `<button class="opt ${chosen === o.key ? 'on' : ''}" data-opt="${o.key}"><span class="k">${o.key}</span>${o.recommended ? '<span class="rec">建議</span>' : ''}　${inline(o.text)}</button>`).join('')}
      <div class="other">
        <input id="otherInput" placeholder="其他：寫一句" value="${chosen || !ans ? '' : esc(ans)}">
        <button class="btn" id="otherSave">送出</button>
      </div>
    </div>
    <div class="pager">
      <button id="prevQ" ${i === 0 ? 'disabled' : ''}>← 上一題</button>
      <div class="dots">${qs.map((x, k) => `<span data-q="${k}" class="${x.answer.trim() ? 'done' : ''} ${k === i ? 'cur' : ''}" title="問題 ${x.n}"></span>`).join('')}</div>
      <button id="nextQ" ${i === qs.length - 1 ? 'disabled' : ''}>下一題 →</button>
    </div>`;
  const save = async v => {
    try {
      const r = await api('/api/review/answer', { body: { path: state.path, digest: state.review.digest, line: q.answer_line, value: v } });
      state.review.digest = r.digest;
      q.answer = v;
      const next = qs.findIndex((x, k) => k > i && !x.answer.trim());
      await openReview(state.path, true);
      state.qi = next >= 0 ? next : i;
      render();
    } catch (e) { toast(e.message); }
  };
  pane.querySelectorAll('[data-opt]').forEach(b => b.onclick = () => save(b.dataset.opt));
  $('#otherSave', pane).onclick = () => { const v = $('#otherInput', pane).value.trim(); if (v) save(v); };
  $('#prevQ', pane).onclick = () => { state.qi = i - 1; render(); };
  $('#nextQ', pane).onclick = () => { state.qi = i + 1; render(); };
  pane.querySelectorAll('[data-q]').forEach(d => d.onclick = () => { state.qi = +d.dataset.q; render(); });
}

// 「要看的」冒號前面當成分組（例：「會進 core 的 Entity 清單（新增 1/4）」→「會進 core 的 Entity 清單」）
function groupOf(what) {
  const head = what.split('：')[0];
  return head.replace(/（[^）]*\d+\/\d+[^）]*）/, '').trim();
}

function renderConfirms(pane) {
  const cs = state.review.confirms;
  if (!cs.length) { pane.innerHTML = '<p class="hint">這輪沒有要你確認的內容。</p>'; return; }
  let h = '<p class="hint">右邊打 ✓，或寫一句意見。點「在哪裡」會在右側打開檔案。</p>';
  let last = null;
  for (const c of cs) {
    const what = c.cells['要看的'] || '';
    const g = groupOf(what);
    if (g !== last && g !== '同上') { h += `<div class="group">${esc(g)}</div>`; last = g; }
    const ans = (c.answer || '').trim();
    const where = c.cells['在哪裡'] || '';
    h += `
      <div class="confirm ${ans ? 'done' : ''}">
        <div>
          <div class="what">${esc(c.cells['#'] || '')}. ${inline(what)}</div>
          <div class="orig">${inline(c.cells['原文'] || '')}</div>
          <div class="where">${inline(where)}</div>
        </div>
        <div class="act">
          ${ans ? `<div class="val">已填：${esc(ans)}</div>` : ''}
          <button class="btn ${ans === '✓' ? '' : 'primary'}" data-ok="${c.line}">✓ 沒問題</button>
          <input data-note="${c.line}" placeholder="或寫一句意見" value="${ans && ans !== '✓' ? esc(ans) : ''}">
        </div>
      </div>`;
  }
  pane.innerHTML = h;
  const save = async (line, v) => {
    try {
      const r = await api('/api/review/cells', { body: { path: state.path, digest: state.review.digest, line, cells: { '確認': v } } });
      state.review.digest = r.digest;
      await openReview(state.path, true);
    } catch (e) { toast(e.message); }
  };
  pane.querySelectorAll('[data-ok]').forEach(b => b.onclick = () => save(+b.dataset.ok, '✓'));
  pane.querySelectorAll('[data-note]').forEach(inp => inp.onkeydown = e => {
    if (e.key === 'Enter' && inp.value.trim()) save(+inp.dataset.note, inp.value.trim());
  });
}

function renderGolden(pane) {
  pane.innerHTML = `<p class="hint">第一版只顯示內容；請在檔案中填寫。</p><div class="card"><pre style="white-space:pre-wrap">${inline(state.review.golden)}</pre></div>`;
}

function renderSpot(pane) {
  const r = state.review;
  pane.innerHTML = `
    <p class="hint">自選 1～2 條 AI 自評為 ✓ 的完成標準核對；發現自評不實，該步改為逐條審查。</p>
    ${r.spot_hint ? `<div class="card">${inline(r.spot_hint)}</div>` : ''}
    <table class="form"><tr><th>抽查了哪幾條</th><th>結果</th><th></th></tr>
    ${r.spot.map(s => `<tr><td><input data-items="${s.line}" value="${esc(s.items)}"></td><td><input data-result="${s.line}" value="${esc(s.result)}"></td><td><button class="btn" data-save="${s.line}">存</button></td></tr>`).join('')}
    </table>
    <button class="btn" id="addSpot">多加一列</button>`;
  pane.querySelectorAll('[data-save]').forEach(b => b.onclick = async () => {
    const line = +b.dataset.save;
    try {
      const res = await api('/api/review/cells', { body: { path: state.path, digest: r.digest, line, cells: {
        '抽查了哪幾條': $(`[data-items="${line}"]`, pane).value, '結果': $(`[data-result="${line}"]`, pane).value } } });
      r.digest = res.digest;
      await openReview(state.path, true);
    } catch (e) { toast(e.message); }
  });
  $('#addSpot', pane).onclick = async () => {
    try { await api('/api/review/spot-row', { body: { path: state.path, digest: r.digest, line: 0 } }); await openReview(state.path, true); }
    catch (e) { toast(e.message); }
  };
}

function renderConclusion(pane) {
  const r = state.review;
  const c = r.counts;
  const left = [];
  if (c.questions_open) left.push(`${c.questions_open} 題沒回答`);
  if (c.confirms_open) left.push(`${c.confirms_open} 列沒確認`);
  if (!c.spot_done) left.push('還沒抽查');
  const reviewerKey = h => Object.keys(h).find(k => k.startsWith('審查者'));
  pane.innerHTML = `
    ${left.length ? `<p class="problems">還有：${left.join('、')}。全部作答後才能填結論。</p>` : ''}
    <table class="form"><tr><th>步驟</th><th>審查者（非產出者）</th><th>日期</th><th>結論</th><th></th></tr>
    ${r.conclusion.map(x => `<tr>
      <td>${esc(x.cells['步驟'])}</td>
      <td><input data-who="${x.line}" value="${esc(x.cells[reviewerKey(x.cells)] || '')}"></td>
      <td><input data-date="${x.line}" value="${esc(x.cells['日期'] || today())}"></td>
      <td><select data-res="${x.line}">${['', '通過', '不通過'].map(v => `<option ${x.cells['結論'] === v ? 'selected' : ''}>${v}</option>`).join('')}</select></td>
      <td><button class="btn" data-save="${x.line}" ${left.length ? 'disabled' : ''}>存</button></td></tr>`).join('')}
    </table>
    <div class="handover">
      <b>交給 AI</b>
      <p class="hint">審查頁作答完，交給這條切片的 AI session 處理；凍結則執行 <code>/domain-freeze</code>。</p>
      <button class="btn primary" id="toAi" ${left.length ? 'disabled' : ''}>審查好了，交給 AI 處理</button>
      <button class="btn" id="toFreeze" ${c.conclusion_done ? '' : 'disabled'}>凍結…</button>
    </div>`;
  pane.querySelectorAll('[data-save]').forEach(b => b.onclick = async () => {
    const line = +b.dataset.save;
    const x = r.conclusion.find(y => y.line === line);
    try {
      const res = await api('/api/review/cells', { body: { path: state.path, digest: r.digest, line, cells: {
        [reviewerKey(x.cells)]: $(`[data-who="${line}"]`, pane).value, '日期': $(`[data-date="${line}"]`, pane).value,
        '結論': $(`[data-res="${line}"]`, pane).value } } });
      r.digest = res.digest;
      await openReview(state.path, true);
    } catch (e) { toast(e.message); }
  });
  $('#toAi', pane).onclick = () => aiSend(`審查好了。審查頁：${state.path}`);
  $('#toFreeze', pane).onclick = () => {
    const step = (state.path.match(/_([\d-]+)\.md$/) || [])[1] || '';
    openAi(true);
    $('#aiInput').value = `/domain-freeze ${step.split('-').map(n => String(+n)).join(' ')}`;
    $('#aiInput').focus();
  };
}

// ---------- 右邊：查閱檔案 ----------

async function openFile(file, line) {
  const base = state.review && state.review.slice ? `slices/${state.review.slice}` : '';
  try {
    const f = await api(`/api/file?path=${encodeURIComponent(file)}&base=${encodeURIComponent(base)}`);
    const v = $('#viewer');
    v.hidden = false;
    $('#viewerPath').textContent = f.path + (line ? `:${line}` : '');
    const n = +line || 0;
    $('#viewerBody').innerHTML = f.text.split('\n').map((l, k) =>
      `<span class="ln ${Math.abs(k + 1 - n) <= 0 && n ? 'hit' : ''}" data-n="${k + 1}">${esc(l) || ' '}</span>`).join('');
    const hit = $('.ln.hit', v);
    if (hit) hit.scrollIntoView({ block: 'center' });
  } catch (e) { toast(e.message); }
}

// ---------- 下方：AI session ----------

function curSlice() { return state.review && state.review.slice; }
function curPurpose() {
  const step = (state.path || '').match(/_([^/]+)\.md$/);
  return step ? `審查 ${step[1]}` : '審查';
}
function curSession() {
  const s = state.status && state.status.slices.find(x => x.slice === curSlice());
  return s && s.session;
}

function openAi(on) {
  $('#aiBody').hidden = !on;
}

async function renderAi() {
  const box = $('#aiSession');
  const sl = curSlice();
  if (!sl) { box.innerHTML = '先選一份審查頁。'; $('#aiState').textContent = ''; return; }
  const s = curSession();
  $('#aiState').textContent = s ? `· ${s.name}` : '· 沒有使用中的 session';
  if (!s) {
    box.innerHTML = await newSessionCard(`<b>${esc(sl)}</b> 沒有使用中的 session。`);
    bindNewSession();
    return;
  }
  const mismatch = s.purpose !== curPurpose();
  if ((mismatch || s.compacted) && state.sessionChoice !== s.id) {
    const why = s.compacted ? '這個 session 經過摘要壓縮，容易憑記憶回答' : `使用中的 session 用途是「${esc(s.purpose)}」，這份審查頁是「${esc(curPurpose())}」`;
    box.innerHTML = await newSessionCard(`${why}。要開新的 session 嗎？`, true);
    bindNewSession();
    $('#keepSession').onclick = () => { state.sessionChoice = s.id; renderAi(); };
    return;
  }
  box.innerHTML = `session：<b>${esc(s.name)}</b>（${esc(s.id.slice(0, 8))}，第 ${s.turns} 次）
    <span class="hint">在 terminal 接著做：<code>claude --resume ${esc(s.id)}</code></span>
    <button class="btn" id="endSession">結束這個 session</button>`;
  $('#endSession').onclick = async () => { await api(`/api/sessions/${s.id}/end`, { body: {} }); await loadStatus(); renderAi(); };
}

async function newSessionCard(msg, withKeep) {
  const h = await api(`/api/handoff?slice=${encodeURIComponent(curSlice())}&purpose=${encodeURIComponent(curPurpose())}&review=${encodeURIComponent(state.path)}`);
  return `<div class="choice">${msg}
    <div>交接提示（由檔案產生，送出前可以改）：</div>
    <textarea id="handoff">${esc(h.text)}</textarea>
    <button class="btn primary" id="newSession">A（建議）：開新的 session</button>
    ${withKeep ? '<button class="btn" id="keepSession">B：繼續用這個</button>' : ''}
  </div>`;
}

function bindNewSession() {
  $('#newSession').onclick = async () => {
    try {
      const s = await api('/api/sessions', { body: { slice: curSlice(), purpose: curPurpose(), handoff: $('#handoff').value } });
      await loadStatus();
      await renderAi();
      await aiSend(s.handoff);
    } catch (e) { toast(e.message); }
  };
}

async function aiSend(text) {
  openAi(true);
  const s = curSession();
  if (!s) { renderAi(); toast('先開一個 session'); return; }
  const log = $('#aiLog');
  log.insertAdjacentHTML('beforeend', `<div class="me">› ${esc(text)}</div>`);
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
        if (line.trim()) showEvent(JSON.parse(line));
      }
    }
  } catch (e) { toast(e.message); }
  $('#aiSend').disabled = false;
  await loadStatus();
  if (state.path) await openReview(state.path, true);  // AI 可能改了審查頁
}

function showEvent(ev) {
  const log = $('#aiLog');
  const sub = ev.sub ? ' sub' : '';
  if (ev.kind === 'text') log.insertAdjacentHTML('beforeend', `<div class="t${sub}">${inline(ev.text)}</div>`);
  else if (ev.kind === 'tool') log.insertAdjacentHTML('beforeend', `<div class="tool${sub}">· ${esc(ev.name)} ${esc(ev.brief)}</div>`);
  else if (ev.kind === 'compacted') log.insertAdjacentHTML('beforeend', `<div class="deny">這個 session 剛經過摘要壓縮，建議做完這一段就開新的 session。</div>`);
  else if (ev.kind === 'error') log.insertAdjacentHTML('beforeend', `<div class="err">${esc(ev.text)}</div>`);
  else if (ev.kind === 'result') {
    for (const d of ev.denials || []) {
      log.insertAdjacentHTML('beforeend', `<div class="deny">被擋下（要核准）：${esc(d.tool)} ${esc(JSON.stringify(d.input))}。請在 terminal 用 <code>claude --resume</code> 處理。</div>`);
    }
    if (!ev.ok) log.insertAdjacentHTML('beforeend', `<div class="err">${esc(ev.text)}</div>`);
  }
  log.scrollTop = log.scrollHeight;
}

// ---------- 事件 ----------

document.addEventListener('click', e => {
  const a = e.target.closest('a.ref-link');
  if (a) { e.preventDefault(); openFile(a.dataset.file, a.dataset.line); }
  const t = e.target.closest('[data-tab]');
  if (t) { state.tab = t.dataset.tab; history.replaceState(null, '', '#' + encodeURIComponent(state.path) + '@' + state.tab); render(); }
});
$('#viewerClose').onclick = () => { $('#viewer').hidden = true; };
$('#navToggle').onclick = () => $('#nav').classList.toggle('open');
$('#aiToggle').onclick = () => openAi($('#aiBody').hidden);
$('#aiForm').onsubmit = e => {
  e.preventDefault();
  const v = $('#aiInput').value.trim();
  if (v) { $('#aiInput').value = ''; aiSend(v); }
};
window.addEventListener('hashchange', route);

// 網址：#<審查頁路徑>@<分頁>，重新整理後停在同一個分頁
function route() {
  const [p, tab] = decodeURIComponent(location.hash.slice(1)).split('@');
  $('#nav').classList.remove('open');
  if (!p) return;
  if (tab) state.tab = tab;
  openReview(p, !!tab).catch(e => toast(e.message));
}

loadStatus().then(route).catch(e => toast(e.message));
