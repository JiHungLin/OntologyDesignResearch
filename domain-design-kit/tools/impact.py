#!/usr/bin/env python3
"""列出修改某個 Entity 或 Relation 時，需要回歸檢查的項目。讀取 .build/。
用法：python tools/impact.py <Entity 或 Relation 名稱>"""
import sys, yaml

BUILD = '.build'

def load(name, key):
    try:
        return (yaml.safe_load(open(f'{BUILD}/{name}')) or {}).get(key) or []
    except FileNotFoundError:
        return []

def as_list(v):
    return v if isinstance(v, list) else ([v] if v else [])

def main():
    if len(sys.argv) != 2 or sys.argv[1] == '--help':
        print(__doc__); return 0
    name = sys.argv[1]
    cqs   = load('cq.yaml', 'competency_questions')
    ents  = load('entities.yaml', 'entities')
    rels  = load('relations.yaml', 'relations')
    sms   = load('flows.yaml', 'state_machines')
    evts  = load('flows.yaml', 'events')
    rules = load('rules.yaml', 'rules')
    maps  = load('mappings.yaml', 'mappings')

    ent = next((e for e in ents if e['name'] == name), None)
    rel = next((r for r in rels if r['name'] == name), None)
    if not ent and not rel:
        print(f"找不到 {name}"); return 1

    hits = {}
    def hit(stage, item): hits.setdefault(stage, []).append(item)

    if ent:
        for r in rels:
            if name == r['domain'] or name in as_list(r['range']):
                hit('② 關係', f"{r['id']} {r['name']}")
        cq_ids = set(ent.get('required_by_cq') or [])
    else:
        cq_ids = set(rel.get('enables_cq') or [])
        for side in [rel['domain']] + as_list(rel['range']):
            hit('② 兩端的 Entity', side)
    for c in cqs:
        if c['id'] in cq_ids or c.get('subject') == name or name in str(c.get('answer_type')):
            hit('① 驗收問題（⑥ 要重驗）', f"{c['id']} {c['question']}")
    for sm in sms:
        if sm['entity'] == name or any(name in str(t.get('guard', '')) for t in sm['transitions']):
            hit('③ 狀態機', sm['entity'])
    for ev in evts:
        if ev.get('subject') == name:
            hit('③ 事件', ev['name'])
    for r in rules:
        refs = as_list(r.get('applies_to')) + [d.split('.')[0] for d in as_list(r.get('discriminates'))]
        if name in refs or name in str(r.get('condition', '')):
            hit('④ 規則', r['id'])
    for m in maps:
        if m.get('entity') == name or m.get('relation') == name:
            hit('⑤ 對照', m.get('table') or m.get('foreign_key') or m.get('implementation'))

    print(f"修改 {name} 時要回歸檢查：")
    for stage in sorted(hits):
        print(f"\n[{stage}]")
        for i in hits[stage]: print(f"    - {i}")
    if not hits: print("    （沒有找到引用，請確認宣告是否完整）")
    return 0

if __name__ == '__main__':
    sys.exit(main())
