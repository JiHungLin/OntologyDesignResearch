// AI 對話：session、右側抽屜、等待與進行中的卡片
import { $, $$, api, CIRCLED, enc, esc, go, inline, LEVEL_NAME, md, plain, remember, state, stepName, toast } from './core.js';
import { showDrawer } from './files.js';
import { markNav } from './nav.js';
import { loadProject, nextOfProject } from './overview.js';
import { route } from './main.js';

// ---------- AI session ----------
// 範圍（scope）：規劃用 _plan，其他用切片代號。一個範圍同一時間一個使用中的 session。
// 換一件事（用途不同）或 session 經過摘要壓縮時，用選擇題問要不要開新的（精簡版「換 session 的時機」）。

export function sessionOf(scope) { return state.sessions.find(s => s.slice === scope && s.status === '使用中'); }
// AI 抽屜跟著「最後交給 AI 的範圍」走，換頁不會斷；頁面自己的範圍是 state.scope
export function aiScope() { return state.aiScope || state.scope; }
export function curSession() { return sessionOf(aiScope()); }
export function scopeName(scope) { return scope === '_plan' ? '規劃' : scope; }

export async function refreshSessions() {
  const r = await api('/api/sessions');
  state.sessions = r.sessions;
  state.gitignored = r.gitignored;
  for (const s of state.sessions) if (s.running) watch(s.id);
  renderAiHead();
}

export async function refreshSlices() {
  const st = await api('/api/status');
  state.slices = st.slices;
  markNav();
  await refreshSessions();
}

export function anyRunning() { return state.sessions.some(s => s.running); }

export function renderAiHead() {
  const s = curSession();
  const run = state.sessions.find(x => x.running);
  const ask = run && (state.approvals[run.id] || []).length;
  $('#aiDot').className = 'dot ' + (ask ? 'ask' : run ? 'busy' : s ? 'on' : '');
  $('#aiLabel').textContent = ask ? `AI 等你核准指令（${ask}）` : run ? `AI 處理中（${scopeName(run.slice)}）` : s ? 'AI 待命中' : 'AI';
}

export function openAi(scope) {
  if (scope) state.aiScope = scope;
  else if (state.scope) state.aiScope = state.scope;
  else if (!state.aiScope) {
    // 總覽頁（重新整理後）：先看正在跑的，其次是使用中的 session
    const s = state.sessions.find(x => x.running) || state.sessions.find(x => x.status === '使用中');
    if (s) state.aiScope = s.slice;
  }
  showDrawer('aiDrawer'); renderAi();
}

export async function renderAi() {
  const box = $('#aiSession');
  const warn = state.gitignored === false ? `<div class="small" style="background:var(--hint);padding:6px 10px;border-radius:10px">設計 repo 的 <code>.gitignore</code> 沒有排除 <code>.domain-web/</code>（AI session 的登記與紀錄放在這裡），請加上這一行。</div>` : '';
  if (state.pending) { box.innerHTML = warn + state.pending.html; state.pending.bind(); return; }
  const s = curSession();
  if (!aiScope()) { box.innerHTML = warn + '<div class="muted">在總覽頁時，AI 對話跟著你按的按鈕走（規劃或某條切片）。</div>'; $('#aiLog').innerHTML = ''; return; }
  if (!s) { box.innerHTML = warn + `<div><b>${esc(scopeName(aiScope()))}</b> 還沒有 AI session。按畫面上的按鈕交給 AI 時會自動開一個。</div>`; $('#aiLog').innerHTML = ''; return; }
  box.innerHTML = warn + `<div><b>${esc(scopeName(s.slice) === s.purpose ? s.purpose : scopeName(s.slice) + '・' + s.purpose)}</b>（第 ${s.turns} 次）${s.running ? '　<span class="chip turn">處理中</span>' : ''}</div>
    <div class="small muted">不用自己關 session：做下一件事時，網頁會自己開新的或問你。</div>
    <details class="tech"><summary>進階：在 terminal 接著做、結束 session</summary>
      <div style="margin:6px 0"><code>claude --resume ${esc(s.id)}</code></div>
      <button class="btn small-btn" id="endSession" ${s.running ? 'disabled' : ''}>結束這個 session</button></details>`;
  $('#endSession').onclick = async () => { await api(`/api/sessions/${s.id}/end`, {}); await refreshSessions(); renderAi(); };
  const ev = await api(`/api/sessions/${s.id}/events`);
  const log = $('#aiLog');
  log.innerHTML = '';
  ev.events.slice(-300).forEach(showEvent);
  log.dataset.sid = s.id;
  log.dataset.n = ev.n;
  renderAiNext(s);
}

