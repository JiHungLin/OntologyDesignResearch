// 圖的縮放與平移（像 Miro、draw.io）：拖曳移動；Ctrl／⌘＋滾輪、觸控板捏合或手機雙指縮放；右上角 －／＋、全圖、1:1。
// 一般滾輪照樣捲頁面。#app 裡 .diagram 底下的 svg 出現時自動掛上（main.js），各圖的程式不用改。
// 同一張圖重畫（例：點了另一個方塊）時保留目前的位置與倍率；svg 有 data-focus="x,y" 時，
// 第一次打開以那一點為中心，之後那一點跑出畫面外才移過去。

const views = new Map();   // 圖的 key → {x, y, s}
const MIN = 0.2, MAX = 4;

function keyOf(svg) {
  const vb = svg.viewBox.baseVal;
  return `${location.hash.split('/').slice(0, 3).join('/')}|${svg.getAttribute('aria-label') || ''}|${Math.round(vb.width)}x${Math.round(vb.height)}`;
}

export function attachPanZoom(svg) {
  if (svg.dataset.pzOn) return;
  svg.dataset.pzOn = '1';
  const vb = svg.viewBox.baseVal;
  const W = vb.width, H = vb.height;
  if (!W || !H) return;
  const box = svg.parentElement;
  box.classList.add('pz');
  const key = keyOf(svg);
  svg.style.width = '100%';
  svg.style.height = Math.round(Math.max(320, Math.min(H + 8, innerHeight * 0.72))) + 'px';
  svg.style.maxWidth = 'none';
  const size = () => ({ cw: svg.clientWidth || 1, ch: svg.clientHeight || 1 });
  const focus = (svg.dataset.focus || '').split(',').map(Number);
  let v = views.get(key);

  const apply = () => {
    const { cw, ch } = size();
    svg.setAttribute('viewBox', `${v.x} ${v.y} ${cw / v.s} ${ch / v.s}`);
    const pct = box.querySelector('.pz-pct');
    if (pct) pct.textContent = Math.round(v.s * 100) + '%';
    views.set(key, v);
  };
  const centerOn = (fx, fy) => { const { cw, ch } = size(); v = { ...v, x: fx - cw / v.s / 2, y: fy - ch / v.s / 2 }; };
  const fit = () => {
    const { cw, ch } = size();
    const s = Math.min(MAX, Math.max(MIN, Math.min(cw / W, ch / H)));
    v = { s, x: (W - cw / s) / 2, y: (H - ch / s) / 2 };
  };
  const actual = () => {   // 1:1；圖比框寬時，左右以 data-focus 那一點為中心
    const { cw } = size();
    const x = W <= cw ? (W - cw) / 2 : focus.length === 2 ? Math.min(W - cw, Math.max(0, focus[0] - cw / 2)) : 0;
    v = { s: 1, x, y: 0 };
  };
  const zoomAt = (k, px, py) => {   // px、py：在 svg 裡的螢幕座標，縮放時這一點不動
    const s = Math.min(MAX, Math.max(MIN, v.s * k));
    const ux = v.x + px / v.s, uy = v.y + py / v.s;
    v = { s, x: ux - px / s, y: uy - py / s };
    apply();
  };

  if (!v) actual();
  else if (focus.length === 2) {   // 選到的那個在畫面外才移過去
    const { cw, ch } = size();
    if (focus[0] < v.x || focus[0] > v.x + cw / v.s || focus[1] < v.y || focus[1] > v.y + ch / v.s) centerOn(focus[0], focus[1]);
  }

  if (!box.querySelector('.pz-ctl')) {
    box.insertAdjacentHTML('afterbegin', `<div class="pz-ctl" aria-label="縮放">
      <button type="button" data-pz="out" title="縮小（Ctrl＋滾輪）">－</button><span class="pz-pct"></span>
      <button type="button" data-pz="in" title="放大（Ctrl＋滾輪）">＋</button>
      <button type="button" data-pz="fit" title="整張圖放進框裡">全圖</button>
      <button type="button" data-pz="one" title="原本的大小">1:1</button></div>
      <div class="pz-hint">拖曳移動・雙指或 Ctrl＋滾輪縮放</div>`);
  }
  box.querySelectorAll('.pz-ctl [data-pz]').forEach(b => b.onclick = e => {
    e.stopPropagation();
    const { cw, ch } = size();
    if (b.dataset.pz === 'in') zoomAt(1.25, cw / 2, ch / 2);
    else if (b.dataset.pz === 'out') zoomAt(0.8, cw / 2, ch / 2);
    else { b.dataset.pz === 'fit' ? fit() : actual(); apply(); }
  });

  svg.addEventListener('wheel', e => {
    if (!e.ctrlKey && !e.metaKey) return;   // 一般滾輪捲頁面；觸控板捏合會帶 ctrlKey
    e.preventDefault();
    const r = svg.getBoundingClientRect();
    zoomAt(Math.exp(-e.deltaY * 0.0015), e.clientX - r.left, e.clientY - r.top);
  }, { passive: false });

  // 拖曳平移：移動超過 4px 才算拖曳，放開時吞掉那一下 click（不會誤選到方塊）
  // 手機雙指：兩指距離變化＝縮放（以兩指中間為中心），兩指一起移動＝平移；放開一指後接著用剩下那指拖曳
  const pts = new Map();   // pointerId → 目前位置
  let drag = null, moved = false, pinch = null;
  const pair = () => {
    const [a, b] = [...pts.values()];
    return { d: Math.hypot(a.x - b.x, a.y - b.y) || 1, mx: (a.x + b.x) / 2, my: (a.y + b.y) / 2 };
  };
  const startDrag = p => { drag = { x: p.x, y: p.y, vx: v.x, vy: v.y }; };
  svg.addEventListener('pointerdown', e => {
    if (e.pointerType === 'mouse' && e.button !== 0) return;
    pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pts.size === 1) { startDrag(pts.get(e.pointerId)); moved = false; return; }
    if (pts.size === 2) {   // 第二指放上來：改成捏合
      pinch = pair(); drag = null; moved = true;
      for (const id of pts.keys()) { try { svg.setPointerCapture(id); } catch { /* 那一指已經放開 */ } }
      svg.classList.add('dragging');
    }
  });
  svg.addEventListener('pointermove', e => {
    if (!pts.has(e.pointerId)) return;
    pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pinch && pts.size >= 2) {
      const now = pair(), r = svg.getBoundingClientRect();
      v = { ...v, x: v.x - (now.mx - pinch.mx) / v.s, y: v.y - (now.my - pinch.my) / v.s };
      zoomAt(now.d / pinch.d, now.mx - r.left, now.my - r.top);
      pinch = now;
      return;
    }
    if (!drag) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (!moved && Math.hypot(dx, dy) < 4) return;
    if (!moved) { moved = true; svg.setPointerCapture(e.pointerId); svg.classList.add('dragging'); }
    v = { ...v, x: drag.vx - dx / v.s, y: drag.vy - dy / v.s };
    apply();
  });
  const end = e => {
    pts.delete(e.pointerId);
    if (pts.size < 2) pinch = null;
    if (pts.size === 1) { startDrag([...pts.values()][0]); return; }   // 剩一指：從它現在的位置接著拖
    if (!pts.size) { drag = null; svg.classList.remove('dragging'); }
  };
  svg.addEventListener('pointerup', end);
  svg.addEventListener('pointercancel', end);
  svg.addEventListener('click', e => { if (moved) { e.stopPropagation(); e.preventDefault(); moved = false; } }, true);

  apply();
}
