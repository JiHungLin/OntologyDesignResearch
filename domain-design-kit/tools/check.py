#!/usr/bin/env python3
"""本體論宣告一致性檢查（結構檢查）。讀取 .build/（由 tools/md2build.py 從 Markdown 交付物轉出）。
用法：python tools/check.py [--step N]
  --step N：目前做到第 N 步（1～6）。這一步之前應有的 .build/ 檔案缺少時亮紅燈。
只檢查結構對不對得起來，不檢查內容是否正確。"""
import os, sys, yaml
from collections import defaultdict

BUILD = '.build'
TRIGGERS = {'actor', 'entity_change', 'external', 'time'}
# 做到第 N 步時，.build/ 應該要有的檔案（第 ⑤ 步之後與第 ④ 步相同）
REQUIRED = {1: ['cq.yaml'],
            2: ['entities.yaml', 'relations.yaml', 'glossary.yaml'],
            3: ['flows.yaml'],
            4: ['rules.yaml']}

def load(name, key):
    """回傳 (資料, 檔案是否存在)。"""
    try:
        return (yaml.safe_load(open(f'{BUILD}/{name}')) or {}).get(key) or [], True
    except FileNotFoundError:
        return [], False

def main():
    if '--help' in sys.argv:
        print(__doc__); return 0
    step = None
    if '--step' in sys.argv:
        step = int(sys.argv[sys.argv.index('--step') + 1])
    cqs, has_cq   = load('cq.yaml', 'competency_questions')
    ents, has_ent = load('entities.yaml', 'entities')
    rels, has_rel = load('relations.yaml', 'relations')
    evts, has_flo = load('flows.yaml', 'events')
    rules, has_rul = load('rules.yaml', 'rules')
    names = {e['name'] for e in ents}
    fails, skipped = [], []

    def result(code, count, unit, missing=None, empty='沒有資料'):
        """印出一項的結果。missing：缺少的檔案；count 為 0 時視為未檢查。"""
        if missing:
            print(f"    – 未檢查（缺 {BUILD}/{'、'.join(missing)}）"); skipped.append(code)
        elif count == 0:
            print(f"    – 未檢查（{empty}）"); skipped.append(code)
        elif code not in fails:
            print(f"    ✓ 通過（檢查了 {count} {unit}）")
        else:
            print(f"    （檢查了 {count} {unit}）")

    def missing(*pairs):
        return [n for n, ok in pairs if not ok]

    if step:
        print(f"[檔案] 做到第 {step} 步時應有的 {BUILD}/ 檔案")
        need = [f for s in range(1, min(step, 4) + 1) for f in REQUIRED[s]]
        absent = [f for f in need if not os.path.exists(f'{BUILD}/{f}')]
        for f in absent:
            print(f"    ✗ 缺 {BUILD}/{f}"); fails.append('檔案')
        if not absent: print(f"    ✓ 通過（{len(need)} 個檔案都在）")
        print()

    print("[多做了] 新增的 Entity 需有能力問題支撐（引用 core 與靜態替代除外）")
    new_ents = [e for e in ents if e.get('origin', 'new') == 'new']
    for e in new_ents:
        if not e.get('required_by_cq'):
            print(f"    ✗ {e['name']} 沒有任何能力問題引用"); fails.append('A')
    result('A', len(new_ents), '個新增 Entity', missing(('entities.yaml', has_ent)))

    print("\n[自我矛盾] Relation 的 domain/range 須已宣告")
    for r in rels:
        for side in ('domain', 'range'):
            targets = r[side] if isinstance(r[side], list) else [r[side]]
            for t in targets:
                if t not in names:
                    print(f"    ✗ {r['name']}.{side} = {t} 未宣告"); fails.append('B')
    result('B', len(rels), '條關係',
           missing(('entities.yaml', has_ent), ('relations.yaml', has_rel)))

    print("\n[少做了] 子類須對適用集表態")
    by_parent = defaultdict(list)
    for e in ents:
        if e.get('parent'): by_parent[e['parent']].append(e)
    for parent, kids in by_parent.items():
        applicable = set()
        for k in kids:
            applicable |= {x for x in (k.get('relations') or {})
                           if not x.endswith('_reason')}
        for k in kids:
            for a in applicable - set(k.get('relations') or {}):
                print(f"    ✗ {k['name']} 未對 {a} 表態"); fails.append('C')
    kids_count = sum(len(k) for k in by_parent.values())
    if has_ent and kids_count == 0:
        print("    – 不適用（沒有子類）")
    else:
        result('C', kids_count, '個子類', missing(('entities.yaml', has_ent)))

    print("\n[少做了] 能力問題的 subject 須能走到答案")
    adj = defaultdict(set)
    for r in rels:
        tgts = r['range'] if isinstance(r['range'], list) else [r['range']]
        for t in tgts:
            adj[r['domain']].add(t); adj[t].add(r['domain'])
    walked, untyped = 0, 0
    for cq in cqs:
        subj = cq.get('subject')
        if not subj or not cq.get('answer_type'):
            untyped += 1; continue   # Markdown 沒有這兩欄，要另外補上才檢查得了
        want = cq['answer_type'].replace('list<','').replace('>','').strip()
        if want in ('decimal','boolean','timestamp','scalar') or want.startswith('struct'):
            continue   # 純值或結構型答案，不檢查路徑
        walked += 1
        seen, stack = {subj}, [subj]
        while stack:
            for n in adj[stack.pop()] - seen:
                seen.add(n); stack.append(n)
        if want not in seen:
            print(f"    ✗ {cq['id']} subject={subj} 走不到 {want}"); fails.append('D')
    if untyped:
        print(f"    – {untyped} 個能力問題沒有 subject 或 answer_type，未檢查")
    result('D', walked, '個能力問題',
           missing(('cq.yaml', has_cq), ('relations.yaml', has_rel)),
           empty='沒有能力問題寫了 subject 與 answer_type' if untyped else '沒有答案是 Entity 的能力問題')

    print("\n[少做了] 每個事件須標觸發來源")
    for ev in evts:
        if ev.get('trigger') not in TRIGGERS:
            print(f"    ✗ {ev['name']} 的 trigger = {ev.get('trigger')}"); fails.append('E')
    result('E', len(evts), '個事件', missing(('flows.yaml', has_flo)))

    print("\n[寫的跟做的對不上] 規則判別的屬性須存得下")
    attrs = {f"{e['name']}.{a['name']}" for e in ents for a in (e.get('attributes') or [])}
    refs = 0
    for r in rules:
        for d in r.get('discriminates') or []:
            refs += 1
            if d not in attrs:
                print(f"    ✗ {r['id']} 判別 {d}，但 Entity 沒有這個屬性"); fails.append('F')
    result('F', refs, '個屬性引用',
           missing(('entities.yaml', has_ent), ('rules.yaml', has_rul)),
           empty='規則都沒有寫判別的屬性')

    print(f"\n{'='*40}")
    print(f"結構檢查：紅燈 {len(fails)} 項、未檢查 {len(skipped)} 項")
    print("只代表結構對得起來，不代表內容正確。規則條件寫錯、與法條原文不符、"
          "狀態轉換漏了情況，要靠挑錯與審查。")
    return 1 if fails else 0

if __name__ == '__main__':
    sys.exit(main())
