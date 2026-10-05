#!/usr/bin/env python3
"""本體論宣告一致性檢查。讀取 .build/（由 AI 從 Markdown 交付物轉出）。
用法：python tools/check.py"""
import sys, yaml
from collections import defaultdict

BUILD = '.build'
TRIGGERS = {'actor', 'entity_change', 'external', 'time'}

def load(name, key):
    try:
        return (yaml.safe_load(open(f'{BUILD}/{name}')) or {}).get(key) or []
    except FileNotFoundError:
        return []

def main():
    if '--help' in sys.argv:
        print(__doc__); return 0
    cqs  = load('cq.yaml', 'competency_questions')
    ents = load('entities.yaml', 'entities')
    rels = load('relations.yaml', 'relations')
    evts = load('flows.yaml', 'events')
    rules = load('rules.yaml', 'rules')
    names = {e['name'] for e in ents}
    fails = []

    print("[多做了] 新增的 Entity 需有能力問題支撐（引用 core 與靜態替代除外）")
    for e in ents:
        if e.get('origin', 'new') == 'new' and not e.get('required_by_cq'):
            print(f"    ✗ {e['name']} 沒有任何能力問題引用"); fails.append('A')
    if 'A' not in fails: print("    ✓ 通過")

    print("\n[自我矛盾] Relation 的 domain/range 須已宣告")
    for r in rels:
        for side in ('domain', 'range'):
            targets = r[side] if isinstance(r[side], list) else [r[side]]
            for t in targets:
                if t not in names:
                    print(f"    ✗ {r['name']}.{side} = {t} 未宣告"); fails.append('B')
    if 'B' not in fails: print("    ✓ 通過")

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
    if 'C' not in fails: print("    ✓ 通過")

    print("\n[少做了] 能力問題的 subject 須能走到答案")
    adj = defaultdict(set)
    for r in rels:
        tgts = r['range'] if isinstance(r['range'], list) else [r['range']]
        for t in tgts:
            adj[r['domain']].add(t); adj[t].add(r['domain'])
    for cq in cqs:
        subj = cq.get('subject')
        want = cq['answer_type'].replace('list<','').replace('>','').strip()
        if want in ('decimal','boolean','timestamp','scalar') or want.startswith('struct'):
            continue   # 純值或結構型答案，不檢查路徑
        seen, stack = {subj}, [subj]
        while stack:
            for n in adj[stack.pop()] - seen:
                seen.add(n); stack.append(n)
        if want not in seen:
            print(f"    ✗ {cq['id']} subject={subj} 走不到 {want}"); fails.append('D')
    if 'D' not in fails: print("    ✓ 通過")

    print("\n[少做了] 每個事件須標觸發來源")
    for ev in evts:
        if ev.get('trigger') not in TRIGGERS:
            print(f"    ✗ {ev['name']} 的 trigger = {ev.get('trigger')}"); fails.append('E')
    if 'E' not in fails: print("    ✓ 通過")

    print("\n[寫的跟做的對不上] 規則判別的屬性須存得下")
    attrs = {f"{e['name']}.{a['name']}" for e in ents for a in (e.get('attributes') or [])}
    for r in rules:
        for d in r.get('discriminates') or []:
            if d not in attrs:
                print(f"    ✗ {r['id']} 判別 {d}，但 Entity 沒有這個屬性"); fails.append('F')
    if 'F' not in fails: print("    ✓ 通過")

    print(f"\n{'='*40}\n紅燈 {len(fails)} 項")
    return 1 if fails else 0

if __name__ == '__main__':
    sys.exit(main())
