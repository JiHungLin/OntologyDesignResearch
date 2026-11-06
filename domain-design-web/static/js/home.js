// 切片首頁：輪到你、關卡
import { $, api, CIRCLED, enc, esc, firstOpenQ, LEVEL_NAME, loadReview, nextTask, plain, setTop, state, stepName, stepNums, tasksOf } from './core.js';
import { bindWaiting, openAi, pendingAsk, runAi, runningCard, sessionOf, waitingCard } from './ai.js';
import { markNav, STEP_FILE } from './nav.js';

// ---------- 切片首頁：輪到你 ----------

// 每一步 AI 做什麼、做完要你做什麼（給還沒開始的關卡看）
export const STEP_INFO = {
  1: ['範圍與驗收問題', '這條切片做到哪裡、做完要能回答哪些問題', '回答範圍的選擇題、確認驗收問題'],
  2: ['名詞盤點', '哪些是「一個東西」、彼此什麼關係', '看模型圖，確認新增的名詞與關係'],
  3: ['流程與狀態', '事情怎麼發生、誰能做、錯了怎麼改', '確認狀態、歷史需求與更正方式'],
  4: ['規則與限制', '什麼情況允許、什麼必須成立、依據是什麼', '回答規則的選擇題、確認依據'],
  5: ['投影到實作與紙上驗證', '每個概念放在哪張表、哪支 API；照設計推演黃金案例', '自己算 1～3 個黃金案例，和設計對答案'],
  6: ['跑起來驗證', '在真的系統上跑黃金案例、回答驗收問題', '簽核（執行者和簽核者不同人）'],
};

