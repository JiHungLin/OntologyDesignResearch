// 總覽與主題草案
import { $, $$, api, CIRCLED, enc, esc, go, inline, keepDraft, setTop, state, stepName, toast } from './core.js';
import { STEP_INFO } from './home.js';
import { bindWaiting, openAi, runAi, runningCard, waitingCard } from './ai.js';
import { markNav, narrow } from './nav.js';
import { inputDialog, needFetch } from './plan.js';

// ---------- 總覽：整個 domain 走到哪 ----------

export async function loadProject() { state.project = await api('/api/project'); showTopic(state.project); return state.project; }

// 主題名稱：切片地圖「領域」的第一段（人資／人事 → 人資）；還沒有切片地圖時照舊「Domain 設計」
export function topicName(P) {
  const ds = (P.plan ? P.plan.domains : []).map(d => (d['領域'] || '').split('／')[0].trim()).filter(Boolean);
  return [...new Set(ds)].join('、');
}

function showTopic(P) {
  const name = topicName(P);
  const b = $('.brand');
  if (b) b.innerHTML = name ? `${esc(name)}<span class="brand-sub">DOMAIN 設計</span>` : 'DOMAIN 設計';
  document.title = name ? `${name}｜Domain 設計` : 'Domain 設計';
}

export function planSlices(P) {
  // 地圖上的切片，依建議順序；加上資料夾裡的進度
  const rows = (P.plan ? P.plan.slices : []).slice().sort((a, b) => (+a['建議順序'] || 99) - (+b['建議順序'] || 99));
  const folders = new Map(P.slices.map(x => [x.slice, x]));
  const out = rows.map(r => ({ code: r['切片'], row: r, f: folders.get(r['切片']) }));
  for (const f of P.slices) if (!rows.some(r => r['切片'] === f.slice)) out.push({ code: f.slice, row: null, f });
  return out;
}

export function scenario(text) {
  const parts = String(text || '').split(/\s*→\s*/);
  return parts.length > 1 ? `<span class="scn">${parts.map((x, k) => `<span class="${k === 0 ? 'from' : k === parts.length - 1 ? 'to' : 'mid'}">${inline(x)}</span>`).join('<i>→</i>')}</span>` : inline(text);
}

export function miniSteps(f) {
  if (!f) return '';
  return `<span class="mini">${f.steps.map(x => `<i class="${x.status.startsWith('已凍結') ? 'frozen' : x.status === '待檢查' ? 'wait' : x.status === '未開始' ? '' : 'draft'}" title="${CIRCLED[x.n]} ${esc(x.name)}：${esc(x.status)}">${CIRCLED[x.n]}</i>`).join('')}</span>`;
}

// 現在整個 domain 輪到誰、做什麼
export function nextOfProject(P) {
  const plan = P.plan;
  const ps = P.plan_session;
  if (ps && ps.running) return { kind: 'running', scope: '_plan' };
  if (!plan && !P.topic) return { kind: 'start' };
  if (!plan) return { kind: 'plan-ai' };
  if (!plan.agreed) return { kind: 'plan' };
  const list = planSlices(P);
  // ①～⑤ 還沒做完的；或 ⑥ 已經開始（有進度或有審查頁）的——⑥ 開始後也是「現在在做的切片」
  // 好幾條同時在做時：AI 正在跑的 → 有審查頁等人作答的（輪到你）→ 地圖上的順序
  const going = list.filter(x => x.f && x.f.next && (x.f.next.n <= 5 || x.f.review || x.f.next.status !== '未開始'));
  const active = going.find(x => x.f.session && x.f.session.running) || going.find(x => x.f.review) || going[0];
  if (active) {
    const f = active.f;
    if (f.session && f.session.running) return { kind: 'running', scope: f.slice, item: active };
    return { kind: f.review ? 'review' : 'slice', item: active };
  }
  const nxt = list.find(x => !x.f && x.row && x.row['狀態'] === '候選');
  if (nxt) return { kind: 'pick', item: nxt };
  return { kind: 'done' };
}

