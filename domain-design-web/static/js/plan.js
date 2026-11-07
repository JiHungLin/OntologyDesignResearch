// 規劃：加資料、切片地圖、推想草稿、開始一條切片、專家問題
import { $, $$, api, CIRCLED, enc, esc, go, inline, keepDraft, md, remember, setTop, state, toast, today } from './core.js';
import { bindWaiting, openAi, runAi, runningCard, sessionOf, waitingCard } from './ai.js';
import { markNav, narrow } from './nav.js';
import { loadProject, planSlices, scenario } from './overview.js';
import { route } from './main.js';

// ---------- 加資料（貼上或上傳） ----------

export function inputDialog({ folder = 'shared', name = '', hint = '' } = {}) {
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

export function basket(scope) { try { return JSON.parse(remember('fb:' + scope) || '[]'); } catch (e) { return []; } }
export function setBasket(scope, items) { remember('fb:' + scope, JSON.stringify(items)); renderBasket(scope); }
export function addFeedback(scope, text) { const b = basket(scope); b.push(text); setBasket(scope, b); toast('放進回饋了，看完再一起交給 AI'); }

export function renderBasket(scope) {
  const el = $('#basket');
  if (!el) return;
  const items = basket(scope);
  el.hidden = !items.length;
  el.innerHTML = `<div class="row spread"><strong>你的回饋（${items.length}）</strong><button class="btn primary" id="sendFb">交給 AI 修改<span class="arr">›</span></button></div>
    <ol>${items.map((x, k) => `<li>${esc(x)} <button class="x-del" data-del="${k}" aria-label="刪除">✕</button></li>`).join('')}</ol>`;
  $$('[data-del]', el).forEach(b => b.onclick = () => { const it = basket(scope); it.splice(+b.dataset.del, 1); setBasket(scope, it); });
  $('#sendFb').onclick = () => {
    const msg = `/domain-plan 使用者看了切片地圖、名詞草圖與資料盤點，回饋如下（逐條處理，改了的記 slices/CHANGELOG.md；答覆待釐清的照格式填寫）：\n` + items.map((x, k) => `${k + 1}. ${x}`).join('\n');
    setBasket(scope, []);
    runAi('_plan', '規劃', msg);
  };
}

export function fbButton(text, label = '寫意見') { return `<button class="btn small-btn" data-fb="${esc(text)}">${label}</button>`; }

export function bindFb() {
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

export const INV_CLASS = { '已有': 'ok', '已蒐集': 'ok', '推想草稿': 'guess', '待提供': 'need', '找不到': 'none' };
// 盤點表「待提供」分兩種：AI 寫了「要找：去哪裡找什麼」的是公開資料、AI 抓不到要人去找；其他是只有使用者手上有的現場資料
export const needFetch = x => x['狀態'] === '待提供' && /要找/.test(x['位置'] || '');
export const whereToFind = x => (x['位置'] || '').replace(/^[—\-\s]*（?\s*要找[：:]\s*/, '').replace(/）\s*$/, '');
export const linkify = t => esc(t).replace(/https?:\/\/[^\s，、；）)]+/g, u => `<a href="${u}" target="_blank" rel="noopener">${u}</a>`);

export async function renderPlan() {
  state.slice = null; state.scope = '_plan';
  markNav();
  setTop(['#/', '總覽'], '<strong>規劃</strong>');
  const P = await loadProject();
  const plan = P.plan;
  if (!plan) { $('#app').innerHTML = runningCard('_plan', 'AI 正在規劃') || `<div class="card">還沒有切片地圖。<a href="#/">回總覽</a>請 AI 規劃。</div>`; const sa = $('#showAi'); if (sa) sa.onclick = () => openAi('_plan'); return; }
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
        const fetchCard = x => {
          const where = whereToFind(x);
          return `<div class="inv-item need fetch fb-host">
            <div class="what"><div><b>${esc(x['資料'])}</b><span class="chip">AI 抓不到</span></div>
            <div class="small muted">${inline(x['內容'] || '')}</div>
            ${where ? `<div class="where small"><span class="label" style="display:inline;margin:0 6px 0 0">去哪裡找</span>${linkify(where)}</div>` : ''}
            <div class="small"><a href="https://www.google.com/search?q=${enc(x['資料'])}" target="_blank" rel="noopener">用 Google 搜尋「${esc(x['資料'])}」↗</a></div></div>
            <div class="row">
              <button class="btn small-btn go" data-give="${esc(x['資料'])}" data-fetch="1">找到了，放進來</button>${fbButton(`資料「${x['資料']}」`, '找不到／說明')}
            </div></div>`;
        };
        const drafts1 = todo.filter(x => (draftOf(x) || {}).pending), fetch = todo.filter(needFetch), mine = todo.filter(x => !drafts1.includes(x) && !fetch.includes(x));
        const group = (title, note, xs, f) => xs.length ? `<div class="inv-group"><h3>${title}（${xs.length}）</h3><p class="small muted">${note}</p><div class="inv">${xs.map(f).join('')}</div></div>` : '';
        return `${todo.length ? group('推想草稿，要你看過', '網路上也找不到的一般做法，AI 先寫成草稿。看過、大致對就接受，才能當假設用。', drafts1, card)
            + group('AI 抓不到的公開資料，要你幫忙找', 'AI 打不開或搜不到這些網頁（規範不准憑記憶寫）。你找到後下載或複製貼上放進來，AI 會照格式摘錄；真的找不到也說一聲，AI 會改用推想並標出來。', fetch, fetchCard)
            + group('只有你們手上有的資料', '實際的表單、單據、做法。有就放進來；沒有也說一聲，AI 會照現有的資料繼續。', mine, card)
          : '<p class="small">資料都處理過了（沒有待提供、待接受的）。</p>'}
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
    <section class="card" id="p-mode">
      <div class="row spread"><div><div class="label">執行模式</div>
        <b>${plan.auto ? '全自動' : '手動'}</b>
        <p class="muted small" style="margin:4px 0 0;max-width:46em">${plan.auto
          ? '人的關卡先由 AI 代答並標「AI（自動）」，你事後看、改；原文核對、正式簽核 ⑥ 仍要你。到<a href="#/auto">全自動頁</a>開始、停止、看每一圈做了什麼（終端機的 <code>python3 tools/auto_run.py</code> 也可以）。'
          : '每一步停下來等你審查、核准。改成全自動後，人的關卡先由 AI 代答並標記，你事後再看（試用中）。'}</p></div>
        <div class="row">${plan.auto ? `<a class="btn primary" href="#/auto">${state.project.autorun && state.project.autorun.running ? '看進度' : '開始全自動'}</a>` : ''}<button class="btn" id="modeToggle" ${running || (state.project.autorun && state.project.autorun.running) ? 'disabled' : ''}>${plan.auto ? '改回手動' : '改成全自動'}</button></div></div>
      <p class="muted small" style="margin:6px 0 0">切換只影響之後的動作，會記在規劃的變更紀錄；已經由 AI 作答的審查頁照樣留著。</p>
    </section>
    <aside class="basket card lift" id="basket" hidden></aside>`;
  renderBasket('_plan');
  $('#modeToggle').onclick = async () => {
    const who = ($('#who').value || '').trim();
    if (!who) { toast('先在上面寫你的名字'); $('#who').focus(); return; }
    remember('reviewer', who);
    try { const r = await api('/api/plan/mode', { mode: plan.auto ? '手動' : '全自動', who }); toast(`執行模式：${r.mode}`); renderPlan(); }
    catch (e) { toast(e.message); }
  };
  bindFb();
  bindWaiting();
  $$('[data-jump]').forEach(b => b.onclick = () => document.getElementById(b.dataset.jump).scrollIntoView({ behavior: 'smooth' }));
  const sa = $('#showAi'); if (sa) sa.onclick = () => openAi('_plan');
  $('#addInput').onclick = () => inputDialog({ folder: 'shared' });
  $$('[data-give]').forEach(b => b.onclick = () => {
    state.onInput = (path) => addFeedback('_plan', b.dataset.fetch
      ? `公開資料「${b.dataset.give}」AI 抓不到，使用者找到原文放在 ${path}（第一行是網址）：請照 domain-plan 摘錄進 inputs/research/（引用時指向 research 條目，不把這份當現場資料），盤點表改為已蒐集`
      : `資料「${b.dataset.give}」已提供：${path}`);
    inputDialog(b.dataset.fetch
      ? { folder: 'shared', name: '公開資料原文_' + b.dataset.give, hint: `AI 抓不到的「${b.dataset.give}」。上傳下載的檔案，或把網頁內容複製貼上；第一行請貼網址（AI 摘錄時要寫出處）。存好後會放進回饋，交給 AI 時它會照格式摘錄。` }
      : { folder: 'shared', name: b.dataset.give, hint: `AI 列的「${b.dataset.give}」。存好後會放進回饋，交給 AI 時它會改盤點表的狀態與位置。` });
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

export async function renderDraft(path) {
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

export async function renderKickoff(code) {
  state.slice = null; state.scope = code;
  setTop(['#/', '總覽'], `<strong>開始 ${esc(code)}</strong>`);
  const P = await loadProject();
  const r = (P.plan ? P.plan.slices : []).find(x => x['切片'] === code) || {};
  if (P.slices.some(x => x.slice === code)) { go(`#/s/${enc(code)}`); return; }
  // 網頁一次只做一條切片：還有切片 ①～⑤ 沒都凍結，就不能開新的（伺服器也會擋）
  const busySlices = P.slices.filter(x => x.next && x.next.n <= 5);
  if (busySlices.length) {
    const b = busySlices[0];
    $('#app').innerHTML = `<div class="narrow"><section class="card lift" style="display:flex;flex-direction:column;gap:12px">
      <span class="chip">還不能開始</span><h1 class="qtitle" style="margin:0">${esc(code)} 要等 ${esc(b.slice)} 做完</h1>
      <p class="muted" style="margin:0">網頁一次只做一條切片。${esc(b.slice)} 還在第 ${CIRCLED[b.next.n]} 步；①～⑤ 都凍結後，就可以開始下一條。先做完的切片會把共用名詞定下來，下一條直接引用。</p>
      <div><a class="btn big primary" href="#/s/${enc(b.slice)}">回去做 ${esc(b.slice)}<span class="arr">›</span></a></div></section></div>`;
    return;
  }
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
      <div class="row"><button class="btn big primary" id="go1">開始<span class="arr">›</span></button></div>
    </div>`;
  $('#addInput').onclick = () => inputDialog({ folder: code });
  const fields = $$('#app [data-k]');
  const clearDraft = keepDraft('new:' + code, fields);
  $('#go1').onclick = () => {
    const a = Object.fromEntries(fields.map(x => [x.dataset.k, x.value.trim()]));
    clearDraft();
    const lines = qs.map(([k, q]) => `- ${q}${a[k] || '（使用者沒寫）'}`).join('\n');
    runAi(code, '第 1 步', `/domain-new-slice ${code}\n\n使用者在網頁上先回答了開工的問題（原話，存成 inputs/${code}/ 的檔案時照抄）：\n${lines}\n\n建立好就接著做第 ① 步。`);
    setTimeout(() => go('#/'), 300);
  };
}

// ---------- 專家問題 ----------

export async function renderEq(slice) {
  state.slice = slice; state.scope = slice;
  markNav();
  setTop([`#/s/${enc(slice)}`, slice], '<strong>專家問題</strong>');
  const h = await api('/api/home?slice=' + enc(slice));
  // 待問、已問在網頁上都算「等專家回覆」：問了沒有不用記，等到專家回覆才算有進展（點了「我問了」會像結案，容易誤會）
  const waitingEq = e => e['狀態'] === '待問' || e['狀態'] === '已問';
  const order = { '待問': 0, '已問': 0, '暫依整理': 1, '已回覆': 2 };
  const eqs = h.eqs.slice().sort((a, b) => (order[a['狀態']] ?? 9) - (order[b['狀態']] ?? 9) || a.line - b.line);
  const toAsk = eqs.filter(waitingEq);
  $('#app').innerHTML = `
    <div><h1 style="margin:0">專家問題</h1><p class="muted" style="margin:4px 0 0">AI 答不了、要問 Domain 專家或客戶的事。不擋關卡：相關的地方先標「待專家確認」，答覆回來再交給 AI 回頭改。</p></div>
    ${toAsk.length ? `<div class="row"><button class="btn primary" id="copyAll">複製 ${toAsk.length} 題等回覆的（給專家）</button></div>` : ''}
    <div class="eqs">${eqs.map(e => {
      const st = e['狀態'], wait = waitingEq(e);
      return `<section class="card eq ${wait ? 'need' : st === '已回覆' ? 'ok' : ''}" data-line="${e.line}">
        <div class="row spread"><b>${esc(e['編號'])}</b><span class="chip ${wait ? 'turn' : st === '已回覆' ? 'new' : ''}">${wait ? '等專家回覆' : esc(st)}</span></div>
        <div class="eq-q">${inline(e['問題（業務語言）'] || e['問題'] || '')}</div>
        <div class="small muted">問誰：${esc(e['問誰'] || '')}　提出於 ${esc(e['提出於'] || '')}</div>
        ${e['答覆'] ? `<div class="box"><div class="label">答覆（${esc(e['答覆日'] || '')}）</div>${inline(e['答覆'])}</div>` : ''}
        ${e['影響'] ? `<details class="tech"><summary>影響哪些地方</summary>${inline(e['影響'])}</details>` : ''}
        <div class="row">
          ${wait ? `<button class="btn small-btn" data-copy="${e.line}">複製這題</button>` : ''}
          ${wait || st === '暫依整理' ? `<button class="btn small-btn primary" data-reply-eq="${esc(e['編號'])}">專家回覆了</button>` : ''}
          ${st === '已回覆' && !e['處理'] ? `<button class="btn small-btn primary" data-handle="${esc(e['編號'])}">交給 AI 處理</button>` : ''}
          ${e['處理'] ? `<span class="small">處理：${inline(e['處理'])}</span>` : ''}
        </div></section>`;
    }).join('') || '<div class="card dashed">沒有專家問題。</div>'}</div>`;
  const qText = e => `${e['編號']}：${e['問題（業務語言）'] || e['問題'] || ''}`;
  const copy = t => navigator.clipboard.writeText(t).then(() => toast('已複製（不含 AI 的建議答案）'), () => toast('複製失敗'));
  const ca = $('#copyAll'); if (ca) ca.onclick = () => copy(toAsk.map(qText).join('\n\n'));
  $$('[data-copy]').forEach(b => b.onclick = () => copy(qText(eqs.find(e => e.line === +b.dataset.copy))));
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
