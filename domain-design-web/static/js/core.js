// 共用工具與資料：$、api、esc／inline／md、toast、state、讀寫審查頁
// 從原本的 app.js 拆出來；資料都在設計 repo 的 .md，網頁只寫人做的事。
import { route } from './main.js';

export const $ = (s, el = document) => el.querySelector(s);
export const $$ = (s, el = document) => [...el.querySelectorAll(s)];
export const CIRCLED = ['', '①', '②', '③', '④', '⑤', '⑥'];
export const state = { slices: [], sessions: [], scope: null, slice: null, home: null, project: null, review: null, path: null, sel: null, showAll: false, watching: {}, approvals: {} };

// ---------- 工具 ----------

export async function api(url, body) {
  const r = await fetch(url, body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {});
  if (!r.ok) {
    let msg = r.statusText;
    try { msg = (await r.json()).detail || msg; } catch (e) { /* 不是 JSON */ }
    throw new Error(msg);
  }
  return r.json();
}

export function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// 行內：`code`，「檔名:行號」做成點了打開檔案的連結
export const FILE_REF = /`?([^\s`「」（）()、，；<>]+?\.(?:md|ya?ml|js|sql|py|log)):(\d+)`?/g;
export function inline(s) {
  return esc(s)
    .replace(FILE_REF, (m, f, n) => `<a class="ref-link" data-file="${f}" data-line="${n}">${f}:${n}</a>`)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>');
}

// 給人看的白話：拿掉出處括號、〔日期〕與標記，技術細節另外收起來
export function plain(s) {
  return String(s || '')
    .replace(/〔[^〕]*〕/g, '')
    .replace(/\[(解讀|待專家確認|未核對|靜態替代|推導)[^\]]*\]/g, '')
    .replace(/（[^（）]*(?:D-\d+|X-\d+|Q\d+|EQ-\d+|\.md|#\d+)[^（）]*）/g, '')
    .replace(/`|\*\*/g, '').replace(/^>\s*/, '').replace(/\s+/g, ' ').trim();
}

