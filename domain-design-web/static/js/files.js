// 檔案：右側抽屜與唯讀檔案頁
import { $, $$, api, enc, esc, md, setTop, state, toast } from './core.js';
import { aiScope, curSession, renderAi } from './ai.js';

// ---------- 檔案 ----------

// 右側一次只放一個抽屜（AI 對話或檔案），最後打開的那個蓋掉另一個
// 兩個抽屜頂端都有「AI 對話｜檔案」分頁：切換時只換顯示，對話不重畫、捲動位置不變
export function showDrawer(id) {
  $$('.drawer').forEach(d => { d.hidden = d.id !== id; });
  $$('[data-tab]').forEach(b => b.classList.toggle('on', b.dataset.tab === id));
}
export function switchTab(id) {
  if (id === 'fileDrawer') { if (state.lastFile) showDrawer('fileDrawer'); return; }
  showDrawer('aiDrawer');
  const s = curSession();
  if (!s || $('#aiLog').dataset.sid !== s.id) renderAi();
}

export async function openFile(file, line) {
  // 「questions.md」「reviews/…」這種相對路徑是相對於切片資料夾：審查頁的切片、目前頁面的切片、AI 對話的切片，依序找
  const sl = (state.review && state.path && state.review.slice) || state.slice || (aiScope() && aiScope() !== '_plan' ? aiScope() : '');
  const base = sl ? `slices/${sl}` : '';
  try {
    const f = await api(`/api/file?path=${enc(file)}&base=${enc(base)}`);
    showDrawer('fileDrawer');
    $('#filePath').textContent = f.path + (line ? `:${line}` : '');
    state.lastFile = f.path;
    $$('.ftab').forEach(b => { b.disabled = false; b.textContent = '檔案：' + f.path.split('/').pop(); b.title = f.path; });
    const n = +line || 0;
    $('#fileBody').innerHTML = f.text.split('\n').map((l, k) => `<span class="ln ${k + 1 === n ? 'hit' : ''}" data-n="${k + 1}">${esc(l) || ' '}</span>`).join('');
    const hit = $('#fileBody .hit');
    if (hit) hit.scrollIntoView({ block: 'center' });
  } catch (e) { toast(e.message); }
}

// ---------- 檔案（唯讀） ----------

export async function renderFile(path) {
  state.slice = (path.match(/^slices\/([^/]+)\//) || [])[1] || null;
  state.scope = state.slice || (path.startsWith('slices/') || path.startsWith('inputs/') ? '_plan' : null);
  setTop(state.slice ? [`#/s/${enc(state.slice)}`, state.slice] : ['#/', '總覽'], `<strong>${esc(path.split('/').pop())}</strong>`);
  const f = await api('/api/file?path=' + enc(path));
  const ext = (path.match(/\.([^./]+)$/) || [])[1] || '';
  $('#app').innerHTML = `
    <div class="file-view">
      <div class="row spread page-head-row"><div class="page-head"><div class="label">唯讀</div><h1 class="ph-path">${esc(f.path)}</h1></div>
        ${f.binary ? '' : `<button class="btn small-btn" id="rawView">看行號</button>`}</div>
      ${f.binary ? `<div class="card dashed">這是原始檔（${Math.round(f.size / 1024)} KB），網頁不顯示內容。AI 會直接讀它。</div>`
        : ext === 'md' ? `<article class="card doc">${md(f.text)}</article>`
        : `<pre class="card code-view">${esc(f.text)}</pre>`}
      <p class="small muted">網頁不直接改這些檔案。要改，在切片首頁「發現問題」或規劃頁「寫意見」交給 AI。</p>
    </div>`;
  const rv = $('#rawView'); if (rv) rv.onclick = () => openFile(f.path, 1);
}
