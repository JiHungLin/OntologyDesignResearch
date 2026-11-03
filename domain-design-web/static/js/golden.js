// 黃金案例
import { $, api, caseOpen, enc, esc, go, HUMAN, inline, loadReview, nextTask, plain, remember, setTop, state, toast, write } from './core.js';
import { progressSegs } from './decide.js';

// ---------- 黃金案例 ----------

// 要得出什麼：「要得出」欄的 ①②… 逐項（docs/02 ⑥，2026-11-04 起）→ items，每一項一個填答格；
// 舊格式：「要回答」欄，或情境最後的「要算：n 筆（…）」，情境就不再重複那一句
export function askOfCase(c) {
  const f = k => (c.fields[k] || {}).value || '';
  const items = f('要得出').split('\n').map(x => x.replace(/^\s*[-*]\s*/, '').trim()).filter(Boolean)
    .map(x => ({ no: (x.match(/^[①-⑳]/) || [''])[0], text: x.replace(/^[①-⑳]\s*/, '') }));
  if (items.length) return { items, ask: items.map(x => x.no + x.text).join('；'), scene: f('情境') };
  if (f('要回答')) return { ask: f('要回答'), scene: f('情境') };
  const m = f('情境').match(/^([\s\S]*?)\s*要算[：:]\s*([\s\S]+?)\s*$/);
  return m ? { ask: m[2], scene: m[1] } : { ask: '', scene: f('情境') };
}

// 「5 筆（登錄時兩段各分到幾度與排放量；改算後 2025 那一段的排放量）」→ 共 5 筆，括號裡用「；」分成幾點
export function askHtml(ask) {
  const m = ask.match(/^(\d+)\s*筆[（(]([\s\S]+)[）)]$/);
  const items = m ? m[2].split('；').map(x => ({ no: '', text: x.trim() })) : askParts(ask);
  return `${m ? `<p style="margin:0 0 4px"><b>共 ${m[1]} 項</b></p>` : ''}<ul class="ask-list">${items.map(a => `<li>${a.no ? `<span class="no">${a.no}</span>` : ''}<span>${inline(a.text)}</span></li>`).join('')}</ul>`;
}

// 提示卡：輸入欄是縮排的條列（每行「- …」）就一行一點；舊格式用「；」分
export function hintItems(s) {
  s = String(s || '');
  return (s.includes('\n') ? s.split('\n') : s.split('；')).map(x => x.replace(/^\s*[-*]\s*/, '').trim()).filter(Boolean);
}

// 時間軸：取情境裡的日期（情境不到兩個日期才用輸入），每個日期一點
export function timelineOf(c) {
  const pick = k => k === '要回答' ? askOfCase(c).ask : (c.fields[k] || {}).value || '';
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
  // 「要回答」問到的日期標成「你來判斷」
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
  // 日期先放上排，太近就放下排；上下兩排都太擠時軸上不寫日期（下面的清單有），免得字疊在一起
  let lastTop = -100, lastLow = -100;
  evs.forEach(e => {
    e.left = (e.t - evs[0].t) / span * 100;
    e.low = e.nolabel = false;
    if (e.left - lastTop >= 14) lastTop = e.left;
    else if (e.left - lastLow >= 14) { e.low = true; lastLow = e.left; }
    else e.nolabel = true;
  });
  return evs;
}

export function askParts(s) {
  return String(s || '').split(/；\s*(?=[①-⑨])/).map(x => x.trim()).filter(Boolean)
    .map(x => ({ no: /^[①-⑨]/.test(x) ? x[0] : '', text: x.replace(/^[①-⑨]\s*/, '') }));
}

