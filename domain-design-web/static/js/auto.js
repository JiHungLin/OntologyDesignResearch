// 全自動：開始、停止、中斷跑步器（tools/auto_run.py），看每一圈做了什麼
import { $, $$, api, CIRCLED, enc, esc, go, inline, md, setTop, state, toast } from './core.js';
import { addStep, renderAi, renderAiHead, runAi, TOOL_NAME } from './ai.js';
import { markNav, refreshNav } from './nav.js';
import { loadProject, planSlices, showTopic } from './overview.js';
import { route } from './main.js';

let timer = null;
let page = 1;   // 「每一圈」的第幾頁（一頁 25 圈，新到舊）

// 碰到用量上限時跑步器等到重置再接著跑（tools/auto_run.py），state.json 的 waiting_until 是要等到幾點
export const waitText = st => st && st.running && st.waiting_until
  ? `用量到上限，等到 ${esc(st.waiting_until.replace('T', ' ').slice(5, 16))} 重置後接著跑` : '';

export function autoBadge(st) {
  if (!st || !st.running) return '';
  return `<a class="brand-sub auto-live" href="#/auto" title="全自動正在跑，點這裡看進度">全自動執行中・第 ${st.round || 1} 圈${waitText(st) ? '（等用量重置）' : ''}${st.stopping ? '（這圈做完停）' : ''}</a>`;
}

function pager(pages) {
  if (pages <= 1) return '';
  const btn = (n, label) => `<button class="btn small-btn" data-page="${n}" ${n < 1 || n > pages || n === page ? 'disabled' : ''}>${label}</button>`;
  return `<div class="row auto-pager">${btn(1, '最新')}${btn(page - 1, '‹ 較新')}<span class="small">第 ${page} / ${pages} 頁</span>${btn(page + 1, '較舊 ›')}${btn(pages, '最舊')}</div>`;
}

function stateLine(st) {
  if (st.running && waitText(st)) return `<b>執行中・${waitText(st)}</b>${st.stopping ? '，<b>按了關閉，馬上停</b>' : ''}<div class="small muted">這一圈被上限切掉，重置後下一圈先收拾做到一半的；不想等就按「關閉全自動」。</div>`;
  if (st.running) return `<b>執行中</b>：第 ${st.round || 1} 圈（從 ${esc((st.round_started || st.started || '').replace('T', ' '))} 開始）${st.stopping ? '，<b>這一圈做完就停</b>' : ''}`
    + `${st.last ? `<div class="small muted">上一圈：${inline(st.last)}</div>` : ''}`;
  if (!st.started) return '還沒有從這裡跑過。';
  const tidy = st.interrupted || /^沒有回報結果/.test(st.last || '') ? '<div class="small">上一次做到一半被切斷，下次開始時第一圈會先收拾（把那個動作做完或還原）。</div>' : '';
  return `<b>已停下來</b>（${esc((st.ended || '').replace('T', ' '))}，跑了 ${st.round || 0} 圈）：${inline(st.reason || '')}${tidy}`;
}

