// 左側導覽
import { $, $$, CIRCLED, enc, esc, state } from './core.js';
import { loadProject, planSlices } from './overview.js';
import { inputDialog } from './plan.js';
import { PAGE_MIN, syncDrawers } from './main.js';

// ---------- 左側導覽 ----------
// 總覽、主題草案、規劃、各切片（狀態＋各步驟檔案）、core/、inputs/。展開狀態記在這個瀏覽器。

export const STEP_FILE = { 1: '01_scope.md', 2: '02_entities.md', 3: '03_flows.md', 4: '04_rules.md', 5: '05_mapping.md', 6: '06_evidence/signoff.md' };

export function navOpenSet() { try { return new Set(JSON.parse(localStorage.getItem('nav-open') || '[]')); } catch (e) { return new Set(); } }
export function navSaveOpen(set) { try { localStorage.setItem('nav-open', JSON.stringify([...set])); } catch (e) { } }

export function sliceState(f, row) {
  if (!f) return { text: (row && row['狀態']) || '', cls: '' };
  if (f.session && f.session.running) return { text: 'AI 進行中', cls: 'busy' };
  const au = state.project && state.project.autorun;
  if (au && au.running && (f.review || (f.next && (f.next.n <= 5 || f.next.status !== '未開始')))) return { text: '全自動進行中', cls: 'busy' };
  if (f.review) return { text: '輪到你審查', cls: 'turn' };
  if (f.auto_review && f.auto_review.open) return { text: `${f.auto_review.open} 題待你決定`, cls: 'turn' };
  if (!f.next) return { text: '完成', cls: 'ok' };
  // ⑥ 還沒開始才算「設計完成」；已經開始（有簽核紀錄）就是還在驗證，不是完成
  if (f.next.n === 6) return f.next.status === '未開始' ? { text: '設計完成', cls: 'ok' } : { text: f.next.status === '凍結中' ? '⑥ 凍結中' : '⑥ 驗證中', cls: '' };
  if (f.next.status === '凍結中') return { text: `${CIRCLED[f.next.n]} 凍結中`, cls: '' };
  return { text: `下一關 ${CIRCLED[f.next.n]}`, cls: '' };
}

export function stepCls(status) { return status.startsWith('已凍結') ? 'frozen' : status === '待檢查' ? 'wait' : status === '未開始' ? '' : 'draft'; }

