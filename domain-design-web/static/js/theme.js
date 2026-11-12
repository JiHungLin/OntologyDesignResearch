// 深淺色切換：跟隨系統 → 淺色 → 深色，存在這個瀏覽器（localStorage）。index.html 開頭的小段程式先套上，避免閃一下。
const KEY = 'lumori-theme';
const MODES = ['system', 'light', 'dark'];
const NAME = { system: '跟隨系統', light: '淺色', dark: '深色' };

function read() {
  try { const t = localStorage.getItem(KEY); return MODES.includes(t) ? t : 'system'; } catch { return 'system'; }
}

function apply(mode) {
  const root = document.documentElement;
  if (mode === 'system') delete root.dataset.theme; else root.dataset.theme = mode;
  const b = document.getElementById('themeBtn');
  if (b) {
    b.dataset.mode = mode;
    const next = MODES[(MODES.indexOf(mode) + 1) % MODES.length];
    b.title = `顏色：${NAME[mode]}（按一下換成${NAME[next]}）`;
    b.setAttribute('aria-label', b.title);
  }
}

apply(read());
const btn = document.getElementById('themeBtn');
if (btn) btn.onclick = () => {
  const next = MODES[(MODES.indexOf(read()) + 1) % MODES.length];
  try { if (next === 'system') localStorage.removeItem(KEY); else localStorage.setItem(KEY, next); } catch { /* 存不了就只換這一次 */ }
  apply(next);
};
