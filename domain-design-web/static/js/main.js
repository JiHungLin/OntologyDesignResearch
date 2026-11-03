// 路由與啟動
import { $, $$, go, loadReview, nextTask, state, toast } from './core.js';
import { renderHome } from './home.js';
import { renderDecide } from './decide.js';
import { renderConfirm } from './confirm.js';
import { renderGolden } from './golden.js';
import { renderFinish } from './finish.js';
import { openFile, renderFile, switchTab } from './files.js';
import { aiScope, curSession, openAi, refreshSlices, renderAiHead, runAi } from './ai.js';
import { markNav, NARROW, narrow, refreshNav, setNav, syncNav } from './nav.js';
import { renderHub, renderStart } from './overview.js';
import { renderCore } from './coreview.js';
import { renderDraft, renderEq, renderKickoff, renderPlan } from './plan.js';

// ---------- 路由 ----------
// #/ 總覽　#/start 主題草案　#/plan 規劃　#/draft/<檔> 推想草稿　#/new/<切片> 開始切片　#/eq/<切片> 專家問題
// #/core[/<分頁>/<項目>] 共用核心　#/s/<切片> 切片首頁　#/r/<審查頁>/decide/<n>　/confirm[/<Entity>]　/golden/<n>　/finish

export async function route() {
  $('#fileDrawer').hidden = true;
  $('#app').classList.remove('wide');
  state.tsel = null;
  const parts = location.hash.replace(/^#\/?/, '').split('/').map(decodeURIComponent);
  try {
    if (parts[0] === 's' && parts[1]) return await renderHome(parts[1]);
    if (parts[0] === 'r' && parts[1]) {
      const path = parts[1];
      const m = path.match(/^slices\/([^/]+)\//);
      if (m) { state.slice = m[1]; state.scope = m[1]; markNav(); renderAiHead(); }
      if (!parts[2]) {   // 只點「審查」：帶到還沒做完的那一項（決定都答了就不再回到決定）
        location.replace(nextTask(await loadReview(path)));
        return;
      }
      if (state.path !== path) await loadReview(path);
      const view = parts[2];
      if (view === 'decide') return await renderDecide(path, +parts[3] || 0);
      if (view === 'confirm') return await renderConfirm(path, parts[3] || null);
      if (view === 'golden') return await renderGolden(path, +parts[3] || 0);
      return await renderFinish(path, parts[3] || null);
    }
    state.path = null;
    if (parts[0] === 'start') return await renderStart();
    if (parts[0] === 'plan') return await renderPlan();
    if (parts[0] === 'draft' && parts[1]) return await renderDraft(parts.slice(1).join('/'));
    if (parts[0] === 'new' && parts[1]) return await renderKickoff(parts[1]);
    if (parts[0] === 'eq' && parts[1]) return await renderEq(parts[1]);
    if (parts[0] === 'f' && parts[1]) return await renderFile(parts.slice(1).join('/'));
    if (parts[0] === 'core') return await renderCore(parts[1] || 'entities', parts[2] || null);
    return await renderHub();
  } catch (e) { toast(e.message); } finally { refreshNav(); }
}

document.addEventListener('click', e => {
  const a = e.target.closest('a.ref-link');
  if (a) { e.preventDefault(); e.stopPropagation(); openFile(a.dataset.file, a.dataset.line); return; }
  const seg = e.target.closest('[data-href]');
  if (seg) go(seg.dataset.href);
  const tab = e.target.closest('[data-tab]');
  if (tab) { switchTab(tab.dataset.tab); return; }
  const x = e.target.closest('[data-close]');
  if (x) $('#' + x.dataset.close).hidden = true;
}, true);
document.addEventListener('keydown', e => { if (e.key === 'Escape') { $('#fileDrawer').hidden = true; $('#aiDrawer').hidden = true; } });
$('#aiBtn').onclick = () => { if ($('#aiDrawer').hidden) openAi(); else $('#aiDrawer').hidden = true; };
$('#navBtn').onclick = () => setNav(true);
$('#navClose').onclick = () => setNav(false);
document.addEventListener('keydown', e => { if (e.ctrlKey && e.key === '\\') { e.preventDefault(); setNav(document.body.classList.contains('nav-closed')); } });
$('#sideNav').addEventListener('click', e => { if (narrow() && e.target.closest('a.nav-a')) setNav(false); });
$('#app').addEventListener('click', () => { if (narrow() && !document.body.classList.contains('nav-closed')) setNav(false); });
export const savedNavClosed = () => { try { return !!localStorage.getItem('nav-closed'); } catch (e) { return false; } };
if (narrow() || savedNavClosed()) document.body.classList.add('nav-closed');
// 視窗縮到窄螢幕就自動收起（不記成你的偏好）；放回寬螢幕就照你上次在寬螢幕的選擇
NARROW.addEventListener('change', e => {
  document.body.classList.toggle('nav-closed', e.matches || savedNavClosed());
  syncNav(); syncDrawers();
});
syncNav();
export const PAGE_MIN = 720;   // 抽屜打開後主畫面至少要留的寬度，不夠就讓抽屜蓋在上面
export function syncDrawers() {
  const open = $$('.drawer').some(d => !d.hidden);
  const navW = document.body.classList.contains('nav-closed') || narrow() ? 0 : $('#sideNav').offsetWidth;
  const drawerW = open ? $('.drawer:not([hidden])').offsetWidth : 0;
  document.body.classList.toggle('drawer-open', open);
  document.body.classList.toggle('drawer-push', open && innerWidth - navW - drawerW >= PAGE_MIN);
}
window.addEventListener('resize', syncDrawers);
export const drawerWatch = new MutationObserver(syncDrawers);
$$('.drawer').forEach(d => drawerWatch.observe(d, { attributes: true, attributeFilter: ['hidden'] }));
syncDrawers();
export const fitTop = () => document.documentElement.style.setProperty('--top-h', $('.top').offsetHeight + 'px');
new ResizeObserver(fitTop).observe($('.top')); fitTop();   // 頂列換行變高時，側欄頂端跟著對齊
// 像 ChatGPT／Claude：Enter 送出、Shift+Enter 換行；中文輸入法選字時的 Enter 不算；輸入框跟著內容長高
$('#aiInput').addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing && e.keyCode !== 229) { e.preventDefault(); $('#aiForm').requestSubmit(); }
});
export const growAi = () => { const t = $('#aiInput'); t.style.height = 'auto'; t.style.height = Math.min(t.scrollHeight + 4, 220) + 'px'; };
$('#aiInput').addEventListener('input', growAi);
$('#aiForm').onsubmit = e => {
  e.preventDefault();
  const v = $('#aiInput').value.trim();
  if (!v) return;
  // 送給抽屜正在顯示的那個對話（總覽頁也一樣），不是只看目前頁面
  const scope = aiScope();
  if (!scope) { toast('還沒有 AI 對話。到規劃頁或某條切片的頁面再打開'); return; }
  $('#aiInput').value = ''; growAi();
  const s = curSession();
  runAi(scope, s ? s.purpose : '對話', v, { keep: true });
};
window.addEventListener('hashchange', route);

refreshSlices().then(route).catch(e => toast(e.message));