export function renderNav() {
  const P = state.project;
  const nav = $('#navTree');
  if (!P) return;
  const open = navOpenSet();
  const a = (href, label, extra = '', cls = '') => `<a class="nav-a ${cls}" href="${href}">${label}${extra ? `<span class="nav-x">${extra}</span>` : ''}</a>`;
  const fileA = (path, label) => a(`#/f/${enc(path)}`, esc(label || path.split('/').pop()));
  const node = (key, summary, body, dflt) => {
    const isOpen = open.has(key) || (dflt && !open.has('!' + key));
    return `<details class="nav-node" data-nav="${esc(key)}" ${isOpen ? 'open' : ''}><summary>${summary}</summary><div class="nav-kids">${body}</div></details>`;
  };
  const folderTree = (groups, top, fileLink) => {
    const dirs = Object.keys(groups).sort();
    return dirs.map(d => {
      const files = groups[d].map(fileLink).join('');
      return d === top ? files : node('dir:' + d, `<span class="nav-dir">${esc(d.slice(top.length + 1))}/</span><span class="nav-x">${groups[d].length}</span>`, files);
    }).join('');
  };
  const plan = P.plan;
  const list = planSlices(P);
  const started = list.filter(x => x.f), waiting = list.filter(x => !x.f);
  const doing = started.find(x => x.f.next && x.f.next.n <= 5);   // 一次只做一條：這條做完前不能開新的
  const pendingDrafts = P.drafts.filter(d => d.pending).length;

  const sliceNode = x => {
    const f = x.f;
    const st = sliceState(f, x.row);
    const steps = f.steps.map(t => {
      const label = `<i class="${stepCls(t.status)}">${CIRCLED[t.n]}</i>${esc(t.name)}`;
      return t.status === '未開始' ? `<span class="nav-a off">${label}<span class="nav-x">未開始</span></span>`
        : a(`#/f/${enc(`slices/${x.code}/${t.file}`)}`, label, esc(t.status.replace(/（.*/, '')));
    }).join('');
    const others = f.files.filter(p => !Object.values(STEP_FILE).some(sf => p.endsWith('/' + sf)));
    const body = a(`#/s/${enc(x.code)}`, '切片首頁')
      + (f.review ? a(`#/r/${enc(f.review.path)}`, '審查（輪到你）', `${f.review.counts.open} 件`, 'hot')
        : f.answered ? a(`#/r/${enc(f.answered.path)}`, '審查頁', '已作答，可以改') : '')
      + (f.auto_review ? a(`#/r/${enc(f.auto_review.path)}/all`, '全自動留給你的決定',
        f.auto_review.open ? `${f.auto_review.open} 題` : '答完，等處理', f.auto_review.open ? 'hot' : '') : '')
      + a(`#/eq/${enc(x.code)}`, '專家問題', f.eq_open ? `${f.eq_open} 題待答` : '')
      + `<div class="nav-steps">${steps}</div>`
      + (others.length ? node('files:' + x.code, '<span class="nav-dir">其他檔案</span>', others.map(p => fileA(p)).join('')) : '');
    return node('s:' + x.code, `<span class="nav-name" title="${esc(x.code)}">${esc(x.code)}</span><span class="nav-st ${st.cls}">${esc(st.text)}</span>`, body, state.slice === x.code);
  };

  nav.innerHTML = `
    ${a('#/', '總覽')}
    ${plan && plan.auto ? a('#/auto', '全自動', P.autorun && P.autorun.running ? `執行中・第 ${P.autorun.round || 1} 圈` : '已停', P.autorun && P.autorun.running ? 'busy' : '') : ''}
    ${P.topic ? fileA(P.topic, '主題草案') : plan ? '' : a('#/start', '主題草案', '還沒寫')}
    ${node('plan', `<span class="nav-name">規劃</span><span class="nav-st ${plan && plan.agreed ? 'ok' : plan ? 'turn' : ''}">${plan ? (plan.agreed ? '已同意' : '討論中') : '還沒有'}</span>`,
      a('#/plan', '規劃頁') + (plan ? fileA('slices/PLAN.md', '切片地圖 PLAN.md') : '')
      + (P.sketch ? fileA('slices/ENTITY_SKETCH.md', '名詞草圖') : '')
      + (P.drafts.length ? node('drafts', `<span class="nav-dir">推想草稿</span><span class="nav-x">${pendingDrafts ? pendingDrafts + ' 待接受' : P.drafts.length}</span>`,
        P.drafts.map(d => a(`#/draft/${enc(d.path)}`, esc(d.title), d.pending ? '待接受' : '')).join('')) : ''), !plan || !plan.agreed)}
    <div class="nav-h">切片</div>
    ${started.map(sliceNode).join('') || '<div class="nav-empty">還沒有開始的切片</div>'}
    ${waiting.length ? node('waiting', `<span class="nav-dir">還沒開始</span><span class="nav-x">${waiting.length}</span>`,
      (doing ? `<div class="nav-empty">等 ${esc(doing.code)} 做完才能開始下一條</div>` : '')
      + waiting.map(x => a(plan && plan.agreed && x.row['狀態'] === '候選' && !doing ? `#/new/${enc(x.code)}` : '#/plan', esc(x.code), esc(x.row['狀態'] || ''))).join('')) : ''}
    <div class="nav-h">資料與成果</div>
    ${node('core', `<span class="nav-name">core</span><span class="nav-x">共用核心</span>`,
      Object.keys(P.core).length ? a('#/core', '共用核心（整理過的）') + folderTree(P.core, 'core', p => fileA(p)) : '<div class="nav-empty">第一次凍結 ②③④ 後才有</div>')}
    ${node('inputs', `<span class="nav-name">inputs</span><span class="nav-x">收集的資料</span>`,
      (Object.keys(P.inputs).length ? folderTree(P.inputs, 'inputs', p => p.startsWith('inputs/drafts/') ? a(`#/draft/${enc(p)}`, esc(p.split('/').pop())) : fileA(p)) : '<div class="nav-empty">還沒有資料</div>')
      + `<button class="nav-add" id="navAddInput">＋ 加資料</button>`)}
    ${a('#/f/' + enc('slices/CHANGELOG.md'), '變更紀錄 CHANGELOG')}`;
  nav.querySelectorAll('details.nav-node').forEach(d => d.addEventListener('toggle', () => {
    const set = navOpenSet(), k = d.dataset.nav;
    set.delete(k); set.delete('!' + k);
    set.add(d.open ? k : '!' + k);
    navSaveOpen(set);
  }));
  $('#navAddInput').onclick = () => inputDialog({ folder: 'shared' });
  markNav();
}

export function markNav() {
  const h = location.hash || '#/';
  let best = null;
  $$('#sideNav a.nav-a').forEach(x => {
    x.classList.remove('on');
    const href = x.getAttribute('href');
    if (h === href || (href !== '#/' && h.startsWith(href + '/'))) if (!best || href.length > best.getAttribute('href').length) best = x;
  });
  if (best) {
    best.classList.add('on');
    for (let d = best.closest('details'); d; d = d.parentElement.closest('details')) d.open = true;
  }
}

export async function refreshNav() { try { await loadProject(); renderNav(); } catch (e) { } }

// 像 Notion：側欄是獨立的一欄（展開時頂列往右擠）。收起時頂列最左邊是 ☰，點了才展開（滑過不彈出）；展開時側欄頂列最左邊是收起鈕；Ctrl+\ 切換
export function setNav(open) {
  document.body.classList.toggle('nav-closed', !open);
  syncNav();
  syncDrawers();
  if (!narrow()) try { localStorage.setItem('nav-closed', open ? '' : '1'); } catch (e) { }
}
export function syncNav() {
  const closed = document.body.classList.contains('nav-closed');
  const b = $('#navBtn');
  b.title = '展開側欄（Ctrl+\\）';
  b.setAttribute('aria-label', b.title);
  b.setAttribute('aria-expanded', String(!closed));
}
// 窄螢幕＝側欄放上去主畫面就剩不到 PAGE_MIN（290 + 720）：側欄改成蓋在上面、預設收起（和 style.css 的 @media 同一個寬度）
export const NARROW = matchMedia('(max-width: 1010px)');
export function narrow() { return NARROW.matches; }