export async function renderAuto(log) {
  clearTimeout(timer);
  state.scope = '_plan';
  markNav();
  setTop(['#/plan', '規劃'], '<strong>全自動</strong>');
  const [P, A] = await Promise.all([loadProject(), api(`/api/auto?page=${page}`)]);
  const pages = Math.max(1, Math.ceil(A.total / A.per));
  if (page > pages) { page = pages; return renderAuto(log); }
  const st = A.state, auto = P.plan && P.plan.auto;
  const busy = (P.slices || []).some(x => x.session && x.session.running) || (P.plan_session && P.plan_session.running);
  const cur = log || st.log || (A.rounds[0] || {}).log;
  $('#app').innerHTML = `
    <section class="card lift" id="a-ctl">
      <h2 style="margin:0">全自動</h2>
      <p class="muted small" style="margin:4px 0 10px;max-width:52em">一圈開一個新的 AI session、只做一個動作（寫一步、凍結、回頭修改），人的關卡由 AI 代答並標「AI（自動）」。
        跑的時候網頁不能作答、不能開 AI 工作（兩邊共用同一份檔案與 git）。跑步器不依賴網頁：關掉網頁或重開伺服器它照樣跑，終端機也能執行 <code>python3 tools/auto_run.py</code>。</p>
      <div style="margin-bottom:10px">${stateLine(st)}</div>
      ${!auto ? '<p class="small">執行模式是手動。要全自動，先到<a href="#/plan">規劃頁</a>最下面改成全自動。</p>' : st.running ? `
        <div class="row">
          <button class="btn primary" id="aStop" ${st.stopping ? 'disabled' : ''}>${st.stopping ? '這一圈做完就關閉' : '關閉全自動（這一圈做完後）'}</button>
          <button class="btn" id="aKill">強制中斷…</button></div>
        <p class="muted small" style="margin:6px 0 0">平常用「關閉全自動」：等這一圈做完、檔案和紀錄都寫好才停。執行模式不變，之後可以再開始。</p>
        <div class="card" id="aKillBox" hidden style="margin-top:10px;background:#FFE8D6">
          <b>確定要強制中斷？</b>
          <p class="small" style="margin:4px 0">這一圈的 AI 和它正在跑的指令會馬上結束，可能停在一組修改的中間：例如規則改了但 CHANGELOG 還沒記、凍結時 commit 了還沒打 tag、<code>core/</code> 只同步一半、⑥ 的容器沒關。
            做到一半的修改留在工作區；被切斷的 git 留下的鎖會刪掉。下次開始全自動時，第一圈會先看 git 的狀態，把那個動作做完或還原，再往下做。</p>
          <p class="small" style="margin:4px 0">只在 AI 明顯卡住、或方向錯了要馬上停時用。</p>
          <div class="row"><button class="btn" id="aKillYes" style="border-color:#c0392b;color:#c0392b">確認強制中斷</button><button class="btn" id="aKillNo">不要，回去</button></div></div>` : `
        <div class="row">
          <label class="small">最多 <input type="number" id="aMax" value="${st.max_steps || 40}" min="1" max="200" style="width:5em"> 圈</label>
          <label class="small"><input type="checkbox" id="aUntil" ${st.until_design_done === false ? '' : 'checked'}> 有一條切片 ⑤ 凍結（設計完成，含回頭修改後重新凍結）就停，讓我先看 AI 代答的審查頁</label>
          <button class="btn primary go" id="aStart" ${busy ? 'disabled' : ''}>開始全自動</button></div>
        ${busy ? '<p class="small">AI 正在做網頁上的工作，做完再開始。</p>' : ''}
        <p class="muted small" style="margin:6px 0 0">也會在這些情況停下來：AI 回報「完成」或「需要人」、連續兩圈沒有任何改變、碰到禁止清單、用量上限。</p>`}
    </section>
    <section class="card" style="margin-top:12px">
      <div class="row spread"><h2 style="margin:0">${cur ? `這一圈的 AI 對話 <span class="muted small">${esc(cur)}</span>` : 'AI 對話'}</h2>
        ${cur && st.running && cur !== st.log ? '<a class="small" href="#/auto">回到正在跑的那一圈</a>' : ''}</div>
      <div class="ai-log auto-log" id="aLog">${cur ? '' : '<p class="muted small">還沒有紀錄。</p>'}</div>
    </section>
    <section class="card" style="margin-top:12px">
      <div class="row spread"><h2 style="margin:0 0 6px">每一圈（新到舊${A.total ? `，共 ${A.total} 圈` : ''}）</h2>${pager(pages)}</div>
      ${A.rounds.length ? `<ol class="auto-rounds small" reversed start="${A.total - (page - 1) * A.per}">${A.rounds.map(r => `<li${r.log === cur ? ' class="on"' : ''}>${r.log ? `<a href="#/auto/${encodeURIComponent(r.log)}">${inline(r.text)}</a>` : inline(r.text)}</li>`).join('')}</ol>${pager(pages)}` : '<p class="muted small">還沒有跑過。</p>'}
    </section>
    ${A.denied.length ? `<section class="card" style="margin-top:12px"><h2 style="margin:0 0 6px">被禁止清單擋下的（新到舊）</h2>
      <ul class="small">${A.denied.map(d => `<li>${esc((d.at || '').replace('T', ' ').slice(0, 19))}　<code>${esc(d.tool)}</code> ${esc(String(d.what || '').slice(0, 200))}<div class="muted">${esc(d.reason || '')}</div></li>`).join('')}</ul></section>` : ''}`;
  $$('.auto-pager button').forEach(b => b.onclick = () => { page = +b.dataset.page; renderAuto(log); });
  const post = async (url, body, msg) => { try { await api(url, body || {}); toast(msg); renderAuto(); } catch (e) { toast(e.message); } };
  if ($('#aStart')) $('#aStart').onclick = () => post('/api/auto/start', { max_steps: +$('#aMax').value || 40, until_design_done: $('#aUntil').checked }, '全自動開始了');
  if ($('#aStop')) $('#aStop').onclick = () => post('/api/auto/stop', null, '這一圈做完就關閉全自動');
  if ($('#aKill')) $('#aKill').onclick = () => { $('#aKillBox').hidden = false; $('#aKill').disabled = true; };
  if ($('#aKillNo')) $('#aKillNo').onclick = () => { $('#aKillBox').hidden = true; $('#aKill').disabled = false; };
  if ($('#aKillYes')) $('#aKillYes').onclick = () => { $('#aKillYes').disabled = true; post('/api/auto/interrupt', null, '已強制中斷；下次開始時第一圈先收拾'); };
  if (cur) follow($('#aLog'), cur, st.running, () => renderAuto());
}

