#!/usr/bin/env python3
"""從研究資料夾重建設計工具包：複製規範文件到 docs/，並把精簡版各步驟的完成標準（含行尾的類別標記）寫進範本的「檢查紀錄」。
用法（在 domain-design-kit/ 內）：python3 build_kit.py"""
import os, re, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
DOCS = {
    '團隊開發流程_精簡版.md': 'docs/01_Domain設計規範.md',
    'Domain設計輸入輸出規範.md': 'docs/02_輸入輸出規範.md',
    '平台架構約定.md': 'docs/03_平台架構約定.md',
    'Domain設計心法.md': 'docs/04_Domain設計心法.md',
    '本體論設計指南.md': 'docs/05_本體論設計指南.md',
}
STEPS = ['① 範圍與驗收問題', '② 名詞盤點', '③ 流程與狀態', '④ 規則與限制', '⑤ 投影到實作', '⑥ 跑起來驗證']
CLASS_RE = re.compile(r'〔(關鍵決定(?:（例外時）)?|修正線索|品質檢查)〕\s*$')  # 完成標準行尾的類別標記
TEMPLATE_STEP = {
    'templates/slice/01_scope.md': [1], 'templates/slice/02_entities.md': [2],
    'templates/slice/03_flows.md': [3], 'templates/slice/04_rules.md': [4],
    'templates/slice/05_mapping.md': [5], 'templates/slice/06_evidence/signoff.md': [6],
}

def checklists(text):
    out = {}
    for i, st in enumerate(STEPS, 1):
        a = text.index('\n## ' + st)
        nxt = [text.find('\n## ' + x, a + 5) for x in STEPS[i:]] + [text.find('\n## 附錄', a + 5)]
        b = min(x for x in nxt if x > 0)
        sec, items = text[a:b], []
        for head in ('**最少要有的測試**', '**完成標準**'):
            if head not in sec:
                continue
            for line in sec[sec.index(head):].split('\n')[1:]:
                if line.startswith('- [ ] '):
                    items.append(line[6:])
                elif items and line.strip():
                    break
        out[i] = items
    return out

def main():
    os.chdir(HERE)
    for src, dst in DOCS.items():
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(os.path.join(SRC, src), dst)
    cl = checklists(open(os.path.join(SRC, '團隊開發流程_精簡版.md'), encoding='utf-8').read())
    pat = re.compile(r'(<!-- CHECKLIST:START -->\n)(?:.*?\n)?(<!-- CHECKLIST:END -->)', re.S)
    for path, steps in TEMPLATE_STEP.items():
        items = sum((cl[s] for s in steps), [])
        tagged = [CLASS_RE.search(it) for it in items]
        if all(tagged):
            # 有類別標記（①～⑤）：完成標準表給 AI 自評，審查重點表給人（精簡版 0.2）
            rows = ['### 完成標準（AI 自評）', '', '| 完成標準 | 類 | AI 自評 |', '|---|---|---|']
            rows += [f'| {CLASS_RE.sub("", it).replace("|", "／")} | {m.group(1)} | |' for it, m in zip(items, tagged)]
            rows += ['', '### 審查重點（人）', '',
                     '<!-- AI 列出：〔關鍵決定〕要看的清單或位置（精簡版 0.2 的表）、AI 提出的決定、自評為「部分」或 ✗ 的完成標準；抽查那一列由審查者自選，AI 不預選 -->',
                     '| # | 要看的 | 在哪裡 | 審查者確認 |', '|---|---|---|---|',
                     '| 抽查 | （審查者自選 1～2 條 AI 自評 ✓ 的完成標準，寫出是哪幾條與結果） | | |']
        elif any(tagged):
            sys.exit(f'{path} 對應的完成標準只有部分標了類別')
        else:
            rows = ['| 完成標準 | AI 自評 | 審查者確認 |', '|---|---|---|']
            rows += [f'| {it.replace("|", "／")} | | |' for it in items]
        t = open(path, encoding='utf-8').read()
        if not pat.search(t):
            sys.exit(f'{path} 缺少 CHECKLIST 標記')
        t = pat.sub(lambda m: m.group(1) + '\n'.join(rows) + '\n' + m.group(2), t)
        open(path, 'w', encoding='utf-8').write(t)
    print('docs 已複製；範本檢查清單：', {p: len(sum((cl[s] for s in st), [])) for p, st in TEMPLATE_STEP.items()})

if __name__ == '__main__':
    main()