// 給草稿、說明用的簡單 Markdown：標題、清單、表格、引用、段落
export function md(text) {
  const out = [];
  let para = [], list = null, table = null;
  const flush = () => {
    if (para.length) { out.push(`<p>${inline(para.join(' '))}</p>`); para = []; }
    if (list) { out.push(`<${list.tag}>${list.items.map(x => `<li>${inline(x)}</li>`).join('')}</${list.tag}>`); list = null; }
    if (table) {
      const [h, ...rows] = table.filter(r => !/^\s*\|[\s:|-]+\|\s*$/.test(r));
      const cells = r => r.trim().replace(/^\||\|$/g, '').split(/(?<!\\)\|/).map(c => c.trim());
      out.push(`<div class="tbl"><table><tr>${cells(h).map(c => `<th>${inline(c)}</th>`).join('')}</tr>${rows.map(r => `<tr>${cells(r).map(c => `<td>${inline(c)}</td>`).join('')}</tr>`).join('')}</table></div>`);
      table = null;
    }
  };
  let inComment = false;
  for (const line of String(text || '').split('\n')) {
    if (inComment) { if (line.includes('-->')) inComment = false; continue; }
    if (line.includes('<!--')) { if (!line.includes('-->')) inComment = true; continue; }
    let m;
    if ((m = line.match(/^(#{1,4})\s+(.*)$/))) { flush(); out.push(`<h${Math.min(m[1].length + 1, 5)}>${inline(m[2])}</h${Math.min(m[1].length + 1, 5)}>`); }
    else if (line.startsWith('|')) { if (!table) { flush(); table = []; } table.push(line); }
    else if ((m = line.match(/^\s*(?:[-*]|(\d+)\.)\s+(.*)$/))) {
      const tag = m[1] ? 'ol' : 'ul';
      if (!list || list.tag !== tag) { flush(); list = { tag, items: [] }; }
      list.items.push(m[2]);
    }
    else if ((m = line.match(/^>\s?(.*)$/))) { flush(); out.push(`<blockquote>${inline(m[1])}</blockquote>`); }
    else if (!line.trim()) flush();
    else { if (list || table) flush(); para.push(line.trim()); }
  }
  flush();
  return out.join('');
}

export function today() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export function remember(k, v) {
  try { if (v === undefined) return localStorage.getItem(k) || ''; localStorage.setItem(k, v); } catch (e) { /* 私密視窗 */ }
  return '';
}

// 表單寫到一半先暫存在這個瀏覽器（依專案分開），重新整理不會清空；送出成功後清掉
export function keepDraft(name, fields) {
  const key = `draft:${(state.project || {}).repo || ''}:${name}`;
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(key) || '{}'); } catch (e) { }
  for (const x of fields) if (saved[x.dataset.k] && !x.value) x.value = saved[x.dataset.k];
  const store = () => { try { localStorage.setItem(key, JSON.stringify(Object.fromEntries(fields.map(x => [x.dataset.k, x.value])))); } catch (e) { } };
  fields.forEach(x => x.addEventListener('input', store));
  return () => { try { localStorage.removeItem(key); } catch (e) { } };
}

let toastTimer;
export function toast(msg) {
  const t = $('#toast');
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 5000);
}

export function go(h) { if (location.hash === h) route(); else location.hash = h; }
export const enc = encodeURIComponent;

export function setTop(back, mid) {
  const b = $('#back');
  b.hidden = !back;
  if (back) { b.href = back[0]; b.textContent = '← ' + back[1]; }
  $('#topMid').innerHTML = mid || '';
}

// 審查頁涵蓋的步驟：伺服器從「這輪審查的步驟」讀出的 steps（含回頭修改的步驟）；沒有時看檔名的兩位數
// （「03-04」是 ③④；「05-2」的 2 是第 2 份，不是第 ② 步）
export function stepNums(x) {
  if (x && x.steps && x.steps.length) return x.steps;
  const nums = (String((x && x.step) || x || '').match(/(?<!\d)\d{2}(?!\d)/g) || []).map(Number);
  return nums.length > 1 ? Array.from({ length: nums[nums.length - 1] - nums[0] + 1 }, (_, k) => nums[0] + k) : nums;
}
export function stepName(x) {
  const nums = stepNums(x);
  return nums.length ? nums.map(n => CIRCLED[n]).join('') : String((x && x.step) || x || '');
}

export const LEVEL_NAME = { 1: '範圍', 2: '名詞盤點', 3: '流程', 4: '規則', 5: '對照與紙上驗證', 6: '驗收' };

// ---------- 資料 ----------

export async function loadReview(path) {
  state.path = path;
  state.review = await api('/api/review?path=' + enc(path));
  return state.review;
}

export async function write(url, body) {
  const r = state.review;
  try {
    const res = await api(url, { path: r.path, digest: r.digest, ...body });
    r.digest = res.digest;
    await loadReview(r.path);
    return true;
  } catch (e) {
    toast(e.message);
    if (/重新載入/.test(e.message)) { await loadReview(r.path); route(); }
    return false;
  }
}

export function tasksOf(r) {
  const c = r.counts;
  return {
    decide: { total: c.questions, open: c.questions_open },
    confirm: { total: c.confirms, open: c.confirms_open },
    golden: { total: c.cases, open: c.cases_open },
    finish: { spot: c.spot_done, sign: c.conclusion_done },
  };
}

export function nextTask(r) {
  const c = r.counts;
  const p = enc(r.path);
  if (c.questions_open) return `#/r/${p}/decide/${firstOpenQ(r)}`;
  if (c.confirms_open) return `#/r/${p}/confirm`;
  if (c.cases_open) return `#/r/${p}/golden/${r.cases.findIndex(caseOpen)}`;
  return `#/r/${p}/finish`;
}

export function firstOpenQ(r, after = -1) {
  const qs = r.questions;
  let i = qs.findIndex((q, k) => k > after && !q.answer.trim());
  if (i < 0) i = qs.findIndex(q => !q.answer.trim());
  return i;
}

export const HUMAN = ['預期結果', '計算過程', '計算者'];
export function caseOpen(c) { return HUMAN.some(k => !(c.fields[k] && c.fields[k].value.trim())); }