// 右側「AI 對話」抽屜：全自動在跑時跟著這一圈（輸入框不能用，跑的時候網頁不開 AI 工作）
let drawerLog = null;
export function renderAutoDrawer(st) {
  $('#aiSession').innerHTML = `<div><b>全自動</b>・第 ${st.round || 1} 圈　<span class="chip turn">執行中</span>${st.stopping ? '　這一圈做完就關閉' : ''}</div>
    <div class="small muted">每一圈是一個新的 AI session；這裡跟著正在跑的那一圈。開始、關閉、看之前的圈在<a href="#/auto">全自動頁</a>。</div>`;
  $('#aiNext').innerHTML = '';
  $('#aiInput').disabled = true; $('#aiSend').disabled = true;
  $('#aiInput').placeholder = '全自動在跑，網頁不開 AI 工作；要停到全自動頁按「關閉全自動」';
  const log = $('#aiLog');
  if (drawerLog === st.log && log.dataset.auto === st.log) return;   // 已經在跟這一圈
  drawerLog = st.log;
  log.innerHTML = ''; log.dataset.auto = st.log; log.dataset.sid = '';
  follow(log, st.log, true, null, () => drawerLog === st.log && log.dataset.auto === st.log);
}

// 照 AI 對話抽屜的樣子畫一圈的事件；這一圈還在跑就每 3 秒接著讀
function follow(box, log, live, onEnd, still) {
  let n = 0;
  const tick = async () => {
    if (!document.body.contains(box) || (still && !still())) return;   // 換頁了、抽屜換成別的內容
    let r;
    try { r = await api(`/api/auto/events?log=${encodeURIComponent(log)}&after=${n}`); } catch (e) { return; }
    const atEnd = box.scrollHeight - box.scrollTop - box.clientHeight < 40;
    for (const ev of r.events) show(box, ev);
    n += r.events.length;
    if (atEnd) box.scrollTop = box.scrollHeight;
    if (r.running) { setTimeout(tick, 3000); return; }
    if (live && onEnd) { live = false; onEnd(); }   // 這一圈結束：重畫，看跑步器停了還是進到下一圈
  };
  tick();
}

