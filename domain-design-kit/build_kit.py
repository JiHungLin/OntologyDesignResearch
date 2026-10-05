#!/usr/bin/env python3
"""從研究資料夾重建設計工具包：複製規範文件到 docs/，並把精簡版各步驟的完成標準寫進範本的「檢查紀錄」。
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
        rows = ['| 完成標準 | AI 自評 | 審查者確認 |', '|---|---|---|']
        for st in steps:
            rows += [f'| {it.replace("|", "／")} | | |' for it in cl[st]]
        t = open(path, encoding='utf-8').read()
        if not pat.search(t):
            sys.exit(f'{path} 缺少 CHECKLIST 標記')
        t = pat.sub(lambda m: m.group(1) + '\n'.join(rows) + '\n' + m.group(2), t)
        open(path, 'w', encoding='utf-8').write(t)
    print('docs 已複製；範本檢查清單：', {p: len(sum((cl[s] for s in st), [])) for p, st in TEMPLATE_STEP.items()})

if __name__ == '__main__':
    main()
