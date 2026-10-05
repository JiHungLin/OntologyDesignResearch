#!/usr/bin/env python3
"""由宣告推導結構不變量。讀取 .build/（由 AI 從 Markdown 交付物轉出）。
用法：python tools/derive.py > .build/invariants.derived.yaml"""
import sys, yaml

BUILD = '.build'

def load(name, key):
    try:
        return (yaml.safe_load(open(f'{BUILD}/{name}')) or {}).get(key) or []
    except FileNotFoundError:
        return []

def main():
    if '--help' in sys.argv:
        print(__doc__); return 0
    rels = load('relations.yaml', 'relations')
    ents = load('entities.yaml', 'entities')
    sms  = load('flows.yaml', 'state_machines')
    cors = load('flows.yaml', 'corrections')
    out, n = [], 0

    def add(stmt, src):
        nonlocal n
        n += 1
        out.append({'id': f'INV-DRV-{n:03d}', 'class': 'derived',
                    'statement': stmt, 'derived_from': src})

    for r in rels:
        nm, dom = r['name'], r['domain']
        if r.get('functional'):
            add(f"同一個 {dom} 最多有一個 {nm}", f"{r['id']}.functional")
        card = r.get('cardinality', '')
        if card.startswith('1'):
            add(f"每個 {dom} 至少有一個 {nm}", f"{r['id']}.cardinality")
        if card.endswith('1'):
            add(f"{dom}.{nm} 不得超過一個", f"{r['id']}.cardinality")
        if card.startswith('0'):
            add(f"{dom} 可以沒有 {nm}，缺少不構成錯誤", f"{r['id']}.cardinality")
        t = r.get('temporal') or {}
        if t.get('constraint'):
            add(f"{nm} 須滿足 {t['constraint']}", f"{r['id']}.temporal")
        if t.get('valid_from') == 'required':
            add(f"{nm} 必須記錄生效起日", f"{r['id']}.temporal")
        if isinstance(r.get('range'), list):
            add(f"{dom}.{nm} 的對象只能屬於 {r['range']} 之一", f"{r['id']}.range-union")
        if r.get('inverse'):
            add(f"{nm} 與 {r['inverse']} 必須雙向一致", f"{r['id']}.inverse")
        if r.get('evidence_required'):
            add(f"缺少 {r['evidence_required']} 時 {nm} 不得成立", f"{r['id']}.evidence")

    for e in ents:
        if (e.get('lifecycle') or {}).get('ends_when'):
            add(f"{e['name']} 終止後不得新增 outgoing relation",
                f"{e.get('id', e['name'])}.lifecycle.ends_when")

    for sm in sms:
        ent = sm['entity']
        allowed = {(t['from'], t['to']) for t in sm['transitions']}
        add(f"{ent} 的狀態轉移只能是 {sorted(allowed)}", f"{ent}.transitions")
        for term in sm.get('terminal', []):
            add(f"{ent} 進入 {term} 後不得再轉移", f"{ent}.terminal")
        for t in sm['transitions']:
            if t.get('guard'):
                add(f"{ent} {t['from']}→{t['to']} 需滿足 {t['guard']}",
                    f"{ent}.guard")
            if t.get('authority'):
                add(f"{ent} {t['from']}→{t['to']} 需 {t['authority']} 權限",
                    f"{ent}.authority")

    for c in cors:
        stmt = f"{c['target']} 的更正只能經由 {c['action']}"
        if c.get('approved_by'):
            stmt += f"，且需 {c['approved_by']} 核准"
        add(stmt, f"corrections.{c['target']}")

    yaml.dump(out, sys.stdout, allow_unicode=True, sort_keys=False)
    print(f"\n# 共推導 {n} 條", file=sys.stderr)
    return 0

if __name__ == '__main__':
    sys.exit(main())