function show(box, ev) {
  if (ev.kind === 'text' && ev.sub) addStep(box, `<div class="sub-text">${inline(ev.text)}</div>`, '子代理');
  else if (ev.kind === 'text') box.insertAdjacentHTML('beforeend', `<div class="t md">${md(ev.text)}</div>`);
  else if (ev.kind === 'tool') addStep(box, `<b>${esc(TOOL_NAME[ev.name] || ev.name)}</b> <code>${esc(ev.brief || '')}</code>`, ev.sub ? '子代理' : (TOOL_NAME[ev.name] || ev.name));
  else if (ev.kind === 'compacted') box.insertAdjacentHTML('beforeend', '<div class="deny">這一圈的 session 經過摘要壓縮。</div>');
  else if (ev.kind === 'result') {
    if (ev.denials && ev.denials.length) box.insertAdjacentHTML('beforeend', `<div class="deny small">擋下 ${ev.denials.length} 個指令：${ev.denials.map(d => `<code>${esc(d.tool)}</code>`).join('、')}</div>`);
    box.insertAdjacentHTML('beforeend', ev.ok ? '<div class="turn-end"></div>' : `<div class="err">${esc(ev.text)}</div>`);
  }
}

// 頂列的「全自動執行中・第 n 圈」：每 10 秒更新（跑步器不依賴網頁，停下來或進到下一圈網頁不會知道）
setInterval(async () => {
  if (!state.project || !state.project.plan || !state.project.plan.auto) return;
  try {
    const st = (await api('/api/auto')).state;
    const was = state.project.autorun || {};
    state.project.autorun = st;
    showTopic(state.project);
    if (was.running && !st.running) toast(`全自動停下來了：${st.reason || ''}`);
    // 在全自動頁上：開始、停下來、進到下一圈都重畫（跑步器不依賴網頁，網頁要自己看）
    const changed = was.running !== st.running || was.round !== st.round || was.stopping !== st.stopping || was.waiting_until !== st.waiting_until;
    if (st.running) { await pullLatest(st); const el = $('#autoLatest'); if (el && latest.text) el.textContent = '正在：' + latest.text; }
    // 開始、停下來、進到下一圈：檔案的狀態變了，整頁重畫（橫幅、鎖、切片的狀態跟著更新）；抽屜開著就跟到下一圈
    // 正在答全自動事後審查頁：只更新導覽與頂列，不重畫頁面（「其他」打到一半的字不會被清掉）
    if (changed) { if (onAutoReview()) await refreshNav(); else await route(); if (!$('#aiDrawer').hidden) renderAi(); }
    renderAiHead();
  } catch (e) { /* 伺服器暫時連不到：下次再試 */ }
}, 10000);

// ---------- 全自動在跑時，其他頁面：只能看，看得到推進到哪 ----------

export const autoOn = () => !!(state.project && state.project.autorun && state.project.autorun.running);

// 全自動正在推進的切片：①～⑤ 還沒做完、有審查頁、或 ⑥ 已開始的（同總覽的「現在在做的切片」）
export function autoSlice(P) {
  const list = planSlices(P).filter(x => x.f && x.f.next);
  return list.find(x => x.f.review || x.f.next.n <= 5 || x.f.next.status !== '未開始') || list[0] || null;
}

export function autoProgress(P) {
  const x = autoSlice(P);
  if (!x) return '規劃';
  const nx = x.f.next;
  return `${x.code} ${CIRCLED[nx.n]}${nx.status === '待檢查' ? ' 送審中（AI 代答、凍結或回頭修改）' : nx.status === '凍結中' ? ' 凍結中' : nx.status === '未開始' ? ' 還沒開始' : ' ' + nx.status}`;
}

const latest = { log: null, n: 0, text: '' };
function latestText(ev) {
  if (ev.kind === 'tool') return `${TOOL_NAME[ev.name] || ev.name}${ev.sub ? '（子代理）' : ''}：${String(ev.brief || '').slice(0, 100)}`;
  if (ev.kind === 'text' && !ev.sub) return String(ev.text).replace(/\s+/g, ' ').slice(0, 140);
  return '';
}
async function pullLatest(st) {
  if (latest.log !== st.log) { latest.log = st.log; latest.n = 0; latest.text = ''; }
  const r = await api(`/api/auto/events?log=${encodeURIComponent(st.log)}&after=${latest.n}`);
  latest.n = r.n;
  for (const ev of r.events) latest.text = latestText(ev) || latest.text;
}

