// 一次一個決定（審查頁的選擇題）
import { $, $$, api, enc, esc, firstOpenQ, go, inline, loadReview, nextTask, setTop, state, write } from './core.js';
import { askAi } from './ai.js';
import { narrow } from './nav.js';

// ---------- 一次一個決定 ----------

export function progressSegs(items, cur, isDone, hrefOf) {
  return `<div class="segs" style="grid-template-columns:repeat(${items.length},minmax(0,1fr))">${items.map((x, k) =>
    `<span class="${k === cur ? 'cur' : isDone(x) ? 'done' : ''}" data-href="${hrefOf(k)}" title="${k + 1}"></span>`).join('')}</div>`;
}

export async function renderDecide(path, i) {
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
      ${r.auto ? `<section class="card soft-card"><div class="label">全自動時 AI 暫時照 A 做</div>
        ${q.source ? `<div class="small">從哪來：${inline(q.source)}</div>` : ''}
        ${q.impact ? `<div class="small">選 A 以外的要改：${inline(q.impact)}</div>` : ''}</section>` : ''}
      <fieldset style="border:0;margin:0;padding:0;display:flex;flex-direction:column;gap:18px">
        <legend class="label">選一個${ans && !chosen ? `（你寫了：${esc(ans)}）` : ''}</legend>
        <div class="opts">${q.options.map(o => `
          <button class="opt ${o.recommended ? 'rec' : ''} ${chosen === o.key ? 'on' : ''}" data-opt="${o.key}">
            <span class="row spread"><span class="k">${o.key}</span>${o.recommended ? `<span class="badge-rec">${r.auto ? '★ 設計目前的做法' : '★ AI 建議'}</span>` : ''}${chosen === o.key ? '<span class="badge-rec">你選的</span>' : ''}</span>
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

export function renderDone(what, msg, nextHref) {
  setTop([`#/s/${enc(state.review.slice)}`, '關卡'], '');
  $('#app').innerHTML = `
    <section class="card lift celebrate pop">
      <div class="stars">★ ★ ★</div>
      <h1>${esc(what)}完成！</h1>
      <p class="muted">${esc(msg)}。答案已經寫回審查頁。</p>
      <div class="row" style="justify-content:center;margin-top:16px">
        <a class="btn big primary" href="${nextHref}">下一個任務<span class="arr">›</span></a>
        <a class="btn big" href="#/s/${enc(state.review.slice)}">回關卡</a>
      </div>
    </section>`;
}
