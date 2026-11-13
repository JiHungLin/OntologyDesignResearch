// 抽查與簽名過關
import { $, $$, api, enc, esc, firstOpenQ, go, inline, loadReview, md, plain, remember, setTop, state, stepNums, toast, today, write } from './core.js';
import { runAi } from './ai.js';
import { narrow } from './nav.js';

// ---------- 抽查與簽名過關 ----------

export async function renderFinish(path, focus) {
  const r = state.review && state.path === path ? state.review : await loadReview(path);
  const c = r.counts;
  const p = enc(path);
  setTop([`#/s/${enc(r.slice)}`, '關卡'], '<strong>最後一關：抽查與簽名</strong>');
  const left = [];
  if (c.questions_open) left.push(`<a href="#/r/${p}/decide/${firstOpenQ(r)}">${c.questions_open} 個決定</a>`);
  if (c.confirms_open) left.push(`<a href="#/r/${p}/confirm">${c.confirms_open} 項確認</a>`);
  if (c.cases_open) left.push(`<a href="#/r/${p}/golden/0">${c.cases_open} 個案例</a>`);
  const spotRow = r.spot.find(s => s.items.trim()) || r.spot[0];
  const name = remember('reviewer');
  const signed = c.conclusion_done;
  const exec_ = r.conclusion.some(x => '執行者' in x.cells);   // ⑥ 的結論表多一欄執行者
  const stage1 = /⑤\s*第一段/.test(((r.meta || []).find(m => m.key === '這輪審查的步驟') || {}).value || '');   // ⑤ 分兩段：第一段答完不凍結（docs/01 ⑤「兩段審查」）

  // 抽查一次看一條：清單挑一條 → 這一條的完成標準、AI 說、證據（AI 寫的編號與行號已換成內容）、判斷按鈕放在同一張卡
  // 審查頁的寫法是「① 第 1、4 條；③ 第 2 條」；畫面上一條的代號是「①1」（步驟＋第幾條）
  const items = r.spot_items;
  const vkey = 'spot:' + path;
  let verdicts = {};
  try { verdicts = JSON.parse(localStorage.getItem(vkey) || '{}'); } catch (e) { }
  if (spotRow && spotRow.items && (spotRow.result || '').trim() && !Object.keys(verdicts).length) {   // 別的瀏覽器填的：照審查頁還原（只挑了、還沒判斷的不算）
    const bad = /不實/.test(spotRow.result);
    for (const m of spotRow.items.matchAll(/([①-⑥])?[^第①-⑥]*?第\s*([\d、，, ]+)\s*條/g))
      for (const k of m[2].match(/\d+/g) || []) verdicts[(m[1] || (items[0] || {}).step || '') + k] = { ok: !bad, note: bad ? spotRow.result : '' };
  }
  const done = items.filter(it => verdicts[it.id]);
  const label = it => `${it.step} 第 ${it.n} 條`;
  const cur = focus && items.find(it => it.id === focus);

  const evHtml = e => {
    const fields = (e.fields || []).filter(([h, v], k) => !(k === 0 && v === e.ref) && v && v !== '—');
    return `<div class="ev-card">
      <div class="row spread"><b>${esc(e.ref)}${e.title ? `<span class="muted small">　${esc(e.title)}</span>` : ''}</b>
        <a class="small ref-link" data-file="${esc(e.file)}" data-line="${e.line || 1}">${esc(e.file.split('/').pop())} 第 ${e.line} 行 ›</a></div>
      ${fields.length ? `<dl>${fields.map(([h, v]) => `<dt>${esc(h)}</dt><dd>${inline(v)}</dd>`).join('')}</dl>` : e.text ? `<div class="orig md">${e.text.includes('\n') ? md(e.text) : inline(e.text.replace(/^\s*[-*]\s+/, ''))}</div>` : ''}
    </div>`;
  };

  let spotHtml;
  if (!items.length) {
    spotHtml = `<div class="small">${inline(r.spot_hint || '（審查頁沒有列出可挑的條目）')}</div>
      <div class="row"><input type="text" id="spotItems" style="flex:1" value="${esc(spotRow ? spotRow.items : '')}" placeholder="抽查了哪幾條，例：① 第 3、7 條">
        <button class="btn go" id="spotOk">核對過，屬實</button></div>
      <input type="text" id="spotBad" class="soft" placeholder="或寫一句哪裡不對，按 Enter">`;
  } else if (cur) {
    const v = verdicts[cur.id];
    spotHtml = `<a href="#/r/${p}/finish" class="small">← 回清單、換一條</a>
      <div class="row spread"><b>${esc(label(cur))}</b>${cur.kind ? `<span class="chip ${/關鍵/.test(cur.kind) ? 'turn' : ''}">${esc(cur.kind)}</span>` : ''}</div>
      <h2 style="margin:0;font-size:20px;line-height:1.5">${inline(cur.text.replace(/\*\*/g, ''))}</h2>
      <div class="box"><div class="label">AI 說它做到了</div>${inline(plain(cur.self))}</div>
      <div><div class="label">證據（AI 提到的地方，已經幫你找出來）</div>
        ${cur.evidence.length ? `<div class="evs">${cur.evidence.filter(e => !e.more).map(evHtml).join('')}
          ${cur.evidence.some(e => e.more) ? `<details class="ev-more"><summary>其他 ${cur.evidence.filter(e => e.more).length} 項證據（需要時再看）</summary><div class="evs">${cur.evidence.filter(e => e.more).map(evHtml).join('')}</div></details>` : ''}</div>`
          : `<div class="small muted">AI 沒有寫出處。<a class="ref-link" data-file="${esc(cur.file)}" data-line="${cur.line}">打開 ${esc(cur.file.split('/').pop())}</a>，自己找這條標準說的內容在哪一段。</div>`}</div>
      <div class="judge">
        <div class="label" style="color:var(--ink);font-size:15px">AI 說的，和證據對得上嗎？</div>
        <div class="row"><button class="btn go" id="vOk">對得上，屬實</button><button class="btn" id="vBad">對不上</button>
          ${v ? `<span class="small">已記下：${v.ok ? '屬實' : '不實：' + esc(v.note)}</span>` : ''}</div>
        <div class="row" id="badBox" hidden><input type="text" id="badNote" class="soft" style="flex:1" placeholder="哪裡不對？寫一句（例：D-01 只寫了結論，沒寫為什麼不用輕量）"><button class="btn primary" id="badSave">記下</button></div>
      </div>`;
  } else {
    spotHtml = `<p class="small muted" style="margin:0">AI 自評下面每一條都做到了。<b>挑 1～2 條</b>你最在意的（建議「關鍵決定」類），點進去看證據、判斷對不對。有一條不實，這一步就改成逐條審查。</p>
      ${done.length ? `<div class="small"><b>已核對 ${done.length} 條：</b>${done.map(it => `${esc(label(it))} ${verdicts[it.id].ok ? '✓ 屬實' : '✗ 不實'}`).join('、')}${done.length >= 1 ? '　（夠了的話往下簽名）' : ''}</div>` : ''}
      <div class="spot-list">${items.map(it => `
        <a class="spot-item ${verdicts[it.id] ? (verdicts[it.id].ok ? 'ok' : 'bad') : ''}" href="#/r/${p}/finish/${enc(it.id)}">
          <span class="row spread"><b>${esc(label(it))}</b><span class="row" style="gap:6px">${verdicts[it.id] ? `<span class="chip ${verdicts[it.id].ok ? 'new' : 'turn'}">${verdicts[it.id].ok ? '屬實' : '不實'}</span>` : ''}${it.kind ? `<span class="chip ${/關鍵/.test(it.kind) ? 'turn' : ''}">${esc(it.kind)}</span>` : ''}</span></span>
          <span>${inline(it.text.replace(/\*\*/g, ''))}</span></a>`).join('')}</div>`;
  }

  $('#app').innerHTML = `
    <div class="narrow">
      ${left.length ? `<div class="card hint">還有 ${left.join('、')} 沒完成，完成後才能簽名。</div>` : ''}
      <section class="card lift spot" style="display:flex;flex-direction:column;gap:16px">
        ${cur ? '' : '<div><span class="chip">抽查</span><h2 style="margin:8px 0 0">AI 說它做到了：挑 1～2 條核對</h2></div>'}
        ${spotHtml}
      </section>
      ${cur ? '' : `      <section class="card lift" style="display:flex;flex-direction:column;gap:12px">
        <div><span class="chip">簽名過關</span><h2 style="margin:8px 0 0">你是審查者（不是產出這一步的人）</h2></div>
        <input type="text" id="who" value="${esc(name)}" placeholder="你的名字">
        ${exec_ ? `<label class="label" for="execBy" style="margin:0">執行者（在核准卡片上放行測試指令、看著它跑的人；不能和你同一人）</label>
        <input type="text" id="execBy" value="${esc(r.conclusion.map(x => x.cells['執行者']).find(Boolean) || '')}" placeholder="執行者的名字">` : ''}
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
        ${stage1 ? `<p class="muted">⑤ 第一段答完了。交給 AI 做第二段：抄回你算的結果、產生 schema 與 API、做紙上推演，再送一份審查頁給你。</p>
        <div class="row" style="justify-content:center">
          <button class="btn big primary" id="stage2">交給 AI 做第二段</button>
        </div>` : `<p class="muted">審查頁都填好了。交給 AI：它會依你的答案修改設計；全部通過的話，再請它凍結。</p>
        <div class="row" style="justify-content:center">
          <button class="btn big primary" id="handover">審查好了，交給 AI</button>
          <button class="btn big" id="freeze">請 AI 凍結</button>
        </div>`}
      </section>` : ''}
`}
    </div>`;
  if (cur) $('.page').scrollTo(0, 0);   // 主畫面自己捲動（style.css .page）

  const spotLine = spotRow ? spotRow.line : null;
  const saveSpot = async (itemsTxt, result) => {
    if (!spotLine) { toast('審查頁沒有抽查表'); return false; }
    return write('/api/review/cells', { line: spotLine, cells: { '抽查了哪幾條': itemsTxt, '結果': result } });
  };
  const saveVerdicts = async () => {
    try { localStorage.setItem(vkey, JSON.stringify(verdicts)); } catch (e) { }
    const ds = items.filter(it => verdicts[it.id]);
    const by = new Map();
    for (const it of ds) by.set(it.step, (by.get(it.step) || []).concat(it.n));
    const txt = [...by].map(([st, ns]) => `${st || items[0].file.split('/').pop() + ' 完成標準'} 第 ${ns.join('、')} 條`).join('；');
    const bad = ds.filter(it => !verdicts[it.id].ok);
    return saveSpot(txt, bad.length ? ds.map(it => verdicts[it.id].ok ? `${label(it)}屬實` : `${label(it)}不實：${verdicts[it.id].note}`).join('；') : '屬實');
  };
  if (cur) {
    $('#vOk').onclick = async () => { verdicts[cur.id] = { ok: true, note: '' }; if (await saveVerdicts()) { toast(`${label(cur)}：屬實`); go(`#/r/${p}/finish`); } };
    $('#vBad').onclick = () => { $('#badBox').hidden = false; $('#badNote').focus(); };
    const saveBad = async () => {
      const note = $('#badNote').value.trim();
      if (!note) { toast('寫一句哪裡不對'); return; }
      verdicts[cur.id] = { ok: false, note };
      if (await saveVerdicts()) { toast(`${label(cur)}：不實，已記下`); go(`#/r/${p}/finish`); }
    };
    $('#badSave').onclick = saveBad;
    $('#badNote').onkeydown = e => { if (e.key === 'Enter') saveBad(); };
    return;
  }
  if (!items.length) {
    $('#spotOk').onclick = () => { const it = $('#spotItems').value.trim(); if (!it) { toast('寫抽查了哪幾條'); return; } saveSpot(it, '屬實').then(ok => ok && renderFinish(path)); };
    $('#spotBad').onkeydown = e => {
      const v = e.target.value.trim(), it = $('#spotItems').value.trim();
      if (e.key === 'Enter' && v) { if (!it) { toast('寫抽查了哪幾條'); return; } saveSpot(it, v).then(ok => ok && renderFinish(path)); }
    };
  }
  $$('[data-verdict]').forEach(b => b.onclick = async () => {
    const who = $('#who').value.trim();
    if (!who) { toast('先寫你的名字'); return; }
    const x = r.conclusion.find(y => y.line === +b.dataset.verdict);
    const key = Object.keys(x.cells).find(k => k.startsWith('審查者'));
    const cells = { [key]: who, '日期': today(), '結論': b.dataset.v };
    if ('執行者' in x.cells) {   // ⑥：審查者就是簽核者，不能和執行者同一人（docs/02「第 ⑥ 步的審查頁」）
      const ex = $('#execBy').value.trim();
      if (!ex) { toast('先寫執行者'); $('#execBy').focus(); return; }
      // 一人團隊可以同一人，執行者加註「（一人團隊）」，之後的人看得出這次沒有分開（docs/01 0.5）
      cells['執行者'] = ex === who ? `${ex}（一人團隊）` : ex;
      if (ex === who) toast('執行者和簽核者是同一人：記成「一人團隊」');
    }
    remember('reviewer', who);
    if (await write('/api/review/cells', { line: x.line, cells })) renderFinish(path);
  });
  const ho = $('#handover');
  const step = (path.match(/_([\d-]+)\.md$/) || [])[1] || '';
  if (ho) ho.onclick = () => runAi(r.slice, `審查 ${step}`, `審查好了。審查頁：${path}`, { review: path });
  const s2 = $('#stage2');
  if (s2) s2.onclick = () => runAi(r.slice, '⑤ 第二段', `/domain-step 5 ${r.slice}（⑤ 第一段已作答：${path}）`, { review: path });
  const fz = $('#freeze');
  if (fz) fz.onclick = () => runAi(r.slice, `凍結 ${step}`, `/domain-freeze ${stepNums(r.steps ? r : step).join(',')} ${r.slice}`, { review: path });
}