// AI 對話下方的「接下來」：AI 在問問題就放選項按鈕；不然依檔案算出現在輪到誰、給一個按鈕帶過去
// AI 在跑時：輸入框上方顯示「正在處理」與最新一個步驟，輸入框暫時不能送（伺服器也一次只收一件）
export function liveText() {
  if (!state.lastTool) return '準備中…';
  const [name, ...rest] = state.lastTool.split(' ');
  return `${TOOL_NAME[name] || name}：${rest.join(' ').slice(0, 120)}`;
}
export function setAiBusy(busy) {
  $('#aiInput').disabled = !!busy;
  $('#aiSend').disabled = !!busy;
  $('#aiInput').placeholder = busy ? 'AI 正在處理，做完才能再交代下一件' : '畫面上的按鈕涵蓋不到的事，才在這裡打字（Enter 送出，Shift+Enter 換行）';
}

export async function renderAiNext(s) {
  const box = $('#aiNext');
  box.innerHTML = '';
  setAiBusy(s && s.running);
  const aps = s && s.running ? state.approvals[s.id] || [] : [];
  if (aps.length) { approvalCards(box, s, aps); return; }
  if (s && s.running) {
    box.innerHTML = `<div class="ai-busy"><span class="spinner"></span><div><b>AI 正在處理</b>，做完會在這裡通知你，畫面也會自動更新。
      <div class="small muted" id="aiLive">${esc(liveText())}</div></div></div>`;
    return;
  }
  if (!s || state.pending) return;
  const ask = parseAsk(s.last_reply);
  if (ask) {
    box.innerHTML = `<div class="label">AI 在等你回答${ask.length > 1 ? `（${ask.length} 題，每題選一個再送出）` : '，點一個'}</div>${askHtml(ask, false)}
      ${ask.length > 1 ? '<button class="btn primary" data-asksend disabled style="margin-top:8px">送出答案</button>' : ''}
      <div class="small muted">都不是的話，直接在下面打字回覆。</div>`;
    bindAsk(box, ask, v => runAi(s.slice, s.purpose, v, { keep: true }));
    return;
  }
  const P = await loadProject();
  const N = nextOfProject(P);
  const it = N.item;
  const step = it && it.f && it.f.next ? `${CIRCLED[it.f.next.n]} ${LEVEL_NAME[it.f.next.n]}` : '';
  const act = {
    start: ['寫主題草案', '#/start'],
    'plan-ai': ['請 AI 規劃', '#/'],
    plan: ['看規劃：補資料、看草稿、同意地圖', '#/plan'],
    review: it && it.f.review && [`開始審查 ${it.code} ${stepName(it.f.review)}`, `#/r/${enc(it.f.review.path)}`],
    slice: it && [`到 ${it.code} 首頁，交給 AI 做 ${step}`, `#/s/${enc(it.code)}`],
    pick: it && ['開始下一條切片：' + it.code, `#/new/${enc(it.code)}`],
  }[N.kind];
  if (!act) return;
  box.innerHTML = `<div class="label">接下來</div><a class="btn primary" href="${act[1]}" id="aiNextGo">${esc(act[0])} ›</a>
    <div class="small muted" style="margin-top:6px">在網頁上按就好，不用貼 AI 寫的指令；需要新的 session 時網頁會自己開。</div>`;
  // 抽屜蓋在主畫面上時，按了先收起抽屜，才看得到帶過去的頁面
  $('#aiNextGo').onclick = e => { e.preventDefault(); if (!document.body.classList.contains('drawer-push')) $('#aiDrawer').hidden = true; go(act[1]); };
}

// 交給 AI 的唯一入口：scope 範圍、purpose 用途、message 要說的話
export const LONG_TURNS = 12;   // 同一個 session 來回這麼多次，就建議開新的（精簡版「換 session 的時機」）