export function levelStrip(levels) {
  return `<nav class="levels" aria-label="切片關卡">${levels.map(l => {
    const label = { frozen: '過關', review: '挑戰中', wait: '等你凍結', freezing: '凍結中', draft: '進行中', locked: '未開始' }[l.state];
    const href = l.state !== 'locked' && state.slice ? `#/f/${enc(`slices/${state.slice}/${STEP_FILE[l.n]}`)}` : '';
    return `<div class="level ${l.state}" title="${esc(l.status)} ${esc(l.tag)}${href ? '（點一下看檔案）' : ''}" ${href ? `data-href="${href}" role="link" tabindex="0"` : ''}>
      <b>${CIRCLED[l.n]}</b><span>${esc(l.name)}<small>${label}</small></span></div>`;
  }).join('')}</nav>`;
}

export async function renderHome(slice) {
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
  // AI 停下來問了選擇題：問題卡就是這一頁的主角，關卡按鈕先不放（按了會開新的 session，問題就沒人接）
  const asking = !(s && s.running) && pendingAsk(slice);
  if (s && s.running) {
    hero = runningCard(slice);
  } else if (asking) {
    hero = waitingCard(slice);
  } else if (cur) {
    const r = await loadReview(cur.path);
    const c = r.counts;
    const nums = stepNums(cur);
    const title = nums.length > 1 ? `關卡 ${stepName(cur)}` : `關卡 ${CIRCLED[nums[0]]}　${LEVEL_NAME[nums[0]] || ''}`;
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
        <a class="btn big yellow" href="${nextTask(r)}">${c.open === (c.questions + c.confirms + c.cases + 2) ? '開始審查' : '繼續審查'}<span class="arr">›</span></a>
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
    const stepOf = last || step;
    // 交回後 AI 做了紙上推演、和你的答案對不上：先回黃金案例頁對答案（改你的答案，或留著讓 AI 說明）
    const lr = last ? await loadReview(last.path) : null;
    // 回頭修改的 session 做完也算處理過（它的回覆會說接下來要重做這一步，或還要改什麼）
    const handled = s && !s.running && (s.purpose === `審查 ${step}` || s.purpose === '回頭修改') && !!s.last_reply;
    // 依這份審查頁重做這一步、做到一半停下（等核准逾時、session 太長）：下一步是繼續做，不是再把審查頁交給 AI
    const nStep = Math.max(0, ...stepNums(stepOf));
    const redoing = s && !s.running && s.purpose === `第 ${nStep} 步` && !!s.last_reply && (!last || !s.started || s.started.slice(0, 10) >= last.date);
    const off = lr ? lr.cases.map((c, k) => ({ c, k })).filter(x => /^不一致/.test(((x.c.paper || {})['紙上判定'] || '').trim())) : [];
    if (off.length) {
      const p = enc(last.path);
      hero = `
      <section class="hero">
        <div style="flex:999 1 480px;min-width:0">
          <span class="chip">輪到你</span>
          <h1>對答案：${off.length} 個黃金案例和設計推出的不一樣</h1>
          <p>AI 依設計另外推了一次，${off.map(x => esc(x.c.id)).join('、')} 和你的答案對不上。逐一看差在哪：你的答案要改就直接改了再送出；你認為設計錯了，就不用改，交給 AI 時說明。</p>
          <p class="muted small">${off.map(x => `<a href="#/r/${p}/golden/${x.k}">${esc(x.c.id)}</a>`).join('　')}</p>
        </div>
        <div class="row"><a class="btn big yellow" href="#/r/${p}/golden/${off[0].k}">去對答案<span class="arr">›</span></a><button class="btn big" id="handover">對完了，交給 AI</button></div>
      </section>`;
    } else if (redoing) {
      const said = s.last_reply || '';
      const nextLine = ((said.match(/下一步[：:]\s*([^\n]+)/g) || []).pop() || '').replace(/^下一步[：:]\s*/, '');
      hero = `
      <section class="hero">
        <div style="flex:999 1 480px;min-width:0">
          <span class="chip">輪到你</span>
          <h1>第 ${CIRCLED[nStep]} 步重做到一半，AI 停下來了</h1>
          <p>AI 依審查頁重做第 ${CIRCLED[nStep]} 步，還沒做完（例：等你核准的指令逾時、session 太長）。請 AI 繼續做；做完會產生新的審查頁，那時再審查。</p>
          ${nextLine ? `<div class="hero-next"><b>AI 說下一步：</b>${esc(plain(nextLine))}</div>` : ''}
          <p class="muted small">按下面的按鈕時，網頁會問你要不要開新的 session（AI 建議開新的話就開）。</p>
        </div>
        <div class="row"><button class="btn big yellow" id="contStep">請 AI 繼續第 ${CIRCLED[nStep]} 步<span class="arr">›</span></button><button class="btn big" id="showAi">看 AI 怎麼說</button></div>
      </section>`;
    } else if (handled) {
      // AI 已經處理過這份審查頁的答案：下一步是繼續這一步（還要送下一份審查頁）或凍結，不是再交一次
      const n = Math.max(0, ...stepNums(stepOf));
      const more = /再送一份審查頁|再送審/.test(((lr && lr.meta.find(m => /填完之後/.test(m.key))) || {}).value || '');
      // AI 處理答案時發現要回頭改設計（審查頁選了要改設計的選項、凍結條件不滿足）：主按鈕改成回頭修改，不是凍結
      const said = s.last_reply || '';
      // 設計已經改好、要重新產出這一步（例：⑥ 程式要對應新 tag、重跑測試）：主按鈕是重做這一步，不是再回頭修改
      const redo = new RegExp(`重做(?:第\\s*)?[${CIRCLED[n]}${n}]\\s*步|繼續做(?:第\\s*)?[${CIRCLED[n]}${n}]|[${CIRCLED[n]}]\\s*按「開始」|繼續第\\s*[${CIRCLED[n]}${n}]\\s*步`).test(said);
      const back = redo || /不能凍結|才能凍結|這一輪不凍結|先不凍結|回頭修改/.test(said);
      const nextLine = ((said.match(/下一步[：:]\s*([^\n]+)/g) || []).pop() || '').replace(/^下一步[：:]\s*/, '');
      const said_ = nextLine ? `<div class="hero-next"><b>AI 說下一步：</b>${esc(plain(nextLine))}</div>` : '';
      if (back) hero = `
      <section class="hero">
        <div style="flex:999 1 480px;min-width:0">
          <span class="chip">輪到你</span>
          <h1>AI 處理完了：${esc(stepName(stepOf))} 還不能凍結</h1>
          <p>${redo ? `你的答案要改的設計已經處理了，但第 ${CIRCLED[n]} 步的產出還是舊的：請 AI 重做第 ${CIRCLED[n]} 步，做完會產生新的審查頁。要你填的欄位（AI 對話裡列的）可以同時做。`
            : 'AI 依你的答案判斷，要先回頭修改設計（或補人才能填的欄位），這一輪才能凍結。'}詳細在右邊的 AI 對話。</p>
          ${said_}
          <p class="muted small">按下面的按鈕時，網頁會問你要不要開新的 session。</p>
        </div>
        <div class="row">${redo ? `<button class="btn big yellow" id="contStep">請 AI 重做第 ${CIRCLED[n]} 步<span class="arr">›</span></button><button class="btn big" id="showAi">看 AI 怎麼說</button><button class="btn big" id="goBack">還要回頭改設計</button>`
          : `<button class="btn big yellow" id="goBack">請 AI 依審查頁回頭修改<span class="arr">›</span></button><button class="btn big" id="showAi">看 AI 怎麼說</button>`}
          <button class="btn big" id="freeze">仍然請 AI 凍結</button></div>
      </section>`;
      else hero = `
      <section class="hero">
        <div style="flex:999 1 480px;min-width:0">
          <span class="chip">輪到你</span>
          <h1>AI 處理完了：${esc(stepName(stepOf))}</h1>
          ${said_}
          <p>${more ? `這份審查頁說這一輪還要再送一份審查頁：請 AI 繼續第 ${CIRCLED[n]} 步，產生下一份。都通過後才凍結。` : '結論都是「通過」的話，請 AI 凍結（凍結＝之後的修改都要留紀錄）。'}</p>
          <p class="muted small">AI 的回覆在右邊的 AI 對話；按下面的按鈕時，網頁會問你要不要開新的 session。</p>
        </div>
        <div class="row">${more ? `<button class="btn big yellow" id="contStep">請 AI 繼續第 ${CIRCLED[n]} 步<span class="arr">›</span></button><button class="btn big" id="freeze">請 AI 凍結</button>`
          : `<button class="btn big yellow" id="freeze">請 AI 凍結<span class="arr">›</span></button><button class="btn big" id="contStep">還要改，請 AI 繼續第 ${CIRCLED[n]} 步</button>`}
          <button class="btn big" id="handover">再交一次審查頁</button></div>
      </section>`;
    } else hero = `
      <section class="hero">
        <div style="flex:999 1 480px;min-width:0">
          <span class="chip">輪到你</span>
          <h1>審查填好了：${esc(stepName(stepOf))}</h1>
          <p>交給 AI 依你的答案修改；結論都是「通過」的話，請 AI 凍結（凍結＝之後的修改都要留紀錄）。</p>
        </div>
        <div class="row"><button class="btn big yellow" id="handover">交給 AI 處理答案</button><button class="btn big" id="freeze">請 AI 凍結</button></div>
      </section>`;
  } else if (h.next) {
    const n = h.next.n;
    const info = STEP_INFO[n];
    const going = h.next.status !== '未開始';
    // 這條切片最後一個 session 做完時說的下一步（例：凍結 ② 後提醒 ⑥ 的黃金案例要補），讓人知道按下去之後 AI 會處理什麼
    const lastSaid = s && !s.running && s.last_reply ? ((s.last_reply.match(/下一步[：:]\s*([^\n]+)/g) || []).pop() || '').replace(/^下一步[：:]\s*/, '') : '';
    hero = h.next.status === '凍結中' ? `
      <section class="hero idle">
        <div style="flex:999 1 480px;min-width:0">
          <span class="chip">輪到 AI</span>
          <h1>第 ${CIRCLED[n]} 步的凍結還沒做完</h1>
          <p>檔頭已經寫「已凍結」，但還沒有 tag <code>${esc(h.next.version || `${slice}/0${n}-v?`)}</code>：CHANGELOG、合併進 core/、commit、打 tag 至少有一件還沒做。做完才能開始下一關。</p>
        </div>
        <button class="btn big primary" id="finishFreeze">請 AI 把凍結做完<span class="arr">›</span></button>
      </section>` : `
      <section class="hero idle">
        <div style="flex:999 1 480px;min-width:0">
          <span class="chip">輪到 AI</span>
          <h1>${going ? `第 ${CIRCLED[n]} 步還沒做完` : `下一關：${CIRCLED[n]} ${esc(info[0])}`}</h1>
          <p>AI 會整理：${esc(info[1])}。做完後另開 AI 挑錯、核對，產生一份審查頁，這裡就會出現新的關卡。</p>
          ${lastSaid ? `<div class="hero-next"><b>AI 上次說：</b>${esc(plain(lastSaid))}</div>` : ''}
          ${going && n === 6 ? '<p class="small">AI 提到的問題（例：黃金案例的內容要補、系統結果和你算的不一致、缺 API）都在這一步裡處理：AI 能改的（案例情境、程式、測試）自己改，要你決定的（你的答案要不要改、要不要回頭改設計）會列在 ⑥ 的審查頁問你。</p>' : ''}
          <p class="muted small">之後輪到你：${esc(info[2])}。${n === 6 ? '第 ⑥ 步要有實作好的系統才做。' : ''}</p>
        </div>
        <button class="btn big primary" id="doStep">${going ? `請 AI 繼續第 ${CIRCLED[n]} 步` : `請 AI 開始第 ${CIRCLED[n]} 步`}<span class="arr">›</span></button>
      </section>`;
  } else {
    hero = `<section class="card lift celebrate pop"><div class="stars">★ ★ ★</div><h1>這條切片全部完成！</h1>
      <p class="muted">①～⑥ 都凍結了。回總覽挑下一條。</p><a class="btn big primary" href="#/">回總覽</a></section>`;
  }

  const designDone = h.levels.slice(0, 5).every(l => l.state === 'frozen') && h.levels[5].state === 'locked';   // ⑥ 開始後（進行中、審查中、待凍結）照一般關卡顯示
  if (designDone && !(s && s.running) && !asking) {
    hero = `<section class="card lift celebrate pop"><div class="stars">★ ★ ★</div><h1>設計完成（待驗證）</h1>
      <p class="muted">①～⑤ 都凍結了，這是一個設計版本。第 ⑥ 步等系統實作好再做；現在可以開始下一條切片。</p>
      <div class="row" style="justify-content:center"><a class="btn big primary" href="#/">挑下一條切片<span class="arr">›</span></a><button class="btn big" id="doStep">系統好了，開始 ⑥</button></div></section>`;
  }

  const eqOpen = h.eqs.filter(e => e['狀態'] !== '已回覆');
  const eqTodo = h.eqs.filter(e => e['狀態'] === '已回覆' && !e['處理']);
  const past = h.reviews.filter(x => !cur || x.path !== cur.path);
  // 審查頁都作答了、還沒凍結：留一個回去改答案的入口（左側的「審查（輪到你）」這時已經不見）
  const reopen = !cur && wait.length && h.reviews[0] && !h.reviews[0].error
    ? `<p class="small reopen"><a href="#/r/${enc(h.reviews[0].path)}">想改答案？回到審查頁（${esc(stepName(h.reviews[0]))}）<span class="arr">›</span></a></p>` : '';
  app.innerHTML = `
    ${levelStrip(h.levels)}
    ${asking ? '' : waitingCard(slice)}
    ${hero}
    ${reopen}
    <div class="cols">
      ${tasks}
      <section class="wide">
        ${changes}
        ${eqOpen.length || eqTodo.length ? `<a class="card hint row spread" href="#/eq/${enc(slice)}" style="text-decoration:none;color:inherit">
          <span><strong>支線：專家問題</strong>　${eqOpen.length ? `${eqOpen.length} 題還沒有答覆（不擋關卡）` : ''}${eqTodo.length ? `　${eqTodo.length} 題答覆了、還沒處理` : ''}</span><span class="btn">打開<span class="arr">›</span></span></a>` : ''}
        <section class="card">
          <div class="label">發現問題、專家或客戶有新說法？</div>
          <div class="row"><input type="text" id="changeText" style="flex:1" placeholder="例：店長說兼職人員也有特休、實作時發現餘額算錯…">
            <button class="btn" id="changeBtn">交給 AI 判斷</button></div>
          <div class="small muted" style="margin-top:6px">AI 會判斷要回哪一步、影響多大，先提出方案，不會直接改。</div>
        </section>
        ${past.length ? `<details class="past"><summary>之前的關卡（${past.length}）</summary>${past.map(x => `<a href="#/r/${enc(x.path)}/finish">${esc(x.date)} ${esc(stepName(x))}${x.counts && !x.counts.open ? ' ✓' : ''}</a>`).join('')}</details>` : ''}
      </section>
    </div>`;
  bindWaiting();
  const sa = $('#showAi'); if (sa) sa.onclick = () => openAi();
  const ds = $('#doStep');
  if (ds) ds.onclick = () => {
    const n = designDone ? 6 : h.next.n;
    runAi(slice, `第 ${n} 步`, `/domain-step ${n} ${slice}`);
  };
  const gb = $('#goBack');
  if (gb) gb.onclick = () => { const r0 = h.reviews[0]; runAi(slice, '回頭修改', `/domain-change 依審查頁 ${r0.path} 的作答回頭修改設計：照你上一次處理這份審查頁時列出的項目（要改的步驟、要開的 EQ、要重跑的測試）`, { review: r0.path }); };
  const cs = $('#contStep');
  if (cs) cs.onclick = () => { const n = Math.max(0, ...stepNums(h.reviews[0])); runAi(slice, `第 ${n} 步`, `/domain-step ${n} ${slice}`); };
  const ff = $('#finishFreeze');
  if (ff) ff.onclick = () => { const n = h.next.n; runAi(slice, `凍結 0${n}`, `/domain-freeze ${n} ${slice}`); };
  const ho = $('#handover');
  if (ho) ho.onclick = () => { const r0 = h.reviews[0]; runAi(slice, `審查 ${r0.step}`, `審查好了。審查頁：${r0.path}`, { review: r0.path }); };
  const fz = $('#freeze');
  if (fz) fz.onclick = () => { const r0 = h.reviews[0]; runAi(slice, `凍結 ${r0.step}`, `/domain-freeze ${stepNums(r0).join(',')} ${slice}`, { review: r0.path }); };
  const cb = $('#changeBtn');
  const change = () => { const v = $('#changeText').value.trim(); if (v) runAi(slice, '修改', `/domain-change ${v}`); };
  cb.onclick = change;
  $('#changeText').onkeydown = e => { if (e.key === 'Enter') change(); };
}
