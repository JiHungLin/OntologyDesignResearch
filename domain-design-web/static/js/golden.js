// 黃金案例
import { $, api, caseOpen, enc, esc, go, HUMAN, inline, loadReview, nextTask, plain, remember, setTop, state, toast, write } from './core.js';
import { progressSegs } from './decide.js';

// ---------- 黃金案例 ----------

// 時間軸：取情境裡的日期（情境不到兩個日期才用輸入），每個日期一點
export function timelineOf(c) {
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