export async function renderGolden(path, i) {
  const r = state.review && state.path === path ? state.review : await loadReview(path);
  const cs = r.cases;
  const p = enc(path);
  if (!cs.length) { go(nextTask(r)); return; }
  if (!cs[i]) i = 0;
  const c = cs[i];
  setTop([`#/s/${enc(r.slice)}`, '關卡'], progressSegs(cs, i, x => !caseOpen(x), k => `#/r/${p}/golden/${k}`) + `<span class="count">案例 ${i + 1} / ${cs.length}</span>`);
  const f = k => (c.fields[k] || {}).value || '';
  const evs = timelineOf(c);
  const askChip = e => e.ask ? `<span class="chip turn">你來判斷 ${[...new Set(e.ask)].join('')}</span>` : '';
  const tl = evs.length > 1 ? `
    <section class="card timeline">
      <div class="tl-wrap"><div class="tl"><div class="axis"></div>${evs.map((e, k) => `
        <div class="ev ${e.ask ? 'ask' : ''} ${e.low ? 'low' : ''}" style="left:${e.left}%">${e.nolabel ? '' : `<div class="d">${esc(e.date)}</div>`}<div class="o">${k + 1}</div></div>`).join('')}
      </div></div>
      <ol class="tl-list">${evs.map((e, k) => `<li class="${e.ask ? 'ask' : ''}"><span class="o">${k + 1}</span><b>${esc(e.date)}</b><span>${esc(e.labels.join('；')) || '<span class="muted">算到這一天</span>'}</span>${askChip(e)}</li>`).join('')}</ol>
    </section>` : '';
  const [kind, ...rest] = c.title.split('：');
  const done = !caseOpen(c);
  const A = askOfCase(c);
  // 已填的預期結果「① 6 日　② 2 日」拆回各項
  const prevItems = {};
  for (const m of f('預期結果').matchAll(/([①-⑳])\s*([^①-⑳]*)/g)) prevItems[m[1]] = m[2].trim();
  const paper = (c.paper || {})['紙上推演'] || '', judged = ((c.paper || {})['紙上判定'] || '').trim();
  const off = /^不一致/.test(judged);
  const name = remember('reviewer');
  // 有設計推出的答案時「對答案」放在主欄上方（推演很長，側欄太窄）
  const wide = done && !!paper;
  const cmp = `
        <div class="card ${done ? '' : 'dashed'}"><h2 style="font-size:17px;margin:0 0 8px">對答案</h2>
          ${done && paper ? `<div class="compare"><div><b>你</b>\n${esc(f('預期結果'))}</div><div><b>設計推出的</b>\n${esc(paper.split('\n').map(l => plain(l.replace(/^- /, '・'))).filter(Boolean).join('\n'))}</div></div>
            ${off ? `<div class="saved-note off"><b>對不上</b><p class="small" style="margin:6px 0 0">${inline(plain(judged.replace(/^不一致[（(]?(待審查者複核[:：])?/, '').replace(/[）)]$/, '')))}</p>
              <p class="small" style="margin:6px 0 0">你的答案要改：直接在下面「你的答案」改，按「送出修改」。你認為設計錯了：不用改，交給 AI 時說明。</p></div>`
            : judged ? `<p class="small"><span class="chip">${esc(judged)}</span></p>` : ''}`
          : done ? `<div class="saved-note"><b>✓ 已存到審查頁</b><p class="small" style="margin:6px 0 0">設計推出的答案還沒有：AI 要等你把審查頁交回（說「審查好了」）後，才依 ②③④ 另外推一次，寫在 golden_cases.md。推完回到這頁就看得到兩邊對照。</p></div>`
          : `<div class="lockbox">送出你的答案後才顯示，<br>免得被設計的答案影響。</div>`}
        </div>
`;
  $('#app').innerHTML = `
    <div>
      <span class="chip">${esc(rest.length ? kind : c.id)}</span>
      <h1 style="margin:10px 0 4px;font-size:30px">${esc(rest.length ? rest.join('：') : c.title)}</h1>
      <p class="muted" style="margin:0">需要的資料都在這頁，不用翻檔案。你先自己得出結果；三個都送出、交回審查頁後，AI 會依設計另外推一次，兩邊對不上的地方就是要討論的地方。</p>
    </div>
    ${tl}
    ${wide ? cmp : ''}
    <div class="cols">
      <section class="wide">
        <div class="card"><div class="label">情境</div>${inline(askOfCase(c).scene)}</div>
        <div class="card"><div class="label">要你得出的結果</div>${A.items ? `<p style="margin:0 0 4px"><b>共 ${A.items.length} 項</b>，每一項在下面各有一格</p><ul class="ask-list">${A.items.map(a => `<li>${a.no ? `<span class="no">${a.no}</span>` : ''}<span>${inline(a.text)}</span></li>`).join('')}</ul>`
          : A.ask ? askHtml(A.ask)
          : '<p class="muted" style="margin:0">審查頁沒有寫要得出什麼：照情境與右邊的提示卡，寫出這個情境走完的結果（數字、日期、會不會被擋下、變成什麼狀態……），一行寫一個。</p>'}
          ${A.items ? '' : '<p class="small muted" style="margin:6px 0 0">可能是數字，也可能是判斷（例：會不會被擋下、用哪一年度、變成什麼狀態）。把結果填在下面「預期結果」，怎麼得出的寫在「計算過程」。</p>'}</div>
        <div class="card" style="display:flex;flex-direction:column;gap:10px">
          <label class="label" for="g_exp" style="color:var(--ink);font-size:17px">你的答案（預期結果）</label>
          ${A.items ? `<div class="item-answers">${A.items.map((a, k) => `<label class="item-q" for="g_it${k}"><span class="no">${a.no || k + 1}</span>${inline(a.text)}</label>
            <input type="text" id="g_it${k}" data-item="${k}" value="${esc(prevItems[a.no] || '')}" placeholder="照括號裡的格式寫">`).join('')}</div>`
          : `<textarea id="g_exp" rows="5" placeholder="一行寫一個結果（上面列了幾項就寫幾行）；數字要寫單位">${esc(f('預期結果'))}</textarea>`}
          <label class="label" for="g_how" style="color:var(--ink)">怎麼得出的（計算過程，附依據）</label>
          <textarea id="g_how" class="soft" rows="4">${esc(f('計算過程'))}</textarea>
          <label class="label" for="g_who" style="color:var(--ink)">計算者</label>
          <input type="text" id="g_who" class="soft" value="${esc(f('計算者') || name)}" placeholder="你的名字（不能是 AI）">
          <div class="row"><button class="btn big primary" id="g_save">${done && paper ? '送出修改' : '送出，對答案'}</button></div>
        </div>
      </section>
      <aside class="side">
        <div class="card hint"><h2 style="font-size:17px;margin:0 0 8px">提示卡</h2>
          <ul style="margin:0;padding-left:20px;font-size:15px;display:flex;flex-direction:column;gap:4px">${hintItems(f('輸入')).map(x => `<li>${inline(x)}</li>`).join('')}</ul>
          ${f('專家確認') ? `<div class="small" style="margin-top:8px"><b>還在等專家：</b>${inline(plain(f('專家確認')))}</div>` : ''}
          <details class="tech" style="margin-top:8px"><summary>技術細節</summary>${c.id} · ${inline(f('驗證'))} · <a class="ref-link" data-file="${esc(path)}" data-line="${c.line}">審查頁第 ${c.line} 行</a></details>
        </div>
${wide ? '' : cmp}      </aside>
    </div>`;
  $('#g_save').onclick = async () => {
    let exp = $('#g_exp') ? $('#g_exp').value.trim() : '';
    if (A.items) {   // 逐項：每一格都要填，存成「① …　② …」一行（docs/02 ⑥ 的寫法）
      const vs = A.items.map((a, k) => $(`#g_it${k}`).value.trim());
      const miss = vs.findIndex(v => !v);
      if (miss >= 0) { toast(`第 ${A.items[miss].no || miss + 1} 項還沒填`); $(`#g_it${miss}`).focus(); return; }
      exp = A.items.map((a, k) => `${a.no || k + 1} ${vs[k]}`).join('　');
    }
    const vals = { '預期結果': exp, '計算過程': $('#g_how').value.trim(), '計算者': $('#g_who').value.trim() };
    if (!vals['預期結果'] || !vals['計算者']) { toast('預期結果與計算者要填'); return; }
    if (/^(ai|claude)$/i.test(vals['計算者'])) { toast('計算者不能是 AI'); return; }
    remember('reviewer', vals['計算者']);
    for (const k of HUMAN) {
      const cur = state.review.cases[i];
      if (!cur.fields[k]) { toast(`審查頁 ${cur.id} 沒有「${k}」這一欄，請 AI 照範本補上`); return; }
      if ((cur.fields[k].value || '') === vals[k]) continue;
      if (!await write('/api/review/case', { line: cur.fields[k].line, key: k, value: vals[k] })) return;
    }
    // 存好了：有設計推出的答案就留在這頁對照；還沒有的話直接到下一個還沒填的案例（都填完就到下一件事）
    const r2 = await loadReview(path);
    const nxt = r2.cases.findIndex((x, k) => k !== i && caseOpen(x));
    toast(`已存到審查頁（${c.id}）` + (nxt >= 0 && !paper ? `，接著是 ${r2.cases[nxt].id}` : ''));
    if (paper) renderGolden(path, i);
    else go(nxt >= 0 ? `#/r/${enc(path)}/golden/${nxt}` : nextTask(r2));
  };
}