export async function runAi(scope, purpose, message, opts = {}) {
  await refreshSessions();
  const s = sessionOf(scope);
  state.aiScope = scope;
  if (s && s.running) { openAi(scope); toast('AI 還在處理上一件事，做完再交下一件'); return; }
  // 整個設計 repo 一次只跑一件（共用同一份檔案與 git）；伺服器也會擋
  const other = state.sessions.find(x => x.running && x.slice !== scope);
  if (other) { openAi(other.slice); toast(`AI 正在做「${scopeName(other.slice)}・${other.purpose}」，做完再交下一件（同一個 repo 一次只跑一件）`); return; }
  const long = s && s.turns >= LONG_TURNS;
  // AI 自己在上一次回覆建議「下一件事開新的 session」：照它的建議問人，不默默接著用
  const advised = s && advisesNew(s.last_reply);
  const same = s && s.purpose === purpose && !s.compacted && !long && !advised;
  if (same || (s && opts.keep)) return send(s, message, opts);
  if (!s) return startNew(scope, purpose, message, opts);
  // 舊的 session 停下來問了選擇題、人還沒回：開新的會讓那些問題沒人接，建議先回答
  const p = pendingAsk(scope);
  if (p) {
    const qs = p.ask.map(a => a.q).filter(Boolean);
    state.pending = {
      html: `<div class="card hint" style="padding:12px 14px"><b>「${esc(s.purpose)}」的 AI 還在等你回答${qs.length ? `：${qs.map(q => `「${esc(plain(q).slice(0, 40))}」`).join('、')}` : ''}。</b>
        現在交代「${esc(purpose)}」會換一個新的 session，舊的問題就沒人接了。
        <div class="row" style="margin-top:8px"><button class="btn primary" id="answerFirst">A（建議）：先回答 AI 的問題</button><button class="btn" id="skipAsk">B：不回答，照樣做這件事</button></div></div>`,
      bind() {
        $('#answerFirst').onclick = () => { state.pending = null; renderAi(); };
        $('#skipAsk').onclick = () => { remember(p.key, '1'); state.pending = null; runAi(scope, purpose, message, opts); };
      },
    };
    return openAi(scope);
  }
  // 用途不同、壓縮過或已經很長：用選擇題問人（建議開新的，新的 session 由檔案產生交接提示，不用人貼）
  const why = s.compacted ? '現在的 session 經過摘要壓縮，容易憑記憶回答'
    : advised ? `AI 上一次回覆建議下一件事開新的 session（現在的 session 是「${esc(s.purpose)}」，來回 ${s.turns} 次）`
    : s.purpose !== purpose ? `現在的 session 是「${esc(s.purpose)}」，這件事是「${esc(purpose)}」`
    : `現在的 session 已經來回 ${s.turns} 次，內容很長`;
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

export function advisesNew(reply) { return /開新的?\s*session|新的\s*session\s*(做|比較)/i.test(reply || ''); }

export async function startNew(scope, purpose, message, opts, handoffText) {
  try {
    if (handoffText === undefined) handoffText = (await api(`/api/handoff?slice=${enc(scope)}&purpose=${enc(purpose)}&review=${enc(opts.review || '')}`)).text;
    // 交接提示叫 AI 先讀檔、執行 /domain-status；接著做這件事，不用再等一輪
    const first = handoffText.replace(/讀完後執行 \/domain-status，用一句話說明現在的狀態與下一步，等我指示。/, '讀完後執行 /domain-status，然後做下面這件事。') + '\n\n' + message;
    const s = await api('/api/sessions', { slice: scope, purpose, handoff: handoffText });
    await refreshSessions();
    return send(s, first, opts);
  } catch (e) { toast(e.message); }
}

export async function send(s, text, opts = {}) {
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
// AI 要執行允許清單之外的指令（第 ⑥ 步的 docker、pytest、tools/run_evidence.py…）：停下來等人核准，一次一條
// （docs/01 ⑥「實作指令與執行紀錄」；網頁這邊由 approve_mcp.py 轉過來，終端機則是 Claude Code 自己問）
function approvalCards(box, s, aps) {
  setAiBusy(true);
  const a = aps[0];
  const inp = a.input || {};
  const cmd = inp.command || inp.file_path || JSON.stringify(inp, null, 2);
  const who = remember('reviewer') || '';
  box.innerHTML = `<div class="approve-card">
    <div class="label">AI 要執行這條指令，等你核准${aps.length > 1 ? `（還有 ${aps.length - 1} 條在排隊）` : ''}</div>
    ${inp.description ? `<p style="margin:4px 0 6px"><b>用途：</b>${esc(inp.description)}</p>` : ''}
    <pre class="cmd">${esc(cmd)}</pre>
    <p class="small muted" style="margin:6px 0">按「放行」就會在這台電腦上執行一次（${esc(TOOL_NAME[a.tool] || a.tool)}）。看不懂在做什麼、或不是這一步該做的，就不放行並寫一句原因，AI 會照你說的改。</p>
    <div class="row" style="gap:6px;flex-wrap:wrap"><input type="text" id="apWho" class="soft" style="flex:0 1 140px" value="${esc(who)}" placeholder="核准人（執行者）">
      <input type="text" id="apWhy" class="soft" style="flex:1 1 200px" placeholder="（不放行時）原因或要它怎麼做"></div>
    <div class="row" style="margin-top:8px;gap:8px"><button class="btn primary" id="apYes">放行這一次</button><button class="btn" id="apNo">不放行</button></div></div>`;
  const go_ = async allow => {
    const by = $('#apWho').value.trim();
    if (!by) { toast('請填核准人（就是 ⑥ 的執行者）'); $('#apWho').focus(); return; }
    remember('reviewer', by);
    try { await api(`/api/sessions/${s.id}/approvals/${a.id}`, { allow, message: $('#apWhy').value.trim(), by }); }
    catch (e) { toast(e.message); }
    state.approvals[s.id] = aps.slice(1);
    renderAiHead(); renderAiNext(s);
  };
  $('#apYes').onclick = () => go_(true);
  $('#apNo').onclick = () => go_(false);
}

async function pollApprovals(sid) {
  let ap;
  try { ap = (await api(`/api/sessions/${sid}/approvals`)).pending; } catch (e) { return; }
  const before = (state.approvals[sid] || []).map(x => x.id).join();
  state.approvals[sid] = ap;
  if (ap.map(x => x.id).join() === before) return;
  renderAiHead();
  if (ap.length) {
    if ($('#aiDrawer').hidden) openAi((state.sessions.find(x => x.id === sid) || {}).slice);
    else renderAiNext(state.sessions.find(x => x.id === sid));
    toast('AI 要執行一條指令，等你核准');
  }
}

export function watch(sid, onEvent) {
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
    const aiLive = $('#aiLive');
    if (aiLive) aiLive.textContent = liveText();
    else if (r.running && shown && !$('.ai-busy')) renderAiNext(sessionOf(state.aiScope) || curSession());
    if (r.running) { await pollApprovals(sid); w.timer = setTimeout(tick, 1500); return; }
    state.approvals[sid] = [];
    w.timer = null; w.onEvent = null;
    await refreshSessions();
    if (!$('#aiDrawer').hidden) renderAi();
    if (!w.quietDone) { toast('AI 做完了，畫面已更新'); route(); }
    w.quietDone = false;
  };
  w.timer = setTimeout(tick, 300);
}

// 行內問 AI：答案顯示在題目旁邊；用這條切片目前的 session，只解釋不改檔
export async function askAi(text, out) {
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

export function curPurpose() {
  const m = (state.path || '').match(/_([^/]+)\.md$/);
  return m ? `審查 ${m[1]}` : '設計';
}

// AI 對話的呈現（像 Claude）：你說的話是泡泡、AI 說的話照 Markdown 排版；讀檔、改檔、指令、子代理這些內部步驟收成一行，點開才看
export const TOOL_NAME = { Read: '讀檔', Edit: '改檔', MultiEdit: '改檔', Write: '寫檔', Bash: '執行指令', Grep: '搜尋文字', Glob: '找檔案',
  Agent: '子代理', Task: '子代理', Skill: '技能', WebSearch: '搜尋網路', WebFetch: '讀網頁', TodoWrite: '待辦清單', NotebookEdit: '改筆記本' };

export function stepsGroup(log) {
  let g = log.lastElementChild;
  if (!g || !g.classList.contains('steps')) {
    g = document.createElement('details');
    g.className = 'steps';
    g.innerHTML = '<summary></summary><div class="step-list"></div>';
    log.appendChild(g);
  }
  return g;
}

export function addStep(log, html, name) {
  const g = stepsGroup(log);
  g.querySelector('.step-list').insertAdjacentHTML('beforeend', `<div data-name="${esc(name)}">${html}</div>`);
  const items = [...g.querySelectorAll('.step-list > div')];
  const names = [...new Set(items.map(x => x.dataset.name))];
  g.querySelector('summary').textContent = `${items.length} 個步驟：${names.slice(0, 4).join('、')}${names.length > 4 ? '…' : ''}`;
}

export function showEvent(ev) {
  const log = $('#aiLog');
  if (ev.kind === 'me') {
    state.lastText = '';
    // 新 session 的第一則是「交接提示＋要做的事」：泡泡只放最後一段，整段收起來
    const paras = ev.text.trim().split(/\n\s*\n/);
    const last = paras[paras.length - 1];
    log.insertAdjacentHTML('beforeend', paras.length > 1 && ev.text.length > 300
      ? `<div class="me"><div>${inline(last.length > 400 ? last.slice(0, 400) + '…' : last)}</div><details class="small"><summary>交接提示與完整內容</summary><div class="md">${md(ev.text)}</div></details></div>`
      : `<div class="me">${inline(ev.text.length > 800 ? ev.text.slice(0, 800) + '…' : ev.text)}</div>`);
  }
  else if (ev.kind === 'text' && ev.sub) addStep(log, `<div class="sub-text">${inline(ev.text)}</div>`, '子代理');
  else if (ev.kind === 'text') { log.insertAdjacentHTML('beforeend', `<div class="t md">${md(ev.text)}</div>`); state.lastText = ev.text; }
  else if (ev.kind === 'tool') addStep(log, `<b>${esc(TOOL_NAME[ev.name] || ev.name)}</b> <code>${esc(ev.brief || '')}</code>`, ev.sub ? '子代理' : (TOOL_NAME[ev.name] || ev.name));
  else if (ev.kind === 'approval') log.insertAdjacentHTML('beforeend', `<div class="${ev.allow ? 'ok-line' : 'deny'} small">${ev.allow ? '✓ 放行' : '✗ 不放行'}（${esc(ev.by || '')}）：<code>${esc(ev.brief || '')}</code>${ev.message ? `　${esc(ev.message)}` : ''}</div>`);
  else if (ev.kind === 'compacted') log.insertAdjacentHTML('beforeend', '<div class="deny">這個 session 剛經過摘要壓縮，建議做完這一段就開新的 session。</div>');
  else if (ev.kind === 'error') log.insertAdjacentHTML('beforeend', `<div class="err">${esc(ev.text)}</div>`);
  else if (ev.kind === 'result') {
    // 被擋下的指令收成一塊：AI 多半會改用別的方法繼續，結果真的缺東西才要處理
    const dn = ev.denials || [];
    if (dn.length) log.insertAdjacentHTML('beforeend', `<details class="deny"><summary>這一輪有 ${dn.length} 個指令被網頁的權限擋下</summary>
      <p class="small" style="margin:6px 0">包括你在核准卡片上選「不放行」的，和網頁一定擋的（自己寫的 python）。AI 通常會改用別的方法繼續；只有它最後說缺了什麼、做不完時才需要處理。</p>
      <ul class="small">${dn.map(d => `<li><code>${esc(d.tool)}</code> ${esc(((d.input || {}).command || JSON.stringify(d.input || '')).slice(0, 200))}</li>`).join('')}</ul></details>`);
    if (!ev.ok) log.insertAdjacentHTML('beforeend', `<div class="err">${esc(ev.text)}</div>`);
    else if (ev.text && ev.text.trim() !== (state.lastText || '').trim()) log.insertAdjacentHTML('beforeend', `<div class="t md">${md(ev.text)}</div>`);
    log.insertAdjacentHTML('beforeend', '<div class="turn-end"></div>');
  }
  log.scrollTop = log.scrollHeight;
}

// AI 最後一則回覆裡的選擇題（WEB_PROMPT 要它照「問題／例子／A（建議）／B／其他」寫）；
// 一則回覆可能問好幾題，每個「問題：」開始新的一題。回傳 [{q, ex, opts}]，沒有選擇題回 null
export function parseAsk(text) {
  const lines = String(text || '').split('\n').map(l => l.replace(/^\s*[-*]\s*/, '').replace(/\*\*/g, '').trim());
  const qs = [];
  let cur = null;
  const open = () => (cur = cur || (qs.push({ q: '', ex: '', opts: [] }), qs[qs.length - 1]));
  for (const l of lines) {
    let m;
    if ((m = l.match(/^問題[：:]\s*(.+)$/))) { qs.push(cur = { q: m[1], ex: '', opts: [] }); }
    else if ((m = l.match(/^例子[：:]\s*(.+)$/))) open().ex = m[1];
    else if ((m = l.match(/^([A-H])(（建議）)?[：:]\s*(.+)$/))) {
      const [sum, out] = m[3].split(/\s*→\s*/);
      open().opts.push({ key: m[1], rec: !!m[2], sum, out: out || '' });
    }
  }
  const ok = qs.filter(x => x.opts.length >= 2);
  return ok.length ? ok : null;
}

// 範圍內的 session 停下來問了選擇題、人還沒回（也沒按「不用回了」）
export function pendingAsk(scope) {
  const s = sessionOf(scope);
  if (!s || s.running || !s.last_reply) return null;
  const key = 'seen:' + s.id + ':' + s.last_at;
  const ask = parseAsk(s.last_reply);
  return ask && !remember(key) ? { s, ask, key } : null;
}

// 選擇題的按鈕：一題時點了就送；好幾題時每題各選一個，再按「送出」一起回
export function askHtml(ask, big) {
  const many = ask.length > 1;
  return ask.map((a, i) => `<div class="ask-q" data-qi="${i}">
    ${a.q ? (big ? `<h2 style="margin:6px 0">${many ? `${i + 1}. ` : ''}${inline(a.q)}</h2>` : `<div class="label">${many ? `${i + 1}. ` : ''}${inline(a.q)}</div>`) : ''}
    ${a.ex && big ? `<div class="box"><div class="label">舉個例子</div>${inline(a.ex)}</div>` : ''}
    <div class="${big ? 'opts' : 'ai-opts'}" ${big ? 'style="margin-top:10px"' : ''}>${a.opts.map(o => big
      ? `<button class="opt ${o.rec ? 'rec' : ''}" data-reply="${o.key}"><span class="row spread"><span class="k">${o.key}</span>${o.rec ? '<span class="badge-rec">★ AI 建議</span>' : ''}</span><span class="sum">${inline(o.sum)}</span>${o.out ? `<span class="out">選了之後：${inline(o.out)}</span>` : ''}</button>`
      : `<button class="opt ${o.rec ? 'rec' : ''}" data-reply="${o.key}"><span class="row spread"><b>${o.key}</b>${o.rec ? '<span class="badge-rec">★ 建議</span>' : ''}</span><span>${inline(o.sum)}</span></button>`).join('')}</div></div>`).join('');
}

// 綁定 askHtml 的按鈕；text 是「都不是？寫一句」的輸入框（可省略），send(回覆文字)
export function bindAsk(box, ask, send, text) {
  const pick = ask.map(() => '');
  const compose = extra => {
    const ans = ask.map((a, i) => pick[i] ? `第 ${i + 1} 題（${plain(a.q).slice(0, 30)}）：${pick[i]}` : '').filter(Boolean);
    return [ans.join('\n'), extra ? (ans.length ? '補充：' : '') + extra : ''].filter(Boolean).join('\n');
  };
  $$('.ask-q', box).forEach(qb => {
    const i = +qb.dataset.qi;
    $$('[data-reply]', qb).forEach(b => b.onclick = () => {
      if (ask.length === 1) return send(b.dataset.reply);
      pick[i] = b.dataset.reply;
      $$('[data-reply]', qb).forEach(x => x.classList.toggle('picked', x === b));
      const go = $('[data-asksend]', box);
      if (go) go.disabled = pick.some(x => !x) && !(text && text.value.trim());
    });
  });
  const go = $('[data-asksend]', box);
  const fire = () => {
    const extra = text ? text.value.trim() : '';
    if (ask.length > 1 && pick.some(x => !x) && !extra) return toast('每一題都選一個，或在下面寫一句');
    const v = ask.length > 1 ? compose(extra) : extra;
    if (v) send(v);
  };
  if (go) go.onclick = fire;
  if (text) {
    text.onkeydown = e => { if (e.key === 'Enter') fire(); };
    if (go) text.oninput = () => { go.disabled = ask.length > 1 && pick.some(x => !x) && !text.value.trim(); };
  }
}

// 「AI 在等你」：範圍內的 session 最後一則回覆；有選擇題就做成按鈕
export const TERMINAL_HINT = /新\s*session|session.*貼|貼上面|claude --resume|\/domain-[a-z-]+/i;

export function waitingCard(scope) {
  const s = sessionOf(scope);
  if (!s || s.running || !s.last_reply) return '';
  const key = 'seen:' + s.id + ':' + s.last_at;
  if (remember(key)) return '';
  const ask = parseAsk(s.last_reply);
  if (!ask) {
    // 摘要用回覆的第一句（通常是「做完了什麼」），不用最後一句：最後常是「開新 session、貼這段、執行 /domain-…」這種 terminal 的做法，在網頁上不用照做
    const lines = s.last_reply.split('\n').map(x => x.trim()).filter(x => x && !/^(#|\||>|```)/.test(x));
    const first = lines.find(x => !TERMINAL_HINT.test(x)) || '';
    const said = s.last_reply.length > 1500 ? s.last_reply.slice(-1500) : s.last_reply;
    return `<details class="card waiting quiet" data-scope="${esc(scope)}"><summary><span class="chip">AI 做完了</span> ${esc(plain(first).slice(0, 120))}</summary>
      ${TERMINAL_HINT.test(said) ? '<div class="small" style="margin:8px 0">AI 回覆裡提到開新 session、貼交接文字或打 <code>/domain-…</code> 指令的地方，在網頁上都不用做：照畫面上的按鈕走，需要新的 session 網頁會自己開。</div>' : ''}
      <div class="ai-said">${md(said)}</div>
      <div class="row" style="margin-top:10px"><input type="text" class="soft" data-replytext style="flex:1" placeholder="回覆 AI（例：好，繼續）"><button class="btn primary" data-replysend>送出</button><button class="btn ghost small-btn" data-seen="${esc(key)}">收起來</button></div></details>`;
  }
  const many = ask.length > 1;
  return `<section class="card lift waiting asking" data-scope="${esc(scope)}">
    <div class="row spread"><span class="chip turn">AI 在等你回答${many ? `：${ask.length} 題，每題選一個再送出` : ''}</span><button class="btn ghost small-btn" data-seen="${esc(key)}">不用回了</button></div>
    <p class="small muted" style="margin:6px 0 0">AI 停在這裡等你（${esc(s.purpose)}）。先回答，它才會接著做完；這時去按別的事，會開新的 session，這些問題就沒人接。</p>
    ${askHtml(ask, true)}
    <div class="ask-other"><label class="label">${many ? '補充，或都不是（可省略）' : '其他：都不是的話，寫一句'}</label>
      <div class="row"><input type="text" class="soft" data-replytext style="flex:1" placeholder="${many ? '補充或都不是？寫一句（可省略）' : '都不是？寫一句'}"><button class="btn primary" data-asksend ${many ? 'disabled' : ''}>送出</button></div></div>
  </section>`;
}

export function bindWaiting() {
  $$('.waiting').forEach(card => {
    const scope = card.dataset.scope;
    const s = sessionOf(scope);
    const reply = v => runAi(scope, s.purpose, v, { keep: true });
    const inp = $('[data-replytext]', card);
    const ask = parseAsk(s.last_reply);
    if (ask) bindAsk(card, ask, reply, inp);
    else {
      const go1 = () => { const v = inp.value.trim(); if (v) reply(v); };
      $('[data-replysend]', card).onclick = go1;
      inp.onkeydown = e => { if (e.key === 'Enter') go1(); };
    }
    // 「不用回了」之後首頁要換回原本的關卡按鈕，所以重畫整頁
    $('[data-seen]', card).onclick = () => { remember($('[data-seen]', card).dataset.seen, '1'); card.classList.contains('asking') ? route() : card.remove(); };
  });
}

// 「AI 正在做…」：範圍內有背景工作時顯示
export function runningCard(scope, what) {
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