export function autoBanner() {
  const P = state.project, st = P.autorun;
  return `<section class="card auto-banner" id="autoBanner"><div class="row spread"><div>
      <b>全自動執行中・第 ${st.round || 1} 圈</b>　${waitText(st) || esc(autoProgress(P))}${st.stopping ? '　（這一圈做完就關閉）' : ''}
      <div class="small" id="autoLatest">${latest.log === st.log && latest.text ? '正在：' + esc(latest.text) : ''}</div>
      <div class="small muted">人的關卡由 AI 代答，這段時間網頁只能看、不能作答或交給 AI。</div></div>
    <a class="btn" href="#/auto">看進度、關閉全自動</a></div></section>`;
}

// 每次換頁後（main.js 的 route）：在跑就在頁面最上面放橫幅、把這一頁的按鈕與輸入鎖住（伺服器也會擋）
// 全自動事後審查頁（reviews/<日期>_auto.md）在跑時也能答（docs/01 0.2「待人決定」）
const onAutoReview = () => /_auto\.md/.test(decodeURIComponent(location.hash));

export function applyAutoLock() {
  if (!autoOn() || location.hash.startsWith('#/auto') || onAutoReview()) return;
  const app = $('#app');
  if (!$('#autoBanner')) app.insertAdjacentHTML('afterbegin', autoBanner());
  lockControls();
}

function lockControls() {
  if (location.hash.startsWith('#/auto') || onAutoReview()) return;
  $$('#app button:not([disabled]), #app input:not([disabled]), #app textarea:not([disabled]), #app select:not([disabled])').forEach(el => {
    if (el.closest('#autoBanner')) return;
    el.disabled = true; el.title = '全自動執行中，只能看';
  });
}

// 有些頁面在 route 結束後還會非同步重畫（例：切片首頁讀完審查頁再畫一次）：#app 有變動就再套一次
new MutationObserver(() => { if (autoOn() && !$('#autoBanner')) applyAutoLock(); else if (autoOn()) lockControls(); })
  .observe(document.getElementById('app'), { childList: true, subtree: true });

// ---------- 全自動事後審查頁答完：一鍵交給 AI 處理（docs/01 0.2「待人決定」） ----------

export const HANDOFF_STEPS = 25;   // 處理答案＋回頭修改 ①～⑤ 大約要的圈數；⑤ 重新凍結就停

export function handoffBlock(r) {
  const P = state.project || {};
  if (P.autorun && P.autorun.running)
    return `<p class="small">全自動正在跑，下一圈就會先處理你的答案。<a href="#/auto">看進度</a></p>`;
  if (P.plan && P.plan.auto)
    return `<div class="row"><button class="btn big primary" id="handoff">交給 AI 處理<span class="arr">›</span></button></div>
      <p class="small muted">開始全自動：先處理你的答案（選 A 記成確認；其他的照你的話回頭修改），${esc(r.slice || '這條切片')} 的 ⑤ 重新凍結就停，最多 ${HANDOFF_STEPS} 圈。之後在全自動頁看進度。</p>`;
  return `<div class="row"><button class="btn big primary" id="handoff">請 AI 處理<span class="arr">›</span></button></div>
    <p class="small muted">手動模式：AI 會照你的答案回頭修改，改完照常送審給你。</p>`;
}

export function bindHandoff(r) {
  const b = $('#handoff');
  if (!b) return;
  b.onclick = async () => {
    b.disabled = true;
    const P = state.project || {};
    try {
      if (P.plan && P.plan.auto) {
        await api('/api/auto/start', { max_steps: HANDOFF_STEPS, until_design_done: true });
        toast('全自動開始了：先處理你的答案');
        go('#/auto');
      } else {
        await runAi(r.slice, '處理事後審查', `/domain-change 處理全自動事後審查頁 ${r.path}`);
      }
    } catch (e) { toast(e.message); b.disabled = false; }
  };
}