export async function renderHub() {
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
      <a class="btn big yellow" href="#/start">寫主題草案<span class="arr">›</span></a></section>`;
  else if (N.kind === 'plan-ai') hero = `<section class="hero idle"><div style="flex:999 1 480px;min-width:0"><span class="chip">輪到 AI</span>
      <h1>主題草案寫好了，請 AI 規劃</h1><p>AI 會盤點這個領域通常有哪些資料（你有的、公開找得到的、只能先推想的），把要做的事切成一條條情境（切片），並列出全局會用到的名詞。</p>
      <p class="muted small">之後輪到你：補資料、看推想草稿、看切片地圖，同意後才開始第一條。</p></div>
      <button class="btn big primary" id="doPlan">請 AI 規劃<span class="arr">›</span></button></section>`;
  else if (N.kind === 'running') hero = runningCard(N.scope, N.scope === '_plan' ? 'AI 正在規劃' : `AI 正在做 ${N.scope}`);
  else if (N.kind === 'plan') {
    const parts = [];
    if (pendingDrafts) parts.push(`<strong>${pendingDrafts} 份推想草稿</strong>要你看`);
    const toFetch = plan.inventory.filter(needFetch).length;
    if (toFetch) parts.push(`<strong>${toFetch} 份公開資料</strong> AI 抓不到、要你幫忙找`);
    if (toProvide - toFetch) parts.push(`<strong>${toProvide - toFetch} 份資料</strong>等你提供`);
    if (pq) parts.push(`<strong>${pq} 個待釐清</strong>`);
    hero = `<section class="hero"><div style="flex:999 1 480px;min-width:0"><span class="chip">輪到你</span>
      <h1>看規劃：${plan.slices.length} 條切片、${P.sketch ? P.sketch.nouns.length : 0} 個名詞</h1>
      <p>${parts.length ? parts.join('、') + '；' : ''}看完切片地圖與名詞草圖，有意見就寫，沒問題就同意。</p></div>
      <a class="btn big yellow" href="#/plan">看規劃<span class="arr">›</span></a></section>`;
  } else if (N.kind === 'review') {
    const f = N.item.f;
    hero = `<section class="hero"><div style="flex:999 1 480px;min-width:0"><span class="chip">輪到你</span>
      <h1>審查 ${esc(f.slice)} ${esc(stepName(f.review))}</h1><p>${scenario(N.item.row ? N.item.row['情境（起點 → 可驗證的結果）'] : '')}</p>
      <p>還有 ${f.review.counts.open} 件事要做。</p></div><a class="btn big yellow" href="#/s/${enc(f.slice)}">去審查<span class="arr">›</span></a></section>`;
  } else if (N.kind === 'slice') {
    const f = N.item.f;
    hero = `<section class="hero idle"><div style="flex:999 1 480px;min-width:0"><span class="chip">進行中</span>
      <h1>${esc(f.slice)}：${f.next.status === '凍結中' ? `${CIRCLED[f.next.n]} ${esc(STEP_INFO[f.next.n][0])}的凍結還沒做完` : f.next.status === '待檢查' ? `${CIRCLED[f.next.n]} ${esc(STEP_INFO[f.next.n][0])}審查填好了，看下一步（凍結、重做或回頭修改）` : `下一關 ${CIRCLED[f.next.n]} ${esc(STEP_INFO[f.next.n][0])}`}</h1><p>${scenario(N.item.row ? N.item.row['情境（起點 → 可驗證的結果）'] : '')}</p></div>
      <a class="btn big primary" href="#/s/${enc(f.slice)}">打開<span class="arr">›</span></a></section>`;
  } else if (N.kind === 'pick') {
    const r = N.item.row;
    hero = `<section class="hero"><div style="flex:999 1 480px;min-width:0"><span class="chip">下一條切片</span>
      <h1>${esc(r['切片'])}</h1><p class="big-scn">${scenario(r['情境（起點 → 可驗證的結果）'])}</p>
      <p class="small">建議順序 ${esc(r['建議順序'])}${r['依賴'] && r['依賴'] !== '—' ? `　依賴：${esc(r['依賴'])}` : ''}</p></div>
      <a class="btn big yellow" href="#/new/${enc(r['切片'])}">開始這一條<span class="arr">›</span></a></section>`;
  } else hero = `<section class="card lift celebrate pop"><div class="stars">★ ★ ★</div><h1>地圖上的切片都做完了</h1>
      <p class="muted">有新的情境或需求，到「規劃」補進地圖。</p><a class="btn big" href="#/plan">看規劃</a></section>`;

  const eqTotal = P.slices.reduce((n, x) => n + x.eq_open, 0);
  const started = list.filter(x => x.f), waiting = list.filter(x => !x.f);
  const doing = started.find(x => x.f.next && x.f.next.n <= 5);   // 一次只做一條：這條做完前不能開新的
  $('#app').innerHTML = `
    <nav class="journey">${journey.map((j, k) => `<div class="${k < stage ? 'done' : k === stage ? 'now' : ''}"><b>${k + 1}</b><span>${esc(j)}</span></div>`).join('')}</nav>
    ${waitingCard('_plan')}
    ${hero}
    ${list.length ? `<section><div class="row spread"><h2 style="margin:0">切片</h2>${plan ? `<a href="#/plan">切片地圖${plan.agreed ? '（已同意）' : '（討論中）'}</a>` : ''}</div>
      ${started.length ? `<div class="slices">${started.map(x => {
        const r = x.row || {};
        const st = x.f.review ? '輪到你審查' : x.f.session && x.f.session.running ? 'AI 進行中' : !x.f.next ? '完成' : x.f.next.n === 6 ? (x.f.next.status === '未開始' ? '設計完成（待驗證）' : '⑥ 驗證中') : x.f.next.status === '凍結中' ? `${CIRCLED[x.f.next.n]} 凍結中` : `下一關 ${CIRCLED[x.f.next.n]}`;
        const sc = r['情境（起點 → 可驗證的結果）'] || '';
        return `<a class="slice ${x.f.review ? 'turn' : ''}" href="#/s/${enc(x.code)}" title="${esc(sc)}">
          <span class="row spread"><b>${esc(x.code)}</b><span class="chip ${x.f.review ? 'turn' : ''}">${esc(st)}</span></span>
          <span class="small clamp3">${scenario(sc)}</span>
          ${miniSteps(x.f)}
          ${x.f.eq_open || x.f.eq_answered ? `<span class="small muted">專家問題：${x.f.eq_open} 題等答覆${x.f.eq_answered ? `、${x.f.eq_answered} 題答覆了待處理` : ''}</span>` : ''}
        </a>`;
      }).join('')}</div>` : ''}
      ${waiting.length ? `<div class="sub-h"><h3>還沒開始（${waiting.length}）</h3><span class="small muted">${doing ? `等 ${esc(doing.code)} 做完（①～⑤ 都凍結）才能開始下一條；點一條看地圖上的說明` : `照建議順序；點一條看地圖上的說明${plan && plan.agreed ? '或開始' : ''}`}</span></div>
      <ol class="slice-list">${waiting.map((x, k) => {
        const r = x.row || {};
        const href = plan && plan.agreed && r['狀態'] === '候選' && !doing ? `#/new/${enc(x.code)}` : '#/plan';
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

export const TOPIC_Q = [
  ['想做的系統', '想做什麼系統？一兩句話就好', '例：連鎖飲料店的人資系統，先做請假與特休'],
  ['給誰用', '給誰用？', '例：店長、員工、總部人資'],
  ['要解決什麼', '現在哪裡最痛、要解決什麼？', '例：特休天數常算錯、事後補請假很亂'],
  ['這一階段一定要做到', '這一階段一定要做到什麼？', '例：特休天數正確、到期提醒'],
  ['明確不做', '明確不做什麼？', '例：薪資計算、招募'],
  ['有沒有專家或客戶', '有沒有 Domain 專家或客戶端使用者可以問？是誰？', '例：總部人資主管王小姐，每週可以問一次'],
  ['其他', '其他想讓 AI 知道的（規模、時程、已有的系統）', '例：20 家店、每店 10 人；月初結算'],
];

export async function renderStart() {
  state.slice = null; state.scope = '_plan';
  markNav();
  setTop(['#/', '總覽'], '<strong>主題草案</strong>');
  const P = state.project || await loadProject();
  $('#app').innerHTML = `
    <div class="narrow">
      <div><span class="chip">第 1 步</span><h1 class="qtitle">寫下你想做的系統</h1>
        <p class="muted">用自己的話寫，不用專業術語；空著的 AI 之後會用選擇題問。存成 <code>inputs/shared/主題草案.md</code>${P.topic ? '（已經有了，這次寫的會加成一節「補充」，不改舊的）' : ''}。</p>
        <p class="small muted" style="margin:0">寫到一半重新整理也不會不見（暫存在這個瀏覽器，存好後清掉）。</p></div>
      <section class="card lift" style="display:flex;flex-direction:column;gap:16px">
        ${TOPIC_Q.map(([k, q, ph], i) => `<label class="label" style="color:var(--ink);font-size:16px">${esc(q)}
          ${i === 0 ? `<textarea data-k="${k}" rows="2" placeholder="${esc(ph)}"></textarea>` : `<input type="text" data-k="${k}" class="soft" placeholder="${esc(ph)}">`}</label>`).join('')}
      </section>
      <section class="card">
        <div class="label">手上有的資料（表單、規章、Excel、訪談）</div>
        <p class="small muted" style="margin:0 0 8px">可以現在放，也可以之後。放進來的存在 <code>inputs/shared/</code>，原樣保留。</p>
        <button class="btn" id="addInput">加資料</button>
      </section>
      <div class="row"><button class="btn big primary" id="saveTopic">存好，請 AI 規劃<span class="arr">›</span></button><button class="btn big" id="saveOnly">只存起來</button></div>
    </div>`;
  const fields = $$('#app [data-k]');
  const clearDraft = keepDraft('topic', fields);
  const collect = () => Object.fromEntries(fields.map(x => [x.dataset.k, x.value.trim()]));
  const save = async () => {
    const f = collect();
    if (!Object.values(f).some(Boolean)) { toast('至少寫一項'); return null; }
    try { const p = (await api('/api/topic', { fields: f })).path; clearDraft(); return p; } catch (e) { toast(e.message); return null; }
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
